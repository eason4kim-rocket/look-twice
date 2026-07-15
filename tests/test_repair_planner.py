import dataclasses
import sys
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repair_planner import (
    ACTION_SAME_VIEW,
    ACTION_WAIT,
    BELIEF_GAP_REASONS,
    SIDE_VIEW_NAMES,
    UTILITY_WEIGHTS,
    BeliefGap,
    RepairPlanner,
    RepairPlanningContext,
    build_planning_context,
)
from v4_scenario import sample_v4_scenario


class RepairPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = sample_v4_scenario("time-skew", 50003)
        self.context = build_planning_context(
            public_context=self.sample.public_context,
            current_step=120,
            current_xy=(-0.6, 1.2),
            current_viewpoint_name="left_near",
            current_predicted_coverage=0.60,
            current_predicted_degradation=0.20,
            current_physical_risk=0.02,
            observations_taken=1,
            replans_taken=0,
        )
        self.planner = RepairPlanner()

    def test_candidate_set_contains_two_local_and_four_side_actions(self) -> None:
        names = {
            score.action.name
            for score in self.planner.rank(BeliefGap(("stale",)), self.context)
        }
        self.assertEqual(
            names, {ACTION_SAME_VIEW, ACTION_WAIT, *SIDE_VIEW_NAMES}
        )

    def test_each_utility_uses_exact_approved_weights(self) -> None:
        ranking = self.planner.rank(BeliefGap(("modality_conflict",)), self.context)
        for score in ranking:
            expected = sum(
                UTILITY_WEIGHTS[name] * getattr(score.features, name)
                for name in UTILITY_WEIGHTS
            )
            self.assertAlmostEqual(score.utility, expected, places=12)

    def test_ranking_is_deterministic_for_every_gap(self) -> None:
        for reason in BELIEF_GAP_REASONS:
            gap = BeliefGap((reason,))
            self.assertEqual(
                self.planner.rank(gap, self.context),
                self.planner.rank(gap, self.context),
            )

    def test_time_skew_prefers_synchronised_same_view_recapture(self) -> None:
        decision = self.planner.choose(BeliefGap(("time_skew",)), self.context)
        self.assertEqual(decision.status, "selected")
        self.assertEqual(decision.selected_action.name, ACTION_SAME_VIEW)
        self.assertTrue(decision.selected_action.synchronous_modalities)

    def test_low_coverage_prefers_a_side_view(self) -> None:
        context = dataclasses.replace(
            self.context,
            current_predicted_coverage=0.02,
            current_predicted_degradation=0.70,
        )
        decision = self.planner.choose(BeliefGap(("low_coverage",)), context)
        self.assertIn(decision.selected_action.name, SIDE_VIEW_NAMES)

    def test_shared_root_prefers_zero_travel_new_capture_when_coverage_is_good(self) -> None:
        decision = self.planner.choose(BeliefGap(("shared_root",)), self.context)
        self.assertEqual(decision.selected_action.name, ACTION_SAME_VIEW)

    def test_unreachable_candidate_is_ranked_but_never_selected(self) -> None:
        raw = deepcopy(self.sample.public_context)
        for candidate in raw["candidate_viewpoints"]:
            candidate["reachable"] = candidate["name"] != "left_near"
            candidate["predicted_coverage"] = (
                1.0 if candidate["name"] == "left_near" else 0.55
            )
            candidate["predicted_degradation"] = 0.0
        context = build_planning_context(
            public_context=raw,
            current_step=10,
            current_xy=(-2.0, 0.0),
            current_viewpoint_name="start",
            current_predicted_coverage=0.0,
            current_predicted_degradation=0.8,
            observations_taken=1,
        )
        decision = self.planner.choose(BeliefGap(("low_coverage",)), context)
        unreachable = next(
            score for score in decision.ranking if score.action.name == "left_near"
        )
        self.assertFalse(unreachable.eligible)
        self.assertNotEqual(decision.selected_action.name, "left_near")

    def test_oracle_and_malicious_contexts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_planning_context(
                public_context=self.sample.oracle_context,
                current_step=0,
                current_xy=(-2.0, 0.0),
                current_viewpoint_name="start",
            )
        leaked = deepcopy(self.sample.public_context)
        leaked["known_static_map"]["truth"] = {"blocked": True}
        with self.assertRaises(ValueError):
            build_planning_context(
                public_context=leaked,
                current_step=0,
                current_xy=(-2.0, 0.0),
                current_viewpoint_name="start",
            )

    def test_typed_planner_context_has_no_oracle_fields(self) -> None:
        fields = {field.name for field in dataclasses.fields(RepairPlanningContext)}
        self.assertTrue(
            fields.isdisjoint(
                {
                    "seed",
                    "profile",
                    "truth",
                    "oracle_context",
                    "external_event",
                    "noise_realization",
                    "future_observation",
                }
            )
        )

    def test_observation_and_replan_limits_fail_safe(self) -> None:
        max_observations = dataclasses.replace(self.context, observations_taken=4)
        decision = self.planner.choose(BeliefGap(("stale",)), max_observations)
        self.assertTrue(decision.should_safe_fallback)
        self.assertEqual(decision.reason, "max_observations_reached")

        max_replans = dataclasses.replace(
            self.context,
            replans_taken=2,
            current_predicted_coverage=0.0,
            current_predicted_degradation=1.0,
            current_physical_risk=1.0,
            visited_actions=frozenset({ACTION_SAME_VIEW, ACTION_WAIT}),
        )
        decision = self.planner.choose(BeliefGap(("low_coverage",)), max_replans)
        self.assertTrue(decision.should_safe_fallback)
        self.assertEqual(decision.reason, "max_replans_reached")

    def test_no_positive_utility_fails_safe(self) -> None:
        raw = deepcopy(self.sample.public_context)
        for candidate in raw["candidate_viewpoints"]:
            candidate["predicted_coverage"] = 0.0
            candidate["predicted_degradation"] = 1.0
            candidate["physical_risk"] = 1.0
        context = build_planning_context(
            public_context=raw,
            current_step=10,
            current_xy=(-2.0, 0.0),
            current_viewpoint_name="start",
            current_predicted_coverage=0.0,
            current_predicted_degradation=1.0,
            current_physical_risk=1.0,
            observations_taken=1,
        )
        decision = self.planner.choose(
            BeliefGap(("calibration_not_applicable",)), context
        )
        self.assertTrue(decision.should_safe_fallback)
        self.assertEqual(decision.reason, "no_positive_utility")
        self.assertTrue(all(score.utility <= 0.0 for score in decision.ranking))

    def test_empty_or_invalid_gap_is_not_silently_planned(self) -> None:
        empty = self.planner.choose(BeliefGap(()), self.context)
        self.assertEqual(empty.reason, "no_belief_gap")
        with self.assertRaises(ValueError):
            BeliefGap(("unknown_reason",))

    def test_gap_order_and_duplicates_are_canonical(self) -> None:
        gap = BeliefGap(("time_skew", "stale", "time_skew"))
        self.assertEqual(gap.reasons, ("stale", "time_skew"))


if __name__ == "__main__":
    unittest.main()
