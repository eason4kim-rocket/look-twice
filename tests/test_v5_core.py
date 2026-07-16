"""Unit tests for Look Twice v5 navigation + proxy pick + contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_manipulation import evaluate_proxy_grasp, end_effector_xy, build_workspace_claim
from v5_policies import POLICIES, naive_decision_from_claims
from v5_scenario import PROFILES, sample_v5_scenario
from v4_motion import Pose2D

CORE = ROOT / "purify_robotics" / "bin" / "purify-robotics-core"


class V5CoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
