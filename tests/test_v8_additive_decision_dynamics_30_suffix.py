from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_v8_additive_decision_dynamics_30_suffix import (
    BINDING_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_INPUT_REPORT,
    EMPTY_PREFIX_SHA256,
    FORMAL_LAYOUT_INDICES,
    FORMAL_SEEDS,
    _build_report,
    _execution_facts,
    _progress_payload,
    bound_source_paths,
    canonical_json,
    checkpoint_errors,
    checkpoint_content_sha256,
    extend_prefix_sha256,
    scientific_parameters,
    source_binding_sha256,
    trial_sha256,
)
from scripts.run_v8_additive_decision_dynamics_bridge import (
    assess_trial,
    load_formal_cases,
    sha256_file,
    trial_layout,
)
from scripts.verify_v8_additive_decision_dynamics_30_suffix import (
    independently_verify_completed_prefix,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]


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


def motion(
    waypoints: list[tuple[float, float]], path_length: float, *, drift: float = 0.01
) -> dict[str, object]:
    target_x, target_y = waypoints[-1]
    return {
        "reached": True,
        "reason": "reached",
        "start_pose": {"x": target_x - 1.0, "y": target_y, "yaw": 0.0},
        "final_pose": {"x": target_x - 0.1, "y": target_y, "yaw": 0.0},
        "final_goal_error_m": 0.1,
        "waypoints": [list(point) for point in waypoints],
        "path_length_m": path_length,
        "elapsed_steps": 500,
        "max_tilt_deg": 5.0,
        "stationary_partner_drift_m": drift,
        "obstacle_contact_rows": 0,
        "stationary_obstacle_contact_rows": 0,
        "partner_contact_rows": 0,
        "max_abs_wheel_target_rad_s": 2.0,
        "trajectory_samples": [],
    }


def fake_trial(case: object, layout_index: int) -> dict[str, object]:
    layout = trial_layout(case, layout_index)
    row: dict[str, object] = {
        "seed": case.seed,  # type: ignore[attr-defined]
        "original_v1_layout_index": layout_index,
        "decision": {
            "selected_corridor": case.selected_corridor,  # type: ignore[attr-defined]
            "full_chain_direct": case.full_chain_direct,  # type: ignore[attr-defined]
            "corridor_a_blocked": case.corridor_a_blocked,  # type: ignore[attr-defined]
            "corridor_b_blocked": case.corridor_b_blocked,  # type: ignore[attr-defined]
            "selected_corridor_clear": case.selected_corridor_clear,  # type: ignore[attr-defined]
            "both_corridors_blocked": case.both_corridors_blocked,  # type: ignore[attr-defined]
            "archived_episode_sha256": case.archived_episode_sha256,  # type: ignore[attr-defined]
            "input_class": case.input_class,  # type: ignore[attr-defined]
        },
        "blocked_corridors": layout["blocked_corridors"],
        "layout_binding": {
            "active_carrier_start": layout["active_carrier_start"],
            "active_scout_start": layout["active_scout_start"],
            "passive_carrier_start": layout["passive_carrier_start"],
            "active_scout_waypoints": layout["active_scout_waypoints"],
            "active_carrier_waypoints": layout["active_carrier_waypoints"],
            "passive_carrier_waypoints": layout["passive_carrier_waypoints"],
            "active_blocker_positions": layout["active_blocker_positions"],
            "passive_blocker_positions": layout["passive_blocker_positions"],
        },
        "script_entity_pose_writes_after_build": 0,
        "active_scout": motion(layout["active_scout_waypoints"], 1.0),
        "active_carrier": motion(layout["active_carrier_waypoints"], 4.8),
        "passive_carrier": motion(layout["passive_carrier_waypoints"], 6.2, drift=0.0),
    }
    row["assessment"] = assess_trial(row)
    return row


