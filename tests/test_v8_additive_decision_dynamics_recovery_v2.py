from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.run_v8_additive_decision_dynamics_bridge import (
    FORMAL_SEEDS,
    assess_trial,
    load_formal_cases,
    sha256_file,
)
from scripts.run_v8_additive_decision_dynamics_recovery_v2 import (
    BINDING_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_INPUT_REPORT,
    PROGRESS_SCHEMA_VERSION,
    atomic_publish_json,
    atomic_write_json,
    bound_source_paths,
    build_report,
    canonical_json,
    checkpoint_errors,
    scientific_parameters,
    source_binding_sha256,
)
from scripts.verify_v8_additive_decision_dynamics_recovery_v2 import validate_report


ROOT = Path(__file__).resolve().parents[1]


def motion(path: float, *, drift: float = 0.01) -> dict[str, object]:
    return {
        "reached": True,
        "reason": "reached",
        "start_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        "final_pose": {"x": path, "y": 0.0, "yaw": 0.0},
        "final_goal_error_m": 0.10,
        "waypoints": [[path, 0.0]],
        "path_length_m": path,
        "elapsed_steps": 500,
        "max_tilt_deg": 5.0,
        "stationary_partner_drift_m": drift,
        "obstacle_contact_rows": 0,
        "stationary_obstacle_contact_rows": 0,
        "partner_contact_rows": 0,
        "max_abs_wheel_target_rad_s": 2.0,
        "trajectory_samples": [],
    }


def fake_args(output_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        backend="amdgpu",
        dt=0.02,
        settle_steps=80,
        maximum_steps_per_waypoint=1800,
        tolerance=0.14,
        drive_sign=-1.0,
        record_stride=50,
        worker_timeout_seconds=3600,
        engineering_smoke=False,
        input_report=DEFAULT_INPUT_REPORT,
        output_dir=output_dir,
    )


def fake_trial(case: object) -> dict[str, object]:
    direct = bool(case.full_chain_direct)  # type: ignore[attr-defined]
    row: dict[str, object] = {
        "seed": case.seed,  # type: ignore[attr-defined]
        "decision": {
            "selected_corridor": case.selected_corridor,  # type: ignore[attr-defined]
            "full_chain_direct": direct,
            "corridor_a_blocked": case.corridor_a_blocked,  # type: ignore[attr-defined]
            "corridor_b_blocked": case.corridor_b_blocked,  # type: ignore[attr-defined]
            "selected_corridor_clear": case.selected_corridor_clear,  # type: ignore[attr-defined]
            "both_corridors_blocked": case.both_corridors_blocked,  # type: ignore[attr-defined]
            "archived_episode_sha256": case.archived_episode_sha256,  # type: ignore[attr-defined]
            "input_class": case.input_class,  # type: ignore[attr-defined]
        },
        "blocked_corridors": [],
        "script_entity_pose_writes_after_build": 0,
        "active_scout": motion(1.0),
        "active_carrier": motion(4.8 if direct else 6.2),
        "passive_carrier": motion(6.2, drift=0.0),
    }
    row["assessment"] = assess_trial(row)
    return row


