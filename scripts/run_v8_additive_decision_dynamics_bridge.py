#!/usr/bin/env python3
"""Replay frozen V8 route decisions through separate rigid-body robots.

This submission-time supplement consumes the immutable 30-world challenge
report.  It does not rerun or change the frozen policy.  For every archived
decision it instantiates an active carrier/scout pair plus a passive carrier,
then drives only wheel DOFs after ``scene.build()``.  The resulting physical
paths test whether the reported route decision and burden advantage survive a
bounded rigid-dynamics realization on AMD ROCm.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.run_v8_additive_dual_body_dynamics import (  # noqa: E402
    ROBOT_SPECS,
    apply_wheel_velocity,
    configure_velocity_control,
    contact_rows,
    distance_xy,
    entity_pose,
    entity_tilt_degrees,
    sha256_file,
)
from v4_motion import DifferentialDriveControlLaw  # noqa: E402
from v6_scenario import sample_v6_scenario  # noqa: E402


SCHEMA_VERSION = "look-twice.additive-decision-dynamics-bridge/v1"
EXPECTED_CHALLENGE_REPORT_SHA256 = (
    "59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0"
)
FORMAL_SEEDS = tuple(range(102500, 102530))
CORRIDOR_Y = {"corridor_a": -0.55, "corridor_b": 0.55}


@dataclass(frozen=True)
class DecisionCase:
    seed: int
    selected_corridor: str | None
    full_chain_direct: bool
    corridor_a_blocked: bool
    corridor_b_blocked: bool
    archived_episode_sha256: str
    input_class: str

    @property
    def selected_corridor_clear(self) -> bool:
        if self.selected_corridor == "corridor_a":
            return not self.corridor_a_blocked
        if self.selected_corridor == "corridor_b":
            return not self.corridor_b_blocked
        return False

    @property
    def both_corridors_blocked(self) -> bool:
        return self.corridor_a_blocked and self.corridor_b_blocked


def git_output(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ("git", *args), cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _truth_for_seed(seed: int) -> tuple[bool, bool]:
    scenario = sample_v6_scenario("independent-noise", seed)
    oracle = scenario.oracle_context
    return (
        bool(oracle["corridor_a_blocked_initial"]),
        bool(oracle["corridor_b_blocked_initial"]),
    )


def load_formal_cases(path: Path) -> list[DecisionCase]:
    observed_sha = sha256_file(path)
    if observed_sha != EXPECTED_CHALLENGE_REPORT_SHA256:
        raise ValueError(
            "challenge report identity mismatch: "
            f"expected {EXPECTED_CHALLENGE_REPORT_SHA256}, observed {observed_sha}"
        )
    payload = read_json_object(path)
    rows = payload.get("analysis", {}).get("per_seed")
    if not isinstance(rows, list):
        raise ValueError("challenge report analysis.per_seed must be a list")
    if [int(row.get("seed", -1)) for row in rows] != list(FORMAL_SEEDS):
        raise ValueError("challenge report does not contain the fixed 30-seed order")

    cases: list[DecisionCase] = []
    for row in rows:
        seed = int(row["seed"])
        active = row.get("active")
        if not isinstance(active, dict):
            raise ValueError(f"seed {seed}: active result missing")
        selected = active.get("selected_corridor")
        if selected not in (None, "corridor_a", "corridor_b"):
            raise ValueError(f"seed {seed}: invalid selected corridor {selected!r}")
        direct = bool(active.get("full_chain_direct"))
        a_blocked, b_blocked = _truth_for_seed(seed)
        case = DecisionCase(
            seed=seed,
            selected_corridor=selected,
            full_chain_direct=direct,
            corridor_a_blocked=a_blocked,
            corridor_b_blocked=b_blocked,
            archived_episode_sha256=str(active.get("sha256", "")),
            input_class="immutable_challenge_report",
        )
        if direct != (selected is not None):
            raise ValueError(f"seed {seed}: direct/selection mismatch")
        if direct and not case.selected_corridor_clear:
            raise ValueError(f"seed {seed}: archived direct route is not oracle-clear")
        if not direct and not case.both_corridors_blocked:
            raise ValueError(f"seed {seed}: non-direct result is not dual-blocked")
        if len(case.archived_episode_sha256) != 64:
            raise ValueError(f"seed {seed}: missing archived episode identity")
        cases.append(case)
    return cases


def engineering_smoke_cases() -> list[DecisionCase]:
    return [
        DecisionCase(170800, "corridor_a", True, False, True, "0" * 64, "smoke"),
        DecisionCase(170801, "corridor_b", True, True, False, "1" * 64, "smoke"),
        DecisionCase(170802, None, False, True, True, "2" * 64, "smoke"),
    ]


def _world(
    offset: tuple[float, float], point: tuple[float, float]
) -> tuple[float, float]:
    return point[0] + offset[0], point[1] + offset[1]


def _detour_side(seed: int) -> float:
    return 1.65 if seed % 2 == 0 else -1.65


def _carrier_waypoints(
    offset: tuple[float, float], selected_corridor: str | None, seed: int
) -> list[tuple[float, float]]:
    lane_y = CORRIDOR_Y[selected_corridor] if selected_corridor else _detour_side(seed)
    return [
        _world(offset, (-0.20, lane_y)),
        _world(offset, (1.85, lane_y)),
        _world(offset, (2.80, 0.0)),
    ]


def trial_layout(case: DecisionCase, index: int) -> dict[str, Any]:
    column, row = index % 3, index // 3
    cell_origin = (column * 20.0, row * 7.0)
    active_offset = cell_origin
    passive_offset = (cell_origin[0] + 8.0, cell_origin[1])
    if case.selected_corridor == "corridor_a":
        viewpoint_y = 1.10
    elif case.selected_corridor == "corridor_b":
        viewpoint_y = -1.10
    else:
        # Keep the parked scout on the opposite side of the active detour.
        viewpoint_y = -1.10 if _detour_side(case.seed) > 0 else 1.10
    blocker_lanes = [
        corridor
        for corridor, blocked in (
            ("corridor_a", case.corridor_a_blocked),
            ("corridor_b", case.corridor_b_blocked),
        )
        if blocked
    ]

    def blocker_positions(
        offset: tuple[float, float],
    ) -> list[tuple[float, float, float]]:
        return [
            (*_world(offset, (0.95, CORRIDOR_Y[corridor])), 0.25)
            for corridor in blocker_lanes
        ]

    return {
        "cell_origin": cell_origin,
        "active_offset": active_offset,
        "passive_offset": passive_offset,
        "active_carrier_start": (
            *_world(active_offset, (-2.0, 0.0)),
            ROBOT_SPECS["carrier"].start_z,
        ),
        "active_scout_start": (
            *_world(active_offset, (-1.6, 1.2)),
            ROBOT_SPECS["scout"].start_z,
        ),
        "passive_carrier_start": (
            *_world(passive_offset, (-2.0, 0.0)),
            ROBOT_SPECS["carrier"].start_z,
        ),
        "active_scout_waypoints": [_world(active_offset, (-0.55, viewpoint_y))],
        "active_carrier_waypoints": _carrier_waypoints(
            active_offset, case.selected_corridor, case.seed
        ),
        "passive_carrier_waypoints": _carrier_waypoints(
            passive_offset, None, case.seed
        ),
        "active_blocker_positions": blocker_positions(active_offset),
        "passive_blocker_positions": blocker_positions(passive_offset),
        "blocked_corridors": blocker_lanes,
    }


def _sum_contacts(entity: Any, others: Sequence[Any]) -> int:
    return sum(contact_rows(entity.get_contacts(with_entity=other)) for other in others)


def drive_waypoints(
    *,
    scene: Any,
    entity: Any,
    indices: list[int],
    spec: Any,
    waypoints: list[tuple[float, float]],
    stationary: Sequence[tuple[Any, list[int]]],
    blockers: Sequence[Any],
    partners: Sequence[Any],
    drive_sign: float,
    maximum_steps_per_waypoint: int,
    tolerance_m: float,
    record_stride: int,
) -> dict[str, Any]:
    controller = DifferentialDriveControlLaw(
        wheel_radius=spec.wheel_radius,
        track_width=spec.track_width,
        linear_gain=1.1,
        heading_gain=2.8,
        max_linear_velocity=0.45 if spec.name == "carrier" else 0.55,
        max_angular_velocity=1.35,
    )
    start_pose = entity_pose(entity)
    stationary_starts = [entity_pose(item[0]) for item in stationary]
    previous = start_pose
    path_length = 0.0
    max_tilt = entity_tilt_degrees(entity)
    max_stationary_drift = 0.0
    max_abs_wheel_target = 0.0
    obstacle_contact_rows = 0
    stationary_obstacle_contact_rows = 0
    partner_contact_rows = 0
    elapsed_steps = 0
    samples: list[dict[str, Any]] = []
    reached_all = True
    failure_reason = "reached"

    for waypoint_index, target in enumerate(waypoints):
        reached = False
        for local_step in range(maximum_steps_per_waypoint):
            pose = entity_pose(entity)
            remaining = math.dist((pose.x, pose.y), target)
            if remaining <= tolerance_m:
                reached = True
                apply_wheel_velocity(entity, indices, 0.0, 0.0, drive_sign)
                break
            command = controller.command(pose, target)
            apply_wheel_velocity(
                entity,
                indices,
                command.left_wheel_velocity,
                command.right_wheel_velocity,
                drive_sign,
            )
            for stationary_entity, stationary_indices in stationary:
                apply_wheel_velocity(
                    stationary_entity, stationary_indices, 0.0, 0.0, drive_sign
                )
            scene.step()
            elapsed_steps += 1
            current = entity_pose(entity)
            path_length += distance_xy(previous, current)
            previous = current
            max_tilt = max(max_tilt, entity_tilt_degrees(entity))
            for stationary_index, (stationary_entity, _) in enumerate(stationary):
                stationary_pose = entity_pose(stationary_entity)
                max_stationary_drift = max(
                    max_stationary_drift,
                    distance_xy(stationary_starts[stationary_index], stationary_pose),
                )
                stationary_obstacle_contact_rows += _sum_contacts(
                    stationary_entity, blockers
                )
            max_abs_wheel_target = max(
                max_abs_wheel_target,
                abs(command.left_wheel_velocity),
                abs(command.right_wheel_velocity),
            )
            obstacle_contact_rows += _sum_contacts(entity, blockers)
            partner_contact_rows += _sum_contacts(entity, partners)
            if local_step % record_stride == 0:
                samples.append(
                    {
                        "waypoint_index": waypoint_index,
                        "step": elapsed_steps,
                        "pose": asdict(current),
                        "remaining_m": remaining,
                        "wheel_target_rad_s": [
                            drive_sign * command.left_wheel_velocity,
                            drive_sign * command.right_wheel_velocity,
                        ],
                    }
                )
            if not all(math.isfinite(value) for value in asdict(current).values()):
                failure_reason = "non_finite_pose"
                break
            if max_tilt > 45.0:
                failure_reason = "excessive_tilt"
                break
        if not reached:
            reached_all = False
            if failure_reason == "reached":
                failure_reason = "waypoint_timeout"
            break

    apply_wheel_velocity(entity, indices, 0.0, 0.0, drive_sign)
    final_pose = entity_pose(entity)
    return {
        "reached": reached_all,
        "reason": failure_reason,
        "start_pose": asdict(start_pose),
        "final_pose": asdict(final_pose),
        "final_goal_error_m": math.dist((final_pose.x, final_pose.y), waypoints[-1]),
        "waypoints": [list(point) for point in waypoints],
        "path_length_m": path_length,
        "elapsed_steps": elapsed_steps,
        "max_tilt_deg": max_tilt,
        "stationary_partner_drift_m": max_stationary_drift,
        "obstacle_contact_rows": obstacle_contact_rows,
        "stationary_obstacle_contact_rows": stationary_obstacle_contact_rows,
        "partner_contact_rows": partner_contact_rows,
        "max_abs_wheel_target_rad_s": max_abs_wheel_target,
        "trajectory_samples": samples,
    }


def assess_trial(trial: dict[str, Any]) -> dict[str, Any]:
    thresholds = {
        "goal_tolerance_m": 0.14,
        "maximum_stationary_drift_m": 0.08,
        "maximum_tilt_deg": 20.0,
        "minimum_scout_path_m": 0.50,
        "minimum_carrier_path_m": 3.50,
        "minimum_direct_pair_path_saving_m": 0.50,
    }
    scout = trial["active_scout"]
    active = trial["active_carrier"]
    passive = trial["passive_carrier"]
    rows = (scout, active, passive)
    direct = bool(trial["decision"]["full_chain_direct"])
    checks = {
        "decision_semantics_valid": bool(
            trial["decision"]["selected_corridor_clear"]
            if direct
            else trial["decision"]["both_corridors_blocked"]
        ),
        "all_bodies_reached": all(bool(row["reached"]) for row in rows),
        "all_goal_errors_within_tolerance": all(
            float(row["final_goal_error_m"]) <= thresholds["goal_tolerance_m"]
            for row in rows
        ),
        "all_bodies_wheel_actuated": all(
            float(row["max_abs_wheel_target_rad_s"]) > 0.1 for row in rows
        ),
        "scout_path_nontrivial": float(scout["path_length_m"])
        >= thresholds["minimum_scout_path_m"],
        "carrier_paths_nontrivial": min(
            float(active["path_length_m"]), float(passive["path_length_m"])
        )
        >= thresholds["minimum_carrier_path_m"],
        "carrier_parked_during_scout": float(scout["stationary_partner_drift_m"])
        <= thresholds["maximum_stationary_drift_m"],
        "scout_parked_during_carrier": float(active["stationary_partner_drift_m"])
        <= thresholds["maximum_stationary_drift_m"],
        "stable_tilt": max(float(row["max_tilt_deg"]) for row in rows)
        <= thresholds["maximum_tilt_deg"],
        "no_blocker_contact": sum(
            int(row["obstacle_contact_rows"])
            + int(row["stationary_obstacle_contact_rows"])
            for row in rows
        )
        == 0,
        "no_active_pair_contact": sum(
            int(row["partner_contact_rows"]) for row in (scout, active)
        )
        == 0,
        "direct_pair_has_physical_path_saving": (
            float(passive["path_length_m"]) - float(active["path_length_m"])
            >= thresholds["minimum_direct_pair_path_saving_m"]
            if direct
            else True
        ),
        "no_script_pose_write_after_build": int(
            trial["script_entity_pose_writes_after_build"]
        )
        == 0,
    }
    return {"thresholds": thresholds, "checks": checks, "passed": all(checks.values())}


def summarize_trials(trials: list[dict[str, Any]], run_class: str) -> dict[str, Any]:
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
    mean_active = statistics.fmean(active_paths)
    mean_passive = statistics.fmean(passive_paths)
    reduction = (mean_passive - mean_active) / mean_passive
    direct_trials = [row for row in trials if row["decision"]["full_chain_direct"]]
    safe_detours = [row for row in trials if not row["decision"]["full_chain_direct"]]
    passed = sum(bool(row["assessment"]["passed"]) for row in trials)
    expected = {
        "formal": {"trials": 30, "direct": 29, "safe_detour": 1},
        "engineering_smoke": {"trials": 3, "direct": 2, "safe_detour": 1},
    }[run_class]
    minimum_reduction = 0.15 if run_class == "formal" else 0.10
    aggregate_checks = {
        "fixed_denominator_complete": len(trials) == expected["trials"],
        "expected_decision_counts": len(direct_trials) == expected["direct"]
        and len(safe_detours) == expected["safe_detour"],
        "all_trials_passed": passed == len(trials),
        "mean_loaded_carrier_path_reduction_meets_run_class_floor": reduction
        >= minimum_reduction,
        "every_direct_pair_saved_at_least_0_50_m": all(
            float(row["passive_carrier"]["path_length_m"])
            - float(row["active_carrier"]["path_length_m"])
            >= 0.50
            for row in direct_trials
        ),
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
        "minimum_mean_path_reduction_fraction": minimum_reduction,
        "direct_pairs_saving_at_least_0_50_m": sum(
            float(row["passive_carrier"]["path_length_m"])
            - float(row["active_carrier"]["path_length_m"])
            >= 0.50
            for row in direct_trials
        ),
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
        "maximum_tilt_deg": max(float(row["max_tilt_deg"]) for row in body_rows),
        "maximum_stationary_partner_drift_m": max(
            max(
                float(row["active_scout"]["stationary_partner_drift_m"]),
                float(row["active_carrier"]["stationary_partner_drift_m"]),
            )
            for row in trials
        ),
        "aggregate_checks": aggregate_checks,
    }


def _add_blockers(
    scene: Any, gs: Any, positions: Iterable[tuple[float, float, float]], prefix: str
) -> list[Any]:
    entities = []
    for index, position in enumerate(positions):
        entities.append(
            scene.add_entity(
                gs.morphs.Box(size=(0.45, 0.45, 0.50), pos=position, fixed=True),
                surface=gs.surfaces.Default(color=(0.55, 0.18, 0.18)),
                name=f"{prefix}-{index}",
            )
        )
    return entities


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    import genesis as gs
    import torch

    run_class = "engineering_smoke" if args.engineering_smoke else "formal"
    cases = (
        engineering_smoke_cases()
        if args.engineering_smoke
        else load_formal_cases(args.input_report)
    )
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

    trials: list[dict[str, Any]] = []
    for record in records:
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
        trials.append(trial)

    script_path = Path(__file__).resolve()
    verifier_path = ROOT / "scripts" / "verify_v8_additive_decision_dynamics_bridge.py"
    protocol_path = ROOT / "docs" / "V8_ADDITIVE_DECISION_DYNAMICS_BRIDGE_PROTOCOL.md"
    engineering_audit_path = (
        ROOT / "docs" / "V8_ADDITIVE_DECISION_DYNAMICS_ENGINEERING_AUDIT.json"
    )
    helper_path = ROOT / "scripts" / "run_v8_additive_dual_body_dynamics.py"
    scenario_path = ROOT / "src" / "v6_scenario.py"
    summary = summarize_trials(trials, run_class)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_class": run_class,
        "boundary": {
            "additive_non_locked": True,
            "formal_result_eligible": False,
            "changes_frozen_v8_endpoint": False,
            "uses_archived_decisions_without_rerunning_policy": not args.engineering_smoke,
            "oracle_used_by_controller": False,
            "claim": (
                "Receipt-bound rigid-dynamics replay of archived route outcomes; "
                "not a new frozen-policy, perception, generalization, or real-robot result."
            ),
        },
        "source": {
            "git_commit": git_output("rev-parse", "HEAD"),
            "git_branch": git_output("branch", "--show-current"),
            "git_status_porcelain": git_output("status", "--porcelain"),
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": sha256_file(script_path),
            "verifier": str(verifier_path.relative_to(ROOT)),
            "verifier_sha256": sha256_file(verifier_path),
            "fixed_protocol": str(protocol_path.relative_to(ROOT)),
            "fixed_protocol_sha256": sha256_file(protocol_path),
            "engineering_audit": str(engineering_audit_path.relative_to(ROOT)),
            "engineering_audit_sha256": sha256_file(engineering_audit_path),
            "dual_body_helper_sha256": sha256_file(helper_path),
            "scenario_source_sha256": sha256_file(scenario_path),
            "carrier_urdf_sha256": sha256_file(ROBOT_SPECS["carrier"].urdf),
            "scout_urdf_sha256": sha256_file(ROBOT_SPECS["scout"].urdf),
        },
        "decision_input": {
            "path": str(args.input_report.relative_to(ROOT)),
            "sha256": sha256_file(args.input_report),
            "fixed_seeds": list(FORMAL_SEEDS),
            "consumed_in_this_run": not args.engineering_smoke,
        },
        "environment": {
            "python": platform.python_version(),
            "genesis": gs.__version__,
            "torch": torch.__version__,
            "torch_hip": torch.version.hip,
            "backend_requested": args.backend,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "protocol": {
            "dt_seconds": args.dt,
            "settle_steps": args.settle_steps,
            "maximum_steps_per_waypoint": args.maximum_steps_per_waypoint,
            "goal_tolerance_m": args.tolerance,
            "drive_sign": args.drive_sign,
            "post_build_actuation_api": "control_dofs_velocity only",
            "post_build_entity_pose_writes": 0,
            "entities_per_trial": {
                "active_non_fixed_carrier": 1,
                "active_non_fixed_scout": 1,
                "passive_non_fixed_carrier": 1,
            },
            "route_binding": (
                "active direct corridor or safe detour is read from the archived "
                "challenge result; passive always follows the fixed outer detour"
            ),
            "oracle_boundary": (
                "initial blocker truth reconstructs the physical scene and audits "
                "the archived decision; it is never supplied to the wheel controller"
            ),
        },
        "summary": summary,
        "trials": trials,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-report",
        type=Path,
        default=ROOT
        / "release"
        / "v8-frozen"
        / "results"
        / "challenge_102500_102529"
        / "CHALLENGE_REPORT.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("amdgpu", "cpu"), default="amdgpu")
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--dt", type=float, default=0.02)
    parser.add_argument("--settle-steps", type=int, default=80)
    parser.add_argument("--maximum-steps-per-waypoint", type=int, default=1800)
    parser.add_argument("--tolerance", type=float, default=0.14)
    parser.add_argument("--drive-sign", type=float, default=-1.0)
    parser.add_argument("--record-stride", type=int, default=50)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.input_report = args.input_report.resolve()
    args.output = args.output.resolve()
    if args.maximum_steps_per_waypoint < 1 or args.record_stride < 1:
        raise SystemExit("step and record-stride values must be positive")
    if args.output.exists() and not args.engineering_smoke:
        raise SystemExit(f"refusing to overwrite formal output: {args.output}")
    report = run_validation(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = report["summary"]
    print(
        f"{report['run_class']}: {summary['passed']}/{summary['trials']} trials; "
        f"loaded-carrier path reduction={summary['paired_mean_path_reduction_percent']:.3f}%"
    )
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
