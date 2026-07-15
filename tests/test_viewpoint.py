import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from viewpoint import Rectangle, ViewpointPlanner, estimate_visibility


class ViewpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = Rectangle(0.4, 1.2, -0.4, 0.4)

    def test_visibility_is_deterministic(self) -> None:
        occluder = Rectangle(-0.25, 0.25, -0.6, 0.6)
        first = estimate_visibility((-0.6, 1.2), self.target, [occluder])
        second = estimate_visibility((-0.6, 1.2), self.target, [occluder])
        self.assertEqual(first, second)

    def test_planner_avoids_visited_candidate(self) -> None:
        planner = ViewpointPlanner()
        candidate, ranking = planner.choose(
            current_xy=(-2.0, 0.0),
            target_region=self.target,
            occluders=[Rectangle(-0.25, 0.25, -0.6, 0.6)],
            visited={"left_near"},
            minimum_visibility=0.0,
        )
        self.assertIsNotNone(candidate)
        self.assertNotEqual(candidate.name, "left_near")
        self.assertEqual(len(ranking), 4)

    def test_shifted_occluder_changes_ranking(self) -> None:
        planner = ViewpointPlanner()
        left_shift = planner.rank(
            current_xy=(-2.0, 0.0),
            target_region=self.target,
            occluders=[Rectangle(-0.25, 0.25, -1.0, 0.2)],
            visited=set(),
        )
        right_shift = planner.rank(
            current_xy=(-2.0, 0.0),
            target_region=self.target,
            occluders=[Rectangle(-0.25, 0.25, -0.2, 1.0)],
            visited=set(),
        )
        self.assertNotEqual(left_shift[0].name, right_shift[0].name)


if __name__ == "__main__":
    unittest.main()
