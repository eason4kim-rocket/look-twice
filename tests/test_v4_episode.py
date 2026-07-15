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

    def test_dynamic_appears_invalidates_clear_plan_and_detours(self) -> None:
        result = self.run_purify("dynamic-change", 50004)
        self.assertTrue(result["metrics"]["plan_invalidation_expected"])
        self.assertTrue(result["metrics"]["plan_invalidation_correct"])
        self.assertFalse(result["metrics"]["unsafe_crossing"])
        self.assertEqual(result["outcome"]["decision"]["resolved_value"], "blocked")

    def test_dynamic_clears_invalidates_detour_plan_and_crosses(self) -> None:
        result = self.run_purify("dynamic-change", 50009)
        self.assertTrue(result["metrics"]["plan_invalidation_correct"])
        self.assertFalse(result["metrics"]["wrong_detour"])
        self.assertEqual(result["outcome"]["decision"]["action"], "cross_region")

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

    def test_plan_invalidation_ablation_exposes_dynamic_hazard(self) -> None:
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
        self.assertTrue(result["metrics"]["unsafe_crossing"])
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
