"""NBV lateral alignment: same-side preference, cross-side penalty, collocate dedupe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_repair import (
    EvidenceAction,
    build_candidate_actions,
    choose_evidence_action,
    lateral_alignment_metrics,
    score_action,
)
from v6_scenario import sample_v6_scenario


class NBVLateralAlignmentTests(unittest.TestCase):
    def test_a_prefers_negative_y_same_side(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95002)
        public = sc.public_context
        # A center y is negative; right_* candidates sit at +y (B side).
        selected, ranking = choose_evidence_action(
            public,
            gap_reasons=[
                "insufficient_roots",
                "missing_side_view_vision_root",
                "target_corridor:corridor_a",
            ],
            carrier_xy=(-2.0, 0.0),
            scout_xy=(-1.6, 1.2),
            visited=set(),
            observations_taken=0,
            max_observations=6,
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.corridor_id, "corridor_a")
        self.assertLess(selected.target_xy[1], 0.0, msg=selected.viewpoint)
        self.assertIn("left", selected.viewpoint)
        # Ranking audit fields present
        top = ranking[0]
        self.assertIn("alignment_score", top)
        self.assertIn("contamination_risk", top)
        self.assertIn("selection_reason", top)
        self.assertTrue(top.get("chosen"))

    def test_b_prefers_positive_y_same_side(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95002)
        public = sc.public_context
        selected, ranking = choose_evidence_action(
            public,
            gap_reasons=[
                "insufficient_roots",
                "missing_side_view_vision_root",
                "target_corridor:corridor_b",
            ],
            carrier_xy=(-2.0, 0.0),
            scout_xy=(-1.6, 1.2),
            visited=set(),
            observations_taken=0,
            max_observations=6,
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertGreater(selected.target_xy[1], 0.0, msg=selected.viewpoint)

    def test_cross_side_a_right_penalized_vs_left(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95000)
        public = sc.public_context
        left = EvidenceAction(
            name="scout_a_left_near",
            kind="side_view",
            observer="scout",
            corridor_id="corridor_a",
            viewpoint="corridor_a/left_near",
            target_xy=(-0.3, -0.95),
            predicted_coverage=0.78,
            predicted_degradation=0.18,
            physical_risk=0.05,
            reachable=True,
            travel_cost=0.2,
        )
        right = EvidenceAction(
            name="scout_a_right_near",
            kind="side_view",
            observer="scout",
            corridor_id="corridor_a",
            viewpoint="corridor_a/right_near",
            target_xy=(-0.3, 0.95),
            predicted_coverage=0.78,
            predicted_degradation=0.18,
            physical_risk=0.05,
            reachable=True,
            travel_cost=0.2,
        )
        gaps = ["insufficient_roots", "target_corridor:corridor_a"]
        u_left, a_left = score_action(left, gap_reasons=gaps, visited=set(), public=public)
        u_right, a_right = score_action(
            right, gap_reasons=gaps, visited=set(), public=public
        )
        self.assertGreater(u_left, u_right)
        self.assertTrue(a_left["same_side"])
        self.assertFalse(a_right["same_side"])
        self.assertGreater(a_right["contamination_risk"], a_left["contamination_risk"])

    def test_collocate_dedupe_marks_loser_unreachable(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95002)
        actions = build_candidate_actions(
            sc.public_context,
            carrier_xy=(-2.0, 0.0),
            scout_xy=(-1.6, 1.2),
            visited=set(),
        )
        side = [a for a in actions if a.kind == "side_view"]
        # Group by rounded xy
        from collections import defaultdict

        groups = defaultdict(list)
        for a in side:
            key = (round(a.target_xy[0], 2), round(a.target_xy[1], 2))
            groups[key].append(a)
        multi = [g for g in groups.values() if len(g) > 1]
        # For collocated groups, at most one reachable
        for g in multi:
            reachable = [a for a in g if a.reachable]
            self.assertLessEqual(len(reachable), 1, msg=[a.name for a in g])

    def test_no_oracle_keys_in_scoring(self) -> None:
        sc = sample_v6_scenario("shared-occlusion", 95005)
        public = dict(sc.public_context)
        # Ensure planner rejects if oracle sneaks in
        with self.assertRaises(ValueError):
            build_candidate_actions(
                {**public, "oracle": {"x": 1}},
                carrier_xy=(-2.0, 0.0),
                scout_xy=(-1.6, 1.2),
                visited=set(),
            )


if __name__ == "__main__":
    unittest.main()
