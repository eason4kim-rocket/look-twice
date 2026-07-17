from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_v5_learned_rgbd_gate import evaluate


def fixtures(*, singleton_rate: float = 0.8):
    training = {
        "device": "cuda:0",
        "rocm": "7.2",
        "gpu": "AMD Radeon PRO W7900D",
        "validation": {"balanced_accuracy": 0.90},
        "test": {"balanced_accuracy": 0.89, "brier": 0.10},
    }
    conformal = {
        "locked_test": {
            "coverage": 0.95,
            "clear_coverage": 0.94,
            "blocked_coverage": 0.96,
            "singleton_rate": singleton_rate,
            "singleton_accuracy": 0.92,
        }
    }
    return training, conformal


class LearnedRgbdGateTests(unittest.TestCase):
    def test_quality_candidate_still_requires_closed_loop(self) -> None:
        result = evaluate(*fixtures())
        self.assertTrue(result["model_candidate_eligible"])
        self.assertFalse(result["online_promotion_eligible"])
        self.assertEqual(
            result["online_promotion_status"],
            "pending_closed_loop_safety_evaluation",
        )

    def test_noninformative_sets_fail_usefulness_gate(self) -> None:
        result = evaluate(*fixtures(singleton_rate=0.0))
        self.assertFalse(result["model_candidate_eligible"])
        self.assertFalse(result["checks"]["locked_test_singleton_rate"]["passed"])


if __name__ == "__main__":
    unittest.main()
