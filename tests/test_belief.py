import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from belief import BeliefStatus, Observation, RegionBelief


def observation(result: str, confidence: float = 1.0, step: int = 1) -> Observation:
    return Observation("inspection", result, confidence, step)


class RegionBeliefTests(unittest.TestCase):
    def test_first_clear_is_only_provisional(self) -> None:
        belief = RegionBelief()
        self.assertEqual(
            belief.add_observation(observation("clear")),
            BeliefStatus.PROVISIONAL_CLEAR,
        )
        self.assertFalse(belief.is_action_allowed("go_to_goal"))

    def test_two_clear_observations_allow_goal(self) -> None:
        belief = RegionBelief()
        belief.add_observation(observation("clear", step=1))
        belief.add_observation(observation("clear", step=2))
        self.assertEqual(belief.status, BeliefStatus.CONFIRMED_CLEAR)
        self.assertTrue(belief.is_action_allowed("go_to_goal"))

    def test_two_blocked_observations_allow_detour(self) -> None:
        belief = RegionBelief()
        belief.add_observation(observation("blocked", step=1))
        belief.add_observation(observation("blocked", step=2))
        self.assertEqual(belief.status, BeliefStatus.CONFIRMED_BLOCKED)
        self.assertTrue(belief.is_action_allowed("go_to_detour"))

    def test_conflict_is_uncertain(self) -> None:
        belief = RegionBelief()
        belief.add_observation(observation("clear", step=1))
        belief.add_observation(observation("blocked", step=2))
        self.assertEqual(belief.status, BeliefStatus.UNCERTAIN)
        self.assertFalse(belief.is_action_allowed("go_to_goal"))
        self.assertFalse(belief.is_action_allowed("go_to_detour"))

    def test_low_confidence_does_not_confirm(self) -> None:
        belief = RegionBelief()
        belief.add_observation(observation("clear", 0.7, 1))
        belief.add_observation(observation("clear", 0.7, 2))
        self.assertEqual(belief.status, BeliefStatus.UNCERTAIN)

    def test_inconclusive_never_confirms_clear(self) -> None:
        belief = RegionBelief()
        belief.add_observation(observation("inconclusive", 0.5, 1))
        self.assertEqual(belief.status, BeliefStatus.UNCERTAIN)
        self.assertFalse(belief.is_action_allowed("go_to_goal"))

    def test_confirmed_evidence_expires(self) -> None:
        belief = RegionBelief(max_age_steps=60)
        belief.add_observation(observation("clear", step=10))
        belief.add_observation(observation("clear", step=20))
        self.assertTrue(belief.is_action_allowed("go_to_goal", current_step=80))
        self.assertFalse(belief.is_action_allowed("go_to_goal", current_step=81))
        self.assertEqual(belief.status, BeliefStatus.STALE)
        belief.add_observation(observation("blocked", step=82))
        self.assertEqual(belief.status, BeliefStatus.PROVISIONAL_BLOCKED)
        belief.add_observation(observation("blocked", step=83))
        self.assertEqual(belief.status, BeliefStatus.CONFIRMED_BLOCKED)


if __name__ == "__main__":
    unittest.main()
