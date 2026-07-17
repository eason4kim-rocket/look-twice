"""Genesis dual-agent runtime for Look Twice v6 (carrier + scout).

Uses one chassis in Genesis for physical RGB-D capture. Logical poses for
carrier and scout are tracked separately; when an agent acts, the chassis is
moved to that agent and captures from its viewpoint. Online claims never include
clean segmentation or world truth as policy inputs.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from v4_genesis_runtime import GenesisEpisodeRuntime
from v4_motion import Pose2D
from v4_scenario import SIMULATION_DT_SECONDS, ExternalEvent, sample_v4_scenario
from v6_motion import AgentMotionResult
from v6_scenario import CARRIER_ID, SCOUT_ID, V6ScenarioSample

CLAIMS_MODE_GENESIS_MULTI = "genesis_rgbd_multi_agent_v6"


def _physics_profile(v6_profile: str) -> str:
    mapping = {
        "independent-noise": "independent-noise",
        "shared-occlusion": "shared-occlusion",
        "evidence-echo": "evidence-echo",
        "dynamic-change": "dynamic-change",
        "time-skew": "time-skew",
        "comm-fault": "shared-occlusion",
    }
    return mapping.get(v6_profile, "independent-noise")


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
        physics_profile = _physics_profile(scenario.profile)
        v4_scenario = sample_v4_scenario(physics_profile, scenario.seed)
        # Align dynamic event with v6 absolute schedule when present.
        v6_event = scenario.oracle_context.get("external_event")
        if v6_event:
            event_step = int(v6_event["step"])
            a_blocked = bool(scenario.oracle_context.get("corridor_a_blocked_initial"))
            v4_scenario = replace(
                v4_scenario,
                external_event=ExternalEvent(
                    kind=str(v6_event.get("kind", "corridor_block_appear")),
                    absolute_step=event_step,
                    absolute_time_seconds=event_step * SIMULATION_DT_SECONDS,
                    from_blocked=a_blocked,
                    to_blocked=bool(v6_event.get("to_blocked", True)),
                ),
            )
        self._inner = GenesisEpisodeRuntime(
            v4_scenario,
            motion_backend=motion_backend,
            maximum_motion_steps=maximum_motion_steps,
        )
        cx, cy = public["carrier_start_xy"]
        sx, sy = public["scout_start_xy"]
        self._poses: dict[str, Pose2D] = {
            CARRIER_ID: Pose2D(float(cx), float(cy), 0.0),
            SCOUT_ID: Pose2D(float(sx), float(sy), 0.0),
        }
        self._active_agent = CARRIER_ID
        self._extra_collisions = 0
        # Place chassis at carrier start.
        self._snap_to_agent(CARRIER_ID)

    def _snap_to_agent(self, agent_id: str) -> None:
        pose = self._poses[agent_id]
        # Kinematic path: move_to current pose is cheap; if far, move.
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

    def environment(self) -> dict[str, Any]:
        env = dict(self._inner.environment)
        env["v6"] = True
        env["v6_motion_backend"] = self.motion_backend
        env["device"] = self.device
        env["claims_mode"] = CLAIMS_MODE_GENESIS_MULTI
        env["dual_agent"] = True
        env["formal_result_eligible"] = False  # smoke path unless calibrated
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
        # Gate: refuse risk entry without admit (use corridor risk regions).
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
        start_pose = self._inner.current_pose
        result = self._inner.move_to((float(target_xy[0]), float(target_xy[1])))
        final = result.final_pose
        self._poses[agent_id] = Pose2D(final.x, final.y, final.yaw)
        if result.collision_count:
            self._extra_collisions += 0  # already in inner
        return AgentMotionResult(
            agent_id=agent_id,
            reached=bool(result.reached),
            target_xy=(float(target_xy[0]), float(target_xy[1])),
            final_pose=self._poses[agent_id],
            path_length=float(result.path_length),
            collision_count=int(result.collision_count),
            elapsed_steps=max(0, self.current_step - start_step),
            reason=str(result.reason),
            trajectory=tuple(result.trajectory) if result.trajectory else (),
            control_commands=tuple(getattr(result, "controls", ()) or ()),
        )

    def set_obstacle(self, x: float, y: float, radius: float = 0.25) -> None:
        # Best-effort: kinematic/scene may not support late add; track for risk only.
        self._extra_obstacles = getattr(self, "_extra_obstacles", [])
        self._extra_obstacles.append((float(x), float(y), float(radius)))

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


__all__ = ("V6GenesisRuntime", "CLAIMS_MODE_GENESIS_MULTI", "_physics_profile")
