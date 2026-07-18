"""Genesis dual-agent runtime for Look Twice v6 (carrier + scout).

Uses one chassis in Genesis for physical RGB-D capture. Logical poses for
carrier and scout are tracked separately; when an agent acts, the chassis is
moved to that agent and captures from its viewpoint. Online claims never include
clean segmentation or world truth as policy inputs.

**World homology (v7 repair-required fix):** the Genesis blocking obstacle is
built from the *V6* oracle (`corridor_*_blocked_initial` / obstacle xy), not
from an independently sampled V4 base world. Rendering, collision, and
evaluation oracle must share that single obstacle state.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from v4_genesis_runtime import GenesisEpisodeRuntime
from v4_motion import Pose2D
from v4_scenario import (
    SIMULATION_DT_SECONDS,
    ExternalEvent,
    ScenarioSample,
    sample_v4_scenario,
)
from v6_motion import AgentMotionResult
from v6_scenario import CARRIER_ID, SCOUT_ID, V6ScenarioSample

CLAIMS_MODE_GENESIS_MULTI = "genesis_rgbd_multi_agent_v6"

# Canonical V6 dual-corridor obstacle anchors (must match synthetic runtime).
V6_OBSTACLE_A_XY = (1.0, -0.3)
V6_OBSTACLE_B_XY = (1.0, 0.3)
V6_OBSTACLE_SIZE = (0.45, 0.45, 0.50)
V6_OBSTACLE_Z = V6_OBSTACLE_SIZE[2] / 2.0
INACTIVE_OBSTACLE_POS = (-10.0, 0.0, V6_OBSTACLE_Z)


def _physics_profile(v6_profile: str) -> str:
    mapping = {
        "independent-noise": "independent-noise",
        "shared-occlusion": "shared-occlusion",
        "evidence-echo": "evidence-echo",
        "dynamic-change": "dynamic-change",
        "time-skew": "time-skew",
        "comm-fault": "shared-occlusion",
        "heavy-occlusion": "shared-occlusion",
        "multi-fault": "dynamic-change",
    }
    return mapping.get(v6_profile, "independent-noise")


def v6_oracle_obstacle_specs(scenario: V6ScenarioSample) -> list[dict[str, Any]]:
    """Return active obstacle specs from V6 oracle only (never V4 RNG)."""
    oracle = scenario.oracle_context
    specs: list[dict[str, Any]] = []
    if bool(oracle.get("corridor_a_blocked_initial")):
        specs.append(
            {
                "corridor_id": "corridor_a",
                "xy": list(V6_OBSTACLE_A_XY),
                "radius": 0.28,
                "size": list(V6_OBSTACLE_SIZE),
            }
        )
    if bool(oracle.get("corridor_b_blocked_initial")):
        specs.append(
            {
                "corridor_id": "corridor_b",
                "xy": list(V6_OBSTACLE_B_XY),
                "radius": 0.28,
                "size": list(V6_OBSTACLE_SIZE),
            }
        )
    return specs


def v6_aligned_v4_scenario(scenario: V6ScenarioSample) -> ScenarioSample:
    """Build a V4 ScenarioSample whose *world truth* matches V6 oracle.

    Reuses V4 fault/stress sampling for sensor noise, but forces obstacle
    placement and initial_blocked from V6. Clear corridors must not retain a
    leftover V4 random obstacle in the dual-corridor workspace.
    """
    physics_profile = _physics_profile(scenario.profile)
    # Sample only for fault realization / ids; world geometry is overwritten.
    base = sample_v4_scenario(physics_profile, scenario.seed)
    oracle = scenario.oracle_context
    a_blocked = bool(oracle.get("corridor_a_blocked_initial"))
    b_blocked = bool(oracle.get("corridor_b_blocked_initial"))
    initial_blocked = a_blocked or b_blocked
    # Primary obstacle entity: prefer A if both, else whichever is blocked.
    if a_blocked:
        obstacle_xy = V6_OBSTACLE_A_XY
    elif b_blocked:
        obstacle_xy = V6_OBSTACLE_B_XY
    else:
        # Parked; entity exists but is inactive in Genesis init path.
        obstacle_xy = (INACTIVE_OBSTACLE_POS[0], INACTIVE_OBSTACLE_POS[1])

    # Map V6 dynamic event onto V4 external_event for the primary obstacle.
    v6_event = oracle.get("external_event")
    if v6_event and int(v6_event.get("step", -1)) >= 0:
        event_step = int(v6_event["step"])
        cid = str(v6_event.get("corridor_id") or "corridor_a")
        to_blocked = bool(v6_event.get("to_blocked", True))
        # from_blocked for that corridor
        from_blocked = a_blocked if cid == "corridor_a" else b_blocked
        external = ExternalEvent(
            kind=str(v6_event.get("kind", "corridor_block_appear")),
            absolute_step=event_step,
            absolute_time_seconds=event_step * SIMULATION_DT_SECONDS,
            from_blocked=from_blocked,
            to_blocked=to_blocked,
        )
        # When event targets B while primary entity is A, V6 runtime moves the
        # correct entity via set_obstacle; still store schedule for step clock.
    else:
        external = ExternalEvent(
            kind="none",
            absolute_step=None,
            absolute_time_seconds=None,
            from_blocked=initial_blocked,
            to_blocked=initial_blocked,
        )

    # Keep occluder out of corridor ROI (V4 already does this for FOV stress).
    return replace(
        base,
        initial_blocked=initial_blocked,
        obstacle_xy=obstacle_xy,
        obstacle_size=V6_OBSTACLE_SIZE,
        external_event=external,
        paired_world_id=f"v6-aligned:{scenario.scenario_id}",
        scenario_id=f"v6-phys:{scenario.scenario_id}",
    )


def _entity_xy(entity: Any) -> tuple[float, float, float]:
    """Best-effort read of a Genesis entity world position."""
    try:
        pos = entity.get_pos()
        if hasattr(pos, "detach"):
            pos = pos.detach().cpu().numpy()
        arr = list(pos)
        return float(arr[0]), float(arr[1]), float(arr[2]) if len(arr) > 2 else 0.0
    except Exception:
        return float("nan"), float("nan"), float("nan")


class V6GenesisRuntime:
    """Dual-agent episode runtime backed by Genesis RGB-D on AMD GPU."""

    def __init__(
        self,
        scenario: V6ScenarioSample,
        *,
        motion_backend: str = "kinematic",
        maximum_motion_steps: int = 2400,
        device: str = "cuda:0",
    ) -> None:
        if motion_backend not in {"skid-steer", "kinematic"}:
            raise ValueError("motion_backend must be skid-steer or kinematic")
        self.scenario = scenario
        self.motion_backend = motion_backend
        self.device = device
        public = scenario.public_context
        self._oracle_specs = v6_oracle_obstacle_specs(scenario)
        v4_scenario = v6_aligned_v4_scenario(scenario)
        a_blocked = bool(scenario.oracle_context.get("corridor_a_blocked_initial"))
        b_blocked = bool(scenario.oracle_context.get("corridor_b_blocked_initial"))
        # Always pre-create secondary entity so dual-block and late B events work.
        self._inner = GenesisEpisodeRuntime(
            v4_scenario,
            motion_backend=motion_backend,
            maximum_motion_steps=maximum_motion_steps,
            secondary_obstacle_xy=V6_OBSTACLE_B_XY,
            secondary_obstacle_size=V6_OBSTACLE_SIZE,
            secondary_obstacle_active=bool(a_blocked and b_blocked),
        )
        # Disable V4's independent dynamic event on the primary entity when V6
        # owns multi-corridor placement (we apply V6 events via set_obstacle).
        self._inner._event_applied = True

        self._secondary_obstacle = self._inner.secondary_blocking_obstacle
        self._sync_physical_obstacles_from_oracle()

        cx, cy = public["carrier_start_xy"]
        sx, sy = public["scout_start_xy"]
        self._poses: dict[str, Pose2D] = {
            CARRIER_ID: Pose2D(float(cx), float(cy), 0.0),
            SCOUT_ID: Pose2D(float(sx), float(sy), 0.0),
        }
        self._active_agent = CARRIER_ID
        self._extra_collisions = 0
        self._admit_then_contact = False
        self._last_collision_entity: str | None = None
        self._last_collision_pose: list[float] | None = None
        self._snap_to_agent(CARRIER_ID)

    def _set_entity_pos(self, entity: Any, x: float, y: float, z: float | None = None) -> None:
        z = V6_OBSTACLE_Z if z is None else float(z)
        tensor = self._inner.torch.tensor(
            (float(x), float(y), float(z)),
            device=self.device if str(self.device).startswith("cuda") else "cuda:0",
            dtype=self._inner.torch.float32,
        )
        entity.set_pos(tensor)

    def _sync_physical_obstacles_from_oracle(self) -> None:
        """Place Genesis obstacle entities exactly at V6 oracle anchors.

        Primary entity owns corridor_a when A is blocked; secondary owns B.
        When only B is blocked, primary is parked inactive and secondary is
        active at B — never leave a V4-sampled obstacle in the clear lane.
        """
        a_blocked = bool(self.scenario.oracle_context.get("corridor_a_blocked_initial"))
        b_blocked = bool(self.scenario.oracle_context.get("corridor_b_blocked_initial"))
        primary = self._inner.blocking_obstacle
        secondary = self._secondary_obstacle

        if a_blocked:
            self._set_entity_pos(primary, *V6_OBSTACLE_A_XY)
        else:
            self._set_entity_pos(primary, *INACTIVE_OBSTACLE_POS[:2])

        if secondary is not None:
            if b_blocked:
                self._set_entity_pos(secondary, *V6_OBSTACLE_B_XY)
            else:
                self._set_entity_pos(secondary, -10.0, -2.0)
        elif b_blocked and not a_blocked:
            # No secondary: place primary at B.
            self._set_entity_pos(primary, *V6_OBSTACLE_B_XY)
        elif b_blocked and a_blocked:
            # Dual block without secondary is unrecoverable homology fail.
            pass

        if a_blocked:
            self._inner._active_obstacle_position = (
                V6_OBSTACLE_A_XY[0],
                V6_OBSTACLE_A_XY[1],
                V6_OBSTACLE_Z,
            )
        elif b_blocked:
            self._inner._active_obstacle_position = (
                V6_OBSTACLE_B_XY[0],
                V6_OBSTACLE_B_XY[1],
                V6_OBSTACLE_Z,
            )
        else:
            self._inner._active_obstacle_position = INACTIVE_OBSTACLE_POS

    def _snap_to_agent(self, agent_id: str) -> None:
        pose = self._poses[agent_id]
        current = self._inner.current_pose
        if math.hypot(current.x - pose.x, current.y - pose.y) > 0.05:
            self._inner.move_to((pose.x, pose.y))
        self._active_agent = agent_id

    @property
    def current_step(self) -> int:
        return self._inner.current_step

    @property
    def collision_count(self) -> int:
        return int(self._inner.collision_count) + self._extra_collisions

    @property
    def evidence_scenario(self) -> Any:
        return self._inner.scenario

    def pose_of(self, agent_id: str) -> Pose2D:
        return self._poses[agent_id]

    def physical_obstacle_poses(self) -> list[dict[str, Any]]:
        """Current physical obstacle entity poses (for alignment audit)."""
        out: list[dict[str, Any]] = []
        px, py, pz = _entity_xy(self._inner.blocking_obstacle)
        out.append(
            {
                "entity": "blocking_obstacle_primary",
                "xy": [px, py],
                "xyz": [px, py, pz],
            }
        )
        if self._secondary_obstacle is not None:
            sx, sy, sz = _entity_xy(self._secondary_obstacle)
            out.append(
                {
                    "entity": "blocking_obstacle_secondary",
                    "xy": [sx, sy],
                    "xyz": [sx, sy, sz],
                }
            )
        return out

    def world_alignment_audit(self) -> dict[str, Any]:
        """Compare V6 oracle obstacle anchors to physical Genesis entities."""
        oracle_specs = v6_oracle_obstacle_specs(self.scenario)
        physical = self.physical_obstacle_poses()
        # Match each oracle corridor obstacle to nearest physical entity
        # that is not parked inactive.
        active_phys = [
            p
            for p in physical
            if math.isfinite(p["xy"][0]) and p["xy"][0] > -5.0
        ]
        pose_errors: list[float] = []
        matched: list[dict[str, Any]] = []
        for spec in oracle_specs:
            ox, oy = float(spec["xy"][0]), float(spec["xy"][1])
            best = None
            best_err = float("inf")
            for p in active_phys:
                err = math.hypot(p["xy"][0] - ox, p["xy"][1] - oy)
                if err < best_err:
                    best_err = err
                    best = p
            pose_errors.append(best_err if best is not None else float("inf"))
            matched.append(
                {
                    "corridor_id": spec["corridor_id"],
                    "oracle_xy": [ox, oy],
                    "physical_xy": None if best is None else list(best["xy"]),
                    "error": best_err if best is not None else None,
                }
            )
        # Extra physical entities not matched (false obstacles in workspace).
        unmatched_phys = []
        for p in active_phys:
            used = False
            for m in matched:
                if m["physical_xy"] and math.hypot(
                    p["xy"][0] - m["physical_xy"][0],
                    p["xy"][1] - m["physical_xy"][1],
                ) < 1e-3:
                    used = True
                    break
            if not used:
                unmatched_phys.append(p)

        max_err = max(pose_errors) if pose_errors else 0.0
        # If oracle has no obstacles, require no active physical in workspace.
        if not oracle_specs:
            max_err = 0.0 if not active_phys else float("inf")
            if active_phys:
                unmatched_phys = active_phys

        world_alignment_passed = (
            max_err <= 1e-4
            and not unmatched_phys
            and all(e is not None and e <= 1e-4 for e in pose_errors)
            if oracle_specs
            else (not active_phys)
        )
        a_b = bool(self.scenario.oracle_context.get("corridor_a_blocked_initial"))
        b_b = bool(self.scenario.oracle_context.get("corridor_b_blocked_initial"))
        if a_b and b_b and self._secondary_obstacle is None:
            world_alignment_passed = False

        return {
            "oracle_obstacle_pose": [s["xy"] for s in oracle_specs],
            "oracle_obstacle_specs": oracle_specs,
            "physical_obstacle_pose": [p["xy"] for p in physical],
            "physical_obstacles": physical,
            "matched": matched,
            "unmatched_physical": unmatched_phys,
            "obstacle_pose_error": max_err if math.isfinite(max_err) else None,
            "obstacle_pose_errors": pose_errors,
            "world_alignment_passed": bool(world_alignment_passed),
            "admit_then_contact": bool(self._admit_then_contact),
            "last_collision_entity": self._last_collision_entity,
            "last_collision_pose": self._last_collision_pose,
        }

    def environment(self) -> dict[str, Any]:
        env = dict(self._inner.environment)
        env["v6"] = True
        env["v6_motion_backend"] = self.motion_backend
        env["device"] = self.device
        env["claims_mode"] = CLAIMS_MODE_GENESIS_MULTI
        env["dual_agent"] = True
        env["world_homology"] = "v6_oracle_obstacles"
        env["world_alignment"] = self.world_alignment_audit()
        # Per-episode: inputs/homology can be marked eligible, but a single
        # episode must never self-declare formal_result_eligible=true.
        # Only locked-test / matrix aggregators may promote formal eligibility.
        env["artifact_inputs_eligible"] = bool(
            env["world_alignment"].get("world_alignment_passed")
        )
        env["formal_result_eligible"] = False
        return env

    def wait_steps(self, count: int) -> None:
        self._inner.wait_steps(count)

    def move_agent_to(
        self,
        agent_id: str,
        target_xy: tuple[float, float],
        *,
        risk_gated: bool = False,
        allow_without_admit: bool = True,
        admitted: bool = False,
    ) -> AgentMotionResult:
        if agent_id not in self._poses:
            raise KeyError(agent_id)
        if risk_gated and not allow_without_admit and not admitted:
            start = self._poses[agent_id]
            if self._segment_hits_risk((start.x, start.y), target_xy):
                return AgentMotionResult(
                    agent_id=agent_id,
                    reached=False,
                    target_xy=(float(target_xy[0]), float(target_xy[1])),
                    final_pose=start,
                    path_length=0.0,
                    collision_count=0,
                    elapsed_steps=0,
                    reason="gate_denied_risk_motion",
                )
        self._snap_to_agent(agent_id)
        start_step = self.current_step
        coll_before = self.collision_count
        result = self._inner.move_to((float(target_xy[0]), float(target_xy[1])))
        # Also count contact with secondary obstacle if present.
        extra = self._count_secondary_contacts()
        if extra:
            self._extra_collisions += extra
        final = result.final_pose
        self._poses[agent_id] = Pose2D(final.x, final.y, final.yaw)
        coll_after = self.collision_count
        if coll_after > coll_before:
            self._last_collision_pose = [final.x, final.y, final.yaw]
            self._last_collision_entity = (
                "blocking_obstacle_secondary"
                if extra
                else "blocking_obstacle_primary"
            )
            if admitted and agent_id == CARRIER_ID:
                self._admit_then_contact = True
        return AgentMotionResult(
            agent_id=agent_id,
            reached=bool(result.reached),
            target_xy=(float(target_xy[0]), float(target_xy[1])),
            final_pose=self._poses[agent_id],
            path_length=float(result.path_length),
            collision_count=int(result.collision_count) + extra,
            elapsed_steps=max(0, self.current_step - start_step),
            reason=str(result.reason),
            trajectory=tuple(result.trajectory) if result.trajectory else (),
            control_commands=tuple(getattr(result, "controls", ()) or ()),
        )

    def _count_secondary_contacts(self) -> int:
        if self._secondary_obstacle is None:
            return 0
        try:
            from v4_genesis_runtime import _contact_rows

            contacts = _contact_rows(
                self._inner.robot.get_contacts(with_entity=self._secondary_obstacle)
            )
            return 1 if contacts > 0 else 0
        except Exception:
            return 0

    def set_obstacle(self, x: float, y: float, radius: float = 0.25) -> None:
        """Move a real Genesis obstacle entity to (x, y) — not a bookkeeping stub.

        Corridor B anchors use the secondary entity; A uses primary.
        """
        x, y = float(x), float(y)
        use_secondary = (
            abs(y - V6_OBSTACLE_B_XY[1]) < 0.08
            and self._secondary_obstacle is not None
        )
        if use_secondary:
            self._set_entity_pos(self._secondary_obstacle, x, y)
        else:
            self._set_entity_pos(self._inner.blocking_obstacle, x, y)
            self._inner._active_obstacle_position = (x, y, V6_OBSTACLE_Z)
        self._extra_obstacles = getattr(self, "_extra_obstacles", [])
        self._extra_obstacles.append((x, y, float(radius)))

    def _segment_hits_risk(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> bool:
        corridors = self.scenario.public_context.get("corridors") or []
        for _ in range(11):
            t = _ / 10.0
            x = a[0] + t * (b[0] - a[0])
            y = a[1] + t * (b[1] - a[1])
            for c in corridors:
                min_x, max_x, min_y, max_y = c["region"]
                if min_x <= x <= max_x and min_y <= y <= max_y:
                    return True
        return False

    def capture_raw(
        self,
        *,
        agent_id: str,
        viewpoint: str,
        viewpoint_xy: tuple[float, float],
        predicted_coverage: float,
    ):
        self._snap_to_agent(agent_id)
        return self._inner.capture_raw(
            viewpoint=f"{agent_id}:{viewpoint}",
            viewpoint_xy=viewpoint_xy,
            predicted_coverage=predicted_coverage,
        )

    def close(self) -> None:
        return self._inner.close()


__all__ = (
    "V6GenesisRuntime",
    "CLAIMS_MODE_GENESIS_MULTI",
    "V6_OBSTACLE_A_XY",
    "V6_OBSTACLE_B_XY",
    "_physics_profile",
    "v6_aligned_v4_scenario",
    "v6_oracle_obstacle_specs",
)
