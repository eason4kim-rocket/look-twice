import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_conformal import (
    CalibrationArtifact,
    CalibrationContext,
    CalibrationSample,
    finite_sample_quantile,
    fit_class_conditional_calibration,
)


def samples():
    result = []
    for seed in range(30000, 30010):
        result.append(CalibrationSample(seed, "independent-noise", 0.2, "sensor-v4", "clear", 0.92))
        result.append(CalibrationSample(seed, "independent-noise", 0.2, "sensor-v4", "blocked", 0.08))
    return result


class V4ConformalTests(unittest.TestCase):
    def test_finite_sample_quantile(self) -> None:
        self.assertEqual(finite_sample_quantile([0.1, 0.2, 0.3, 0.4], 0.2), 0.4)

    def test_fit_is_order_independent_and_hash_is_stable(self) -> None:
        first = fit_class_conditional_calibration(samples(), git_commit="abc123")
        second = fit_class_conditional_calibration(reversed(samples()), git_commit="abc123")
        self.assertEqual(first, second)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.seed_ranges[0].start, 30000)
        self.assertEqual(first.seed_ranges[0].end, 30009)

    def test_prediction_and_fail_closed_applicability(self) -> None:
        artifact = fit_class_conditional_calibration(samples(), git_commit="abc123")
        context = CalibrationContext("independent-noise", 0.2, "sensor-v4")
        self.assertEqual(artifact.predict(p_clear=0.95, context=context).prediction_set, ("clear",))
        self.assertEqual(artifact.predict(p_clear=0.05, context=context).prediction_set, ("blocked",))

        ood = CalibrationContext("ood-severity", 0.9, "sensor-v4")
        result = artifact.predict(p_clear=0.99, context=ood)
        self.assertFalse(result.applicable)
        self.assertEqual(result.prediction_set, ("clear", "blocked"))
        self.assertEqual(result.applicability_reason, "profile_not_calibrated")

    def test_sensor_version_and_noise_range_are_checked(self) -> None:
        artifact = fit_class_conditional_calibration(samples(), git_commit="abc123")
        wrong_sensor = artifact.check_applicability(
            CalibrationContext("independent-noise", 0.2, "sensor-v3")
        )
        self.assertEqual(wrong_sensor.reason, "sensor_version_mismatch")
        high_noise = artifact.check_applicability(
            CalibrationContext("independent-noise", 0.8, "sensor-v4")
        )
        self.assertEqual(high_noise.reason, "noise_intensity_out_of_range")

    def test_artifact_round_trip(self) -> None:
        artifact = fit_class_conditional_calibration(samples(), git_commit="abc123")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            artifact.save(path)
            self.assertEqual(CalibrationArtifact.load(path), artifact)


if __name__ == "__main__":
    unittest.main()
