from django.test import TestCase

from routing.models import FuelStation
from routing.services.fuel_optimizer import RoutePolyline, match_stations_to_route


class MatchStationsToRouteTests(TestCase):
    def setUp(self):
        # A simple straight-line "route" heading east along latitude 35.0,
        # from lon -100 to lon -90 (~500 miles at this latitude).
        self.geometry = [[35.0, lon / 10.0] for lon in range(-1000, -899, 5)]
        self.polyline = RoutePolyline.from_geometry(self.geometry)

        FuelStation.objects.create(
            opis_truckstop_id=1, name="On route", city="A", state="OK",
            price_per_gallon="3.00", latitude=35.0, longitude=-95.0, geocoded=True,
        )
        FuelStation.objects.create(
            opis_truckstop_id=2, name="Far away", city="B", state="TX",
            price_per_gallon="2.50", latitude=25.0, longitude=-95.0, geocoded=True,
        )
        FuelStation.objects.create(
            opis_truckstop_id=3, name="Ungeocoded", city="C", state="OK",
            price_per_gallon="2.80", latitude=None, longitude=None, geocoded=False,
        )

    def test_matches_only_stations_within_corridor(self):
        matched = match_stations_to_route(
            FuelStation.objects.filter(geocoded=True), self.polyline, corridor_miles=10
        )
        names = {m.name for m in matched}
        self.assertIn("On route", names)
        self.assertNotIn("Far away", names)

    def test_position_along_route_is_reasonable(self):
        matched = match_stations_to_route(
            FuelStation.objects.filter(geocoded=True), self.polyline, corridor_miles=10
        )
        on_route = next(m for m in matched if m.name == "On route")
        # Station is at lon -95, roughly halfway between -100 and -90.
        self.assertGreater(on_route.position_along_route_miles, 0)
        self.assertLess(on_route.position_along_route_miles, self.polyline.total_miles)
