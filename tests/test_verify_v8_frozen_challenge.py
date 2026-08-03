from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_v8_frozen_challenge import (  # noqa: E402
    ACTIVE,
    PASSIVE,
    build_full_wall_rocm_telemetry,
    exact_mcnemar_two_sided,
    expected_execution_order,
    expected_report,
    expected_runtime_source_closure_record,
    file_sha256,
    load_episode_records,
    verify_challenge,
    wilson_interval,
)


PRODUCTION_PREREG = (
    ROOT
    / "release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json"
)
PRODUCTION_RUNTIME_SOURCE_MANIFEST = (
    ROOT
    / "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _episode(prereg: dict, seed: int, policy: str) -> dict:
    identities = prereg["identities"]
    environment = dict(prereg["episode_contract"]["required_environment"])
    direct = policy == ACTIVE and seed % 5 != 0  # 24/30 active, 0/30 passive
    environment.update(
        {
            "purify_binary_sha256": identities["purify_binary_sha256"],
            "purify_invoked": True,
            "purify_invoked_count": 1,
            "rgbd_observation_count": 1,
            "world_alignment": {
                "world_alignment_passed": True,
                "admit_then_contact": False,
            },
        }
    )
    carrier_length = float(seed - 102490) if policy == ACTIVE else float(seed - 102492)
    scout_length = 3.0 if policy == ACTIVE else 0.0
    admitted = direct
    return {
        "schema_version": "look-twice.episode/v7",
        "scenario": {
            "scenario_id": f"v6:independent-noise:{seed}",
            "profile": "independent-noise",
            "seed": seed,
            "oracle_context": {"seed": seed, "profile": "independent-noise"},
        },
        "configuration": {"policy": policy},
        "metrics": {
            "policy": policy,
            "route_mode": "direct" if direct else "detour",
            "used_detour": not direct,
            "selected_corridor": "corridor_a" if direct else None,
            "mission_success": True,
            "carrier_reached_goal": True,
            "payload_delivered": True,
            "within_deadline": True,
            "unsafe_crossing": False,
            "collision_count": 0,
            "admit_then_contact": False,
            "clear_admitted_collision": False,
            "fallback_used": False,
            "vision_fallback_used": False,
            "vision_checkpoint_loaded": True,
            "checkpoint_loaded": True,
            "initial_gate_denied": True,
            "repair_attempted": policy == ACTIVE,
            "purify_invoked": True,
            "purify_invoked_count": 1,
            "purify_go_receipt_count": 1,
            "purify_go_receipts_ok": True,
            "genesis_live_rgbd": True,
            "vision_proposal_count": 1,
            "world_alignment_passed": True,
            "checkpoint_sha256": identities["checkpoint_sha256"],
            "vision_checkpoint_sha256": identities["checkpoint_sha256"],
            "conformal_artifact_sha256": identities[
                "vision_conformal_artifact_sha256"
            ],
            "vision_conformal_artifact_sha256": identities[
                "vision_conformal_artifact_sha256"
            ],
            "purify_binary_sha256": identities["purify_binary_sha256"],
        },
        "outcome": {"mission_success": True, "safe_fallback": False},
        "environment": environment,
        "rgbd_observation_audits": [{}],
        "vision_audits": [
            {
                "checkpoint_sha256": identities["checkpoint_sha256"],
                "conformal_artifact_sha256": identities[
                    "vision_conformal_artifact_sha256"
                ],
                "fallback_used": False,
                "checkpoint_loaded": True,
            }
        ],
        "gate_receipts": [
            {
                "python_admitted": admitted,
                "purify_go_admitted": admitted,
                "effective_admit": admitted,
                "action": "cross_corridor",
                "corridor_id": "corridor_a",
            }
        ],
        "purify_go_receipts": [
            {
                "_go_calibration_artifact_id": "v8-spatial-conformal:"
                + identities["go_conformal_artifact_sha256"][:16],
                "_purify_binary_sha256": identities["purify_binary_sha256"],
                "_purify_invoked": True,
            }
        ],
        "motion_segments": [
            {
                "agent_id": "carrier",
                "path_length": carrier_length,
                "collision_count": 0,
            },
            {"agent_id": "scout", "path_length": scout_length, "collision_count": 0},
        ],
        "world_alignment": {
            "world_alignment_passed": True,
            "admit_then_contact": False,
        },
    }


def _rewrite_sums(results: Path) -> None:
    relatives = [
        path.relative_to(results).as_posix()
        for path in results.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    lines = [f"{file_sha256(results / relative)}  {relative}" for relative in sorted(relatives)]
    (results / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_fixture(root: Path) -> tuple[Path, Path, Path]:
    repo = root / "repo"
    results = root / "results"
    runner = repo / "scripts/run_v8_frozen_challenge.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("#!/usr/bin/env python3\n# fixed test runner\n", encoding="utf-8")
    validator = repo / "scripts/verify_v8_frozen_challenge.py"
    validator.write_text("#!/usr/bin/env python3\n# fixed test validator\n", encoding="utf-8")

    prereg = json.loads(PRODUCTION_PREREG.read_text(encoding="utf-8"))
    runtime_manifest_target = repo / prereg["identities"][
        "runtime_source_closure"
    ]["manifest_path"]
    runtime_manifest_target.parent.mkdir(parents=True, exist_ok=True)
    runtime_manifest_target.write_bytes(PRODUCTION_RUNTIME_SOURCE_MANIFEST.read_bytes())
    runtime_manifest_payload = json.loads(
        PRODUCTION_RUNTIME_SOURCE_MANIFEST.read_text(encoding="utf-8")
    )
    for row in runtime_manifest_payload["files"]:
        source = ROOT / row["path"]
        target = repo / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    prereg["identities"]["runner_sha256"] = file_sha256(runner)
    prereg["identities"]["validator_sha256"] = file_sha256(validator)
    prereg["public_binding"]["runner_protocol_commit"] = "a" * 40
    prereg_path = root / "V8_FROZEN_CHALLENGE_PREREGISTRATION.json"
    _write_json(prereg_path, prereg)
    prereg_sha = file_sha256(prereg_path)

    for seed in range(102500, 102530):
        for policy, prefix in ((ACTIVE, "active"), (PASSIVE, "passive")):
            _write_json(
                results
                / f"episodes/{prefix}__independent-noise__{seed}.json",
                _episode(prereg, seed, policy),
            )

    source_rows = [
        {
            "path": row["path"],
            "expected_sha256": row["sha256"],
            "observed_sha256": row["sha256"],
            "matched": True,
        }
        for row in prereg["identities"]["critical_source_files"]
    ]
    attempts = []
    for index, row in enumerate(expected_execution_order(prereg)):
        started = 1_000_000_000 + index * 40_000_000
        ended = started + 30_000_000
        attempts.append(
            {
                **row,
                "started_monotonic_ns": started,
                "ended_monotonic_ns": ended,
                "wall_seconds": 0.03,
                "exit_code": 0,
                "timeout_seconds": 300.0,
                "timed_out": False,
                "start_new_session": True,
                "termination_grace_seconds": 10.0,
                "termination_actions": [],
            }
        )
    manifest = {
        "schema_version": "look-twice.v8-frozen-challenge-run-manifest/v1",
        "preregistration_sha256": prereg_sha,
        "runner_sha256": prereg["identities"]["runner_sha256"],
        "validator_sha256": prereg["identities"]["validator_sha256"],
        "runner_protocol_commit": prereg["public_binding"][
            "runner_protocol_commit"
        ],
        "preregistration_public_commit": "b" * 40,
        "frozen_identities": {
            key: prereg["identities"][key]
            for key in (
                "checkpoint_sha256",
                "vision_conformal_artifact_sha256",
                "go_conformal_artifact_sha256",
                "purify_binary_sha256",
                "source_tree_fingerprint_sha256",
            )
        },
        "execution": {
            "order": expected_execution_order(prereg),
            "attempted_episode_count": 60,
            "completed_episode_count": 60,
            "retry_count": 0,
            "early_stopped": False,
            "all_outcomes_preserved": True,
            "subprocess_exit_code": 0,
            "attempts": attempts,
        },
        "source_preflight": {
            "source_tree_fingerprint_sha256": prereg["identities"][
                "source_tree_fingerprint_sha256"
            ],
            "critical_source_file_count": 13,
            "mismatch_count": 0,
            "files": source_rows,
        },
        "runtime": {
            "environment_overrides": {
                "MIOPEN_FIND_MODE": "FAST",
                "PATH": "/opt/venv/bin:/usr/bin",
                "PATH_prepend": "/opt/venv/bin",
            }
        },
        "runtime_source_closure": expected_runtime_source_closure_record(prereg),
        "fixed_episode_contract": {
            "episode_timeout_seconds": 300.0,
            "timeout_process_group_termination": {
                "start_new_session": True,
                "first_signal": "SIGTERM",
                "grace_seconds": 10.0,
                "final_signal": "SIGKILL",
                "retry_after_timeout": False,
            },
        },
    }
    _write_json(results / "RUN_MANIFEST.json", manifest)
    _write_json(
        results / "raw/PRESTART_BINDING.json",
        {
            "schema_version": "look-twice.v8-frozen-challenge-prestart-binding/v1",
            "bound_at_utc_before_first_episode": "2026-08-03T00:00:00Z",
            "preregistration_sha256": prereg_sha,
            "runner_sha256": prereg["identities"]["runner_sha256"],
            "validator_sha256": prereg["identities"]["validator_sha256"],
            "runner_protocol_commit": prereg["public_binding"][
                "runner_protocol_commit"
            ],
            "preregistration_public_commit": "b" * 40,
            "fixed_subprocess_environment": {
                "MIOPEN_FIND_MODE": "FAST",
                "PATH": "/opt/venv/bin:/usr/bin",
                "PATH_prepend": "/opt/venv/bin",
            },
            "runtime_source_closure": expected_runtime_source_closure_record(prereg),
            "planned_schedule": expected_execution_order(prereg),
            "no_episode_had_started": True,
        },
    )

    telemetry = {
        "schema_version": "look-twice.v8-frozen-challenge-rocm-telemetry/v1",
        "scope": "entire_challenge_subprocess_wall",
        "sampler_started_monotonic_ns": 0,
        "challenge_subprocess_started_monotonic_ns": 1_000_000_000,
        "challenge_subprocess_ended_monotonic_ns": 4_000_000_000,
        "sampler_ended_monotonic_ns": 5_000_000_000,
        "sample_interval_seconds": 2.0,
        "command_exit_code": 0,
        "sampler_errors": [],
        "preflight": {
            "no_other_kfd_processes": True,
            "gpu_use_percent": 0.0,
            "vram_allocated_percent": 0.0,
        },
        "samples": [
            {
                "monotonic_ns": timestamp,
                "device": "card0",
                "gpu_use_percent": 90.0,
                "vram_allocated_percent": 10.0,
                "graphics_package_power_w": 120.0,
            }
            for timestamp in (
                500_000_000,
                1_500_000_000,
                2_500_000_000,
                3_500_000_000,
                4_500_000_000,
            )
        ],
    }
    _write_json(results / "ROCM_TELEMETRY.json", telemetry)

    load_errors: list[str] = []
    records = load_episode_records(results, prereg, load_errors)
    if load_errors:
        raise AssertionError(load_errors)
    _write_json(
        results / "CHALLENGE_REPORT.json",
        expected_report(records, prereg_sha, manifest, telemetry),
    )
    _rewrite_sums(results)
    return repo, results, prereg_path


class FrozenChallengeVerifierTests(unittest.TestCase):
    def test_valid_complete_fixture_passes_and_recomputes_primary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            verification = verify_challenge(results, prereg, repo)
        self.assertTrue(verification["passed"], verification["errors"])
        primary = verification["recomputed_report"]["analysis"]["primary_endpoint"]
        self.assertEqual(primary["name"], "full_chain_direct_rate_difference")
        self.assertEqual(primary["active"]["count"], 24)
        self.assertEqual(primary["passive"]["count"], 0)
        self.assertEqual(primary["paired_table"]["active_only_direct"], 24)
        self.assertAlmostEqual(primary["exact_mcnemar_two_sided_p"], 2 / (2**24))
        denominator = verification["recomputed_report"]["analysis"][
            "full_pipeline_denominator"
        ]
        self.assertEqual(denominator["episodes"], {"count": 60, "expected": 60})
        self.assertEqual(denominator["frozen_checkpoint_loaded"]["count"], 60)
        burden = verification["recomputed_report"]["analysis"][
            "logical_role_kinematic_operational_burden"
        ]
        self.assertEqual(
            burden["loaded_carrier"]["paired_delta_active_minus_passive"]["mean"],
            2.0,
        )
        self.assertEqual(burden["active_scout"]["median"], 3.0)
        telemetry = verification["recomputed_report"]["analysis"][
            "full_wall_rocm_telemetry"
        ]
        self.assertEqual(telemetry["sample_count"], 5)
        self.assertEqual(telemetry["measured_wall_seconds"], 3.0)
        self.assertEqual(telemetry["gpu_busy_sample_rate"]["rate"], 1.0)
        self.assertEqual(
            telemetry["episode_subprocess_wall_seconds"]["all"]["n"], 60
        )

    def test_route_only_direct_without_full_gate_admit_is_not_primary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg_path = _build_fixture(Path(temporary))
            episode_path = (
                results / "episodes/active__independent-noise__102501.json"
            )
            episode = json.loads(episode_path.read_text(encoding="utf-8"))
            receipt = episode["gate_receipts"][0]
            receipt["python_admitted"] = False
            receipt["purify_go_admitted"] = False
            receipt["effective_admit"] = False
            _write_json(episode_path, episode)

            prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
            manifest = json.loads(
                (results / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            telemetry = json.loads(
                (results / "ROCM_TELEMETRY.json").read_text(encoding="utf-8")
            )
            load_errors: list[str] = []
            records = load_episode_records(results, prereg, load_errors)
            self.assertEqual(load_errors, [])
            _write_json(
                results / "CHALLENGE_REPORT.json",
                expected_report(
                    records, file_sha256(prereg_path), manifest, telemetry
                ),
            )
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg_path, repo)

        self.assertTrue(verification["passed"], verification["errors"])
        analysis = verification["recomputed_report"]["analysis"]
        self.assertEqual(analysis["primary_endpoint"]["active"]["count"], 23)
        self.assertEqual(
            analysis["secondary_endpoints"]["route_only_direct"]["active"][
                "count"
            ],
            24,
        )
        row = next(row for row in analysis["per_seed"] if row["seed"] == 102501)
        self.assertTrue(row["active"]["route_only_direct"])
        self.assertFalse(row["active"]["full_chain_direct"])

    def test_admit_for_different_corridor_is_not_full_chain_direct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg_path = _build_fixture(Path(temporary))
            episode_path = (
                results / "episodes/active__independent-noise__102501.json"
            )
            episode = json.loads(episode_path.read_text(encoding="utf-8"))
            self.assertEqual(episode["metrics"]["selected_corridor"], "corridor_a")
            episode["gate_receipts"][0]["corridor_id"] = "corridor_b"
            _write_json(episode_path, episode)

            prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
            manifest = json.loads(
                (results / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            telemetry = json.loads(
                (results / "ROCM_TELEMETRY.json").read_text(encoding="utf-8")
            )
            load_errors: list[str] = []
            records = load_episode_records(results, prereg, load_errors)
            self.assertEqual(load_errors, [])
            _write_json(
                results / "CHALLENGE_REPORT.json",
                expected_report(
                    records, file_sha256(prereg_path), manifest, telemetry
                ),
            )
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg_path, repo)

        self.assertTrue(verification["passed"], verification["errors"])
        analysis = verification["recomputed_report"]["analysis"]
        self.assertEqual(analysis["primary_endpoint"]["active"]["count"], 23)
        self.assertEqual(
            analysis["secondary_endpoints"]["route_only_direct"]["active"][
                "count"
            ],
            24,
        )
        row = next(row for row in analysis["per_seed"] if row["seed"] == 102501)
        self.assertEqual(row["active"]["full_admit_receipt_count"], 1)
        self.assertEqual(
            row["active"]["selected_corridor_full_admit_receipt_count"], 0
        )
        self.assertFalse(row["active"]["full_chain_direct"])

    def test_tampered_episode_identity_and_checksum_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "episodes/active__independent-noise__102500.json"
            episode = json.loads(path.read_text(encoding="utf-8"))
            episode["metrics"]["checkpoint_sha256"] = "0" * 64
            _write_json(path, episode)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "episode_102500_active_metrics_checkpoint_mismatch",
            verification["errors"],
        )
        self.assertIn(
            "checksummed_file_digest_mismatch:episodes/active__independent-noise__102500.json",
            verification["errors"],
        )

    def test_missing_raw_episode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            (results / "episodes/passive__independent-noise__102529.json").unlink()
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "raw_episode_missing:episodes/passive__independent-noise__102529.json",
            verification["errors"],
        )

    def test_telemetry_must_span_entire_subprocess_wall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "ROCM_TELEMETRY.json"
            telemetry = json.loads(path.read_text(encoding="utf-8"))
            telemetry["samples"][0]["monotonic_ns"] = 1_100_000_000
            _write_json(path, telemetry)
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn("telemetry_does_not_cover_subprocess_start", verification["errors"])

    def test_telemetry_summary_keeps_zero_percent_idle_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _repo, results, _prereg = _build_fixture(Path(temporary))
            manifest = json.loads(
                (results / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            telemetry = json.loads(
                (results / "ROCM_TELEMETRY.json").read_text(encoding="utf-8")
            )
            telemetry["samples"][0]["gpu_use_percent"] = 0.0
            summary = build_full_wall_rocm_telemetry(manifest, telemetry)
        self.assertEqual(summary["sample_count"], 5)
        self.assertEqual(summary["gpu_use_percent"]["minimum"], 0.0)
        self.assertEqual(summary["gpu_use_percent"]["mean"], 72.0)
        self.assertEqual(summary["gpu_busy_sample_rate"]["busy_samples"], 4)
        self.assertEqual(summary["gpu_busy_sample_rate"]["rate"], 0.8)

    def test_each_attempt_requires_positive_wall_and_zero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "RUN_MANIFEST.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["execution"]["attempts"][7]["exit_code"] = 1
            manifest["execution"]["attempts"][8]["wall_seconds"] = 0.0
            _write_json(path, manifest)
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn("run_manifest_attempt_7_exit_code_not_zero", verification["errors"])
        self.assertIn("run_manifest_attempt_8_wall_seconds_invalid", verification["errors"])

    def test_report_cannot_disagree_with_raw_recomputation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "CHALLENGE_REPORT.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            report["analysis"]["primary_endpoint"]["active"]["count"] = 30
            _write_json(path, report)
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "challenge_report_does_not_match_raw_recomputation",
            verification["errors"],
        )

    def test_unsigned_extra_result_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            extra = results / "logs/extra.stdout.log"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("not listed\n", encoding="utf-8")
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "sha256sums_entry_missing:logs/extra.stdout.log",
            verification["errors"],
        )

    def test_tampered_signed_extra_result_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            extra = results / "logs/extra.stdout.log"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("original\n", encoding="utf-8")
            _rewrite_sums(results)
            extra.write_text("tampered\n", encoding="utf-8")
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "checksummed_file_digest_mismatch:logs/extra.stdout.log",
            verification["errors"],
        )

    def test_execution_order_and_source_preflight_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "RUN_MANIFEST.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["execution"]["order"][0:2] = reversed(
                manifest["execution"]["order"][0:2]
            )
            manifest["source_preflight"]["files"][0]["observed_sha256"] = "f" * 64
            _write_json(path, manifest)
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn("run_manifest_execution_order_mismatch", verification["errors"])
        self.assertTrue(
            any(
                error.startswith("source_preflight_observed_sha_mismatch:")
                for error in verification["errors"]
            )
        )

    def test_runtime_dependency_manifest_identity_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, results, prereg = _build_fixture(Path(temporary))
            path = results / "RUN_MANIFEST.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["runtime_source_closure"][
                "tree_fingerprint_sha256_observed"
            ] = "0" * 64
            _write_json(path, manifest)
            _rewrite_sums(results)
            verification = verify_challenge(results, prereg, repo)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "run_manifest_runtime_source_closure_tree_fingerprint_sha256_observed_mismatch",
            verification["errors"],
        )

    def test_statistical_helpers_cover_zero_discordance_and_boundaries(self) -> None:
        self.assertEqual(exact_mcnemar_two_sided(0, 0), 1.0)
        self.assertEqual(exact_mcnemar_two_sided(3, 0), 0.25)
        interval = wilson_interval(0, 30)
        self.assertEqual(interval["lower"], 0.0)
        self.assertGreater(interval["upper"], 0.0)
        self.assertLess(interval["upper"], 0.2)


if __name__ == "__main__":
    unittest.main()
