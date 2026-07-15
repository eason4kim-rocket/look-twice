import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from analyze_v3_results import bootstrap_mean_interval, expected_calibration_error


class V3AnalysisTests(unittest.TestCase):
    def test_perfect_calibration_has_zero_error(self) -> None:
        samples = [(0.0, 0.0)] * 5 + [(1.0, 1.0)] * 5
        self.assertEqual(expected_calibration_error(samples), 0.0)

    def test_bootstrap_is_reproducible(self) -> None:
        first = bootstrap_mean_interval([1.0, 2.0, 3.0])
        second = bootstrap_mean_interval([1.0, 2.0, 3.0])
        self.assertEqual(first, second)
        self.assertEqual(first[0], 2.0)


if __name__ == "__main__":
    unittest.main()
