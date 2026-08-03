from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_v8_frozen_challenge import (
    ACTIVE_POLICY,
    EPISODE_COUNT,
    EXPECTED_CHECKPOINT_SHA256,
    PASSIVE_POLICY,
    RUNTIME_REQUIRED_STATIC_ASSET,
    RUNTIME_SOURCE_MANIFEST_SCHEMA,
    RUNTIME_SOURCE_TREE_FINGERPRINT_ALGORITHM,
    SEED_END,
    SEED_START,
    aggregate_motion_burden,
    aggregate_primary_endpoint,
    build_episode_command,
    build_report_with_bound_validator,
    build_schedule,
    bind_runtime_source_import_canary,
    compact_episode_result,
    file_sha256,
    main,
    motion_burden_from_payload,
    prepare_output_directory,
    run_runtime_source_import_canary,
    runtime_source_tree_fingerprint,
    telemetry_coverage_checks,
    validate_preregistration,
    verify_identity_manifest,
    verify_json_artifact,
    verify_runtime_source_manifest,
    write_sha256sums,
    _run_one_episode,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PREREGISTRATION = (
    ROOT
    / "release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json"
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _record(seed: int, policy: str, carrier: float, scout: float) -> dict:
    return {
        "seed": seed,
        "policy": policy,
        "attempt_integrity_valid": True,
        "result": {
            "motion_burden": {
                "valid": True,
                "carrier_path_length": carrier,
                "scout_path_length": scout,
                "total_team_path_length": carrier + scout,
            }
        },
    }


class FrozenChallengeRunnerTests(unittest.TestCase):
    def test_schedule_is_fixed_complete_and_parity_balanced(self) -> None:
        schedule = build_schedule()
        self.assertEqual(len(schedule), EPISODE_COUNT)
        self.assertEqual({row["seed"] for row in schedule}, set(range(SEED_START, SEED_END + 1)))
        self.assertEqual(
            [row["policy"] for row in schedule[:2]],
            [PASSIVE_POLICY, ACTIVE_POLICY],
        )
        self.assertEqual(
            [row["policy"] for row in schedule[2:4]],
            [ACTIVE_POLICY, PASSIVE_POLICY],
        )
        self.assertEqual(schedule[0]["episode_path"], "episodes/passive__independent-noise__102500.json")
        self.assertEqual(schedule[-1]["episode_path"], "episodes/passive__independent-noise__102529.json")
        self.assertEqual(
            sum(row["policy"] == ACTIVE_POLICY for row in schedule), 30
        )
        self.assertEqual(
            sum(row["policy"] == PASSIVE_POLICY for row in schedule), 30
        )

    def test_episode_command_contains_the_complete_frozen_contract(self) -> None:
        root = Path("/frozen")
        paths = {
            "entrypoint": root / "src/look_twice_v7.py",
            "checkpoint": root / "checkpoint.pt",
            "vision_artifact": root / "vision.json",
            "go_artifact": root / "go.json",
            "purify_binary": root / "purify",
            "output_dir": root / "out",
        }
        command = build_episode_command(
            python="/opt/venv/bin/python", paths=paths, spec=build_schedule()[0]
        )
        rendered = " ".join(command)
        for expected in (
            "--runtime genesis",
            "--motion-backend kinematic",
            "--policy purify-passive",
            "--profile independent-noise",
            "--seed 102500",
            "--device cuda:0",
            "--vision-backend torch_spatial_rgbd",
            "--use-purify-go-gate",
            "--repair-required",
            "--go-conformal-artifact /frozen/go.json",
        ):
            self.assertIn(expected, rendered)
        self.assertTrue(command[-1].endswith("episodes/passive__independent-noise__102500.json"))

    def test_json_artifact_verifies_raw_identity_and_checkpoint_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact.json"
            payload = {
                "schema_version": "test/v1",
                "artifact_sha256": "a" * 64,
                "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            }
            _write_json(path, payload)
            raw_sha = file_sha256(path)
            result = verify_json_artifact(
                path,
                expected_file_sha256=raw_sha,
                expected_artifact_sha256="a" * 64,
                expected_checkpoint_sha256=EXPECTED_CHECKPOINT_SHA256,
            )
            self.assertTrue(result["file_sha256_verified"])
            self.assertTrue(result["artifact_sha256_verified"])
            payload["artifact_sha256"] = "b" * 64
            _write_json(path, payload)
            with self.assertRaisesRegex(ValueError, "artifact identity mismatch"):
                verify_json_artifact(
                    path,
                    expected_file_sha256=file_sha256(path),
                    expected_artifact_sha256="a" * 64,
                    expected_checkpoint_sha256=EXPECTED_CHECKPOINT_SHA256,
                )

    def test_source_preflight_hashes_every_declared_file_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected: dict[str, str] = {}
            for relative, content in (("src/a.py", "a\n"), ("scripts/b.py", "b\n")):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                expected[relative] = file_sha256(path)
            fingerprint = "c" * 64
            manifest = root / "identity.json"
            _write_json(
                manifest,
                {
                    "source_tree_fingerprint_sha256": fingerprint,
                    "critical_source_files": [
                        {"path": path, "sha256": sha}
                        for path, sha in expected.items()
                    ],
                },
            )
            result = verify_identity_manifest(
                manifest,
                root,
                expected_manifest_file_sha256=file_sha256(manifest),
                expected_fingerprint=fingerprint,
                expected_files=expected,
            )
            self.assertTrue(result["all_verified"])
            self.assertEqual(result["critical_source_file_count"], 2)
            (root / "src/a.py").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "critical frozen source mismatch"):
                verify_identity_manifest(
                    manifest,
                    root,
                    expected_manifest_file_sha256=file_sha256(manifest),
                    expected_fingerprint=fingerprint,
                    expected_files=expected,
                )

    def test_runtime_dependency_manifest_closes_python_set_and_static_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "src/a.py"
            asset = root / RUNTIME_REQUIRED_STATIC_ASSET
            source.parent.mkdir(parents=True)
            asset.parent.mkdir(parents=True)
            source.write_text("VALUE = 1\n", encoding="utf-8")
            asset.write_text("<robot/>\n", encoding="utf-8")
            declared = {
                "src/a.py": file_sha256(source),
                RUNTIME_REQUIRED_STATIC_ASSET: file_sha256(asset),
            }
            tree = runtime_source_tree_fingerprint(declared)
            manifest = root / "runtime.json"
            _write_json(
                manifest,
                {
                    "schema_version": RUNTIME_SOURCE_MANIFEST_SCHEMA,
                    "root_entrypoint": "src/a.py",
                    "source_origin_git_commit": "a" * 40,
                    "python_file_count": 1,
                    "static_asset_file_count": 1,
                    "file_count": 2,
                    "tree_fingerprint_algorithm": (
                        RUNTIME_SOURCE_TREE_FINGERPRINT_ALGORITHM
                    ),
                    "tree_fingerprint_sha256": tree,
                    "files": [
                        {"path": path, "sha256": digest}
                        for path, digest in declared.items()
                    ],
                },
            )
            result = verify_runtime_source_manifest(
                manifest,
                root,
                expected_manifest_file_sha256=file_sha256(manifest),
                expected_tree_fingerprint=tree,
                expected_file_count=2,
                expected_python_file_count=1,
                expected_static_asset_file_count=1,
                expected_root_entrypoint="src/a.py",
            )
            self.assertTrue(result["exact_set_verified"])
            self.assertEqual(result["file_count_observed"], 2)
            (root / "src/extra.py").write_text("EXTRA = 1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Python file set mismatch"):
                verify_runtime_source_manifest(
                    manifest,
                    root,
                    expected_manifest_file_sha256=file_sha256(manifest),
                    expected_tree_fingerprint=tree,
                    expected_file_count=2,
                    expected_python_file_count=1,
                    expected_static_asset_file_count=1,
                    expected_root_entrypoint="src/a.py",
                )

    def test_runtime_import_canary_resolves_every_module_to_frozen_src(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = []
            for index in range(29):
                relative = f"src/challenge_canary_{index:02d}.py"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"INDEX = {index}\n", encoding="utf-8")
                rows.append({"path": relative})
            canary = run_runtime_source_import_canary(
                python=sys.executable,
                repo_root=root,
                runtime_source_closure={"files": rows},
            )
            bound = bind_runtime_source_import_canary({"files": rows}, canary)
            self.assertTrue(canary["passed"])
            self.assertEqual(canary["resolved_module_count"], 29)
            self.assertTrue(canary["all_within_runtime_source_root"])
            self.assertTrue(bound["import_canary"]["exact_paths_verified"])

    def test_episode_timeout_kills_process_group_and_preserves_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entrypoint = root / "src/look_twice_v7.py"
            entrypoint.parent.mkdir(parents=True)
            entrypoint.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            output = root / "output"
            prepare_output_directory(output)
            paths = {
                "repo_root": root,
                "entrypoint": entrypoint,
                "checkpoint": root / "checkpoint.pt",
                "vision_artifact": root / "vision.json",
                "go_artifact": root / "go.json",
                "purify_binary": root / "purify",
                "output_dir": output,
            }
            with (
                mock.patch(
                    "scripts.run_v8_frozen_challenge.EPISODE_TIMEOUT_SECONDS",
                    0.1,
                ),
                mock.patch(
                    "scripts.run_v8_frozen_challenge.EPISODE_TERMINATION_GRACE_SECONDS",
                    0.1,
                ),
            ):
                record = _run_one_episode(
                    python=sys.executable,
                    paths=paths,
                    spec=build_schedule()[0],
                    env=os.environ,
                )
            self.assertTrue(record["timed_out"])
            self.assertFalse(record["attempt_integrity_valid"])
            self.assertEqual(record["exception"]["type"], "TimeoutExpired")
            self.assertTrue(record["termination_actions"])
            self.assertTrue((output / str(record["error_path"])).is_file())

    def test_output_directory_is_creation_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new" / "challenge"
            prepare_output_directory(output)
            self.assertTrue((output / "episodes").is_dir())
            with self.assertRaisesRegex(ValueError, "no resume/overwrite/resample"):
                prepare_output_directory(output)

    def test_telemetry_coverage_requires_both_boundaries_and_no_large_gap(self) -> None:
        samples = [
            {"monotonic_ns": 900, "command_exit_code": 0},
            {"monotonic_ns": 1_500_000_900, "command_exit_code": 0},
            {"monotonic_ns": 2_000_000_900, "command_exit_code": 0},
        ]
        checks = telemetry_coverage_checks(
            sampler_started_monotonic_ns=0,
            sampler_ended_monotonic_ns=2_100_000_000,
            challenge_started_monotonic_ns=1_000,
            challenge_ended_monotonic_ns=2_000_000_000,
            samples=samples,
            sampler_errors=[],
        )
        self.assertTrue(checks["all_valid"])
        samples[-1]["monotonic_ns"] = 1_999_999_999
        checks = telemetry_coverage_checks(
            sampler_started_monotonic_ns=0,
            sampler_ended_monotonic_ns=2_100_000_000,
            challenge_started_monotonic_ns=1_000,
            challenge_ended_monotonic_ns=2_000_000_000,
            samples=samples,
            sampler_errors=[],
        )
        self.assertFalse(checks["sample_after_or_at_challenge_end"])
        self.assertFalse(checks["all_valid"])

    def test_motion_burden_sums_all_segments_by_agent_without_energy_claim(self) -> None:
        payload = {
            "motion_segments": [
                {"agent_id": "carrier", "path_length": 1.25},
                {"agent_id": "scout", "path_length": 2.0},
                {"agent_id": "carrier", "path_length": 0.75},
            ]
        }
        motion = motion_burden_from_payload(payload)
        self.assertTrue(motion["valid"])
        self.assertEqual(motion["carrier_path_length"], 2.0)
        self.assertEqual(motion["scout_path_length"], 2.0)
        self.assertEqual(motion["total_team_path_length"], 4.0)

    def test_primary_full_chain_direct_requires_mission_route_and_joint_admit(self) -> None:
        payload = {
            "metrics": {
                "mission_success": True,
                "carrier_reached_goal": True,
                "payload_delivered": True,
                "within_deadline": True,
                "route_mode": "direct",
                "used_detour": False,
                "selected_corridor": "corridor_a",
            },
            "gate_receipts": [
                {
                    "action": "cross_corridor",
                    "corridor_id": "corridor_a",
                    "python_admitted": True,
                    "purify_go_admitted": False,
                    "effective_admit": False,
                }
            ],
            "motion_segments": [],
        }
        spec = {"seed": 102500, "policy": ACTIVE_POLICY}
        route_only = compact_episode_result(payload, spec)
        self.assertTrue(route_only["direct_route"])
        self.assertFalse(route_only["full_chain_direct"])
        payload["gate_receipts"].append(
            {
                "action": "cross_corridor",
                "corridor_id": "corridor_b",
                "python_admitted": True,
                "purify_go_admitted": True,
                "effective_admit": True,
            }
        )
        wrong_corridor = compact_episode_result(payload, spec)
        self.assertFalse(wrong_corridor["full_chain_direct"])
        payload["gate_receipts"].append(
            {
                "action": "inspect_corridor",
                "corridor_id": "corridor_a",
                "python_admitted": True,
                "purify_go_admitted": True,
                "effective_admit": True,
            }
        )
        wrong_action = compact_episode_result(payload, spec)
        self.assertFalse(wrong_action["full_chain_direct"])
        payload["gate_receipts"].append(
            {
                "action": "cross_corridor",
                "corridor_id": "corridor_a",
                "python_admitted": True,
                "purify_go_admitted": True,
                "effective_admit": True,
            }
        )
        full_chain = compact_episode_result(payload, spec)
        self.assertTrue(full_chain["full_chain_direct"])
        self.assertEqual(full_chain["behavior_linked_full_admit_receipt_count"], 1)

    def test_primary_paired_table_never_counts_route_only_direct(self) -> None:
        records = [
            {
                "seed": 102500,
                "policy": ACTIVE_POLICY,
                "attempt_integrity_valid": True,
                "result": {
                    "direct_route": True,
                    "full_chain_direct": False,
                },
            },
            {
                "seed": 102500,
                "policy": PASSIVE_POLICY,
                "attempt_integrity_valid": True,
                "result": {
                    "direct_route": False,
                    "full_chain_direct": False,
                },
            },
        ]
        primary = aggregate_primary_endpoint(records)
        self.assertEqual(primary["name"], "full_chain_direct_rate_difference")
        self.assertEqual(
            primary["by_policy"][ACTIVE_POLICY]["full_chain_direct_count"], 0
        )
        self.assertEqual(
            primary["mcnemar_discordance"],
            {"active_only": 0, "passive_only": 0},
        )
        self.assertFalse(primary["paired_rows"][0]["active_full_chain_direct"])

    def test_motion_aggregation_reports_paired_carrier_and_team_deltas(self) -> None:
        records = [
            _record(102500, ACTIVE_POLICY, 8.0, 3.0),
            _record(102500, PASSIVE_POLICY, 10.0, 0.0),
            _record(102501, ACTIVE_POLICY, 12.0, 5.0),
            _record(102501, PASSIVE_POLICY, 14.0, 0.0),
        ]
        result = aggregate_motion_burden(records)
        self.assertEqual(
            result["by_policy"][ACTIVE_POLICY]["loaded_carrier_path_length"]["mean"],
            10.0,
        )
        self.assertEqual(
            result["paired_active_minus_passive_loaded_carrier_path_length"]["mean"],
            -2.0,
        )
        self.assertEqual(
            result["paired_active_minus_passive_total_team_path_length"]["mean"],
            2.0,
        )
        self.assertIn("not energy", result["claim_guardrail"])

    def test_sha256sums_recursively_binds_every_raw_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "challenge"
            prepare_output_directory(output)
            for relative in (
                "RUN_MANIFEST.json",
                "ROCM_TELEMETRY.json",
                "CHALLENGE_REPORT.json",
                build_schedule()[0]["episode_path"],
            ):
                path = output / str(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            raw_log = output / "logs/kept-and-checksummed.txt"
            raw_log.write_text(
                "raw log\n", encoding="utf-8"
            )
            sums = write_sha256sums(output).read_text(encoding="utf-8")
            self.assertIn("RUN_MANIFEST.json", sums)
            self.assertIn(str(build_schedule()[0]["episode_path"]), sums)
            self.assertIn(
                f"{file_sha256(raw_log)}  logs/kept-and-checksummed.txt", sums
            )
            self.assertNotIn("SHA256SUMS", sums)

    def test_dry_run_accepts_unbound_public_placeholders_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "must-not-exist"
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(
                    [
                        "--output-dir",
                        str(output),
                        "--preregistration",
                        str(PRODUCTION_PREREGISTRATION),
                        "--dry-run",
                    ]
                )
            result = json.loads(stream.getvalue())
            self.assertEqual(code, 0)
            self.assertFalse(output.exists())
            self.assertFalse(result["touched_rocm"])
            self.assertEqual(result["fixed_episode_count"], 60)

    def test_bound_validator_derives_the_exact_public_report(self) -> None:
        from tests.test_verify_v8_frozen_challenge import _build_fixture

        with tempfile.TemporaryDirectory() as temporary:
            _repo, results, prereg_path = _build_fixture(Path(temporary))
            manifest = json.loads(
                (results / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            telemetry = json.loads(
                (results / "ROCM_TELEMETRY.json").read_text(encoding="utf-8")
            )
            expected = json.loads(
                (results / "CHALLENGE_REPORT.json").read_text(encoding="utf-8")
            )
            observed = build_report_with_bound_validator(
                paths={
                    "validator": ROOT / "scripts/verify_v8_frozen_challenge.py",
                    "preregistration": prereg_path,
                    "output_dir": results,
                },
                preregistration={
                    "file_sha256": file_sha256(prereg_path),
                    "validator_sha256_declared": file_sha256(
                        ROOT / "scripts/verify_v8_frozen_challenge.py"
                    ),
                },
                manifest=manifest,
                telemetry=telemetry,
            )
        self.assertEqual(observed, expected)

    def test_real_run_requires_runner_and_public_commit_bindings(self) -> None:
        prereg = json.loads(PRODUCTION_PREREGISTRATION.read_text(encoding="utf-8"))
        prereg["identities"]["runner_sha256"] = "0" * 64
        prereg["public_binding"]["runner_protocol_commit"] = "1" * 40
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prereg.json"
            _write_json(path, prereg)
            with self.assertRaisesRegex(ValueError, "not bound to this runner"):
                validate_preregistration(
                    path,
                    ROOT / "scripts/run_v8_frozen_challenge.py",
                    require_runner_binding=True,
                    validator_path=ROOT / "scripts/verify_v8_frozen_challenge.py",
                )


if __name__ == "__main__":
    unittest.main()