class DecisionDynamics30SuffixVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = load_formal_cases(DEFAULT_INPUT_REPORT)[20:30]
        self.assertEqual([case.seed for case in self.cases], list(FORMAL_SEEDS))
        self.assertTrue(all(case.full_chain_direct for case in self.cases))

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
            "prior_completed_evidence": {
                "path": (
                    "release/v8-derived/"
                    "decision_dynamics_single_scene_60_102500_102519/REPORT.json"
                ),
                "sha256": (
                    "3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450"
                ),
                "expected_sha256": (
                    "3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450"
                ),
                "role": "combined_claim_input_only",
                "source_binding_launch_prerequisite": True,
                "suffix_scientific_acceptance_input": False,
                "controller_input": False,
                "prefix_outcomes_parsed_by_suffix_runner": False,
                "prefix_entities_in_suffix_scene": False,
            },
            "integrity_rule": "fixed suffix checkpoints are never a full result",
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
        identity: dict[str, object] = {
            "attempt_id": attempt_id,
            "process_identity": "test-host:pid:4242",
            "process_id": 4242,
            "genesis_initialization_id": (f"{attempt_id}:genesis-initialization-0"),
            "single_scene_id": f"{attempt_id}:genesis-scene-0",
            "scene_build_id": f"{attempt_id}:scene-build-0",
        }
        binding = self._binding(args, identity)
        (output / "SOURCE_BINDING.json").write_bytes(canonical_json(binding))
        binding_sha = source_binding_sha256(binding)
        execution = _execution_facts(
            run_class="formal", trial_count=10, attempt_identity=identity
        )

        trials: list[dict[str, object]] = []
        checkpoint_paths: list[Path] = []
        prefix_sha = EMPTY_PREFIX_SHA256
        for local_index, (case, layout_index) in enumerate(
            zip(self.cases, FORMAL_LAYOUT_INDICES, strict=True)
        ):
            trial = fake_trial(case, layout_index)
            checkpoint: dict[str, object] = {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "generated_at_utc": "2026-08-05T00:00:00+00:00",
                "run_class": "formal",
                **identity,
                "trial_index": local_index,
                "seed_index": local_index,
                "seed": case.seed,
                "original_v1_layout_index": layout_index,
                "source_binding_sha256": binding_sha,
                "trial_sha256": trial_sha256(trial),
                "previous_prefix_sha256": prefix_sha,
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
            prefix_sha = extend_prefix_sha256(
                prefix_sha, str(checkpoint["checkpoint_content_sha256"])
            )

        progress = _progress_payload(
            run_class="formal",
            cases=self.cases,
            binding_sha256=binding_sha,
            attempt_identity=identity,
            checkpoint_paths=checkpoint_paths,
            prefix_sha256=prefix_sha,
        )
        (output / "PROGRESS.json").write_bytes(canonical_json(progress))
        environment = {
            "python": "3.12",
            "genesis": "1.1.2",
            "torch": "2.9.1+rocm",
            "torch_hip": "7.2",
            "backend_requested": "amdgpu",
            "gpu": "AMD Radeon",
            "single_process_id": identity["process_id"],
            "process_identity": identity["process_identity"],
            "genesis_initialization_id": identity["genesis_initialization_id"],
            "single_scene_id": identity["single_scene_id"],
            "scene_build_id": identity["scene_build_id"],
        }
        report = _build_report(
            args=args,
            binding=binding,
            cases=self.cases,
            trials=trials,
            checkpoint_paths=checkpoint_paths,
            output_dir=output,
            attempt_identity=identity,
            environment=environment,
        )
        report_path = output / "REPORT.json"
        report_path.write_bytes(canonical_json(report))
        self._write_checksums(output)
        return report_path, report

    def test_complete_suffix_runner_round_trip_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            self.assertEqual(validate_report(report, report_path=report_path), [])

    def test_partial_checkpoint_and_nine_trial_report_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            checkpoint_path = report_path.parent / "TRIALS" / "102520.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint_errors = validate_report(checkpoint, report_path=checkpoint_path)
            self.assertTrue(any("sealed REPORT.json" in e for e in checkpoint_errors))
            report["trials"] = report["trials"][:-1]  # type: ignore[index]
            report["checkpoint_index"] = report["checkpoint_index"][:-1]  # type: ignore[index]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("requires 10 trials" in e for e in errors))
            self.assertTrue(
                any("partial suffix checkpoint prefix" in e for e in errors)
            )

    def test_duplicate_reorder_and_smoke_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            trials = report["trials"]  # type: ignore[assignment]
            trials[1] = copy.deepcopy(trials[0])
            report["run_class"] = "engineering_smoke"
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("trial seed order" in e for e in errors))
            self.assertTrue(any("duplicate seeds" in e for e in errors))
            self.assertTrue(any("run_class" in e for e in errors))

    def test_original_layout_waypoint_blocker_and_goal_error_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            first = report["trials"][0]  # type: ignore[index]
            first["original_v1_layout_index"] = 0
            first["active_carrier"]["waypoints"][0][0] += 1.0
            first["layout_binding"]["active_blocker_positions"] = []
            target = first["active_scout"]["waypoints"][-1]
            first["active_scout"]["final_pose"]["x"] = target[0]
            first["active_scout"]["final_pose"]["y"] = target[1]
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("original_v1_layout_index" in e for e in errors))
            self.assertTrue(any("active_carrier.waypoints" in e for e in errors))
            self.assertTrue(any("layout_binding" in e for e in errors))
            self.assertTrue(any("inconsistent with final pose" in e for e in errors))

    def test_cross_attempt_and_broken_checkpoint_prefix_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            checkpoint_path = report_path.parent / "TRIALS" / "102521.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["attempt_id"] = "b" * 64
            checkpoint["previous_prefix_sha256"] = "0" * 64
            checkpoint["checkpoint_content_sha256"] = checkpoint_content_sha256(
                checkpoint
            )
            checkpoint_path.write_bytes(canonical_json(checkpoint))
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("checkpoint 102521.attempt_id" in e for e in errors))
            self.assertTrue(
                any("checkpoint 102521 previous prefix" in e for e in errors)
            )

    def test_contacts_reduction_and_pose_write_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            for trial in report["trials"]:  # type: ignore[union-attr]
                trial["active_carrier"]["path_length_m"] = 5.9
            first = report["trials"][0]  # type: ignore[index]
            first["active_carrier"]["obstacle_contact_rows"] = 1
            first["script_entity_pose_writes_after_build"] = 1
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("obstacle_contact_rows" in e for e in errors))
            self.assertTrue(any("direct-pair saving" in e for e in errors))
            self.assertTrue(any("pose_writes_after_build" in e for e in errors))

    def test_prefix_binding_and_honest_two_shard_boundary_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["combined_claim_boundary"]["all_90_co_resident"] = True  # type: ignore[index]
            report["combined_claim_boundary"][  # type: ignore[index]
                "maximum_co_resident_non_fixed_robot_entities"
            ] = 90
            report["boundary"]["single_scene_90_body_execution"] = True  # type: ignore[index]
            report["boundary"]["prefix_checkpoints_in_this_scene"] = True  # type: ignore[index]
            report["source"]["prior_completed_evidence"]["sha256"] = "0" * 64  # type: ignore[index]
            report["source"]["prior_completed_evidence"][  # type: ignore[index]
                "prefix_outcomes_parsed_by_suffix_runner"
            ] = True
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("prohibited 90-co-resident claim" in e for e in errors))
            self.assertTrue(any("cannot belong to suffix scene" in e for e in errors))
            self.assertTrue(any("combined_claim_boundary" in e for e in errors))
            self.assertTrue(any("prior completed evidence" in e for e in errors))

    def test_motion_source_and_completed_prefix_source_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            binding_path = report_path.parent / "SOURCE_BINDING.json"
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            del binding["source_files"]["motion_source"]
            del binding["source_files"]["completed_60_prefix_report"]
            del binding["source_files"]["completed_60_prefix_verifier"]
            binding["source_files"]["v1_runner"]["sha256"] = "0" * 64
            binding_path.write_bytes(canonical_json(binding))
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("motion_source" in e for e in errors))
            self.assertTrue(any("completed_60_prefix_report" in e for e in errors))
            self.assertTrue(any("completed_60_prefix_verifier" in e for e in errors))
            self.assertTrue(any("fixed V1 runner hash" in e for e in errors))

    def test_prefix_is_independently_verified_and_artifact_tamper_fails(self) -> None:
        self.assertEqual(independently_verify_completed_prefix(), [])
        source = (
            ROOT / "release/v8-derived/decision_dynamics_single_scene_60_102500_102519"
        )
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "prefix"
            shutil.copytree(source, copied)
            checkpoint = copied / "TRIALS" / "102500.json"
            checkpoint.write_bytes(checkpoint.read_bytes() + b"\n")
            errors = independently_verify_completed_prefix(copied / "REPORT.json")
            self.assertTrue(
                any("independent verification" in error for error in errors)
            )

            report_path, report = self.build_fixture(Path(directory) / "suffix")
            with patch(
                "scripts.verify_v8_additive_decision_dynamics_30_suffix."
                "independently_verify_completed_prefix",
                return_value=["completed prefix independent verification failed"],
            ):
                suffix_errors = validate_report(report, report_path=report_path)
            self.assertTrue(
                any(
                    "independent verification failed" in error
                    for error in suffix_errors
                )
            )

    def test_checkpoint_hash_checksum_scope_and_teardown_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = self.build_fixture(Path(directory) / "output")
            report["checkpoint_index"][0]["sha256"] = "0" * 64  # type: ignore[index]
            del report["execution"]["teardown_guard_enabled"]  # type: ignore[index]
            with (report_path.parent / "SHA256SUMS").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(f"{'0' * 64}  EXTRA\n")
            errors = validate_report(report, report_path=report_path)
            self.assertTrue(any("checkpoint 102520 hash" in e for e in errors))
            self.assertTrue(any("teardown_guard_enabled" in e for e in errors))
            self.assertTrue(any("SHA256SUMS scope mismatch" in e for e in errors))

    def test_runner_checkpoint_prepublish_schema_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path, _ = self.build_fixture(Path(directory) / "output")
            checkpoint_path = report_path.parent / "TRIALS" / "102520.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            binding = json.loads(
                (report_path.parent / "SOURCE_BINDING.json").read_text(encoding="utf-8")
            )
            identity = {
                key: checkpoint[key]
                for key in (
                    "attempt_id",
                    "process_identity",
                    "process_id",
                    "genesis_initialization_id",
                    "single_scene_id",
                    "scene_build_id",
                )
            }
            kwargs = {
                "case": self.cases[0],
                "trial_index": 0,
                "run_class": "formal",
                "binding_sha256": source_binding_sha256(binding),
                "attempt_identity": identity,
                "trial_count": 10,
                "original_v1_layout_index": 20,
                "previous_prefix_sha256": EMPTY_PREFIX_SHA256,
            }
            self.assertEqual(checkpoint_errors(checkpoint, **kwargs), [])
            tampered = copy.deepcopy(checkpoint)
            tampered["schema_version"] = "wrong-schema"
            tampered["original_v1_layout_index"] = 0
            errors = checkpoint_errors(tampered, **kwargs)
            self.assertTrue(any("schema_version" in error for error in errors))
            self.assertTrue(
                any("original_v1_layout_index" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
