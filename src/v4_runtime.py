"""Runtime adapters for the v4 evidence/action closed loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from v4_evidence import RawEvidenceFrame, SyntheticEvidenceSource
from v4_motion import KinematicMotionController, MotionResult, Pose2D
from v4_scenario import ScenarioSample, TARGET_REGION


class EpisodeRuntime(Protocol):
    @property
    def current_step(self) -> int: ...

    @property
    def current_pose(self) -> Pose2D: ...

    @property
    def collision_count(self) -> int: ...

    @property
    def environment(self) -> dict[str, Any]: ...

    def move_to(self, target_xy: tuple[float, float]) -> MotionResult: ...

    def wait_steps(self, count: int) -> None: ...

    def capture_raw(
        self,
        *,
        viewpoint: str,
        viewpoint_xy: tuple[float, float],
        predicted_coverage: float,
    ) -> RawEvidenceFrame: ...

    def close(self) -> None: ...


@dataclass
class _SyntheticState:
    pose: Pose2D
    step: int = 0
    collisions: int = 0
    in_contact: bool = False


class SyntheticEpisodeRuntime:
    """CI-only deterministic runtime; never label its output as a GPU result."""

    def __init__(
        self,
        scenario: ScenarioSample,
        *,
        start_pose: Pose2D = Pose2D(-2.0, 0.0, 0.0),
        dt: float = 0.02,
        maximum_motion_steps: int = 2000,
        final_heading_provider: Callable[[tuple[float, float]], float | None]
        | None = None,
        risk_region: tuple[float, float, float, float] = TARGET_REGION,
    ) -> None:
        self.scenario = scenario
        self.risk_region = risk_region
        self.state = _SyntheticState(start_pose)
        self.source = SyntheticEvidenceSource()
        self.controller = KinematicMotionController(
            get_pose=lambda: self.state.pose,
            apply_pose=self._apply_pose,
            simulation_step=self._step_once,
            obstacle_contact_count=lambda: self.state.collisions,
            dt=dt,
            maximum_steps=maximum_motion_steps,
            final_heading_provider=final_heading_provider,
        )

    @property
    def current_step(self) -> int:
        return self.state.step

    @property
    def current_pose(self) -> Pose2D:
        return self.state.pose

    @property
    def collision_count(self) -> int:
        return self.state.collisions

    @property
    def environment(self) -> dict[str, Any]:
        return {
            "runtime": "synthetic-ci",
            "physics_backend": "deterministic-unicycle",
            "gpu": None,
            "rocm": None,
            "formal_result_eligible": False,
        }

    def _apply_pose(self, pose: Pose2D) -> None:
        self.state.pose = pose

    def _step_once(self) -> None:
        self.state.step += 1
        pose = self.state.pose
        min_x, max_x, min_y, max_y = self.risk_region
        in_risk_region = (
            min_x <= pose.x <= max_x
            and min_y <= pose.y <= max_y
        )
        contact = in_risk_region and self.scenario.truth_blocked_at(self.state.step)
        if contact and not self.state.in_contact:
            self.state.collisions += 1
        self.state.in_contact = contact

    def move_to(self, target_xy: tuple[float, float]) -> MotionResult:
        return self.controller.move_to(target_xy)

    def wait_steps(self, count: int) -> None:
        if count < 0:
            raise ValueError("wait count cannot be negative")
        for _ in range(count):
            self._step_once()

    def capture_raw(
        self,
        *,
        viewpoint: str,
        viewpoint_xy: tuple[float, float],
        predicted_coverage: float,
    ) -> RawEvidenceFrame:
        return self.source.raw_frame(
            scenario=self.scenario,
            viewpoint=viewpoint,
            viewpoint_xy=viewpoint_xy,
            predicted_coverage=predicted_coverage,
            capture_step=self.current_step,
        )

    def close(self) -> None:
        return None


def runtime_from_name(
    name: str,
    *,
    scenario: ScenarioSample,
    evidence_dir: Path | None = None,
) -> EpisodeRuntime:
    del evidence_dir
    if name == "synthetic":
        return SyntheticEpisodeRuntime(scenario)
    raise ValueError(f"unsupported runtime adapter: {name}")


__all__ = ("EpisodeRuntime", "SyntheticEpisodeRuntime", "runtime_from_name")
