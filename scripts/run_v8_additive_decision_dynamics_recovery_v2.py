#!/usr/bin/env python3
"""Checkpointed, seed-isolated recovery for the V8 decision/dynamics bridge.

The V1 formal runner placed all 30 independent worlds in one Genesis scene and
then drove them sequentially.  That preserved the intended per-world physics
but made every scene step pay for 90 dynamic bodies.  This recovery runner
keeps every scientific input and every within-seed interaction unchanged while
executing one fixed seed per fresh Genesis subprocess.  A completed seed is
sealed atomically and is never rerun or replaced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v8_additive_decision_dynamics_bridge import (  # noqa: E402
    EXPECTED_CHALLENGE_REPORT_SHA256,
    FORMAL_SEEDS,
    ROBOT_SPECS,
    DecisionCase,
    _add_blockers,
    assess_trial,
    configure_velocity_control,
    drive_waypoints,
    engineering_smoke_cases,
    git_output,
    load_formal_cases,
    sha256_file,
    summarize_trials,
    trial_layout,
)


REPORT_SCHEMA_VERSION = "look-twice.additive-decision-dynamics-recovery-v2/v1"
CHECKPOINT_SCHEMA_VERSION = (
    "look-twice.additive-decision-dynamics-recovery-v2-checkpoint/v1"
)
BINDING_SCHEMA_VERSION = (
    "look-twice.additive-decision-dynamics-recovery-v2-source-binding/v1"
)
PROGRESS_SCHEMA_VERSION = (
    "look-twice.additive-decision-dynamics-recovery-v2-progress/v1"
)
ENGINEERING_SEEDS = (170800, 170801, 170802)
DEFAULT_INPUT_REPORT = (
    ROOT
    / "release"
    / "v8-frozen"
    / "results"
    / "challenge_102500_102529"
    / "CHALLENGE_REPORT.json"
)
DEFAULT_PROTOCOL = (
    ROOT / "docs" / "V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROTOCOL.md"
)
DEFAULT_VERIFIER = (
    ROOT / "scripts" / "verify_v8_additive_decision_dynamics_recovery_v2.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_publish_json(path: Path, value: Any) -> None:
    """Publish an immutable JSON file; fail if the final name already exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.unsealed")
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def append_json_line(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def expected_cases(engineering_smoke: bool, input_report: Path) -> list[DecisionCase]:
    return (
        engineering_smoke_cases()
        if engineering_smoke
        else load_formal_cases(input_report)
    )


def scientific_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "backend": args.backend,
        "dt_seconds": args.dt,
        "settle_steps": args.settle_steps,
        "maximum_steps_per_waypoint": args.maximum_steps_per_waypoint,
        "goal_tolerance_m": args.tolerance,
        "drive_sign": args.drive_sign,
        "record_stride": args.record_stride,
        "worker_timeout_seconds": args.worker_timeout_seconds,
        "execution_layout": "one_fixed_seed_per_fresh_genesis_subprocess",
        "seed_order": list(
            ENGINEERING_SEEDS if args.engineering_smoke else FORMAL_SEEDS
        ),
    }


def bound_source_paths(input_report: Path) -> dict[str, Path]:
    return {
        "runner": Path(__file__).resolve(),
        "verifier": DEFAULT_VERIFIER,
        "fixed_protocol": DEFAULT_PROTOCOL,
        "v1_runner": ROOT / "scripts" / "run_v8_additive_decision_dynamics_bridge.py",
        "dual_body_helper": ROOT / "scripts" / "run_v8_additive_dual_body_dynamics.py",
        "scenario_source": ROOT / "src" / "v6_scenario.py",
        "carrier_urdf": ROBOT_SPECS["carrier"].urdf,
        "scout_urdf": ROBOT_SPECS["scout"].urdf,
        "decision_input": input_report,
    }


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def build_source_binding(args: argparse.Namespace) -> dict[str, Any]:
    paths = bound_source_paths(args.input_report)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing bound source files: {missing}")
    git_status = git_output("status", "--porcelain", "--untracked-files=all")
    if not args.engineering_smoke and git_status != "":
        raise RuntimeError(
            f"formal V2 must start from a clean source tree; observed:\n{git_status}"
        )
    input_sha = sha256_file(args.input_report)
    if input_sha != EXPECTED_CHALLENGE_REPORT_SHA256:
        raise RuntimeError(
            "immutable decision input mismatch: "
            f"expected {EXPECTED_CHALLENGE_REPORT_SHA256}, observed {input_sha}"
        )
    binding = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "run_class": "engineering_smoke" if args.engineering_smoke else "formal",
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_branch": git_output("branch", "--show-current"),
        "git_status_porcelain_at_initial_start": git_status,
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
            "Once any fixed-seed checkpoint is sealed, this binding and every "
            "bound source byte must remain unchanged. Completed checkpoints are "
            "never rerun, replaced, or selectively omitted."
        ),
    }
    return binding


