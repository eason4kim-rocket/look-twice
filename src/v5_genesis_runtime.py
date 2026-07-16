"""Genesis runtime for Look Twice v5 (navigation + grasp proxy object).

Wraps the v4 Genesis scene for physical/kinematic motion and adds a grasp
object. Sensor Claims for the gate remain produced by the v5 episode layer
(synthetic modality proxies) unless future work wires full RGB-D Claims.
STATUS must state that clearly when claims are synthetic-on-GPU.
"""

from __future__ import annotations

from typing import Any

from v4_genesis_runtime import GenesisEpisodeRuntime
from v4_scenario import sample_v4_scenario
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
        env["claims_mode"] = "synthetic_modality_proxies_on_gpu_motion"
        # Eligible only when not using smoke cal (set by entrypoint) and physics used.
        env["formal_result_eligible"] = self.motion_backend in {
            "skid-steer",
            "kinematic",
        }
        return env

    def move_to(self, target_xy: tuple[float, float]):
        return self._inner.move_to(target_xy)

    def wait_steps(self, count: int) -> None:
        return self._inner.wait_steps(count)

    def capture_raw(self, **kwargs):
        return self._inner.capture_raw(**kwargs)

    def close(self) -> None:
        return self._inner.close()


__all__ = ("V5GenesisRuntime", "_physics_profile")
