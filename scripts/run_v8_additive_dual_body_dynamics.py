#!/usr/bin/env python3
"""Additive dual-body rigid-dynamics validation on Genesis + AMD ROCm.

This is deliberately separate from the frozen V8 endpoint.  It creates one
non-fixed carrier and one non-fixed scout per seed, drives only their wheel
DOFs after ``scene.build()``, and records bounded corridor-following checks.
It never replaces, extends, or relabels the preregistered kinematic result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from v4_motion import DifferentialDriveControlLaw, Pose2D  # noqa: E402


SCHEMA_VERSION = "look-twice.additive-dual-body-dynamics/v1"
DEFAULT_SEEDS = tuple(range(160820, 160840))
WHEEL_JOINTS = ("left_wheel_joint", "right_wheel_joint")


@dataclass(frozen=True)
class RobotSpec:
    name: str
    urdf: Path
    start_z: float
    wheel_radius: float
    track_width: float
    mass_kg: float
    max_force: float


ROBOT_SPECS = {
    "carrier": RobotSpec(
        name="carrier",
        urdf=ROOT / "assets" / "robots" / "diff_drive_carrier.urdf",
        start_z=0.151,
        wheel_radius=0.08,
        track_width=0.44,
        mass_kg=23.35,
        max_force=35.0,
    ),
    "scout": RobotSpec(
        name="scout",
        urdf=ROOT / "assets" / "robots" / "diff_drive_scout.urdf",
        start_z=0.111,
        wheel_radius=0.06,
        track_width=0.32,
        mass_kg=8.9,
        max_force=20.0,
    ),
}


def parse_seeds(value: str) -> tuple[int, ...]:
    """Parse ``1,2,5:8`` into a sorted, unique seed tuple."""
    seeds: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            start_text, stop_text = token.split(":", 1)
            start, stop = int(start_text), int(stop_text)
            if start < 0 or stop <= start:
                raise ValueError(f"invalid half-open seed range: {token}")
            seeds.update(range(start, stop))
        else:
            seed = int(token)
            if seed < 0:
                raise ValueError("seeds must be non-negative")
            seeds.add(seed)
    if not seeds:
        raise ValueError("at least one seed is required")
    return tuple(sorted(seeds))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ("git", *args), cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def quaternion_wxyz_to_pose(
    position: Iterable[float], quaternion: Iterable[float]
) -> Pose2D:
    px, py, _ = (float(value) for value in position)
    w, x, y, z = (float(value) for value in quaternion)
    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    return Pose2D(px, py, math.atan2(sin_yaw, cos_yaw))


def quaternion_tilt_degrees(quaternion: Iterable[float]) -> float:
    """Angle between the body and world up axes, independent of yaw."""
    w, x, y, z = (float(value) for value in quaternion)
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm <= 1e-12:
        return float("inf")
    x, y = x / norm, y / norm
    up_z = max(-1.0, min(1.0, 1.0 - 2.0 * (x * x + y * y)))
    return math.degrees(math.acos(up_z))


def tensor_list(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in value]


def entity_pose(entity: Any) -> Pose2D:
    return quaternion_wxyz_to_pose(
        tensor_list(entity.get_pos()), tensor_list(entity.get_quat())
    )


def entity_tilt_degrees(entity: Any) -> float:
    return quaternion_tilt_degrees(tensor_list(entity.get_quat()))


def wheel_dof_indices(entity: Any) -> list[int]:
    indices: list[int] = []
    for name in WHEEL_JOINTS:
        local = entity.get_joint(name).dofs_idx_local
        if isinstance(local, int):
            values = [local]
        elif hasattr(local, "tolist"):
            unpacked = local.tolist()
            values = unpacked if isinstance(unpacked, list) else [unpacked]
        else:
            values = list(local)
        if len(values) != 1:
            raise RuntimeError(f"{name} exposes {len(values)} DOFs; expected one")
        indices.append(int(values[0]))
    if len(set(indices)) != 2:
        raise RuntimeError(f"wheel DOFs are not distinct: {indices}")
    return indices


def contact_rows(contacts: dict[str, Any]) -> int:
    if not contacts:
        return 0
    mask = contacts.get("valid_mask")
    if mask is not None:
        return int(mask.sum().item())
    for key in ("geom_a", "position", "penetration"):
        value = contacts.get(key)
        if value is not None:
            return int(value.shape[0])
    return 0


def local_xy(pose: Pose2D, offset: tuple[float, float]) -> tuple[float, float]:
    return pose.x - offset[0], pose.y - offset[1]


def distance_xy(a: Pose2D, b: Pose2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def trial_layout(seed: int, index: int) -> dict[str, Any]:
    """Return deterministic, non-overlapping warehouse geometry for one seed."""
    column, row = index % 4, index // 4
    offset = (column * 12.0, row * 6.0)
    rng = random.Random(seed)
    clear_lane_y = (-0.34 if seed % 2 == 0 else 0.34) + rng.uniform(-0.025, 0.025)
    blocked_lane_y = -0.34 if clear_lane_y > 0 else 0.34
    scout_y = (0.95 if clear_lane_y < 0 else -0.95) + rng.uniform(-0.04, 0.04)

    def world(point: tuple[float, float]) -> tuple[float, float]:
        return point[0] + offset[0], point[1] + offset[1]

    return {
        "seed": seed,
        "offset": offset,
        "carrier_start": (*world((-2.0, 0.0)), ROBOT_SPECS["carrier"].start_z),
        "scout_start": (*world((-1.6, 1.2)), ROBOT_SPECS["scout"].start_z),
        "scout_waypoints": [world((-0.55, scout_y))],
        "carrier_waypoints": [
            world((0.10, clear_lane_y)),
            world((1.90, clear_lane_y)),
            world((2.80, 0.0)),
        ],
        "blocker_pos": (*world((1.0, blocked_lane_y)), 0.25),
        "clear_lane_y": clear_lane_y,
        "blocked_lane_y": blocked_lane_y,
    }


def configure_velocity_control(entity: Any, spec: RobotSpec) -> list[int]:
    indices = wheel_dof_indices(entity)
    entity.set_dofs_kp(np.zeros(2, dtype=np.float32), dofs_idx_local=indices)
    entity.set_dofs_kv(np.full(2, 8.0, dtype=np.float32), dofs_idx_local=indices)
    entity.set_dofs_force_range(
        np.full(2, -spec.max_force, dtype=np.float32),
        np.full(2, spec.max_force, dtype=np.float32),
        dofs_idx_local=indices,
    )
    entity.control_dofs_velocity(np.zeros(2, dtype=np.float32), dofs_idx_local=indices)
    return indices


def apply_wheel_velocity(
    entity: Any, indices: list[int], left: float, right: float, drive_sign: float
) -> None:
    entity.control_dofs_velocity(
        np.asarray((drive_sign * left, drive_sign * right), dtype=np.float32),
        dofs_idx_local=indices,
    )


def drive_waypoints(
    *,
    scene: Any,
    entity: Any,
    indices: list[int],
    spec: RobotSpec,
    waypoints: list[tuple[float, float]],
    stationary_entity: Any,
    stationary_indices: list[int],
    blocker: Any,
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
    stationary_start = entity_pose(stationary_entity)
    previous = start_pose
    path_length = 0.0
    max_tilt = entity_tilt_degrees(entity)
    max_stationary_drift = 0.0
    max_abs_wheel_target = 0.0
    obstacle_contact_rows = 0
    robot_contact_rows = 0
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
            apply_wheel_velocity(
                stationary_entity, stationary_indices, 0.0, 0.0, drive_sign
            )
            scene.step()
            elapsed_steps += 1
            current = entity_pose(entity)
            stationary_now = entity_pose(stationary_entity)
            path_length += distance_xy(previous, current)
            previous = current
            max_tilt = max(max_tilt, entity_tilt_degrees(entity))
            max_stationary_drift = max(
                max_stationary_drift,
                distance_xy(stationary_start, stationary_now),
            )
            max_abs_wheel_target = max(
                max_abs_wheel_target,
                abs(command.left_wheel_velocity),
                abs(command.right_wheel_velocity),
            )
            obstacle_contact_rows += contact_rows(
                entity.get_contacts(with_entity=blocker)
            )
            robot_contact_rows += contact_rows(
                entity.get_contacts(with_entity=stationary_entity)
            )
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
        "robot_contact_rows": robot_contact_rows,
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
    }
    scout, carrier = trial["scout"], trial["carrier"]
    checks = {
        "scout_reached": bool(scout["reached"]),
        "carrier_reached": bool(carrier["reached"]),
        "scout_within_goal_tolerance": scout["final_goal_error_m"]
        <= thresholds["goal_tolerance_m"],
        "carrier_within_goal_tolerance": carrier["final_goal_error_m"]
        <= thresholds["goal_tolerance_m"],
        "scout_wheel_actuation": scout["max_abs_wheel_target_rad_s"] > 0.1,
        "carrier_wheel_actuation": carrier["max_abs_wheel_target_rad_s"] > 0.1,
        "scout_path_nontrivial": scout["path_length_m"]
        >= thresholds["minimum_scout_path_m"],
        "carrier_path_nontrivial": carrier["path_length_m"]
        >= thresholds["minimum_carrier_path_m"],
        "carrier_stayed_parked_during_scout": scout["stationary_partner_drift_m"]
        <= thresholds["maximum_stationary_drift_m"],
        "scout_stayed_parked_during_carrier": carrier["stationary_partner_drift_m"]
        <= thresholds["maximum_stationary_drift_m"],
        "stable_tilt": max(scout["max_tilt_deg"], carrier["max_tilt_deg"])
        <= thresholds["maximum_tilt_deg"],
        "no_blocker_contact": (
            scout["obstacle_contact_rows"] + carrier["obstacle_contact_rows"] == 0
        ),
        "no_pair_robot_contact": (
            scout["robot_contact_rows"] + carrier["robot_contact_rows"] == 0
        ),
        "no_script_pose_teleport_after_build": trial[
            "script_entity_set_pos_calls_after_build"
        ]
        == 0,
    }
    return {"thresholds": thresholds, "checks": checks, "passed": all(checks.values())}


def summarize_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(bool(trial["assessment"]["passed"]) for trial in trials)
    scout = [trial["scout"] for trial in trials]
    carrier = [trial["carrier"] for trial in trials]
    return {
        "trials": len(trials),
        "passed": passed,
        "failed": len(trials) - passed,
        "pass_rate": passed / len(trials),
        "all_passed": passed == len(trials),
        "distinct_non_fixed_robot_entities": 2 * len(trials),
        "scout_reached": sum(bool(row["reached"]) for row in scout),
        "carrier_reached": sum(bool(row["reached"]) for row in carrier),
        "total_obstacle_contact_rows": sum(
            int(row["obstacle_contact_rows"]) for row in (*scout, *carrier)
        ),
        "total_pair_robot_contact_rows": sum(
            int(row["robot_contact_rows"]) for row in (*scout, *carrier)
        ),
        "maximum_tilt_deg": max(
            float(row["max_tilt_deg"]) for row in (*scout, *carrier)
        ),
        "maximum_stationary_partner_drift_m": max(
            float(row["stationary_partner_drift_m"]) for row in (*scout, *carrier)
        ),
        "mean_scout_path_m": statistics.fmean(
            float(row["path_length_m"]) for row in scout
        ),
        "mean_carrier_path_m": statistics.fmean(
            float(row["path_length_m"]) for row in carrier
        ),
    }


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    import genesis as gs
    import torch

    backend = gs.amdgpu if args.backend == "amdgpu" else gs.cpu
    gs.init(backend=backend, logging_level="warning")
    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(dt=args.dt),
    )
    scene.add_entity(gs.morphs.Plane())

    records: list[dict[str, Any]] = []
    for index, seed in enumerate(args.seeds):
        layout = trial_layout(seed, index)
        carrier = scene.add_entity(
            gs.morphs.URDF(
                file=str(ROBOT_SPECS["carrier"].urdf),
                pos=layout["carrier_start"],
                fixed=False,
            ),
            name=f"carrier-{seed}",
        )
        scout = scene.add_entity(
            gs.morphs.URDF(
                file=str(ROBOT_SPECS["scout"].urdf),
                pos=layout["scout_start"],
                fixed=False,
            ),
            name=f"scout-{seed}",
        )
        blocker = scene.add_entity(
            gs.morphs.Box(
                size=(0.45, 0.45, 0.50),
                pos=layout["blocker_pos"],
                fixed=True,
            ),
            surface=gs.surfaces.Default(color=(0.55, 0.18, 0.18)),
            name=f"blocked-lane-{seed}",
        )
        records.append(
            {
                "seed": seed,
                "layout": layout,
                "carrier_entity": carrier,
                "scout_entity": scout,
                "blocker_entity": blocker,
            }
        )

    scene.build()
    for record in records:
        record["carrier_indices"] = configure_velocity_control(
            record["carrier_entity"], ROBOT_SPECS["carrier"]
        )
        record["scout_indices"] = configure_velocity_control(
            record["scout_entity"], ROBOT_SPECS["scout"]
        )
    for _ in range(args.settle_steps):
        scene.step()

    trials: list[dict[str, Any]] = []
    for record in records:
        layout = record["layout"]
        scout_result = drive_waypoints(
            scene=scene,
            entity=record["scout_entity"],
            indices=record["scout_indices"],
            spec=ROBOT_SPECS["scout"],
            waypoints=layout["scout_waypoints"],
            stationary_entity=record["carrier_entity"],
            stationary_indices=record["carrier_indices"],
            blocker=record["blocker_entity"],
            drive_sign=args.drive_sign,
            maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
            tolerance_m=args.tolerance,
            record_stride=args.record_stride,
        )
        carrier_result = drive_waypoints(
            scene=scene,
            entity=record["carrier_entity"],
            indices=record["carrier_indices"],
            spec=ROBOT_SPECS["carrier"],
            waypoints=layout["carrier_waypoints"],
            stationary_entity=record["scout_entity"],
            stationary_indices=record["scout_indices"],
            blocker=record["blocker_entity"],
            drive_sign=args.drive_sign,
            maximum_steps_per_waypoint=args.maximum_steps_per_waypoint,
            tolerance_m=args.tolerance,
            record_stride=args.record_stride,
        )
        offset = tuple(layout["offset"])
        trial = {
            "seed": record["seed"],
            "world_offset_xy": list(offset),
            "clear_lane_y_local": layout["clear_lane_y"],
            "blocked_lane_y_local": layout["blocked_lane_y"],
            "carrier_start_xy_local": [-2.0, 0.0],
            "scout_start_xy_local": [-1.6, 1.2],
            "script_entity_set_pos_calls_after_build": 0,
            "scout": scout_result,
            "carrier": carrier_result,
        }
        trial["assessment"] = assess_trial(trial)
        trials.append(trial)

    script_path = Path(__file__).resolve()
    environment = {
        "python": platform.python_version(),
        "genesis": gs.__version__,
        "torch": torch.__version__,
        "torch_hip": torch.version.hip,
        "backend_requested": args.backend,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "boundary": {
            "additive_non_locked": True,
            "formal_result_eligible": False,
            "changes_frozen_v8_endpoint": False,
            "claim": (
                "Bounded, submission-time dual-body rigid-dynamics validation; "
                "not a rerun of the frozen V8 comparison and not real-robot evidence."
            ),
        },
        "source": {
            "git_commit": git_output("rev-parse", "HEAD"),
            "git_branch": git_output("branch", "--show-current"),
            "git_status_porcelain": git_output("status", "--porcelain"),
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": sha256_file(script_path),
            "carrier_urdf_sha256": sha256_file(ROBOT_SPECS["carrier"].urdf),
            "scout_urdf_sha256": sha256_file(ROBOT_SPECS["scout"].urdf),
        },
        "environment": environment,
        "protocol": {
            "seeds": list(args.seeds),
            "dt_seconds": args.dt,
            "settle_steps": args.settle_steps,
            "maximum_steps_per_waypoint": args.maximum_steps_per_waypoint,
            "goal_tolerance_m": args.tolerance,
            "drive_sign": args.drive_sign,
            "post_build_actuation_api": "control_dofs_velocity only",
            "carrier_and_scout_are_distinct_non_fixed_entities": True,
            "robot_specs": {
                name: {
                    "urdf": str(spec.urdf.relative_to(ROOT)),
                    "mass_kg": spec.mass_kg,
                    "wheel_radius_m": spec.wheel_radius,
                    "track_width_m": spec.track_width,
                    "maximum_wheel_force": spec.max_force,
                }
                for name, spec in ROBOT_SPECS.items()
            },
        },
        "summary": summarize_trials(trials),
        "trials": trials,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=DEFAULT_SEEDS,
        help="comma-separated seeds and/or half-open ranges, e.g. 160800:160820",
    )
    parser.add_argument("--backend", choices=("amdgpu", "cpu"), default="amdgpu")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dt", type=float, default=0.02)
    parser.add_argument("--settle-steps", type=int, default=80)
    parser.add_argument("--maximum-steps-per-waypoint", type=int, default=1800)
    parser.add_argument("--tolerance", type=float, default=0.14)
    parser.add_argument("--record-stride", type=int, default=20)
    parser.add_argument(
        "--drive-sign",
        type=float,
        choices=(-1.0, 1.0),
        default=-1.0,
        help="URDF joint-axis sign mapping; fixed by the published protocol",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.dt <= 0 or args.settle_steps < 0:
        raise SystemExit("dt must be positive and settle steps non-negative")
    if args.maximum_steps_per_waypoint < 1 or args.record_stride < 1:
        raise SystemExit("step limits must be positive")
    report = run_validation(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = report["summary"]
    print(
        f"dual_body_dynamics passed={summary['passed']}/{summary['trials']} "
        f"failed={summary['failed']} output={args.output}"
    )
    return 0 if summary["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