def binding_errors(binding: dict[str, Any], args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if binding.get("schema_version") != BINDING_SCHEMA_VERSION:
        errors.append("source binding schema mismatch")
    expected_class = "engineering_smoke" if args.engineering_smoke else "formal"
    if binding.get("run_class") != expected_class:
        errors.append("source binding run class mismatch")
    if binding.get("scientific_parameters") != scientific_parameters(args):
        errors.append("scientific parameters changed after initial binding")
    if binding.get("git_commit") != git_output("rev-parse", "HEAD"):
        errors.append("git commit changed after initial binding")
    files = binding.get("source_files")
    if not isinstance(files, dict):
        return [*errors, "source binding file map missing"]
    for name, expected_path in bound_source_paths(args.input_report).items():
        row = files.get(name)
        if not isinstance(row, dict):
            errors.append(f"bound source missing: {name}")
            continue
        if row.get("path") != _relative(expected_path):
            errors.append(f"bound source path changed: {name}")
        if not expected_path.is_file() or row.get("sha256") != sha256_file(
            expected_path
        ):
            errors.append(f"bound source bytes changed: {name}")
    return errors


def source_binding_sha256(binding: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(binding))


def checkpoint_errors(
    checkpoint: dict[str, Any],
    *,
    case: DecisionCase,
    index: int,
    run_class: str,
    binding_sha256: str,
) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, observed {actual!r}")

    require(
        "schema_version", checkpoint.get("schema_version"), CHECKPOINT_SCHEMA_VERSION
    )
    require("run_class", checkpoint.get("run_class"), run_class)
    require("seed", checkpoint.get("seed"), case.seed)
    require("seed_index", checkpoint.get("seed_index"), index)
    require(
        "source_binding_sha256", checkpoint.get("source_binding_sha256"), binding_sha256
    )
    require(
        "source_binding_matched_preflight",
        checkpoint.get("source_binding_matched_preflight"),
        True,
    )
    require(
        "source_binding_matched_postflight",
        checkpoint.get("source_binding_matched_postflight"),
        True,
    )
    execution = checkpoint.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution metadata missing")
    else:
        require(
            "execution.layout",
            execution.get("layout"),
            "one_fixed_seed_per_fresh_genesis_subprocess",
        )
        require(
            "execution.non_fixed_robot_entities",
            execution.get("non_fixed_robot_entities"),
            3,
        )
        require(
            "execution.post_build_entity_pose_writes",
            execution.get("post_build_entity_pose_writes"),
            0,
        )
    trial = checkpoint.get("trial")
    if not isinstance(trial, dict):
        return [*errors, "trial payload missing"]
    require("trial.seed", trial.get("seed"), case.seed)
    decision = trial.get("decision")
    expected_decision = {
        "selected_corridor": case.selected_corridor,
        "full_chain_direct": case.full_chain_direct,
        "corridor_a_blocked": case.corridor_a_blocked,
        "corridor_b_blocked": case.corridor_b_blocked,
        "selected_corridor_clear": case.selected_corridor_clear,
        "both_corridors_blocked": case.both_corridors_blocked,
        "archived_episode_sha256": case.archived_episode_sha256,
        "input_class": case.input_class,
    }
    require("trial.decision", decision, expected_decision)
    require(
        "trial.script_entity_pose_writes_after_build",
        trial.get("script_entity_pose_writes_after_build"),
        0,
    )
    try:
        expected_assessment = assess_trial(trial)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"trial assessment cannot be recomputed: {exc}")
    else:
        require("trial.assessment", trial.get("assessment"), expected_assessment)
    return errors


