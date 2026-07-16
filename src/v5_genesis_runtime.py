"""Genesis runtime for Look Twice v5 (navigation + grasp proxy object).

Wraps the v4 Genesis scene for physical/kinematic motion and adds a grasp
object. RGB-D / entity-segmentation capture is exposed via ``capture_raw`` and
``evidence_scenario`` so the episode layer can build real Depth + Semantic
Claims (see ``v5_rgbd_claims``). Synthetic Claims remain only for CPU CI.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from v4_genesis_runtime import GenesisEpisodeRuntime
from v4_scenario import SIMULATION_DT_SECONDS, ExternalEvent, sample_v4_scenario
from v5_scenario import V5ScenarioSample

_V4_PROFILES = {
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "pose-calibration-drift",
    "structured-depth-dropout",
    "dynamic-change",
    "ood-severity",
}


def _physics_profile(v5_profile: str) -> str:
    if v5_profile in _V4_PROFILES:
        return v5_profile
    if v5_profile == "manipulation-occlusion":
        return "shared-occlusion"
    if v5_profile == "repair-required":
        # Heavy first-view occlusion/fault; side views repair (same as shared-occlusion).
        return "shared-occlusion"
    return "independent-noise"


class V5GenesisRuntime:
    """EpisodeRuntime-compatible adapter for v5 on W7900D."""

    def __init__(
        self,
        scenario: V5ScenarioSample,
        *,
        motion_backend: str = "skid-steer",
        maximum_motion_steps: int = 2400,
    ) -> None:
        if motion_backend not in {"skid-steer", "kinematic"}:
            raise ValueError("motion_backend must be skid-steer or kinematic")
        physics_profile = _physics_profile(scenario.profile)
        v4_scenario = sample_v4_scenario(physics_profile, scenario.seed)
        v5_event = scenario.oracle_context.get("external_event")
        if v5_event:
            event_step = int(v5_event["step"])
            v4_scenario = replace(
                v4_scenario,
                external_event=ExternalEvent(
                    kind=str(v5_event["kind"]),
                    absolute_step=event_step,
                    absolute_time_seconds=event_step * SIMULATION_DT_SECONDS,
                    from_blocked=bool(scenario.oracle_context["nav_blocked_initial"]),
                    to_blocked=bool(v5_event["to_blocked"]),
                ),
            )
        self.v5_scenario = scenario
        self.motion_backend = motion_backend
        self._inner = GenesisEpisodeRuntime(
            v4_scenario,
            motion_backend=motion_backend,
            maximum_motion_steps=maximum_motion_steps,
        )
        # Grasp object as a free box near public grasp_xy (visual + collision).
        try:
            import genesis as gs

            gx, gy = scenario.public_context["grasp_xy"]
            self.grasp_object = self._inner.scene.add_entity(
                gs.morphs.Box(
                    size=(0.08, 0.08, 0.08),
                    pos=(float(gx), float(gy), 0.06),
                    fixed=False,
                ),
                surface=gs.surfaces.Default(color=(0.85, 0.55, 0.12)),
            )
            # Scene already built in GenesisEpisodeRuntime — late add may fail.
            # If add after build is unsupported, ignore; proxy grasp stays geometric.
            self._grasp_spawned = True
        except Exception:
            self.grasp_object = None
            self._grasp_spawned = False

    @property
    def current_step(self) -> int:
        return self._inner.current_step

    @property
    def current_pose(self):
        return self._inner.current_pose

    @property
    def collision_count(self) -> int:
        return self._inner.collision_count

    @property
    def environment(self) -> dict[str, Any]:
        env = dict(self._inner.environment)
        env["v5"] = True
        env["v5_motion_backend"] = self.motion_backend
        env["grasp_entity_spawned"] = self._grasp_spawned
        # Episode overwrites with genesis_rgbd_depth_semantic when RGB-D path runs.
        env["claims_mode"] = "genesis_rgbd_depth_semantic_available"
        env["formal_result_eligible"] = self.motion_backend in {
            "skid-steer",
            "kinematic",
        }
        return env

    @property
    def evidence_scenario(self) -> Any:
        """v4 ScenarioSample used by process_evidence_frame (fault/profile)."""
        return self._inner.scenario

    def move_to(self, target_xy: tuple[float, float]):
        return self._inner.move_to(target_xy)

    def wait_steps(self, count: int) -> None:
        return self._inner.wait_steps(count)

    def capture_raw(self, **kwargs):
        return self._inner.capture_raw(**kwargs)

    def close(self) -> None:
        return self._inner.close()


__all__ = ("V5GenesisRuntime", "_physics_profile")
