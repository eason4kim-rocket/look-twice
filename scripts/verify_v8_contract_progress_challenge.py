#!/usr/bin/env python3
"""Independently verify the V8 contract-progress paired challenge.

The verifier trusts neither runner summaries nor episode-level convenience
metrics for path length.  It reconstructs the fixed schedule, validates every
raw episode, recomputes paired endpoints, enforces an exact file set, and checks
the final SHA256 index.  It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import stat
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SEED_START = 102530
SEED_END = 102549
SEEDS = tuple(range(SEED_START, SEED_END + 1))
PROFILE = "independent-noise"
BASELINE_POLICY = "purify-active-vision"
CANDIDATE_POLICY = "purify-active-contract-progress"
POLICY_ARTIFACT_ID = "v8-contract-progress-nbv/1"
EPISODE_COUNT = 40
EPISODE_TIMEOUT_SECONDS = 300

EXPECTED_CHECKPOINT_SHA256 = (
    "7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783"
)
EXPECTED_VISION_FILE_SHA256 = (
    "8ccce120c2321582d4c9ad6ead90bcd55c562f9808db105f79ae7a76b46aa213"
)
EXPECTED_VISION_ARTIFACT_SHA256 = (
    "ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f"
)
EXPECTED_GO_FILE_SHA256 = (
    "128d2c1a7c814b2f82f1bb660289026ae27f876434ae0c2add4a223242f59eac"
)
EXPECTED_GO_ARTIFACT_SHA256 = (
    "d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97"
)
EXPECTED_PURIFY_SHA256 = (
    "31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00"
)
EXPECTED_IDENTITY_MANIFEST_SHA256 = (
    "a7ecc586043f26f06daec73464b11146a6bba2832aa67c53c50ce67d2d315c7d"
)
EXPECTED_SOURCE_TREE_SHA256 = (
    "983d7d373a3eedc6f6204e91d2d63b95a7e563506add24d37ee5a30c95aa71a9"
)
EXPECTED_RUNTIME_MANIFEST_SHA256 = (
    "018f064f0361e59371e6694d7909da8639960f41f2ef158687c8e65e24d45c2f"
)
EXPECTED_RUNTIME_TREE_SHA256 = (
    "abc1b6810aed6dc19a127069b9b5d5f044def24f35c9a13602f7f5096742b1be"
)
GO_CALIBRATION_ID = f"v8-spatial-conformal:{EXPECTED_GO_ARTIFACT_SHA256[:16]}"
VISION_CALIBRATION_ID = f"look-twice-v8-spatial:{EXPECTED_VISION_ARTIFACT_SHA256[:16]}"

PREREG_SCHEMA = "look-twice.v8-contract-progress-challenge-preregistration/v1"
MANIFEST_SCHEMA = "look-twice.v8-contract-progress-challenge-run-manifest/v1"
REPORT_SCHEMA = "look-twice.v8-contract-progress-challenge-report/v1"
VERIFICATION_SCHEMA = "look-twice.v8-contract-progress-challenge-verification/v1"
PRESTART_SCHEMA = "look-twice.v8-contract-progress-challenge-prestart-binding/v1"
POSTRUN_SCHEMA = "look-twice.v8-contract-progress-challenge-postrun-binding/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_PREFIX = "TO_BE_"
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 0xC0A7A9
CANDIDATE_SOURCE_TREE_ALGORITHM = (
    "sha256 of lexicographically path-sorted lines formatted as "
    "'<file_sha256>  <relative_path>\\n' over the exact git-tracked src/** file set"
)


class VerificationError(ValueError):
    """Raised for structural or integrity failures."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VerificationError(f"JSON root is not an object: {path}")
    return payload


def _safe_git_environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "LANG",
        "LANGUAGE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in allowed or key.startswith("LC_")
    }
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
        }
    )
    return environment


