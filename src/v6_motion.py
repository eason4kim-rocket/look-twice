"""Multi-agent kinematic motion for v6 (batched training / CI)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from v4_motion import Pose2D


@dataclass(frozen=True, slots=True)
class AgentMotionResult:
    agent_id: str
    reached: bool
    target_xy: tuple[float, float]
    final_pose: Pose2D
    path_length: float
    collision_count: int
    elapsed_steps: int
    reason: str
    trajectory: tuple[dict[str, Any], ...] = ()
    control_commands: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["final_pose"] = {
            "x": self.final_pose.x,
            "y": self.final_pose.y,
            "yaw": self.final_pose.yaw,
        }
        payload["target_xy"] = list(self.target_xy)
        payload["trajectory"] = list(self.trajectory)
        payload["control_commands"] = list(self.control_commands)
        return payload


@dataclass
class MultiAgentKinematicRuntime:
    """Lightweight dual-agent runtime for unit tests and synthetic smokes."""

    poses: dict[str, Pose2D]
    step: int = 0
    collision_count: int = 0
    obstacles: list[tuple[float, float, float]] = field(default_factory=list)
    # obstacles: x, y, radius
    risk_regions: list[tuple[float, float, float, float]] = field(default_factory=list)
    max_speed: float = 0.15  # m per sim step

    @property
    def current_step(self) -> int:
        return self.step

    def pose_of(self, agent_id: str) -> Pose2D:
        return self.poses[agent_id]

    def wait_steps(self, n: int) -> None:
        self.step += max(0, int(n))

    def move_agent_to(
        self,
        agent_id: str,
        target_xy: tuple[float, float],
        *,
        risk_gated: bool = False,
        allow_without_admit: bool = True,
        admitted: bool = False,
    ) -> AgentMotionResult:
        if agent_id not in self.poses:
            raise KeyError(agent_id)
        start = self.poses[agent_id]
        tx, ty = float(target_xy[0]), float(target_xy[1])
        # Risk gate: refuse entry into risk region without admit.
        if risk_gated and not allow_without_admit and not admitted:
            if self._segment_hits_risk((start.x, start.y), (tx, ty)):
                return AgentMotionResult(
                    agent_id=agent_id,
                    reached=False,
                    target_xy=(tx, ty),
                    final_pose=start,
                    path_length=0.0,
                    collision_count=0,
                    elapsed_steps=0,
                    reason="gate_denied_risk_motion",
                )

        dist = math.hypot(tx - start.x, ty - start.y)
        steps = max(1, int(math.ceil(dist / self.max_speed))) if dist > 1e-9 else 1
        traj: list[dict[str, Any]] = []
        controls: list[dict[str, Any]] = []
        path = 0.0
        x, y = start.x, start.y
        collisions = 0
        for i in range(1, steps + 1):
            nx = start.x + (tx - start.x) * (i / steps)
            ny = start.y + (ty - start.y) * (i / steps)
            path += math.hypot(nx - x, ny - y)
            if self._collides(nx, ny):
                collisions += 1
                self.collision_count += 1
                pose = Pose2D(x, y, math.atan2(ty - start.y, tx - start.x))
                self.poses[agent_id] = pose
                self.step += i
                return AgentMotionResult(
                    agent_id=agent_id,
                    reached=False,
                    target_xy=(tx, ty),
                    final_pose=pose,
                    path_length=path,
                    collision_count=collisions,
                    elapsed_steps=i,
                    reason="collision",
                    trajectory=tuple(traj),
                    control_commands=tuple(controls),
                )
            x, y = nx, ny
            traj.append({"step": i, "x": x, "y": y})
            controls.append({"step": i, "v": self.max_speed, "w": 0.0})
        yaw = math.atan2(ty - start.y, tx - start.x) if dist > 1e-9 else start.yaw
        pose = Pose2D(tx, ty, yaw)
        self.poses[agent_id] = pose
        self.step += steps
        return AgentMotionResult(
            agent_id=agent_id,
            reached=True,
            target_xy=(tx, ty),
            final_pose=pose,
            path_length=path if dist > 1e-9 else 0.0,
            collision_count=collisions,
            elapsed_steps=steps,
            reason="ok",
            trajectory=tuple(traj),
            control_commands=tuple(controls),
        )

    def _collides(self, x: float, y: float) -> bool:
        for ox, oy, r in self.obstacles:
            if math.hypot(x - ox, y - oy) <= r:
                return True
        return False

    def _segment_hits_risk(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> bool:
        for _ in range(11):
            t = _ / 10.0
            x = a[0] + t * (b[0] - a[0])
            y = a[1] + t * (b[1] - a[1])
            for min_x, max_x, min_y, max_y in self.risk_regions:
                if min_x <= x <= max_x and min_y <= y <= max_y:
                    return True
        return False

    def set_obstacle(self, x: float, y: float, radius: float = 0.25) -> None:
        self.obstacles.append((float(x), float(y), float(radius)))

    def clear_obstacles(self) -> None:
        self.obstacles.clear()

    def environment(self) -> dict[str, Any]:
        return {
            "runtime": "v6-synthetic-kinematic",
            "formal_result_eligible": False,
            "physics_backend": "batched-kinematic",
            "v6": True,
        }

    def close(self) -> None:
        return None


def build_runtime_from_scenario(scenario: Any) -> MultiAgentKinematicRuntime:
    from v6_scenario import CARRIER_ID, SCOUT_ID

    public = scenario.public_context
    poses = {
        CARRIER_ID: Pose2D(
            float(public["carrier_start_xy"][0]),
            float(public["carrier_start_xy"][1]),
            0.0,
        ),
        SCOUT_ID: Pose2D(
            float(public["scout_start_xy"][0]),
            float(public["scout_start_xy"][1]),
            0.0,
        ),
    }
    risks = [tuple(c["region"]) for c in public["corridors"]]
    rt = MultiAgentKinematicRuntime(poses=poses, risk_regions=list(risks))
    # Place oracle obstacles only inside runtime for collision/truth; never claims.
    if scenario.oracle_context.get("corridor_a_blocked_initial"):
        rt.set_obstacle(1.0, -0.3, 0.28)
    if scenario.oracle_context.get("corridor_b_blocked_initial"):
        rt.set_obstacle(1.0, 0.3, 0.28)
    return rt


__all__ = (
    "AgentMotionResult",
    "MultiAgentKinematicRuntime",
    "build_runtime_from_scenario",
)
