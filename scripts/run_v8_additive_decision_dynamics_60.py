#!/usr/bin/env python3
"""Run a checkpointed 60-body decision/dynamics supplement in one scene.

The formal run consumes only the immutable decisions for seeds 102500-102519.
All 20 independent worlds (three non-fixed robots per world) are added before
one ``scene.build()`` call and are then actuated in fixed seed order.  A
completed trial is published atomically as partial evidence, including failed
assessments.  These checkpoints cannot be resumed or combined across attempts:
an interrupted full result must start again in a new output directory and a
fresh single Genesis scene.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.run_v8_additive_decision_dynamics_bridge import (  # noqa: E402
    EXPECTED_CHALLENGE_REPORT_SHA256,
    ROBOT_SPECS,
    DecisionCase,
    _add_blockers,
    assess_trial,
    configure_velocity_control,
    drive_waypoints,
    git_output,
    load_formal_cases,
    sha256_file,
    trial_layout,
)


REPORT_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60/v1"
CHECKPOINT_SCHEMA_VERSION = (
    "look-twice.additive-decision-dynamics-60-checkpoint/v1"
)
BINDING_SCHEMA_VERSION = (
    "look-twice.additive-decision-dynamics-60-source-binding/v1"
)
PROGRESS_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-60-progress/v1"

FORMAL_SEEDS = tuple(range(102500, 102520))
ENGINEERING_SEEDS = (170860, 170861)
FROZEN_DT_SECONDS = 0.02
FROZEN_SETTLE_STEPS = 80
FROZEN_MAXIMUM_STEPS_PER_WAYPOINT = 1800
FROZEN_GOAL_TOLERANCE_M = 0.14
FROZEN_DRIVE_SIGN = -1.0
FROZEN_RECORD_STRIDE = 50
DEFAULT_INPUT_REPORT = (
    ROOT
    / "release"
    / "v8-frozen"
    / "results"
    / "challenge_102500_102529"
    / "CHALLENGE_REPORT.json"
)
DEFAULT_PROTOCOL = ROOT / "docs" / "V8_ADDITIVE_DECISION_DYNAMICS_60_PROTOCOL.md"
DEFAULT_VERIFIER = (
    ROOT / "scripts" / "verify_v8_additive_decision_dynamics_60.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_binding_sha256(binding: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(binding))


def trial_sha256(trial: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(trial))


def checkpoint_content_sha256(checkpoint: Mapping[str, Any]) -> str:
    """Hash a checkpoint without its self-referential content-hash field."""
    payload = dict(checkpoint)
    payload.pop("checkpoint_content_sha256", None)
    return sha256_bytes(canonical_json(payload))


EMPTY_PREFIX_SHA256 = sha256_bytes(canonical_json([]))


def extend_prefix_sha256(
    previous_prefix_sha256: str, checkpoint_sha256: str
) -> str:
    return sha256_bytes(
        canonical_json(
            {
                "previous_prefix_sha256": previous_prefix_sha256,
                "checkpoint_content_sha256": checkpoint_sha256,
            }
        )
    )


def new_attempt_identity() -> dict[str, Any]:
    process_id = os.getpid()
    attempt_id = sha256_bytes(
        f"{utc_now()}:{platform.node()}:{process_id}:".encode("utf-8")
        + os.urandom(32)
    )
    return {
        "attempt_id": attempt_id,
        "process_identity": f"{platform.node()}:pid:{process_id}",
        "process_id": process_id,
        "genesis_initialization_id": f"{attempt_id}:genesis-initialization-0",
        "single_scene_id": f"{attempt_id}:genesis-scene-0",
        "scene_build_id": f"{attempt_id}:scene-build-0",
    }


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, value: Any) -> None:
    """Atomically replace mutable progress metadata and fsync file + directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def atomic_publish_bytes(path: Path, payload: bytes) -> None:
    """Publish immutable bytes without ever replacing an existing final path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.unsealed")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_publish_json(path: Path, value: Any) -> None:
    atomic_publish_bytes(path, canonical_json(value))


def expected_cases(engineering_smoke: bool, input_report: Path) -> list[DecisionCase]:
    if engineering_smoke:
        return [
            DecisionCase(
                seed=ENGINEERING_SEEDS[0],
                selected_corridor="corridor_a",
                full_chain_direct=True,
                corridor_a_blocked=False,
                corridor_b_blocked=True,
                archived_episode_sha256="0" * 64,
                input_class="engineering_smoke",
            ),
            DecisionCase(
                seed=ENGINEERING_SEEDS[1],
                selected_corridor=None,
                full_chain_direct=False,
                corridor_a_blocked=True,
                corridor_b_blocked=True,
                archived_episode_sha256="1" * 64,
                input_class="engineering_smoke",
            ),
        ]
    cases = load_formal_cases(input_report)[: len(FORMAL_SEEDS)]
    if tuple(case.seed for case in cases) != FORMAL_SEEDS:
        raise RuntimeError("immutable challenge report formal prefix mismatch")
    return cases


def frozen_parameter_errors(args: argparse.Namespace) -> list[str]:
    expected = {
        "dt": FROZEN_DT_SECONDS,
        "settle_steps": FROZEN_SETTLE_STEPS,
        "maximum_steps_per_waypoint": FROZEN_MAXIMUM_STEPS_PER_WAYPOINT,
        "tolerance": FROZEN_GOAL_TOLERANCE_M,
        "drive_sign": FROZEN_DRIVE_SIGN,
        "record_stride": FROZEN_RECORD_STRIDE,
    }
    errors = [
        f"{name}: expected frozen value {value!r}, observed {getattr(args, name)!r}"
        for name, value in expected.items()
        if getattr(args, name) != value
    ]
    if not args.engineering_smoke and args.backend != "amdgpu":
        errors.append(
            f"backend: formal run requires 'amdgpu', observed {args.backend!r}"
        )
    return errors


def scientific_parameters(args: argparse.Namespace) -> dict[str, Any]:
    seeds = ENGINEERING_SEEDS if args.engineering_smoke else FORMAL_SEEDS
    return {
        "backend": args.backend,
        "dt_seconds": args.dt,
        "settle_steps": args.settle_steps,
        "maximum_steps_per_waypoint": args.maximum_steps_per_waypoint,
        "goal_tolerance_m": args.tolerance,
        "drive_sign": args.drive_sign,
        "record_stride": args.record_stride,
        "execution_layout": "single_genesis_scene_cross_seed_co_resident",
        "scene_build_count": 1,
        "fixed_seed_order": list(seeds),
        "non_fixed_robot_entities_per_trial": 3,
        "non_fixed_robot_entities_in_scene": 3 * len(seeds),
    }


def bound_source_paths(input_report: Path) -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "verifier": DEFAULT_VERIFIER,
        "fixed_protocol": DEFAULT_PROTOCOL,
        "v1_runner": ROOT / "scripts" / "run_v8_additive_decision_dynamics_bridge.py",
        "dual_body_helper": ROOT / "scripts" / "run_v8_additive_dual_body_dynamics.py",
        "scenario_source": ROOT / "src" / "v6_scenario.py",
        "motion_source": ROOT / "src" / "v4_motion.py",
        "carrier_urdf": ROBOT_SPECS["carrier"].urdf,
        "scout_urdf": ROBOT_SPECS["scout"].urdf,
        "decision_input": input_report,
    }


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def build_source_binding(
    args: argparse.Namespace, attempt_identity: Mapping[str, Any]
) -> dict[str, Any]:
    paths = bound_source_paths(args.input_report)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing bound source files: {missing}")
    input_sha = sha256_file(args.input_report)
    if not args.engineering_smoke and input_sha != EXPECTED_CHALLENGE_REPORT_SHA256:
        raise RuntimeError(
            "immutable decision input mismatch: "
            f"expected {EXPECTED_CHALLENGE_REPORT_SHA256}, observed {input_sha}"
        )
    git_status = git_output("status", "--porcelain", "--untracked-files=all")
    if not args.engineering_smoke and git_status != "":
        raise RuntimeError(
            f"formal 60-body run requires a clean source tree; observed:\n{git_status}"
        )
    return {
        "schema_version": BINDING_SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "run_class": "engineering_smoke" if args.engineering_smoke else "formal",
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_branch": git_output("branch", "--show-current"),
        "git_status_porcelain_at_start": git_status,
        "attempt_identity": dict(attempt_identity),
        "scientific_parameters": scientific_parameters(args),
        "source_files": {
            name: {"path": _relative(path), "sha256": sha256_file(path)}
            for name, path in paths.items()
        },
        "decision_input": {
            "path": _relative(args.input_report),
            "sha256": input_sha,
            "consumed_in_this_run": not args.engineering_smoke,
        },
        "integrity_rule": (
            "Every completed trial is immutable partial evidence from this one "
            "live scene. Checkpoints may not be resumed, replaced, selectively "
            "omitted, or combined across attempts into a full result."
        ),
    }


def binding_errors(
    binding: Mapping[str, Any], args: argparse.Namespace
) -> list[str]:
    errors: list[str] = []
    expected_class = "engineering_smoke" if args.engineering_smoke else "formal"
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        errors.append("source binding schema mismatch")
    if binding.get("run_class") != expected_class:
        errors.append("source binding run class mismatch")
    if binding.get("scientific_parameters") != scientific_parameters(args):
        errors.append("scientific parameters changed after source binding")
    if binding.get("git_commit") != git_output("rev-parse", "HEAD"):
        errors.append("git commit changed after source binding")
    identity = binding.get("attempt_identity")
    if not isinstance(identity, Mapping):
        errors.append("attempt identity missing from source binding")
    elif identity.get("process_id") != os.getpid():
        errors.append("bound process identity does not match live process")
    files = binding.get("source_files")
    if not isinstance(files, Mapping):
        return [*errors, "source binding file map missing"]
    for name, path in bound_source_paths(args.input_report).items():
        row = files.get(name)
        if not isinstance(row, Mapping):
            errors.append(f"bound source missing: {name}")
            continue
        if row.get("path") != _relative(path):
            errors.append(f"bound source path changed: {name}")
        if not path.is_file() or row.get("sha256") != sha256_file(path):
            errors.append(f"bound source bytes changed: {name}")
    return errors


def _execution_facts(
    *,
    run_class: str,
    trial_count: int,
    attempt_identity: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **dict(attempt_identity),
        "layout": "single_genesis_scene_60_non_fixed_bodies"
        if run_class == "formal"
        else "single_genesis_scene_engineering_smoke",
        "genesis_scene_count": 1,
        "scene_build_count": 1,
        "cross_seed_entities_share_scene": True,
        "non_fixed_robot_entities_in_scene": 3 * trial_count,
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


def checkpoint_errors(
    checkpoint: Mapping[str, Any],
    *,
    case: DecisionCase,
    trial_index: int,
    run_class: str,
    binding_sha256: str,
    attempt_identity: Mapping[str, Any],
    trial_count: int,
    previous_prefix_sha256: str,
) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, observed {actual!r}")

    require("schema_version", checkpoint.get("schema_version"), CHECKPOINT_SCHEMA_VERSION)
    require("run_class", checkpoint.get("run_class"), run_class)
    require("trial_index", checkpoint.get("trial_index"), trial_index)
    require("seed", checkpoint.get("seed"), case.seed)
    require("source_binding_sha256", checkpoint.get("source_binding_sha256"), binding_sha256)
    for name, expected in attempt_identity.items():
        require(name, checkpoint.get(name), expected)
    trial = checkpoint.get("trial")
    if not isinstance(trial, Mapping):
        return [*errors, "trial payload missing"]
    require("trial.seed", trial.get("seed"), case.seed)
    require("trial_sha256", checkpoint.get("trial_sha256"), trial_sha256(trial))
    require(
        "checkpoint_content_sha256",
        checkpoint.get("checkpoint_content_sha256"),
        checkpoint_content_sha256(checkpoint),
    )
    require(
        "previous_prefix_sha256",
        checkpoint.get("previous_prefix_sha256"),
        previous_prefix_sha256,
    )
    require("source_binding_matched_preflight", checkpoint.get("source_binding_matched_preflight"), True)
    require("source_binding_matched_postflight", checkpoint.get("source_binding_matched_postflight"), True)
    execution = checkpoint.get("execution")
    expected_execution = _execution_facts(
        run_class=run_class,
        trial_count=trial_count,
        attempt_identity=attempt_identity,
    )
    if execution != expected_execution:
        errors.append("checkpoint execution identity mismatch")
    try:
        expected_assessment = assess_trial(dict(trial))
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"trial assessment cannot be recomputed: {exc}")
    else:
        require("trial.assessment", trial.get("assessment"), expected_assessment)
    return errors


def summarize_trials(trials: Sequence[dict[str, Any]], run_class: str) -> dict[str, Any]:
    expected = {
        "formal": {"trials": 20, "direct": 19, "safe_detour": 1, "floor": 0.15},
        "engineering_smoke": {"trials": 2, "direct": 1, "safe_detour": 1, "floor": 0.10},
    }[run_class]
    active_paths = [float(row["active_carrier"]["path_length_m"]) for row in trials]
    passive_paths = [float(row["passive_carrier"]["path_length_m"]) for row in trials]
    scout_rows = [row["active_scout"] for row in trials]
    body_rows = [
        body
        for trial in trials
        for body in (
            trial["active_scout"],
            trial["active_carrier"],
            trial["passive_carrier"],
        )
    ]
    tilt_values = [float(row["max_tilt_deg"]) for row in body_rows]
    drift_values = [
        float(row[role]["stationary_partner_drift_m"])
        for row in trials
        for role in ("active_scout", "active_carrier")
    ]
    metric_values = [*active_paths, *passive_paths, *tilt_values, *drift_values]
    metrics_finite = bool(active_paths) and all(
        math.isfinite(value) for value in metric_values
    )
    mean_active = statistics.fmean(active_paths) if metrics_finite else 0.0
    mean_passive = statistics.fmean(passive_paths) if metrics_finite else 0.0
    reduction_valid = metrics_finite and mean_passive > 0.0
    reduction = (
        (mean_passive - mean_active) / mean_passive if reduction_valid else 0.0
    )
    if not math.isfinite(reduction):
        reduction = 0.0
        reduction_valid = False
    direct_trials = [row for row in trials if row["decision"]["full_chain_direct"]]
    safe_detours = [row for row in trials if not row["decision"]["full_chain_direct"]]
    passed = sum(bool(row["assessment"]["passed"]) for row in trials)
    direct_savings = [
        float(row["passive_carrier"]["path_length_m"])
        - float(row["active_carrier"]["path_length_m"])
        for row in direct_trials
    ]
    direct_savings_valid = all(math.isfinite(value) for value in direct_savings)
    direct_saving_checks = [
        math.isfinite(value) and value >= 0.50 for value in direct_savings
    ]
    aggregate_checks = {
        "fixed_denominator_complete": len(trials) == expected["trials"],
        "expected_decision_counts": len(direct_trials) == expected["direct"]
        and len(safe_detours) == expected["safe_detour"],
        "all_trials_passed": passed == len(trials),
        "all_reported_metrics_finite_and_denominator_positive": reduction_valid
        and direct_savings_valid,
        "mean_loaded_carrier_path_reduction_meets_run_class_floor": reduction_valid
        and reduction >= expected["floor"],
        "every_direct_pair_saved_at_least_0_50_m": direct_savings_valid
        and all(direct_saving_checks),
    }
    return {
        "trials": len(trials),
        "passed": passed,
        "failed": len(trials) - passed,
        "all_passed": all(aggregate_checks.values()),
        "active_direct_decisions": len(direct_trials),
        "active_safe_detours": len(safe_detours),
        "distinct_non_fixed_robot_entities": 3 * len(trials),
        "active_scout_reached": sum(bool(row["reached"]) for row in scout_rows),
        "active_carrier_reached": sum(bool(row["active_carrier"]["reached"]) for row in trials),
        "passive_carrier_reached": sum(bool(row["passive_carrier"]["reached"]) for row in trials),
        "mean_active_loaded_carrier_path_m": mean_active,
        "mean_passive_loaded_carrier_path_m": mean_passive,
        "paired_mean_path_reduction_fraction": reduction,
        "paired_mean_path_reduction_percent": 100.0 * reduction,
        "minimum_mean_path_reduction_fraction": expected["floor"],
        "direct_pairs_saving_at_least_0_50_m": sum(direct_saving_checks),
        "total_blocker_contact_rows": sum(
            int(body["obstacle_contact_rows"])
            + int(body["stationary_obstacle_contact_rows"])
            for body in body_rows
        ),
        "total_active_pair_contact_rows": sum(
            int(row[role]["partner_contact_rows"])
            for row in trials
            for role in ("active_scout", "active_carrier")
        ),
        "maximum_tilt_deg": max(tilt_values, default=0.0)
        if metrics_finite
        else 0.0,
        "maximum_stationary_partner_drift_m": max(drift_values, default=0.0)
        if metrics_finite
        else 0.0,
        "aggregate_checks": aggregate_checks,
    }


def _progress_payload(
    *,
    run_class: str,
    cases: Sequence[DecisionCase],
    binding_sha256: str,
    attempt_identity: Mapping[str, Any],
    checkpoint_paths: Sequence[Path],
    prefix_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "updated_at_utc": utc_now(),
        "run_class": run_class,
        **dict(attempt_identity),
        "source_binding_sha256": binding_sha256,
        "fixed_seed_order": [case.seed for case in cases],
        "sealed_prefix_count": len(checkpoint_paths),
        "sealed_prefix_seeds": [int(path.stem) for path in checkpoint_paths],
        "sealed_checkpoint_sha256": [sha256_file(path) for path in checkpoint_paths],
        "sealed_prefix_sha256": prefix_sha256,
        "next_seed": cases[len(checkpoint_paths)].seed
        if len(checkpoint_paths) < len(cases)
        else None,
        "partial_evidence_only": True,
        "partial_checkpoints_are_full_results": False,
        "resume_supported": False,
        "outcomes_exposed_in_progress_file": False,
    }


def _build_report(
    *,
    args: argparse.Namespace,
    binding: dict[str, Any],
    cases: Sequence[DecisionCase],
    trials: list[dict[str, Any]],
    checkpoint_paths: Sequence[Path],
    output_dir: Path,
    attempt_identity: Mapping[str, Any],
    environment: dict[str, Any],
) -> dict[str, Any]:
    run_class = binding["run_class"]
    summary = summarize_trials(trials, run_class)
    execution = _execution_facts(
        run_class=run_class,
        trial_count=len(cases),
        attempt_identity=attempt_identity,
    )
    checkpoint_index: list[dict[str, Any]] = []
    prefix_sha = EMPTY_PREFIX_SHA256
    for index, (case, path) in enumerate(zip(cases, checkpoint_paths, strict=True)):
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint.get("previous_prefix_sha256") != prefix_sha:
            raise RuntimeError(f"checkpoint prefix chain mismatch at seed {case.seed}")
        content_sha = checkpoint_content_sha256(checkpoint)
        if checkpoint.get("checkpoint_content_sha256") != content_sha:
            raise RuntimeError(f"checkpoint content hash mismatch at seed {case.seed}")
        prefix_after = extend_prefix_sha256(prefix_sha, content_sha)
        checkpoint_index.append(
            {
                "trial_index": index,
                "seed": case.seed,
                "path": str(path.relative_to(output_dir)),
                "sha256": sha256_file(path),
                "trial_sha256": trial_sha256(trials[index]),
                "previous_prefix_sha256": prefix_sha,
                "checkpoint_content_sha256": content_sha,
                "prefix_sha256_after": prefix_after,
                "partial_evidence_only": True,
            }
        )
        prefix_sha = prefix_after
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "run_class": run_class,
        "attempt_identity": dict(attempt_identity),
        "boundary": {
            "additive_non_locked": True,
            "formal_result_eligible": False,
            "changes_frozen_v8_endpoint": False,
            "uses_archived_decisions_without_rerunning_policy": not args.engineering_smoke,
            "oracle_used_by_controller": False,
            "single_scene_60_body_execution": run_class == "formal",
            "cross_seed_entities_co_resident": True,
            "fixed_order_serial_actuation": True,
            "simultaneous_cooperative_control": False,
            "partial_checkpoints_are_full_results": False,
            "resume_supported": False,
            "teardown_guard_enabled": True,
            "claim": (
                "Receipt-bound rigid-dynamics replay of 20 archived decisions in "
                "one 60-body Genesis scene; partial checkpoints preserve completed "
                "trials but are not a resumable or standalone full result."
                if run_class == "formal"
                else "Small-denominator single-scene engineering smoke only."
            ),
        },
        "source": {
            "git_commit": binding["git_commit"],
            "git_branch": binding["git_branch"],
            "git_status_porcelain_at_start": binding["git_status_porcelain_at_start"],
            "source_binding_path": "SOURCE_BINDING.json",
            "source_binding_sha256": source_binding_sha256(binding),
            "source_files": binding["source_files"],
        },
        "decision_input": {
            **binding["decision_input"],
            "fixed_seeds": [case.seed for case in cases],
        },
        "execution": execution,
        "checkpoint_chain": {
            "empty_prefix_sha256": EMPTY_PREFIX_SHA256,
            "final_prefix_sha256": prefix_sha,
            "checkpoint_count": len(checkpoint_index),
            "content_hash_rule": (
                "SHA256(canonical checkpoint JSON with the "
                "checkpoint_content_sha256 field omitted)"
            ),
            "prefix_hash_rule": (
                "SHA256(canonical {previous_prefix_sha256, "
                "checkpoint_content_sha256})"
            ),
        },
        "environment": environment,
        "protocol": {
            **binding["scientific_parameters"],
            "post_build_controller_configuration_apis": [
                "set_dofs_kp",
                "set_dofs_kv",
                "set_dofs_force_range",
            ],
            "post_build_motion_actuation_api": "control_dofs_velocity only",
            "post_build_entity_pose_writes": 0,
            "route_binding": (
                "active direct corridor or safe detour is read from the archived "
                "challenge result; passive always follows the fixed outer detour"
            ),
            "checkpoint_policy": (
                "publish every completed trial exactly once, including failed "
                "assessments; never resume or combine checkpoints across attempts"
            ),
        },
        "checkpoint_index": checkpoint_index,
        "summary": summary,
        "trials": trials,
    }


def run(args: argparse.Namespace) -> int:
    args.input_report = args.input_report.resolve()
    args.output_dir = args.output_dir.resolve()
    parameter_errors = frozen_parameter_errors(args)
    if parameter_errors:
        raise RuntimeError(
            "protocol parameters are frozen: " + "; ".join(parameter_errors)
        )
    if args.output_dir.exists():
        raise RuntimeError(f"refusing to overwrite output directory: {args.output_dir}")

    cases = expected_cases(args.engineering_smoke, args.input_report)
    run_class = "engineering_smoke" if args.engineering_smoke else "formal"
    attempt_identity = new_attempt_identity()
    binding = build_source_binding(args, attempt_identity)
    binding_sha = source_binding_sha256(binding)

    args.output_dir.mkdir(parents=True, exist_ok=False)
    _fsync_directory(args.output_dir.parent)
    binding_path = args.output_dir / "SOURCE_BINDING.json"
    progress_path = args.output_dir / "PROGRESS.json"
    trials_dir = args.output_dir / "TRIALS"
    report_path = args.output_dir / "REPORT.json"
    sums_path = args.output_dir / "SHA256SUMS"
    atomic_publish_json(binding_path, binding)
    atomic_write_json(
        progress_path,
        _progress_payload(
            run_class=run_class,
            cases=cases,
            binding_sha256=binding_sha,
            attempt_identity=attempt_identity,
            checkpoint_paths=[],
            prefix_sha256=EMPTY_PREFIX_SHA256,
        ),
    )

    import genesis as gs
    import torch

    backend = gs.amdgpu if args.backend == "amdgpu" else gs.cpu
    gs.init(backend=backend, logging_level="warning")
    scene = gs.Scene(show_viewer=False, sim_options=gs.options.SimOptions(dt=args.dt))
    scene.add_entity(gs.morphs.Plane())
    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        layout = trial_layout(case, index)
        active_carrier = scene.add_entity(
            gs.morphs.URDF(
                file=str(ROBOT_SPECS["carrier"].urdf),
                pos=layout["active_carrier_start"],
                fixed=False,
            ),
            name=f"active-carrier-{case.seed}",
        )
        active_scout = scene.add_entity(
            gs.morphs.URDF(
                file=str(ROBOT_SPECS["scout"].urdf),
                pos=layout["active_scout_start"],
                fixed=False,
            ),
            name=f"active-scout-{case.seed}",
        )
        passive_carrier = scene.add_entity(
            gs.morphs.URDF(
                file=str(ROBOT_SPECS["carrier"].urdf),
                pos=layout["passive_carrier_start"],
                fixed=False,
            ),
            name=f"passive-carrier-{case.seed}",
        )
        active_blockers = _add_blockers(
            scene, gs, layout["active_blocker_positions"], f"active-blocker-{case.seed}"
        )
        passive_blockers = _add_blockers(
            scene,
            gs,
            layout["passive_blocker_positions"],
            f"passive-blocker-{case.seed}",
        )
        records.append(
            {
                "case": case,
                "layout": layout,
                "active_carrier": active_carrier,
                "active_scout": active_scout,
                "passive_carrier": passive_carrier,
                "active_blockers": active_blockers,
                "passive_blockers": passive_blockers,
            }
        )

    # The single build is the defining topology of this supplement.
    scene.build()
    for record in records:
        record["active_carrier_indices"] = configure_velocity_control(
            record["active_carrier"], ROBOT_SPECS["carrier"]
        )
        record["active_scout_indices"] = configure_velocity_control(
            record["active_scout"], ROBOT_SPECS["scout"]
        )
        record["passive_carrier_indices"] = configure_velocity_control(
            record["passive_carrier"], ROBOT_SPECS["carrier"]
        )
    for _ in range(args.settle_steps):
        scene.step()

    environment = {
        "python": platform.python_version(),
        "genesis": gs.__version__,
        "torch": torch.__version__,
        "torch_hip": torch.version.hip,
        "backend_requested": args.backend,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "single_process_id": os.getpid(),
        "process_identity": attempt_identity["process_identity"],
        "genesis_initialization_id": attempt_identity["genesis_initialization_id"],
        "single_scene_id": attempt_identity["single_scene_id"],
        "scene_build_id": attempt_identity["scene_build_id"],
    }
    trials: list[dict[str, Any]] = []
    checkpoint_paths: list[Path] = []
    prefix_sha = EMPTY_PREFIX_SHA256
    for trial_index, record in enumerate(records):
        trial_started_at_utc = utc_now()
        trial_started_monotonic = time.monotonic()
        case: DecisionCase = record["case"]
        layout = record["layout"]
        scout_result = drive_waypoints(
            scene=scene,
            entity=record["active_scout"],
            indices=record["active_scout_indices"],
            spec=ROBOT_SPECS["scout"],
            waypoints=layout["active_scout_waypoints"],
            stationary=((record["active_carrier"], record["active_carrier_indices"]),),
            blockers=record["active_blockers"],
            partners=(record["active_carrier"],),
            drive_sign=args.drive_sign,
            maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
            tolerance_m=args.tolerance,
            record_stride=args.record_stride,
        )
        active_result = drive_waypoints(
            scene=scene,
            entity=record["active_carrier"],
            indices=record["active_carrier_indices"],
            spec=ROBOT_SPECS["carrier"],
            waypoints=layout["active_carrier_waypoints"],
            stationary=((record["active_scout"], record["active_scout_indices"]),),
            blockers=record["active_blockers"],
            partners=(record["active_scout"],),
            drive_sign=args.drive_sign,
            maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
            tolerance_m=args.tolerance,
            record_stride=args.record_stride,
        )
        passive_result = drive_waypoints(
            scene=scene,
            entity=record["passive_carrier"],
            indices=record["passive_carrier_indices"],
            spec=ROBOT_SPECS["carrier"],
            waypoints=layout["passive_carrier_waypoints"],
            stationary=(),
            blockers=record["passive_blockers"],
            partners=(),
            drive_sign=args.drive_sign,
            maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
            tolerance_m=args.tolerance,
            record_stride=args.record_stride,
        )
        trial = {
            "seed": case.seed,
            "decision": {
                "selected_corridor": case.selected_corridor,
                "full_chain_direct": case.full_chain_direct,
                "corridor_a_blocked": case.corridor_a_blocked,
                "corridor_b_blocked": case.corridor_b_blocked,
                "selected_corridor_clear": case.selected_corridor_clear,
                "both_corridors_blocked": case.both_corridors_blocked,
                "archived_episode_sha256": case.archived_episode_sha256,
                "input_class": case.input_class,
            },
            "blocked_corridors": layout["blocked_corridors"],
            "script_entity_pose_writes_after_build": 0,
            "active_scout": scout_result,
            "active_carrier": active_result,
            "passive_carrier": passive_result,
        }
        trial["assessment"] = assess_trial(trial)
        trial_ended_at_utc = utc_now()
        trial_wall_seconds = time.monotonic() - trial_started_monotonic
        postflight_errors = binding_errors(binding, args)
        if postflight_errors:
            raise RuntimeError(
                "source binding changed during live scene: "
                + "; ".join(postflight_errors)
            )
        checkpoint = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "run_class": run_class,
            **dict(attempt_identity),
            "trial_index": trial_index,
            "seed_index": trial_index,
            "seed": case.seed,
            "source_binding_sha256": binding_sha,
            "trial_sha256": trial_sha256(trial),
            "previous_prefix_sha256": prefix_sha,
            "source_binding_matched_preflight": True,
            "source_binding_matched_postflight": True,
            "partial_evidence_only": True,
            "partial_checkpoints_are_full_results": False,
            "resume_supported": False,
            "timing": {
                "started_at_utc": trial_started_at_utc,
                "ended_at_utc": trial_ended_at_utc,
                "wall_seconds": trial_wall_seconds,
                "non_scientific_observability_only": True,
            },
            "execution": _execution_facts(
                run_class=run_class,
                trial_count=len(cases),
                attempt_identity=attempt_identity,
            ),
            "trial": trial,
        }
        checkpoint["checkpoint_content_sha256"] = checkpoint_content_sha256(checkpoint)
        checkpoint_path = trials_dir / f"{case.seed}.json"
        atomic_publish_json(checkpoint_path, checkpoint)
        observed = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        errors = checkpoint_errors(
            observed,
            case=case,
            trial_index=trial_index,
            run_class=run_class,
            binding_sha256=binding_sha,
            attempt_identity=attempt_identity,
            trial_count=len(cases),
            previous_prefix_sha256=prefix_sha,
        )
        if errors:
            raise RuntimeError(
                f"sealed checkpoint {case.seed} failed closed: " + "; ".join(errors)
            )
        trials.append(trial)
        checkpoint_paths.append(checkpoint_path)
        prefix_sha = extend_prefix_sha256(
            prefix_sha, str(checkpoint["checkpoint_content_sha256"])
        )
        atomic_write_json(
            progress_path,
            _progress_payload(
                run_class=run_class,
                cases=cases,
                binding_sha256=binding_sha,
                attempt_identity=attempt_identity,
                checkpoint_paths=checkpoint_paths,
                prefix_sha256=prefix_sha,
            ),
        )
        print(
            f"sealed partial {len(trials)}/{len(cases)} seed={case.seed} "
            f"passed={bool(trial['assessment']['passed'])} "
            f"checkpoint_sha256={sha256_file(checkpoint_path)}",
            flush=True,
        )

    final_binding_errors = binding_errors(binding, args)
    if final_binding_errors:
        raise RuntimeError(
            "source binding changed before report: " + "; ".join(final_binding_errors)
        )
    report = _build_report(
        args=args,
        binding=binding,
        cases=cases,
        trials=trials,
        checkpoint_paths=checkpoint_paths,
        output_dir=args.output_dir,
        attempt_identity=attempt_identity,
        environment=environment,
    )
    # A failing scientific aggregate is still a complete immutable result.
    atomic_publish_json(report_path, report)
    checksum_paths = [binding_path, progress_path, *checkpoint_paths, report_path]
    checksum_payload = "".join(
        f"{sha256_file(path)}  {path.relative_to(args.output_dir)}\n"
        for path in checksum_paths
    ).encode("utf-8")
    atomic_publish_bytes(sums_path, checksum_payload)
    summary = report["summary"]
    print(
        f"{run_class}: {summary['passed']}/{summary['trials']} trials; "
        f"loaded-carrier path reduction={summary['paired_mean_path_reduction_percent']:.3f}% "
        f"report_sha256={sha256_file(report_path)}",
        flush=True,
    )
    return 0 if summary["all_passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-report", type=Path, default=DEFAULT_INPUT_REPORT)
    parser.add_argument("--backend", choices=("amdgpu", "cpu"), default="amdgpu")
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--dt", type=float, default=FROZEN_DT_SECONDS)
    parser.add_argument("--settle-steps", type=int, default=FROZEN_SETTLE_STEPS)
    parser.add_argument(
        "--maximum-steps-per-waypoint",
        type=int,
        default=FROZEN_MAXIMUM_STEPS_PER_WAYPOINT,
    )
    parser.add_argument("--tolerance", type=float, default=FROZEN_GOAL_TOLERANCE_M)
    parser.add_argument("--drive-sign", type=float, default=FROZEN_DRIVE_SIGN)
    parser.add_argument("--record-stride", type=int, default=FROZEN_RECORD_STRIDE)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dt <= 0.0 or args.tolerance <= 0.0:
        raise SystemExit("dt and tolerance must be positive")
    if args.settle_steps < 0:
        raise SystemExit("settle steps must be non-negative")
    if args.maximum_steps_per_waypoint < 1 or args.record_stride < 1:
        raise SystemExit("step and record-stride values must be positive")
    if not math.isfinite(args.drive_sign) or args.drive_sign == 0.0:
        raise SystemExit("drive sign must be finite and non-zero")
    return run(args)


if __name__ == "__main__":
    exit_code = main()
    # Genesis 1.1.2 may fault during interpreter-global ROCm teardown after all
    # evidence has been durably sealed. Avoid that unrelated destructor path.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
