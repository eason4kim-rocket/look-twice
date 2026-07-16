"""Repair-required cells: detour counts as nav; side_view requires real move."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_scenario import PROFILES, sample_v5_scenario

CORE = ROOT / "purify_robotics" / "bin" / "purify-robotics-core"


def _run_repair(policy: str, seed: int) -> dict:
    from purify_bridge import PurifyBridge
    from look_twice_v5 import _V5SyntheticRuntime
    from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact

    scenario = sample_v5_scenario("repair-required", seed)
    runtime = _V5SyntheticRuntime(scenario)
    cal = smoke_calibration_artifact("c" * 40)
    try:
        if policy == "naive":
            return run_v5_episode(
                scenario=scenario,
                runtime=runtime,
                calibration=cal,
                config=V5EpisodeConfig(policy=policy),
                bridge=None,
            )
        with PurifyBridge((CORE,)) as bridge:
            return run_v5_episode(
                scenario=scenario,
                runtime=runtime,
                calibration=cal,
                config=V5EpisodeConfig(policy=policy),
                bridge=bridge,
            )
    finally:
        runtime.close()


class RepairRequiredScenarioTests(unittest.TestCase):
    def test_profile_forces_single_initial_viewpoint(self) -> None:
        self.assertIn("repair-required", PROFILES)
        sc = sample_v5_scenario("repair-required", 50000)
        self.assertTrue(sc.public_context["repair_required"])
        self.assertEqual(sc.public_context["initial_viewpoint_budget"], 1)
        self.assertFalse(sc.oracle_context["nav_blocked_initial"])
        blocked = sample_v5_scenario("repair-required", 50001)
        self.assertTrue(blocked.oracle_context["nav_blocked_initial"])
        self.assertEqual(blocked.public_context["initial_viewpoint_budget"], 1)

    def test_mission_equals_nav_and_pick_and_not_unsafe(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        for policy, seed in (
            ("purify-passive", 50000),
            ("purify-active", 50000),
            ("naive", 50001),
        ):
            result = _run_repair(policy, seed)
            m = result["metrics"]
            expected = bool(
                m["nav_success"] and m["pick_success"] and not m["unsafe_crossing"]
            )
            self.assertEqual(
                m["mission_success"],
                expected,
                msg=f"{policy} seed={seed} mission invariant broken: {m}",
            )

    def test_successful_detour_counts_as_nav_success_clear_wrong_detour(self) -> None:
        """Passive clear: deny gate → safe detour → nav+mission; wrong_detour."""
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        result = _run_repair("purify-passive", 50000)
        m = result["metrics"]
        self.assertFalse(m["initial_gate_admitted"])
        self.assertFalse(m["repair_attempted"])
        self.assertTrue(m["detour_success"])
        self.assertTrue(m["used_detour"])
        self.assertEqual(m["route_mode"], "detour")
        self.assertTrue(m["nav_success"])
        self.assertFalse(m["direct_cross_success"])
        self.assertTrue(m["wrong_detour"])  # oracle clear + detour
        self.assertFalse(m["unsafe_crossing"])
        if m["pick_success"]:
            self.assertTrue(m["mission_success"])

    def test_blocked_detour_not_wrong_detour(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        result = _run_repair("purify-passive", 50001)
        m = result["metrics"]
        self.assertTrue(m["detour_success"])
        self.assertTrue(m["nav_success"])
        self.assertEqual(m["route_mode"], "detour")
        self.assertFalse(m["wrong_detour"])
        self.assertFalse(m["unsafe_crossing"])
        if m["pick_success"]:
            self.assertTrue(m["mission_success"])

    def test_active_clear_real_side_view_then_direct(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        result = _run_repair("purify-active", 50000)
        m = result["metrics"]
        self.assertFalse(m["initial_gate_admitted"])
        self.assertTrue(m["repair_attempted"])
        self.assertTrue(m["repair_success"])
        self.assertEqual(m["route_mode"], "direct")
        self.assertTrue(m["direct_cross_success"])
        self.assertFalse(m["wrong_detour"])
        self.assertTrue(m["nav_success"])
        self.assertTrue(m["mission_success"])
        self.assertFalse(m["unsafe_crossing"])
        self.assertGreaterEqual(m["real_side_view_count"], 1)

        side = [
            d
            for d in result["repair_decisions"]
            if d.get("action_kind_executed") == "side_view"
        ]
        self.assertGreaterEqual(len(side), 1)
        for d in side:
            self.assertIn("previous_viewpoint", d)
            self.assertIn("selected_viewpoint", d)
            self.assertIn("planned_distance", d)
            self.assertIn("actual_distance", d)
            self.assertIn("viewpoint_changed", d)
            self.assertTrue(d["viewpoint_changed"])
            self.assertGreater(float(d["actual_distance"]), 0.10)
            self.assertNotEqual(d["previous_viewpoint"], d["selected_viewpoint"])

    def test_active_blocked_safe_detour_not_wrong(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        result = _run_repair("purify-active", 50001)
        m = result["metrics"]
        self.assertFalse(m["unsafe_crossing"])
        self.assertTrue(m["nav_success"])
        self.assertFalse(m["wrong_detour"])
        # May attempt repair but should not force an unsafe direct cross.
        self.assertIn(m["route_mode"], ("detour", "direct", "none"))
        if m["route_mode"] == "direct":
            # Only admissible if gate stayed safe and world allowed it.
            self.assertTrue(m["direct_cross_success"])
        else:
            self.assertTrue(m["detour_success"])
            self.assertEqual(m["route_mode"], "detour")
        if m["pick_success"]:
            self.assertTrue(m["mission_success"])

    def test_naive_blocked_can_be_unsafe(self) -> None:
        result = _run_repair("naive", 50001)
        m = result["metrics"]
        self.assertFalse(m["mission_success"])
        self.assertTrue(m["unsafe_crossing"] or not m["nav_success"])

    def test_visited_viewpoint_not_eligible_for_side_view(self) -> None:
        from repair_planner import BeliefGap, RepairPlanner, build_planning_context

        scenario = sample_v5_scenario("repair-required", 50000)
        # Planner schema requires the full left_/right_ side set only.
        public = {
            "candidate_viewpoints": [
                c
                for c in scenario.public_context["candidate_viewpoints"]
                if str(c.get("name", "")).startswith(("left_", "right_"))
            ],
            "known_static_map": scenario.public_context["known_static_map"],
        }
        # Stand at left_near; mark it visited — must not reselect as side_view.
        left = next(
            c
            for c in public["candidate_viewpoints"]
            if c["name"] == "left_near"
        )
        context = build_planning_context(
            public_context=public,
            current_step=10,
            current_xy=(float(left["xy"][0]), float(left["xy"][1])),
            current_viewpoint_name="left_near",
            current_predicted_coverage=0.7,
            current_predicted_degradation=0.2,
            current_physical_risk=0.1,
            visited_actions={"left_near"},
            observations_taken=1,
            replans_taken=0,
        )
        planner = RepairPlanner(max_observations=4, max_replans=2)
        decision = planner.choose(
            BeliefGap(("shared_root", "insufficient_roots")), context
        )
        ranking = {s.action.name: s for s in decision.ranking}
        self.assertIn("left_near", ranking)
        self.assertFalse(ranking["left_near"].eligible)
        if decision.selected_action is not None:
            if decision.selected_action.kind == "side_view":
                self.assertNotEqual(decision.selected_action.name, "left_near")
                dist = math.dist(
                    context.current_xy, decision.selected_action.target_xy
                )
                self.assertGreater(dist, 0.10)

    def test_same_view_never_marked_viewpoint_changed_on_active(self) -> None:
        """same_view telemetry must not claim viewpoint diversity."""
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        from v5_episode import MIN_SIDE_VIEW_DISTANCE_M

        self.assertEqual(MIN_SIDE_VIEW_DISTANCE_M, 0.10)
        result = _run_repair("purify-active", 50000)
        same = [
            d
            for d in result["repair_decisions"]
            if d.get("action_kind_executed") == "same_view"
        ]
        for d in same:
            self.assertFalse(
                d.get("viewpoint_changed"),
                msg=f"same_view claimed diversity: {d}",
            )
            self.assertLessEqual(float(d.get("actual_distance") or 0.0), 0.10)
        # And every true side_view must move.
        side = [
            d
            for d in result["repair_decisions"]
            if d.get("action_kind_executed") == "side_view"
        ]
        for d in side:
            self.assertTrue(d.get("viewpoint_changed"))
            self.assertGreater(float(d["actual_distance"]), 0.10)


if __name__ == "__main__":
    unittest.main()
