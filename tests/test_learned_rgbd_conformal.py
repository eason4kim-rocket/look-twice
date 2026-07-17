"""Tests for clustered learned RGB-D conformal calibration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd_conformal import (
    coverage_metrics,
    finite_sample_quantile,
    fit_clustered_thresholds,
    prediction_set,
)


class LearnedRgbdConformalTests(unittest.TestCase):
    def test_finite_sample_quantile_uses_ceil_rank(self) -> None:
        self.assertEqual(finite_sample_quantile([0.1, 0.2, 0.3, 0.4], 0.25), 0.4)

    def test_cluster_fit_uses_worst_view_per_seed(self) -> None:
        rows = [
            {"seed": 2, "label_blocked": 0, "p_blocked": 0.1},
            {"seed": 2, "label_blocked": 0, "p_blocked": 0.4},
            {"seed": 4, "label_blocked": 0, "p_blocked": 0.2},
            {"seed": 3, "label_blocked": 1, "p_blocked": 0.9},
            {"seed": 3, "label_blocked": 1, "p_blocked": 0.6},
            {"seed": 5, "label_blocked": 1, "p_blocked": 0.8},
        ]
        result = fit_clustered_thresholds(rows, 0.2)
        self.assertAlmostEqual(result["clear"], 0.4)
        self.assertAlmostEqual(result["blocked"], 0.4)
        self.assertEqual(result["clear_worlds"], 2.0)

    def test_prediction_set_and_coverage(self) -> None:
        self.assertEqual(prediction_set(0.1, clear_threshold=0.2, blocked_threshold=0.2), ("clear",))
        self.assertEqual(prediction_set(0.5, clear_threshold=0.6, blocked_threshold=0.6), ("clear", "blocked"))
        rows = [
            {"label_blocked": 0, "p_blocked": 0.1},
            {"label_blocked": 1, "p_blocked": 0.9},
        ]
        result = coverage_metrics(rows, clear_threshold=0.2, blocked_threshold=0.2)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["singleton_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
