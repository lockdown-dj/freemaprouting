from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from routing.models import FuelStation


class RoutePlanViewTests(TestCase):
    def setUp(self):
        cache.clear()
        # A ~690 mile straight "route" along latitude 35.0 (roughly OSRM's
        # geometry shape: a list of [lat, lon] points).
        self.fake_geometry = [[35.0, lon / 10.0] for lon in range(-1000, -890, 2)]
        self.fake_route = {
            "distance_miles": 690.0,
            "duration_seconds": 3600 * 10,
            "geometry": self.fake_geometry,
        }

        FuelStation.objects.create(
            opis_truckstop_id=1, name="Cheap Stop", city="Midway", state="OK",
            price_per_gallon="2.50", latitude=35.0, longitude=-96.0, geocoded=True,
        )
        FuelStation.objects.create(
            opis_truckstop_id=2, name="Pricey Stop", city="Nearstart", state="TX",
            price_per_gallon="4.00", latitude=35.0, longitude=-99.5, geocoded=True,
        )

    @patch("routing.views.routing_client.get_route")
    @patch("routing.views.geocoding.geocode_address")
    def test_route_plan_happy_path(self, mock_geocode, mock_route):
        mock_geocode.side_effect = [
            {"latitude": 35.0, "longitude": -100.0, "display_name": "Start, USA"},
            {"latitude": 35.0, "longitude": -89.0, "display_name": "Finish, USA"},
        ]
        mock_route.return_value = self.fake_route

        response = self.client.post(
            reverse("route-plan"),
            data={"start": "Start City", "finish": "Finish City", "range_miles": 500, "mpg": 10},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Reported distance is computed from the route geometry itself
        # (consistent with how fuel-stop positions are measured), not
        # OSRM's separately-reported figure -- see RoutePolyline.
        self.assertGreater(body["distance_miles"], 500)
        self.assertGreaterEqual(body["total_fuel_stops"], 1)
        self.assertGreater(body["total_fuel_cost_usd"], 0)
        self.assertIn("map_image_url", body)
        self.assertTrue(body["map_image_url"].startswith("https://www.openstreetmap.org/directions"))
        # Cheapest reachable station should be preferred over the pricier one.
        stop_names = [s["name"] for s in body["fuel_stops"]]
        self.assertIn("Cheap Stop", stop_names)

        # Second identical request should hit the plan cache: geocode/route
        # mocks should NOT be called again.
        mock_geocode.reset_mock()
        mock_route.reset_mock()
        response2 = self.client.post(
            reverse("route-plan"),
            data={"start": "Start City", "finish": "Finish City", "range_miles": 500, "mpg": 10},
            content_type="application/json",
        )
        self.assertEqual(response2.status_code, 200)
        mock_geocode.assert_not_called()
        mock_route.assert_not_called()

    def test_same_start_and_finish_is_rejected(self):
        response = self.client.post(
            reverse("route-plan"),
            data={"start": "Chicago, IL", "finish": "Chicago, IL"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("routing.views.geocoding.geocode_address")
    def test_geocoding_failure_returns_422(self, mock_geocode):
        from routing.exceptions import GeocodingError

        mock_geocode.side_effect = GeocodingError("Could not find a location matching 'Nowhereville'.")
        response = self.client.post(
            reverse("route-plan"),
            data={"start": "Nowhereville", "finish": "Chicago, IL"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.json())
