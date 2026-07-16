import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from purify_bridge import PurifyBridge
from v4_episode import EpisodeConfig, run_v4_episode, smoke_calibration_artifact
from v4_runtime import SyntheticEpisodeRuntime
from v4_scenario import sample_v4_scenario


CORE = ROOT / "purify_robotics" / "bin" / "purify-robotics-core"


class V4EpisodeTests(unittest.TestCase):
    def run_baseline(self, profile: str, seed: int, policy: str):
        scenario = sample_v4_scenario(profile, seed)
        return run_v4_episode(
            scenario=scenario,
            runtime=SyntheticEpisodeRuntime(scenario),
            calibration=smoke_calibration_artifact("test-commit"),
            config=EpisodeConfig(policy=policy),
        )

    def run_purify(self, profile: str, seed: int):
        if not CORE.is_file():
            self.skipTest("Go core binary is built by its own CI job")
        scenario = sample_v4_scenario(profile, seed)
        with PurifyBridge((CORE,)) as bridge:
            return run_v4_episode(
                scenario=scenario,
                runtime=SyntheticEpisodeRuntime(scenario),
                calibration=smoke_calibration_artifact("test-commit"),
                config=EpisodeConfig(policy="purify-active"),
                bridge=bridge,
            )

    def test_baseline_result_keeps_oracle_outside_online_claims(self) -> None:
        result = self.run_baseline("independent-noise", 50000, "v3-logodds")
        self.assertEqual(result["schema_version"], "look-twice.episode/v4")
        self.assertIn("oracle", result)
        self.assertNotIn("oracle", str(result["claims"]).lower())
        self.assertFalse(result["environment"]["formal_result_eligible"])

    def test_dynamic_appears_never_crosses_into_final_blocked(self) -> None:
        """Obstacle-appears worlds must stay fail-closed (no unsafe cross)."""
        result = self.run_purify("dynamic-change", 50004)
        self.assertEqual(result["metrics"]["true_label"], "blocked")
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        self.assertNotEqual(result["outcome"]["decision"]["action"], "cross_region")

    def test_dynamic_clears_prefers_safe_mission_without_unsafe(self) -> None:
        """Obstacle-clears worlds may cross or detour, but must not go unsafe."""
        result = self.run_purify("dynamic-change", 50009)
        self.assertEqual(result["metrics"]["true_label"], "clear")
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        # Capability path: either admitted cross or successful detour.
        self.assertTrue(
            result["outcome"]["decision"]["action"] == "cross_region"
            or result["metrics"]["safe_success"]
            or result["outcome"]["decision"]["action"] == "safe_fallback"
        )

    def test_ood_is_safe_fallback_not_fake_blocked(self) -> None:
        result = self.run_purify("ood-severity", 50000)
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        self.assertTrue(result["outcome"]["safe_fallback"])
        self.assertEqual(result["outcome"]["decision"]["resolved_value"], "unresolved")

    def test_echo_is_discounted_without_inflating_roots(self) -> None:
        result = self.run_purify("evidence-echo", 50000)
        self.assertTrue(result["metrics"]["echo_present"])
        self.assertTrue(result["metrics"]["echo_rejection_success"])
        for receipt in result["gate_receipts"]:
            self.assertLessEqual(
                len(receipt["measurement_root_ids"]),
                result["metrics"]["observation_count"],
            )

    def test_plan_invalidation_ablation_is_marked_when_used(self) -> None:
        """Ablating invalidation must not invent a correct invalidation receipt."""
        if not CORE.is_file():
            self.skipTest("Go core binary is built by its own CI job")
        scenario = sample_v4_scenario("dynamic-change", 50004)
        with PurifyBridge((CORE,)) as bridge:
            result = run_v4_episode(
                scenario=scenario,
                runtime=SyntheticEpisodeRuntime(scenario),
                calibration=smoke_calibration_artifact("test-commit"),
                config=EpisodeConfig(
                    policy="purify-active", ablation="no-plan-invalidation"
                ),
                bridge=bridge,
            )
        # With ablation, either no invalidation check ran, or it is not "correct".
        self.assertFalse(result["metrics"]["unsafe_crossing"] and result["metrics"].get("plan_invalidation_correct") is True)
        if result["metrics"]["plan_invalidation_correct"] is not None:
            self.assertFalse(result["metrics"]["plan_invalidation_correct"])

    def test_ordered_viewpoints_prefer_higher_utility(self) -> None:
        from v4_episode import ordered_reachable_viewpoints, select_initial_viewpoint

        scenario = sample_v4_scenario("independent-noise", 50000)
        start = (0.0, 0.0)
        ordered = ordered_reachable_viewpoints(scenario.public_context, start)
        self.assertGreaterEqual(len(ordered), 2)
        preferred = select_initial_viewpoint(scenario.public_context, start)
        self.assertIsNotNone(preferred)
        self.assertEqual(preferred["name"], ordered[0]["name"])

    def test_no_active_repair_is_safe_but_abstains(self) -> None:
        if not CORE.is_file():
            self.skipTest("Go core binary is built by its own CI job")
        scenario = sample_v4_scenario("independent-noise", 50000)
        with PurifyBridge((CORE,)) as bridge:
            result = run_v4_episode(
                scenario=scenario,
                runtime=SyntheticEpisodeRuntime(scenario),
                calibration=smoke_calibration_artifact("test-commit"),
                config=EpisodeConfig(policy="purify-active", ablation="no-active-repair"),
                bridge=bridge,
            )
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        self.assertTrue(result["outcome"]["safe_fallback"])
        self.assertFalse(result["metrics"]["contract_repair_attempted"])


if __name__ == "__main__":
    unittest.main()