def verify_candidate_source_closure(
    root: Path,
    *,
    expected_file_count: int | None = None,
    expected_tree_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind the exact tracked ``src/**`` tree and reject every extra code path.

    The filesystem walk is intentionally compared with ``git ls-files``.  This
    catches untracked *and ignored* import hooks/bytecode, not merely a dirty Git
    status, and rejects symlinks or other non-regular entries anywhere below
    ``src``.
    """

    root = root.resolve()
    source_root = root / "src"
    if source_root.is_symlink() or not source_root.is_dir():
        raise VerificationError("candidate src root is not an ordinary directory")
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "src"],
        cwd=root,
        env=_safe_git_environment(),
        check=False,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(f"candidate git ls-files failed: {stderr}")
    try:
        decoded = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise VerificationError("candidate tracked src paths are not UTF-8") from exc
    tracked_rows = decoded.split("\0")
    if tracked_rows and tracked_rows[-1] == "":
        tracked_rows.pop()
    tracked: set[str] = set()
    for relative in tracked_rows:
        pure = PurePosixPath(relative)
        if (
            not relative
            or pure.is_absolute()
            or relative != pure.as_posix()
            or pure.parts[0] != "src"
            or any(part in {"", ".", ".."} for part in pure.parts)
            or any(ord(character) < 32 for character in relative)
            or relative in tracked
        ):
            raise VerificationError(
                f"unsafe or duplicate candidate tracked source path: {relative!r}"
            )
        tracked.add(relative)
    if not tracked:
        raise VerificationError("candidate Git index contains no tracked src files")

    actual: set[str] = set()
    for path in source_root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise VerificationError(
                f"candidate src contains a forbidden symlink: {path}"
            )
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise VerificationError(
                f"candidate src contains a non-regular path: {path}"
            )
        actual.add(path.relative_to(root).as_posix())
    if actual != tracked:
        raise VerificationError(
            "candidate exact tracked src closure mismatch: "
            f"missing={sorted(tracked - actual)} extra={sorted(actual - tracked)}"
        )

    observations: list[dict[str, Any]] = []
    digest_by_path: dict[str, str] = {}
    for relative in sorted(tracked):
        path = root / relative
        current = root
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.is_symlink():
                raise VerificationError(
                    f"candidate source path traverses a symlink: {current}"
                )
        if not stat.S_ISREG(path.lstat().st_mode):
            raise VerificationError(
                f"candidate tracked source is not regular: {relative}"
            )
        digest = file_sha256(path)
        digest_by_path[relative] = digest
        observations.append({"path": relative, "sha256": digest})
    material = "".join(
        f"{digest_by_path[relative]}  {relative}\n"
        for relative in sorted(digest_by_path)
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
    if expected_file_count is not None and len(observations) != expected_file_count:
        raise VerificationError(
            "candidate tracked src file count mismatch: "
            f"expected {expected_file_count}, got {len(observations)}"
        )
    if expected_tree_sha256 is not None and fingerprint != expected_tree_sha256:
        raise VerificationError(
            "candidate tracked src tree fingerprint mismatch: "
            f"expected {expected_tree_sha256}, got {fingerprint}"
        )
    return {
        "tree_fingerprint_algorithm": CANDIDATE_SOURCE_TREE_ALGORITHM,
        "tree_fingerprint_sha256": fingerprint,
        "tracked_file_count": len(observations),
        "exact_git_tracked_file_set_verified": True,
        "untracked_and_ignored_files_absent": True,
        "symlinks_and_nonregular_paths_absent": True,
        "files": observations,
    }


def exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def build_schedule() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        arms = (
            ("baseline", "candidate")
            if seed % 2 == 0
            else (
                "candidate",
                "baseline",
            )
        )
        for arm in arms:
            policy = BASELINE_POLICY if arm == "baseline" else CANDIDATE_POLICY
            stem = f"{arm}__{PROFILE}__{seed}"
            rows.append(
                {
                    "schedule_index": len(rows),
                    "seed": seed,
                    "arm": arm,
                    "policy": policy,
                    "profile": PROFILE,
                    "episode_path": f"{arm}/episodes/{stem}.json",
                    "stdout_path": f"{arm}/logs/{stem}.stdout.txt",
                    "stderr_path": f"{arm}/logs/{stem}.stderr.txt",
                    "error_path": f"{arm}/errors/{stem}.json",
                }
            )
    if len(rows) != EPISODE_COUNT:
        raise AssertionError("fixed schedule size changed")
    return rows


def schedule_sha256() -> str:
    return canonical_json_sha256(build_schedule())


def _is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PLACEHOLDER_PREFIX)


def validate_preregistration(
    payload: Mapping[str, Any],
    *,
    runner_sha256: str | None = None,
    verifier_sha256: str | None = None,
    candidate_root: Path | None = None,
    formal: bool,
) -> dict[str, Any]:
    errors: list[str] = []

    def expect(path: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")

    expect("schema_version", payload.get("schema_version"), PREREG_SCHEMA)
    expect(
        "protocol_path",
        payload.get("protocol_path"),
        "docs/V8_CONTRACT_PROGRESS_CHALLENGE_PROTOCOL.md",
    )
    expected_status = "PREREGISTERED_BEFORE_ANY_CHALLENGE_EPISODE"
    if formal:
        expect("status", payload.get("status"), expected_status)
    elif payload.get("status") not in {
        expected_status,
        "DRAFT_HASH_BINDING_REQUIRED_BEFORE_EXECUTION",
    }:
        errors.append("status is neither the draft nor formal preregistration status")
    created_utc = payload.get("created_utc")
    if formal:
        try:
            created_at = datetime.fromisoformat(str(created_utc).replace("Z", "+00:00"))
        except ValueError:
            created_at = None
        if created_at is None or created_at.tzinfo is None:
            errors.append("created_utc is not a timezone-aware public binding time")
    elif not (
        created_utc == "TO_BE_SET_AT_PUBLIC_BINDING"
        or isinstance(created_utc, str)
        and bool(created_utc)
    ):
        errors.append("created_utc is neither a draft placeholder nor a timestamp")

    design = payload.get("design")
    if not isinstance(design, Mapping):
        errors.append("design must be an object")
        design = {}
    fixed_design = {
        "seed_start": SEED_START,
        "seed_end": SEED_END,
        "seeds": list(SEEDS),
        "n_worlds": len(SEEDS),
        "n_episodes": EPISODE_COUNT,
        "profile": PROFILE,
        "baseline_policy": BASELINE_POLICY,
        "candidate_policy": CANDIDATE_POLICY,
        "candidate_policy_artifact_id": POLICY_ARTIFACT_ID,
        "seed_order": "strictly_ascending",
        "paired_by_seed": True,
        "attempts_per_seed_policy": 1,
        "retry_count_allowed": 0,
        "seed_substitution_allowed": False,
        "early_stopping_allowed": False,
        "resume_allowed": False,
        "continue_after_bad_outcome": True,
        "persist_every_attempt_locally": True,
        "retuning_allowed": False,
        "checkpoint_changes_allowed": False,
        "calibration_changes_allowed": False,
        "gate_changes_allowed": False,
        "threshold_changes_allowed": False,
        "episode_timeout_seconds": EPISODE_TIMEOUT_SECONDS,
    }
    for key, expected in fixed_design.items():
        expect(f"design.{key}", design.get(key), expected)
    expect(
        "design.within_seed_order_rule",
        design.get("within_seed_order_rule"),
        {
            "even_seed": [BASELINE_POLICY, CANDIDATE_POLICY],
            "odd_seed": [CANDIDATE_POLICY, BASELINE_POLICY],
        },
    )

    algorithm = payload.get("candidate_algorithm_contract")
    expected_algorithm = {
        "intervention_type": "compound_v8_system_intervention",
        "intervention_pipeline": [
            "one_initial_physical_rgbd_capture",
            "one_shared_frozen_seg_v3_backbone_forward",
            "two_corridor_scoped_roi_proposals",
            "geometry_vision_physical_capture_root_unification",
            "contract_debt_then_online_go_p_blocked_then_travel_nbv",
        ],
        "frozen_components": [
            "seg_v3_checkpoint",
            "vision_conformal_thresholds",
            "go_conformal_thresholds",
            "purify_gate_rules",
            "world_generator",
            "kinematic_motion_backend",
        ],
        "attribution": (
            "overall_v8_plus_compound_intervention_not_planner_only_"
            "or_shared_capture_only"
        ),
        "contract_debt_source": (
            "latest_applicable_online_purify_go_receipt_"
            "distinct_measurement_roots_clause"
        ),
        "corridor_order": [
            "lower_repair_step_debt",
            "lower_online_go_p_blocked",
            "lower_public_geometry_scout_travel_distance",
            "stable_deterministic_ties",
        ],
        "allowed_inputs": [
            "current_corridor_scoped_purify_go_receipts",
            "effective_python_go_decisions",
            "public_map_geometry",
            "current_robot_poses",
            "public_candidate_actions",
            "visit_history",
            "online_claim_derived_confirmed_blocked_set",
            "observations_taken",
            "max_observations",
            "side_observations_per_corridor",
            "max_side_observation_budget_per_corridor",
        ],
        "forbidden_inputs": [
            "scenario_seed",
            "oracle_state",
            "future_image",
            "clean_segmentation",
            "noise_realization",
            "retry_outcome",
        ],
        "go_p_blocked_semantics": (
            "online_receipt_value_not_oracle_occupancy_or_new_calibration"
        ),
        "go_measurement_root_debt_definition": (
            "max(required_roots_minus_actual_roots,0)"
        ),
        "repair_step_debt_rule": (
            "measurement_root_debt_if_positive_else_one_for_"
            "otherwise_repairable_denied_gate"
        ),
        "chosen_ranking_debt_fields_required": True,
        "malformed_missing_inapplicable_or_hard_deny_receipt": "fail_closed",
        "fail_closed_delegation": (
            "audited_frozen_v8_public_probe_or_safe_detour_only_never_direct_admission"
        ),
        "chosen_ranking_go_p_blocked_required": True,
        "chosen_ranking_go_receipt_sha256_required": True,
        "evidence_request_receipt_rehash_and_decision_binding": True,
        "go_receipt_time_binding": (
            "evaluated_step_equals_strictly_increasing_evidence_request_current_step"
        ),
        "authorized_execution_closure_required": True,
        "terminal_budget_denied_side_view": (
            "proposal_only_noop_after_exactly_three_authorized_side_views"
        ),
        "safe_fallback_semantics": (
            "final_route_control_noop_with_raw_safe_detour_proof"
        ),
    }
    if algorithm != expected_algorithm:
        errors.append("candidate_algorithm_contract differs from the frozen design")

    population = payload.get("population_boundary")
    if not isinstance(population, Mapping):
        errors.append("population_boundary must be an object")
        population = {}
    for key, expected in {
        "generator_family": "same_generator_as_v8_spatial_dataset_v1",
        "challenge_subset": [SEED_START, SEED_END],
        "same_generator": True,
        "non_locked": True,
        "not_ood": True,
        "not_physical_robot": True,
        "formal_result_eligible": False,
    }.items():
        expect(f"population_boundary.{key}", population.get(key), expected)

    runtime_contract = payload.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        errors.append("runtime_contract must be an object")
        runtime_contract = {}
    for key, expected in {
        "runtime": "genesis-amd",
        "motion_backend": "kinematic",
        "device": "cuda:0",
        "vision_backend": "torch_spatial_rgbd",
        "repair_required": True,
        "purify_go_gate": True,
        "heuristic_fallback_allowed": False,
        "audited_fail_closed_frozen_v8_probe_delegation_allowed": True,
        "baseline_and_candidate_source_roots_must_differ": True,
        "baseline_exact_python_file_set_required": True,
        "baseline_exact_src_file_set_required": True,
        "candidate_exact_git_tracked_src_closure_required": True,
        "python_user_site_allowed": False,
        "python_bytecode_writes_allowed": False,
        "anonymous_public_remote_head_required": True,
        "postrun_local_and_live_remote_revalidation_required": True,
        "formal_output_outside_both_source_roots": True,
        "frozen_go_binary_receipt_authentication_required": True,
        "python_launcher_and_resolved_target_identity_required": True,
        "attempt_fixed_argv_exact_reconstruction_required": True,
        "clean_gpu_kfd_and_idle_preflight_required": True,
        "attempt_artifacts_fsynced_before_attempt_record": True,
        "go_authentication_adverse_result_report_required": True,
        "malformed_episode_adverse_result_report_required": True,
        "runner_attempt_integrity_is_provisional_until_frozen_go_auth": True,
        "git_replace_objects_disabled": True,
        "git_status_fsmonitor_and_untracked_cache_disabled": True,
        "output_creation_only": True,
        "raw_failures_retained": True,
        "process_group_timeout_kill": True,
    }.items():
        expect(f"runtime_contract.{key}", runtime_contract.get(key), expected)

    identities = payload.get("identities")
    if not isinstance(identities, Mapping):
        errors.append("identities must be an object")
        identities = {}
    for key, expected in {
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "vision_conformal_file_sha256": EXPECTED_VISION_FILE_SHA256,
        "vision_conformal_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
        "go_conformal_file_sha256": EXPECTED_GO_FILE_SHA256,
        "go_conformal_artifact_sha256": EXPECTED_GO_ARTIFACT_SHA256,
        "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
        "identity_manifest_file_sha256": EXPECTED_IDENTITY_MANIFEST_SHA256,
        "source_tree_fingerprint_sha256": EXPECTED_SOURCE_TREE_SHA256,
        "baseline_runtime_source_manifest_file_sha256": EXPECTED_RUNTIME_MANIFEST_SHA256,
        "baseline_runtime_source_tree_fingerprint_sha256": EXPECTED_RUNTIME_TREE_SHA256,
        "candidate_tracked_src_tree_fingerprint_algorithm": (
            CANDIDATE_SOURCE_TREE_ALGORITHM
        ),
    }.items():
        expect(f"identities.{key}", identities.get(key), expected)
    for key, expected in {
        "baseline_runtime_source_manifest_path": (
            "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
        ),
        "runner_path": "scripts/run_v8_contract_progress_challenge.py",
        "verifier_path": "scripts/verify_v8_contract_progress_challenge.py",
    }.items():
        expect(f"identities.{key}", identities.get(key), expected)

    observed_runner = identities.get("runner_sha256")
    observed_verifier = identities.get("verifier_sha256")
    if formal:
        if not isinstance(observed_runner, str) or not SHA256_RE.fullmatch(
            observed_runner
        ):
            errors.append("identities.runner_sha256 is not a bound SHA256")
        if not isinstance(observed_verifier, str) or not SHA256_RE.fullmatch(
            observed_verifier
        ):
            errors.append("identities.verifier_sha256 is not a bound SHA256")
    else:
        if not (
            _is_placeholder(observed_runner)
            or SHA256_RE.fullmatch(str(observed_runner or ""))
        ):
            errors.append("identities.runner_sha256 is not a placeholder or SHA256")
        if not (
            _is_placeholder(observed_verifier)
            or SHA256_RE.fullmatch(str(observed_verifier or ""))
        ):
            errors.append("identities.verifier_sha256 is not a placeholder or SHA256")
    if runner_sha256 and not _is_placeholder(observed_runner):
        expect("identities.runner_sha256", observed_runner, runner_sha256)
    if verifier_sha256 and not _is_placeholder(observed_verifier):
        expect("identities.verifier_sha256", observed_verifier, verifier_sha256)

    candidate_src_count = identities.get("candidate_tracked_src_file_count")
    candidate_src_tree_sha = identities.get(
        "candidate_tracked_src_tree_fingerprint_sha256"
    )
    if formal:
        if (
            isinstance(candidate_src_count, bool)
            or not isinstance(candidate_src_count, int)
            or candidate_src_count <= 0
        ):
            errors.append(
                "identities.candidate_tracked_src_file_count is not a positive integer"
            )
        if not isinstance(candidate_src_tree_sha, str) or not SHA256_RE.fullmatch(
            candidate_src_tree_sha
        ):
            errors.append(
                "identities.candidate_tracked_src_tree_fingerprint_sha256 "
                "is not a bound SHA256"
            )
    else:
        if not (
            _is_placeholder(candidate_src_count)
            or (
                not isinstance(candidate_src_count, bool)
                and isinstance(candidate_src_count, int)
                and candidate_src_count > 0
            )
        ):
            errors.append(
                "identities.candidate_tracked_src_file_count is neither a "
                "placeholder nor a positive integer"
            )
        if not (
            _is_placeholder(candidate_src_tree_sha)
            or SHA256_RE.fullmatch(str(candidate_src_tree_sha or ""))
        ):
            errors.append(
                "identities.candidate_tracked_src_tree_fingerprint_sha256 "
                "is neither a placeholder nor a SHA256"
            )

    source_rows = identities.get("candidate_source_files")
    if not isinstance(source_rows, list) or not source_rows:
        errors.append("identities.candidate_source_files must be a non-empty list")
        source_rows = []
    declared_paths: list[str] = []
    source_observations: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows):
        if not isinstance(row, Mapping):
            errors.append(f"candidate_source_files[{index}] is not an object")
            continue
        relative = str(row.get("path") or "")
        pure = PurePosixPath(relative)
        if not relative or pure.is_absolute() or ".." in pure.parts:
            errors.append(f"candidate_source_files[{index}].path is unsafe")
            continue
        if relative in declared_paths:
            errors.append(f"duplicate candidate source path: {relative}")
            continue
        declared_paths.append(relative)
        declared_sha = str(row.get("sha256") or "")
        if formal and not SHA256_RE.fullmatch(declared_sha):
            errors.append(f"candidate source hash is not bound: {relative}")
        elif not formal and not (
            _is_placeholder(declared_sha) or SHA256_RE.fullmatch(declared_sha)
        ):
            errors.append(f"invalid candidate source hash: {relative}")
        observation: dict[str, Any] = {
            "path": relative,
            "sha256_declared": declared_sha,
        }
        if candidate_root is not None:
            path = candidate_root / relative
            if path.is_symlink() or not path.is_file():
                errors.append(f"candidate source is missing: {relative}")
            else:
                actual = file_sha256(path)
                observation["sha256_observed"] = actual
                if not _is_placeholder(declared_sha) and actual != declared_sha:
                    errors.append(
                        f"candidate source hash mismatch {relative}: {actual}"
                    )
        source_observations.append(observation)

    required_candidate_paths = [
        "src/v8_contract_progress_nbv.py",
        "src/v8_spatial_runtime.py",
        "src/v8_seg_v3_model.py",
        "src/v7_vision_claims.py",
        "src/v6_episode.py",
        "src/v7_episode.py",
        "src/look_twice_v7.py",
    ]
    if declared_paths != required_candidate_paths:
        errors.append(
            "candidate source binding path set/order changed: "
            f"expected {required_candidate_paths}, got {declared_paths}"
        )

    candidate_source_closure: dict[str, Any] | None = None
    if (
        candidate_root is not None
        and not _is_placeholder(candidate_src_count)
        and not _is_placeholder(candidate_src_tree_sha)
        and not isinstance(candidate_src_count, bool)
        and isinstance(candidate_src_count, int)
        and isinstance(candidate_src_tree_sha, str)
        and SHA256_RE.fullmatch(candidate_src_tree_sha)
    ):
        try:
            candidate_source_closure = verify_candidate_source_closure(
                candidate_root,
                expected_file_count=candidate_src_count,
                expected_tree_sha256=candidate_src_tree_sha,
            )
        except VerificationError as exc:
            errors.append(str(exc))

    binding = payload.get("public_binding")
    if not isinstance(binding, Mapping):
        errors.append("public_binding must be an object")
        binding = {}
    expect(
        "public_binding.method",
        binding.get("method"),
        "two_commit_public_preregistration",
    )
    expect("public_binding.remote_name", binding.get("remote_name"), "origin")
    expect(
        "public_binding.fresh_seed_opened_before_commit_b",
        binding.get("fresh_seed_opened_before_commit_b"),
        False,
    )
    if formal:
        value = str(binding.get("commit_a") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            errors.append("public_binding.commit_a is not a 40-hex commit")
        expect(
            "public_binding.commit_b",
            binding.get("commit_b"),
            "SELF_NOT_EMBEDDED_CURRENT_CLEAN_HEAD_RECORDED_AT_PRESTART",
        )
        expect(
            "public_binding.commit_b_diff_from_a_may_only_change",
            binding.get("commit_b_diff_from_a_may_only_change"),
            "release/v8-derived/contract_progress_challenge_102530_102549/PREREGISTRATION.json",
        )

    mandatory_gates = payload.get("mandatory_gates")
    if not isinstance(mandatory_gates, Mapping):
        errors.append("mandatory_gates must be an object")
        mandatory_gates = {}
    for key, expected in {
        "valid_attempts_required": 40,
        "mission_success_required": 40,
        "unsafe_allowed": 0,
        "false_clear_allowed": 0,
        "fallback_allowed": 0,
        "collision_allowed": 0,
        "exact_v8_identity_every_episode": True,
        "purify_invoked_every_episode": True,
        "candidate_policy_artifact_id_every_candidate_episode": True,
        "repair_decision_selected_chosen_alignment_every_episode": True,
        "candidate_selector_invoked_every_candidate_episode": True,
        "candidate_selected_equals_chosen_action_every_decision": True,
        "candidate_evidence_request_receipt_rehashed_every_decision": True,
        "candidate_decision_steps_strictly_increasing": True,
        "candidate_go_receipt_exactly_then_current_every_decision": True,
        "candidate_authorized_execution_closure_every_episode": True,
        "native_chosen_required_for_each_repairable_selector_decision": True,
        "zero_native_allowed_only_for_strict_raw_no_repairable_delegation": True,
        "delegated_policy_provenance_every_delegated_item": True,
        "terminal_noop_only_under_exact_budget_and_route_proof": True,
        "compound_intervention_raw_execution_every_candidate_episode": True,
        "compound_initial_capture_raw_binding_every_candidate_episode": True,
        "candidate_helper_absent_from_every_baseline_episode": True,
        "every_chosen_side_view_has_same_corridor_go_p_blocked": True,
        "every_chosen_side_view_has_same_corridor_go_receipt_binding": True,
        "candidate_direct_count_not_below_baseline": True,
        "paired_baseline_direct_to_candidate_nondirect_allowed": 0,
    }.items():
        expect(f"mandatory_gates.{key}", mandatory_gates.get(key), expected)

    gates = payload.get("capability_gates")
    if not isinstance(gates, Mapping):
        errors.append("capability_gates must be an object")
        gates = {}
    expect(
        "capability scout threshold",
        gates.get("scout_path_relative_reduction_min"),
        0.25,
    )
    expect(
        "capability team threshold", gates.get("team_path_relative_reduction_min"), 0.1
    )
    expect(
        "capability capture threshold",
        gates.get("physical_capture_relative_reduction_min"),
        0.2,
    )
    expect(
        "proposal/capture separation",
        gates.get("vision_proposals_are_not_physical_captures"),
        True,
    )
    expect(
        "physical capture definition",
        gates.get("physical_capture_definition"),
        "metrics.observation_count_equal_to_len_metrics.viewpoints_sequence",
    )
    expect("capability denominator", gates.get("denominator"), "all_20_paired_worlds")

    reporting = payload.get("reporting_contract")
    if not isinstance(reporting, Mapping):
        errors.append("reporting_contract must be an object")
        reporting = {}
    for key, expected in {
        "raw_episode_files_expected": 40,
        "per_seed_rows_required": 20,
        "paired_deltas_required": True,
        "mean_median_min_max_required": True,
        "deterministic_paired_bootstrap_95_required": True,
        "wilson_95_for_direct_rates_required": True,
        "carrier_scout_team_path_required": True,
        "physical_capture_and_vision_proposal_counts_separate": True,
        "exact_path_set_required": True,
        "sha256_index_required": True,
        "postrun_immutable_binding_required": True,
        "adverse_no_receipt_run_must_still_report": True,
        "malformed_episode_must_still_report": True,
        "runner_true_to_verifier_false_downgrade_must_still_report": True,
        "no_result_may_be_deleted_replaced_or_rerun": True,
        "sealed_pdf_or_submission_package_may_be_modified": False,
    }.items():
        expect(f"reporting_contract.{key}", reporting.get(key), expected)

    if errors:
        raise VerificationError("invalid preregistration:\n- " + "\n- ".join(errors))
    return {
        "formal_binding_required": formal,
        "runner_sha256": observed_runner,
        "verifier_sha256": observed_verifier,
        "candidate_source_files": source_observations,
        "candidate_source_closure": candidate_source_closure,
        "contract_valid": True,
    }


def _finite_nonnegative(value: Any, *, name: str, errors: list[str]) -> float:
    if isinstance(value, bool):
        errors.append(f"{name} must be numeric")
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        errors.append(f"{name} must be numeric")
        return 0.0
    if not math.isfinite(number) or number < 0.0:
        errors.append(f"{name} must be finite and non-negative")
        return 0.0
    return number


def _nonnegative_int(value: Any, *, name: str, errors: list[str]) -> int:
    if isinstance(value, bool):
        errors.append(f"{name} must be an integer")
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        errors.append(f"{name} must be an integer")
        return 0
    try:
        exact = float(value) == float(number)
    except (TypeError, ValueError, OverflowError):
        exact = False
    if not exact or number < 0:
        errors.append(f"{name} must be a non-negative integer")
        return 0
    return number


def _path_by_agent(payload: Mapping[str, Any], errors: list[str]) -> dict[str, float]:
    segments = payload.get("motion_segments")
    if not isinstance(segments, list):
        errors.append("motion_segments must be a list")
        return {"scout": 0.0, "carrier": 0.0, "team": 0.0}
    totals = {"scout": 0.0, "carrier": 0.0}
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            errors.append(f"motion_segments[{index}] must be an object")
            continue
        agent = str(segment.get("agent_id") or "")
        length = _finite_nonnegative(
            segment.get("path_length"),
            name=f"motion_segments[{index}].path_length",
            errors=errors,
        )
        if agent in totals:
            totals[agent] += length
    return {
        "scout": totals["scout"],
        "carrier": totals["carrier"],
        "team": totals["scout"] + totals["carrier"],
    }


def _full_chain_direct(payload: Mapping[str, Any]) -> bool:
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return False
    selected = metrics.get("selected_corridor")
    if not (
        metrics.get("mission_success") is True
        and metrics.get("route_mode") == "direct"
        and isinstance(selected, str)
        and selected
    ):
        return False
    receipts = payload.get("gate_receipts")
    if not isinstance(receipts, list):
        return False
    return any(
        isinstance(receipt, Mapping)
        and receipt.get("corridor_id") == selected
        and receipt.get("python_admitted") is True
        and receipt.get("purify_go_admitted") is True
        and receipt.get("effective_admit") is True
        for receipt in receipts
    )


def _compound_intervention_audit(
    payload: Mapping[str, Any], *, candidate: bool
) -> tuple[bool, list[str]]:
    metrics = payload.get("metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    audits = payload.get("rgbd_observation_audits")
    audits = audits if isinstance(audits, list) else []
    claims = payload.get("claims")
    claims = claims if isinstance(claims, list) else []
    decisions = payload.get("repair_decisions")
    decisions = decisions if isinstance(decisions, list) else []
    errors: list[str] = []
    contract_keys = [
        key for key in metrics if str(key).startswith("contract_progress_")
    ]
    shared_audits = [
        audit
        for audit in audits
        if isinstance(audit, Mapping) and audit.get("shared_initial_ab_capture") is True
    ]
    vision_audits = [
        audit
        for audit in audits
        if isinstance(audit, Mapping) and audit.get("kind") == "vision_proposal_v7"
    ]
    viewpoints_sequence = metrics.get("viewpoints_sequence")
    if (
        not isinstance(viewpoints_sequence, list)
        or not viewpoints_sequence
        or any(
            not isinstance(viewpoint, str) or not viewpoint
            for viewpoint in viewpoints_sequence
        )
    ):
        errors.append("episode physical viewpoint sequence is malformed")
        viewpoints_sequence = []
    audit_viewpoints = [str(audit.get("viewpoint") or "") for audit in vision_audits]
    if viewpoints_sequence and (
        any(viewpoint not in viewpoints_sequence for viewpoint in audit_viewpoints)
        or set(audit_viewpoints) != set(viewpoints_sequence)
    ):
        errors.append(
            "episode live vision audits do not close over physical viewpoints"
        )
    if metrics.get("vision_sources") != ["genesis_rgb"]:
        errors.append("episode vision_sources is not exactly live genesis_rgb")
    if not vision_audits or any(
        audit.get("vision_source") != "genesis_rgb" for audit in vision_audits
    ):
        errors.append("episode contains missing or non-live vision proposal audits")
    if not candidate:
        if contract_keys:
            errors.append("baseline episode contains candidate contract-progress flags")
        if shared_audits or any(
            isinstance(audit, Mapping) and audit.get("shared_rgbd_backbone") is True
            for audit in audits
        ):
            errors.append("baseline episode used the candidate shared A/B helper")
        if any(
            isinstance(decision, Mapping)
            and (
                any(str(key).startswith("contract_progress_") for key in decision)
                or decision.get("policy_artifact_id") == POLICY_ARTIFACT_ID
                or any(
                    isinstance(item, Mapping)
                    and (
                        item.get("policy_artifact_id") == POLICY_ARTIFACT_ID
                        or item.get("delegating_policy_artifact_id")
                        == POLICY_ARTIFACT_ID
                    )
                    for item in (
                        decision.get("ranking_head")
                        if isinstance(decision.get("ranking_head"), list)
                        else []
                    )
                )
            )
            for decision in decisions
        ):
            errors.append("baseline episode contains candidate selector provenance")
        return not errors, errors

    expected_metrics = {
        "contract_progress_nbv_enabled": True,
        "contract_progress_nbv_policy_artifact_id": POLICY_ARTIFACT_ID,
        "contract_progress_shared_initial_ab_capture": True,
        "contract_progress_shared_initial_ab_proposal_count": 2,
        "contract_progress_shared_initial_ab_corridors": [
            "corridor_a",
            "corridor_b",
        ],
        "contract_progress_all_rgbd_geometry_vision_roots_bound": True,
    }
    for key, expected in expected_metrics.items():
        if metrics.get(key) != expected:
            errors.append(f"candidate compound metric {key} differs from {expected!r}")
    capture_roots = metrics.get("contract_progress_shared_initial_capture_root_ids")
    device_roots = metrics.get("contract_progress_shared_initial_device_root_ids")
    if (
        not isinstance(capture_roots, list)
        or len(capture_roots) != 1
        or not capture_roots[0]
    ):
        errors.append(
            "candidate shared A/B must expose exactly one physical capture root"
        )
    if (
        not isinstance(device_roots, list)
        or len(device_roots) != 1
        or not device_roots[0]
    ):
        errors.append("candidate shared A/B must expose exactly one device root")
    genesis_audits = [
        audit
        for audit in audits
        if isinstance(audit, Mapping)
        and audit.get("kind") == "vision_proposal_v7"
        and audit.get("vision_source") == "genesis_rgb"
    ]
    if not genesis_audits:
        errors.append("candidate has no raw genesis_rgb vision proposal audits")
    vision_claims = [
        claim
        for claim in claims
        if isinstance(claim, Mapping) and claim.get("modality") == "vision_semantic_v7"
    ]
    geometry_claims = [
        claim
        for claim in claims
        if isinstance(claim, Mapping)
        and (
            "depth" in str(claim.get("modality") or "").lower()
            or "geometry" in str(claim.get("modality") or "").lower()
        )
    ]
    if not vision_claims or not geometry_claims:
        errors.append("candidate raw vision/depth-geometry claims are incomplete")

    for index, audit in enumerate(genesis_audits):
        corridor = str(audit.get("corridor_id") or "")
        capture_root = str(audit.get("physical_capture_root_id") or "")
        device_root = str(audit.get("physical_device_root_id") or "")
        model_id = str(audit.get("model_id") or "")
        input_sha = str(audit.get("input_sha256") or "")
        if (
            audit.get("physical_capture_root_bound") is not True
            or corridor not in {"corridor_a", "corridor_b"}
            or not capture_root
            or not device_root
        ):
            errors.append(
                f"candidate genesis proposal {index} lacks a physical root binding"
            )
            continue
        matching_vision = [
            claim
            for claim in vision_claims
            if _nested(claim, "scope", "region_id") == corridor
            and claim.get("capture_root_id") == capture_root
            and claim.get("device_root_id") == device_root
            and (not model_id or claim.get("model_id") == model_id)
            and (not input_sha or claim.get("artifact_sha256") == input_sha)
        ]
        if not matching_vision:
            errors.append(
                f"candidate genesis proposal {index} has no matching rooted vision claim"
            )
        physical_root_geometry = [
            claim
            for claim in geometry_claims
            if claim.get("capture_root_id") == capture_root
            and claim.get("device_root_id") == device_root
        ]
        if not physical_root_geometry:
            errors.append(
                f"candidate genesis proposal {index} is not rooted in a depth/geometry capture"
            )
        same_scope_geometry = [
            claim
            for claim in geometry_claims
            if _nested(claim, "scope", "region_id") == corridor
        ]
        if audit.get("shared_initial_ab_capture") is not True:
            if not any(
                claim.get("capture_root_id") == capture_root
                and claim.get("device_root_id") == device_root
                for claim in same_scope_geometry
            ):
                errors.append(
                    f"candidate side proposal {index} lacks same-scope geometry root"
                )
        if matching_vision:
            observed_steps = {claim.get("observed_step") for claim in matching_vision}
            conflicting = [
                claim
                for claim in same_scope_geometry
                if claim.get("observed_step") in observed_steps
                and (
                    claim.get("capture_root_id") != capture_root
                    or claim.get("device_root_id") != device_root
                )
            ]
            if conflicting:
                errors.append(
                    f"candidate proposal {index} same-step/scope geometry root conflicts"
                )

    if len(shared_audits) != 2:
        errors.append(
            "candidate raw audits must contain exactly two shared A/B proposals"
        )
    else:
        raw_corridors = sorted(
            str(audit.get("corridor_id") or "") for audit in shared_audits
        )
        raw_capture_roots = {
            str(audit.get("shared_physical_capture_root_id") or "")
            for audit in shared_audits
        }
        raw_device_roots = {
            str(audit.get("shared_device_root_id") or "") for audit in shared_audits
        }
        if raw_corridors != ["corridor_a", "corridor_b"]:
            errors.append("candidate raw shared proposals are not exactly A/B scoped")
        if raw_capture_roots != set(capture_roots or []):
            errors.append("candidate raw/metric shared capture roots differ")
        if raw_device_roots != set(device_roots or []):
            errors.append("candidate raw/metric shared device roots differ")
        if not all(
            viewpoints_sequence
            and viewpoints_sequence[0] == "carrier_initial_front"
            and audit.get("viewpoint") == viewpoints_sequence[0]
            and audit.get("observer_agent_id") == "carrier"
            and audit.get("shared_rgbd_backbone") is True
            and _nested(audit, "features", "shared_rgbd_backbone") == 1.0
            and audit.get("physical_capture_root_bound") is True
            and audit.get("physical_capture_root_id")
            == audit.get("shared_physical_capture_root_id")
            and audit.get("physical_device_root_id")
            == audit.get("shared_device_root_id")
            and audit.get("shared_initial_b_mask_source")
            == "public_geometry_projection"
            and audit.get("shared_geometry_pose_semantics") == "legacy_default_empty"
            and audit.get("shared_initial_a_mask_source")
            in {
                "raw_frame.corridor_mask",
                "raw_frame.target_corridor_mask",
                "public_geometry_projection",
            }
            for audit in shared_audits
        ):
            errors.append("candidate shared A/B raw root/backbone audit is incomplete")
        for audit in shared_audits:
            corridor = str(audit.get("corridor_id") or "")
            capture_root = audit.get("physical_capture_root_id")
            device_root = audit.get("physical_device_root_id")
            matching_shared_claims = [
                claim
                for claim in vision_claims
                if _nested(claim, "scope", "region_id") == corridor
                and claim.get("capture_root_id") == capture_root
                and claim.get("device_root_id") == device_root
                and claim.get("model_id") == audit.get("model_id")
                and claim.get("artifact_sha256") == audit.get("input_sha256")
            ]
            if len(matching_shared_claims) != 1:
                errors.append(
                    "candidate shared audit does not bind exactly one raw vision claim"
                )
                continue
            vision_claim = matching_shared_claims[0]
            if not any(
                claim.get("capture_root_id") == capture_root
                and claim.get("device_root_id") == device_root
                and claim.get("observed_step") == vision_claim.get("observed_step")
                and claim.get("received_step") == vision_claim.get("received_step")
                for claim in geometry_claims
            ):
                errors.append(
                    "candidate shared vision claim is not time/root bound to raw geometry"
                )
    if metrics.get("contract_progress_rgbd_vision_proposal_count") != len(
        genesis_audits
    ):
        errors.append("candidate metric/raw genesis proposal counts differ")
    if metrics.get("contract_progress_physical_root_bound_vision_count") != sum(
        bool(audit.get("physical_capture_root_bound")) for audit in genesis_audits
    ):
        errors.append("candidate metric/raw bound-proposal counts differ")
    return not errors, errors


_GO_RECEIPT_FIELDS = {
    "schema_version",
    "receipt_id",
    "contract_id",
    "action",
    "fact_id",
    "predicate",
    "scope",
    "evaluated_step",
    "valid_until_step",
    "admitted",
    "decision",
    "p_blocked",
    "prediction_set",
    "calibration_artifact_id",
    "calibration_applicable",
    "clauses",
    "used_claim_ids",
    "discounted_claims",
    "measurement_root_ids",
    "device_root_ids",
    "unresolved_conflicts",
    "belief_gaps",
    "assumptions",
    "receipt_sha256",
}
_GO_CLAUSE_NAMES = {
    "prediction_set",
    "evidence_age",
    "distinct_measurement_roots",
    "modality_skew",
    "unresolved_conflicts",
    "calibration_applicable",
    "scope_match",
}
_GO_HARD_CLAUSES = {
    "evidence_age",
    "modality_skew",
    "unresolved_conflicts",
    "calibration_applicable",
    "scope_match",
}


def _go_receipt_index(
    payload: Mapping[str, Any],
    *,
    authenticated_receipt_hashes: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    go_receipts = payload.get("purify_go_receipts")
    receipt_index: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if isinstance(go_receipts, list):
        for index, receipt in enumerate(go_receipts):
            if not isinstance(receipt, Mapping):
                errors.append(f"purify_go_receipts[{index}] must be an object")
                continue
            receipt_sha = receipt.get("receipt_sha256")
            corridor_id = _nested(receipt, "scope", "region_id")
            go_p = receipt.get("p_blocked")
            clauses = receipt.get("clauses")
            clause_rows = clauses if isinstance(clauses, list) else []
            clause_names = [
                str(clause.get("clause") or "")
                for clause in clause_rows
                if isinstance(clause, Mapping)
            ]
            clauses_by_name = {
                str(clause.get("clause")): clause
                for clause in clause_rows
                if isinstance(clause, Mapping)
                and str(clause.get("clause") or "") in _GO_CLAUSE_NAMES
            }
            roots_clause = clauses_by_name.get("distinct_measurement_roots")
            roots_actual = (
                roots_clause.get("actual")
                if isinstance(roots_clause, Mapping)
                else None
            )
            roots_required = (
                roots_clause.get("required")
                if isinstance(roots_clause, Mapping)
                else None
            )
            base_fields = {str(key) for key in receipt if not str(key).startswith("_")}
            prediction_set = receipt.get("prediction_set")
            prediction_labels = (
                {str(label) for label in prediction_set}
                if isinstance(prediction_set, list)
                else set()
            )
            prediction_clause = clauses_by_name.get("prediction_set")
            prediction_actual = (
                prediction_clause.get("actual")
                if isinstance(prediction_clause, Mapping)
                else None
            )
            prediction_actual_labels = (
                {str(label) for label in prediction_actual}
                if isinstance(prediction_actual, list)
                else set()
            )
            scope = receipt.get("scope")
            evaluated_step = receipt.get("evaluated_step")
            valid_until_step = receipt.get("valid_until_step")
            authenticated = bool(
                authenticated_receipt_hashes is None
                or (
                    isinstance(receipt_sha, str)
                    and receipt_sha in authenticated_receipt_hashes
                )
            )
            valid = bool(
                isinstance(receipt_sha, str)
                and SHA256_RE.fullmatch(receipt_sha)
                and authenticated
                and receipt_sha not in receipt_index
                and base_fields == _GO_RECEIPT_FIELDS
                and receipt.get("schema_version") == "purify.robotics.gate-receipt/v1"
                and receipt.get("_purify_invoked") is True
                and receipt.get("_purify_binary_sha256") == EXPECTED_PURIFY_SHA256
                and receipt.get("_go_calibration_artifact_id") == GO_CALIBRATION_ID
                and receipt.get("_runtime_calibration_id") == VISION_CALIBRATION_ID
                and receipt.get("calibration_artifact_id") == GO_CALIBRATION_ID
                and receipt.get("calibration_applicable") is True
                and isinstance(corridor_id, str)
                and corridor_id in {"corridor_a", "corridor_b"}
                and isinstance(scope, Mapping)
                and set(scope) == {"robot_id", "payload_id", "region_id"}
                and scope.get("robot_id") == "carrier"
                and scope.get("payload_id") == "payload_loaded"
                and not isinstance(evaluated_step, bool)
                and isinstance(evaluated_step, int)
                and evaluated_step >= 0
                and not isinstance(valid_until_step, bool)
                and isinstance(valid_until_step, int)
                and valid_until_step >= evaluated_step
                and not isinstance(go_p, bool)
                and isinstance(go_p, (int, float))
                and math.isfinite(float(go_p))
                and 0.0 <= float(go_p) <= 1.0
                and len(clause_rows) == len(_GO_CLAUSE_NAMES)
                and set(clause_names) == _GO_CLAUSE_NAMES
                and len(set(clause_names)) == len(clause_names)
                and all(
                    isinstance(clauses_by_name[name].get("passed"), bool)
                    for name in _GO_CLAUSE_NAMES
                )
                and bool(prediction_labels)
                and prediction_labels <= {"clear", "blocked"}
                and prediction_actual_labels == prediction_labels
                and not isinstance(roots_actual, bool)
                and isinstance(roots_actual, int)
                and roots_actual >= 0
                and not isinstance(roots_required, bool)
                and isinstance(roots_required, int)
                and roots_required > 0
            )
            if not valid:
                if not authenticated:
                    errors.append(
                        f"purify_go_receipts[{index}] was not authenticated by "
                        "the frozen Go binary"
                    )
                else:
                    errors.append(
                        f"purify_go_receipts[{index}] is not an exact canonical "
                        "frozen-Go receipt"
                    )
                continue
            receipt_index[receipt_sha] = {
                "corridor_id": corridor_id,
                "go_p_blocked": float(go_p),
                "roots_actual": roots_actual,
                "roots_required": roots_required,
                "evaluated_step": evaluated_step,
                "valid_until_step": valid_until_step,
                "hard_reasons": sorted(
                    {
                        *(
                            {"go_prediction_blocked"}
                            if "clear" not in prediction_labels
                            else set()
                        ),
                        *{
                            f"go_clause_failed:{name}"
                            for name in _GO_HARD_CLAUSES
                            if clauses_by_name[name].get("passed") is False
                        },
                    }
                ),
                "repairable": bool(
                    "clear" in prediction_labels
                    and all(
                        clauses_by_name[name].get("passed") is True
                        for name in _GO_HARD_CLAUSES
                    )
                ),
            }
    else:
        errors.append("purify_go_receipts must be a list")
    return receipt_index, errors


def _go_binding_valid(
    item: Mapping[str, Any],
    receipt_index: Mapping[str, Mapping[str, Any]],
) -> bool:
    action = item.get("action")
    go_p = item.get("go_p_blocked")
    receipt_sha = item.get("go_receipt_sha256")
    receipt_observation = receipt_index.get(str(receipt_sha or ""))
    measurement_root_debt = item.get("go_measurement_root_debt")
    repair_step_debt = item.get("repair_step_debt")
    expected_measurement_debt = (
        max(
            int(receipt_observation["roots_required"])
            - int(receipt_observation["roots_actual"]),
            0,
        )
        if receipt_observation is not None
        else None
    )
    expected_repair_debt = (
        max(1, expected_measurement_debt)
        if expected_measurement_debt is not None
        else None
    )
    return bool(
        isinstance(action, Mapping)
        and action.get("kind") == "side_view"
        and isinstance(action.get("corridor_id"), str)
        and "go_p_blocked" in item
        and not isinstance(go_p, bool)
        and isinstance(go_p, (int, float))
        and math.isfinite(float(go_p))
        and 0.0 <= float(go_p) <= 1.0
        and receipt_observation is not None
        and receipt_observation["corridor_id"] == action.get("corridor_id")
        and math.isclose(
            float(receipt_observation["go_p_blocked"]),
            float(go_p),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        and not isinstance(measurement_root_debt, bool)
        and measurement_root_debt == expected_measurement_debt
        and not isinstance(repair_step_debt, bool)
        and repair_step_debt == expected_repair_debt
    )


_EFFECTIVE_HARD_REASONS = {
    "calibration_not_applicable",
    "evidence_conflict",
    "modality_conflict",
    "prediction_blocked",
    "purify_go_missing",
    "unknown_observer",
    "unknown_root",
}


def _effective_gate_hard_reasons(
    payload: Mapping[str, Any],
    *,
    corridor_id: str,
    go_receipt_sha256: str,
) -> set[str]:
    gates = payload.get("gate_receipts")
    if not isinstance(gates, list):
        return set()
    result: set[str] = set()
    for gate in gates:
        if not isinstance(gate, Mapping):
            continue
        if (
            gate.get("corridor_id") != corridor_id
            or _nested(gate, "purify_go_receipt", "receipt_sha256") != go_receipt_sha256
            or gate.get("effective_admit") is not False
        ):
            continue
        reasons = gate.get("reasons")
        if isinstance(reasons, list):
            result.update(str(reason) for reason in reasons)
    return result & _EFFECTIVE_HARD_REASONS


def _claim_confirmed_blocked(
    payload: Mapping[str, Any], *, corridor_id: str, evaluated_step: int
) -> bool:
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return False
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        quality = claim.get("quality")
        visibility = claim.get("visibility")
        observed_step = claim.get("observed_step")
        received_step = claim.get("received_step")
        if (
            claim.get("value") == "blocked"
            and _nested(claim, "scope", "region_id") == corridor_id
            and not isinstance(quality, bool)
            and isinstance(quality, (int, float))
            and math.isfinite(float(quality))
            and float(quality) >= 0.35
            and not isinstance(visibility, bool)
            and isinstance(visibility, (int, float))
            and math.isfinite(float(visibility))
            and float(visibility) >= 0.35
            and not isinstance(observed_step, bool)
            and isinstance(observed_step, int)
            and 0 <= observed_step <= evaluated_step
            and not isinstance(received_step, bool)
            and isinstance(received_step, int)
            and observed_step <= received_step <= evaluated_step
        ):
            return True
    return False


_EVIDENCE_REQUEST_FIELDS = {
    "schema_version",
    "receipt_id",
    "authorized",
    "selected_observer",
    "target_viewpoint",
    "target_fact_id",
    "target_scope",
    "expected_gap_repairs",
    "policy_artifact_id",
    "candidate_ranking_sha256",
    "physical_risk",
    "valid_until_step",
    "receipt_sha256",
    "reasons",
}


def _decision_evidence_request_valid(
    decision: Mapping[str, Any], request: Mapping[str, Any]
) -> bool:
    """Authenticate the producer's decision→authorization receipt binding."""

    selected = decision.get("selected")
    reasons = request.get("reasons")
    valid_until = request.get("valid_until_step")
    ranking_sha = request.get("candidate_ranking_sha256")
    receipt_sha = request.get("receipt_sha256")
    if (
        set(request) != _EVIDENCE_REQUEST_FIELDS
        or request.get("schema_version") != "look-twice.evidence-request-receipt/v1"
        or request.get("policy_artifact_id") != POLICY_ARTIFACT_ID
        or request.get("authorized") is not decision.get("authorized")
        or decision.get("execution_status")
        != (
            "authorized_for_execution"
            if request.get("authorized") is True
            else "authorization_denied_noop"
        )
        or not isinstance(reasons, list)
        or any(not isinstance(reason, str) for reason in reasons)
        or isinstance(valid_until, bool)
        or not isinstance(valid_until, int)
        or valid_until < 40
        or not isinstance(ranking_sha, str)
        or not SHA256_RE.fullmatch(ranking_sha)
        or not isinstance(receipt_sha, str)
        or not SHA256_RE.fullmatch(receipt_sha)
        or decision.get("evidence_request_receipt_sha256") != receipt_sha
        or request.get("receipt_id") != f"evr_{receipt_sha[:20]}"
    ):
        return False
    current_step = valid_until - 40
    if selected is None:
        if not (
            request.get("authorized") is False
            and request.get("selected_observer") is None
            and request.get("target_viewpoint") is None
            and request.get("target_fact_id") is None
            and request.get("target_scope") is None
        ):
            return False
        body = {
            "authorized": False,
            "step": current_step,
            "reasons": reasons,
            "ranking": ranking_sha,
        }
    elif isinstance(selected, Mapping):
        name = str(selected.get("name") or "")
        observer = str(selected.get("observer") or "")
        viewpoint = str(selected.get("viewpoint") or name)
        corridor = str(selected.get("corridor_id") or "")
        expected_scope = (
            {
                "robot_id": "carrier",
                "payload_id": "payload_loaded",
                "region_id": corridor,
            }
            if corridor
            else None
        )
        risk = selected.get("physical_risk") or 0.0
        if (
            not name
            or request.get("selected_observer") != (observer or None)
            or request.get("target_viewpoint") != (viewpoint or None)
            or request.get("target_fact_id")
            != (f"region:{corridor}" if corridor else None)
            or request.get("target_scope") != expected_scope
            or isinstance(risk, bool)
            or not isinstance(risk, (int, float))
            or not math.isfinite(float(risk))
            or request.get("physical_risk") != float(risk)
        ):
            return False
        body = {
            "authorized": request.get("authorized"),
            "name": name,
            "observer": observer,
            "viewpoint": viewpoint,
            "step": current_step,
            "reasons": reasons,
            "ranking": ranking_sha,
            "policy": POLICY_ARTIFACT_ID,
        }
    else:
        return False
    return canonical_json_sha256(body) == receipt_sha


def _terminal_delegated_noop_valid(
    payload: Mapping[str, Any],
    decisions: Sequence[Any],
    *,
    decision_index: int,
    decision: Mapping[str, Any],
    chosen_items: Sequence[Mapping[str, Any]],
    no_repairable_proof_valid: bool,
) -> bool:
    """Prove a final denied side-view proposal was not physically executed."""

    if (
        len(decisions) != 4
        or decision_index != 3
        or decision_index != len(decisions) - 1
        or not no_repairable_proof_valid
        or decision.get("authorized") is not False
        or decision.get("execution_status") != "authorization_denied_noop"
        or len(chosen_items) != 1
    ):
        return False
    chosen = chosen_items[0]
    action = chosen.get("action")
    selected = decision.get("selected")
    if (
        chosen.get("delegated_baseline_fail_closed") is not True
        or not isinstance(action, Mapping)
        or action.get("kind") != "side_view"
        or not isinstance(selected, Mapping)
        or selected.get("kind") != "side_view"
        or selected.get("name") != action.get("name")
    ):
        return False

    request_receipts = payload.get("evidence_request_receipts")
    if not isinstance(request_receipts, list) or len(request_receipts) != len(
        decisions
    ):
        return False
    configuration = payload.get("configuration")
    if not isinstance(configuration, Mapping):
        return False
    max_observations = configuration.get("max_observations")
    max_replans = configuration.get("max_replans")
    if max_observations != 6 or max_replans != 3:
        return False
    prior_viewpoints: list[str] = []
    prior_targets: list[tuple[float, float]] = []
    for index, (prior_decision, request) in enumerate(zip(decisions, request_receipts)):
        if not isinstance(prior_decision, Mapping) or not isinstance(request, Mapping):
            return False
        prior_selected = prior_decision.get("selected")
        if not isinstance(prior_selected, Mapping):
            return False
        if not _decision_evidence_request_valid(prior_decision, request) or request.get(
            "receipt_sha256"
        ) != prior_decision.get("evidence_request_receipt_sha256"):
            return False
        reasons = request.get("reasons")
        if index < decision_index:
            prior_kind = str(prior_selected.get("kind") or "")
            if (
                prior_decision.get("authorized") is not True
                or prior_kind != "side_view"
                or reasons != []
                or len(prior_targets) >= max_replans
                or 1 + len(prior_viewpoints) >= max_observations
            ):
                return False
            prior_viewpoints.append(str(prior_selected.get("viewpoint") or ""))
            target = prior_selected.get("target_xy")
            if (
                not isinstance(target, list)
                or len(target) != 2
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in target
                )
            ):
                return False
            prior_targets.append((float(target[0]), float(target[1])))
        else:
            if not isinstance(reasons, list):
                return False

    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return False
    replan_count = metrics.get("replan_count")
    observation_count = metrics.get("observation_count")
    viewpoints = metrics.get("viewpoints_sequence")
    if (
        isinstance(replan_count, bool)
        or replan_count != len(prior_targets)
        or isinstance(observation_count, bool)
        or not isinstance(observation_count, int)
        or not isinstance(viewpoints, list)
        or observation_count != len(viewpoints)
        or not viewpoints
        or viewpoints[0] != "carrier_initial_front"
        or viewpoints[1:] != prior_viewpoints
        or str(action.get("viewpoint") or "") in viewpoints
        or metrics.get("route_mode") != "detour"
        or metrics.get("used_detour") is not True
        or metrics.get("selected_corridor") is not None
        or metrics.get("repair_success") is not False
    ):
        return False
    if (
        replan_count != max_replans
        or observation_count >= max_observations
        or request_receipts[-1]["reasons"] != ["max_replans_reached"]
    ):
        return False
    motion_segments = payload.get("motion_segments")
    if not isinstance(motion_segments, list):
        return False
    scout_segments = [
        segment
        for segment in motion_segments
        if isinstance(segment, Mapping) and segment.get("agent_id") == "scout"
    ]
    if len(scout_segments) != len(prior_targets):
        return False
    for segment, expected_target in zip(scout_segments, prior_targets):
        target = segment.get("target_xy")
        if (
            not isinstance(target, list)
            or len(target) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in target
            )
            or not all(
                math.isclose(
                    float(observed),
                    expected,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
                for observed, expected in zip(target, expected_target)
            )
        ):
            return False
    audits = payload.get("rgbd_observation_audits")
    if not isinstance(audits, list):
        return False
    return not any(
        isinstance(audit, Mapping)
        and audit.get("kind") == "vision_proposal_v7"
        and audit.get("viewpoint") == action.get("viewpoint")
        and audit.get("corridor_id") == action.get("corridor_id")
        for audit in audits
    )


def _terminal_delegated_route_noop_valid(
    payload: Mapping[str, Any],
    decisions: Sequence[Any],
    *,
    decision_index: int,
    decision: Mapping[str, Any],
    chosen_items: Sequence[Mapping[str, Any]],
    no_repairable_proof_valid: bool,
    bound_request: Mapping[str, Any] | None,
) -> bool:
    """Bind a final safe-fallback label to the subsequent physical detour."""

    if (
        decision_index != len(decisions) - 1
        or not no_repairable_proof_valid
        or len(chosen_items) != 1
        or not isinstance(bound_request, Mapping)
        or not _decision_evidence_request_valid(decision, bound_request)
    ):
        return False
    chosen = chosen_items[0]
    action = chosen.get("action")
    selected = decision.get("selected")
    if (
        chosen.get("delegated_baseline_fail_closed") is not True
        or not isinstance(action, Mapping)
        or action.get("kind") != "safe_fallback"
        or not isinstance(selected, Mapping)
        or selected.get("kind") != "safe_fallback"
        or selected.get("name") != action.get("name")
    ):
        return False
    metrics = payload.get("metrics")
    configuration = payload.get("configuration")
    if not isinstance(metrics, Mapping) or not isinstance(configuration, Mapping):
        return False
    if (
        metrics.get("route_mode") != "detour"
        or metrics.get("used_detour") is not True
        or metrics.get("selected_corridor") is not None
        or metrics.get("repair_success") is not False
    ):
        return False
    observation_count = metrics.get("observation_count")
    max_observations = configuration.get("max_observations")
    if (
        isinstance(observation_count, bool)
        or not isinstance(observation_count, int)
        or max_observations != 6
    ):
        return False
    if decision.get("authorized") is True:
        return (
            decision.get("execution_status") == "authorized_for_execution"
            and bound_request.get("reasons") == []
            and observation_count < max_observations
        )
    return bool(
        decision.get("authorized") is False
        and decision.get("execution_status") == "authorization_denied_noop"
        and bound_request.get("reasons") == ["max_observations_reached"]
        and observation_count == max_observations
    )


def _candidate_execution_closure_valid(
    payload: Mapping[str, Any], decisions: Sequence[Any]
) -> bool:
    """Bind every authorized observation/motion to its decision in order."""

    executed_viewpoints: list[str] = []
    scout_targets: list[tuple[float, float]] = []
    for decision in decisions:
        if not isinstance(decision, Mapping):
            return False
        selected = decision.get("selected")
        if decision.get("authorized") is not True:
            continue
        if not isinstance(selected, Mapping):
            return False
        kind = str(selected.get("kind") or "")
        if kind not in {"wait", "safe_fallback"}:
            viewpoint = str(selected.get("viewpoint") or "")
            if not viewpoint:
                return False
            executed_viewpoints.append(viewpoint)
        if kind == "side_view":
            if selected.get("observer") != "scout":
                return False
            target = selected.get("target_xy")
            if (
                not isinstance(target, list)
                or len(target) != 2
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in target
                )
            ):
                return False
            scout_targets.append((float(target[0]), float(target[1])))

    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return False
    viewpoints = metrics.get("viewpoints_sequence")
    observation_count = metrics.get("observation_count")
    replan_count = metrics.get("replan_count")
    if (
        not isinstance(viewpoints, list)
        or not viewpoints
        or viewpoints[0] != "carrier_initial_front"
        or isinstance(observation_count, bool)
        or not isinstance(observation_count, int)
        or observation_count != len(viewpoints)
        or viewpoints[1:] != executed_viewpoints
        or isinstance(replan_count, bool)
        or replan_count != len(scout_targets)
    ):
        return False
    segments = payload.get("motion_segments")
    if not isinstance(segments, list):
        return False
    scout_segments = [
        segment
        for segment in segments
        if isinstance(segment, Mapping) and segment.get("agent_id") == "scout"
    ]
    if len(scout_segments) != len(scout_targets):
        return False
    for segment, expected_target in zip(scout_segments, scout_targets):
        observed_target = segment.get("target_xy")
        if (
            not isinstance(observed_target, list)
            or len(observed_target) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in observed_target
            )
            or not all(
                math.isclose(
                    float(observed),
                    expected,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
                for observed, expected in zip(observed_target, expected_target)
            )
        ):
            return False
    return True


def _repair_decision_audit(
    payload: Mapping[str, Any],
    *,
    candidate: bool,
    authenticated_go_receipt_hashes: set[str] | None = None,
) -> dict[str, Any]:
    decisions = payload.get("repair_decisions")
    errors: list[str] = []
    if not isinstance(decisions, list):
        return {
            "alignment_valid": False,
            "candidate_selector_invoked_valid": not candidate,
            "candidate_conditional_native_invocation_valid": not candidate,
            "delegated_policy_provenance_valid": not candidate,
            "candidate_raw_repairable_contract": False,
            "candidate_no_repairable_proof_valid": not candidate,
            "candidate_execution_closure_valid": not candidate,
            "nondelegated_candidate_chosen_count": 0,
            "delegated_chosen_count": 0,
            "delegated_decision_count": 0,
            "terminal_delegated_noop_count": 0,
            "terminal_delegated_route_noop_count": 0,
            "native_selector_decision_count": 0,
            "errors": ["repair_decisions must be a list"],
        }
    receipt_index, receipt_errors = _go_receipt_index(
        payload,
        authenticated_receipt_hashes=authenticated_go_receipt_hashes,
    )
    errors.extend(receipt_errors)
    nondelegated_candidate_chosen_count = 0
    delegated_chosen_count = 0
    alignment_valid = True
    delegated_policy_provenance_valid = True
    selector_invoked_valid = bool(not candidate or decisions)
    no_repairable_proof_valid = True
    delegated_decision_count = 0
    terminal_delegated_noop_count = 0
    terminal_delegated_route_noop_count = 0
    raw_repairable_selector_contract = False
    native_selector_decision_count = 0
    conditional_decisions_valid = True
    execution_closure_valid = bool(
        not candidate or _candidate_execution_closure_valid(payload, decisions)
    )
    if candidate and not execution_closure_valid:
        conditional_decisions_valid = False
        errors.append("candidate authorized decision execution closure is inconsistent")
    request_receipts = payload.get("evidence_request_receipts")
    request_index: dict[str, Mapping[str, Any]] = {}
    if candidate:
        if not isinstance(request_receipts, list) or len(request_receipts) != len(
            decisions
        ):
            selector_invoked_valid = False
            errors.append(
                "candidate evidence-request receipt count differs from decisions"
            )
        else:
            for request_index_number, request in enumerate(request_receipts):
                if not isinstance(request, Mapping):
                    selector_invoked_valid = False
                    errors.append(
                        "candidate evidence-request receipt "
                        f"{request_index_number} is not an object"
                    )
                    continue
                receipt_sha = str(request.get("receipt_sha256") or "")
                if not SHA256_RE.fullmatch(receipt_sha) or receipt_sha in request_index:
                    selector_invoked_valid = False
                    errors.append(
                        "candidate evidence-request receipt hash is invalid or "
                        "duplicated"
                    )
                    continue
                request_index[receipt_sha] = request
    if candidate and not decisions:
        errors.append("candidate episode contains no selector invocation decision")
    previous_request_step: int | None = None
    for decision_index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping):
            alignment_valid = False
            errors.append(f"repair_decisions[{decision_index}] must be an object")
            continue
        ranking = decision.get("ranking_head")
        if not isinstance(ranking, list):
            alignment_valid = False
            errors.append(
                f"repair_decisions[{decision_index}].ranking_head must be a list"
            )
            continue
        chosen_items = [
            item
            for item in ranking
            if isinstance(item, Mapping) and item.get("chosen") is True
        ]
        selected = decision.get("selected")
        if selected is None:
            aligned = not chosen_items
        elif isinstance(selected, Mapping) and isinstance(selected.get("name"), str):
            aligned = bool(
                selected.get("name")
                and len(chosen_items) == 1
                and isinstance(chosen_items[0].get("action"), Mapping)
                and chosen_items[0]["action"].get("name") == selected.get("name")
                and (not candidate or chosen_items[0]["action"] == selected)
            )
        else:
            aligned = False
        if not aligned:
            alignment_valid = False
            errors.append(
                f"repair_decisions[{decision_index}] selected/chosen mismatch"
            )

        if not candidate:
            continue
        request_sha = str(decision.get("evidence_request_receipt_sha256") or "")
        bound_request = request_index.get(request_sha)
        if bound_request is None or not _decision_evidence_request_valid(
            decision, bound_request
        ):
            selector_invoked_valid = False
            errors.append(
                f"candidate repair decision {decision_index} lacks an "
                "authenticated evidence-request authorization binding"
            )
        else:
            request_step = int(bound_request["valid_until_step"]) - 40
            if (
                previous_request_step is not None
                and request_step <= previous_request_step
            ):
                selector_invoked_valid = False
                errors.append(
                    "candidate evidence-request decision steps are not strictly "
                    "increasing"
                )
            previous_request_step = request_step
        if (
            decision.get("contract_progress_nbv_enabled") is not True
            or decision.get("policy_artifact_id") != POLICY_ARTIFACT_ID
            or decision.get("contract_progress_selector_invoked") is not True
        ):
            selector_invoked_valid = False
            errors.append(
                f"candidate repair decision {decision_index} lacks selector invocation"
            )
        decision_delegated = decision.get("delegated_baseline_fail_closed") is True
        decision_authorized = decision.get("authorized") is True
        corridor_audit = decision.get("contract_progress_selector_corridor_audit")
        corridor_states_valid = bool(
            isinstance(corridor_audit, Mapping)
            and set(corridor_audit) == {"corridor_a", "corridor_b"}
        )
        both_corridors_hard = corridor_states_valid
        all_delegation_reasons_nonempty_truthful = corridor_states_valid
        repairable_corridors: set[str] = set()
        prior_authorized_side_corridors = [
            str(_nested(prior, "selected", "corridor_id") or "")
            for prior in decisions[:decision_index]
            if isinstance(prior, Mapping)
            and prior.get("authorized") is True
            and _nested(prior, "selected", "kind") == "side_view"
        ]
        public_corridors = {
            str(item.get("id") or "")
            for item in _nested(payload, "scenario", "public_context", "corridors")
            or []
            if isinstance(item, Mapping)
        }
        if corridor_states_valid:
            for corridor_id in ("corridor_a", "corridor_b"):
                audit = corridor_audit[corridor_id]
                if not isinstance(audit, Mapping) or set(audit) != {
                    "go_receipt_sha256",
                    "go_p_blocked",
                    "roots_actual",
                    "roots_required",
                    "go_measurement_root_debt",
                    "repair_step_debt",
                    "fail_closed_reasons",
                }:
                    corridor_states_valid = False
                    both_corridors_hard = False
                    break
                receipt_sha = audit.get("go_receipt_sha256")
                go_p = audit.get("go_p_blocked")
                fail_reasons = audit.get("fail_closed_reasons")
                if not isinstance(fail_reasons, list):
                    corridor_states_valid = False
                    both_corridors_hard = False
                    break
                fail_reason_set = {str(reason) for reason in fail_reasons}
                validated_hard: set[str] = set()
                observation = None
                if receipt_sha is None:
                    if go_p is None and "missing_go_receipt" in fail_reason_set:
                        validated_hard.add("missing_go_receipt")
                else:
                    observation = receipt_index.get(str(receipt_sha))
                    request_step = (
                        int(bound_request["valid_until_step"]) - 40
                        if isinstance(bound_request, Mapping)
                        and isinstance(bound_request.get("valid_until_step"), int)
                        and not isinstance(bound_request.get("valid_until_step"), bool)
                        else None
                    )
                    if (
                        observation is None
                        or observation.get("corridor_id") != corridor_id
                        or isinstance(go_p, bool)
                        or not isinstance(go_p, (int, float))
                        or not math.isclose(
                            float(go_p),
                            float(observation["go_p_blocked"]),
                            rel_tol=0.0,
                            abs_tol=1e-12,
                        )
                        or audit.get("roots_actual") != observation.get("roots_actual")
                        or audit.get("roots_required")
                        != observation.get("roots_required")
                        or audit.get("go_measurement_root_debt")
                        != max(
                            int(observation["roots_required"])
                            - int(observation["roots_actual"]),
                            0,
                        )
                        or audit.get("repair_step_debt")
                        != max(
                            1,
                            int(observation["roots_required"])
                            - int(observation["roots_actual"]),
                        )
                        or request_step is None
                        or int(observation["evaluated_step"]) != request_step
                        or request_step > int(observation["valid_until_step"])
                    ):
                        corridor_states_valid = False
                        both_corridors_hard = False
                        break
                    validated_hard.update(observation.get("hard_reasons", []))
                    validated_hard.update(
                        _effective_gate_hard_reasons(
                            payload,
                            corridor_id=corridor_id,
                            go_receipt_sha256=str(receipt_sha),
                        )
                    )
                if observation is not None and _claim_confirmed_blocked(
                    payload,
                    corridor_id=corridor_id,
                    evaluated_step=int(observation["evaluated_step"]),
                ):
                    validated_hard.add("confirmed_blocked")
                repair_debt = audit.get("repair_step_debt")
                if isinstance(repair_debt, int) and not isinstance(repair_debt, bool):
                    prior_side_count = prior_authorized_side_corridors.count(
                        corridor_id
                    )
                    if prior_side_count + repair_debt > 2:
                        validated_hard.add("insufficient_side_view_budget")
                    if 1 + len(prior_authorized_side_corridors) + repair_debt > 6:
                        validated_hard.add("insufficient_observation_budget")
                if corridor_id not in public_corridors and public_corridors:
                    validated_hard.add("corridor_not_in_public_geometry")
                reported_reasons_truthful = fail_reason_set <= validated_hard
                actual_hard = bool(validated_hard)
                if not reported_reasons_truthful:
                    corridor_states_valid = False
                    all_delegation_reasons_nonempty_truthful = False
                    errors.append(
                        f"candidate repair decision {decision_index} corridor "
                        f"{corridor_id} reports unbound fail-closed reasons"
                    )
                if not fail_reason_set:
                    all_delegation_reasons_nonempty_truthful = False
                if (
                    observation is not None
                    and observation.get("repairable") is True
                    and not actual_hard
                    and reported_reasons_truthful
                ):
                    raw_repairable_selector_contract = True
                    repairable_corridors.add(corridor_id)
                    both_corridors_hard = False
                elif not actual_hard:
                    both_corridors_hard = False
        else:
            selector_invoked_valid = False
            errors.append(
                f"candidate repair decision {decision_index} lacks exact corridor audit"
            )
        proof_valid = False
        if decision_delegated:
            delegated_decision_count += 1
            proof_valid = bool(
                decision.get("contract_progress_no_repairable_contract") is True
                and decision.get("contract_progress_selector_selection_reason")
                == "fail_closed_no_repairable_go_contract"
                and corridor_states_valid
                and both_corridors_hard
                and all_delegation_reasons_nonempty_truthful
            )
            if not proof_valid:
                no_repairable_proof_valid = False
                errors.append(
                    f"delegated repair decision {decision_index} lacks an "
                    "independently bound no-repairable proof"
                )
        terminal_delegated_noop = bool(
            decision_delegated
            and _terminal_delegated_noop_valid(
                payload,
                decisions,
                decision_index=decision_index,
                decision=decision,
                chosen_items=chosen_items,
                no_repairable_proof_valid=proof_valid,
            )
        )
        if terminal_delegated_noop:
            terminal_delegated_noop_count += 1
        terminal_delegated_route_noop = bool(
            decision_delegated
            and _terminal_delegated_route_noop_valid(
                payload,
                decisions,
                decision_index=decision_index,
                decision=decision,
                chosen_items=chosen_items,
                no_repairable_proof_valid=proof_valid,
                bound_request=bound_request,
            )
        )
        if terminal_delegated_route_noop:
            terminal_delegated_route_noop_count += 1
        native_count_before = nondelegated_candidate_chosen_count
        delegated_chosen_before = delegated_chosen_count
        for item_index, item in enumerate(ranking):
            if not isinstance(item, Mapping):
                delegated_policy_provenance_valid = False
                errors.append(
                    f"candidate ranking item {decision_index}:{item_index} is not an object"
                )
                continue
            delegated = item.get("delegated_baseline_fail_closed") is True
            policy_id = item.get("policy_artifact_id")
            if delegated:
                provenance_valid = bool(
                    policy_id == "heuristic-v6/1"
                    and item.get("delegating_policy_artifact_id") == POLICY_ARTIFACT_ID
                )
                if not provenance_valid:
                    delegated_policy_provenance_valid = False
                    errors.append(
                        f"delegated ranking item {decision_index}:{item_index} "
                        "has invalid policy provenance"
                    )
                action = item.get("action")
                if isinstance(action, Mapping) and action.get("kind") == "side_view":
                    if not _go_binding_valid(item, receipt_index):
                        delegated_policy_provenance_valid = False
                        errors.append(
                            f"delegated side view {decision_index}:{item_index} "
                            "lacks same-corridor online Go binding"
                        )
                if item.get("chosen") is True:
                    action = item.get("action")
                    action_kind = (
                        action.get("kind") if isinstance(action, Mapping) else None
                    )
                    safe_fallback_shape_valid = bool(
                        action_kind == "safe_fallback"
                        and item.get("go_p_blocked") is None
                        and item.get("go_receipt_sha256") is None
                        and item.get("go_measurement_root_debt") is None
                        and item.get("repair_step_debt") is None
                    )
                    delegated_execution_valid = bool(
                        action_kind == "side_view"
                        and decision_authorized
                        and _go_binding_valid(item, receipt_index)
                    )
                    if delegated_execution_valid:
                        delegated_chosen_count += 1
                    elif not (
                        terminal_delegated_noop
                        and action_kind == "side_view"
                        and _go_binding_valid(item, receipt_index)
                    ) and not (
                        terminal_delegated_route_noop and safe_fallback_shape_valid
                    ):
                        delegated_policy_provenance_valid = False
                        errors.append(
                            f"delegated chosen item {decision_index}:{item_index} "
                            "is neither an authorized receipt-bound side view nor "
                            "a valid safe fallback"
                        )
            else:
                if item.get("delegating_policy_artifact_id") is not None:
                    delegated_policy_provenance_valid = False
                    errors.append(
                        f"non-delegated ranking item {decision_index}:{item_index} "
                        "has a delegating policy ID"
                    )
                if policy_id not in (None, POLICY_ARTIFACT_ID):
                    delegated_policy_provenance_valid = False
                    errors.append(
                        f"non-delegated ranking item {decision_index}:{item_index} "
                        "has an unexpected policy ID"
                    )
                if item.get("chosen") is True and policy_id == POLICY_ARTIFACT_ID:
                    receipt_observation = receipt_index.get(
                        str(item.get("go_receipt_sha256") or "")
                    )
                    if (
                        decision_authorized
                        and _go_binding_valid(item, receipt_index)
                        and receipt_observation is not None
                        and receipt_observation.get("repairable") is True
                        and str(_nested(item, "action", "corridor_id") or "")
                        in repairable_corridors
                        and isinstance(corridor_audit, Mapping)
                        and _nested(
                            corridor_audit,
                            str(_nested(item, "action", "corridor_id") or ""),
                            "go_receipt_sha256",
                        )
                        == item.get("go_receipt_sha256")
                    ):
                        nondelegated_candidate_chosen_count += 1
                    else:
                        errors.append(
                            f"non-delegated candidate chosen item "
                            f"{decision_index}:{item_index} is not an authorized "
                            "online-Go-bound side view"
                        )

        native_this_decision = nondelegated_candidate_chosen_count - native_count_before
        delegated_this_decision = delegated_chosen_count - delegated_chosen_before
        if decision_delegated:
            valid_delegated_branch = bool(
                native_this_decision == 0
                and proof_valid
                and (
                    delegated_this_decision == 1
                    or (
                        delegated_this_decision == 0
                        and (terminal_delegated_noop or terminal_delegated_route_noop)
                    )
                )
            )
            if not valid_delegated_branch:
                conditional_decisions_valid = False
        else:
            if (
                native_this_decision != 1
                or delegated_this_decision != 0
                or not repairable_corridors
            ):
                conditional_decisions_valid = False
                errors.append(
                    f"candidate repair decision {decision_index} is neither a "
                    "native repairable choice nor a proved fail-closed delegation"
                )
            else:
                native_selector_decision_count += 1

    raw_repairable_contract = raw_repairable_selector_contract
    conditional_native_valid = bool(
        not candidate or (selector_invoked_valid and conditional_decisions_valid)
    )
    if candidate and not conditional_native_valid:
        errors.append("candidate conditional native/delegation rule failed")
    return {
        "alignment_valid": alignment_valid,
        "candidate_selector_invoked_valid": (
            selector_invoked_valid if candidate else True
        ),
        "candidate_conditional_native_invocation_valid": conditional_native_valid,
        "delegated_policy_provenance_valid": (
            delegated_policy_provenance_valid if candidate else True
        ),
        "nondelegated_candidate_chosen_count": (nondelegated_candidate_chosen_count),
        "delegated_chosen_count": delegated_chosen_count,
        "delegated_decision_count": delegated_decision_count,
        "terminal_delegated_noop_count": terminal_delegated_noop_count,
        "terminal_delegated_route_noop_count": (terminal_delegated_route_noop_count),
        "native_selector_decision_count": native_selector_decision_count,
        "candidate_raw_repairable_contract": (
            raw_repairable_contract if candidate else False
        ),
        "candidate_no_repairable_proof_valid": (
            no_repairable_proof_valid if candidate else True
        ),
        "candidate_execution_closure_valid": execution_closure_valid,
        "errors": errors,
    }


def derive_episode_row(
    payload: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    authenticated_go_receipt_hashes: set[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    metrics = payload.get("metrics")
    config = payload.get("configuration")
    environment = payload.get("environment")
    scenario = payload.get("scenario")
    for name, value in (
        ("metrics", metrics),
        ("configuration", config),
        ("environment", environment),
        ("scenario", scenario),
    ):
        if not isinstance(value, Mapping):
            errors.append(f"{name} must be an object")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    config = config if isinstance(config, Mapping) else {}
    environment = environment if isinstance(environment, Mapping) else {}
    scenario = scenario if isinstance(scenario, Mapping) else {}

    if payload.get("schema_version") != "look-twice.episode/v7":
        errors.append("schema_version must be look-twice.episode/v7")
    if scenario.get("seed") != spec["seed"]:
        errors.append("scenario.seed does not match schedule")
    if scenario.get("profile") != PROFILE:
        errors.append("scenario.profile does not match fixed profile")
    if config.get("policy") != spec["policy"]:
        errors.append("configuration.policy does not match schedule")
    if config.get("vision_backend") != "torch_spatial_rgbd":
        errors.append("vision backend is not frozen torch_spatial_rgbd")
    if config.get("use_purify_go_gate") is not True:
        errors.append("Purify Go gate is not enabled")
    if config.get("repair_required") is not True:
        errors.append("repair_required is not true")
    for field, expected in {
        "ttl_steps": 2000,
        "max_observations": 6,
        "max_replans": 3,
        "device": "cuda:0",
        "prefer_rgbd_claims": True,
        "vision_enabled": True,
        "require_vision_clear_root": True,
        "require_side_view_vision_root": True,
        "enforce_modality_conflict": True,
        "use_v7_contract": True,
        "sensor_version": "look-twice-rgbd-multi-agent-v6/1",
    }.items():
        if config.get(field) != expected:
            errors.append(f"configuration.{field} differs from frozen V8")
    if config.get("learned_checkpoint") is not None:
        errors.append("configuration.learned_checkpoint must remain null")
    if environment.get("formal_result_eligible") is not False:
        errors.append("formal_result_eligible must be false")
    if environment.get("runtime") != "genesis-amd":
        errors.append("runtime must be genesis-amd")
    if environment.get("physics_backend") != "kinematic":
        errors.append("physics_backend must be kinematic")
    if environment.get("device") != "cuda:0":
        errors.append("environment.device must be cuda:0")
    if environment.get("artifact_inputs_eligible") is not True:
        errors.append("environment.artifact_inputs_eligible must be true")
    for field in (
        "mission_success",
        "unsafe_crossing",
        "clear_admitted_collision",
        "admit_then_contact",
        "fallback_used",
        "vision_fallback_used",
        "checkpoint_loaded",
        "genesis_live_rgbd",
        "world_alignment_passed",
        "purify_invoked",
    ):
        if not isinstance(metrics.get(field), bool):
            errors.append(f"metrics.{field} must be Boolean")
    if metrics.get("route_mode") not in {"direct", "detour"}:
        errors.append("metrics.route_mode must be direct or detour")
    if metrics.get("selected_corridor") is not None and not isinstance(
        metrics.get("selected_corridor_oracle_blocked"), bool
    ):
        errors.append(
            "selected-corridor oracle-blocked audit must be Boolean when selected"
        )

    paths = _path_by_agent(payload, errors)
    capture_count = _nonnegative_int(
        metrics.get("observation_count"),
        name="metrics.observation_count",
        errors=errors,
    )
    viewpoints = metrics.get("viewpoints_sequence")
    if not isinstance(viewpoints, list):
        errors.append("metrics.viewpoints_sequence must be a list")
        viewpoints = []
    if capture_count != len(viewpoints):
        errors.append(
            "physical capture count mismatch: metrics.observation_count != "
            "len(metrics.viewpoints_sequence)"
        )
    proposal_count = _nonnegative_int(
        metrics.get("vision_proposal_count"),
        name="metrics.vision_proposal_count",
        errors=errors,
    )
    if proposal_count < capture_count:
        errors.append("vision proposal count is below physical capture count")

    identity_valid = bool(
        metrics.get("checkpoint_sha256") == EXPECTED_CHECKPOINT_SHA256
        and metrics.get("conformal_artifact_sha256") == EXPECTED_VISION_ARTIFACT_SHA256
        and metrics.get("purify_binary_sha256") == EXPECTED_PURIFY_SHA256
        and metrics.get("checkpoint_loaded") is True
        and metrics.get("fallback_used") is False
        and metrics.get("vision_fallback_used") is False
        and metrics.get("genesis_live_rgbd") is True
        and metrics.get("world_alignment_passed") is True
    )
    if not identity_valid:
        errors.append("one or more frozen V8 runtime identities/flags are invalid")

    go_receipts = payload.get("purify_go_receipts")
    if not isinstance(go_receipts, list) or not go_receipts:
        errors.append("purify_go_receipts must be a non-empty list")
        go_receipts = []
    purify_invoked_count = _nonnegative_int(
        metrics.get("purify_invoked_count"),
        name="metrics.purify_invoked_count",
        errors=errors,
    )
    purify_valid = bool(
        metrics.get("purify_invoked") is True
        and purify_invoked_count > 0
        and purify_invoked_count == len(go_receipts)
        and all(
            isinstance(receipt, Mapping)
            and isinstance(receipt.get("receipt_sha256"), str)
            and SHA256_RE.fullmatch(str(receipt.get("receipt_sha256"))) is not None
            and receipt.get("_purify_invoked") is True
            and receipt.get("_purify_binary_sha256") == EXPECTED_PURIFY_SHA256
            and receipt.get("calibration_artifact_id") == GO_CALIBRATION_ID
            and receipt.get("_go_calibration_artifact_id") == GO_CALIBRATION_ID
            and receipt.get("_runtime_calibration_id") == VISION_CALIBRATION_ID
            and receipt.get("calibration_applicable") is True
            for receipt in go_receipts
        )
    )
    if not purify_valid:
        errors.append("Purify invocation or frozen Go calibration identity is invalid")

    collision_count = _nonnegative_int(
        metrics.get("collision_count"),
        name="metrics.collision_count",
        errors=errors,
    )
    unsafe = metrics.get("unsafe_crossing") is not False
    false_clear = any(
        (
            metrics.get("clear_admitted_collision") is True,
            metrics.get("admit_then_contact") is True,
            metrics.get("selected_corridor_oracle_blocked") is True,
        )
    )
    fallback = bool(
        metrics.get("fallback_used") is True
        or metrics.get("vision_fallback_used") is True
    )
    compound_valid, compound_errors = _compound_intervention_audit(
        payload, candidate=spec["arm"] == "candidate"
    )
    errors.extend(compound_errors)
    repair_audit = _repair_decision_audit(
        payload,
        candidate=spec["arm"] == "candidate",
        authenticated_go_receipt_hashes=authenticated_go_receipt_hashes,
    )
    errors.extend(str(error) for error in repair_audit["errors"])
    alignment_valid = bool(repair_audit["alignment_valid"])
    candidate_selector_valid = bool(repair_audit["candidate_selector_invoked_valid"])
    candidate_invocation_valid = bool(
        repair_audit["candidate_conditional_native_invocation_valid"]
    )
    delegated_provenance_valid = bool(repair_audit["delegated_policy_provenance_valid"])
    policy_receipt_valid = bool(
        candidate_selector_valid
        and candidate_invocation_valid
        and delegated_provenance_valid
    )
    if not policy_receipt_valid:
        errors.append("candidate policy artifact receipt is missing or inconsistent")

    return {
        "seed": spec["seed"],
        "arm": spec["arm"],
        "policy": spec["policy"],
        "structural_valid": not errors,
        "validation_errors": errors,
        "mission_success": metrics.get("mission_success") is True,
        "unsafe": unsafe,
        "false_clear": false_clear,
        "fallback": fallback,
        "collision_count": collision_count,
        "identity_valid": identity_valid,
        "purify_valid": purify_valid,
        "compound_intervention_valid": compound_valid,
        "repair_decision_alignment_valid": alignment_valid,
        "candidate_selector_invoked_valid": candidate_selector_valid,
        "candidate_conditional_native_invocation_valid": (candidate_invocation_valid),
        "delegated_policy_provenance_valid": delegated_provenance_valid,
        "nondelegated_candidate_chosen_count": repair_audit[
            "nondelegated_candidate_chosen_count"
        ],
        "delegated_chosen_count": repair_audit["delegated_chosen_count"],
        "delegated_decision_count": repair_audit["delegated_decision_count"],
        "terminal_delegated_noop_count": repair_audit["terminal_delegated_noop_count"],
        "terminal_delegated_route_noop_count": repair_audit[
            "terminal_delegated_route_noop_count"
        ],
        "candidate_execution_closure_valid": repair_audit[
            "candidate_execution_closure_valid"
        ],
        "native_selector_decision_count": repair_audit[
            "native_selector_decision_count"
        ],
        "candidate_raw_repairable_contract": repair_audit[
            "candidate_raw_repairable_contract"
        ],
        "candidate_no_repairable_proof_valid": repair_audit[
            "candidate_no_repairable_proof_valid"
        ],
        "candidate_policy_receipt_valid": policy_receipt_valid,
        "full_chain_direct": _full_chain_direct(payload),
        "selected_corridor": metrics.get("selected_corridor"),
        "route_mode": metrics.get("route_mode"),
        "scout_path_length": paths["scout"],
        "carrier_path_length": paths["carrier"],
        "team_path_length": paths["team"],
        "physical_capture_count": capture_count,
        "vision_proposal_count": proposal_count,
    }


def wilson_95(count: int, total: int) -> dict[str, float | int]:
    if total <= 0:
        return {"count": count, "total": total, "lower": 0.0, "upper": 1.0}
    z = 1.959963984540054
    p = count / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    spread = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denom
    return {
        "count": count,
        "total": total,
        "rate": p,
        "lower": max(0.0, center - spread),
        "upper": min(1.0, center + spread),
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def paired_summary(
    candidate: Sequence[float], baseline: Sequence[float]
) -> dict[str, Any]:
    if len(candidate) != len(baseline) or not candidate:
        return {"n": 0, "valid": False}
    deltas = [float(c) - float(b) for c, b in zip(candidate, baseline)]
    rng = random.Random(BOOTSTRAP_SEED + len(deltas))
    boot_means: list[float] = []
    boot_reductions: list[float] = []
    n = len(deltas)
    for _ in range(BOOTSTRAP_REPLICATES):
        indexes = [rng.randrange(n) for _ in range(n)]
        sampled_delta = statistics.fmean(deltas[index] for index in indexes)
        sampled_candidate = statistics.fmean(candidate[index] for index in indexes)
        sampled_baseline = statistics.fmean(baseline[index] for index in indexes)
        boot_means.append(sampled_delta)
        if sampled_baseline > 0:
            boot_reductions.append(1.0 - sampled_candidate / sampled_baseline)
    mean_candidate = statistics.fmean(candidate)
    mean_baseline = statistics.fmean(baseline)
    reduction = 1.0 - mean_candidate / mean_baseline if mean_baseline > 0.0 else None
    return {
        "n": n,
        "valid": True,
        "baseline": {
            "mean": mean_baseline,
            "median": statistics.median(baseline),
            "minimum": min(baseline),
            "maximum": max(baseline),
        },
        "candidate": {
            "mean": mean_candidate,
            "median": statistics.median(candidate),
            "minimum": min(candidate),
            "maximum": max(candidate),
        },
        "paired_delta_candidate_minus_baseline": {
            "mean": statistics.fmean(deltas),
            "median": statistics.median(deltas),
            "minimum": min(deltas),
            "maximum": max(deltas),
            "bootstrap_95": {
                "method": "paired_percentile_bootstrap",
                "replicates": BOOTSTRAP_REPLICATES,
                "rng_seed": BOOTSTRAP_SEED + n,
                "lower": _percentile(boot_means, 0.025),
                "upper": _percentile(boot_means, 0.975),
            },
        },
        "relative_reduction": reduction,
        "relative_reduction_bootstrap_95": {
            "lower": _percentile(boot_reductions, 0.025),
            "upper": _percentile(boot_reductions, 0.975),
        },
    }


def derive_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    preregistration_sha256: str,
    run_manifest_sha256: str,
    postrun_binding_valid: bool = True,
) -> dict[str, Any]:
    by_key = {(int(row["seed"]), str(row["arm"])): row for row in rows}
    paired: list[dict[str, Any]] = []
    for seed in SEEDS:
        baseline = by_key.get((seed, "baseline"))
        candidate = by_key.get((seed, "candidate"))
        if baseline is None or candidate is None:
            continue
        paired.append(
            {
                "seed": seed,
                "baseline": dict(baseline),
                "candidate": dict(candidate),
                "paired_deltas_candidate_minus_baseline": {
                    "scout_path_length": float(candidate["scout_path_length"])
                    - float(baseline["scout_path_length"]),
                    "carrier_path_length": float(candidate["carrier_path_length"])
                    - float(baseline["carrier_path_length"]),
                    "team_path_length": float(candidate["team_path_length"])
                    - float(baseline["team_path_length"]),
                    "physical_capture_count": int(candidate["physical_capture_count"])
                    - int(baseline["physical_capture_count"]),
                    "vision_proposal_count": int(candidate["vision_proposal_count"])
                    - int(baseline["vision_proposal_count"]),
                },
            }
        )

    baseline_rows = [
        by_key[(seed, "baseline")] for seed in SEEDS if (seed, "baseline") in by_key
    ]
    candidate_rows = [
        by_key[(seed, "candidate")] for seed in SEEDS if (seed, "candidate") in by_key
    ]

    def values(arm_rows: Sequence[Mapping[str, Any]], name: str) -> list[float]:
        return [float(row[name]) for row in arm_rows]

    burden = {
        "scout_path_length": paired_summary(
            values(candidate_rows, "scout_path_length"),
            values(baseline_rows, "scout_path_length"),
        ),
        "carrier_path_length": paired_summary(
            values(candidate_rows, "carrier_path_length"),
            values(baseline_rows, "carrier_path_length"),
        ),
        "team_path_length": paired_summary(
            values(candidate_rows, "team_path_length"),
            values(baseline_rows, "team_path_length"),
        ),
        "physical_capture_count": paired_summary(
            values(candidate_rows, "physical_capture_count"),
            values(baseline_rows, "physical_capture_count"),
        ),
        "vision_proposal_count_descriptive_only": paired_summary(
            values(candidate_rows, "vision_proposal_count"),
            values(baseline_rows, "vision_proposal_count"),
        ),
    }

    baseline_direct = sum(bool(row["full_chain_direct"]) for row in baseline_rows)
    candidate_direct = sum(bool(row["full_chain_direct"]) for row in candidate_rows)
    baseline_only = sum(
        bool(by_key[(seed, "baseline")]["full_chain_direct"])
        and not bool(by_key[(seed, "candidate")]["full_chain_direct"])
        for seed in SEEDS
        if (seed, "baseline") in by_key and (seed, "candidate") in by_key
    )
    candidate_only = sum(
        bool(by_key[(seed, "candidate")]["full_chain_direct"])
        and not bool(by_key[(seed, "baseline")]["full_chain_direct"])
        for seed in SEEDS
        if (seed, "baseline") in by_key and (seed, "candidate") in by_key
    )

    valid_attempts = sum(bool(row["structural_valid"]) for row in rows)
    mission_success = sum(bool(row["mission_success"]) for row in rows)
    unsafe_count = sum(bool(row["unsafe"]) for row in rows)
    false_clear_count = sum(bool(row["false_clear"]) for row in rows)
    fallback_count = sum(bool(row["fallback"]) for row in rows)
    collision_count = sum(int(row["collision_count"]) for row in rows)
    identity_valid_count = sum(bool(row["identity_valid"]) for row in rows)
    purify_valid_count = sum(bool(row["purify_valid"]) for row in rows)
    compound_valid_count = sum(bool(row["compound_intervention_valid"]) for row in rows)
    alignment_valid_count = sum(
        bool(row["repair_decision_alignment_valid"]) for row in rows
    )
    candidate_policy_valid_count = sum(
        bool(row["candidate_policy_receipt_valid"]) for row in candidate_rows
    )
    candidate_selector_valid_count = sum(
        bool(row["candidate_selector_invoked_valid"]) for row in candidate_rows
    )
    candidate_invocation_valid_count = sum(
        bool(row["candidate_conditional_native_invocation_valid"])
        for row in candidate_rows
    )
    candidate_execution_closure_valid_count = sum(
        bool(row["candidate_execution_closure_valid"]) for row in candidate_rows
    )
    candidate_repairable_count = sum(
        bool(row["candidate_raw_repairable_contract"]) for row in candidate_rows
    )
    candidate_no_repairable_count = len(candidate_rows) - candidate_repairable_count
    candidate_no_repairable_proof_valid_count = sum(
        bool(row["candidate_no_repairable_proof_valid"])
        for row in candidate_rows
        if not bool(row["candidate_raw_repairable_contract"])
    )
    delegated_provenance_valid_count = sum(
        bool(row["delegated_policy_provenance_valid"]) for row in candidate_rows
    )
    provisional_integrity_downgrade_count = sum(
        bool(row.get("attempt_integrity_provisional_downgraded")) for row in rows
    )

    mandatory = {
        "all_40_attempts_structurally_valid": len(rows) == 40 and valid_attempts == 40,
        "mission_success_40_of_40": len(rows) == 40 and mission_success == 40,
        "unsafe_zero": unsafe_count == 0,
        "false_clear_zero": false_clear_count == 0,
        "fallback_zero": fallback_count == 0,
        "collision_zero": collision_count == 0,
        "exact_v8_identity_40_of_40": identity_valid_count == 40,
        "purify_valid_40_of_40": purify_valid_count == 40,
        "compound_intervention_and_baseline_isolation_40_of_40": (
            compound_valid_count == 40
        ),
        "repair_decision_alignment_40_of_40": alignment_valid_count == 40,
        "candidate_policy_receipt_20_of_20": candidate_policy_valid_count == 20,
        "candidate_selector_invoked_20_of_20": (candidate_selector_valid_count == 20),
        "candidate_conditional_native_invocation_20_of_20": (
            candidate_invocation_valid_count == 20
        ),
        "candidate_authorized_execution_closure_20_of_20": (
            candidate_execution_closure_valid_count == 20
        ),
        "candidate_no_repairable_proof_all_no_repairable_episodes": (
            candidate_no_repairable_proof_valid_count == candidate_no_repairable_count
        ),
        "delegated_policy_provenance_20_of_20": (
            delegated_provenance_valid_count == 20
        ),
        "candidate_direct_not_below_baseline": candidate_direct >= baseline_direct,
        "no_paired_direct_regression": baseline_only == 0,
        "postrun_immutable_binding_valid": postrun_binding_valid,
    }
    mandatory["all_pass"] = all(mandatory.values())
    scout_reduction = burden["scout_path_length"].get("relative_reduction")
    team_reduction = burden["team_path_length"].get("relative_reduction")
    capture_reduction = burden["physical_capture_count"].get("relative_reduction")
    capability = {
        "scout_path_relative_reduction_min_0_25": bool(
            scout_reduction is not None and float(scout_reduction) >= 0.25
        ),
        "team_path_relative_reduction_min_0_10": bool(
            team_reduction is not None and float(team_reduction) >= 0.10
        ),
        "physical_capture_relative_reduction_min_0_20": bool(
            capture_reduction is not None and float(capture_reduction) >= 0.20
        ),
        "scout_path_relative_reduction_observed": scout_reduction,
        "team_path_relative_reduction_observed": team_reduction,
        "physical_capture_relative_reduction_observed": capture_reduction,
    }
    capability["all_pass"] = bool(
        capability["scout_path_relative_reduction_min_0_25"]
        and capability["team_path_relative_reduction_min_0_10"]
        and capability["physical_capture_relative_reduction_min_0_20"]
    )

    return {
        "schema_version": REPORT_SCHEMA,
        "formal_result_eligible": False,
        "evidence_scope": {
            "worlds": 20,
            "paired_episodes": 40,
            "seed_range": [SEED_START, SEED_END],
            "generator_family": "same_generator_as_v8_spatial_dataset_v1",
            "same_generator": True,
            "not_ood": True,
            "not_physical_robot": True,
            "not_locked": True,
            "motion_backend": "kinematic",
        },
        "source_binding": {
            "preregistration_sha256": preregistration_sha256,
            "run_manifest_sha256": run_manifest_sha256,
        },
        "attempt_accounting": {
            "rows": len(rows),
            "structurally_valid": valid_attempts,
            "mission_success": mission_success,
            "unsafe": unsafe_count,
            "false_clear": false_clear_count,
            "fallback": fallback_count,
            "collisions": collision_count,
            "identity_valid": identity_valid_count,
            "purify_valid": purify_valid_count,
            "compound_intervention_valid": compound_valid_count,
            "repair_decision_alignment_valid": alignment_valid_count,
            "candidate_policy_receipt_valid": candidate_policy_valid_count,
            "candidate_selector_invoked_valid": candidate_selector_valid_count,
            "candidate_conditional_native_invocation_valid": (
                candidate_invocation_valid_count
            ),
            "candidate_authorized_execution_closure_valid": (
                candidate_execution_closure_valid_count
            ),
            "candidate_repairability_strata": {
                "repairable_raw_contract": candidate_repairable_count,
                "no_repairable_raw_contract": candidate_no_repairable_count,
                "no_repairable_proof_valid": (
                    candidate_no_repairable_proof_valid_count
                ),
            },
            "delegated_policy_provenance_valid": (delegated_provenance_valid_count),
            "runner_provisional_integrity_downgraded_by_verifier": (
                provisional_integrity_downgrade_count
            ),
        },
        "full_chain_direct": {
            "baseline": wilson_95(baseline_direct, len(baseline_rows)),
            "candidate": wilson_95(candidate_direct, len(candidate_rows)),
            "paired_table": {
                "baseline_only": baseline_only,
                "candidate_only": candidate_only,
                "both_direct": sum(
                    bool(by_key[(seed, "baseline")]["full_chain_direct"])
                    and bool(by_key[(seed, "candidate")]["full_chain_direct"])
                    for seed in SEEDS
                    if (seed, "baseline") in by_key and (seed, "candidate") in by_key
                ),
                "neither_direct": sum(
                    not bool(by_key[(seed, "baseline")]["full_chain_direct"])
                    and not bool(by_key[(seed, "candidate")]["full_chain_direct"])
                    for seed in SEEDS
                    if (seed, "baseline") in by_key and (seed, "candidate") in by_key
                ),
            },
        },
        "operational_burden": burden,
        "mandatory_gates": mandatory,
        "capability_gates": capability,
        "promotion_pass": bool(mandatory["all_pass"] and capability["all_pass"]),
        "per_seed": paired,
    }


def _safe_relative_path(value: Any, *, name: str) -> str:
    relative = str(value or "")
    pure = PurePosixPath(relative)
    if (
        not relative
        or pure.is_absolute()
        or relative != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise VerificationError(f"unsafe {name}: {relative!r}")
    return pure.as_posix()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise VerificationError(f"cannot read JSONL {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise VerificationError(f"blank JSONL row at {path}:{line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerificationError(
                f"invalid JSONL at {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise VerificationError(f"non-object JSONL row at {path}:{line_number}")
        rows.append(row)
    return rows


def _walk_relative_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise VerificationError(f"symlink is forbidden in output root: {path}")
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return files


def _expected_attempt_command(
    spec: Mapping[str, Any],
    *,
    output_root: Path,
    prestart: Mapping[str, Any],
) -> list[str]:
    arm_root_key = "baseline_root" if spec["arm"] == "baseline" else "candidate_root"
    required_paths = {
        key: str(prestart.get(key) or "")
        for key in (
            "python_executable",
            "baseline_root",
            "candidate_root",
            "checkpoint_path",
            "vision_artifact_path",
            "go_artifact_path",
            "purify_binary_path",
        )
    }
    if any(
        not value or not Path(value).is_absolute() for value in required_paths.values()
    ):
        raise VerificationError("prestart command-binding paths are not absolute")
    return [
        required_paths["python_executable"],
        str(Path(required_paths[arm_root_key]) / "src" / "look_twice_v7.py"),
        "--runtime",
        "genesis",
        "--motion-backend",
        "kinematic",
        "--policy",
        str(spec["policy"]),
        "--profile",
        PROFILE,
        "--seed",
        str(spec["seed"]),
        "--device",
        "cuda:0",
        "--vision-backend",
        "torch_spatial_rgbd",
        "--vision-checkpoint",
        required_paths["checkpoint_path"],
        "--vision-conformal-artifact",
        required_paths["vision_artifact_path"],
        "--go-conformal-artifact",
        required_paths["go_artifact_path"],
        "--use-purify-go-gate",
        "--purify-binary",
        required_paths["purify_binary_path"],
        "--repair-required",
        "--json-output",
        str(output_root / str(spec["episode_path"])),
    ]


def authenticate_output_go_receipts(
    output_root: Path,
    prestart: Mapping[str, Any],
) -> set[str]:
    """Ask the frozen Go binary—not Python JSON—to verify receipt hashes."""

    unique: dict[str, dict[str, Any]] = {}
    for spec in build_schedule():
        episode_path = output_root / str(spec["episode_path"])
        if not episode_path.is_file():
            continue
        try:
            payload = read_json_object(episode_path)
        except VerificationError:
            # A child may leave a present, hashable, but truncated/non-JSON
            # episode.  It has no authenticatable receipts; the manifest pass
            # below retains it as one structural failure instead of suppressing
            # the complete adverse report.
            continue
        receipts = payload.get("purify_go_receipts")
        if not isinstance(receipts, list):
            continue
        for receipt in receipts:
            if not isinstance(receipt, Mapping):
                continue
            receipt_sha = str(receipt.get("receipt_sha256") or "")
            if not SHA256_RE.fullmatch(receipt_sha):
                continue
            base = {
                str(key): value
                for key, value in receipt.items()
                if not str(key).startswith("_")
            }
            prior = unique.get(receipt_sha)
            if prior is not None and prior != base:
                raise VerificationError(
                    f"duplicate Go receipt SHA has conflicting payload: {receipt_sha}"
                )
            unique[receipt_sha] = base
    # An all-failure run may legitimately retain no episode receipt at all.  That
    # is a failed scientific result, not a verifier crash: the per-episode gates
    # will remain false and the complete adverse report can still be written.
    if not unique:
        return set()

    binary = Path(str(prestart.get("purify_binary_path") or ""))
    if (
        not binary.is_absolute()
        or binary.is_symlink()
        or not binary.is_file()
        or file_sha256(binary) != EXPECTED_PURIFY_SHA256
    ):
        raise VerificationError("cannot authenticate Go receipts with frozen Purify")

    commands: list[dict[str, Any]] = []
    ordered_hashes = sorted(unique)
    for index, receipt_sha in enumerate(ordered_hashes):
        receipt = unique[receipt_sha]
        evaluated_step = receipt.get("evaluated_step")
        if (
            isinstance(evaluated_step, bool)
            or not isinstance(evaluated_step, int)
            or evaluated_step < 0
        ):
            raise VerificationError(
                f"Go receipt {receipt_sha} has no valid evaluated_step"
            )
        commands.append(
            {
                "schema_version": "purify.robotics.command.v1",
                "request_id": f"verify-{index:08d}",
                "op": "invalidate_plan",
                "payload": {
                    "previous_receipt": receipt,
                    "current_step": evaluated_step,
                    "triggering_claims": [],
                },
            }
        )
    input_text = "".join(
        json.dumps(
            command,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
        for command in commands
    )
    completed = subprocess.run(
        [str(binary)],
        input=input_text,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(120, len(commands) * 2),
        env={
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LANGUAGE"} or key.startswith("LC_")
        },
    )
    if completed.returncode != 0:
        raise VerificationError(
            "frozen Purify receipt-authentication process failed: "
            f"{completed.stderr.strip()}"
        )
    lines = completed.stdout.splitlines()
    if len(lines) != len(commands):
        raise VerificationError("frozen Purify returned an incomplete receipt proof")
    authenticated: set[str] = set()
    for command, receipt_sha, line in zip(commands, ordered_hashes, lines):
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerificationError("frozen Purify returned invalid JSON") from exc
        if not isinstance(response, Mapping):
            raise VerificationError("frozen Purify response is not an object")
        if (
            response.get("schema_version") != "purify.robotics.response.v1"
            or response.get("request_id") != command["request_id"]
            or not isinstance(response.get("ok"), bool)
        ):
            raise VerificationError(
                f"frozen Purify returned a malformed proof for Go receipt {receipt_sha}"
            )
        # A well-formed negative response is retained as an unauthenticated
        # receipt.  `_go_receipt_index` then marks each episode that used it
        # structurally invalid while the verifier still emits the full report.
        if response.get("ok") is False:
            continue
        result = response.get("result")
        if (
            not isinstance(result, Mapping)
            or result.get("schema_version")
            != "purify.robotics.plan-invalidation-receipt/v1"
            or result.get("previous_receipt_sha256") != receipt_sha
        ):
            raise VerificationError(
                f"frozen Purify rejected or misbound Go receipt {receipt_sha}"
            )
        authenticated.add(receipt_sha)
    return authenticated


def _failed_episode_row(
    spec: Mapping[str, Any], validation_error: str
) -> dict[str, Any]:
    """Return the complete conservative row shape for a retained bad episode."""

    baseline = spec["arm"] == "baseline"
    return {
        "seed": spec["seed"],
        "arm": spec["arm"],
        "policy": spec["policy"],
        "structural_valid": False,
        "validation_errors": [validation_error],
        "mission_success": False,
        "unsafe": False,
        "false_clear": False,
        "fallback": False,
        "collision_count": 0,
        "identity_valid": False,
        "purify_valid": False,
        "compound_intervention_valid": False,
        "repair_decision_alignment_valid": False,
        "candidate_selector_invoked_valid": baseline,
        "candidate_conditional_native_invocation_valid": baseline,
        "delegated_policy_provenance_valid": baseline,
        "nondelegated_candidate_chosen_count": 0,
        "delegated_chosen_count": 0,
        "delegated_decision_count": 0,
        "terminal_delegated_noop_count": 0,
        "terminal_delegated_route_noop_count": 0,
        "candidate_execution_closure_valid": baseline,
        "native_selector_decision_count": 0,
        "candidate_raw_repairable_contract": False,
        "candidate_no_repairable_proof_valid": baseline,
        "candidate_policy_receipt_valid": baseline,
        "full_chain_direct": False,
        "selected_corridor": None,
        "route_mode": None,
        "scout_path_length": 0.0,
        "carrier_path_length": 0.0,
        "team_path_length": 0.0,
        "physical_capture_count": 0,
        "vision_proposal_count": 0,
    }


def validate_manifest_and_load_rows(
    output_root: Path,
    manifest: Mapping[str, Any],
    prestart: Mapping[str, Any],
    authenticated_go_receipt_hashes: set[str],
) -> tuple[
    list[dict[str, Any]],
    set[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise VerificationError("unexpected RUN_MANIFEST schema")
    if manifest.get("formal_result_eligible") is not False:
        raise VerificationError("RUN_MANIFEST formal_result_eligible must be false")
    expected_schedule = build_schedule()
    if manifest.get("fixed_schedule") != expected_schedule:
        raise VerificationError(
            "RUN_MANIFEST fixed_schedule differs from preregistration"
        )
    if manifest.get("schedule_sha256") != schedule_sha256():
        raise VerificationError("RUN_MANIFEST schedule hash mismatch")
    attempts = manifest.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != EPISODE_COUNT:
        raise VerificationError("RUN_MANIFEST must retain exactly 40 attempts")
    jsonl_attempts = _read_jsonl(output_root / "raw" / "ATTEMPTS.jsonl")
    if jsonl_attempts != attempts:
        raise VerificationError("ATTEMPTS.jsonl differs from RUN_MANIFEST attempts")
    windows = _read_jsonl(output_root / "raw" / "EPISODE_WINDOWS.jsonl")
    if len(windows) != EPISODE_COUNT:
        raise VerificationError("EPISODE_WINDOWS.jsonl must contain 40 rows")

    expected_paths = {
        "raw/PRESTART_BINDING.json",
        "raw/POSTRUN_BINDING.json",
        "raw/ATTEMPTS.jsonl",
        "raw/EPISODE_WINDOWS.jsonl",
        "raw/ROCM_SAMPLES.jsonl",
        "RUN_MANIFEST.json",
        "ROCM_TELEMETRY.json",
    }
    rows: list[dict[str, Any]] = []
    previous_end_ns: int | None = None
    for spec, attempt, window in zip(expected_schedule, attempts, windows):
        for key in ("schedule_index", "seed", "arm", "policy", "profile"):
            if attempt.get(key) != spec.get(key):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} has wrong {key}"
                )
            if window.get(key) != spec.get(key):
                raise VerificationError(
                    f"episode window {spec['schedule_index']} has wrong {key}"
                )
        for key in ("episode_path", "stdout_path", "stderr_path", "error_path"):
            if attempt.get(key) != spec[key]:
                raise VerificationError(
                    f"attempt {spec['schedule_index']} has wrong {key}"
                )
        if attempt.get("retry_count") != 0:
            raise VerificationError(
                f"attempt {spec['schedule_index']} violates the no-retry contract"
            )
        if attempt.get("attempt_artifacts_fsynced") is not True:
            raise VerificationError(
                f"attempt {spec['schedule_index']} lacks durable artifact persistence"
            )
        expected_command = _expected_attempt_command(
            spec,
            output_root=output_root,
            prestart=prestart,
        )
        internal_runner_empty_command = attempt.get("command") == []
        if (
            not internal_runner_empty_command
            and attempt.get("command") != expected_command
        ):
            raise VerificationError(
                f"attempt {spec['schedule_index']} command differs from fixed argv"
            )
        if not isinstance(attempt.get("attempt_integrity_valid"), bool):
            raise VerificationError(
                f"attempt {spec['schedule_index']} lacks a Boolean integrity flag"
            )
        if isinstance(attempt.get("command_exit_code"), bool) or not isinstance(
            attempt.get("command_exit_code"), int
        ):
            raise VerificationError(
                f"attempt {spec['schedule_index']} exit code is not an integer"
            )
        if not isinstance(attempt.get("timed_out"), bool):
            raise VerificationError(
                f"attempt {spec['schedule_index']} timed_out is not Boolean"
            )
        for key in ("episode_exists", "error_exists"):
            if not isinstance(attempt.get(key), bool):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} {key} is not Boolean"
                )
        start_ns = attempt.get("started_monotonic_ns")
        end_ns = attempt.get("ended_monotonic_ns")
        if (
            isinstance(start_ns, bool)
            or not isinstance(start_ns, int)
            or isinstance(end_ns, bool)
            or not isinstance(end_ns, int)
            or start_ns < 0
            or end_ns < start_ns
        ):
            raise VerificationError(
                f"attempt {spec['schedule_index']} has invalid monotonic window"
            )
        if previous_end_ns is not None and start_ns < previous_end_ns:
            raise VerificationError(
                f"attempt {spec['schedule_index']} overlaps or reorders the prior cell"
            )
        previous_end_ns = end_ns
        for key in (
            "started_monotonic_ns",
            "ended_monotonic_ns",
            "command_exit_code",
            "timed_out",
        ):
            if window.get(key) != attempt.get(key):
                raise VerificationError(
                    f"episode window {spec['schedule_index']} differs on {key}"
                )
        wall_seconds = attempt.get("wall_seconds")
        if (
            isinstance(wall_seconds, bool)
            or not isinstance(wall_seconds, (int, float))
            or not math.isfinite(float(wall_seconds))
            or float(wall_seconds) < 0.0
            or abs(float(wall_seconds) - (end_ns - start_ns) / 1e9) > 1e-6
        ):
            raise VerificationError(
                f"attempt {spec['schedule_index']} wall time differs from raw window"
            )
        for key in ("stdout_path", "stderr_path"):
            relative = _safe_relative_path(attempt[key], name=key)
            expected_paths.add(relative)
            path = output_root / relative
            if not path.is_file() or file_sha256(path) != attempt.get(
                f"{key[:-5]}_sha256"
            ):
                raise VerificationError(f"attempt log hash mismatch: {relative}")

        episode_relative = _safe_relative_path(
            attempt["episode_path"], name="episode_path"
        )
        error_relative = _safe_relative_path(attempt["error_path"], name="error_path")
        episode_exists = attempt.get("episode_exists") is True
        error_exists = attempt.get("error_exists") is True
        episode_parse_error: str | None = None
        if episode_exists:
            expected_paths.add(episode_relative)
            episode_path = output_root / episode_relative
            if not episode_path.is_file():
                raise VerificationError(
                    f"declared episode is missing: {episode_relative}"
                )
            if file_sha256(episode_path) != attempt.get("episode_sha256"):
                raise VerificationError(f"episode hash mismatch: {episode_relative}")
            try:
                payload = read_json_object(episode_path)
            except VerificationError as exc:
                episode_parse_error = f"{type(exc).__name__}: {exc}"
                row = _failed_episode_row(
                    spec,
                    f"episode JSON malformed but retained: {episode_parse_error}",
                )
                provisional_row = _failed_episode_row(
                    spec,
                    f"episode JSON malformed but retained: {episode_parse_error}",
                )
            else:
                provisional_row = derive_episode_row(
                    payload,
                    spec,
                    authenticated_go_receipt_hashes=None,
                )
                row = derive_episode_row(
                    payload,
                    spec,
                    authenticated_go_receipt_hashes=(authenticated_go_receipt_hashes),
                )
        else:
            if attempt.get("episode_sha256") is not None:
                raise VerificationError(
                    f"missing episode {spec['schedule_index']} has a declared hash"
                )
            row = _failed_episode_row(
                spec, "episode JSON missing from retained attempt"
            )
            provisional_row = _failed_episode_row(
                spec, "episode JSON missing from retained attempt"
            )
        if attempt.get("command_exit_code") != 0:
            row["structural_valid"] = False
            row["validation_errors"] = [
                *row.get("validation_errors", []),
                f"episode command exit code {attempt.get('command_exit_code')}",
            ]
        if attempt.get("timed_out") is True:
            row["structural_valid"] = False
            row["validation_errors"] = [
                *row.get("validation_errors", []),
                "episode timed out",
            ]
        if error_exists:
            expected_paths.add(error_relative)
            error_path = output_root / error_relative
            if not error_path.is_file() or file_sha256(error_path) != attempt.get(
                "error_sha256"
            ):
                raise VerificationError(f"error artifact mismatch: {error_relative}")
            error_payload = read_json_object(error_path)
            if (
                error_payload.get("schema_version")
                != "look-twice.v8-contract-progress-challenge-attempt-error/v1"
                or error_payload.get("schedule_index") != spec["schedule_index"]
                or error_payload.get("seed") != spec["seed"]
                or error_payload.get("arm") != spec["arm"]
                or error_payload.get("policy") != spec["policy"]
                or error_payload.get("retry_permitted") is not False
            ):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} error artifact is misbound"
                )
            if not internal_runner_empty_command and (
                error_payload.get("command_exit_code")
                != attempt.get("command_exit_code")
                or error_payload.get("timed_out") != attempt.get("timed_out")
            ):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} error outcome is misbound"
                )
            expected_runner_errors = (
                []
                if episode_parse_error is not None or not episode_exists
                else list(provisional_row.get("validation_errors", []))
            )
            if not internal_runner_empty_command and (
                error_payload.get("parse_error") != episode_parse_error
                or error_payload.get("episode_validation_errors")
                != expected_runner_errors
            ):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} error details differ from "
                    "the independently reconstructed runner result"
                )
            if internal_runner_empty_command and not (
                attempt.get("attempt_integrity_valid") is False
                and attempt.get("command_exit_code") == 127
                and isinstance(error_payload.get("internal_runner_error"), str)
                and bool(error_payload.get("internal_runner_error"))
            ):
                raise VerificationError(
                    f"attempt {spec['schedule_index']} empty argv is not a retained "
                    "internal-runner failure"
                )
        elif (output_root / error_relative).exists():
            raise VerificationError(
                f"undeclared error artifact exists: {error_relative}"
            )
        elif attempt.get("error_sha256") is not None:
            raise VerificationError(
                f"attempt {spec['schedule_index']} declares a hash for no error file"
            )
        elif episode_parse_error is not None:
            raise VerificationError(
                f"attempt {spec['schedule_index']} malformed episode lacks a "
                "retained error artifact"
            )
        elif internal_runner_empty_command:
            raise VerificationError(
                f"attempt {spec['schedule_index']} has empty argv without an error artifact"
            )
        provisional_integrity = bool(
            attempt.get("command_exit_code") == 0
            and attempt.get("timed_out") is False
            and episode_exists
            and not error_exists
            and provisional_row["structural_valid"]
        )
        recorded_integrity = attempt.get("attempt_integrity_valid")
        if recorded_integrity is not provisional_integrity:
            raise VerificationError(
                f"attempt {spec['schedule_index']} integrity flag differs from "
                "the independently reconstructed runner-provisional result"
            )
        verified_integrity = bool(
            attempt.get("command_exit_code") == 0
            and attempt.get("timed_out") is False
            and episode_exists
            and not error_exists
            and row["structural_valid"]
        )
        if not provisional_integrity and verified_integrity:
            raise VerificationError(
                f"attempt {spec['schedule_index']} cannot be independently "
                "promoted above its runner-provisional result"
            )
        row["attempt_integrity_provisional_downgraded"] = bool(
            provisional_integrity and not verified_integrity
        )
        if row["attempt_integrity_provisional_downgraded"]:
            row["validation_errors"] = [
                *row.get("validation_errors", []),
                "independent verifier downgraded runner provisional integrity",
            ]
        if error_exists:
            row["structural_valid"] = False
            row["validation_errors"] = [
                *row.get("validation_errors", []),
                "retained attempt error artifact exists",
            ]
        rows.append(row)

    expected_accounting = {
        "expected": EPISODE_COUNT,
        "attempted": len(attempts),
        "valid": sum(bool(row.get("attempt_integrity_valid")) for row in attempts),
        "timed_out": sum(bool(row.get("timed_out")) for row in attempts),
        "retry_count": 0,
        "seed_substitutions": 0,
        "early_stopped": len(attempts) != EPISODE_COUNT,
    }
    if manifest.get("attempt_accounting") != expected_accounting:
        raise VerificationError("RUN_MANIFEST attempt accounting is not raw-derived")
    source_roots = manifest.get("source_roots")
    if not isinstance(source_roots, Mapping) or not all(
        isinstance(source_roots.get(arm), str) and source_roots.get(arm)
        for arm in ("baseline", "candidate")
    ):
        raise VerificationError("RUN_MANIFEST source roots are missing")
    if source_roots.get("baseline") == source_roots.get("candidate"):
        raise VerificationError("RUN_MANIFEST source roots are not isolated")
    expected_runtime = {
        "runtime": "genesis-amd",
        "motion_backend": "kinematic",
        "device": "cuda:0",
        "profile": PROFILE,
        "seed_range": [SEED_START, SEED_END],
        "episode_timeout_seconds": EPISODE_TIMEOUT_SECONDS,
    }
    if manifest.get("fixed_runtime") != expected_runtime:
        raise VerificationError("RUN_MANIFEST fixed runtime contract changed")
    return rows, expected_paths, attempts, windows


def _parse_checksum_index(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines != sorted(lines, key=lambda line: line.split("  ", 1)[-1]):
        raise VerificationError("SHA256SUMS is not path-sorted")
    for number, line in enumerate(lines, 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or not SHA256_RE.fullmatch(parts[0]):
            raise VerificationError(f"invalid SHA256SUMS line {number}")
        relative = _safe_relative_path(parts[1], name="checksum path")
        if relative in result:
            raise VerificationError(f"duplicate checksum path: {relative}")
        result[relative] = parts[0]
    return result


def _required_monotonic_ns(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationError(f"{name} must be a non-negative integer")
    return value


def _required_aware_datetime(value: Any, *, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(f"{name} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise VerificationError(f"{name} is not timezone-aware")
    return parsed


def _telemetry_numeric(value: Any, *, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"{name} must be finite numeric or null")
    number = float(value)
    if not math.isfinite(number):
        raise VerificationError(f"{name} must be finite numeric or null")
    return number


def _parse_recorded_kfd_pids(text: str) -> list[int]:
    pids: set[int] = set()
    for line in text.splitlines():
        match = re.match(r"^\s*([1-9][0-9]*)\s+", line)
        if match:
            pids.add(int(match.group(1)))
        for explicit in re.finditer(
            r"(?:\"?PID\"?\s*[:=]\s*)([1-9][0-9]*)",
            line,
            flags=re.IGNORECASE,
        ):
            pids.add(int(explicit.group(1)))
    return sorted(pids)


def validate_raw_telemetry(
    output_root: Path,
    telemetry: Mapping[str, Any],
    windows: Sequence[Mapping[str, Any]],
    prestart: Mapping[str, Any],
) -> dict[str, Any]:
    samples = _read_jsonl(output_root / "raw" / "ROCM_SAMPLES.jsonl")
    if len(samples) < 2:
        raise VerificationError("raw ROCm telemetry must contain at least two samples")
    times = [
        _required_monotonic_ns(
            row.get("captured_monotonic_ns"),
            name=f"ROCM_SAMPLES[{index}].captured_monotonic_ns",
        )
        for index, row in enumerate(samples)
    ]
    if any(current <= previous for previous, current in zip(times, times[1:])):
        raise VerificationError(
            "raw ROCm sample timestamps are not strictly increasing"
        )
    if any(row.get("command_exit_code") != 0 for row in samples):
        raise VerificationError("one or more raw ROCm samples report command failure")

    challenge_start = _required_monotonic_ns(
        telemetry.get("challenge_started_monotonic_ns"),
        name="ROCM_TELEMETRY.challenge_started_monotonic_ns",
    )
    challenge_end = _required_monotonic_ns(
        telemetry.get("challenge_ended_monotonic_ns"),
        name="ROCM_TELEMETRY.challenge_ended_monotonic_ns",
    )
    if challenge_end < challenge_start:
        raise VerificationError("ROCm challenge end precedes challenge start")
    if not windows:
        raise VerificationError("cannot validate telemetry without episode windows")
    first_attempt_start = _required_monotonic_ns(
        windows[0].get("started_monotonic_ns"), name="first attempt start"
    )
    last_attempt_end = _required_monotonic_ns(
        windows[-1].get("ended_monotonic_ns"), name="last attempt end"
    )
    if challenge_start > first_attempt_start or challenge_end < last_attempt_end:
        raise VerificationError(
            "challenge telemetry window does not contain all attempts"
        )
    if times[0] > challenge_start or times[-1] < challenge_end:
        raise VerificationError("raw ROCm samples do not cover challenge start and end")
    gaps = [(current - previous) / 1e9 for previous, current in zip(times, times[1:])]
    max_gap = max(gaps)
    if max_gap > 5.5:
        raise VerificationError(
            f"raw ROCm sampling gap exceeds 5.5 seconds: {max_gap:.9f}"
        )

    if telemetry.get("schema_version") != (
        "look-twice.v8-contract-progress-challenge-rocm-telemetry/v1"
    ):
        raise VerificationError("unexpected ROCM_TELEMETRY schema")
    if telemetry.get("sample_interval_seconds") != 2.0:
        raise VerificationError("ROCm sample interval contract changed")
    if telemetry.get("max_allowed_gap_seconds") != 5.5:
        raise VerificationError("ROCm maximum-gap contract changed")
    if telemetry.get("sample_count") != len(samples):
        raise VerificationError("ROCm sample_count differs from raw samples")
    if telemetry.get("sampler_errors") != []:
        raise VerificationError("ROCm sampler retained one or more errors")
    if telemetry.get("coverage_valid") is not True:
        raise VerificationError("runner ROCm coverage flag is not true")
    observed_reported_gap = _telemetry_numeric(
        telemetry.get("max_observed_gap_seconds"),
        name="ROCM_TELEMETRY.max_observed_gap_seconds",
    )
    if observed_reported_gap is None or not math.isclose(
        observed_reported_gap, max_gap, rel_tol=0.0, abs_tol=1e-12
    ):
        raise VerificationError("reported ROCm maximum gap differs from raw samples")

    first_preflight = _nested(prestart, "clean_gpu_preflight", "first_telemetry_sample")
    if first_preflight != samples[0]:
        raise VerificationError("prestart GPU sample differs from first raw sample")
    gpu_preflight = prestart.get("clean_gpu_preflight")
    if not isinstance(gpu_preflight, Mapping):
        raise VerificationError("prestart clean GPU proof is missing")
    showpids_stdout = gpu_preflight.get("showpids_stdout")
    reported_pids = gpu_preflight.get("reported_kfd_pids")
    stale_pids = gpu_preflight.get("stale_kfd_pids")
    if (
        gpu_preflight.get("showpids_exit_code") != 0
        or not isinstance(showpids_stdout, str)
        or not isinstance(gpu_preflight.get("showpids_stderr"), str)
        or reported_pids != _parse_recorded_kfd_pids(showpids_stdout)
        or gpu_preflight.get("live_kfd_pids") != []
        or stale_pids != reported_pids
        or gpu_preflight.get("no_live_kfd_processes") is not True
        or gpu_preflight.get("open_kfd_fds") != []
        or gpu_preflight.get("global_dev_kfd_fd_scan_clear") is not True
        or gpu_preflight.get("first_telemetry_idle") is not True
        or gpu_preflight.get("idle_thresholds")
        != {
            "gpu_use_percent_max": 5.0,
            "vram_allocated_percent_max": 2.0,
        }
    ):
        raise VerificationError("prestart live/stale KFD and idle proof is invalid")
    first_gpu_use = _telemetry_numeric(
        first_preflight.get("gpu_use_percent"),
        name="prestart first GPU use",
    )
    first_vram_use = _telemetry_numeric(
        first_preflight.get("vram_allocated_percent"),
        name="prestart first VRAM use",
    )
    if (
        first_gpu_use is None
        or first_gpu_use > 5.0
        or first_vram_use is None
        or first_vram_use > 2.0
    ):
        raise VerificationError("prestart first telemetry sample is not idle")

    fields = (
        "gpu_use_percent",
        "vram_allocated_percent",
        "memory_activity_percent",
        "graphics_package_power_w",
        "temperature_edge_c",
        "temperature_junction_c",
        "temperature_memory_c",
    )
    expected_summary: dict[str, Any] = {"sample_count": len(samples)}
    for field in fields:
        values = [
            number
            for index, row in enumerate(samples)
            if (
                number := _telemetry_numeric(
                    row.get(field), name=f"ROCM_SAMPLES[{index}].{field}"
                )
            )
            is not None
        ]
        expected_summary[field] = (
            {
                "mean": statistics.fmean(values),
                "minimum": min(values),
                "maximum": max(values),
                "median": statistics.median(values),
                "samples": len(values),
            }
            if values
            else None
        )
    if telemetry.get("summary") != expected_summary:
        raise VerificationError("ROCm summary differs from raw-sample recomputation")
    return {
        "sample_count": len(samples),
        "first_sample_monotonic_ns": times[0],
        "last_sample_monotonic_ns": times[-1],
        "max_observed_gap_seconds": max_gap,
        "challenge_window_contains_all_attempts": True,
        "raw_samples_cover_challenge_window": True,
        "strictly_increasing_timestamps": True,
        "summary_recomputed": True,
    }


def _git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        env=_safe_git_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"postrun Git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _public_github_url(remote_url: str) -> tuple[str, str]:
    value = remote_url.strip()
    relative: str | None = None
    if value.startswith("git@github.com:"):
        relative = value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        relative = value.removeprefix("ssh://git@github.com/")
    elif value.startswith("https://github.com/"):
        relative = value.removeprefix("https://github.com/")
    if relative is None:
        raise VerificationError("postrun Git remote is not public GitHub")
    relative = relative.removesuffix(".git").strip("/")
    parts = relative.split("/")
    if len(parts) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts
    ):
        raise VerificationError("postrun GitHub repository slug is malformed")
    slug = "/".join(parts)
    return f"https://github.com/{slug}.git", slug


def _verify_current_git_snapshot(
    candidate_root: Path, expected: Mapping[str, Any]
) -> None:
    head = _git_output(candidate_root, "rev-parse", "HEAD")
    if head != expected.get("commit_b_observed_clean_head"):
        raise VerificationError("candidate HEAD changed after postrun binding")
    if _git_output(
        candidate_root,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ):
        raise VerificationError("candidate checkout is not clean at verification")
    commit_a = str(expected.get("commit_a") or "")
    if (
        _git_output(candidate_root, "rev-parse", f"{head}^") != commit_a
        or _git_output(candidate_root, "rev-list", "--count", f"{commit_a}..{head}")
        != "1"
        or _git_output(
            candidate_root, "diff", "--name-only", f"{commit_a}..{head}"
        ).splitlines()
        != expected.get("commit_a_to_b_changed_paths")
    ):
        raise VerificationError("candidate two-commit relationship changed")
    remote_name = str(expected.get("public_remote_name") or "")
    public_url, slug = _public_github_url(
        _git_output(candidate_root, "remote", "get-url", remote_name)
    )
    if slug != expected.get("public_github_repository"):
        raise VerificationError("candidate public GitHub repository changed")
    environment = _safe_git_environment()
    environment.update({"GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"})
    remote = subprocess.run(
        ["git", "-c", "credential.helper=", "ls-remote", "--heads", public_url],
        cwd=candidate_root.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if remote.returncode != 0:
        raise VerificationError(
            f"anonymous postrun public remote check failed: {remote.stderr.strip()}"
        )
    live_refs = {
        fields[1]
        for line in remote.stdout.splitlines()
        if len(fields := line.split()) == 2 and fields[0] == head
    }
    recorded_refs = expected.get("public_remote_head_refs")
    if (
        not isinstance(recorded_refs, list)
        or not recorded_refs
        or not set(recorded_refs) <= live_refs
    ):
        raise VerificationError("recorded Commit B public branch head moved")


def _verify_current_baseline_closure(root: Path, closure: Mapping[str, Any]) -> None:
    rows = closure.get("files")
    if not isinstance(rows, list):
        raise VerificationError("postrun baseline closure files are missing")
    declared: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise VerificationError("postrun baseline closure row is malformed")
        relative = str(row.get("path") or "")
        digest = str(row.get("sha256") or "")
        if relative in declared or not SHA256_RE.fullmatch(digest):
            raise VerificationError("postrun baseline closure row is invalid")
        declared[relative] = digest
        path = root / relative
        if path.is_symlink() or not path.is_file() or file_sha256(path) != digest:
            raise VerificationError(f"current baseline closure changed: {relative}")
    source_root = root / "src"
    actual: set[str] = set()
    for path in source_root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise VerificationError(f"current baseline src contains symlink: {path}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise VerificationError(f"current baseline src contains non-file: {path}")
        actual.add(path.relative_to(root).as_posix())
    declared_src = {path for path in declared if path.startswith("src/")}
    if actual != declared_src:
        raise VerificationError(
            "current baseline exact src closure changed: "
            f"missing={sorted(declared_src - actual)} extra={sorted(actual - declared_src)}"
        )


def validate_postrun_binding(
    output_root: Path,
    prereg: Mapping[str, Any],
    prestart: Mapping[str, Any],
    manifest: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
) -> bool:
    path = output_root / "raw" / "POSTRUN_BINDING.json"
    postrun = read_json_object(path)
    if postrun.get("schema_version") != POSTRUN_SCHEMA:
        raise VerificationError("unexpected POSTRUN_BINDING schema")
    if manifest.get("postrun_binding_sha256") != file_sha256(path) or manifest.get(
        "postrun_revalidation_passed"
    ) is not postrun.get("revalidation_passed"):
        raise VerificationError("RUN_MANIFEST postrun binding fields differ")
    if postrun.get("attempts_completed") != EPISODE_COUNT or not attempts:
        raise VerificationError("postrun binding does not follow all 40 attempts")
    last_end_ns = _required_monotonic_ns(
        attempts[-1].get("ended_monotonic_ns"), name="last attempt end"
    )
    checked_ns = _required_monotonic_ns(
        postrun.get("checked_monotonic_ns_after_all_attempts"),
        name="postrun check monotonic timestamp",
    )
    if (
        postrun.get("last_attempt_ended_monotonic_ns") != last_end_ns
        or checked_ns < last_end_ns
    ):
        raise VerificationError("postrun monotonic chronology is invalid")
    checked_at = _required_aware_datetime(
        postrun.get("checked_at_utc_after_all_attempts"),
        name="postrun check UTC timestamp",
    )
    last_ended_at = _required_aware_datetime(
        attempts[-1].get("ended_at_utc"), name="last attempt end UTC timestamp"
    )
    if checked_at < last_ended_at:
        raise VerificationError("postrun wall-clock check precedes last attempt")

    pre_snapshot = prestart.get("immutable_binding")
    if not isinstance(pre_snapshot, Mapping):
        raise VerificationError("prestart immutable binding is missing")
    pre_hash = canonical_json_sha256(pre_snapshot)
    if (
        prestart.get("immutable_binding_sha256") != pre_hash
        or postrun.get("prestart_immutable_binding_sha256") != pre_hash
    ):
        raise VerificationError("prestart immutable binding hash changed")
    passed = postrun.get("revalidation_passed") is True
    if not passed:
        if (
            postrun.get("prestart_equals_postrun") is not False
            or not isinstance(postrun.get("validation_error"), str)
            or not postrun.get("validation_error")
        ):
            raise VerificationError(
                "failed postrun binding lacks retained failure proof"
            )
        return False

    post_snapshot = postrun.get("immutable_binding")
    if (
        not isinstance(post_snapshot, Mapping)
        or post_snapshot != pre_snapshot
        or postrun.get("prestart_equals_postrun") is not True
        or postrun.get("validation_error") is not None
        or postrun.get("postrun_immutable_binding_sha256") != pre_hash
    ):
        raise VerificationError("successful postrun binding differs from prestart")
    paths = post_snapshot.get("paths")
    files = post_snapshot.get("files")
    git_snapshot = post_snapshot.get("git")
    if not all(isinstance(value, Mapping) for value in (paths, files, git_snapshot)):
        raise VerificationError("postrun immutable snapshot sections are missing")
    baseline_root = Path(str(paths.get("baseline_root") or ""))
    candidate_root = Path(str(paths.get("candidate_root") or ""))
    if (
        not baseline_root.is_absolute()
        or not candidate_root.is_absolute()
        or output_root == baseline_root
        or baseline_root in output_root.parents
        or output_root == candidate_root
        or candidate_root in output_root.parents
    ):
        raise VerificationError("formal output/source root isolation changed")
    for name in (
        "checkpoint",
        "vision_artifact",
        "go_artifact",
        "purify_binary",
        "identity_manifest",
    ):
        observation = files.get(name)
        if not isinstance(observation, Mapping):
            raise VerificationError(f"postrun {name} observation is missing")
        current = Path(str(observation.get("path") or ""))
        if (
            not current.is_absolute()
            or current.is_symlink()
            or not current.is_file()
            or file_sha256(current) != observation.get("sha256")
        ):
            raise VerificationError(f"current frozen artifact changed: {name}")
    _verify_current_baseline_closure(
        baseline_root, post_snapshot["baseline_runtime_closure"]
    )
    identities = prereg["identities"]
    current_candidate = verify_candidate_source_closure(
        candidate_root,
        expected_file_count=int(identities["candidate_tracked_src_file_count"]),
        expected_tree_sha256=str(
            identities["candidate_tracked_src_tree_fingerprint_sha256"]
        ),
    )
    if current_candidate != post_snapshot.get("candidate_source_closure"):
        raise VerificationError("current candidate exact src closure changed")
    _verify_current_git_snapshot(candidate_root, git_snapshot)
    python_identity = post_snapshot.get("python_identity")
    if not isinstance(python_identity, Mapping):
        raise VerificationError("postrun Python identity is missing")
    invocation = Path(str(python_identity.get("invocation_path") or ""))
    target = invocation.resolve()
    if (
        str(invocation) != paths.get("python_executable")
        or str(target) != python_identity.get("resolved_target_path")
        or not target.is_file()
        or file_sha256(target) != python_identity.get("resolved_target_sha256")
    ):
        raise VerificationError("formal Python launcher/target identity changed")
    version = subprocess.run(
        [str(invocation), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if version.returncode != 0 or (
        version.stdout or version.stderr
    ).strip() != python_identity.get("version"):
        raise VerificationError("formal Python version identity changed")
    return True


def verify_output(
    output_root: Path,
    preregistration_path: Path,
    *,
    runner_path: Path,
    verifier_path: Path,
    stage: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not output_root.is_dir():
        raise VerificationError(f"output root not found: {output_root}")
    prereg = read_json_object(preregistration_path)
    prereg_obs = validate_preregistration(
        prereg,
        runner_sha256=file_sha256(runner_path),
        verifier_sha256=file_sha256(verifier_path),
        formal=True,
    )
    prestart = read_json_object(output_root / "raw" / "PRESTART_BINDING.json")
    if prestart.get("schema_version") != PRESTART_SCHEMA:
        raise VerificationError("unexpected PRESTART_BINDING schema")
    authenticated_go_receipt_hashes = authenticate_output_go_receipts(
        output_root, prestart
    )
    manifest_path = output_root / "RUN_MANIFEST.json"
    manifest = read_json_object(manifest_path)
    rows, expected_paths, attempts, windows = validate_manifest_and_load_rows(
        output_root,
        manifest,
        prestart,
        authenticated_go_receipt_hashes,
    )
    if manifest.get("preregistration_sha256") != file_sha256(preregistration_path):
        raise VerificationError("RUN_MANIFEST preregistration hash mismatch")
    if manifest.get("runner_sha256") != file_sha256(runner_path):
        raise VerificationError("RUN_MANIFEST runner hash mismatch")
    if manifest.get("verifier_sha256") != file_sha256(verifier_path):
        raise VerificationError("RUN_MANIFEST verifier hash mismatch")
    if prestart.get("fixed_schedule") != build_schedule():
        raise VerificationError("prestart schedule mismatch")
    if prestart.get("schedule_sha256") != schedule_sha256():
        raise VerificationError("prestart schedule hash mismatch")
    if prestart.get("preregistration_sha256") != file_sha256(preregistration_path):
        raise VerificationError("prestart preregistration hash mismatch")
    if prestart.get("runner_sha256") != file_sha256(runner_path):
        raise VerificationError("prestart runner hash mismatch")
    if prestart.get("verifier_sha256") != file_sha256(verifier_path):
        raise VerificationError("prestart verifier hash mismatch")
    if prestart.get("baseline_root") == prestart.get("candidate_root"):
        raise VerificationError("baseline and candidate roots were not separated")
    if prestart.get("baseline_root") != _nested(manifest, "source_roots", "baseline"):
        raise VerificationError("prestart/manifest baseline roots differ")
    if prestart.get("candidate_root") != _nested(manifest, "source_roots", "candidate"):
        raise VerificationError("prestart/manifest candidate roots differ")
    if prestart.get("fresh_seed_opened_before_prestart") is not False:
        raise VerificationError("fresh seed chronology declaration is invalid")
    if prestart.get("no_episode_had_started") is not True:
        raise VerificationError("prestart does not declare zero started episodes")
    bound_ns = _required_monotonic_ns(
        prestart.get("bound_monotonic_ns_before_first_episode"),
        name="prestart binding monotonic timestamp",
    )
    first_attempt_ns = _required_monotonic_ns(
        attempts[0].get("started_monotonic_ns"), name="first attempt start"
    )
    if bound_ns > first_attempt_ns:
        raise VerificationError("prestart binding was recorded after the first attempt")
    bound_at = _required_aware_datetime(
        prestart.get("bound_at_utc_before_first_episode"),
        name="prestart binding UTC timestamp",
    )
    binding = prereg["public_binding"]
    if prestart.get("commit_a") != binding.get("commit_a"):
        raise VerificationError("prestart Commit A differs from preregistration")
    commit_b = str(prestart.get("commit_b_observed") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit_b) or commit_b == binding.get(
        "commit_a"
    ):
        raise VerificationError("prestart Commit B proof is malformed")
    git_two_commit_proof = prestart.get("git_two_commit_proof")
    if git_two_commit_proof != {
        "candidate_checkout_clean": True,
        "commit_a_strict_ancestor": True,
        "commit_b_direct_parent_is_commit_a": True,
        "commit_count_a_to_b": 1,
        "changed_paths_a_to_b": [binding.get("commit_b_diff_from_a_may_only_change")],
    }:
        raise VerificationError("prestart two-commit Git proof is incomplete")
    remote_proof = prestart.get("public_remote_proof")
    if not isinstance(remote_proof, Mapping):
        raise VerificationError("prestart public remote proof is missing")
    if remote_proof.get("remote_name") != binding.get("remote_name"):
        raise VerificationError("prestart public remote name changed")
    github_repository = remote_proof.get("github_repository")
    if not isinstance(github_repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github_repository
    ):
        raise VerificationError("prestart public GitHub repository is malformed")
    if remote_proof.get("access") != "anonymous_https_no_credential_helper":
        raise VerificationError("prestart does not record anonymous public access")
    if remote_proof.get("remote_head_commit") != commit_b:
        raise VerificationError("prestart public remote head does not equal Commit B")
    remote_refs = remote_proof.get("remote_head_refs")
    if (
        not isinstance(remote_refs, list)
        or not remote_refs
        or remote_refs != sorted(set(remote_refs))
        or any(
            not isinstance(ref, str) or not ref.startswith("refs/heads/")
            for ref in remote_refs
        )
    ):
        raise VerificationError("prestart public remote-head refs are malformed")
    if remote_proof.get("commit_b_public_remote_head_verified") is not True:
        raise VerificationError("prestart does not prove Commit B was public")
    prereg_created_at = _required_aware_datetime(
        prereg.get("created_utc"), name="preregistration creation UTC timestamp"
    )
    remote_checked_at = _required_aware_datetime(
        remote_proof.get("checked_at_utc"), name="public remote check UTC timestamp"
    )
    if not prereg_created_at <= remote_checked_at <= bound_at:
        raise VerificationError(
            "public preregistration/remote/prestart wall-clock chronology is invalid"
        )

    frozen_identities = prestart.get("frozen_identities")
    if frozen_identities != {
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "vision_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
        "go_artifact_sha256": EXPECTED_GO_ARTIFACT_SHA256,
        "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
        "baseline_runtime_tree_sha256": EXPECTED_RUNTIME_TREE_SHA256,
    }:
        raise VerificationError("prestart frozen identities changed")
    baseline_closure = prestart.get("baseline_runtime_closure")
    if not isinstance(baseline_closure, Mapping):
        raise VerificationError("prestart baseline runtime closure is missing")
    closure_files = baseline_closure.get("files")
    if not isinstance(closure_files, list) or len(closure_files) != 30:
        raise VerificationError("prestart baseline runtime closure file set changed")
    closure_observed: dict[str, str] = {}
    closure_paths: set[str] = set()
    for row in closure_files:
        if not isinstance(row, Mapping):
            raise VerificationError(
                "prestart baseline runtime closure row is malformed"
            )
        relative = str(row.get("path") or "")
        digest = str(row.get("sha256") or "")
        if not relative or relative in closure_paths or not SHA256_RE.fullmatch(digest):
            raise VerificationError("prestart baseline runtime closure row is invalid")
        closure_paths.add(relative)
        closure_observed[relative] = digest
    closure_fingerprint = hashlib.sha256(
        "".join(
            f"{closure_observed[path]}  {path}\n" for path in sorted(closure_observed)
        ).encode("utf-8")
    ).hexdigest()
    if (
        closure_fingerprint != EXPECTED_RUNTIME_TREE_SHA256
        or baseline_closure.get("tree_fingerprint_sha256")
        != EXPECTED_RUNTIME_TREE_SHA256
        or baseline_closure.get("file_count") != 30
        or baseline_closure.get("python_file_count") != 29
        or baseline_closure.get("exact_python_file_set_verified") is not True
        or baseline_closure.get("exact_src_file_set_verified") is not True
        or baseline_closure.get("source_origin_git_commit")
        != "aadd429d2da9de690a361218c40c9dfb22b04eb2"
        or _nested(baseline_closure, "manifest", "sha256")
        != EXPECTED_RUNTIME_MANIFEST_SHA256
    ):
        raise VerificationError("prestart baseline runtime closure proof is invalid")
    prestart_sources = prestart.get("candidate_source_files")
    if not isinstance(prestart_sources, list) or len(prestart_sources) != len(
        prereg_obs["candidate_source_files"]
    ):
        raise VerificationError("prestart candidate source observations are incomplete")
    for declared, observed in zip(
        prereg_obs["candidate_source_files"], prestart_sources
    ):
        if (
            not isinstance(observed, Mapping)
            or observed.get("path") != declared.get("path")
            or observed.get("sha256_declared") != declared.get("sha256_declared")
            or observed.get("sha256_observed") != declared.get("sha256_declared")
        ):
            raise VerificationError("prestart candidate source binding mismatch")

    prestart_candidate_closure = prestart.get("candidate_source_closure")
    if not isinstance(prestart_candidate_closure, Mapping):
        raise VerificationError("prestart full candidate source closure is missing")
    closure_rows = prestart_candidate_closure.get("files")
    if not isinstance(closure_rows, list):
        raise VerificationError("prestart candidate closure files are missing")
    closure_digests: dict[str, str] = {}
    for row in closure_rows:
        if not isinstance(row, Mapping):
            raise VerificationError("prestart candidate closure row is malformed")
        relative = str(row.get("path") or "")
        digest = str(row.get("sha256") or "")
        if (
            not relative.startswith("src/")
            or relative in closure_digests
            or not SHA256_RE.fullmatch(digest)
        ):
            raise VerificationError("prestart candidate closure row is invalid")
        closure_digests[relative] = digest
    candidate_fingerprint = hashlib.sha256(
        "".join(
            f"{closure_digests[relative]}  {relative}\n"
            for relative in sorted(closure_digests)
        ).encode("utf-8")
    ).hexdigest()
    if (
        prestart_candidate_closure.get("tree_fingerprint_algorithm")
        != CANDIDATE_SOURCE_TREE_ALGORITHM
        or prestart_candidate_closure.get("tree_fingerprint_sha256")
        != candidate_fingerprint
        or prestart_candidate_closure.get("tracked_file_count") != len(closure_rows)
        or len(closure_rows) != prereg["identities"]["candidate_tracked_src_file_count"]
        or candidate_fingerprint
        != prereg["identities"]["candidate_tracked_src_tree_fingerprint_sha256"]
        or prestart_candidate_closure.get("exact_git_tracked_file_set_verified")
        is not True
        or prestart_candidate_closure.get("untracked_and_ignored_files_absent")
        is not True
        or prestart_candidate_closure.get("symlinks_and_nonregular_paths_absent")
        is not True
    ):
        raise VerificationError("prestart candidate full closure proof is invalid")

    postrun_binding_valid = validate_postrun_binding(
        output_root, prereg, prestart, manifest, attempts
    )

    telemetry = read_json_object(output_root / "ROCM_TELEMETRY.json")
    telemetry_observation = validate_raw_telemetry(
        output_root,
        telemetry,
        windows,
        prestart,
    )
    telemetry_valid = True

    report = derive_report(
        rows,
        preregistration_sha256=file_sha256(preregistration_path),
        run_manifest_sha256=file_sha256(manifest_path),
        postrun_binding_valid=postrun_binding_valid,
    )
    actual_paths = _walk_relative_files(output_root)
    if stage in {"report", "checksum", "final"}:
        expected_paths.add("REPORT.json")
    if stage in {"checksum", "final"}:
        expected_paths.add("SHA256SUMS")
    if stage == "final":
        expected_paths.add("VERIFICATION.json")
    if actual_paths != expected_paths:
        raise VerificationError(
            "exact output path set mismatch: "
            f"missing={sorted(expected_paths - actual_paths)} "
            f"extra={sorted(actual_paths - expected_paths)}"
        )

    checksum_valid = None
    if stage in {"checksum", "final"}:
        declared = _parse_checksum_index(output_root / "SHA256SUMS")
        required = actual_paths - {"SHA256SUMS", "VERIFICATION.json"}
        if set(declared) != required:
            raise VerificationError(
                "checksum path set mismatch: "
                f"missing={sorted(required - set(declared))} "
                f"extra={sorted(set(declared) - required)}"
            )
        for relative, expected_sha in declared.items():
            if file_sha256(output_root / relative) != expected_sha:
                raise VerificationError(f"checksum mismatch: {relative}")
        checksum_valid = True

    if stage in {"report", "checksum", "final"}:
        stored_report = read_json_object(output_root / "REPORT.json")
        if stored_report != report:
            raise VerificationError(
                "REPORT.json differs from independent recomputation"
            )

    verification = {
        "schema_version": VERIFICATION_SCHEMA,
        "verified_at_utc": utc_now(),
        "formal_result_eligible": False,
        "stage": stage,
        "preregistration": prereg_obs,
        "schedule_sha256": schedule_sha256(),
        "attempt_count": len(rows),
        "exact_path_set_valid": True,
        "telemetry_valid": telemetry_valid,
        "raw_telemetry_observation": telemetry_observation,
        "postrun_binding_valid": postrun_binding_valid,
        "checksum_valid": checksum_valid,
        "report_sha256": canonical_json_sha256(report),
        "run_manifest_file_sha256": file_sha256(manifest_path),
        "preregistration_file_sha256": file_sha256(preregistration_path),
        "mandatory_gates": report["mandatory_gates"],
        "capability_gates": report["capability_gates"],
        "promotion_pass": bool(report["promotion_pass"] and telemetry_valid),
        "structural_verification_pass": True,
    }
    if stage == "final":
        stored_verification = read_json_object(output_root / "VERIFICATION.json")
        comparable = dict(stored_verification)
        comparable.pop("verified_at_utc", None)
        expected_comparable = dict(verification)
        expected_comparable.pop("verified_at_utc", None)
        if comparable != expected_comparable:
            raise VerificationError(
                "VERIFICATION.json differs from final recomputation"
            )
    return report, verification


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument(
        "--runner",
        type=Path,
        default=Path(__file__)
        .resolve()
        .with_name("run_v8_contract_progress_challenge.py"),
    )
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--write-verification", action="store_true")
    parser.add_argument("--require-final", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    modes = sum(
        bool(value)
        for value in (args.write_report, args.write_verification, args.require_final)
    )
    if modes != 1:
        print(
            "ERROR: choose exactly one of --write-report, --write-verification, "
            "or --require-final",
            file=sys.stderr,
        )
        return 2
    output_root = args.output_root.resolve()
    prereg = args.preregistration.resolve()
    runner = args.runner.resolve()
    verifier = Path(__file__).resolve()
    try:
        if args.write_report:
            if (output_root / "REPORT.json").exists():
                raise VerificationError("REPORT.json already exists")
            report, _ = verify_output(
                output_root,
                prereg,
                runner_path=runner,
                verifier_path=verifier,
                stage="base",
            )
            exclusive_write_json(output_root / "REPORT.json", report)
            print(
                json.dumps(
                    {"report_written": True, "promotion_pass": report["promotion_pass"]}
                )
            )
            return 0
        if args.write_verification:
            if (output_root / "VERIFICATION.json").exists():
                raise VerificationError("VERIFICATION.json already exists")
            _, verification = verify_output(
                output_root,
                prereg,
                runner_path=runner,
                verifier_path=verifier,
                stage="checksum",
            )
            verification["stage"] = "final"
            exclusive_write_json(output_root / "VERIFICATION.json", verification)
            print(
                json.dumps(
                    {
                        "verification_written": True,
                        "promotion_pass": verification["promotion_pass"],
                    }
                )
            )
            return 0
        _, verification = verify_output(
            output_root,
            prereg,
            runner_path=runner,
            verifier_path=verifier,
            stage="final",
        )
        print(json.dumps(verification, indent=2, ensure_ascii=False))
        return 0
    except (OSError, VerificationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
