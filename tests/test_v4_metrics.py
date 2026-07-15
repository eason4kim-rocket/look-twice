import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from v4_metrics import (
    EpisodeOutcome,
    aggregate_episode_outcomes,
    brier_score,
    conformal_coverage,
    conformal_miscoverage,
    expected_calibration_error,
    wilson_score_interval_95,
)


class V4MetricTests(unittest.TestCase):
    def test_wilson_score_interval_95(self) -> None:
        low, high = wilson_score_interval_95(5, 10)
        self.assertAlmostEqual(low, 0.236593, places=5)
        self.assertAlmostEqual(high, 0.763407, places=5)
        with self.assertRaises(ValueError):
            wilson_score_interval_95(0, 0)

    def test_brier_ece_and_conformal_metrics(self) -> None:
        self.assertAlmostEqual(brier_score([0.8, 0.4], [1, 0]), 0.1)
        self.assertAlmostEqual(
            expected_calibration_error([0.8, 0.4], [1, 0], bins=2), 0.3
        )
        sets = [("clear",), ("clear", "blocked")]
        labels = ["clear", "blocked"]
        self.assertEqual(conformal_coverage(sets, labels), 1.0)
        self.assertEqual(conformal_miscoverage(sets, labels), 0.0)

    def test_episode_aggregate_uses_event_specific_denominators(self) -> None:
        episodes = [
            EpisodeOutcome(
                unsafe_crossing=False,
                safe_success=True,
                wrong_detour=False,
                contract_repair_attempted=True,
                contract_repair_success=True,
                plan_invalidation_expected=True,
                plan_invalidation_correct=False,
                echo_present=True,
                echo_rejection_success=True,
                p_clear=0.9,
                true_label="clear",
                prediction_set=("clear",),
            ),
            EpisodeOutcome(
                unsafe_crossing=True,
                safe_success=False,
                wrong_detour=True,
                p_clear=0.2,
                true_label="blocked",
                prediction_set=("clear",),
            ),
            EpisodeOutcome(failed=True),
        ]
        result = aggregate_episode_outcomes(episodes)
        self.assertEqual(result["episodes"], 3)
        self.assertEqual(result["failed_episodes"], 1)
        self.assertEqual(result["unsafe_crossing_denominator"], 2)
        self.assertEqual(result["unsafe_crossing_count"], 1)
        self.assertEqual(result["contract_repair_success_denominator"], 1)
        self.assertEqual(result["plan_invalidation_correct_denominator"], 1)
        self.assertEqual(result["echo_rejection_success_denominator"], 1)
        self.assertAlmostEqual(result["brier_score"], 0.025)
        self.assertEqual(result["conformal_coverage"], 0.5)


