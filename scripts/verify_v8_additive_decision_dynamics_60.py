#!/usr/bin/env python3
"""Fail-closed verifier for the fixed single-scene 60-body supplement."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v8_additive_decision_dynamics_bridge import (  # noqa: E402
    EXPECTED_CHALLENGE_REPORT_SHA256,
    assess_trial,
    load_formal_cases,
    sha256_file,
    trial_layout,
)


REPORT_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60/v1"
CHECKPOINT_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60-checkpoint/v1"
BINDING_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60-source-binding/v1"
PROGRESS_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60-progress/v1"
RUN_CLASS = "formal"
FORMAL_SEEDS = tuple(range(102500, 102520))
EXPECTED_TRIALS = 20
EXPECTED_DIRECT = 19
EXPECTED_SAFE_DETOURS = 1
EXPECTED_BODIES = 60
EXPECTED_CHECKSUM_ENTRIES = 23
EXPECTED_V1_RUNNER_SHA256 = (
    "6d885b8b004c816e663c5e346e2bf740e75440c24f97457931f237a824331b8c"
)
IDENTITY_KEYS = (
    "attempt_id",
    "process_identity",
    "process_id",
    "genesis_initialization_id",
    "single_scene_id",
    "scene_build_id",
)
REQUIRED_SOURCE_NAMES = {
    "runner",
    "verifier",
    "fixed_protocol",
    "v1_runner",
    "dual_body_helper",
    "scenario_source",
    "motion_source",
    "carrier_urdf",
    "scout_urdf",
    "decision_input",
}
DEFAULT_INPUT_REPORT = (
    ROOT
    / "release"
    / "v8-frozen"
    / "results"
    / "challenge_102500_102529"
    / "CHALLENGE_REPORT.json"
)


def _get(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


EMPTY_PREFIX_SHA256 = _sha256_bytes(_canonical_json([]))


def trial_sha256(trial: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json(trial))


def source_binding_sha256(binding: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json(binding))


def checkpoint_content_sha256(checkpoint: dict[str, Any]) -> str:
    payload = dict(checkpoint)
    payload.pop("checkpoint_content_sha256", None)
    return _sha256_bytes(_canonical_json(payload))


def extend_prefix_sha256(previous: str, checkpoint_digest: str) -> str:
    return _sha256_bytes(
        _canonical_json(
            {
                "previous_prefix_sha256": previous,
                "checkpoint_content_sha256": checkpoint_digest,
            }
        )
    )


def _json_equal(actual: Any, expected: Any) -> bool:
    try:
        return _canonical_json(actual) == _canonical_json(expected)
    except (TypeError, ValueError):
        return False


def _all_numbers_finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_all_numbers_finite(child) for child in value.values())
    if isinstance(value, list):
        return all(_all_numbers_finite(child) for child in value)
    return True


def _identity_errors(identity: Any, *, label: str) -> list[str]:
    if not isinstance(identity, dict):
        return [f"{label}: expected identity object"]
    errors: list[str] = []
    if set(identity) != set(IDENTITY_KEYS):
        errors.append(
            f"{label}: expected exactly identity keys {list(IDENTITY_KEYS)!r}"
        )
    attempt_id = identity.get("attempt_id")
    if (
        not isinstance(attempt_id, str)
        or len(attempt_id) != 64
        or any(character not in "0123456789abcdef" for character in attempt_id)
    ):
        errors.append(f"{label}.attempt_id: expected lowercase SHA256 identity")
    process_id = identity.get("process_id")
    if (
        isinstance(process_id, bool)
        or not isinstance(process_id, int)
        or process_id <= 0
    ):
        errors.append(f"{label}.process_id: expected positive integer")
    process_identity = identity.get("process_identity")
    if not isinstance(process_identity, str) or not process_identity.endswith(
        f":pid:{process_id}"
    ):
        errors.append(f"{label}.process_identity: inconsistent with process_id")
    if isinstance(attempt_id, str):
        expected_derived = {
            "genesis_initialization_id": f"{attempt_id}:genesis-initialization-0",
            "single_scene_id": f"{attempt_id}:genesis-scene-0",
            "scene_build_id": f"{attempt_id}:scene-build-0",
        }
        for key, expected in expected_derived.items():
            if identity.get(key) != expected:
                errors.append(f"{label}.{key}: inconsistent with attempt_id")
    return errors


def _safe_child(root: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _read_json_object(path: Path) -> dict[str, Any]:
    def reject_nonfinite(token: str) -> None:
        raise ValueError(f"non-finite JSON number {token}")

    value = json.loads(
        path.read_text(encoding="utf-8"), parse_constant=reject_nonfinite
    )
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _formal_cases() -> list[Any]:
    cases = load_formal_cases(DEFAULT_INPUT_REPORT)[:EXPECTED_TRIALS]
    seeds = [case.seed for case in cases]
    if seeds != list(FORMAL_SEEDS):
        raise ValueError(f"immutable input prefix mismatch: {seeds}")
    if sum(bool(case.full_chain_direct) for case in cases) != EXPECTED_DIRECT:
        raise ValueError("immutable input does not contain fixed 19-direct prefix")
    detours = [case.seed for case in cases if not case.full_chain_direct]
    if detours != [102515]:
        raise ValueError(f"immutable input safe-detour mismatch: {detours}")
    return cases


def _expected_decision(case: Any) -> dict[str, Any]:
    return {
        "selected_corridor": case.selected_corridor,
        "full_chain_direct": case.full_chain_direct,
        "corridor_a_blocked": case.corridor_a_blocked,
        "corridor_b_blocked": case.corridor_b_blocked,
        "selected_corridor_clear": case.selected_corridor_clear,
        "both_corridors_blocked": case.both_corridors_blocked,
        "archived_episode_sha256": case.archived_episode_sha256,
        "input_class": case.input_class,
    }


def _trial_errors(trial: dict[str, Any], case: Any, index: int) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if not _json_equal(actual, expected):
            errors.append(
                f"trial {case.seed} {name}: expected {expected!r}, observed {actual!r}"
            )

    require("seed", trial.get("seed"), case.seed)
    require("decision", trial.get("decision"), _expected_decision(case))
    layout = trial_layout(case, index)
    require(
        "blocked_corridors", trial.get("blocked_corridors"), layout["blocked_corridors"]
    )
    require(
        "script_entity_pose_writes_after_build",
        trial.get("script_entity_pose_writes_after_build"),
        0,
    )
    roles = ("active_scout", "active_carrier", "passive_carrier")
    expected_waypoints = {
        "active_scout": layout["active_scout_waypoints"],
        "active_carrier": layout["active_carrier_waypoints"],
        "passive_carrier": layout["passive_carrier_waypoints"],
    }
    bodies: dict[str, dict[str, Any]] = {}
    for role in roles:
        body = trial.get(role)
        if not isinstance(body, dict):
            errors.append(f"trial {case.seed} {role}: expected object")
            continue
        bodies[role] = body
        require(f"{role}.reached", body.get("reached"), True)
        fixed_waypoints = [list(point) for point in expected_waypoints[role]]
        require(f"{role}.waypoints", body.get("waypoints"), fixed_waypoints)
        goal_error = _finite_number(body.get("final_goal_error_m"))
        if goal_error is None or goal_error > 0.14:
            errors.append(f"trial {case.seed} {role}: invalid goal error")
        wheel_target = _finite_number(body.get("max_abs_wheel_target_rad_s"))
        if wheel_target is None or wheel_target <= 0.1:
            errors.append(f"trial {case.seed} {role}: wheel target not nontrivial")
        tilt = _finite_number(body.get("max_tilt_deg"))
        if tilt is None or tilt > 20.0:
            errors.append(f"trial {case.seed} {role}: tilt exceeds fixed limit")
        for contact_field in (
            "obstacle_contact_rows",
            "stationary_obstacle_contact_rows",
            "partner_contact_rows",
        ):
            require(f"{role}.{contact_field}", body.get(contact_field), 0)
        for pose_field in ("start_pose", "final_pose"):
            pose = body.get(pose_field)
            if not isinstance(pose, dict) or not pose:
                errors.append(f"trial {case.seed} {role}.{pose_field}: missing")
            elif any(_finite_number(component) is None for component in pose.values()):
                errors.append(f"trial {case.seed} {role}.{pose_field}: non-finite")
        final_pose = body.get("final_pose")
        if isinstance(final_pose, dict) and goal_error is not None:
            final_x = _finite_number(final_pose.get("x"))
            final_y = _finite_number(final_pose.get("y"))
            if final_x is not None and final_y is not None:
                target = expected_waypoints[role][-1]
                recomputed_goal_error = math.dist((final_x, final_y), target)
                if not math.isclose(
                    goal_error,
                    recomputed_goal_error,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    errors.append(
                        f"trial {case.seed} {role}.final_goal_error_m: "
                        "inconsistent with final pose and fixed final waypoint"
                    )

    scout = bodies.get("active_scout")
    active = bodies.get("active_carrier")
    passive = bodies.get("passive_carrier")
    if scout is not None:
        scout_path = _finite_number(scout.get("path_length_m"))
        if scout_path is None or scout_path < 0.50:
            errors.append(f"trial {case.seed}: scout path below fixed minimum")
        scout_drift = _finite_number(scout.get("stationary_partner_drift_m"))
        if scout_drift is None or scout_drift > 0.08:
            errors.append(f"trial {case.seed}: carrier drift exceeds fixed limit")
    if active is not None:
        active_drift = _finite_number(active.get("stationary_partner_drift_m"))
        if active_drift is None or active_drift > 0.08:
            errors.append(f"trial {case.seed}: scout drift exceeds fixed limit")
    if active is not None and passive is not None:
        active_path = _finite_number(active.get("path_length_m"))
        passive_path = _finite_number(passive.get("path_length_m"))
        if active_path is None or active_path < 3.50:
            errors.append(f"trial {case.seed}: active carrier path below minimum")
        if passive_path is None or passive_path < 3.50:
            errors.append(f"trial {case.seed}: passive carrier path below minimum")
        if (
            case.full_chain_direct
            and active_path is not None
            and passive_path is not None
            and passive_path - active_path < 0.50
        ):
            errors.append(f"trial {case.seed}: direct-pair saving below 0.50 m")

    try:
        assessment = assess_trial(trial)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        errors.append(f"trial {case.seed}: cannot recompute assessment: {exc}")
    else:
        require("assessment", trial.get("assessment"), assessment)
        require("assessment.passed", assessment.get("passed"), True)
    if trial.get("trial_index") not in (None, index):
        errors.append(f"trial {case.seed} trial_index mismatch")
    return errors


def recompute_summary(trials: list[dict[str, Any]]) -> dict[str, Any]:
    active_paths = [float(row["active_carrier"]["path_length_m"]) for row in trials]
    passive_paths = [float(row["passive_carrier"]["path_length_m"]) for row in trials]
    bodies = [
        body
        for row in trials
        for body in (
            row["active_scout"],
            row["active_carrier"],
            row["passive_carrier"],
        )
    ]
    direct = [row for row in trials if row["decision"]["full_chain_direct"]]
    detours = [row for row in trials if not row["decision"]["full_chain_direct"]]
    mean_active = statistics.fmean(active_paths)
    mean_passive = statistics.fmean(passive_paths)
    reduction = (mean_passive - mean_active) / mean_passive
    passed = sum(bool(row["assessment"]["passed"]) for row in trials)
    direct_savings = sum(
        float(row["passive_carrier"]["path_length_m"])
        - float(row["active_carrier"]["path_length_m"])
        >= 0.50
        for row in direct
    )
    aggregate_checks = {
        "fixed_denominator_complete": len(trials) == EXPECTED_TRIALS,
        "expected_decision_counts": len(direct) == EXPECTED_DIRECT
        and len(detours) == EXPECTED_SAFE_DETOURS,
        "all_trials_passed": passed == EXPECTED_TRIALS,
        "all_reported_metrics_finite_and_denominator_positive": all(
            math.isfinite(value)
            for value in (
                *active_paths,
                *passive_paths,
                *(float(body["max_tilt_deg"]) for body in bodies),
                *(
                    float(row[role]["stationary_partner_drift_m"])
                    for row in trials
                    for role in ("active_scout", "active_carrier")
                ),
            )
        )
        and mean_passive > 0.0,
        "mean_loaded_carrier_path_reduction_meets_run_class_floor": reduction >= 0.15,
        "every_direct_pair_saved_at_least_0_50_m": direct_savings == EXPECTED_DIRECT,
    }
    return {
        "trials": len(trials),
        "passed": passed,
        "failed": len(trials) - passed,
        "all_passed": all(aggregate_checks.values()),
        "active_direct_decisions": len(direct),
        "active_safe_detours": len(detours),
        "distinct_non_fixed_robot_entities": 3 * len(trials),
        "active_scout_reached": sum(
            bool(row["active_scout"]["reached"]) for row in trials
        ),
        "active_carrier_reached": sum(
            bool(row["active_carrier"]["reached"]) for row in trials
        ),
        "passive_carrier_reached": sum(
            bool(row["passive_carrier"]["reached"]) for row in trials
        ),
        "mean_active_loaded_carrier_path_m": mean_active,
        "mean_passive_loaded_carrier_path_m": mean_passive,
        "paired_mean_path_reduction_fraction": reduction,
        "paired_mean_path_reduction_percent": 100.0 * reduction,
        "minimum_mean_path_reduction_fraction": 0.15,
        "direct_pairs_saving_at_least_0_50_m": direct_savings,
        "total_blocker_contact_rows": sum(
            int(body["obstacle_contact_rows"])
            + int(body["stationary_obstacle_contact_rows"])
            for body in bodies
        ),
        "total_active_pair_contact_rows": sum(
            int(row[role]["partner_contact_rows"])
            for row in trials
            for role in ("active_scout", "active_carrier")
        ),
        "maximum_tilt_deg": max(float(body["max_tilt_deg"]) for body in bodies),
        "maximum_stationary_partner_drift_m": max(
            max(
                float(row["active_scout"]["stationary_partner_drift_m"]),
                float(row["active_carrier"]["stationary_partner_drift_m"]),
            )
            for row in trials
        ),
        "aggregate_checks": aggregate_checks,
    }


def _checksum_errors(output_root: Path, expected_paths: set[str]) -> list[str]:
    path = output_root / "SHA256SUMS"
    if not path.is_file():
        return ["SHA256SUMS missing"]
    errors: list[str] = []
    observed: dict[str, str] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            errors.append(f"SHA256SUMS line {line_number}: invalid format")
            continue
        digest, relative = parts[0], parts[1].lstrip("*")
        if relative in observed:
            errors.append(f"SHA256SUMS duplicate path: {relative}")
            continue
        observed[relative] = digest
        child = _safe_child(output_root, relative)
        if child is None or not child.is_file():
            errors.append(f"SHA256SUMS path missing or escapes output root: {relative}")
        elif sha256_file(child) != digest:
            errors.append(f"SHA256SUMS hash mismatch: {relative}")
    if set(observed) != expected_paths:
        errors.append(
            "SHA256SUMS scope mismatch: "
            f"expected {sorted(expected_paths)}, observed {sorted(observed)}"
        )
    if len(observed) != EXPECTED_CHECKSUM_ENTRIES:
        errors.append(
            f"SHA256SUMS entry count: expected {EXPECTED_CHECKSUM_ENTRIES}, "
            f"observed {len(observed)}"
        )
    return errors


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path | None = None,
    verify_local_source: bool = True,
    verify_artifacts: bool = True,
) -> list[str]:
    """Validate only a complete 20/20 REPORT; partial checkpoints fail closed."""

    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if not _json_equal(actual, expected):
            errors.append(f"{name}: expected {expected!r}, observed {actual!r}")

    if not _all_numbers_finite(report):
        errors.append("report contains non-finite numeric value")

    require("schema_version", report.get("schema_version"), REPORT_SCHEMA_VERSION)
    require("run_class", report.get("run_class"), RUN_CLASS)
    boundary_expected = {
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
    }
    for field, expected in boundary_expected.items():
        require(f"boundary.{field}", _get(report, "boundary", field), expected)

    require(
        "decision_input.sha256",
        _get(report, "decision_input", "sha256"),
        EXPECTED_CHALLENGE_REPORT_SHA256,
    )
    require(
        "decision_input.fixed_seeds",
        _get(report, "decision_input", "fixed_seeds"),
        list(FORMAL_SEEDS),
    )
    require(
        "decision_input.consumed_in_this_run",
        _get(report, "decision_input", "consumed_in_this_run"),
        True,
    )
    require(
        "decision_input.path",
        _get(report, "decision_input", "path"),
        "release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json",
    )

    execution_expected = {
        "layout": "single_genesis_scene_60_non_fixed_bodies",
        "genesis_scene_count": 1,
        "scene_build_count": 1,
        "cross_seed_entities_share_scene": True,
        "non_fixed_robot_entities_in_scene": EXPECTED_BODIES,
        "non_fixed_robot_entities_per_trial": 3,
        "fixed_order_serial_trial_actuation": True,
        "simultaneous_cooperative_control": False,
        "checkpoint_scope": "partial_evidence_from_live_non_resumable_scene",
        "partial_checkpoints_are_full_results": False,
        "resume_supported": False,
        "post_build_controller_configuration_apis": [
            "set_dofs_kp",
            "set_dofs_kv",
            "set_dofs_force_range",
        ],
        "post_build_motion_actuation_api": "control_dofs_velocity only",
        "post_build_entity_pose_writes": 0,
        "teardown_guard_enabled": True,
        "teardown_guard_method": "os._exit_after_fsynced_report_and_sha256s",
    }
    for field, expected in execution_expected.items():
        require(f"execution.{field}", _get(report, "execution", field), expected)
    require(
        "protocol.post_build_controller_configuration_apis",
        _get(report, "protocol", "post_build_controller_configuration_apis"),
        ["set_dofs_kp", "set_dofs_kv", "set_dofs_force_range"],
    )
    require(
        "protocol.post_build_motion_actuation_api",
        _get(report, "protocol", "post_build_motion_actuation_api"),
        "control_dofs_velocity only",
    )
    require(
        "protocol.post_build_entity_pose_writes",
        _get(report, "protocol", "post_build_entity_pose_writes"),
        0,
    )
    require(
        "protocol.fixed_seed_order",
        _get(report, "protocol", "fixed_seed_order"),
        list(FORMAL_SEEDS),
    )
    fixed_scientific_parameters = {
        "backend": "amdgpu",
        "dt_seconds": 0.02,
        "settle_steps": 80,
        "maximum_steps_per_waypoint": 1800,
        "goal_tolerance_m": 0.14,
        "drive_sign": -1.0,
        "record_stride": 50,
        "execution_layout": "single_genesis_scene_cross_seed_co_resident",
        "scene_build_count": 1,
        "fixed_seed_order": list(FORMAL_SEEDS),
        "non_fixed_robot_entities_per_trial": 3,
        "non_fixed_robot_entities_in_scene": EXPECTED_BODIES,
    }
    for field, expected in fixed_scientific_parameters.items():
        require(f"protocol.{field}", _get(report, "protocol", field), expected)
    require(
        "checkpoint_chain.empty_prefix_sha256",
        _get(report, "checkpoint_chain", "empty_prefix_sha256"),
        EMPTY_PREFIX_SHA256,
    )
    require(
        "checkpoint_chain.checkpoint_count",
        _get(report, "checkpoint_chain", "checkpoint_count"),
        EXPECTED_TRIALS,
    )
    require(
        "checkpoint_chain.content_hash_rule",
        _get(report, "checkpoint_chain", "content_hash_rule"),
        "SHA256(canonical checkpoint JSON with the checkpoint_content_sha256 field omitted)",
    )
    require(
        "checkpoint_chain.prefix_hash_rule",
        _get(report, "checkpoint_chain", "prefix_hash_rule"),
        "SHA256(canonical {previous_prefix_sha256, checkpoint_content_sha256})",
    )

    cases = _formal_cases()
    trials = report.get("trials")
    if not isinstance(trials, list):
        errors.append("trials: expected list")
        trials = []
    trial_seeds = [row.get("seed") for row in trials if isinstance(row, dict)]
    require("trial seed order", trial_seeds, list(FORMAL_SEEDS))
    if len(set(trial_seeds)) != len(trial_seeds):
        errors.append("trials contain duplicate seeds")
    if len(trials) != EXPECTED_TRIALS:
        errors.append(
            f"complete REPORT requires {EXPECTED_TRIALS} trials, observed {len(trials)}"
        )
    for index, case in enumerate(cases):
        if index >= len(trials) or not isinstance(trials[index], dict):
            errors.append(f"trial {case.seed}: missing complete trial")
            continue
        errors.extend(_trial_errors(trials[index], case, index))

    if len(trials) == EXPECTED_TRIALS and all(isinstance(row, dict) for row in trials):
        try:
            expected_summary = recompute_summary(trials)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            errors.append(f"summary cannot be recomputed: {exc}")
        else:
            require("summary", report.get("summary"), expected_summary)
            require("summary.all_passed", expected_summary["all_passed"], True)
            require("summary.passed", expected_summary["passed"], EXPECTED_TRIALS)
            require("summary.failed", expected_summary["failed"], 0)
            require(
                "summary.active_direct_decisions",
                expected_summary["active_direct_decisions"],
                EXPECTED_DIRECT,
            )
            require(
                "summary.active_safe_detours",
                expected_summary["active_safe_detours"],
                EXPECTED_SAFE_DETOURS,
            )
            require(
                "summary.distinct_non_fixed_robot_entities",
                expected_summary["distinct_non_fixed_robot_entities"],
                EXPECTED_BODIES,
            )
            if expected_summary["paired_mean_path_reduction_fraction"] < 0.15:
                errors.append("paired mean path reduction below fixed 15% floor")

    output_root = report_path.resolve().parent if report_path is not None else None
    if report_path is None:
        errors.append("report_path required for fail-closed artifact verification")
    elif report_path.name != "REPORT.json":
        errors.append("only an atomically sealed REPORT.json can be a full result")

    binding: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
    binding_digest = _get(report, "source", "source_binding_sha256")
    if output_root is not None:
        require(
            "source.source_binding_path",
            _get(report, "source", "source_binding_path"),
            "SOURCE_BINDING.json",
        )
        binding_path = _safe_child(
            output_root, _get(report, "source", "source_binding_path")
        )
        if binding_path is None or not binding_path.is_file():
            errors.append("source binding path missing or escapes output root")
        else:
            try:
                binding = _read_json_object(binding_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"source binding unreadable: {exc}")
            else:
                require(
                    "source binding schema",
                    binding.get("schema_version"),
                    BINDING_SCHEMA_VERSION,
                )
                require("source binding run_class", binding.get("run_class"), RUN_CLASS)
                require(
                    "source binding clean start",
                    binding.get("git_status_porcelain_at_start"),
                    "",
                )
                require(
                    "source binding sha256",
                    source_binding_sha256(binding),
                    binding_digest,
                )
                require(
                    "source binding report copy",
                    _get(report, "source", "source_files"),
                    binding.get("source_files"),
                )
                require(
                    "source binding decision sha256",
                    _get(binding, "decision_input", "sha256"),
                    EXPECTED_CHALLENGE_REPORT_SHA256,
                )
                require(
                    "source binding decision path",
                    _get(binding, "decision_input", "path"),
                    "release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json",
                )
                require(
                    "source binding decision consumed",
                    _get(binding, "decision_input", "consumed_in_this_run"),
                    True,
                )
                for field in (
                    "git_commit",
                    "git_branch",
                    "git_status_porcelain_at_start",
                ):
                    require(
                        f"report source {field}",
                        _get(report, "source", field),
                        binding.get(field),
                    )
                require(
                    "source binding scientific parameters",
                    binding.get("scientific_parameters"),
                    fixed_scientific_parameters,
                )
                candidate_identity = binding.get("attempt_identity")
                errors.extend(
                    _identity_errors(
                        candidate_identity, label="source binding identity"
                    )
                )
                if isinstance(candidate_identity, dict):
                    identity = {
                        key: candidate_identity.get(key) for key in IDENTITY_KEYS
                    }
                    require(
                        "report attempt_identity",
                        report.get("attempt_identity"),
                        identity,
                    )
                    for key, expected in identity.items():
                        require(
                            f"report execution.{key}",
                            _get(report, "execution", key),
                            expected,
                        )
                files = binding.get("source_files")
                if not isinstance(files, dict):
                    errors.append("source binding source_files: expected object")
                else:
                    missing_names = REQUIRED_SOURCE_NAMES - set(files)
                    unexpected_names = set(files) - REQUIRED_SOURCE_NAMES
                    if missing_names or unexpected_names:
                        errors.append(
                            "source binding file identity set mismatch: "
                            f"missing={sorted(missing_names)}, "
                            f"unexpected={sorted(unexpected_names)}"
                        )
                    require(
                        "source binding motion source path",
                        _get(files, "motion_source", "path"),
                        "src/v4_motion.py",
                    )
                    require(
                        "source binding fixed V1 runner hash",
                        _get(files, "v1_runner", "sha256"),
                        EXPECTED_V1_RUNNER_SHA256,
                    )
                    require(
                        "source binding decision-input file hash",
                        _get(files, "decision_input", "sha256"),
                        EXPECTED_CHALLENGE_REPORT_SHA256,
                    )
                    for name, row in files.items():
                        if not isinstance(row, dict):
                            errors.append(f"source binding row invalid: {name}")
                            continue
                        child = _safe_child(ROOT, row.get("path"))
                        if child is None or not child.is_file():
                            errors.append(
                                f"bound source missing or escapes root: {name}"
                            )
                        elif verify_local_source and sha256_file(child) != row.get(
                            "sha256"
                        ):
                            errors.append(f"bound source hash mismatch: {name}")

    checkpoint_index = report.get("checkpoint_index")
    if not isinstance(checkpoint_index, list):
        errors.append("checkpoint_index: expected list")
        checkpoint_index = []
    require(
        "checkpoint index seeds",
        [row.get("seed") for row in checkpoint_index if isinstance(row, dict)],
        list(FORMAL_SEEDS),
    )
    require(
        "checkpoint index trial ordinals",
        [row.get("trial_index") for row in checkpoint_index if isinstance(row, dict)],
        list(range(EXPECTED_TRIALS)),
    )
    if len(checkpoint_index) != EXPECTED_TRIALS:
        errors.append(
            "partial checkpoint prefix cannot be accepted as a complete REPORT: "
            f"observed {len(checkpoint_index)}/{EXPECTED_TRIALS}"
        )

    expected_checksum_paths = {"SOURCE_BINDING.json", "PROGRESS.json", "REPORT.json"}
    checkpoint_digests: list[str] = []
    expected_prefix_sha256 = EMPTY_PREFIX_SHA256
    if verify_artifacts and output_root is not None and binding is not None:
        for index, case in enumerate(cases):
            if index >= len(checkpoint_index) or not isinstance(
                checkpoint_index[index], dict
            ):
                errors.append(f"checkpoint {case.seed}: missing index row")
                continue
            row = checkpoint_index[index]
            checkpoint_path = _safe_child(output_root, row.get("path"))
            relative = f"TRIALS/{case.seed}.json"
            expected_checksum_paths.add(relative)
            require(f"checkpoint {case.seed} path", row.get("path"), relative)
            if checkpoint_path is None or not checkpoint_path.is_file():
                errors.append(f"checkpoint {case.seed}: missing or escapes output root")
                continue
            digest = sha256_file(checkpoint_path)
            checkpoint_digests.append(digest)
            require(f"checkpoint {case.seed} hash", row.get("sha256"), digest)
            try:
                checkpoint = _read_json_object(checkpoint_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"checkpoint {case.seed}: unreadable: {exc}")
                continue
            require(
                f"checkpoint {case.seed} schema",
                checkpoint.get("schema_version"),
                CHECKPOINT_SCHEMA_VERSION,
            )
            require(
                f"checkpoint {case.seed} run_class",
                checkpoint.get("run_class"),
                RUN_CLASS,
            )
            require(f"checkpoint {case.seed} seed", checkpoint.get("seed"), case.seed)
            require(
                f"checkpoint {case.seed} seed_index",
                checkpoint.get("seed_index"),
                index,
            )
            require(
                f"checkpoint {case.seed} trial_index",
                checkpoint.get("trial_index"),
                index,
            )
            require(
                f"checkpoint {case.seed} source binding",
                checkpoint.get("source_binding_sha256"),
                binding_digest,
            )
            require(
                f"checkpoint {case.seed} source preflight",
                checkpoint.get("source_binding_matched_preflight"),
                True,
            )
            require(
                f"checkpoint {case.seed} source postflight",
                checkpoint.get("source_binding_matched_postflight"),
                True,
            )
            require(
                f"checkpoint {case.seed} previous prefix",
                checkpoint.get("previous_prefix_sha256"),
                expected_prefix_sha256,
            )
            require(
                f"checkpoint index {case.seed} previous prefix",
                row.get("previous_prefix_sha256"),
                expected_prefix_sha256,
            )
            calculated_checkpoint_content_sha256 = checkpoint_content_sha256(checkpoint)
            require(
                f"checkpoint {case.seed} content hash",
                checkpoint.get("checkpoint_content_sha256"),
                calculated_checkpoint_content_sha256,
            )
            require(
                f"checkpoint index {case.seed} content hash",
                row.get("checkpoint_content_sha256"),
                calculated_checkpoint_content_sha256,
            )
            calculated_prefix_after = extend_prefix_sha256(
                expected_prefix_sha256, calculated_checkpoint_content_sha256
            )
            require(
                f"checkpoint index {case.seed} prefix after",
                row.get("prefix_sha256_after"),
                calculated_prefix_after,
            )
            require(
                f"checkpoint index {case.seed} partial evidence",
                row.get("partial_evidence_only"),
                True,
            )
            checkpoint_execution = checkpoint.get("execution")
            if not isinstance(checkpoint_execution, dict):
                errors.append(f"checkpoint {case.seed} execution: expected object")
            else:
                for field, expected in execution_expected.items():
                    require(
                        f"checkpoint {case.seed} execution.{field}",
                        checkpoint_execution.get(field),
                        expected,
                    )
                if identity is not None:
                    for key, expected in identity.items():
                        require(
                            f"checkpoint {case.seed} execution.{key}",
                            checkpoint_execution.get(key),
                            expected,
                        )
            if identity is not None:
                for key, expected in identity.items():
                    require(
                        f"checkpoint {case.seed}.{key}",
                        checkpoint.get(key),
                        expected,
                    )
            require(
                f"checkpoint {case.seed} partial_evidence_only",
                checkpoint.get("partial_evidence_only"),
                True,
            )
            require(
                f"checkpoint {case.seed} partial_checkpoints_are_full_results",
                checkpoint.get("partial_checkpoints_are_full_results"),
                False,
            )
            require(
                f"checkpoint {case.seed} resume_supported",
                checkpoint.get("resume_supported"),
                False,
            )
            timing = checkpoint.get("timing")
            if not isinstance(timing, dict):
                errors.append(f"checkpoint {case.seed} timing: expected object")
            else:
                wall_seconds = _finite_number(timing.get("wall_seconds"))
                if wall_seconds is None or wall_seconds < 0.0:
                    errors.append(
                        f"checkpoint {case.seed} timing.wall_seconds: invalid"
                    )
                for field in ("started_at_utc", "ended_at_utc"):
                    if not isinstance(timing.get(field), str) or not timing.get(field):
                        errors.append(f"checkpoint {case.seed} timing.{field}: missing")
                require(
                    f"checkpoint {case.seed} timing observability boundary",
                    timing.get("non_scientific_observability_only"),
                    True,
                )
            trial = checkpoint.get("trial")
            if not isinstance(trial, dict):
                errors.append(f"checkpoint {case.seed} trial: expected object")
                continue
            digest_trial = trial_sha256(trial)
            require(
                f"checkpoint {case.seed} trial_sha256",
                checkpoint.get("trial_sha256"),
                digest_trial,
            )
            require(
                f"checkpoint index {case.seed} trial_sha256",
                row.get("trial_sha256"),
                digest_trial,
            )
            if index < len(trials):
                require(
                    f"checkpoint {case.seed} report trial copy", trial, trials[index]
                )
            expected_prefix_sha256 = calculated_prefix_after

        progress_path = output_root / "PROGRESS.json"
        if not progress_path.is_file():
            errors.append("PROGRESS.json missing")
        else:
            try:
                progress = _read_json_object(progress_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"PROGRESS.json unreadable: {exc}")
            else:
                require(
                    "progress schema",
                    progress.get("schema_version"),
                    PROGRESS_SCHEMA_VERSION,
                )
                require("progress run_class", progress.get("run_class"), RUN_CLASS)
                require(
                    "progress source binding",
                    progress.get("source_binding_sha256"),
                    binding_digest,
                )
                require(
                    "progress fixed seed order",
                    progress.get("fixed_seed_order"),
                    list(FORMAL_SEEDS),
                )
                require(
                    "progress sealed count",
                    progress.get("sealed_prefix_count"),
                    EXPECTED_TRIALS,
                )
                require(
                    "progress sealed seeds",
                    progress.get("sealed_prefix_seeds"),
                    list(FORMAL_SEEDS),
                )
                require(
                    "progress sealed hashes",
                    progress.get("sealed_checkpoint_sha256"),
                    checkpoint_digests,
                )
                require(
                    "progress sealed prefix hash",
                    progress.get("sealed_prefix_sha256"),
                    expected_prefix_sha256,
                )
                require("progress next seed", progress.get("next_seed"), None)
                require(
                    "progress partial evidence",
                    progress.get("partial_evidence_only"),
                    True,
                )
                require(
                    "progress checkpoints not full results",
                    progress.get("partial_checkpoints_are_full_results"),
                    False,
                )
                require(
                    "progress resume_supported", progress.get("resume_supported"), False
                )
                require(
                    "progress outcomes hidden",
                    progress.get("outcomes_exposed_in_progress_file"),
                    False,
                )
                if identity is not None:
                    for key, expected in identity.items():
                        require(f"progress.{key}", progress.get(key), expected)
        require(
            "checkpoint_chain.final_prefix_sha256",
            _get(report, "checkpoint_chain", "final_prefix_sha256"),
            expected_prefix_sha256,
        )
        errors.extend(_checksum_errors(output_root, expected_checksum_paths))

    if identity is not None:
        environment_identity_fields = {
            "single_process_id": identity["process_id"],
            "process_identity": identity["process_identity"],
            "genesis_initialization_id": identity["genesis_initialization_id"],
            "single_scene_id": identity["single_scene_id"],
            "scene_build_id": identity["scene_build_id"],
        }
        for key, expected in environment_identity_fields.items():
            require(f"environment.{key}", _get(report, "environment", key), expected)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report_path = args.report.resolve()
    try:
        report = _read_json_object(report_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: report unreadable: {exc}")
        return 1
    errors = validate_report(report, report_path=report_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "PASS: additive decision-to-dynamics single-scene 60-body "
        f"{report['summary']['passed']}/{report['summary']['trials']} "
        f"report_sha256={sha256_file(report_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