class RecoveryV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_formal_cases(DEFAULT_INPUT_REPORT)

    def binding(self, args: SimpleNamespace) -> dict[str, object]:
        return {
            "schema_version": BINDING_SCHEMA_VERSION,
            "created_at_utc": "2026-08-05T00:00:00+00:00",
            "run_class": "formal",
            "git_commit": "f" * 40,
            "git_branch": "test",
            "git_status_porcelain_at_initial_start": "",
            "scientific_parameters": scientific_parameters(args),
            "source_files": {
                name: {
                    "path": str(path.resolve().relative_to(ROOT)),
                    "sha256": sha256_file(path),
                }
                for name, path in bound_source_paths(DEFAULT_INPUT_REPORT).items()
            },
            "decision_input": {
                "path": str(DEFAULT_INPUT_REPORT.resolve().relative_to(ROOT)),
                "sha256": sha256_file(DEFAULT_INPUT_REPORT),
                "consumed_in_this_run": True,
            },
            "integrity_rule": "test fixture",
        }

    def checkpoint(
        self, case: object, index: int, binding: dict[str, object]
    ) -> dict[str, object]:
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "generated_at_utc": "2026-08-05T00:00:00+00:00",
            "run_class": "formal",
            "seed": case.seed,  # type: ignore[attr-defined]
            "seed_index": index,
            "source_binding_sha256": source_binding_sha256(binding),
            "source_binding_matched_preflight": True,
            "source_binding_matched_postflight": True,
            "execution": {
                "layout": "one_fixed_seed_per_fresh_genesis_subprocess",
                "original_v1_spatial_index": index,
                "genesis_scenes_in_this_checkpoint": 1,
                "non_fixed_robot_entities": 3,
                "active_and_passive_replicas_share_scene": True,
                "cross_seed_entities_share_scene": False,
                "post_build_actuation_api": "control_dofs_velocity only",
                "post_build_entity_pose_writes": 0,
            },
            "environment": {
                "python": "3.12.0",
                "genesis": "1.1.2",
                "torch": "2.9.1+rocm7.2",
                "torch_hip": "7.2",
                "backend_requested": "amdgpu",
                "gpu": "AMD Radeon AI PRO R9700",
            },
            "trial": fake_trial(case),
        }

    def build_fixture(self, output: Path) -> tuple[Path, dict[str, object]]:
        args = fake_args(output)
        binding = self.binding(args)
        output.mkdir()
        atomic_write_json(output / "SOURCE_BINDING.json", binding)
        checkpoint_paths: list[Path] = []
        attempt_lines: list[str] = []
        for index, case in enumerate(self.cases):
            checkpoint_path = output / "TRIALS" / f"{case.seed}.json"
            atomic_publish_json(checkpoint_path, self.checkpoint(case, index, binding))
            checkpoint_paths.append(checkpoint_path)
            attempt_lines.append(
                json.dumps(
                    {
                        "seed": case.seed,
                        "checkpoint_sealed": True,
                        "checkpoint_path": str(checkpoint_path.relative_to(output)),
                        "checkpoint_sha256": sha256_file(checkpoint_path),
                    },
                    sort_keys=True,
                )
            )
        (output / "ATTEMPTS.jsonl").write_text(
            "\n".join(attempt_lines) + "\n", encoding="utf-8"
        )
        atomic_write_json(
            output / "PROGRESS.json",
            {
                "schema_version": PROGRESS_SCHEMA_VERSION,
                "run_class": "formal",
                "source_binding_sha256": source_binding_sha256(binding),
                "fixed_seed_order": list(FORMAL_SEEDS),
                "sealed_prefix_count": 30,
                "sealed_prefix_seeds": list(FORMAL_SEEDS),
                "sealed_checkpoint_sha256": [
                    sha256_file(path) for path in checkpoint_paths
                ],
                "next_seed": None,
                "outcomes_exposed_in_progress_file": False,
            },
        )
        report = build_report(
            args=args,
            binding=binding,
            cases=self.cases,
            checkpoint_paths=checkpoint_paths,
            output_dir=output,
        )
        report_path = output / "REPORT.json"
        atomic_write_json(report_path, report)
        return report_path, report

    def test_full_fake_formal_report_passes_fail_closed_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            self.assertEqual(
                validate_report(report, report_path=report_path),
                [],
            )

    def test_checkpoint_recomputes_assessment_and_rejects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = fake_args(Path(directory) / "output")
            binding = self.binding(args)
            checkpoint = self.checkpoint(self.cases[0], 0, binding)
            checkpoint["trial"]["active_carrier"]["obstacle_contact_rows"] = 1  # type: ignore[index]
            errors = checkpoint_errors(
                checkpoint,
                case=self.cases[0],
                index=0,
                run_class="formal",
                binding_sha256=source_binding_sha256(binding),
            )
            self.assertTrue(any("assessment" in error for error in errors))

    def test_verifier_rejects_checkpoint_hash_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["checkpoint_index"][0]["sha256"] = "0" * 64  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("hash mismatch" in error for error in errors))

    def test_verifier_rejects_seed_reorder_and_duplicate_seal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["trials"][0], report["trials"][1] = (  # type: ignore[index]
                report["trials"][1],  # type: ignore[index]
                report["trials"][0],  # type: ignore[index]
            )
            attempts = report_path.parent / "ATTEMPTS.jsonl"
            attempts.write_text(
                attempts.read_text(encoding="utf-8")
                + attempts.read_text(encoding="utf-8").splitlines()[0]
                + "\n",
                encoding="utf-8",
            )
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("trial seed order" in error for error in errors))
            self.assertTrue(any("repeated sealed seed" in error for error in errors))

    def test_verifier_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["checkpoint_index"][0]["path"] = "../outside.json"  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("escapes output root" in error for error in errors))

    def test_atomic_publish_never_overwrites_a_sealed_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "sealed.json"
            atomic_publish_json(target, {"value": 1})
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                atomic_publish_json(target, {"value": 2})
            self.assertEqual(target.read_bytes(), original)

    def test_nonfinite_json_is_rejected_before_publication(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json({"bad": float("nan")})

    def test_source_binding_change_invalidates_every_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = fake_args(Path(directory) / "output")
            binding = self.binding(args)
            checkpoint = self.checkpoint(self.cases[0], 0, binding)
            changed = copy.deepcopy(binding)
            changed["scientific_parameters"]["goal_tolerance_m"] = 0.15  # type: ignore[index]
            errors = checkpoint_errors(
                checkpoint,
                case=self.cases[0],
                index=0,
                run_class="formal",
                binding_sha256=source_binding_sha256(changed),
            )
            self.assertTrue(any("source_binding_sha256" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
