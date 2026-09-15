"""
Core domain logic: given a route's polyline geometry and a queryset of
candidate fuel stations, decide

  (a) which stations actually lie "along" the route (the corridor filter), and
  (b) where to stop and how much fuel to buy at each stop, to minimize total
      spend, without ever exceeding the vehicle's max range between fill-ups
      (the fuel-stop optimizer).

Both steps run entirely in-process against data already pulled from the
database / a single OSRM response -- no external API calls happen here,
which is what keeps this service fast and keeps per-request calls to the
routing API down to exactly one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote

import numpy as np

from routing.exceptions import RouteInfeasibleError

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lon1, lat2, lon2):
    """Vectorized (numpy-friendly) great-circle distance in miles."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


@dataclass
class RoutePolyline:
    """A route's shape points plus cumulative distance travelled at each point."""

    lat: np.ndarray
    lon: np.ndarray
    cumulative_miles: np.ndarray

    @classmethod
    def from_geometry(cls, geometry_lat_lon):
        lat = np.array([p[0] for p in geometry_lat_lon], dtype=float)
        lon = np.array([p[1] for p in geometry_lat_lon], dtype=float)
        if len(lat) < 2:
            cumulative = np.zeros(len(lat))
        else:
            seg_miles = haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])
            cumulative = np.concatenate([[0.0], np.cumsum(seg_miles)])
        return cls(lat=lat, lon=lon, cumulative_miles=cumulative)

    @property
    def total_miles(self):
        return float(self.cumulative_miles[-1]) if len(self.cumulative_miles) else 0.0

    @property
    def bounds(self):
        """(min_lat, max_lat, min_lon, max_lon)"""
        return float(self.lat.min()), float(self.lat.max()), float(self.lon.min()), float(self.lon.max())


@dataclass
class MatchedStation:
    id: int
    name: str
    city: str
    state: str
    address: str
    price_per_gallon: float
    latitude: float
    longitude: float
    distance_from_route_miles: float
    position_along_route_miles: float


@dataclass
class FuelStop(MatchedStation):
    gallons_purchased: float = 0.0
    cost: float = 0.0


@dataclass
class FuelPlan:
    stops: list[FuelStop] = field(default_factory=list)
    total_distance_miles: float = 0.0
    total_gallons: float = 0.0
    total_cost: float = 0.0
    starting_tank_gallons: float = 0.0


def bounding_box_prefilter(stations_qs, polyline: RoutePolyline, corridor_miles: float):
    """
    Cheap first pass: only consider stations whose lat/lon falls inside the
    route's bounding box, expanded by the corridor buffer. This is done as
    a plain DB range query so it uses the lat/lon index and avoids pulling
    every geocoded station into Python before the more expensive precise
    distance check.
    """
    min_lat, max_lat, min_lon, max_lon = polyline.bounds
    # ~69 miles per degree of latitude; longitude degrees shrink with
    # latitude, so pad generously rather than computing an exact cosine
    # correction -- this is a coarse prefilter, precision is handled next.
    lat_pad = corridor_miles / 69.0
    lon_pad = corridor_miles / 45.0

    return stations_qs.filter(
        latitude__gte=min_lat - lat_pad,
        latitude__lte=max_lat + lat_pad,
        longitude__gte=min_lon - lon_pad,
        longitude__lte=max_lon + lon_pad,
    )


def match_stations_to_route(stations_qs, polyline: RoutePolyline, corridor_miles: float) -> list[MatchedStation]:
    """
    Precise pass: for each candidate station, find its minimum distance to
    any point on the route polyline (vectorized with numpy -- fast even for
    a few thousand candidates against a few thousand route points) and its
    approximate position along the route (the cumulative distance at the
    nearest polyline point). Stations farther than `corridor_miles` from
    the route are dropped.
    """
    candidates = list(bounding_box_prefilter(stations_qs, polyline, corridor_miles))
    if not candidates:
        return []

    station_lat = np.array([s.latitude for s in candidates])
    station_lon = np.array([s.longitude for s in candidates])

    # distances[i, j] = distance from station i to polyline point j
    distances = haversine_miles(
        station_lat[:, None], station_lon[:, None], polyline.lat[None, :], polyline.lon[None, :]
    )
    nearest_point_idx = np.argmin(distances, axis=1)
    nearest_distance = distances[np.arange(len(candidates)), nearest_point_idx]

    matched = []
    for i, station in enumerate(candidates):
        if nearest_distance[i] <= corridor_miles:
            matched.append(
                MatchedStation(
                    id=station.id,
                    name=station.name,
                    city=station.city,
                    state=station.state,
                    address=station.address,
                    price_per_gallon=float(station.price_per_gallon),
                    latitude=station.latitude,
                    longitude=station.longitude,
                    distance_from_route_miles=round(float(nearest_distance[i]), 2),
                    position_along_route_miles=round(float(polyline.cumulative_miles[nearest_point_idx[i]]), 2),
                )
            )
    return matched


def _cheapest_dedup_by_position(matched: list[MatchedStation], cluster_miles: float = 1.0) -> list[MatchedStation]:
    """
    Multiple stations often sit at essentially the same highway exit. Keep
    only the cheapest one per ~cluster_miles cluster along the route so the
    optimizer isn't choosing between near-duplicates.
    """
    ordered = sorted(matched, key=lambda s: s.position_along_route_miles)
    deduped: list[MatchedStation] = []
    for station in ordered:
        if deduped and abs(station.position_along_route_miles - deduped[-1].position_along_route_miles) <= cluster_miles:
            if station.price_per_gallon < deduped[-1].price_per_gallon:
                deduped[-1] = station
        else:
            deduped.append(station)
    return deduped


