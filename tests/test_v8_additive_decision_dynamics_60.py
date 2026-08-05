from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.run_v8_additive_decision_dynamics_60 import (
    BINDING_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_INPUT_REPORT,
    EMPTY_PREFIX_SHA256,
    PROGRESS_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    _execution_facts,
    bound_source_paths,
    canonical_json,
    checkpoint_content_sha256,
    extend_prefix_sha256,
    scientific_parameters,
    source_binding_sha256,
    summarize_trials,
    trial_sha256,
)
from scripts.run_v8_additive_decision_dynamics_bridge import (
    assess_trial,
    load_formal_cases,
    sha256_file,
    trial_layout,
)
from scripts.verify_v8_additive_decision_dynamics_60 import (
    FORMAL_SEEDS,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]


def motion(
    path: float,
    *,
    start: tuple[float, float, float],
    waypoints: list[tuple[float, float]],
    drift: float = 0.01,
) -> dict[str, object]:
    final_target = waypoints[-1]
    final_pose = {"x": final_target[0] - 0.10, "y": final_target[1], "yaw": 0.0}
    return {
        "reached": True,
        "reason": "reached",
        "start_pose": {"x": start[0], "y": start[1], "yaw": 0.0},
        "final_pose": final_pose,
        "final_goal_error_m": 0.10,
        "waypoints": [list(point) for point in waypoints],
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
        engineering_smoke=False,
        input_report=DEFAULT_INPUT_REPORT,
        output_dir=output_dir,
    )


def fake_trial(case: object, index: int) -> dict[str, object]:
    direct = bool(case.full_chain_direct)  # type: ignore[attr-defined]
    layout = trial_layout(case, index)  # type: ignore[arg-type]
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
        "blocked_corridors": layout["blocked_corridors"],
        "script_entity_pose_writes_after_build": 0,
        "active_scout": motion(
            1.0,
            start=layout["active_scout_start"],
            waypoints=layout["active_scout_waypoints"],
        ),
        "active_carrier": motion(
            4.8 if direct else 6.2,
            start=layout["active_carrier_start"],
            waypoints=layout["active_carrier_waypoints"],
        ),
        "passive_carrier": motion(
            6.2,
            start=layout["passive_carrier_start"],
            waypoints=layout["passive_carrier_waypoints"],
            drift=0.0,
        ),
    }
    row["assessment"] = assess_trial(row)
    return row


