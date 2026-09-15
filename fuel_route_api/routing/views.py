import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FuelStation
from .serializers import RoutePlanRequestSerializer, RoutePlanResponseSerializer
from .services import fuel_optimizer, geocoding, routing_client

logger = logging.getLogger(__name__)


def _cache_key(prefix, *parts):
    raw = "|".join(str(p).strip().lower() for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"{prefix}:{digest}"


class RoutePlanView(APIView):
    """
    POST /api/v1/route/

    Body:
        {
            "start": "Los Angeles, CA",
            "finish": "New York, NY",
            "range_miles": 500,   // optional, defaults to settings.VEHICLE_RANGE_MILES
            "mpg": 10             // optional, defaults to settings.VEHICLE_MPG
        }

    Returns the driving route (geometry + distance/duration), a viewable
    static map URL, the optimal sequence of fuel stops along the route,
    and the total projected fuel spend.

    Per-request external API usage: exactly one Nominatim geocode call per
    location not already cached (2 max) and exactly one OSRM routing call.
    Both the geocoding and full route-plan results are cached, so a
    repeated (start, finish) pair returns instantly with zero external
    calls on subsequent requests.
    """

    def post(self, request):
        req = RoutePlanRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        data = req.validated_data

        plan_key = _cache_key("plan", data["start"], data["finish"], data["range_miles"], data["mpg"])
        cached_response = cache.get(plan_key)
        if cached_response is not None:
            return Response(cached_response)

        start_geo = geocoding.geocode_address(data["start"])
        finish_geo = geocoding.geocode_address(data["finish"])

        route_key = _cache_key(
            "route", start_geo["latitude"], start_geo["longitude"], finish_geo["latitude"], finish_geo["longitude"]
        )
        route = cache.get(route_key)
        if route is None:
            route = routing_client.get_route(
                start_geo["latitude"], start_geo["longitude"], finish_geo["latitude"], finish_geo["longitude"]
            )
            cache.set(route_key, route, settings.ROUTE_CACHE_TTL)

        polyline = fuel_optimizer.RoutePolyline.from_geometry(route["geometry"])

        stations_qs = FuelStation.objects.filter(geocoded=True)
        matched = fuel_optimizer.match_stations_to_route(stations_qs, polyline, settings.ROUTE_CORRIDOR_MILES)

        plan = fuel_optimizer.plan_fuel_stops(
            matched_stations=matched,
            total_distance_miles=polyline.total_miles,
            range_miles=data["range_miles"],
            mpg=data["mpg"],
        )

        map_url = fuel_optimizer.build_static_map_url(polyline, plan.stops, start_geo, finish_geo)

        payload = {
            "start": {"query": data["start"], **start_geo},
            "finish": {"query": data["finish"], **finish_geo},
            "distance_miles": round(polyline.total_miles, 1),
            "duration_hours": round(route["duration_seconds"] / 3600, 2),
            "vehicle": {"range_miles": data["range_miles"], "mpg": data["mpg"]},
            "route_geometry": route["geometry"],
            "map_image_url": map_url,
            "fuel_stops": [
                {
                    "name": s.name,
                    "city": s.city,
                    "state": s.state,
                    "address": s.address,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "price_per_gallon": s.price_per_gallon,
                    "position_along_route_miles": s.position_along_route_miles,
                    "distance_from_route_miles": s.distance_from_route_miles,
                    "gallons_purchased": s.gallons_purchased,
                    "cost": s.cost,
                }
                for s in plan.stops
            ],
            "total_fuel_stops": len(plan.stops),
            "total_gallons_purchased": plan.total_gallons,
            "total_fuel_cost_usd": plan.total_cost,
            "assumptions": [
                "Vehicle starts at `start` with a full tank, so no purchase is required until "
                "range is exhausted.",
                f"Vehicle range is {data['range_miles']:.0f} miles per full tank and it achieves "
                f"{data['mpg']:.1f} miles per gallon.",
                "Fuel stations are matched within "
                f"{settings.ROUTE_CORRIDOR_MILES:.0f} miles of the driving route and their "
                "coordinates are city-level (geocoded from city/state, not the exact exit address).",
                "Prices are taken as-is from the supplied fuel price dataset and are not adjusted "
                "for date or inflation.",
            ],
        }

        resp = RoutePlanResponseSerializer(payload)
        cache.set(plan_key, resp.data, settings.PLAN_CACHE_TTL)
        return Response(resp.data)
