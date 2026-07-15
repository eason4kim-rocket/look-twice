import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scenario import PROFILES, sample_scenario


class ScenarioTests(unittest.TestCase):
    def test_same_profile_and_seed_are_identical(self) -> None:
        self.assertEqual(
            sample_scenario("dynamic-change", 17),
            sample_scenario("dynamic-change", 17),
        )

    def test_all_profiles_stay_in_valid_ranges(self) -> None:
        for profile in PROFILES:
            sample = sample_scenario(profile, 4)
            self.assertGreaterEqual(sample.noise_severity, 0.0)
            self.assertLessEqual(sample.noise_severity, 1.0)
            self.assertLess(len(sample.unreachable_viewpoints), 4)

    def test_dynamic_event_reverses_initial_truth(self) -> None:
        for seed in range(5):
            sample = sample_scenario("dynamic-change", seed)
            expected = "clears" if sample.initial_blocked else "appears"
            self.assertEqual(sample.dynamic_event, expected)


if __name__ == "__main__":
    unittest.main()
