import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_v4_experiments import (
    EPISODE_SCHEMA,
    ERROR_SCHEMA,
    EpisodeSpec,
    RunnerConfig,
    experiment_matrix,
    physical_validation_matrix,
    run_job,
    run_matrix,
)


FAKE_SUCCESS = textwrap.dedent(
    """
    import argparse, json
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--motion-backend", default="skid-steer")
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--calibration")
    parser.add_argument("--allow-smoke-calibration", action="store_true")
    parser.add_argument("--device")
    args = parser.parse_args()
    counter = Path(__file__).with_suffix(".count")
    count = int(counter.read_text() if counter.exists() else "0") + 1
    counter.write_text(str(count))
    payload = {
        "schema_version": "look-twice.episode/v4",
        "configuration": {
            "policy": args.policy,
            "runtime": args.runtime,
            "motion_backend": (
                "kinematic-ci" if args.runtime == "synthetic" else args.motion_backend
            ),
        },
        "scenario": {
            "public_context": {"paired_world_id": "test-world"},
            "oracle_context": {"profile": args.profile, "seed": args.seed},
        },
        "metrics": {"safe_success": True, "unsafe_crossing": False},
        "outcome": {"mission_success": True},
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload))
    """
)

FAKE_FAILURE = "import sys; print('intentional failure', file=sys.stderr); sys.exit(7)\n"
FAKE_INCOMPLETE = textwrap.dedent(
    """
    import argparse, json
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", required=True, type=Path)
    args, _ = parser.parse_known_args()
    args.json_output.write_text(json.dumps({"schema_version": "wrong"}))
    """
)


class V4ExperimentRunnerTests(unittest.TestCase):
    def test_frozen_matrix_sizes_and_seed_ranges(self) -> None:
        smoke = experiment_matrix("smoke")
        formal = experiment_matrix("formal")
        physical = physical_validation_matrix()
        self.assertEqual(len(smoke), 6 * 8 * 2)
        self.assertEqual(len(formal), 6 * 8 * 20)
        self.assertEqual(len(physical), 3 * 4 * 5)
        self.assertEqual({spec.seed for spec in smoke}, {50000, 50001})
        self.assertEqual(
            {spec.seed for spec in formal}, set(range(50000, 50020))
        )
        self.assertEqual(
            {spec.policy for spec in physical},
            {"naive-majority", "purify-passive", "purify-active"},
        )

    def test_formal_constraints_and_synthetic_dev_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entrypoint = root / "entry.py"
            entrypoint.write_text(FAKE_SUCCESS)
            calibration = root / "calibration.json"
            calibration.write_text("{}")
            with self.assertRaisesRegex(ValueError, "formal mode requires --runtime genesis"):
                self.config(root, entrypoint, mode="formal", runtime="synthetic", calibration=calibration)
            with self.assertRaisesRegex(ValueError, "formal mode requires --calibration"):
                self.config(root, entrypoint, mode="formal", runtime="genesis")
            with self.assertRaisesRegex(ValueError, "kinematic CI"):
                self.config(root, entrypoint, runtime="synthetic", motion="skid-steer")

            formal = self.config(
                root,
                entrypoint,
                mode="formal",
                runtime="genesis",
                motion="skid-steer",
                calibration=calibration,
            )
            self.assertEqual(formal.runtime, "genesis")

    def test_success_is_atomic_and_matching_result_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entrypoint = root / "entry.py"
            entrypoint.write_text(FAKE_SUCCESS)
            config = self.config(root, entrypoint)
            spec = EpisodeSpec("naive-majority", "independent-noise", 50000)

            first = run_job(config, spec)
            self.assertEqual(first.status, "completed")
            payload = json.loads(first.output_path.read_text())
            self.assertEqual(payload["schema_version"], EPISODE_SCHEMA)
            self.assertEqual(payload["experiment_runner"]["policy"], spec.policy)
            self.assertFalse(any((root / "raw").glob("*.child-*.json")))

            second = run_job(config, spec)
            self.assertEqual(second.status, "skipped")
            self.assertEqual(entrypoint.with_suffix(".count").read_text(), "1")

    def test_schema_or_config_mismatch_is_not_treated_as_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entrypoint = root / "entry.py"
            entrypoint.write_text(FAKE_SUCCESS)
            config = self.config(root, entrypoint)
            spec = EpisodeSpec("v3-logodds", "time-skew", 50001)
            first = run_job(config, spec)
            payload = json.loads(first.output_path.read_text())
            payload["configuration"]["policy"] = "wrong-policy"
            first.output_path.write_text(json.dumps(payload))

            second = run_job(config, spec)
            self.assertEqual(second.status, "completed")
            self.assertEqual(entrypoint.with_suffix(".count").read_text(), "2")
            repaired = json.loads(second.output_path.read_text())
            self.assertEqual(repaired["configuration"]["policy"], spec.policy)

    def test_failure_writes_error_without_overwriting_previous_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            success_entry = root / "success.py"
            success_entry.write_text(FAKE_SUCCESS)
            spec = EpisodeSpec("lineage-only", "evidence-echo", 50000)
            success = run_job(self.config(root, success_entry), spec)
            original = success.output_path.read_bytes()

            failure_entry = root / "failure.py"
            failure_entry.write_text(FAKE_FAILURE)
            failure_config = self.config(root, failure_entry, device="cuda:0")
            failed = run_job(failure_config, spec)
            self.assertEqual(failed.status, "error")
            self.assertEqual(success.output_path.read_bytes(), original)
            error = json.loads(failed.error_path.read_text())
            self.assertEqual(error["schema_version"], ERROR_SCHEMA)
            self.assertEqual(error["returncode"], 7)
            self.assertIn("intentional failure", error["stderr_tail"])

    def test_successful_but_incomplete_child_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entrypoint = root / "incomplete.py"
            entrypoint.write_text(FAKE_INCOMPLETE)
            spec = EpisodeSpec("conformal-only", "ood-severity", 50001)
            result = run_job(self.config(root, entrypoint), spec)
            self.assertEqual(result.status, "error")
            self.assertFalse(result.output_path.exists())
            self.assertTrue(result.error_path.exists())

    def test_run_matrix_appends_durable_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entrypoint = root / "entry.py"
            entrypoint.write_text(FAKE_SUCCESS)
            config = self.config(root, entrypoint)
            specs = (
                EpisodeSpec("naive-majority", "independent-noise", 50000),
                EpisodeSpec("purify-active", "shared-occlusion", 50001),
            )
            counts = run_matrix(config, specs)
            self.assertEqual(counts, {"completed": 2, "skipped": 0, "error": 0})
            lines = (root / "results" / "progress.log").read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertTrue(all(json.loads(line)["status"] == "completed" for line in lines))
            summary = json.loads((root / "results" / "run_summary.json").read_text())
            self.assertEqual(summary["counts"], counts)

    @staticmethod
    def config(
        root,
        entrypoint,
        *,
        mode="smoke",
        runtime="synthetic",
        motion="kinematic",
        calibration=None,
        device=None,
    ):
        return RunnerConfig(
            mode=mode,
            runtime=runtime,
            motion_backend=motion,
            calibration=calibration,
            device=device,
            output_dir=root / "results",
            python=sys.executable,
            entrypoint=entrypoint,
        )


if __name__ == "__main__":
    unittest.main()

