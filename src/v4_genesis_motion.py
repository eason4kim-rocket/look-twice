"""Genesis adapter for the v4 skid-steer motion controller.

This module is imported only by the GPU integration entrypoint.  Keeping the
Genesis-specific calls here prevents the local standard-library tests from
requiring the simulator.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Iterable

from v4_motion import Pose2D, SkidSteerMotionController


WHEEL_JOINT_NAMES = (
    "left_front_wheel_joint",
    "left_rear_wheel_joint",
    "right_front_wheel_joint",
    "right_rear_wheel_joint",
)


def quaternion_wxyz_to_yaw(quaternion: Iterable[float]) -> float:
    """Convert a Genesis `(w, x, y, z)` quaternion to planar yaw."""
    w, x, y, z = (float(value) for value in quaternion)
    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(sin_yaw, cos_yaw)


def skid_steer_urdf_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "robots" / "look_twice_skid_steer.urdf"


def wheel_dof_indices(robot) -> list[int]:
    indices: list[int] = []
    for name in WHEEL_JOINT_NAMES:
        local = robot.get_joint(name).dofs_idx_local
        if isinstance(local, int):
            indices.append(local)
        else:
            values = list(local)
            if len(values) != 1:
                raise RuntimeError(f"wheel joint {name} has {len(values)} DOFs, expected 1")
            indices.append(int(values[0]))
    if len(set(indices)) != 4:
        raise RuntimeError(f"wheel DOFs are not distinct: {indices}")
    return indices


def _contact_rows(contacts: dict) -> int:
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


class GenesisSkidSteerAdapter:
    """Bind a built Genesis articulated robot to `SkidSteerMotionController`."""

    def __init__(
        self,
        *,
        robot,
        scene,
        collision_entities: Iterable,
        after_step: Callable[[], None] | None = None,
        maximum_steps: int = 2000,
        final_heading_provider: Callable[[tuple[float, float]], float | None]
        | None = None,
    ) -> None:
        import numpy as np

        self.robot = robot
        self.scene = scene
        self.collision_entities = tuple(collision_entities)
        self.after_step = after_step
        self.indices = wheel_dof_indices(robot)
        self._contact_total = 0

        # Velocity control uses Kv as viscous tracking gain.  Wheel position
        # stiffness must remain zero so continuous joints do not fight rotation.
        robot.set_dofs_kp(np.zeros(4), dofs_idx_local=self.indices)
        robot.set_dofs_kv(np.full(4, 8.0), dofs_idx_local=self.indices)
        robot.set_dofs_force_range(
            np.full(4, -20.0), np.full(4, 20.0), dofs_idx_local=self.indices
        )
        self.controller = SkidSteerMotionController(
            get_pose=self.get_pose,
            apply_wheel_velocities=self.apply_wheel_velocities,
            stop_wheels=self.stop_wheels,
            simulation_step=self.simulation_step,
            obstacle_contact_count=lambda: self._contact_total,
            maximum_steps=maximum_steps,
            final_heading_provider=final_heading_provider,
        )

    def get_pose(self) -> Pose2D:
        position = self.robot.get_pos()
        quaternion = self.robot.get_quat()
        return Pose2D(
            float(position[0].item()),
            float(position[1].item()),
            quaternion_wxyz_to_yaw(quaternion.tolist()),
        )

    @property
    def contact_total(self) -> int:
        return self._contact_total

    def apply_wheel_velocities(self, velocities: tuple[float, float, float, float]) -> None:
        import numpy as np

        self.robot.control_dofs_velocity(
            np.asarray(velocities, dtype=np.float32), dofs_idx_local=self.indices
        )

    def stop_wheels(self) -> None:
        self.apply_wheel_velocities((0.0, 0.0, 0.0, 0.0))

    def simulation_step(self) -> None:
        self.scene.step()
        new_contacts = 0
        for entity in self.collision_entities:
            new_contacts += _contact_rows(self.robot.get_contacts(with_entity=entity))
        if new_contacts:
            self._contact_total += new_contacts
        if self.after_step is not None:
            self.after_step()

    def move_to(self, target_xy: tuple[float, float]):
        return self.controller.move_to(target_xy)
