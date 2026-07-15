import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from scripts.collect_v4_calibration import (
    FORMAL_SEEDS,
    ID_PROFILES,
    REQUIRED_SAMPLE_FIELDS,
    ROW_SCHEMA,
    CalibrationSpec,
    CollectorConfig,
    _worker_command,
    calibration_matrix,
    collect_specs,
)
from v4_evidence import SENSOR_VERSION
from v4_scenario import sample_v4_scenario


class V4CalibrationCollectorTests(unittest.TestCase):
    def test_frozen_paired_split_excludes_ood(self) -> None:
        smoke = calibration_matrix("smoke")
        formal = calibration_matrix("formal")
        self.assertEqual(len(smoke), 7 * 2)
        self.assertEqual(len(formal), 7 * 50)
        self.assertNotIn("ood-severity", ID_PROFILES)
        self.assertEqual({spec.seed for spec in formal}, set(FORMAL_SEEDS))
        with self.assertRaisesRegex(ValueError, "forbidden"):
            CalibrationSpec("ood-severity", 30000)

    def test_synthetic_two_seed_collection_fields_pairing_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            specs = calibration_matrix("smoke")
            with contextlib.redirect_stdout(io.StringIO()):
                first = collect_specs(config, specs)
            self.assertEqual(first, {"completed": 14, "skipped": 0, "error": 0})
            first_jsonl = config.output_jsonl.read_bytes()
            rows = [
                json.loads(line)
                for line in config.output_jsonl.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 14)
            self.assertEqual(
                [(row["profile"], row["seed"]) for row in rows],
                sorted((row["profile"], row["seed"]) for row in rows),
            )
            for row in rows:
                self.assertEqual(row["schema_version"], ROW_SCHEMA)
                self.assertTrue(all(field in row for field in REQUIRED_SAMPLE_FIELDS))
                self.assertEqual(row["sensor_version"], SENSOR_VERSION)
                self.assertIn(row["true_label"], {"clear", "blocked"})
                self.assertGreaterEqual(row["p_clear"], 0.0)
                self.assertLessEqual(row["p_clear"], 1.0)
                self.assertEqual(len(row["receipt_sha256"]), 64)
                self.assertEqual(
                    set(row["raw_artifact_sha256"]),
                    {"rgb", "depth", "segmentation"},
                )
                self.assertEqual(
                    set(row["corrupted_artifact_sha256"]),
                    {"rgb", "depth", "segmentation"},
                )
                self.assertFalse(row["gpu_environment"]["formal_result_eligible"])
                scenario = sample_v4_scenario(row["profile"], row["seed"])
                expected = (
                    "blocked"
                    if scenario.truth_blocked_at(row["capture_step"])
                    else "clear"
                )
                self.assertEqual(row["true_label"], expected)

            for seed in (30000, 30001):
                paired_ids = {
                    row["paired_world_id"] for row in rows if row["seed"] == seed
                }
                self.assertEqual(len(paired_ids), 1)

            with contextlib.redirect_stdout(io.StringIO()):
                second = collect_specs(config, specs)
            self.assertEqual(second, {"completed": 0, "skipped": 14, "error": 0})
            self.assertEqual(config.output_jsonl.read_bytes(), first_jsonl)

    def test_pose_drift_discards_mismatched_score_and_calibrates_base_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            spec = CalibrationSpec("pose-calibration-drift", 30000)
            with contextlib.redirect_stdout(io.StringIO()):
                counts = collect_specs(config, (spec,))
            self.assertEqual(counts["error"], 0)
            row = json.loads(config.output_jsonl.read_text())
            self.assertEqual(row["sensor_version"], SENSOR_VERSION)
            self.assertEqual(row["observed_sensor_version"], SENSOR_VERSION)
            discarded = row["discarded_nonapplicable_capture"]
            self.assertIsNotNone(discarded)
            self.assertNotEqual(discarded["observed_sensor_version"], SENSOR_VERSION)
            self.assertEqual(
                discarded["reason"],
                "sensor_version_not_applicable_to_calibration_artifact",
            )
            self.assertTrue(row["calibration_applicable_during_collection"])
            self.assertIsInstance(row["p_clear"], float)

    def test_formal_requires_genesis_and_rocm_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "requires --runtime genesis"):
                self.config(root, mode="formal", runtime="synthetic", device="cuda:0")
            with self.assertRaisesRegex(ValueError, "requires a ROCm"):
                self.config(root, mode="formal", runtime="genesis", device="cpu")
            formal = self.config(
                root, mode="formal", runtime="genesis", device="cuda:0"
            )
            self.assertEqual(formal.motion_backend, "kinematic")

    def test_genesis_worker_is_one_independent_subprocess_per_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(
                root,
                mode="formal",
                runtime="genesis",
                device="cuda:0",
            )
            spec = CalibrationSpec("independent-noise", 30000)
            command = _worker_command(config, spec, root / "row.json")
            self.assertIn("--worker", command)
            self.assertIn("--worker-profile", command)
            self.assertIn("--worker-seed", command)
            self.assertEqual(command[0], sys.executable)

    @staticmethod
    def config(
        root,
        *,
        mode="smoke",
        runtime="synthetic",
        device="cpu",
    ):
        return CollectorConfig(
            mode=mode,
            runtime=runtime,
            motion_backend="kinematic",
            device=device,
            output_dir=root / "collection",
            output_jsonl=root / "collection" / "calibration.jsonl",
            python=sys.executable,
            script=REPO_ROOT / "scripts" / "collect_v4_calibration.py",
        )


if __name__ == "__main__":
    unittest.main()
