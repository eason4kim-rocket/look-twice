import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from viewpoint import (
    InformationGainViewpointPlanner,
    Rectangle,
    expected_information_gain,
)


class InformationGainTests(unittest.TestCase):
    def test_reliable_sensor_has_more_information(self) -> None:
        self.assertGreater(
            expected_information_gain(0.5, 0.95),
            expected_information_gain(0.5, 0.60),
        )

    def test_unreachable_candidate_is_never_selected(self) -> None:
        planner = InformationGainViewpointPlanner()
        target = Rectangle(0.4, 1.2, -0.4, 0.4)
        first, ranking = planner.choose(
            current_xy=(-2.0, 0.0),
            target_region=target,
            occluders=[Rectangle(-0.25, 0.25, -0.6, 0.6)],
            visited=set(),
            unreachable=set(),
            p_blocked=0.5,
            severity=0.3,
        )
        self.assertIsNotNone(first)
        second, _ = planner.choose(
            current_xy=(-2.0, 0.0),
            target_region=target,
            occluders=[Rectangle(-0.25, 0.25, -0.6, 0.6)],
            visited=set(),
            unreachable={first.name},
            p_blocked=0.5,
            severity=0.3,
        )
        self.assertIsNotNone(second)
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(len(ranking), 4)

    def test_ranking_is_deterministic(self) -> None:
        planner = InformationGainViewpointPlanner()
        kwargs = dict(
            current_xy=(-2.0, 0.0),
            target_region=Rectangle(0.4, 1.2, -0.4, 0.4),
            occluders=[Rectangle(-0.25, 0.25, -0.7, 0.4)],
            visited=set(),
            unreachable=set(),
            p_blocked=0.35,
            severity=0.4,
        )
        self.assertEqual(planner.rank(**kwargs), planner.rank(**kwargs))


if __name__ == "__main__":
    unittest.main()
