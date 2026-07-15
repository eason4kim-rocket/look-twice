import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from belief import BeliefStatus, Observation, ProbabilisticRegionBelief


class ProbabilisticBeliefTests(unittest.TestCase):
    def test_two_clear_observations_open_gate(self) -> None:
        belief = ProbabilisticRegionBelief()
        belief.add_observation(Observation("left", "clear", 0.92, 10), evidence_weight=1.0)
        belief.add_observation(Observation("right", "clear", 0.92, 20), evidence_weight=1.0)
        self.assertEqual(belief.status, BeliefStatus.CONFIRMED_CLEAR)
        self.assertTrue(belief.is_action_allowed("go_to_goal"))
        self.assertLess(belief.p_blocked, 0.18)

    def test_conflicting_observations_restore_uncertainty(self) -> None:
        belief = ProbabilisticRegionBelief()
        belief.add_observation(Observation("left", "clear", 0.9, 10))
        belief.add_observation(Observation("right", "blocked", 0.9, 20))
        self.assertEqual(belief.status, BeliefStatus.UNCERTAIN)
        self.assertAlmostEqual(belief.p_blocked, 0.5)
        self.assertAlmostEqual(belief.entropy, 1.0)

    def test_stale_probability_returns_to_prior_and_gate_closes(self) -> None:
        belief = ProbabilisticRegionBelief(max_age_steps=5)
        belief.add_observation(Observation("left", "blocked", 0.95, 1))
        belief.add_observation(Observation("left", "blocked", 0.95, 2))
        self.assertTrue(belief.is_action_allowed("go_to_detour", current_step=2))
        self.assertFalse(belief.is_action_allowed("go_to_detour", current_step=8))
        self.assertEqual(belief.status, BeliefStatus.STALE)
        self.assertAlmostEqual(belief.p_blocked, 0.5)

    def test_inconclusive_cannot_open_gate(self) -> None:
        belief = ProbabilisticRegionBelief()
        belief.add_observation(Observation("left", "inconclusive", 0.7, 1))
        self.assertEqual(belief.status, BeliefStatus.UNCERTAIN)
        self.assertFalse(belief.is_action_allowed("go_to_goal"))


if __name__ == "__main__":
    unittest.main()
