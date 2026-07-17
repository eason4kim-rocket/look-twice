"""Unit tests for Look Twice v5 navigation + proxy pick + contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_manipulation import evaluate_proxy_grasp, end_effector_xy, build_workspace_claim
from v5_policies import POLICIES, naive_decision_from_claims
from v5_scenario import PROFILES, sample_v5_scenario
from v4_motion import Pose2D

CORE = ROOT / "purify_robotics" / "bin" / "purify-robotics-core"


class V5CoreTests(unittest.TestCase):
    def test_live_git_commit_precedes_static_pin(self) -> None:
        from v5_episode import git_commit

        live = "a" * 40
        with mock.patch.dict("os.environ", {"LOOK_TWICE_GIT_COMMIT": ""}):
            with mock.patch("v5_episode.subprocess.check_output", return_value=live + "\n"):
                self.assertEqual(git_commit(), live)

    def test_profiles_and_determinism(self) -> None:
        self.assertIn("manipulation-occlusion", PROFILES)
        a = sample_v5_scenario("dynamic-change", 50000).to_dict()
        b = sample_v5_scenario("dynamic-change", 50000).to_dict()
        self.assertEqual(a, b)
        self.assertIn("step", a["oracle_context"]["external_event"])

    def test_proxy_grasp_geometry(self) -> None:
        pose = Pose2D(1.15, 0.0, 0.0)
        ok = evaluate_proxy_grasp(pose, (1.35, 0.0), close_command=True, lift_command=True)
        self.assertTrue(ok.success)
        far = evaluate_proxy_grasp(
            Pose2D(0.0, 0.0, 0.0), (1.35, 0.0), close_command=True, lift_command=True
        )
        self.assertFalse(far.success)
        ee = end_effector_xy(pose)
        self.assertGreater(ee[0], pose.x)

    def test_workspace_claim_wire(self) -> None:
        claim = build_workspace_claim(
            clear=True,
            confidence=0.9,
            observed_step=10,
            valid_until_step=50,
            capture_root_id="cap-1",
        )
        wire = claim.to_wire()
        self.assertEqual(wire["predicate"], "graspable")
        self.assertEqual(wire["value"], "clear")
        self.assertEqual(wire["modality"], "workspace_geometry")

    def test_naive_majority(self) -> None:
        claims = [
            {"modality": "depth_geometry", "value": "clear"},
            {"modality": "simulated_semantic_sensor", "value": "clear"},
            {"modality": "static_map", "value": "blocked"},
        ]
        self.assertEqual(naive_decision_from_claims(claims), "clear")

    def test_synthetic_episode_naive(self) -> None:
        from look_twice_v5 import _V5SyntheticRuntime
        from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact

        scenario = sample_v5_scenario("independent-noise", 50000)
        runtime = _V5SyntheticRuntime(scenario)
        try:
            result = run_v5_episode(
                scenario=scenario,
                runtime=runtime,
                calibration=smoke_calibration_artifact("a" * 40),
                config=V5EpisodeConfig(policy="naive"),
                bridge=None,
            )
        finally:
            runtime.close()
        self.assertEqual(result["schema_version"], "look-twice.episode/v5")
        self.assertIn("action_contracts", result)
        self.assertEqual(len(result["action_contracts"]), 2)
        self.assertFalse(result["environment"]["formal_result_eligible"])
        self.assertIn("metrics", result)
        self.assertIn("nav_success", result["metrics"])
        self.assertIn("pick_success", result["metrics"])
        # Mission is nav ∧ pick ∧ ¬unsafe (no pick-only credit).
        if result["metrics"]["mission_success"]:
            self.assertTrue(result["metrics"]["nav_success"])
            self.assertTrue(result["metrics"]["pick_success"])
            self.assertFalse(result["metrics"]["unsafe_crossing"])
        self.assertGreaterEqual(result["configuration"]["ttl_steps"], 1000)

    def test_point_in_risk_and_trajectory_helper(self) -> None:
        from v5_episode import (
            point_in_risk_region,
            segment_intersects_risk,
            trajectory_enters_risk,
            trajectory_is_unsafe,
        )
        from v4_motion import MotionResult, Pose2D

        self.assertTrue(point_in_risk_region(0.8, 0.0))
        self.assertFalse(point_in_risk_region(-1.0, 0.0))
        result = MotionResult(
            reached=True,
            target_xy=(0.9, 0.0),
            final_pose=Pose2D(0.9, 0.0, 0.0),
            path_length=1.0,
            collision_count=0,
            elapsed_steps=10,
            reason="reached",
            trajectory=({"step": 0, "x": 0.2, "y": 0.0}, {"step": 5, "x": 0.8, "y": 0.0}),
            controls=(),
        )
        self.assertTrue(trajectory_enters_risk(result, (-0.5, 0.0)))
        self.assertFalse(segment_intersects_risk((-1.0, 0.6), (1.0, 0.6)))
        self.assertTrue(
            trajectory_is_unsafe(
                result,
                start_step=100,
                start_xy=(-0.5, 0.0),
                truth_blocked_at=lambda step: step >= 105,
            )
        )

    def test_synthetic_episode_purify_active(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        from purify_bridge import PurifyBridge
        from look_twice_v5 import _V5SyntheticRuntime
        from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact

        scenario = sample_v5_scenario("evidence-echo", 50000)
        runtime = _V5SyntheticRuntime(scenario)
        with PurifyBridge((CORE,)) as bridge:
            try:
                result = run_v5_episode(
                    scenario=scenario,
                    runtime=runtime,
                    calibration=smoke_calibration_artifact("b" * 40),
                    config=V5EpisodeConfig(policy="purify-active"),
                    bridge=bridge,
                )
            finally:
                runtime.close()
        self.assertGreaterEqual(len(result["gate_receipts"]), 1)
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        # Dual contract objects present even if not both admitted
        actions = {c["action"] for c in result["action_contracts"]}
        self.assertEqual(actions, {"cross_region", "pick_proxy"})

    def test_dynamic_change_separates_naive_from_active(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        from look_twice_v5 import _V5SyntheticRuntime
        from purify_bridge import PurifyBridge
        from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact

        # Seed 50000: clear → blocked. Naive may enter then become unsafe;
        # active should invalidate and not claim mission through a blocked slab.
        scenario = sample_v5_scenario("dynamic-change", 50000)
        naive_runtime = _V5SyntheticRuntime(scenario)
        try:
            naive = run_v5_episode(
                scenario=scenario,
                runtime=naive_runtime,
                calibration=smoke_calibration_artifact("c" * 40),
                config=V5EpisodeConfig(policy="naive"),
            )
        finally:
            naive_runtime.close()
        self.assertTrue(naive["metrics"]["unsafe_crossing"])
        self.assertFalse(naive["metrics"]["mission_success"])

        active_runtime = _V5SyntheticRuntime(scenario)
        with PurifyBridge((CORE,)) as bridge:
            try:
                active = run_v5_episode(
                    scenario=scenario,
                    runtime=active_runtime,
                    calibration=smoke_calibration_artifact("d" * 40),
                    config=V5EpisodeConfig(policy="purify-active"),
                    bridge=bridge,
                )
            finally:
                active_runtime.close()
        self.assertFalse(active["metrics"]["unsafe_crossing"])
        self.assertGreaterEqual(active["metrics"]["invalidation_count"], 1)
        # After the world flip, active must not force an unsafe corridor push.
        # Safe detour is valid nav; mission may complete if pick also succeeds.
        if active["metrics"]["mission_success"]:
            self.assertTrue(active["metrics"]["nav_success"])
            self.assertTrue(active["metrics"]["pick_success"])
            self.assertIn(active["metrics"]["route_mode"], ("detour", "direct"))

    def test_passive_expired_receipt_fails_closed_and_detours(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary missing")
        from look_twice_v5 import _V5SyntheticRuntime
        from purify_bridge import PurifyBridge
        from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact

        scenario = sample_v5_scenario("independent-noise", 50000)
        runtime = _V5SyntheticRuntime(scenario)
        with PurifyBridge((CORE,)) as bridge:
            try:
                result = run_v5_episode(
                    scenario=scenario,
                    runtime=runtime,
                    calibration=smoke_calibration_artifact("e" * 40),
                    # Both roots are fresh at evaluation, but the older root
                    # expires during travel to the commitment boundary.
                    config=V5EpisodeConfig(policy="purify-passive", ttl_steps=500),
                    bridge=bridge,
                )
            finally:
                runtime.close()
        self.assertTrue(result["metrics"]["used_detour"])
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        # Safe detour is successful navigation (not a gated risk cross).
        self.assertTrue(result["metrics"]["nav_success"])
        self.assertTrue(result["metrics"]["detour_success"])
        self.assertEqual(result["metrics"]["route_mode"], "detour")
        # Mission still requires pick ∧ ¬unsafe; never invent pick-only credit.
        expected_mission = bool(
            result["metrics"]["nav_success"]
            and result["metrics"]["pick_success"]
            and not result["metrics"]["unsafe_crossing"]
        )
        self.assertEqual(result["metrics"]["mission_success"], expected_mission)
        self.assertGreaterEqual(result["metrics"]["invalidation_count"], 1)


if __name__ == "__main__":
    unittest.main()
