from django.test import SimpleTestCase

from routing.exceptions import RouteInfeasibleError
from routing.services.fuel_optimizer import MatchedStation, plan_fuel_stops


def station(id, position, price):
    return MatchedStation(
        id=id, name=f"Station {id}", city="City", state="ST", address="",
        price_per_gallon=price, latitude=0.0, longitude=0.0,
        distance_from_route_miles=1.0, position_along_route_miles=position,
    )


class PlanFuelStopsTests(SimpleTestCase):
    RANGE = 500
    MPG = 10

    def test_no_stops_needed_within_range(self):
        stations = [station(1, 100, 3.00)]
        plan = plan_fuel_stops(stations, total_distance_miles=400, range_miles=self.RANGE, mpg=self.MPG)
        self.assertEqual(plan.stops, [])
        self.assertEqual(plan.total_cost, 0.0)
        self.assertEqual(plan.total_gallons, 0.0)

    def test_single_stop_buys_exactly_enough_to_finish(self):
        # 600 mile trip, one station at mile 450. Vehicle arrives with
        # 50 miles of range left (500-450), needs 150 more miles to finish
        # (600-450), so must buy (150-50)/10 = 10 gallons.
        stations = [station(1, 450, 3.50)]
        plan = plan_fuel_stops(stations, total_distance_miles=600, range_miles=self.RANGE, mpg=self.MPG)
        self.assertEqual(len(plan.stops), 1)
        self.assertAlmostEqual(plan.stops[0].gallons_purchased, 10.0)
        self.assertAlmostEqual(plan.total_cost, 35.0)

    def test_prefers_cheaper_station_and_buys_minimal_at_pricier_one(self):
        # 900 mile trip. Station A (expensive) at mile 450 -- the only stop
        # reachable on the initial full tank. Station B (cheap) at mile 550
        # is reachable from A (450+500=950 >= 550) and is cheaper, so the
        # vehicle should top off just enough AT A to reach B, then buy the
        # rest of the trip's fuel at B's cheaper price.
        stations = [station(1, 450, 4.00), station(2, 550, 2.50)]
        plan = plan_fuel_stops(stations, total_distance_miles=900, range_miles=self.RANGE, mpg=self.MPG)

        self.assertEqual([s.id for s in plan.stops], [1, 2])
        # Arrive at A with 500-450=50mi range left; need 100mi to reach B;
        # buy (100-50)/10 = 5 gallons at A's (expensive) price.
        self.assertAlmostEqual(plan.stops[0].gallons_purchased, 5.0)
        self.assertAlmostEqual(plan.stops[0].cost, 20.0)
        # B supplies the rest of the trip at the cheaper price.
        self.assertGreater(plan.stops[1].gallons_purchased, 0)
        self.assertAlmostEqual(plan.total_cost, sum(s.cost for s in plan.stops))

    def test_fills_full_when_no_cheaper_station_within_reach(self):
        # 1000 mile trip. Station A at mile 100 (cheap), Station B at mile
        # 550 (more expensive, but the only option reachable from A).
        # Since B isn't cheaper than A, the vehicle should fill up fully
        # at A before heading to B.
        stations = [station(1, 100, 3.00), station(2, 550, 3.50)]
        plan = plan_fuel_stops(stations, total_distance_miles=1000, range_miles=self.RANGE, mpg=self.MPG)
        self.assertEqual([s.id for s in plan.stops], [1, 2])
        # Arrive at A with 500-100=400mi range left; topping off to a full
        # 500mi tank means buying (500-400)/10 = 10 gallons.
        self.assertAlmostEqual(plan.stops[0].gallons_purchased, 10.0)

    def test_skips_reaching_destination_without_an_unnecessary_stop(self):
        # 600 mile trip with a station at mile 450 that's reachable, and
        # the destination itself is also reachable from mile 450
        # (450+500=950 >= 600) -- confirms the loop terminates via the
        # "destination reachable, no more stops needed" path rather than
        # incorrectly requiring another station.
        stations = [station(1, 450, 3.50)]
        plan = plan_fuel_stops(stations, total_distance_miles=600, range_miles=self.RANGE, mpg=self.MPG)
        self.assertEqual(len(plan.stops), 1)

    def test_infeasible_gap_raises(self):
        # No station within 500 miles of the start on a 1000 mile trip.
        stations = [station(1, 600, 3.00)]
        with self.assertRaises(RouteInfeasibleError):
            plan_fuel_stops(stations, total_distance_miles=1000, range_miles=self.RANGE, mpg=self.MPG)

    def test_total_cost_matches_sum_of_stop_costs(self):
        stations = [station(1, 200, 3.10), station(2, 650, 2.90), station(3, 1100, 3.40)]
        plan = plan_fuel_stops(stations, total_distance_miles=1400, range_miles=self.RANGE, mpg=self.MPG)
        self.assertAlmostEqual(plan.total_cost, round(sum(s.cost for s in plan.stops), 2))
        self.assertAlmostEqual(plan.total_gallons, round(sum(s.gallons_purchased for s in plan.stops), 3))
