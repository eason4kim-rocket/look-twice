#!/usr/bin/env python3
"""Verify the additive dual-body dynamics report and its source bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "look-twice.additive-dual-body-dynamics/v1"
EXPECTED_SEEDS = list(range(160820, 160840))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def close(actual: Any, expected: Any) -> bool:
    try:
        return math.isclose(
            float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12
        )
    except (TypeError, ValueError):
        return False


def validate_report(report: dict[str, Any], *, verify_source: bool = True) -> list[str]:
    errors: list[str] = []
    require(
        report.get("schema_version") == SCHEMA_VERSION,
        "schema_version mismatch",
        errors,
    )

    boundary = report.get("boundary") or {}
    require(
        boundary.get("additive_non_locked") is True, "not additive/non-locked", errors
    )
    require(
        boundary.get("formal_result_eligible") is False,
        "formal endpoint was broadened",
        errors,
    )
    require(
        boundary.get("changes_frozen_v8_endpoint") is False,
        "frozen endpoint changed",
        errors,
    )

    protocol = report.get("protocol") or {}
    require(
        protocol.get("seeds") == EXPECTED_SEEDS,
        "confirmatory seed set mismatch",
        errors,
    )
    require(
        protocol.get("carrier_and_scout_are_distinct_non_fixed_entities") is True,
        "dual non-fixed entity declaration missing",
        errors,
    )
    require(
        protocol.get("post_build_actuation_api") == "control_dofs_velocity only",
        "post-build actuation API mismatch",
        errors,
    )

    trials = report.get("trials") or []
    require(len(trials) == len(EXPECTED_SEEDS), "trial count mismatch", errors)
    require(
        [trial.get("seed") for trial in trials] == EXPECTED_SEEDS,
        "trial seed order mismatch",
        errors,
    )

    passed = 0
    obstacle_contacts = 0
    pair_contacts = 0
    tilts: list[float] = []
    drifts: list[float] = []
    scout_paths: list[float] = []
    carrier_paths: list[float] = []
    for trial in trials:
        assessment = trial.get("assessment") or {}
        checks = assessment.get("checks") or {}
        all_checks = bool(checks) and all(value is True for value in checks.values())
        require(
            assessment.get("passed") is all_checks,
            f"seed {trial.get('seed')}: assessment mismatch",
            errors,
        )
        require(
            trial.get("script_entity_set_pos_calls_after_build") == 0,
            f"seed {trial.get('seed')}: post-build pose write",
            errors,
        )
        if assessment.get("passed") is True:
            passed += 1
        for role in ("scout", "carrier"):
            motion = trial.get(role) or {}
            obstacle_contacts += int(motion.get("obstacle_contact_rows", -1))
            pair_contacts += int(motion.get("robot_contact_rows", -1))
            tilts.append(float(motion.get("max_tilt_deg", float("inf"))))
            drifts.append(float(motion.get("stationary_partner_drift_m", float("inf"))))
        scout_paths.append(
            float((trial.get("scout") or {}).get("path_length_m", float("nan")))
        )
        carrier_paths.append(
            float((trial.get("carrier") or {}).get("path_length_m", float("nan")))
        )

    summary = report.get("summary") or {}
    expected_summary = {
        "trials": len(trials),
        "passed": passed,
        "failed": len(trials) - passed,
        "distinct_non_fixed_robot_entities": 2 * len(trials),
        "total_obstacle_contact_rows": obstacle_contacts,
        "total_pair_robot_contact_rows": pair_contacts,
    }
    for key, expected in expected_summary.items():
        require(summary.get(key) == expected, f"summary {key} mismatch", errors)
    require(
        summary.get("all_passed") is (passed == len(trials)),
        "summary all_passed mismatch",
        errors,
    )
    require(
        close(summary.get("pass_rate"), passed / len(trials)),
        "summary pass_rate mismatch",
        errors,
    )
    if trials:
        require(
            close(summary.get("maximum_tilt_deg"), max(tilts)),
            "summary maximum_tilt_deg mismatch",
            errors,
        )
        require(
            close(summary.get("maximum_stationary_partner_drift_m"), max(drifts)),
            "summary maximum_stationary_partner_drift_m mismatch",
            errors,
        )
        require(
            close(
                summary.get("mean_scout_path_m"), sum(scout_paths) / len(scout_paths)
            ),
            "summary mean_scout_path_m mismatch",
            errors,
        )
        require(
            close(
                summary.get("mean_carrier_path_m"),
                sum(carrier_paths) / len(carrier_paths),
            ),
            "summary mean_carrier_path_m mismatch",
            errors,
        )

    environment = report.get("environment") or {}
    require(
        environment.get("backend_requested") == "amdgpu",
        "AMD backend not requested",
        errors,
    )
    require(bool(environment.get("torch_hip")), "ROCm/HIP version missing", errors)
    require("AMD" in str(environment.get("gpu")), "AMD GPU identity missing", errors)

    source = report.get("source") or {}
    require(
        source.get("git_status_porcelain") == "", "source tree was not clean", errors
    )
    if verify_source:
        bindings = (
            (source.get("script"), source.get("script_sha256"), "script"),
            (
                "assets/robots/diff_drive_carrier.urdf",
                source.get("carrier_urdf_sha256"),
                "carrier URDF",
            ),
            (
                "assets/robots/diff_drive_scout.urdf",
                source.get("scout_urdf_sha256"),
                "scout URDF",
            ),
        )
        for relative, expected_hash, label in bindings:
            path = ROOT / str(relative)
            require(path.is_file(), f"{label} source missing", errors)
            if path.is_file():
                require(
                    sha256_file(path) == expected_hash,
                    f"{label} SHA256 mismatch",
                    errors,
                )

    require(
        summary.get("all_passed") is True, "acceptance bar did not fully pass", errors
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--skip-source-hashes",
        action="store_true",
        help="verify report consistency without requiring the bound source tree",
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    errors = validate_report(report, verify_source=not args.skip_source_hashes)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "PASS: additive dual-body dynamics "
        f"{report['summary']['passed']}/{report['summary']['trials']} "
        f"report_sha256={sha256_file(args.report)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
