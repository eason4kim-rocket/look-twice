import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_scenario import (
    FORBIDDEN_PLANNER_KEYS,
    PROFILES,
    SIMULATION_DT_SECONDS,
    assert_public_context_safe,
    sample_v4_scenario,
)


def nested_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(nested_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(nested_keys(child))
    return keys


class V4ScenarioTests(unittest.TestCase):
    def test_profiles_are_the_frozen_v4_stress_matrix(self) -> None:
        self.assertEqual(
            PROFILES,
            (
                "independent-noise",
                "shared-occlusion",
                "evidence-echo",
                "time-skew",
                "pose-calibration-drift",
                "structured-depth-dropout",
                "dynamic-change",
                "ood-severity",
            ),
        )

    def test_same_profile_and_seed_are_byte_deterministic(self) -> None:
        first = sample_v4_scenario("shared-occlusion", 50003)
        second = sample_v4_scenario("shared-occlusion", 50003)
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")),
            json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    def test_profiles_share_one_paired_base_world(self) -> None:
        samples = [sample_v4_scenario(profile, 50007) for profile in PROFILES]
        reference = samples[0]
        for sample in samples[1:]:
            self.assertEqual(sample.paired_world_id, reference.paired_world_id)
            self.assertEqual(sample.initial_blocked, reference.initial_blocked)
            self.assertEqual(sample.obstacle_xy, reference.obstacle_xy)
            self.assertEqual(sample.obstacle_size, reference.obstacle_size)
            self.assertEqual(sample.occluder_xy, reference.occluder_xy)
            self.assertEqual(sample.occluder_size, reference.occluder_size)
            self.assertEqual(
                sample.unreachable_viewpoints, reference.unreachable_viewpoints
            )
            self.assertEqual(sample.public_context, reference.public_context)
        self.assertEqual(len({sample.scenario_id for sample in samples}), len(PROFILES))

    def test_dynamic_event_uses_an_absolute_external_clock(self) -> None:
        sample = sample_v4_scenario("dynamic-change", 50005)
        event = sample.external_event
        self.assertEqual(event.schedule, "absolute")
        self.assertEqual(event.clock, "simulation_step")
        self.assertIsNotNone(event.absolute_step)
        self.assertEqual(
            event.absolute_time_seconds,
            event.absolute_step * SIMULATION_DT_SECONDS,
        )
        self.assertEqual(
            sample.truth_blocked_at(event.absolute_step - 1), sample.initial_blocked
        )
        self.assertEqual(sample.truth_blocked_at(event.absolute_step), event.to_blocked)
        self.assertNotEqual(event.from_blocked, event.to_blocked)
        # Re-sampling represents any policy: no policy timing or call count enters
        # the absolute event schedule.
        self.assertEqual(
            event.absolute_step,
            sample_v4_scenario("dynamic-change", 50005).external_event.absolute_step,
        )

    def test_non_dynamic_profiles_have_no_future_event(self) -> None:
        for profile in set(PROFILES) - {"dynamic-change"}:
            event = sample_v4_scenario(profile, 50001).external_event
            self.assertEqual(event.kind, "none")
            self.assertIsNone(event.absolute_step)

    def test_public_context_contains_no_oracle_future_or_noise_realisation(self) -> None:
        sample = sample_v4_scenario("ood-severity", 50009)
        public = sample.public_context
        assert_public_context_safe(public)
        self.assertTrue(nested_keys(public).isdisjoint(FORBIDDEN_PLANNER_KEYS))
        encoded = json.dumps(public, sort_keys=True)
        for forbidden_fragment in (
            '"seed"',
            '"profile"',
            '"world_truth"',
            '"fault_realization"',
            '"external_event"',
        ):
            self.assertNotIn(forbidden_fragment, encoded)
        self.assertIn("outside_calibration_domain", sample.oracle_context["fault_realization"])

    def test_context_is_fresh_and_cannot_mutate_the_sample(self) -> None:
        sample = sample_v4_scenario("independent-noise", 3)
        first = sample.public_context
        first["candidate_viewpoints"][0]["reachable"] = False
        self.assertNotEqual(first, sample.public_context)

    def test_stress_profiles_activate_the_intended_oracle_fault(self) -> None:
        shared = sample_v4_scenario("shared-occlusion", 4).fault_realization
        echo = sample_v4_scenario("evidence-echo", 4).fault_realization
        skew = sample_v4_scenario("time-skew", 4).fault_realization
        drift = sample_v4_scenario("pose-calibration-drift", 4).fault_realization
        dropout = sample_v4_scenario(
            "structured-depth-dropout", 4
        ).fault_realization
        ood = sample_v4_scenario("ood-severity", 4).fault_realization
        self.assertIsNotNone(shared.shared_cause_id)
        self.assertGreater(shared.shared_occlusion_fraction, 0.0)
        self.assertGreaterEqual(echo.evidence_echo_count, 2)
        self.assertGreater(skew.semantic_lag_steps, 2)
        self.assertNotEqual(drift.pose_drift_xy, (0.0, 0.0))
        self.assertGreater(dropout.structured_depth_dropout_fraction, 0.0)
        self.assertTrue(ood.outside_calibration_domain)

    def test_invalid_profile_and_negative_query_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sample_v4_scenario("not-a-profile", 1)
        with self.assertRaises(ValueError):
            sample_v4_scenario("independent-noise", 1).truth_blocked_at(-1)


if __name__ == "__main__":
    unittest.main()