class DecisionDynamics60VerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_formal_cases(DEFAULT_INPUT_REPORT)[:20]
        self.assertEqual([case.seed for case in self.cases], list(FORMAL_SEEDS))

    def _binding(
        self, args: SimpleNamespace, attempt_identity: dict[str, object]
    ) -> dict[str, object]:
        return {
            "schema_version": BINDING_SCHEMA_VERSION,
            "created_at_utc": "2026-08-05T00:00:00+00:00",
            "run_class": "formal",
            "git_commit": "f" * 40,
            "git_branch": "test",
            "git_status_porcelain_at_start": "",
            "attempt_identity": attempt_identity,
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
            "integrity_rule": "partial checkpoints are never a full result",
        }

    def _write_checksums(self, output: Path) -> None:
        paths = [
            output / "SOURCE_BINDING.json",
            output / "PROGRESS.json",
            *[output / "TRIALS" / f"{seed}.json" for seed in FORMAL_SEEDS],
            output / "REPORT.json",
        ]
        (output / "SHA256SUMS").write_text(
            "".join(
                f"{sha256_file(path)}  {path.relative_to(output)}\n" for path in paths
            ),
            encoding="utf-8",
        )

    def build_fixture(self, output: Path) -> tuple[Path, dict[str, object]]:
        output.mkdir()
        (output / "TRIALS").mkdir()
        args = fake_args(output)
        attempt_id = "a" * 64
        attempt_identity: dict[str, object] = {
            "attempt_id": attempt_id,
            "process_identity": "test-host:pid:4242",
            "process_id": 4242,
            "genesis_initialization_id": (f"{attempt_id}:genesis-initialization-0"),
            "single_scene_id": f"{attempt_id}:genesis-scene-0",
            "scene_build_id": f"{attempt_id}:scene-build-0",
        }
        binding = self._binding(args, attempt_identity)
        (output / "SOURCE_BINDING.json").write_bytes(canonical_json(binding))
        binding_sha = source_binding_sha256(binding)
        execution = _execution_facts(
            run_class="formal",
            trial_count=20,
            attempt_identity=attempt_identity,
        )
        trials: list[dict[str, object]] = []
        checkpoint_index: list[dict[str, object]] = []
        checkpoint_paths: list[Path] = []
        prefix_sha256 = EMPTY_PREFIX_SHA256
        for index, case in enumerate(self.cases):
            trial = fake_trial(case, index)
            checkpoint = {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "generated_at_utc": "2026-08-05T00:00:00+00:00",
                "run_class": "formal",
                "trial_index": index,
                "seed_index": index,
                "seed": case.seed,
                **attempt_identity,
                "source_binding_sha256": binding_sha,
                "trial_sha256": trial_sha256(trial),
                "previous_prefix_sha256": prefix_sha256,
                "source_binding_matched_preflight": True,
                "source_binding_matched_postflight": True,
                "partial_evidence_only": True,
                "partial_checkpoints_are_full_results": False,
                "resume_supported": False,
                "timing": {
                    "started_at_utc": "2026-08-05T00:00:00+00:00",
                    "ended_at_utc": "2026-08-05T00:01:00+00:00",
                    "wall_seconds": 60.0,
                    "non_scientific_observability_only": True,
                },
                "execution": execution,
                "trial": trial,
            }
            checkpoint["checkpoint_content_sha256"] = checkpoint_content_sha256(
                checkpoint
            )
            checkpoint_path = output / "TRIALS" / f"{case.seed}.json"
            checkpoint_path.write_bytes(canonical_json(checkpoint))
            checkpoint_paths.append(checkpoint_path)
            trials.append(trial)
            prefix_after = extend_prefix_sha256(
                prefix_sha256, str(checkpoint["checkpoint_content_sha256"])
            )
            checkpoint_index.append(
                {
                    "trial_index": index,
                    "seed": case.seed,
                    "path": str(checkpoint_path.relative_to(output)),
                    "sha256": sha256_file(checkpoint_path),
                    "trial_sha256": trial_sha256(trial),
                    "previous_prefix_sha256": prefix_sha256,
                    "checkpoint_content_sha256": checkpoint[
                        "checkpoint_content_sha256"
                    ],
                    "prefix_sha256_after": prefix_after,
                    "partial_evidence_only": True,
                }
            )
            prefix_sha256 = prefix_after
        progress = {
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "updated_at_utc": "2026-08-05T00:00:00+00:00",
            "run_class": "formal",
            **attempt_identity,
            "source_binding_sha256": binding_sha,
            "fixed_seed_order": list(FORMAL_SEEDS),
            "sealed_prefix_count": 20,
            "sealed_prefix_seeds": list(FORMAL_SEEDS),
            "sealed_checkpoint_sha256": [
                sha256_file(path) for path in checkpoint_paths
            ],
            "sealed_prefix_sha256": prefix_sha256,
            "next_seed": None,
            "partial_evidence_only": True,
            "partial_checkpoints_are_full_results": False,
            "resume_supported": False,
            "outcomes_exposed_in_progress_file": False,
        }
        (output / "PROGRESS.json").write_bytes(canonical_json(progress))
        report: dict[str, object] = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at_utc": "2026-08-05T00:00:00+00:00",
            "run_class": "formal",
            "boundary": {
                "additive_non_locked": True,
                "formal_result_eligible": False,
                "changes_frozen_v8_endpoint": False,
                "uses_archived_decisions_without_rerunning_policy": True,
                "oracle_used_by_controller": False,
                "single_scene_60_body_execution": True,
                "cross_seed_entities_co_resident": True,
                "fixed_order_serial_actuation": True,
                "simultaneous_cooperative_control": False,
                "partial_checkpoints_are_full_results": False,
                "resume_supported": False,
                "teardown_guard_enabled": True,
            },
            "source": {
                "git_commit": binding["git_commit"],
                "git_branch": binding["git_branch"],
                "git_status_porcelain_at_start": "",
                "source_binding_path": "SOURCE_BINDING.json",
                "source_binding_sha256": binding_sha,
                "source_files": binding["source_files"],
            },
            "decision_input": {
                **binding["decision_input"],  # type: ignore[dict-item]
                "fixed_seeds": list(FORMAL_SEEDS),
            },
            "attempt_identity": attempt_identity,
            "execution": execution,
            "checkpoint_chain": {
                "empty_prefix_sha256": EMPTY_PREFIX_SHA256,
                "final_prefix_sha256": prefix_sha256,
                "checkpoint_count": 20,
                "content_hash_rule": (
                    "SHA256(canonical checkpoint JSON with the "
                    "checkpoint_content_sha256 field omitted)"
                ),
                "prefix_hash_rule": (
                    "SHA256(canonical {previous_prefix_sha256, "
                    "checkpoint_content_sha256})"
                ),
            },
            "environment": {
                "python": "3.12",
                "genesis": "1.1.2",
                "torch": "2.9.1+rocm",
                "torch_hip": "7.2",
                "backend_requested": "amdgpu",
                "gpu": "AMD Radeon",
                "single_process_id": attempt_identity["process_id"],
                "process_identity": attempt_identity["process_identity"],
                "genesis_initialization_id": attempt_identity[
                    "genesis_initialization_id"
                ],
                "single_scene_id": attempt_identity["single_scene_id"],
                "scene_build_id": attempt_identity["scene_build_id"],
            },
            "protocol": {
                **binding["scientific_parameters"],  # type: ignore[dict-item]
                "post_build_controller_configuration_apis": [
                    "set_dofs_kp",
                    "set_dofs_kv",
                    "set_dofs_force_range",
                ],
                "post_build_motion_actuation_api": "control_dofs_velocity only",
                "post_build_entity_pose_writes": 0,
            },
            "checkpoint_index": checkpoint_index,
            "summary": summarize_trials(trials, "formal"),
            "trials": trials,
        }
        report_path = output / "REPORT.json"
        report_path.write_bytes(canonical_json(report))
        self._write_checksums(output)
        return report_path, report

    def test_complete_20_of_20_single_scene_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            self.assertEqual(validate_report(report, report_path=report_path), [])

    def test_partial_checkpoint_is_never_accepted_as_full_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, _ = self.build_fixture(Path(directory) / "output")
            checkpoint_path = report_path.parent / "TRIALS" / "102500.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            errors = validate_report(checkpoint, report_path=checkpoint_path)
            self.assertTrue(
                any("only an atomically sealed REPORT.json" in e for e in errors)
            )
            self.assertTrue(any("requires 20 trials" in e for e in errors))

    def test_report_with_19_trials_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["trials"] = report["trials"][:-1]  # type: ignore[index]
            report["checkpoint_index"] = report["checkpoint_index"][:-1]  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("requires 20 trials" in e for e in errors))
            self.assertTrue(any("partial checkpoint prefix" in e for e in errors))

    def test_duplicate_or_reordered_seed_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            trials = report["trials"]  # type: ignore[assignment]
            trials[1] = copy.deepcopy(trials[0])
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("trial seed order" in e for e in errors))
            self.assertTrue(any("duplicate seeds" in e for e in errors))

    def test_single_scene_and_serial_claims_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["execution"]["genesis_scene_count"] = 20  # type: ignore[index]
            report["execution"]["cross_seed_entities_share_scene"] = False  # type: ignore[index]
            report["boundary"]["simultaneous_cooperative_control"] = True  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("genesis_scene_count" in e for e in errors))
            self.assertTrue(any("cross_seed_entities_share_scene" in e for e in errors))
            self.assertTrue(
                any("simultaneous_cooperative_control" in e for e in errors)
            )

    def test_contact_and_mean_reduction_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            first = report["trials"][0]  # type: ignore[index]
            first["active_carrier"]["obstacle_contact_rows"] = 1  # type: ignore[index]
            for row in report["trials"]:  # type: ignore[union-attr]
                row["active_carrier"]["path_length_m"] = 5.8
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("obstacle_contact_rows" in e for e in errors))
            self.assertTrue(any("direct-pair saving" in e for e in errors))

    def test_motion_source_binding_is_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            binding_path = report_path.parent / "SOURCE_BINDING.json"
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            del binding["source_files"]["motion_source"]
            binding_path.write_bytes(canonical_json(binding))
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("motion_source" in e for e in errors))

    def test_checkpoint_hash_and_teardown_guard_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["checkpoint_index"][0]["sha256"] = "0" * 64  # type: ignore[index]
            del report["execution"]["teardown_guard_enabled"]  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("checkpoint 102500 hash" in e for e in errors))
            self.assertTrue(any("teardown_guard_enabled" in e for e in errors))

    def test_cross_attempt_checkpoint_and_broken_prefix_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            checkpoint_path = report_path.parent / "TRIALS" / "102501.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["attempt_id"] = "b" * 64
            checkpoint["previous_prefix_sha256"] = "0" * 64
            checkpoint["checkpoint_content_sha256"] = checkpoint_content_sha256(
                checkpoint
            )
            checkpoint_path.write_bytes(canonical_json(checkpoint))
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("checkpoint 102501.attempt_id" in e for e in errors))
            self.assertTrue(
                any("checkpoint 102501 previous prefix" in e for e in errors)
            )

    def test_engineering_smoke_is_not_accepted_as_formal_full_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["run_class"] = "engineering_smoke"
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("run_class" in error for error in errors))

    def test_route_geometry_and_goal_error_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            first = report["trials"][0]  # type: ignore[index]
            first["blocked_corridors"] = []
            first["active_carrier"]["waypoints"][0][0] += 1.0  # type: ignore[index]
            first["passive_carrier"]["final_goal_error_m"] = 0.05  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("blocked_corridors" in error for error in errors))
            self.assertTrue(
                any("active_carrier.waypoints" in error for error in errors)
            )
            self.assertTrue(
                any(
                    "passive_carrier.final_goal_error_m" in error
                    and "inconsistent" in error
                    for error in errors
                )
            )

    def test_checkpoint_chain_report_fields_are_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            chain = report["checkpoint_chain"]  # type: ignore[assignment]
            chain["empty_prefix_sha256"] = "0" * 64
            chain["checkpoint_count"] = 19
            chain["final_prefix_sha256"] = "f" * 64
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(
                any("checkpoint_chain.empty_prefix_sha256" in error for error in errors)
            )
            self.assertTrue(
                any("checkpoint_chain.checkpoint_count" in error for error in errors)
            )
            self.assertTrue(
                any("checkpoint_chain.final_prefix_sha256" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
