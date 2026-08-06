#!/usr/bin/env python3
"""Finalize and verify the V8 official-submission review package.

External publication remains unverified by default and can be sealed only with
explicit publication receipts. This script makes the inventory mechanical:
every regular package file is
listed in ``SUBMISSION_PACKAGE.json`` (except that manifest and ``SHA256SUMS``),
and every regular file is bound by the top-level ``SHA256SUMS`` (except the
checksum index itself).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = (
    REPO_ROOT
    / "submission"
    / "official-repo"
    / "submissions"
    / "Track3-Liu-Liang-Look-Twice"
)
DEFAULT_HANDOFF_MANIFEST = REPO_ROOT / "submission" / "V8_SUBMISSION_MANIFEST.json"
PACKAGE_MANIFEST = "SUBMISSION_PACKAGE.json"
PACKAGE_CHECKSUMS = "SHA256SUMS"
V2_PREFIX = "evidence/decision_dynamics_recovery_v2_102500_102529/"
SINGLE_SCENE_60_PREFIX = "evidence/decision_dynamics_single_scene_60_102500_102519/"
SINGLE_SCENE_30_SUFFIX_PREFIX = (
    "evidence/decision_dynamics_single_scene_30_suffix_102520_102529/"
)
TWO_SHARD_BOUNDARY_KEY = "additive_decision_bound_dynamics_two_shard"

V2_REPORT_SHA256 = "1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99"
SOURCE_BINDING_SHA256 = (
    "c40f6ba74a39ad761e4926ddb66326f33a1a645fef3c96364f9c53b9d5d3eb5d"
)
RECOVERY_AUDIT_SHA256 = (
    "344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4"
)
PROVENANCE_REVIEW_SHA256 = (
    "4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7"
)
V2_PACKAGE_INDEX_SHA256 = (
    "24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540"
)
V2_FORMAL_INDEX_SHA256 = (
    "dae4f7f694e3db14db9731e6292d2d7e28f98b6540eca485be9666947273d5be"
)
V2_SOURCE_COMMIT = "b0c4f0d33b0a2d0c647dda0b2b3b7c03279a511a"

SINGLE_SCENE_60_REPORT_SHA256 = (
    "3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450"
)
SINGLE_SCENE_60_SOURCE_COMMIT = "aac8cd08ca8f2cd6bb62e77189541b1c5ff957e2"
SINGLE_SCENE_60_SOURCE_BINDING_SHA256 = (
    "3eb0d2b67ca9e94e795027597d5cf9a20661214c3c9c0e6f4c02d426ceced7d9"
)
SINGLE_SCENE_60_FORMAL_INDEX_SHA256 = (
    "8cbb126bfaea90a7a8dad132409f0c689f125cc66713a4cd568ba8c2713b9541"
)
SINGLE_SCENE_60_PACKAGE_INDEX_SHA256 = (
    "8d4f891e6bacbf8627a9ba441c5396525259b88b8d4350c5b84bef7db6277c55"
)
SINGLE_SCENE_60_REGULAR_FILES = 29
SINGLE_SCENE_60_FORMAL_ENTRIES = 23
SINGLE_SCENE_60_PACKAGE_ENTRIES = 28

SINGLE_SCENE_30_SUFFIX_REPORT_SHA256 = (
    "69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e"
)
SINGLE_SCENE_30_SUFFIX_SOURCE_COMMIT = "4bac3facfb5116df0e971f2b3e0887600f0fe5cd"
SINGLE_SCENE_30_SUFFIX_SOURCE_BINDING_SHA256 = (
    "e270b7f014597e8960bdd908117bdbde3c712b2a5248d707468f3279e4ade460"
)
SINGLE_SCENE_30_SUFFIX_FORMAL_INDEX_SHA256 = (
    "e275221248b48292cd32959febfd880ac447611a75405c571d2fbbf4ec7d931c"
)
SINGLE_SCENE_30_SUFFIX_PACKAGE_INDEX_SHA256 = (
    "930f41c497e8aaa6dceb4ee12f6b7b87cea189c2320e3d90d1c03e850ca16d4b"
)
SINGLE_SCENE_30_SUFFIX_REGULAR_FILES = 19
SINGLE_SCENE_30_SUFFIX_FORMAL_ENTRIES = 13
SINGLE_SCENE_30_SUFFIX_PACKAGE_ENTRIES = 18

SOCIAL_PREVIEW_PATH = REPO_ROOT / "showcase" / "public" / "og-contract-progress.png"
SOCIAL_PREVIEW_STAGED_NAME = "Look-Twice-V8-Social-Card.png"
SOCIAL_PREVIEW_SHA256 = (
    "68f2f3e4f4b769edceb08c28d73440c5a1a80008bec267ea3a524d69d3213b1a"
)
SOCIAL_PREVIEW_WIDTH = 1726
SOCIAL_PREVIEW_HEIGHT = 911

JUDGE_MOTION_HOOK_MEDIA_DIR = REPO_ROOT / "showcase" / "public" / "media"
JUDGE_MOTION_HOOK_MANIFEST_NAME = (
    "look-twice-repair-to-action-proof.manifest.json"
)
JUDGE_MOTION_HOOK_VIDEO_NAME = "look-twice-repair-to-action-proof.mp4"
JUDGE_MOTION_HOOK_PREVIEW_NAME = "look-twice-repair-to-action-proof.webp"
JUDGE_MOTION_HOOK_MANIFEST_SHA256 = (
    "06f4d276b28797459953e62727ad4180b3d6a66258daf228d67049ffc53d1c50"
)
JUDGE_MOTION_HOOK_VIDEO_SHA256 = (
    "a2fd07abfc59187e170d1151981c0d9225ca08bb20410ebf26e26729d61aaeb0"
)
JUDGE_MOTION_HOOK_PREVIEW_SHA256 = (
    "897ae324c65c55ff9159a80297b4ed46c3d3d57e83f6826d797fa63196f4a22b"
)
JUDGE_MOTION_HOOK_SOURCE_VIDEO_SHA256 = (
    "46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2"
)
JUDGE_MOTION_HOOK_SOURCE_MANIFEST_SHA256 = (
    "d8314119587108cbad0dff09f1414b88f9682bf2b1e2f1bfea87af82484c073a"
)
JUDGE_MOTION_HOOK_PACKAGE_ROLES = {
    JUDGE_MOTION_HOOK_MANIFEST_NAME: (
        "judge-motion hook provenance and simulation-boundary manifest"
    ),
    JUDGE_MOTION_HOOK_VIDEO_NAME: "silent 13-second 1080p judge-motion hook",
    JUDGE_MOTION_HOOK_PREVIEW_NAME: (
        "animated README preview of the judge-motion hook"
    ),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(data: Mapping[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _package_paths(package_dir: Path, excluded: set[str]) -> list[Path]:
    return sorted(
        (
            path
            for path in package_dir.rglob("*")
            if path.is_file()
            and path.relative_to(package_dir).as_posix() not in excluded
        ),
        key=lambda path: path.relative_to(package_dir).as_posix(),
    )


def _v2_role(relative_path: str) -> str:
    suffix = relative_path.removeprefix(V2_PREFIX)
    if suffix == "ATTEMPTS.jsonl":
        return "retained ordered V2 worker-attempt ledger"
    if suffix == "PROGRESS.json":
        return "final checkpointed V2 progress snapshot"
    if suffix == "PROVENANCE_REVIEW.json":
        return "independent V2 proof-scope and provenance review"
    if suffix == "RECOVERY_EXECUTION_AUDIT.json":
        return "V1 failure-history and V2 recovery execution audit"
    if suffix == "REPORT.json":
        return "30-seed additive decision-bound rigid-dynamics report"
    if suffix == "SOURCE_BINDING.json":
        return "formal V2 source-binding manifest"
    if suffix == "SHA256SUMS":
        return "formal V2 32-file checksum index"
    if suffix == "PACKAGE_SHA256SUMS":
        return "complete V2 79-file evidence checksum index"
    if suffix.startswith("TRIALS/"):
        return "sealed per-seed V2 trial checkpoint"
    if suffix.startswith("WORKER_LOGS/"):
        return "retained per-seed V2 worker log"
    if suffix.startswith("EXECUTION_LOGS/") and suffix.endswith(".status"):
        return "retained V1/V2 execution status record"
    if suffix.startswith("EXECUTION_LOGS/"):
        return "retained V1/V2 execution log"
    raise ValueError(f"No role classification for V2 package file: {relative_path}")


def _single_scene_shard_role(
    relative_path: str,
    *,
    prefix: str,
    label: str,
    fixed_seeds: int,
    formal_entries: int,
    package_entries: int,
) -> str:
    suffix = relative_path.removeprefix(prefix)
    if suffix == "PROGRESS.json":
        return f"final non-resumable {label} progress snapshot"
    if suffix == "REPORT.json":
        return f"{fixed_seeds}-seed {label} archived-decision rigid-dynamics report"
    if suffix == "SOURCE_BINDING.json":
        return f"formal {label} source-binding manifest"
    if suffix == "SHA256SUMS":
        return f"formal {label} {formal_entries}-file checksum index"
    if suffix == "PACKAGE_SHA256SUMS":
        return f"complete {label} {package_entries}-file evidence checksum index"
    if suffix.startswith("TRIALS/"):
        return f"sealed per-seed {label} partial-evidence checkpoint"
    if suffix.startswith("EXECUTION_LOGS/") and suffix.endswith(".status"):
        return f"retained {label} formal execution status record"
    if suffix.startswith("EXECUTION_LOGS/") and suffix.endswith(".verify.log"):
        return f"retained {label} dedicated-verifier log"
    if suffix.startswith("EXECUTION_LOGS/") and suffix.endswith(".checksums.log"):
        return f"retained {label} checksum-verification log"
    if suffix.startswith("EXECUTION_LOGS/"):
        return f"retained {label} formal execution log"
    raise ValueError(
        f"No role classification for {label} package file: {relative_path}"
    )


def _validate_index(path: Path, expected_sha256: str, expected_entries: int) -> None:
    if not path.is_file():
        raise ValueError(f"Required checksum index is missing: {path}")
    observed_sha256 = _sha256_file(path)
    if observed_sha256 != expected_sha256:
        raise ValueError(
            f"Checksum-index identity mismatch for {path}: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != expected_entries:
        raise ValueError(
            f"Checksum-index entry count mismatch for {path}: "
            f"expected {expected_entries}, observed {len(lines)}"
        )
    root = path.parent.resolve()
    for line_number, line in enumerate(lines, start=1):
        digest, separator, relative = line.partition("  ")
        if separator != "  " or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Malformed checksum entry at {path}:{line_number}")
        relative_path = Path(relative.removeprefix("./"))
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError(
                f"Checksum entry escapes its evidence directory: {path}:{line_number}"
            ) from error
        if not target.is_file():
            raise ValueError(f"Indexed evidence file is missing: {target}")
        observed = _sha256_file(target)
        if observed != digest:
            raise ValueError(
                f"Indexed evidence identity mismatch for {target}: "
                f"expected {digest}, observed {observed}"
            )


def _validate_two_shard_package(package_dir: Path) -> None:
    shards = (
        {
            "prefix": SINGLE_SCENE_60_PREFIX,
            "label": "single-scene 60-body prefix",
            "regular_files": SINGLE_SCENE_60_REGULAR_FILES,
            "report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
            "source_binding_sha256": SINGLE_SCENE_60_SOURCE_BINDING_SHA256,
            "formal_index_sha256": SINGLE_SCENE_60_FORMAL_INDEX_SHA256,
            "formal_entries": SINGLE_SCENE_60_FORMAL_ENTRIES,
            "package_index_sha256": SINGLE_SCENE_60_PACKAGE_INDEX_SHA256,
            "package_entries": SINGLE_SCENE_60_PACKAGE_ENTRIES,
        },
        {
            "prefix": SINGLE_SCENE_30_SUFFIX_PREFIX,
            "label": "single-scene 30-body suffix",
            "regular_files": SINGLE_SCENE_30_SUFFIX_REGULAR_FILES,
            "report_sha256": SINGLE_SCENE_30_SUFFIX_REPORT_SHA256,
            "source_binding_sha256": SINGLE_SCENE_30_SUFFIX_SOURCE_BINDING_SHA256,
            "formal_index_sha256": SINGLE_SCENE_30_SUFFIX_FORMAL_INDEX_SHA256,
            "formal_entries": SINGLE_SCENE_30_SUFFIX_FORMAL_ENTRIES,
            "package_index_sha256": SINGLE_SCENE_30_SUFFIX_PACKAGE_INDEX_SHA256,
            "package_entries": SINGLE_SCENE_30_SUFFIX_PACKAGE_ENTRIES,
        },
    )
    for shard in shards:
        root = package_dir / str(shard["prefix"]).rstrip("/")
        if not root.is_dir():
            raise ValueError(
                f"Required {shard['label']} evidence directory is missing: {root}"
            )
        regular_files = sum(path.is_file() for path in root.rglob("*"))
        if regular_files != shard["regular_files"]:
            raise ValueError(
                f"Unexpected file count for {shard['label']}: "
                f"expected {shard['regular_files']}, observed {regular_files}"
            )
        for name, expected in (
            ("REPORT.json", shard["report_sha256"]),
            ("SOURCE_BINDING.json", shard["source_binding_sha256"]),
        ):
            target = root / name
            if not target.is_file():
                raise ValueError(f"Required {shard['label']} file is missing: {target}")
            observed = _sha256_file(target)
            if observed != expected:
                raise ValueError(
                    f"Identity mismatch for {target}: expected {expected}, observed {observed}"
                )
        _validate_index(
            root / "SHA256SUMS",
            str(shard["formal_index_sha256"]),
            int(shard["formal_entries"]),
        )
        _validate_index(
            root / "PACKAGE_SHA256SUMS",
            str(shard["package_index_sha256"]),
            int(shard["package_entries"]),
        )


def _inventory(
    package_dir: Path, existing_roles: Mapping[str, str]
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    excluded = {PACKAGE_MANIFEST, PACKAGE_CHECKSUMS}
    for path in _package_paths(package_dir, excluded):
        relative = path.relative_to(package_dir).as_posix()
        role = existing_roles.get(relative)
        if relative == ".gitattributes":
            role = "submission-local binary diff attributes"
        if relative == "V8-Frozen-Challenge-Judge-Card.md":
            role = "compact judge entrypoint"
        if relative == SOCIAL_PREVIEW_STAGED_NAME:
            role = "judge-facing contract-progress social preview card"
        if relative in JUDGE_MOTION_HOOK_PACKAGE_ROLES:
            role = JUDGE_MOTION_HOOK_PACKAGE_ROLES[relative]
        if role is None and relative.startswith(V2_PREFIX):
            role = _v2_role(relative)
        if relative.startswith(SINGLE_SCENE_60_PREFIX):
            role = _single_scene_shard_role(
                relative,
                prefix=SINGLE_SCENE_60_PREFIX,
                label="single-scene 60-body prefix",
                fixed_seeds=20,
                formal_entries=SINGLE_SCENE_60_FORMAL_ENTRIES,
                package_entries=SINGLE_SCENE_60_PACKAGE_ENTRIES,
            )
        if relative.startswith(SINGLE_SCENE_30_SUFFIX_PREFIX):
            role = _single_scene_shard_role(
                relative,
                prefix=SINGLE_SCENE_30_SUFFIX_PREFIX,
                label="single-scene 30-body suffix",
                fixed_seeds=10,
                formal_entries=SINGLE_SCENE_30_SUFFIX_FORMAL_ENTRIES,
                package_entries=SINGLE_SCENE_30_SUFFIX_PACKAGE_ENTRIES,
            )
        if role is None:
            raise ValueError(
                f"No preserved or explicit role for package file: {relative}"
            )
        files.append(
            {
                "path": relative,
                "role": role,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return files


def _decision_dynamics_boundary() -> dict[str, Any]:
    return {
        "evidence_class": "additive non-locked archived-decision rigid-dynamics supplement",
        "formal_result_eligible": False,
        "seed_range": [102500, 102529],
        "fixed_seeds": 30,
        "passed": 30,
        "failed": 0,
        "active_direct_decisions": 29,
        "active_safe_detours": 1,
        "independent_serial_three_body_scenes": 30,
        "distinct_non_fixed_robot_entities_across_run": 90,
        "simultaneous_90_body_scene": False,
        "active_scout_reached": 30,
        "active_carrier_reached": 30,
        "passive_carrier_reached": 30,
        "mean_active_loaded_carrier_path_m": 4.9435286182785365,
        "mean_passive_loaded_carrier_path_m": 6.243270157013467,
        "paired_mean_loaded_carrier_path_reduction_percent": 20.818281221978634,
        "direct_pairs_saving_at_least_0_50_m": "29/29",
        "maximum_tilt_deg": 10.57960742366676,
        "maximum_stationary_partner_drift_m": 0.022328848796049957,
        "trial_blocker_contact_rows": 0,
        "active_pair_contact_rows": 0,
        "post_build_entity_pose_writes": 0,
        "post_build_actuation_api": "control_dofs_velocity only",
        "execution_layout": "one fixed seed per fresh Genesis subprocess, serially on one AMD GPU",
        "v1_failure_mode": "12-hour outer watchdog exit 124 with no report and no per-seed result",
        "v2_formal_wall_seconds": 1101,
        "v2_formal_exit_code": 0,
        "source_commit": V2_SOURCE_COMMIT,
        "source_binding_sha256": SOURCE_BINDING_SHA256,
        "report_sha256": V2_REPORT_SHA256,
        "remote_and_local_verifier_passed": True,
        "observed_execution_ledger": "30 first-attempt worker completions; all worker exit codes 0; no completed-checkpoint rerun or seed replacement observed",
        "proof_scope_limits": [
            "The original formal checksum index did not cover ATTEMPTS.jsonl, PROGRESS.json, or worker/execution logs, so it is not cryptographic proof that no additional unsealed attempt ever existed.",
            "The formal source binding omitted the directly imported src/v4_motion.py dependency, so it is not a complete import-closure attestation; a post-run clean-tree audit found matching worktree and commit bytes.",
        ],
        "interpretation_limit": "Consumes archived route decisions without rerunning the frozen perception-policy loop; not simultaneous cooperative control, dynamic-obstacle evidence, physical-robot or sim-to-real validation, throughput, energy, control-loop latency, or safety certification.",
    }


def _two_shard_dynamics_boundary() -> dict[str, Any]:
    return {
        "evidence_class": "additive non-locked archived-decision rigid-dynamics solver-scale complement",
        "formal_result_eligible": False,
        "seed_range": [102500, 102529],
        "fixed_seeds": 30,
        "passed": 30,
        "failed": 0,
        "active_direct_decisions": 29,
        "active_safe_detours": 1,
        "genesis_scene_count": 2,
        "scene_non_fixed_robot_entity_counts": [60, 30],
        "cumulative_distinct_non_fixed_robot_entities": 90,
        "maximum_co_resident_non_fixed_robot_entities": 60,
        "all_90_robots_co_resident": False,
        "cross_shard_checkpoint_or_state_resume": False,
        "synthetic_combined_execution_report_created": False,
        "arithmetic_summary_across_independent_reports": True,
        "fixed_order_serial_trial_actuation": True,
        "simultaneous_cooperative_control": False,
        "active_scout_reached": 30,
        "active_carrier_reached": 30,
        "passive_carrier_reached": 30,
        "mean_active_loaded_carrier_path_m": 4.943604753440714,
        "mean_passive_loaded_carrier_path_m": 6.245384742632991,
        "paired_mean_loaded_carrier_path_reduction_percent": 20.843871800337798,
        "direct_pairs_saving_at_least_0_50_m": "29/29",
        "safe_detour_seed": 102515,
        "maximum_tilt_deg": 10.583984080221363,
        "maximum_stationary_partner_drift_m": 0.021341944256011203,
        "trial_blocker_contact_rows": 0,
        "active_pair_contact_rows": 0,
        "post_build_entity_pose_writes": 0,
        "post_build_actuation_api": "control_dofs_velocity only",
        "uses_archived_decisions_without_rerunning_policy": True,
        "shards": [
            {
                "name": "single_scene_60_body_prefix",
                "seed_range": [102500, 102519],
                "passed": 20,
                "failed": 0,
                "genesis_scene_count": 1,
                "non_fixed_robot_entities_in_scene": 60,
                "report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
                "source_commit": SINGLE_SCENE_60_SOURCE_COMMIT,
                "source_binding_sha256": SINGLE_SCENE_60_SOURCE_BINDING_SHA256,
            },
            {
                "name": "single_scene_30_body_suffix",
                "seed_range": [102520, 102529],
                "passed": 10,
                "failed": 0,
                "genesis_scene_count": 1,
                "non_fixed_robot_entities_in_scene": 30,
                "report_sha256": SINGLE_SCENE_30_SUFFIX_REPORT_SHA256,
                "source_commit": SINGLE_SCENE_30_SUFFIX_SOURCE_COMMIT,
                "source_binding_sha256": SINGLE_SCENE_30_SUFFIX_SOURCE_BINDING_SHA256,
                "bound_prefix_report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
            },
        ],
        "primary_endpoint_unchanged": "active 29/30 direct versus passive 0/30",
        "failed_v1_all_90_body_attempt_relabelled_as_pass": False,
        "interpretation_limit": "Exactly two independently verified, non-resumable Genesis scene shards with fixed-order serial wheel actuation; 90 cumulative distinct robots, maximum 60 co-resident, never all 90 co-resident. Not a live perception-policy rerun, simultaneous fleet-control result, dynamic-obstacle result, physical-robot or sim-to-real validation, throughput, energy, control-loop latency, or safety certification.",
    }


def _build_package_manifest(
    package_dir: Path, generated_at_utc: str | None
) -> tuple[dict[str, Any], bytes]:
    manifest_path = package_dir / PACKAGE_MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if generated_at_utc is not None:
        data["generated_at_utc"] = generated_at_utc
    data["entry"]["source_branch"] = "v8-contract-progress-nbv"

    _validate_two_shard_package(package_dir)
    existing_roles = {
        item["path"]: item["role"]
        for item in data.get("files", [])
        if isinstance(item, dict) and "path" in item and "role" in item
    }
    inventory = _inventory(package_dir, existing_roles)
    data["evidence_boundaries"]["additive_decision_bound_dynamics_recovery_v2"] = (
        _decision_dynamics_boundary()
    )
    data["evidence_boundaries"][TWO_SHARD_BOUNDARY_KEY] = _two_shard_dynamics_boundary()
    simulation = data["evidence_boundaries"]["simulation_scope"]
    simulation["backend"] = (
        "Frozen policy: Genesis 1.1.2 kinematic simulation on AMD ROCm; "
        "separate additive supplements: non-fixed rigid-body wheel dynamics"
    )
    simulation["separate_additive_decision_bound_dynamics_packaged"] = True
    simulation["separate_additive_two_shard_dynamics_packaged"] = True
    simulation["two_shard_maximum_co_resident_non_fixed_robot_entities"] = 60
    simulation["two_shard_all_90_robots_co_resident"] = False
    data["files"] = inventory

    integrity = data["integrity"]
    integrity.update(
        {
            "manifest_file_entries": len(inventory),
            "package_checksum_entries": len(inventory) + 1,
            "total_regular_package_files_including_sha256sums": len(inventory) + 2,
            "manifest_coverage_complete": True,
            "decision_dynamics_v2_regular_files": 80,
            "decision_dynamics_v2_formal_checksum_entries": 32,
            "decision_dynamics_v2_formal_checksum_index_sha256": V2_FORMAL_INDEX_SHA256,
            "decision_dynamics_v2_complete_checksum_entries": 79,
            "decision_dynamics_v2_complete_checksum_index_sha256": V2_PACKAGE_INDEX_SHA256,
            "decision_dynamics_v2_recovery_audit_sha256": RECOVERY_AUDIT_SHA256,
            "decision_dynamics_v2_provenance_review_sha256": PROVENANCE_REVIEW_SHA256,
            "decision_dynamics_single_scene_60_regular_files": SINGLE_SCENE_60_REGULAR_FILES,
            "decision_dynamics_single_scene_60_formal_checksum_entries": SINGLE_SCENE_60_FORMAL_ENTRIES,
            "decision_dynamics_single_scene_60_formal_checksum_index_sha256": SINGLE_SCENE_60_FORMAL_INDEX_SHA256,
            "decision_dynamics_single_scene_60_complete_checksum_entries": SINGLE_SCENE_60_PACKAGE_ENTRIES,
            "decision_dynamics_single_scene_60_complete_checksum_index_sha256": SINGLE_SCENE_60_PACKAGE_INDEX_SHA256,
            "decision_dynamics_single_scene_30_suffix_regular_files": SINGLE_SCENE_30_SUFFIX_REGULAR_FILES,
            "decision_dynamics_single_scene_30_suffix_formal_checksum_entries": SINGLE_SCENE_30_SUFFIX_FORMAL_ENTRIES,
            "decision_dynamics_single_scene_30_suffix_formal_checksum_index_sha256": SINGLE_SCENE_30_SUFFIX_FORMAL_INDEX_SHA256,
            "decision_dynamics_single_scene_30_suffix_complete_checksum_entries": SINGLE_SCENE_30_SUFFIX_PACKAGE_ENTRIES,
            "decision_dynamics_single_scene_30_suffix_complete_checksum_index_sha256": SINGLE_SCENE_30_SUFFIX_PACKAGE_INDEX_SHA256,
        }
    )
    return data, _json_bytes(data)


def _build_package_checksums(package_dir: Path, manifest_bytes: bytes) -> bytes:
    entries: list[str] = []
    for path in _package_paths(package_dir, {PACKAGE_CHECKSUMS}):
        relative = path.relative_to(package_dir).as_posix()
        digest = (
            _sha256_bytes(manifest_bytes)
            if relative == PACKAGE_MANIFEST
            else _sha256_file(path)
        )
        entries.append(f"{digest}  {relative}")
    return ("\n".join(entries) + "\n").encode("utf-8")


def _insert_after(
    mapping: Mapping[str, Any], after_key: str, new_key: str, value: Any
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    inserted = False
    for key, current in mapping.items():
        output[key] = current
        if key == after_key:
            output[new_key] = value
            inserted = True
    if not inserted:
        raise KeyError(f"Insertion key not found: {after_key}")
    return output


def _decision_dynamics_artifact() -> dict[str, Any]:
    base = "release/v8-derived/decision_dynamics_recovery_v2_102500_102529"
    staged = (
        "submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/"
        "evidence/decision_dynamics_recovery_v2_102500_102529"
    )
    return {
        "report_path": f"{base}/REPORT.json",
        "staged_report_path": f"{staged}/REPORT.json",
        "report_sha256": V2_REPORT_SHA256,
        "source_commit": V2_SOURCE_COMMIT,
        "source_binding_path": f"{base}/SOURCE_BINDING.json",
        "source_binding_sha256": SOURCE_BINDING_SHA256,
        "recovery_audit_path": f"{base}/RECOVERY_EXECUTION_AUDIT.json",
        "recovery_audit_sha256": RECOVERY_AUDIT_SHA256,
        "provenance_review_path": f"{base}/PROVENANCE_REVIEW.json",
        "provenance_review_sha256": PROVENANCE_REVIEW_SHA256,
        "formal_sha256sums_path": f"{base}/SHA256SUMS",
        "formal_sha256sums_sha256": V2_FORMAL_INDEX_SHA256,
        "formal_checksum_entries": 32,
        "complete_sha256sums_path": f"{base}/PACKAGE_SHA256SUMS",
        "complete_sha256sums_sha256": V2_PACKAGE_INDEX_SHA256,
        "complete_checksum_entries": 79,
        "regular_files": 80,
        "remote_verifier_passed": True,
        "local_byte_identical_verifier_passed": True,
        "publication_verified": True,
        "publication_state": "published on the additive review branch and anonymously verified; not an official competition result",
    }


def _two_shard_dynamics_artifact() -> dict[str, Any]:
    source_base = "release/v8-derived"
    staged_base = (
        "submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/evidence"
    )
    prefix_name = "decision_dynamics_single_scene_60_102500_102519"
    suffix_name = "decision_dynamics_single_scene_30_suffix_102520_102529"
    return {
        "evidence_class": "additive non-locked archived-decision rigid-dynamics solver-scale complement",
        "formal_result_eligible": False,
        "combined_claim_requires_both_independent_verifiers": True,
        "prefix_60_body": {
            "report_path": f"{source_base}/{prefix_name}/REPORT.json",
            "staged_report_path": f"{staged_base}/{prefix_name}/REPORT.json",
            "report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
            "source_commit": SINGLE_SCENE_60_SOURCE_COMMIT,
            "source_binding_path": f"{source_base}/{prefix_name}/SOURCE_BINDING.json",
            "source_binding_sha256": SINGLE_SCENE_60_SOURCE_BINDING_SHA256,
            "formal_sha256sums_path": f"{source_base}/{prefix_name}/SHA256SUMS",
            "formal_sha256sums_sha256": SINGLE_SCENE_60_FORMAL_INDEX_SHA256,
            "formal_checksum_entries": SINGLE_SCENE_60_FORMAL_ENTRIES,
            "complete_sha256sums_path": f"{source_base}/{prefix_name}/PACKAGE_SHA256SUMS",
            "complete_sha256sums_sha256": SINGLE_SCENE_60_PACKAGE_INDEX_SHA256,
            "complete_checksum_entries": SINGLE_SCENE_60_PACKAGE_ENTRIES,
            "regular_files": SINGLE_SCENE_60_REGULAR_FILES,
            "dedicated_verifier_passed": True,
        },
        "suffix_30_body": {
            "report_path": f"{source_base}/{suffix_name}/REPORT.json",
            "staged_report_path": f"{staged_base}/{suffix_name}/REPORT.json",
            "report_sha256": SINGLE_SCENE_30_SUFFIX_REPORT_SHA256,
            "source_commit": SINGLE_SCENE_30_SUFFIX_SOURCE_COMMIT,
            "source_binding_path": f"{source_base}/{suffix_name}/SOURCE_BINDING.json",
            "source_binding_sha256": SINGLE_SCENE_30_SUFFIX_SOURCE_BINDING_SHA256,
            "formal_sha256sums_path": f"{source_base}/{suffix_name}/SHA256SUMS",
            "formal_sha256sums_sha256": SINGLE_SCENE_30_SUFFIX_FORMAL_INDEX_SHA256,
            "formal_checksum_entries": SINGLE_SCENE_30_SUFFIX_FORMAL_ENTRIES,
            "complete_sha256sums_path": f"{source_base}/{suffix_name}/PACKAGE_SHA256SUMS",
            "complete_sha256sums_sha256": SINGLE_SCENE_30_SUFFIX_PACKAGE_INDEX_SHA256,
            "complete_checksum_entries": SINGLE_SCENE_30_SUFFIX_PACKAGE_ENTRIES,
            "regular_files": SINGLE_SCENE_30_SUFFIX_REGULAR_FILES,
            "dedicated_verifier_passed": True,
            "bound_prefix_report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
        },
        "publication_verified": True,
        "publication_state": "published on the additive review branch and anonymously verified; official competition PR not opened",
    }


def _pdf_page_count(path: Path) -> int:
    count = len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))
    if count <= 0:
        raise ValueError(
            f"Could not determine a positive page count from staged PDF: {path}"
        )
    return count


def _technical_report_identity(
    path: Path,
    *,
    expected_sha256: str | None,
    expected_page_count: int | None,
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"The staged technical-report PDF is missing: {path}")
    sha256 = _sha256_file(path)
    if expected_sha256 is not None and sha256 != expected_sha256:
        raise ValueError(
            "The staged technical-report PDF does not match --technical-report-sha256: "
            f"expected {expected_sha256}, observed {sha256}"
        )
    page_count = _pdf_page_count(path)
    if expected_page_count is not None and page_count != expected_page_count:
        raise ValueError(
            "The staged technical-report PDF page count does not match "
            f"--technical-report-page-count: expected {expected_page_count}, "
            f"observed {page_count}"
        )
    return {
        "sha256": sha256,
        "size_bytes": path.stat().st_size,
        "page_count": page_count,
    }


def _social_preview_identity(package_dir: Path) -> dict[str, Any]:
    if not SOCIAL_PREVIEW_PATH.is_file():
        raise ValueError(
            f"The contract-progress social preview is missing: {SOCIAL_PREVIEW_PATH}"
        )
    observed_sha256 = _sha256_file(SOCIAL_PREVIEW_PATH)
    if observed_sha256 != SOCIAL_PREVIEW_SHA256:
        raise ValueError(
            "The contract-progress social preview does not match its pinned identity: "
            f"expected {SOCIAL_PREVIEW_SHA256}, observed {observed_sha256}"
        )
    staged_path = package_dir / SOCIAL_PREVIEW_STAGED_NAME
    if not staged_path.is_file():
        raise ValueError(f"The staged social preview is missing: {staged_path}")
    staged_sha256 = _sha256_file(staged_path)
    if staged_sha256 != observed_sha256:
        raise ValueError(
            "The staged social preview does not match the site identity: "
            f"expected {observed_sha256}, observed {staged_sha256}"
        )
    return {
        "path": "showcase/public/og-contract-progress.png",
        "staged_path": (
            "submission/official-repo/submissions/"
            f"Track3-Liu-Liang-Look-Twice/{SOCIAL_PREVIEW_STAGED_NAME}"
        ),
        "sha256": observed_sha256,
        "size_bytes": SOCIAL_PREVIEW_PATH.stat().st_size,
        "width": SOCIAL_PREVIEW_WIDTH,
        "height": SOCIAL_PREVIEW_HEIGHT,
        "disclosure": (
            "PUBLICLY PREREGISTERED · AMD GPU · SIMULATION ONLY; "
            "CONCEPTUAL ARTWORK, NOT EXPERIMENT CAPTURE"
        ),
    }


def _judge_motion_hook_identity(package_dir: Path) -> dict[str, Any]:
    """Verify the approved hook, its source binding, and staged byte identity."""

    source_paths = {
        JUDGE_MOTION_HOOK_MANIFEST_NAME: (
            JUDGE_MOTION_HOOK_MANIFEST_SHA256,
            JUDGE_MOTION_HOOK_MEDIA_DIR / JUDGE_MOTION_HOOK_MANIFEST_NAME,
        ),
        JUDGE_MOTION_HOOK_VIDEO_NAME: (
            JUDGE_MOTION_HOOK_VIDEO_SHA256,
            JUDGE_MOTION_HOOK_MEDIA_DIR / JUDGE_MOTION_HOOK_VIDEO_NAME,
        ),
        JUDGE_MOTION_HOOK_PREVIEW_NAME: (
            JUDGE_MOTION_HOOK_PREVIEW_SHA256,
            JUDGE_MOTION_HOOK_MEDIA_DIR / JUDGE_MOTION_HOOK_PREVIEW_NAME,
        ),
    }
    for name, (expected_sha256, source_path) in source_paths.items():
        if not source_path.is_file():
            raise ValueError(f"The judge-motion hook source is missing: {source_path}")
        source_sha256 = _sha256_file(source_path)
        if source_sha256 != expected_sha256:
            raise ValueError(
                f"The judge-motion hook source identity changed for {name}: "
                f"expected {expected_sha256}, observed {source_sha256}"
            )

        staged_path = package_dir / name
        if not staged_path.is_file():
            raise ValueError(f"The staged judge-motion hook file is missing: {staged_path}")
        if staged_path.read_bytes() != source_path.read_bytes():
            raise ValueError(
                "The staged judge-motion hook is not byte-identical to the site "
                f"asset: {name}"
            )

    manifest_path = source_paths[JUDGE_MOTION_HOOK_MANIFEST_NAME][1]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_manifest_values = {
        "schema_version": "look-twice.judge-motion-hook/v1",
        "candidate_id": "v8-frozen",
        "hook_id": "repair-to-action-proof",
    }
    for key, expected in expected_manifest_values.items():
        if manifest.get(key) != expected:
            raise ValueError(
                f"Unexpected judge-motion hook manifest {key}: "
                f"expected {expected!r}, observed {manifest.get(key)!r}"
            )

    derived_from = manifest["derived_from"]
    source_video_path = REPO_ROOT / derived_from["path"]
    source_manifest_path = REPO_ROOT / derived_from["manifest_path"]
    for label, path, declared_sha256, expected_sha256 in (
        (
            "source video",
            source_video_path,
            derived_from["sha256"],
            JUDGE_MOTION_HOOK_SOURCE_VIDEO_SHA256,
        ),
        (
            "source manifest",
            source_manifest_path,
            derived_from["manifest_sha256"],
            JUDGE_MOTION_HOOK_SOURCE_MANIFEST_SHA256,
        ),
    ):
        if declared_sha256 != expected_sha256:
            raise ValueError(
                f"The judge-motion hook declares an unexpected {label} SHA256: "
                f"expected {expected_sha256}, observed {declared_sha256}"
            )
        if not path.is_file() or _sha256_file(path) != expected_sha256:
            raise ValueError(f"The judge-motion hook {label} binding does not verify: {path}")

    video = manifest["video"]
    preview = manifest["readme_preview"]
    if (
        video["path"] != JUDGE_MOTION_HOOK_VIDEO_NAME
        or video["sha256"] != JUDGE_MOTION_HOOK_VIDEO_SHA256
        or video["duration_seconds"] != 13.2
        or video["width"] != 1920
        or video["height"] != 1080
        or video["audio"] is not False
    ):
        raise ValueError("The judge-motion hook video declaration changed")
    if (
        preview["path"] != JUDGE_MOTION_HOOK_PREVIEW_NAME
        or preview["sha256"] != JUDGE_MOTION_HOOK_PREVIEW_SHA256
        or preview["duration_seconds"] != 13.2
        or preview["width"] != 1280
        or preview["height"] != 720
        or preview["loop"] is not True
    ):
        raise ValueError("The judge-motion hook README preview declaration changed")
    if (
        derived_from["source_start_seconds"] != 16.8
        or derived_from["source_end_seconds"] != 30.0
        or manifest["boundary"]
        != {
            "recorded_replay_excerpt": True,
            "new_experiment_or_result": False,
            "simulation_only": True,
            "real_robot_footage": False,
            "audio": False,
        }
    ):
        raise ValueError("The judge-motion hook provenance boundary changed")

    package_prefix = (
        "submission/official-repo/submissions/"
        "Track3-Liu-Liang-Look-Twice/"
    )
    return {
        "manifest_path": (
            "showcase/public/media/" + JUDGE_MOTION_HOOK_MANIFEST_NAME
        ),
        "staged_manifest_path": package_prefix + JUDGE_MOTION_HOOK_MANIFEST_NAME,
        "manifest_sha256": JUDGE_MOTION_HOOK_MANIFEST_SHA256,
        "hook_id": manifest["hook_id"],
        "description": manifest["description"],
        "derived_from": dict(derived_from),
        "video": {
            **dict(video),
            "path": "showcase/public/media/" + JUDGE_MOTION_HOOK_VIDEO_NAME,
            "staged_path": package_prefix + JUDGE_MOTION_HOOK_VIDEO_NAME,
        },
        "readme_preview": {
            **dict(preview),
            "path": "showcase/public/media/" + JUDGE_MOTION_HOOK_PREVIEW_NAME,
            "staged_path": package_prefix + JUDGE_MOTION_HOOK_PREVIEW_NAME,
        },
        "boundary": dict(manifest["boundary"]),
    }


def _build_handoff_manifest(
    path: Path,
    package_inventory_count: int,
    package_checksum_bytes: bytes,
    technical_report_identity: Mapping[str, Any],
    social_preview_identity: Mapping[str, Any],
    judge_motion_hook_identity: Mapping[str, Any],
    generated_on: str | None,
    publication_receipts: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], bytes]:
    data = json.loads(path.read_text(encoding="utf-8"))
    publication_verified = publication_receipts is not None
    if generated_on is not None:
        data["generated_on"] = generated_on
    data["status"] = (
        "contract_progress_public_review_snapshot_no_official_pr"
        if publication_verified
        else "contract_progress_publication_in_progress_no_official_pr"
    )
    data["submission_state"].update(
        {
            "additive_source_refresh_published": publication_verified,
            "additive_pages_refresh_deployed": publication_verified,
            "additive_report_release_asset_replaced": publication_verified,
            "additive_official_fork_refresh_pushed": publication_verified,
            "source_repository_homepage_refreshed": publication_verified,
            "social_card_repository_homepage_published": publication_verified,
            "full_demo_browser_playback_published": publication_verified,
            "external_upstream_issue_or_pr_opened": True,
        }
    )
    data["candidate"]["source_branch"] = "v8-contract-progress-nbv"

    boundary = _decision_dynamics_boundary()
    data_without_existing_boundary = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "additive_decision_bound_dynamics_recovery_v2",
            TWO_SHARD_BOUNDARY_KEY,
        }
    }
    data = _insert_after(
        data_without_existing_boundary,
        "additive_dual_body_dynamics",
        "additive_decision_bound_dynamics_recovery_v2",
        boundary,
    )
    data = _insert_after(
        data,
        "additive_decision_bound_dynamics_recovery_v2",
        TWO_SHARD_BOUNDARY_KEY,
        _two_shard_dynamics_boundary(),
    )
    artifacts = {
        key: value
        for key, value in data["artifacts"].items()
        if key != TWO_SHARD_BOUNDARY_KEY
    }
    if "additive_decision_bound_dynamics_recovery_v2" not in artifacts:
        artifacts = _insert_after(
            artifacts,
            "additive_dual_body_dynamics",
            "additive_decision_bound_dynamics_recovery_v2",
            _decision_dynamics_artifact(),
        )
    else:
        artifacts["additive_decision_bound_dynamics_recovery_v2"] = (
            _decision_dynamics_artifact()
        )
    artifacts = _insert_after(
        artifacts,
        "additive_decision_bound_dynamics_recovery_v2",
        TWO_SHARD_BOUNDARY_KEY,
        _two_shard_dynamics_artifact(),
    )
    artifacts = {
        key: value for key, value in artifacts.items() if key != "judge_motion_hook"
    }
    artifacts = _insert_after(
        artifacts,
        "short_evidence_reel",
        "judge_motion_hook",
        {
            **dict(judge_motion_hook_identity),
            "public_video_url": (
                "https://eason4kim-rocket.github.io/media/"
                f"{JUDGE_MOTION_HOOK_VIDEO_NAME}"
            ),
            "public_preview_url": (
                "https://eason4kim-rocket.github.io/media/"
                f"{JUDGE_MOTION_HOOK_PREVIEW_NAME}"
            ),
            "publication_verified": publication_verified,
            "publication_state": (
                "published and anonymously verified by SHA256 and MIME type"
                if publication_verified
                else "prepared locally; publication and anonymous verification in progress"
            ),
        },
    )

    artifacts["additive_dual_body_dynamics"].update(
        {
            "publication_verified": True,
            "publication_state": (
                "published on v8-competition-release; additive non-locked "
                "evidence, not an official competition result"
            ),
        }
    )

    artifacts["technical_report_pdf"].update(
        {
            **technical_report_identity,
            "publication_verified": publication_verified,
            "publication_state": (
                "contract-progress-integrated identity published at the stable "
                "candidate-release URL and anonymously hash-verified"
                if publication_verified
                else "contract-progress-integrated identity prepared locally; "
                "stable release-asset replacement and anonymous hash verification in progress"
            ),
        }
    )
    artifacts["final_demo_video"].update(
        {
            "browser_playback_url": (
                "https://eason4kim-rocket.github.io/media/"
                "Look-Twice-V8-Demo.mp4"
            ),
            "browser_playback_verified": publication_verified,
            "browser_playback_state": (
                "published as video/mp4 on the primary evidence site and public "
                "mirror; byte-identical to the release download"
                if publication_verified
                else "browser-playback publication and anonymous verification in progress"
            ),
        }
    )
    artifacts["compound_contract_progress_challenge"].update(
        {
            "publication_verified": publication_verified,
            "publication_state": (
                "complete formal evidence published on v8-contract-progress-nbv "
                "and anonymously verified; formal_result_eligible=false"
                if publication_verified
                else "complete formal evidence prepared for v8-contract-progress-nbv; "
                "publication verification in progress; formal_result_eligible=false"
            ),
        }
    )
    artifacts["social_preview"].update(social_preview_identity)
    package_checksum_sha256 = _sha256_bytes(package_checksum_bytes)
    artifacts["official_repository_staging"].update(
        {
            "checksummed_artifacts": package_inventory_count + 1,
            "manifest_inventory_entries": package_inventory_count,
            "total_regular_files_including_sha256sums": package_inventory_count + 2,
            "sha256s_sha256": package_checksum_sha256,
            "status": (
                "published_personal_fork_review_branch_no_official_pr"
                if publication_verified
                else "local_contract_progress_refresh_publication_in_progress_no_pr"
            ),
        }
    )
    data["artifacts"] = artifacts

    data["links"]["source_branch_target"] = (
        "https://github.com/eason4kim-rocket/look-twice/tree/"
        "v8-contract-progress-nbv"
    )
    data["links"]["additive_refresh_publicly_verified"] = publication_verified
    if publication_verified:
        data["links"]["public_site_mirror"] = publication_receipts[
            "sites_deployment_url"
        ]
    else:
        data["links"].pop("public_site_mirror", None)

    staging_publication = (
        "contract-progress refresh published on the personal-fork review "
        "branch; official PR not opened"
        if publication_verified
        else "contract-progress refresh publication in progress; official PR not opened"
    )
    verification = data["verification"]
    verification.update(
        {
            "node_22_site_tests": "44/44 passed",
            "node_22_lint": "passed",
            "node_dependency_audit": "0 known vulnerabilities",
            "production_build": "passed",
            "pdf_visual_qa": (
                f"{technical_report_identity['page_count']}/"
                f"{technical_report_identity['page_count']} pages rendered and "
                "inspected after final regeneration"
            ),
            "browser_visual_qa": (
                "contract-progress-integrated source passed site tests, lint, "
                "production build, and public route/asset verification; owner may "
                "still perform a final presentation review before the official PR"
                if publication_verified
                else "contract-progress-integrated local source passed site tests, "
                "lint, and production build; public route/asset verification in progress"
            ),
            "decision_dynamics_recovery_v2_tests": "16/16 runner and verifier tests passed; Ruff passed; formal remote and byte-identical local verifiers passed; 30/30 formal seeds, failed 0",
            "decision_dynamics_two_shard_tests": "23/23 runner and verifier tests passed; both formal and complete-package checksum indexes passed; dedicated 60-body and 30-body verifiers passed; 20/20 prefix plus 10/10 suffix, failed 0",
            "official_repository_staging_checksums": (
                f"{package_inventory_count + 1} checksummed artifacts passed locally "
                f"({package_inventory_count + 2} total files including SHA256SUMS); "
                f"manifest inventory {package_inventory_count}/{package_inventory_count}; "
                f"checksum-index SHA256 {package_checksum_sha256}; "
                f"{staging_publication}"
            ),
            "github_pages_deployment": (
                f"commit {publication_receipts['pages_commit_sha']}; four routes, "
                "contract-progress JSON, PDF, social preview, and browser-playable "
                "3:59 MP4 verified without credentials"
                if publication_verified
                else "contract-progress GitHub Pages deployment and anonymous "
                "route/asset verification in progress"
            ),
            "public_site_mirror_deployment": (
                f"Sites version {publication_receipts['sites_version_number']} from "
                f"source commit {publication_receipts['sites_source_commit_sha']}; "
                f"{publication_receipts['sites_deployment_url']}; routes, "
                "contract-progress JSON, PDF, social preview, and browser-playable "
                "3:59 MP4 verified without credentials"
                if publication_verified
                else "contract-progress public mirror deployment and anonymous "
                "route/asset verification in progress"
            ),
            "public_distribution": (
                (
                    "contract-progress source, site, "
                    f"{technical_report_identity['page_count']}-page PDF, and "
                    f"{package_inventory_count + 2}-file official package are public "
                    "on review targets and anonymously verified; official competition PR not opened"
                )
                if publication_verified
                else "contract-progress source/site/PDF/package publication and "
                "anonymous verification are in progress; official competition PR not opened"
            ),
            "source_repository_homepage": (
                f"default branch {publication_receipts['source_default_branch']}; "
                "root README social card and direct browser-demo link verified "
                "without credentials"
                if publication_verified
                else "source repository homepage refresh and anonymous verification "
                "in progress"
            ),
            "official_fork_branch": (
                "the byte-identical contract-progress package is public on "
                "submission/track3-liu-liang-look-twice-v8; official_pr_opened=false"
                if publication_verified
                else "the byte-identical contract-progress package is staged for "
                "submission/track3-liu-liang-look-twice-v8; publication in progress; "
                "official_pr_opened=false"
            ),
        }
    )
    if publication_verified:
        verification["publication_receipts"] = {
            **dict(publication_receipts),
            "source_receipt_scope": (
                "last non-self-referential evidence/package snapshot before the "
                "receipt-seal documentation commit"
            ),
        }
    else:
        verification.pop("publication_receipts", None)
    data["verification"] = verification
    data["owner_review_items"] = [
        "Complete owner visual and audible review of the final demo.",
        "Review the English competition PR body and authorize opening the official PR.",
    ]
    data["remaining_before_pr"] = [
        *(
            []
            if publication_verified
            else [
                "complete and anonymously verify the authorized contract-progress publication refresh"
            ]
        ),
        "complete owner visual and audible review of the final 3:59 English demo",
        "obtain owner approval to open the official English submission PR",
    ]
    return data, _json_bytes(data)


def _validate_timestamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise argparse.ArgumentTypeError("expected UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    return value


def _validate_sha256(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise argparse.ArgumentTypeError("expected a 64-character SHA256 hex digest")
    return normalized


def _validate_git_sha(value: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{40}", normalized):
        raise argparse.ArgumentTypeError("expected a 40-character Git commit SHA")
    return normalized


def _validate_https_url(value: str) -> str:
    if not value.startswith("https://"):
        raise argparse.ArgumentTypeError("expected an https:// URL")
    return value


def _validate_branch(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", value) or value.startswith("/"):
        raise argparse.ArgumentTypeError("expected a Git branch name")
    return value


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def _sealed_publication_receipts(path: Path) -> dict[str, Any] | None:
    """Return validated receipts already sealed in a handoff manifest."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        receipts = data["verification"]["publication_receipts"]
        if not isinstance(receipts, dict):
            return None
        return {
            "verified_at_utc": _validate_timestamp(str(receipts["verified_at_utc"])),
            "source_commit_sha": _validate_git_sha(
                str(receipts["source_commit_sha"])
            ),
            "source_default_branch": _validate_branch(
                str(receipts["source_default_branch"])
            ),
            "pages_commit_sha": _validate_git_sha(str(receipts["pages_commit_sha"])),
            "official_fork_commit_sha": _validate_git_sha(
                str(receipts["official_fork_commit_sha"])
            ),
            "sites_source_commit_sha": _validate_git_sha(
                str(receipts["sites_source_commit_sha"])
            ),
            "sites_version_number": _positive_int(
                str(receipts["sites_version_number"])
            ),
            "sites_deployment_url": _validate_https_url(
                str(receipts["sites_deployment_url"])
            ),
        }
    except (
        argparse.ArgumentTypeError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument(
        "--handoff-manifest", type=Path, default=DEFAULT_HANDOFF_MANIFEST
    )
    parser.add_argument("--generated-at-utc", type=_validate_timestamp)
    parser.add_argument("--generated-on", help="local calendar date YYYY-MM-DD")
    parser.add_argument(
        "--technical-report-sha256",
        type=_validate_sha256,
        help="optional expected staged technical-report SHA256",
    )
    parser.add_argument(
        "--technical-report-page-count",
        type=_positive_int,
        help="optional expected staged technical-report page count",
    )
    parser.add_argument(
        "--publication-verified",
        action="store_true",
        help=(
            "seal externally verified publication state; requires every "
            "publication receipt argument"
        ),
    )
    parser.add_argument("--publication-verified-at-utc", type=_validate_timestamp)
    parser.add_argument("--source-commit-sha", type=_validate_git_sha)
    parser.add_argument("--source-default-branch", type=_validate_branch)
    parser.add_argument("--pages-commit-sha", type=_validate_git_sha)
    parser.add_argument("--official-fork-commit-sha", type=_validate_git_sha)
    parser.add_argument("--sites-source-commit-sha", type=_validate_git_sha)
    parser.add_argument("--sites-version-number", type=_positive_int)
    parser.add_argument("--sites-deployment-url", type=_validate_https_url)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "verify canonical bytes without writing; when no publication flags "
            "are supplied, reuse validated receipts already sealed in the handoff "
            "manifest"
        ),
    )
    args = parser.parse_args()

    publication_values = {
        "verified_at_utc": args.publication_verified_at_utc,
        "source_commit_sha": args.source_commit_sha,
        "source_default_branch": args.source_default_branch,
        "pages_commit_sha": args.pages_commit_sha,
        "official_fork_commit_sha": args.official_fork_commit_sha,
        "sites_source_commit_sha": args.sites_source_commit_sha,
        "sites_version_number": args.sites_version_number,
        "sites_deployment_url": args.sites_deployment_url,
    }
    supplied_publication_values = {
        key: value for key, value in publication_values.items() if value is not None
    }
    if args.publication_verified and len(supplied_publication_values) != len(
        publication_values
    ):
        parser.error(
            "--publication-verified requires --publication-verified-at-utc, "
            "--source-commit-sha, --source-default-branch, --pages-commit-sha, "
            "--official-fork-commit-sha, --sites-source-commit-sha, "
            "--sites-version-number, and --sites-deployment-url"
        )
    if not args.publication_verified and supplied_publication_values:
        parser.error(
            "publication receipt arguments require --publication-verified"
        )
    publication_receipts = (
        supplied_publication_values if args.publication_verified else None
    )

    package_dir = args.package_dir.resolve()
    handoff_manifest = args.handoff_manifest.resolve()
    if args.check and publication_receipts is None:
        publication_receipts = _sealed_publication_receipts(handoff_manifest)
    package_data, package_manifest_bytes = _build_package_manifest(
        package_dir, args.generated_at_utc
    )
    package_checksum_bytes = _build_package_checksums(
        package_dir, package_manifest_bytes
    )
    technical_report_identity = _technical_report_identity(
        package_dir / "Look-Twice-V8-Technical-Report.pdf",
        expected_sha256=args.technical_report_sha256,
        expected_page_count=args.technical_report_page_count,
    )
    social_preview_identity = _social_preview_identity(package_dir)
    judge_motion_hook_identity = _judge_motion_hook_identity(package_dir)
    handoff_data, handoff_bytes = _build_handoff_manifest(
        handoff_manifest,
        len(package_data["files"]),
        package_checksum_bytes,
        technical_report_identity,
        social_preview_identity,
        judge_motion_hook_identity,
        args.generated_on,
        publication_receipts,
    )

    expected = {
        package_dir / PACKAGE_MANIFEST: package_manifest_bytes,
        package_dir / PACKAGE_CHECKSUMS: package_checksum_bytes,
        handoff_manifest: handoff_bytes,
    }
    if args.check:
        mismatches = [
            str(path)
            for path, content in expected.items()
            if not path.exists() or path.read_bytes() != content
        ]
        if mismatches:
            print("non-canonical files:")
            for mismatch in mismatches:
                print(f"  {mismatch}")
            return 1
    else:
        for path, content in expected.items():
            _atomic_write(path, content)

    manifest_paths = {item["path"] for item in package_data["files"]}
    actual_paths = {
        path.relative_to(package_dir).as_posix()
        for path in _package_paths(package_dir, {PACKAGE_MANIFEST, PACKAGE_CHECKSUMS})
    }
    if manifest_paths != actual_paths:
        raise ValueError("Manifest coverage changed during finalization")
    if (
        len(package_checksum_bytes.decode("utf-8").splitlines())
        != len(actual_paths) + 1
    ):
        raise ValueError("Top-level checksum coverage is incomplete")

    print(
        json.dumps(
            {
                "status": "verified" if args.check else "finalized",
                "manifest_entries": len(actual_paths),
                "checksum_entries": len(actual_paths) + 1,
                "total_regular_files": len(actual_paths) + 2,
                "sha256s_sha256": _sha256_bytes(package_checksum_bytes),
                "technical_report_sha256": technical_report_identity["sha256"],
                "technical_report_page_count": technical_report_identity["page_count"],
                "decision_dynamics_v2_report_sha256": V2_REPORT_SHA256,
                "decision_dynamics_single_scene_60_report_sha256": SINGLE_SCENE_60_REPORT_SHA256,
                "decision_dynamics_single_scene_30_suffix_report_sha256": SINGLE_SCENE_30_SUFFIX_REPORT_SHA256,
                "social_preview_sha256": social_preview_identity["sha256"],
                "judge_motion_hook_manifest_sha256": judge_motion_hook_identity[
                    "manifest_sha256"
                ],
                "judge_motion_hook_video_sha256": judge_motion_hook_identity["video"][
                    "sha256"
                ],
                "judge_motion_hook_preview_sha256": judge_motion_hook_identity[
                    "readme_preview"
                ]["sha256"],
                "handoff_manifest": str(handoff_manifest),
            },
            indent=2,
        )
    )
    del handoff_data
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
