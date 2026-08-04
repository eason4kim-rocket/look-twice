#!/usr/bin/env python3
"""Finalize and verify the local V8 official-submission package.

The package is intentionally local-only until the owner authorizes publication.
This script makes the final inventory mechanical: every regular package file is
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

REPORT_SHA256 = "1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99"
SOURCE_BINDING_SHA256 = "c40f6ba74a39ad761e4926ddb66326f33a1a645fef3c96364f9c53b9d5d3eb5d"
RECOVERY_AUDIT_SHA256 = "344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4"
PROVENANCE_REVIEW_SHA256 = "4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7"
V2_PACKAGE_INDEX_SHA256 = "24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540"
V2_FORMAL_INDEX_SHA256 = "dae4f7f694e3db14db9731e6292d2d7e28f98b6540eca485be9666947273d5be"
V2_SOURCE_COMMIT = "b0c4f0d33b0a2d0c647dda0b2b3b7c03279a511a"
TECHNICAL_REPORT_SHA256 = "29935428bf1eedd5942fa89e961fbc8b057e99130cc5df18a28fe3040c71d35e"


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
            if path.is_file() and path.relative_to(package_dir).as_posix() not in excluded
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


def _inventory(package_dir: Path, existing_roles: Mapping[str, str]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    excluded = {PACKAGE_MANIFEST, PACKAGE_CHECKSUMS}
    for path in _package_paths(package_dir, excluded):
        relative = path.relative_to(package_dir).as_posix()
        role = existing_roles.get(relative)
        if role is None and relative.startswith(V2_PREFIX):
            role = _v2_role(relative)
        if role is None:
            raise ValueError(f"No preserved or explicit role for package file: {relative}")
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
        "report_sha256": REPORT_SHA256,
        "remote_and_local_verifier_passed": True,
        "observed_execution_ledger": "30 first-attempt worker completions; all worker exit codes 0; no completed-checkpoint rerun or seed replacement observed",
        "proof_scope_limits": [
            "The original formal checksum index did not cover ATTEMPTS.jsonl, PROGRESS.json, or worker/execution logs, so it is not cryptographic proof that no additional unsealed attempt ever existed.",
            "The formal source binding omitted the directly imported src/v4_motion.py dependency, so it is not a complete import-closure attestation; a post-run clean-tree audit found matching worktree and commit bytes.",
        ],
        "interpretation_limit": "Consumes archived route decisions without rerunning the frozen perception-policy loop; not simultaneous cooperative control, dynamic-obstacle evidence, physical-robot or sim-to-real validation, throughput, energy, control-loop latency, or safety certification.",
    }


def _build_package_manifest(
    package_dir: Path, generated_at_utc: str | None
) -> tuple[dict[str, Any], bytes]:
    manifest_path = package_dir / PACKAGE_MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if generated_at_utc is not None:
        data["generated_at_utc"] = generated_at_utc

    existing_roles = {
        item["path"]: item["role"]
        for item in data.get("files", [])
        if isinstance(item, dict) and "path" in item and "role" in item
    }
    inventory = _inventory(package_dir, existing_roles)
    data["evidence_boundaries"][
        "additive_decision_bound_dynamics_recovery_v2"
    ] = _decision_dynamics_boundary()
    simulation = data["evidence_boundaries"]["simulation_scope"]
    simulation["backend"] = (
        "Frozen policy: Genesis 1.1.2 kinematic simulation on AMD ROCm; "
        "separate additive supplements: non-fixed rigid-body wheel dynamics"
    )
    simulation["separate_additive_decision_bound_dynamics_packaged"] = True
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
        "report_sha256": REPORT_SHA256,
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
        "publication_verified": False,
        "publication_state": "local owner-review identity; not pushed, deployed, released, or submitted",
    }


def _build_handoff_manifest(
    path: Path,
    package_dir: Path,
    package_inventory_count: int,
    package_checksum_bytes: bytes,
    generated_on: str | None,
) -> tuple[dict[str, Any], bytes]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if generated_on is not None:
        data["generated_on"] = generated_on

    boundary = _decision_dynamics_boundary()
    data_without_existing_boundary = {
        key: value
        for key, value in data.items()
        if key != "additive_decision_bound_dynamics_recovery_v2"
    }
    data = _insert_after(
        data_without_existing_boundary,
        "additive_dual_body_dynamics",
        "additive_decision_bound_dynamics_recovery_v2",
        boundary,
    )
    artifacts = data["artifacts"]
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

    pdf = package_dir / "Look-Twice-V8-Technical-Report.pdf"
    if _sha256_file(pdf) != TECHNICAL_REPORT_SHA256:
        raise ValueError("The staged technical-report PDF does not match its final identity")
    artifacts["technical_report_pdf"].update(
        {
            "sha256": TECHNICAL_REPORT_SHA256,
            "size_bytes": pdf.stat().st_size,
            "page_count": 15,
            "publication_verified": False,
            "publication_state": "local V2-integrated identity; stable URL still serves the earlier public baseline pending owner approval",
        }
    )
    package_checksum_sha256 = _sha256_bytes(package_checksum_bytes)
    artifacts["official_repository_staging"].update(
        {
            "checksummed_artifacts": package_inventory_count + 1,
            "manifest_inventory_entries": package_inventory_count,
            "total_regular_files_including_sha256sums": package_inventory_count + 2,
            "sha256s_sha256": package_checksum_sha256,
            "status": "local_v2_refresh_ready_no_push_no_pr",
        }
    )
    data["artifacts"] = artifacts

    verification = data["verification"]
    verification.update(
        {
            "node_22_site_tests": "35/35 passed",
            "node_22_lint": "passed",
            "node_dependency_audit": "0 known vulnerabilities",
            "production_build": "passed",
            "pdf_visual_qa": "15/15 pages rendered and inspected after final regeneration",
            "browser_visual_qa": "previous public baseline inspection retained; V2 local source, tests, lint, and production-build QA passed; owner browser review remains before deployment",
            "decision_dynamics_recovery_v2_tests": "16/16 runner and verifier tests passed; Ruff passed; formal remote and byte-identical local verifiers passed; 30/30 formal seeds, failed 0",
            "official_repository_staging_checksums": (
                f"{package_inventory_count + 1} checksummed artifacts passed locally "
                f"({package_inventory_count + 2} total files including SHA256SUMS); "
                f"manifest inventory {package_inventory_count}/{package_inventory_count}; "
                f"checksum-index SHA256 {package_checksum_sha256}; V2 refresh not pushed"
            ),
            "public_distribution": "previous challenge/feasibility baseline remains public and anonymously verified; V2 source, site, 15-page PDF, and 105-file official package are local only pending owner approval",
            "official_fork_branch": "public branch remains at the earlier baseline; the byte-identical local V2 package refresh is prepared on the local official-fork branch but unpushed; official_pr_opened=false",
        }
    )
    data["verification"] = verification
    data["owner_review_items"] = [
        "Complete owner visual and audible review of the final demo.",
        "Review the locally verified V2 source/site/PDF/official-package diff and authorize or reject publication.",
        "Review the prepared Genesis issue and PR packet and authorize or reject upstream publication.",
        "Review the English competition PR body and authorize opening the official PR.",
    ]
    data["remaining_before_pr"] = [
        "complete owner visual and audible review of the final 3:59 English demo",
        "obtain owner approval to publish and anonymously verify the V2 source/site/PDF/official-fork refresh",
        "obtain separate owner approval before filing the Genesis upstream issue or PR",
        "obtain owner approval to open the official English submission PR",
    ]
    return data, _json_bytes(data)


def _validate_timestamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise argparse.ArgumentTypeError("expected UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument(
        "--handoff-manifest", type=Path, default=DEFAULT_HANDOFF_MANIFEST
    )
    parser.add_argument("--generated-at-utc", type=_validate_timestamp)
    parser.add_argument("--generated-on", help="local calendar date YYYY-MM-DD")
    parser.add_argument(
        "--check", action="store_true", help="verify canonical bytes without writing"
    )
    args = parser.parse_args()

    package_dir = args.package_dir.resolve()
    handoff_manifest = args.handoff_manifest.resolve()
    package_data, package_manifest_bytes = _build_package_manifest(
        package_dir, args.generated_at_utc
    )
    package_checksum_bytes = _build_package_checksums(
        package_dir, package_manifest_bytes
    )
    handoff_data, handoff_bytes = _build_handoff_manifest(
        handoff_manifest,
        package_dir,
        len(package_data["files"]),
        package_checksum_bytes,
        args.generated_on,
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
    if len(package_checksum_bytes.decode("utf-8").splitlines()) != len(actual_paths) + 1:
        raise ValueError("Top-level checksum coverage is incomplete")

    print(
        json.dumps(
            {
                "status": "verified" if args.check else "finalized",
                "manifest_entries": len(actual_paths),
                "checksum_entries": len(actual_paths) + 1,
                "total_regular_files": len(actual_paths) + 2,
                "sha256s_sha256": _sha256_bytes(package_checksum_bytes),
                "technical_report_sha256": TECHNICAL_REPORT_SHA256,
                "decision_dynamics_report_sha256": REPORT_SHA256,
                "handoff_manifest": str(handoff_manifest),
            },
            indent=2,
        )
    )
    del handoff_data
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