def run_single_seed(
    *,
    args: argparse.Namespace,
    case: DecisionCase,
    index: int,
    binding: dict[str, Any],
) -> dict[str, Any]:
    import genesis as gs
    import torch

    backend = gs.amdgpu if args.backend == "amdgpu" else gs.cpu
    gs.init(backend=backend, logging_level="warning")
    layout = trial_layout(case, index)
    scene = gs.Scene(show_viewer=False, sim_options=gs.options.SimOptions(dt=args.dt))
    scene.add_entity(gs.morphs.Plane())
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
    scene.build()
    active_carrier_indices = configure_velocity_control(
        active_carrier, ROBOT_SPECS["carrier"]
    )
    active_scout_indices = configure_velocity_control(
        active_scout, ROBOT_SPECS["scout"]
    )
    passive_carrier_indices = configure_velocity_control(
        passive_carrier, ROBOT_SPECS["carrier"]
    )
    for _ in range(args.settle_steps):
        scene.step()

    scout_result = drive_waypoints(
        scene=scene,
        entity=active_scout,
        indices=active_scout_indices,
        spec=ROBOT_SPECS["scout"],
        waypoints=layout["active_scout_waypoints"],
        stationary=((active_carrier, active_carrier_indices),),
        blockers=active_blockers,
        partners=(active_carrier,),
        drive_sign=args.drive_sign,
        maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
        tolerance_m=args.tolerance,
        record_stride=args.record_stride,
    )
    active_result = drive_waypoints(
        scene=scene,
        entity=active_carrier,
        indices=active_carrier_indices,
        spec=ROBOT_SPECS["carrier"],
        waypoints=layout["active_carrier_waypoints"],
        stationary=((active_scout, active_scout_indices),),
        blockers=active_blockers,
        partners=(active_scout,),
        drive_sign=args.drive_sign,
        maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
        tolerance_m=args.tolerance,
        record_stride=args.record_stride,
    )
    passive_result = drive_waypoints(
        scene=scene,
        entity=passive_carrier,
        indices=passive_carrier_indices,
        spec=ROBOT_SPECS["carrier"],
        waypoints=layout["passive_carrier_waypoints"],
        stationary=(),
        blockers=passive_blockers,
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
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "run_class": binding["run_class"],
        "seed": case.seed,
        "seed_index": index,
        "source_binding_sha256": source_binding_sha256(binding),
        "execution": {
            "layout": "one_fixed_seed_per_fresh_genesis_subprocess",
            "original_v1_spatial_index": index,
            "genesis_scenes_in_this_checkpoint": 1,
            "non_fixed_robot_entities": 3,
            "active_and_passive_replicas_share_scene": True,
            "cross_seed_entities_share_scene": False,
            "post_build_actuation_api": "control_dofs_velocity only",
            "post_build_entity_pose_writes": 0,
        },
        "environment": {
            "python": platform.python_version(),
            "genesis": gs.__version__,
            "torch": torch.__version__,
            "torch_hip": torch.version.hip,
            "backend_requested": args.backend,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "trial": trial,
    }


def worker_main(args: argparse.Namespace) -> int:
    binding = json.loads(args.binding.read_text(encoding="utf-8"))
    errors = binding_errors(binding, args)
    if errors:
        raise RuntimeError("; ".join(errors))
    cases = expected_cases(args.engineering_smoke, args.input_report)
    if args.worker_index < 0 or args.worker_index >= len(cases):
        raise RuntimeError("worker index outside fixed seed order")
    case = cases[args.worker_index]
    if case.seed != args.worker_seed:
        raise RuntimeError("worker seed/index mismatch")
    checkpoint = run_single_seed(
        args=args, case=case, index=args.worker_index, binding=binding
    )
    postflight_errors = binding_errors(binding, args)
    if postflight_errors:
        raise RuntimeError("postflight binding failed: " + "; ".join(postflight_errors))
    checkpoint["source_binding_matched_preflight"] = True
    checkpoint["source_binding_matched_postflight"] = True
    atomic_publish_json(args.worker_output, checkpoint)
    print(
        f"worker sealed seed={case.seed} "
        f"checkpoint_sha256={sha256_file(args.worker_output)}"
    )
    return 0


def _progress_payload(
    *,
    run_class: str,
    cases: Sequence[DecisionCase],
    binding_sha256: str,
    checkpoints: Sequence[Path],
) -> dict[str, Any]:
    return {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "updated_at_utc": utc_now(),
        "run_class": run_class,
        "source_binding_sha256": binding_sha256,
        "fixed_seed_order": [case.seed for case in cases],
        "sealed_prefix_count": len(checkpoints),
        "sealed_prefix_seeds": [int(path.stem) for path in checkpoints],
        "sealed_checkpoint_sha256": [sha256_file(path) for path in checkpoints],
        "next_seed": cases[len(checkpoints)].seed
        if len(checkpoints) < len(cases)
        else None,
        "outcomes_exposed_in_progress_file": False,
    }


def _worker_command(
    args: argparse.Namespace,
    *,
    case: DecisionCase,
    index: int,
    binding_path: Path,
    worker_output: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--worker-seed",
        str(case.seed),
        "--worker-index",
        str(index),
        "--worker-output",
        str(worker_output),
        "--binding",
        str(binding_path),
        "--input-report",
        str(args.input_report),
        "--backend",
        args.backend,
        "--dt",
        str(args.dt),
        "--settle-steps",
        str(args.settle_steps),
        "--maximum-steps-per-waypoint",
        str(args.maximum_steps_per_waypoint),
        "--tolerance",
        str(args.tolerance),
        "--drive-sign",
        str(args.drive_sign),
        "--record-stride",
        str(args.record_stride),
        "--worker-timeout-seconds",
        str(args.worker_timeout_seconds),
    ]
    if args.engineering_smoke:
        command.append("--engineering-smoke")
    return command


def build_report(
    *,
    args: argparse.Namespace,
    binding: dict[str, Any],
    cases: Sequence[DecisionCase],
    checkpoint_paths: Sequence[Path],
    output_dir: Path,
) -> dict[str, Any]:
    checkpoints = [
        json.loads(path.read_text(encoding="utf-8")) for path in checkpoint_paths
    ]
    trials = [checkpoint["trial"] for checkpoint in checkpoints]
    run_class = binding["run_class"]
    summary = summarize_trials(trials, run_class)
    environments = [checkpoint["environment"] for checkpoint in checkpoints]
    environment_identities = {
        sha256_bytes(canonical_json(environment)) for environment in environments
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "run_class": run_class,
        "boundary": {
            "additive_non_locked": True,
            "formal_result_eligible": False,
            "changes_frozen_v8_endpoint": False,
            "uses_archived_decisions_without_rerunning_policy": not args.engineering_smoke,
            "oracle_used_by_controller": False,
            "not_simultaneous_90_body_scene": True,
            "claim": (
                "Checkpointed receipt-bound rigid-dynamics replay across fixed, "
                "independent seed scenes; not a frozen-policy rerun, real-robot "
                "result, or simultaneous 90-body execution."
            ),
        },
        "source": {
            "git_commit": binding["git_commit"],
            "git_branch": binding["git_branch"],
            "git_status_porcelain_at_initial_start": binding[
                "git_status_porcelain_at_initial_start"
            ],
            "source_binding_path": "SOURCE_BINDING.json",
            "source_binding_sha256": source_binding_sha256(binding),
            "source_files": binding["source_files"],
        },
        "decision_input": {
            **binding["decision_input"],
            "fixed_seeds": [case.seed for case in cases],
        },
        "execution": {
            "layout": "one_fixed_seed_per_fresh_genesis_subprocess",
            "fixed_order_no_parallel_reordering": True,
            "atomic_checkpoint_per_completed_seed": True,
            "resume_accepts_only_unchanged_binding_and_sealed_prefix": True,
            "completed_checkpoint_reruns": 0,
            "seed_replacements": 0,
            "genesis_scene_count": len(cases),
            "non_fixed_robot_entities_per_scene": 3,
            "distinct_non_fixed_robot_entities_across_run": 3 * len(cases),
            "cross_seed_entities_share_scene": False,
            "active_and_passive_replicas_share_scene": True,
        },
        "environment": {
            "all_worker_environments_identical": len(environment_identities) == 1,
            "worker_environment": environments[0],
        },
        "protocol": {
            **binding["scientific_parameters"],
            "post_build_actuation_api": "control_dofs_velocity only",
            "post_build_entity_pose_writes": 0,
            "entities_per_seed": {
                "active_non_fixed_carrier": 1,
                "active_non_fixed_scout": 1,
                "passive_non_fixed_carrier": 1,
            },
            "route_binding": (
                "active direct corridor or safe detour is read from the archived "
                "challenge result; passive always follows the fixed outer detour"
            ),
        },
        "checkpoint_index": [
            {
                "seed": case.seed,
                "path": str(path.relative_to(output_dir)),
                "sha256": sha256_file(path),
            }
            for case, path in zip(cases, checkpoint_paths, strict=True)
        ],
        "summary": summary,
        "trials": trials,
    }


def coordinator_main(args: argparse.Namespace) -> int:
    args.output_dir = args.output_dir.resolve()
    args.input_report = args.input_report.resolve()
    binding_path = args.output_dir / "SOURCE_BINDING.json"
    progress_path = args.output_dir / "PROGRESS.json"
    attempts_path = args.output_dir / "ATTEMPTS.jsonl"
    report_path = args.output_dir / "REPORT.json"
    trials_dir = args.output_dir / "TRIALS"
    logs_dir = args.output_dir / "WORKER_LOGS"
    cases = expected_cases(args.engineering_smoke, args.input_report)
    run_class = "engineering_smoke" if args.engineering_smoke else "formal"

    if args.resume:
        if not binding_path.is_file():
            raise RuntimeError("resume requested without SOURCE_BINDING.json")
        if report_path.exists():
            raise RuntimeError("formal report already exists; refusing to overwrite")
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        errors = binding_errors(binding, args)
        if errors:
            raise RuntimeError("resume binding failed: " + "; ".join(errors))
    else:
        if args.output_dir.exists():
            raise RuntimeError(
                f"output directory already exists; use --resume only for a sealed prefix: {args.output_dir}"
            )
        binding = build_source_binding(args)
        args.output_dir.mkdir(parents=True)
        atomic_write_json(binding_path, binding)

    binding_sha = source_binding_sha256(binding)
    checkpoint_paths = [trials_dir / f"{case.seed}.json" for case in cases]
    sealed: list[Path] = []
    missing_seen = False
    for index, (case, path) in enumerate(zip(cases, checkpoint_paths, strict=True)):
        if not path.is_file():
            missing_seen = True
            continue
        if missing_seen:
            raise RuntimeError("sealed checkpoints must be an exact fixed-order prefix")
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        errors = checkpoint_errors(
            checkpoint,
            case=case,
            index=index,
            run_class=run_class,
            binding_sha256=binding_sha,
        )
        if errors:
            raise RuntimeError(
                f"sealed checkpoint {case.seed} failed closed: " + "; ".join(errors)
            )
        sealed.append(path)
    atomic_write_json(
        progress_path,
        _progress_payload(
            run_class=run_class,
            cases=cases,
            binding_sha256=binding_sha,
            checkpoints=sealed,
        ),
    )

    for index in range(len(sealed), len(cases)):
        case = cases[index]
        final_path = checkpoint_paths[index]
        attempt_number = (
            len(list(logs_dir.glob(f"{case.seed}-attempt-*.log"))) + 1
            if logs_dir.exists()
            else 1
        )
        log_path = logs_dir / f"{case.seed}-attempt-{attempt_number}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        started = utc_now()
        command = _worker_command(
            args,
            case=case,
            index=index,
            binding_path=binding_path,
            worker_output=final_path,
        )
        status = "worker_error"
        exit_code: int | None = None
        try:
            with log_path.open("wb") as log_handle:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    timeout=args.worker_timeout_seconds,
                    check=False,
                )
            exit_code = completed.returncode
            status = "completed" if exit_code == 0 else "worker_error"
        except subprocess.TimeoutExpired:
            status = "infrastructure_timeout"
        ended = utc_now()
        append_json_line(
            attempts_path,
            {
                "seed": case.seed,
                "seed_index": index,
                "attempt": attempt_number,
                "started_at_utc": started,
                "ended_at_utc": ended,
                "status": status,
                "exit_code": exit_code,
                "checkpoint_sealed": False,
                "log_path": str(log_path.relative_to(args.output_dir)),
            },
        )
        if not final_path.is_file():
            raise RuntimeError(
                f"seed {case.seed} did not produce a sealed checkpoint; "
                "rerun the unchanged command with --resume"
            )
        checkpoint = json.loads(final_path.read_text(encoding="utf-8"))
        errors = checkpoint_errors(
            checkpoint,
            case=case,
            index=index,
            run_class=run_class,
            binding_sha256=binding_sha,
        )
        if errors:
            raise RuntimeError(
                f"worker checkpoint {case.seed} failed closed: " + "; ".join(errors)
            )
        sealed.append(final_path)
        append_json_line(
            attempts_path,
            {
                "seed": case.seed,
                "seed_index": index,
                "attempt": attempt_number,
                "sealed_at_utc": utc_now(),
                "status": "checkpoint_sealed",
                "checkpoint_sealed": True,
                "checkpoint_path": str(final_path.relative_to(args.output_dir)),
                "checkpoint_sha256": sha256_file(final_path),
            },
        )
        atomic_write_json(
            progress_path,
            _progress_payload(
                run_class=run_class,
                cases=cases,
                binding_sha256=binding_sha,
                checkpoints=sealed,
            ),
        )
        print(
            f"sealed {len(sealed)}/{len(cases)} seed={case.seed} "
            f"checkpoint_sha256={sha256_file(final_path)}",
            flush=True,
        )

    report = build_report(
        args=args,
        binding=binding,
        cases=cases,
        checkpoint_paths=sealed,
        output_dir=args.output_dir,
    )
    atomic_write_json(report_path, report)
    checksum_paths = [binding_path, *sealed, report_path]
    checksum_lines = [
        f"{sha256_file(path)}  {path.relative_to(args.output_dir)}"
        for path in checksum_paths
    ]
    (args.output_dir / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
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
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--input-report", type=Path, default=DEFAULT_INPUT_REPORT)
    parser.add_argument("--backend", choices=("amdgpu", "cpu"), default="amdgpu")
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dt", type=float, default=0.02)
    parser.add_argument("--settle-steps", type=int, default=80)
    parser.add_argument("--maximum-steps-per-waypoint", type=int, default=1800)
    parser.add_argument("--tolerance", type=float, default=0.14)
    parser.add_argument("--drive-sign", type=float, default=-1.0)
    parser.add_argument("--record-stride", type=int, default=50)
    parser.add_argument("--worker-timeout-seconds", type=int, default=3600)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-seed", type=int, default=-1, help=argparse.SUPPRESS)
    parser.add_argument("--worker-index", type=int, default=-1, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--binding", type=Path, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.input_report = args.input_report.resolve()
    if args.maximum_steps_per_waypoint < 1 or args.record_stride < 1:
        raise SystemExit("step and record-stride values must be positive")
    if args.worker_timeout_seconds < 1:
        raise SystemExit("worker timeout must be positive")
    if args.worker:
        if args.worker_output is None or args.binding is None:
            raise SystemExit("worker mode requires --worker-output and --binding")
        args.worker_output = args.worker_output.resolve()
        args.binding = args.binding.resolve()
        return worker_main(args)
    if args.output_dir is None:
        raise SystemExit("coordinator mode requires --output-dir")
    return coordinator_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
