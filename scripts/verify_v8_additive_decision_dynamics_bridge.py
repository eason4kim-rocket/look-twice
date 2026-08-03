#!/usr/bin/env python3
"""Fail-closed verifier for the formal decision-to-dynamics bridge report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "look-twice.additive-decision-dynamics-bridge/v1"
EXPECTED_INPUT_SHA256 = (
    "59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0"
)
FORMAL_SEEDS = list(range(102500, 102530))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def validate_report(
    report: dict[str, Any], *, verify_local_source: bool = True
) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, observed {actual!r}")

    require("schema_version", report.get("schema_version"), SCHEMA_VERSION)
    require("run_class", report.get("run_class"), "formal")
    require(
        "boundary.additive_non_locked",
        _get(report, "boundary", "additive_non_locked"),
        True,
    )
    require(
        "boundary.formal_result_eligible",
        _get(report, "boundary", "formal_result_eligible"),
        False,
    )
    require(
        "boundary.changes_frozen_v8_endpoint",
        _get(report, "boundary", "changes_frozen_v8_endpoint"),
        False,
    )
    require(
        "boundary.uses_archived_decisions_without_rerunning_policy",
        _get(report, "boundary", "uses_archived_decisions_without_rerunning_policy"),
        True,
    )
    require(
        "boundary.oracle_used_by_controller",
        _get(report, "boundary", "oracle_used_by_controller"),
        False,
    )
    require(
        "decision_input.sha256",
        _get(report, "decision_input", "sha256"),
        EXPECTED_INPUT_SHA256,
    )
    require(
        "decision_input.fixed_seeds",
        _get(report, "decision_input", "fixed_seeds"),
        FORMAL_SEEDS,
    )
    require(
        "decision_input.consumed_in_this_run",
        _get(report, "decision_input", "consumed_in_this_run"),
        True,
    )
    require(
        "protocol.post_build_actuation_api",
        _get(report, "protocol", "post_build_actuation_api"),
        "control_dofs_velocity only",
    )
    require(
        "protocol.post_build_entity_pose_writes",
        _get(report, "protocol", "post_build_entity_pose_writes"),
        0,
    )
    require(
        "source.git_status_porcelain",
        _get(report, "source", "git_status_porcelain"),
        "",
    )

    expected_summary = {
        "trials": 30,
        "passed": 30,
        "failed": 0,
        "all_passed": True,
        "active_direct_decisions": 29,
        "active_safe_detours": 1,
        "distinct_non_fixed_robot_entities": 90,
        "active_scout_reached": 30,
        "active_carrier_reached": 30,
        "passive_carrier_reached": 30,
        "direct_pairs_saving_at_least_0_50_m": 29,
        "total_blocker_contact_rows": 0,
        "total_active_pair_contact_rows": 0,
        "minimum_mean_path_reduction_fraction": 0.15,
    }
    for key, expected in expected_summary.items():
        require(f"summary.{key}", _get(report, "summary", key), expected)
    reduction = _get(report, "summary", "paired_mean_path_reduction_fraction")
    if (
        not isinstance(reduction, (int, float))
        or isinstance(reduction, bool)
        or reduction < 0.15
    ):
        errors.append(
            f"summary.paired_mean_path_reduction_fraction: expected >= 0.15, observed {reduction!r}"
        )
    max_tilt = _get(report, "summary", "maximum_tilt_deg")
    if (
        not isinstance(max_tilt, (int, float))
        or isinstance(max_tilt, bool)
        or max_tilt > 20.0
    ):
        errors.append(
            f"summary.maximum_tilt_deg: expected <= 20, observed {max_tilt!r}"
        )
    max_drift = _get(report, "summary", "maximum_stationary_partner_drift_m")
    if (
        not isinstance(max_drift, (int, float))
        or isinstance(max_drift, bool)
        or max_drift > 0.08
    ):
        errors.append(
            f"summary.maximum_stationary_partner_drift_m: expected <= 0.08, observed {max_drift!r}"
        )
    checks = _get(report, "summary", "aggregate_checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
    ):
        errors.append("summary.aggregate_checks: every fixed check must be true")

    trials = report.get("trials")
    if not isinstance(trials, list):
        errors.append("trials: expected list")
        trials = []
    require(
        "trial seed order",
        [row.get("seed") for row in trials if isinstance(row, dict)],
        FORMAL_SEEDS,
    )
    for index, trial in enumerate(trials):
        if not isinstance(trial, dict):
            errors.append(f"trials[{index}]: expected object")
            continue
        if _get(trial, "assessment", "passed") is not True:
            errors.append(f"trials[{index}].assessment.passed: expected true")
        checks = _get(trial, "assessment", "checks")
        if (
            not isinstance(checks, dict)
            or not checks
            or not all(value is True for value in checks.values())
        ):
            errors.append(
                f"trials[{index}].assessment.checks: every check must be true"
            )
        require(
            f"trials[{index}].script_entity_pose_writes_after_build",
            trial.get("script_entity_pose_writes_after_build"),
            0,
        )

    if verify_local_source:
        for field in ("script", "verifier", "fixed_protocol", "engineering_audit"):
            relative = _get(report, "source", field)
            expected_hash = _get(report, "source", f"{field}_sha256")
            if not isinstance(relative, str) or not isinstance(expected_hash, str):
                errors.append(f"source.{field}: missing path/hash")
                continue
            path = ROOT / relative
            if not path.is_file():
                errors.append(f"source.{field}: local file missing: {relative}")
            elif sha256_file(path) != expected_hash:
                errors.append(f"source.{field}: local identity mismatch")
        bindings = {
            "dual_body_helper_sha256": ROOT
            / "scripts"
            / "run_v8_additive_dual_body_dynamics.py",
            "scenario_source_sha256": ROOT / "src" / "v6_scenario.py",
            "carrier_urdf_sha256": ROOT
            / "assets"
            / "robots"
            / "diff_drive_carrier.urdf",
            "scout_urdf_sha256": ROOT / "assets" / "robots" / "diff_drive_scout.urdf",
        }
        for field, path in bindings.items():
            if not path.is_file() or sha256_file(path) != _get(report, "source", field):
                errors.append(f"source.{field}: local identity mismatch")
        input_path = ROOT / str(_get(report, "decision_input", "path"))
        if not input_path.is_file() or sha256_file(input_path) != EXPECTED_INPUT_SHA256:
            errors.append(
                "decision_input.path: local immutable report identity mismatch"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--skip-local-source", action="store_true")
    args = parser.parse_args()
    report_path = args.report.resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    errors = validate_report(report, verify_local_source=not args.skip_local_source)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "PASS: additive decision-to-dynamics bridge 30/30 "
        f"report_sha256={sha256_file(report_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
