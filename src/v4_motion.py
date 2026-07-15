"""Motion backends shared by the Look Twice v4 batch and physical demos.

The controller code deliberately has no Genesis import.  The integration layer
provides small callbacks, which keeps the control law deterministic and lets the
CPU test suite exercise the exact same waypoint follower used on the GPU scene.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class ControlCommand:
    linear_velocity: float
    angular_velocity: float
    left_wheel_velocity: float
    right_wheel_velocity: float


@dataclass(frozen=True)
class MotionResult:
    reached: bool
    target_xy: tuple[float, float]
    final_pose: Pose2D
    path_length: float
    collision_count: int
    elapsed_steps: int
    reason: str
    trajectory: tuple[dict[str, float | int], ...]
    controls: tuple[dict[str, float | int], ...]

    def to_dict(self) -> dict:
        return asdict(self)


class MotionController(Protocol):
    def move_to(self, target_xy: tuple[float, float]) -> MotionResult: ...


def wrap_angle(angle: float) -> float:
    """Return an angle in [-pi, pi)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class DifferentialDriveControlLaw:
    """A bounded heading-and-distance controller for a skid-steer base."""

    def __init__(
        self,
        *,
        wheel_radius: float = 0.07,
        track_width: float = 0.34,
        linear_gain: float = 1.25,
        heading_gain: float = 2.5,
        max_linear_velocity: float = 0.55,
        max_angular_velocity: float = 1.6,
    ) -> None:
        if wheel_radius <= 0 or track_width <= 0:
            raise ValueError("wheel radius and track width must be positive")
        self.wheel_radius = wheel_radius
        self.track_width = track_width
        self.linear_gain = linear_gain
        self.heading_gain = heading_gain
        self.max_linear_velocity = max_linear_velocity
        self.max_angular_velocity = max_angular_velocity

    def command(self, pose: Pose2D, target_xy: tuple[float, float]) -> ControlCommand:
        dx = target_xy[0] - pose.x
        dy = target_xy[1] - pose.y
        distance = math.hypot(dx, dy)
        desired_heading = math.atan2(dy, dx)
        heading_error = wrap_angle(desired_heading - pose.yaw)

        angular = max(
            -self.max_angular_velocity,
            min(self.max_angular_velocity, self.heading_gain * heading_error),
        )
        # Do not drive aggressively sideways while the chassis is still turning.
        alignment = max(0.0, math.cos(heading_error))
        linear = min(self.max_linear_velocity, self.linear_gain * distance) * alignment
        left = (linear - 0.5 * self.track_width * angular) / self.wheel_radius
        right = (linear + 0.5 * self.track_width * angular) / self.wheel_radius
        return ControlCommand(linear, angular, left, right)

    def rotation_command(self, pose: Pose2D, target_yaw: float) -> ControlCommand:
        heading_error = wrap_angle(target_yaw - pose.yaw)
        angular = max(
            -self.max_angular_velocity,
            min(self.max_angular_velocity, self.heading_gain * heading_error),
        )
        left = (-0.5 * self.track_width * angular) / self.wheel_radius
        right = (0.5 * self.track_width * angular) / self.wheel_radius
        return ControlCommand(0.0, angular, left, right)


class _CallbackMotionBase:
    def __init__(
        self,
        *,
        get_pose: Callable[[], Pose2D],
        simulation_step: Callable[[], None],
        obstacle_contact_count: Callable[[], int],
        control_law: DifferentialDriveControlLaw | None = None,
        tolerance: float = 0.08,
        maximum_steps: int = 2000,
        record_stride: int = 2,
        final_heading_provider: Callable[[tuple[float, float]], float | None]
        | None = None,
        heading_tolerance: float = 0.06,
    ) -> None:
        if (
            tolerance <= 0
            or heading_tolerance <= 0
            or maximum_steps < 1
            or record_stride < 1
        ):
            raise ValueError("motion limits must be positive")
        self.get_pose = get_pose
        self.simulation_step = simulation_step
        self.obstacle_contact_count = obstacle_contact_count
        self.control_law = control_law or DifferentialDriveControlLaw()
        self.tolerance = tolerance
        self.maximum_steps = maximum_steps
        self.record_stride = record_stride
        self.final_heading_provider = final_heading_provider
        self.heading_tolerance = heading_tolerance

    def _command_or_complete(
        self, pose: Pose2D, target_xy: tuple[float, float]
    ) -> ControlCommand | None:
        if math.dist((pose.x, pose.y), target_xy) > self.tolerance:
            return self.control_law.command(pose, target_xy)
        if self.final_heading_provider is None:
            return None
        target_yaw = self.final_heading_provider(target_xy)
        if target_yaw is None or abs(wrap_angle(target_yaw - pose.yaw)) <= self.heading_tolerance:
            return None
        return self.control_law.rotation_command(pose, target_yaw)

    @staticmethod
    def _distance(a: Pose2D, b: Pose2D) -> float:
        return math.hypot(b.x - a.x, b.y - a.y)

    def _finish(
        self,
        *,
        reached: bool,
        target_xy: tuple[float, float],
        path_length: float,
        collision_count: int,
        elapsed_steps: int,
        reason: str,
        trajectory: list[dict[str, float | int]],
        controls: list[dict[str, float | int]],
    ) -> MotionResult:
        return MotionResult(
            reached=reached,
            target_xy=target_xy,
            final_pose=self.get_pose(),
            path_length=path_length,
            collision_count=collision_count,
            elapsed_steps=elapsed_steps,
            reason=reason,
            trajectory=tuple(trajectory),
            controls=tuple(controls),
        )


