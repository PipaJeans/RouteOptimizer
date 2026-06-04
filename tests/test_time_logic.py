import random
import unittest
from datetime import datetime

from app.algorithms.GA import genetic_algorithm
from app.algorithms.NN import nearest_neighbor
from app.models import Point


def mk_point(pid, fixed_order=None, time_from=None, time_to=None, service_time=0, asap=False):
    return Point(
        id=pid,
        address=pid,
        lat=55.0,
        lon=37.0,
        time_from=time_from,
        time_to=time_to,
        service_time=service_time,
        fixed_order=fixed_order,
        asap=asap,
    )


class RouteLogicTests(unittest.TestCase):
    def setUp(self):
        random.seed(42)

    def test_ga_no_false_wait_inside_window(self):
        points = [
            mk_point("S", fixed_order=0),
            mk_point("A", fixed_order=1, time_from=9 * 60, time_to=18 * 60),
        ]
        dist = {"S-A": (1000, 3600)}

        result = genetic_algorithm(
            points=points,
            dist_matrix=dist,
            departure_time=datetime(2026, 1, 1, 9, 0, 0),
            route_type="open",
            optimization_type="time",
            max_driving_hours=10.0,
        )

        self.assertEqual(result["total_time_seconds"], 3600)

    def test_ga_midnight_wait_daily_window(self):
        points = [
            mk_point("S", fixed_order=0),
            mk_point("A", fixed_order=1, time_from=9 * 60, time_to=18 * 60),
        ]
        dist = {"S-A": (1000, 2 * 3600)}

        result = genetic_algorithm(
            points=points,
            dist_matrix=dist,
            departure_time=datetime(2026, 1, 1, 23, 30, 0),
            route_type="open",
            optimization_type="time",
            max_driving_hours=10.0,
        )

        self.assertEqual(result["total_time_seconds"], 34200)

    def test_ga_12h_rest_scenarios(self):
        points_exact = [
            mk_point("S", fixed_order=0),
            mk_point("A", fixed_order=1),
            mk_point("B", fixed_order=2),
        ]
        dist_exact = {"S-A": (1000, 6 * 3600), "A-B": (1000, 4 * 3600)}

        result_exact = genetic_algorithm(
            points=points_exact,
            dist_matrix=dist_exact,
            departure_time=datetime(2026, 1, 1, 0, 0, 0),
            route_type="open",
            optimization_type="time",
            max_driving_hours=10.0,
        )
        self.assertEqual(result_exact["total_time_seconds"], 10 * 3600)

        points_exceed = [
            mk_point("S", fixed_order=0),
            mk_point("A", fixed_order=1),
            mk_point("B", fixed_order=2),
        ]
        dist_exceed = {"S-A": (1000, 8 * 3600), "A-B": (1000, 4 * 3600)}

        result_exceed = genetic_algorithm(
            points=points_exceed,
            dist_matrix=dist_exceed,
            departure_time=datetime(2026, 1, 1, 0, 0, 0),
            route_type="open",
            optimization_type="time",
            max_driving_hours=10.0,
        )
        self.assertEqual(result_exceed["total_time_seconds"], 24 * 3600)

        points_under = [
            mk_point("S", fixed_order=0),
            mk_point("A", fixed_order=1),
            mk_point("B", fixed_order=2),
        ]
        dist_under = {"S-A": (1000, 5 * 3600), "A-B": (1000, 4 * 3600)}

        result_under = genetic_algorithm(
            points=points_under,
            dist_matrix=dist_under,
            departure_time=datetime(2026, 1, 1, 0, 0, 0),
            route_type="open",
            optimization_type="time",
            max_driving_hours=10.0,
        )
        self.assertEqual(result_under["total_time_seconds"], 9 * 3600)

    def test_nn_prefers_non_late_candidate(self):
        points = [
            mk_point("S", fixed_order=0),
            mk_point("A", time_from=9 * 60, time_to=18 * 60),
            mk_point("B", time_from=0, time_to=9 * 60),
        ]
        points_dict = {p.id: p for p in points}
        time_params = {
            p.id: {
                "from": (p.time_from * 60) if p.time_from is not None else None,
                "to": (p.time_to * 60) if p.time_to is not None else None,
                "service": p.service_time * 60,
                "asap": p.asap,
            }
            for p in points
        }
        dist = {
            "S-A": (1000, 3600),
            "S-B": (1000, 3600),
            "A-B": (1000, 600),
            "B-A": (1000, 600),
        }

        route = nearest_neighbor(
            points_dict=points_dict,
            start_id="S",
            dist_matrix=dist,
            departure_ts=9 * 3600,
            route_type="open",
            time_params=time_params,
        )

        self.assertEqual(route[1], "A", msg=f"NN should prefer non-late candidate first, got route {route}")


if __name__ == "__main__":
    unittest.main()