class V4MetricCLITests(unittest.TestCase):
    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_calibration_cli_enforces_standard_split_and_supports_test_override(self) -> None:
        profiles = (
            "independent-noise",
            "shared-occlusion",
            "evidence-echo",
            "time-skew",
            "pose-calibration-drift",
            "structured-depth-dropout",
            "dynamic-change",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            standard = root / "standard.jsonl"
            rows = []
            for profile in profiles:
                for seed in range(30000, 30050):
                    clear = seed % 2 == 0
                    rows.append(
                        {
                            "seed": seed,
                            "profile": profile,
                            "noise_intensity": 0.2,
                            "sensor_version": "sensor-v4",
                            "true_label": "clear" if clear else "blocked",
                            "p_clear": 0.9 if clear else 0.1,
                        }
                    )
            standard.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            artifact = root / "calibration.json"
            completed = self.run_command(
                "scripts/build_v4_calibration.py",
                "--input",
                str(standard),
                "--output",
                str(artifact),
                "--git-commit",
                "test-commit",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["alpha"], 0.05)
            self.assertEqual(payload["seed_ranges"], [{"end": 30049, "start": 30000}])
            self.assertNotIn("ood-severity", payload["applicable_profiles"])

            small = root / "small.jsonl"
            small.write_text(
                json.dumps({**rows[0], "seed": 1, "true_label": "clear", "p_clear": 0.9})
                + "\n"
                + json.dumps({**rows[1], "seed": 2, "true_label": "blocked", "p_clear": 0.1})
                + "\n",
                encoding="utf-8",
            )
            rejected = self.run_command(
                "scripts/build_v4_calibration.py",
                "--input",
                str(small),
                "--output",
                str(root / "rejected.json"),
            )
            self.assertNotEqual(rejected.returncode, 0)
            allowed = self.run_command(
                "scripts/build_v4_calibration.py",
                "--input",
                str(small),
                "--output",
                str(root / "testing.json"),
                "--git-commit",
                "test-commit",
                "--allow-nonstandard-split",
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_summarizer_preserves_failed_records_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "raw"
            output = root / "summary"
            inputs.mkdir()

            def episode(policy, safe, unsafe):
                return {
                    "schema_version": 4,
                    "configuration": {
                        "policy": policy,
                        "profile": "evidence-echo",
                        "seed": 50000,
                    },
                    "metrics": {
                        "safe_success": safe,
                        "unsafe_crossing": unsafe,
                        "wrong_detour": False,
                        "echo_present": True,
                        "echo_rejection_success": policy == "purify-active",
                        "p_clear": 0.9 if safe else 0.2,
                        "true_label": "clear",
                        "prediction_set": ["clear"] if safe else ["blocked"],
                        "observation_count": 2,
                        "path_length": 4.0,
                    },
                }

            (inputs / "one.json").write_text(
                json.dumps(episode("naive-majority", False, True)), encoding="utf-8"
            )
            (inputs / "two.jsonl").write_text(
                json.dumps(episode("purify-active", True, False)) + "\n{" + "\n",
                encoding="utf-8",
            )
            command = (
                "scripts/summarize_v4_experiments.py",
                "--input",
                str(inputs),
                "--output-dir",
                str(output),
            )
            first = self.run_command(*command)
            self.assertEqual(first.returncode, 0, first.stderr)
            snapshots = {
                name: (output / name).read_bytes()
                for name in ("runs.csv", "aggregate.csv", "paired_comparisons.csv")
            }
            second = self.run_command(*command)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                snapshots,
                {name: (output / name).read_bytes() for name in snapshots},
            )
            with (output / "runs.csv").open(newline="", encoding="utf-8") as handle:
                runs = list(csv.DictReader(handle))
            self.assertEqual(len(runs), 3)
            self.assertNotIn("raw_json", runs[0])
            self.assertEqual(len(runs[0]["record_sha256"]), 64)
            self.assertEqual(sum(row["failure_type"] == "load_error" for row in runs), 1)
            self.assertTrue(any(row["unsafe_crossing"] == "True" for row in runs))
            with (output / "paired_comparisons.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                paired = list(csv.DictReader(handle))
            self.assertTrue(
                any(row["metric"] == "safe_success" and row["eligible_pairs"] == "1" for row in paired)
            )

    def test_summarizer_understands_real_v4_episode_and_ignores_runner_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            output = root / "summary"
            raw.mkdir()
            episode = {
                "schema_version": "look-twice.episode/v4",
                "configuration": {"policy": "purify-active"},
                "scenario": {
                    "oracle_context": {
                        "profile": "dynamic-change",
                        "seed": 50000,
                    }
                },
                "metrics": {
                    "safe_success": True,
                    "unsafe_crossing": False,
                    "wrong_detour": False,
                    "p_clear": 0.9,
                    "true_label": "clear",
                    "prediction_set": ["clear"],
                },
                "outcome": {"mission_success": True},
            }
            (raw / "episode.json").write_text(json.dumps(episode), encoding="utf-8")
            (root / "run_summary.json").write_text(
                json.dumps(
                    {
                        "schema_version": "look-twice.experiment-summary/v4",
                        "counts": {"completed": 1},
                    }
                ),
                encoding="utf-8",
            )
            completed = self.run_command(
                "scripts/summarize_v4_experiments.py",
                "--input",
                str(root),
                "--output-dir",
                str(output),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with (output / "runs.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "completed")
            self.assertEqual(rows[0]["profile"], "dynamic-change")
            self.assertEqual(rows[0]["seed"], "50000")


if __name__ == "__main__":
    unittest.main()