class KinematicMotionController(_CallbackMotionBase):
    """Fast experiment backend using explicit unicycle integration."""

    def __init__(
        self,
        *,
        apply_pose: Callable[[Pose2D], None],
        dt: float = 0.02,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.apply_pose = apply_pose
        self.dt = dt

    def move_to(self, target_xy: tuple[float, float]) -> MotionResult:
        trajectory: list[dict[str, float | int]] = []
        controls: list[dict[str, float | int]] = []
        path_length = 0.0
        initial_contacts = self.obstacle_contact_count()
        previous = self.get_pose()
        for step in range(self.maximum_steps + 1):
            pose = self.get_pose()
            command = self._command_or_complete(pose, target_xy)
            if command is None:
                if not trajectory:
                    trajectory.append({"step": step, **asdict(pose)})
                    controls.append(
                        {
                            "step": step,
                            "linear_velocity": 0.0,
                            "angular_velocity": 0.0,
                            "left_wheel_velocity": 0.0,
                            "right_wheel_velocity": 0.0,
                        }
                    )
                return self._finish(
                    reached=True,
                    target_xy=target_xy,
                    path_length=path_length,
                    collision_count=max(0, self.obstacle_contact_count() - initial_contacts),
                    elapsed_steps=step,
                    reason="reached",
                    trajectory=trajectory,
                    controls=controls,
                )
            if self.obstacle_contact_count() > initial_contacts:
                return self._finish(
                    reached=False,
                    target_xy=target_xy,
                    path_length=path_length,
                    collision_count=self.obstacle_contact_count() - initial_contacts,
                    elapsed_steps=step,
                    reason="obstacle_contact",
                    trajectory=trajectory,
                    controls=controls,
                )
            next_yaw = wrap_angle(pose.yaw + command.angular_velocity * self.dt)
            next_pose = Pose2D(
                x=pose.x + command.linear_velocity * math.cos(next_yaw) * self.dt,
                y=pose.y + command.linear_velocity * math.sin(next_yaw) * self.dt,
                yaw=next_yaw,
            )
            self.apply_pose(next_pose)
            self.simulation_step()
            current = self.get_pose()
            path_length += self._distance(previous, current)
            previous = current
            if step % self.record_stride == 0:
                trajectory.append({"step": step, **asdict(current)})
                controls.append({"step": step, **asdict(command)})
        return self._finish(
            reached=False,
            target_xy=target_xy,
            path_length=path_length,
            collision_count=max(0, self.obstacle_contact_count() - initial_contacts),
            elapsed_steps=self.maximum_steps,
            reason="timeout",
            trajectory=trajectory,
            controls=controls,
        )


class SkidSteerMotionController(_CallbackMotionBase):
    """Physics backend that sends angular velocity targets to four wheel DOFs."""

    def __init__(
        self,
        *,
        apply_wheel_velocities: Callable[[tuple[float, float, float, float]], None],
        stop_wheels: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.apply_wheel_velocities = apply_wheel_velocities
        self.stop_wheels = stop_wheels

    def move_to(self, target_xy: tuple[float, float]) -> MotionResult:
        trajectory: list[dict[str, float | int]] = []
        controls: list[dict[str, float | int]] = []
        path_length = 0.0
        initial_contacts = self.obstacle_contact_count()
        previous = self.get_pose()
        reason = "timeout"
        reached = False
        elapsed = self.maximum_steps
        for step in range(self.maximum_steps + 1):
            pose = self.get_pose()
            command = self._command_or_complete(pose, target_xy)
            if command is None:
                reached, reason, elapsed = True, "reached", step
                if not trajectory:
                    trajectory.append({"step": step, **asdict(pose)})
                    controls.append(
                        {
                            "step": step,
                            "linear_velocity": 0.0,
                            "angular_velocity": 0.0,
                            "left_wheel_velocity": 0.0,
                            "right_wheel_velocity": 0.0,
                        }
                    )
                break
            if self.obstacle_contact_count() > initial_contacts:
                reason, elapsed = "obstacle_contact", step
                break
            self.apply_wheel_velocities(
                (
                    command.left_wheel_velocity,
                    command.left_wheel_velocity,
                    command.right_wheel_velocity,
                    command.right_wheel_velocity,
                )
            )
            self.simulation_step()
            current = self.get_pose()
            path_length += self._distance(previous, current)
            previous = current
            if step % self.record_stride == 0:
                trajectory.append({"step": step, **asdict(current)})
                controls.append({"step": step, **asdict(command)})
        self.stop_wheels()
        return self._finish(
            reached=reached,
            target_xy=target_xy,
            path_length=path_length,
            collision_count=max(0, self.obstacle_contact_count() - initial_contacts),
            elapsed_steps=elapsed,
            reason=reason,
            trajectory=trajectory,
            controls=controls,
        )