def plan_fuel_stops(
    matched_stations: list[MatchedStation],
    total_distance_miles: float,
    range_miles: float,
    mpg: float,
) -> FuelPlan:
    """
    Greedy optimal fuel-purchase plan (continuous / fractional purchases,
    single tank of capacity `range_miles`, start full).

    At any point where a purchase decision is made, look ahead at every
    station reachable on a full tank from here. If a cheaper-or-equal
    priced station is reachable, buy only the fuel needed to get there
    (minimizing gallons bought at the current, pricier stop). Otherwise
    -- this is the cheapest fuel available before running out of range --
    fill the tank completely and drive to the cheapest station within the
    new (full-tank) reach.

    This is the standard optimal greedy for the bounded-tank, continuous-
    purchase, price-varies-by-stop fuel cost minimization problem.
    """
    tank_capacity_miles = range_miles
    stations = _cheapest_dedup_by_position(matched_stations)

    plan = FuelPlan(total_distance_miles=total_distance_miles, starting_tank_gallons=tank_capacity_miles / mpg)

    position = 0.0
    fuel_range_remaining = tank_capacity_miles  # start with a full tank
    current_price = None  # price at `position`, if we are standing at a station

    def window_after(pos, max_pos):
        return [s for s in stations if pos < s.position_along_route_miles <= max_pos]

    def charge_current_stop(gallons):
        plan.stops[-1].gallons_purchased += gallons
        plan.stops[-1].cost += gallons * current_price
        plan.total_gallons += gallons
        plan.total_cost += gallons * current_price

    guard = 0
    while position + fuel_range_remaining < total_distance_miles - 1e-6:
        guard += 1
        if guard > 2000:
            raise RouteInfeasibleError("Fuel planning did not converge; route may be malformed.")

        max_reach = position + tank_capacity_miles
        window = window_after(position, max_reach)
        destination_reachable = max_reach >= total_distance_miles - 1e-6

        if not window and not destination_reachable:
            raise RouteInfeasibleError(
                f"No fuel station is reachable within {tank_capacity_miles:.0f} miles of mile "
                f"{position:.0f} on this route, so the {total_distance_miles:.0f}-mile trip "
                "cannot be completed with the assumed vehicle range."
            )

        cheapest_in_window = min(window, key=lambda s: s.price_per_gallon) if window else None

        if (
            current_price is not None
            and cheapest_in_window is not None
            and cheapest_in_window.price_per_gallon < current_price
        ):
            # A cheaper station is ahead: buy only what's needed to reach it.
            target = cheapest_in_window
            distance_to_target = target.position_along_route_miles - position
            gallons_needed = max(0.0, distance_to_target - fuel_range_remaining) / mpg
            if gallons_needed > 0:
                charge_current_stop(gallons_needed)
                fuel_range_remaining += gallons_needed * mpg
        elif destination_reachable:
            # No station ahead is cheaper than here, but the destination
            # itself is reachable on a full tank from here: no more stops
            # are needed, just enough fuel to finish. Let the final-leg
            # top-up below (after the loop) handle the exact amount.
            break
        else:
            # Nothing cheaper within reach and the destination is still out
            # of reach: this is the best price available before running out
            # of range (or we're still at the start), so fill all the way
            # up, then drive to the cheapest reachable stop.
            target = cheapest_in_window
            if current_price is not None:
                fill_gallons = (tank_capacity_miles - fuel_range_remaining) / mpg
                if fill_gallons > 0:
                    charge_current_stop(fill_gallons)
                    fuel_range_remaining = tank_capacity_miles

        # Drive to the chosen target station.
        distance_travelled = target.position_along_route_miles - position
        fuel_range_remaining -= distance_travelled
        position = target.position_along_route_miles
        current_price = target.price_per_gallon

        plan.stops.append(
            FuelStop(
                id=target.id,
                name=target.name,
                city=target.city,
                state=target.state,
                address=target.address,
                price_per_gallon=target.price_per_gallon,
                latitude=target.latitude,
                longitude=target.longitude,
                distance_from_route_miles=target.distance_from_route_miles,
                position_along_route_miles=target.position_along_route_miles,
                gallons_purchased=0.0,
                cost=0.0,
            )
        )

    # Final leg: if we made at least one stop, buy just enough fuel at the
    # last stop to cover the remaining distance to the destination (no
    # need to top up further than that).
    if plan.stops:
        distance_remaining = total_distance_miles - position
        gallons_needed = max(0.0, distance_remaining - fuel_range_remaining) / mpg
        if gallons_needed > 0:
            charge_current_stop(gallons_needed)

    plan.total_gallons = round(plan.total_gallons, 3)
    plan.total_cost = round(plan.total_cost, 2)
    for stop in plan.stops:
        stop.gallons_purchased = round(stop.gallons_purchased, 3)
        stop.cost = round(stop.cost, 2)

    return plan


def build_static_map_url(polyline: RoutePolyline, stops: list[FuelStop], start, finish):
    """
    Builds a viewable URL so the route can be eyeballed straight from a
    browser/Postman, on top of the raw GeoJSON geometry returned for
    programmatic map rendering. This costs zero extra API calls -- it's
    just a URL, not fetched server-side.

    Deep-links into OpenStreetMap's own directions page (their main site,
    not a third-party static-image mirror -- an earlier version of this used
    the community-run staticmap.openstreetmap.de renderer, which has since
    gone offline). Trade-off: no fuel-stop pins, just the start/finish route.
    """
    route = f"{start['latitude']},{start['longitude']};{finish['latitude']},{finish['longitude']}"
    return f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={quote(route, safe='')}"
