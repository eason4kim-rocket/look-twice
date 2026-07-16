"""Genesis 1.1.x / AMD runtime for Look Twice v4.

The visualization camera is rigidly derived from the chassis pose at every
capture.  This preserves RGB, depth, and entity segmentation together; Genesis
camera sensors that attach directly to links currently expose RGB only.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import numpy as np

from v4_evidence import RawEvidenceFrame
from v4_genesis_motion import GenesisSkidSteerAdapter, skid_steer_urdf_path
from v4_motion import KinematicMotionController, MotionResult, Pose2D
from v4_perception import ImageROI
from v4_scenario import ScenarioSample, TARGET_REGION


def project_risk_region_roi(
    *,
    camera_pos: tuple[float, float, float],
    camera_lookat: tuple[float, float, float],
    up: tuple[float, float, float],
    resolution: tuple[int, int],
    vertical_fov_degrees: float,
    region: tuple[float, float, float, float] = TARGET_REGION,
    maximum_height: float = 0.75,
    padding_pixels: int = 4,
) -> ImageROI:
    """Project the known 3-D risk prism into an image ROI using a pinhole model."""
    width, height = resolution
    if width < 2 or height < 2 or not 1.0 < vertical_fov_degrees < 179.0:
        raise ValueError("invalid camera projection parameters")
    position = np.asarray(camera_pos, dtype=np.float64)
    forward = np.asarray(camera_lookat, dtype=np.float64) - position
    forward_norm = np.linalg.norm(forward)
    if forward_norm <= 1e-9:
        raise ValueError("camera look-at vector is degenerate")
    forward /= forward_norm
    up_vector = np.asarray(up, dtype=np.float64)
    right = np.cross(forward, up_vector)
    right_norm = np.linalg.norm(right)
    if right_norm <= 1e-9:
        raise ValueError("camera up vector is parallel to viewing direction")
    right /= right_norm
    camera_up = np.cross(right, forward)
    focal = 0.5 * height / math.tan(math.radians(vertical_fov_degrees) / 2.0)
    points: list[tuple[float, float]] = []
    min_x, max_x, min_y, max_y = region
    for x in (min_x, max_x):
        for y in (min_y, max_y):
            for z in (0.01, maximum_height):
                relative = np.asarray((x, y, z), dtype=np.float64) - position
                depth = float(np.dot(relative, forward))
                if depth <= 1e-4:
                    continue
                u = width / 2.0 + focal * float(np.dot(relative, right)) / depth
                v = height / 2.0 - focal * float(np.dot(relative, camera_up)) / depth
                points.append((u, v))
    if len(points) < 4:
        raise ValueError("risk region is outside the mounted camera frustum")
    x0 = max(0, int(math.floor(min(point[0] for point in points))) - padding_pixels)
    y0 = max(0, int(math.floor(min(point[1] for point in points))) - padding_pixels)
    x1 = min(width, int(math.ceil(max(point[0] for point in points))) + padding_pixels)
    y1 = min(height, int(math.ceil(max(point[1] for point in points))) + padding_pixels)
    if x1 - x0 < 2 or y1 - y0 < 2:
        raise ValueError("projected risk ROI is empty after clipping")
    return ImageROI(x0, y0, x1, y1)


def _contact_rows(contacts: dict[str, Any]) -> int:
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


class GenesisEpisodeRuntime:
    """One Genesis scene with either physical skid-steer or fast kinematics."""

    SENSOR_RESOLUTION = (320, 240)
    SENSOR_FOV = 60.0

    def __init__(
        self,
        scenario: ScenarioSample,
        *,
        motion_backend: str = "skid-steer",
        video_output: Path | None = None,
        video_stride: int = 4,
        maximum_motion_steps: int = 2400,
    ) -> None:
        import genesis as gs
        import torch

        if motion_backend not in {"skid-steer", "kinematic"}:
            raise ValueError("motion_backend must be skid-steer or kinematic")
        if video_stride < 1:
            raise ValueError("video_stride must be positive")
        self.gs = gs
        self.torch = torch
        self.scenario = scenario
        self.motion_backend = motion_backend
        self.video_output = video_output
        self.video_stride = video_stride
        self._step = 0
        self._event_applied = False
        self._closed = False
        self._kinematic_contacts = 0
        self._last_contacting = False
        self._kinematic_pose = Pose2D(-2.0, 0.0, 0.0)

        scene = gs.Scene(
            show_viewer=False,
            sim_options=gs.options.SimOptions(dt=0.02),
            vis_options=gs.options.VisOptions(segmentation_level="entity"),
        )
        self.scene = scene
        self.plane = scene.add_entity(gs.morphs.Plane())
        fixed_robot = motion_backend == "kinematic"
        self.robot = scene.add_entity(
            gs.morphs.URDF(
                file=str(skid_steer_urdf_path()),
                pos=(-2.0, 0.0, 0.11),
                fixed=fixed_robot,
            )
        )
        self.occluder = scene.add_entity(
            gs.morphs.Box(
                size=scenario.occluder_size,
                pos=(scenario.occluder_xy[0], scenario.occluder_xy[1], 0.5),
                fixed=True,
            ),
            surface=gs.surfaces.Default(color=(0.42, 0.44, 0.47)),
        )
        self.target_patch = scene.add_entity(
            gs.morphs.Box(
                size=(0.8, 0.8, 0.02),
                pos=(0.8, 0.0, 0.012),
                fixed=True,
                collision=False,
            ),
            surface=gs.surfaces.Default(color=(0.15, 0.65, 0.25)),
        )
        self._active_obstacle_position = (
            scenario.obstacle_xy[0],
            scenario.obstacle_xy[1],
            scenario.obstacle_size[2] / 2.0,
        )
        self._inactive_obstacle_position = (
            -10.0,
            0.0,
            scenario.obstacle_size[2] / 2.0,
        )
        colour_rng = random.Random(scenario.seed + 4109)
        self.blocking_obstacle = scene.add_entity(
            gs.morphs.Box(
                size=scenario.obstacle_size,
                pos=(
                    self._active_obstacle_position
                    if scenario.initial_blocked
                    else self._inactive_obstacle_position
                ),
                fixed=True,
            ),
            surface=gs.surfaces.Default(
                color=tuple(colour_rng.uniform(0.08, 0.92) for _ in range(3))
            ),
        )
        self.sensor_camera = scene.add_camera(
            res=self.SENSOR_RESOLUTION,
            pos=(-1.8, 0.0, 0.48),
            lookat=(0.0, 0.0, 0.25),
            up=(0.0, 0.0, 1.0),
            fov=self.SENSOR_FOV,
            GUI=False,
        )
        self.video_camera = None
        if video_output is not None:
            self.video_camera = scene.add_camera(
                res=(640, 480),
                pos=(0.0, 0.0, 7.5),
                lookat=(0.0, 0.0, 0.0),
                up=(0.0, 1.0, 0.0),
                fov=45,
                GUI=False,
            )
        scene.build()
        segmentation_index_by_entity = {
            entity_key: segmentation_idx
            for segmentation_idx, entity_key in scene.visualizer.segmentation_idx_dict.items()
        }
        self.obstacle_segmentation_idx = segmentation_index_by_entity[
            self.blocking_obstacle.idx
        ]
        self.target_segmentation_idx = segmentation_index_by_entity[
            self.target_patch.idx
        ]
        if self.video_camera is not None:
            video_output.parent.mkdir(parents=True, exist_ok=True)
            self.video_camera.start_recording()

        def heading_provider(target: tuple[float, float]) -> float:
            # Side viewpoints: face the inspection region. Corridor goals past the
            # gate (including v5 grasp/goal) must face +x so the arm/EE is not
            # rotated 180° after "reached".
            tx, ty = float(target[0]), float(target[1])
            if abs(ty) > 0.55:
                return math.atan2(-ty, 0.8 - tx)
            if tx <= 0.45:
                return math.atan2(-ty, 0.8 - tx)
            return 0.0
        if motion_backend == "skid-steer":
            self._skid = GenesisSkidSteerAdapter(
                robot=self.robot,
                scene=self.scene,
                collision_entities=(self.blocking_obstacle, self.occluder),
                after_step=self._after_scene_step,
                maximum_steps=maximum_motion_steps,
                final_heading_provider=heading_provider,
            )
            self._motion = self._skid.controller
        else:
            self._skid = None
            self._motion = KinematicMotionController(
                get_pose=lambda: self._kinematic_pose,
                apply_pose=self._apply_kinematic_pose,
                simulation_step=self._kinematic_scene_step,
                obstacle_contact_count=lambda: self._kinematic_contacts,
                final_heading_provider=heading_provider,
                maximum_steps=maximum_motion_steps,
            )

    @property
    def current_step(self) -> int:
        return self._step

    @property
    def current_pose(self) -> Pose2D:
        if self._skid is not None:
            return self._skid.get_pose()
        return self._kinematic_pose

    @property
    def collision_count(self) -> int:
        if self._skid is not None:
            return self._skid.contact_total
        return self._kinematic_contacts

    @property
    def environment(self) -> dict[str, Any]:
        return {
            "runtime": "genesis-amd",
            "formal_result_eligible": True,
            "physics_backend": self.motion_backend,
            "genesis": self.gs.__version__,
            "genesis_backend": "gs.amdgpu",
            "torch": self.torch.__version__,
            "rocm": self.torch.version.hip,
            "gpu": (
                self.torch.cuda.get_device_name(0)
                if self.torch.cuda.is_available()
                else None
            ),
        }

    def _apply_dynamic_event(self) -> None:
        event = self.scenario.external_event
        if self._event_applied or not event.is_due(self._step):
            return
        position = (
            self._active_obstacle_position
            if event.to_blocked
            else self._inactive_obstacle_position
        )
        self.blocking_obstacle.set_pos(
            self.torch.tensor(position, device="cuda:0", dtype=self.torch.float32)
        )
        self._event_applied = True

    def _after_scene_step(self) -> None:
        self._step += 1
        self._apply_dynamic_event()
        if self.video_camera is not None and self._step % self.video_stride == 0:
            self.video_camera.render()

    def _apply_kinematic_pose(self, pose: Pose2D) -> None:
        self._kinematic_pose = pose
        self.robot.set_pos(
            self.torch.tensor(
                (pose.x, pose.y, 0.11), device="cuda:0", dtype=self.torch.float32
            )
        )
        self.robot.set_quat(
            self.torch.tensor(
                (
                    math.cos(pose.yaw / 2.0),
                    0.0,
                    0.0,
                    math.sin(pose.yaw / 2.0),
                ),
                device="cuda:0",
                dtype=self.torch.float32,
            )
        )

    def _kinematic_scene_step(self) -> None:
        self.scene.step()
        # Occluder is a FOV/visual slab for shared-occlusion stress, not a
        # navigable-world wall. Counting it as chassis contact made admitted
        # clear plans fail at pre_cross_gate. Only the true blocking obstacle
        # gates kinematic contact / unsafe.
        contacts = _contact_rows(
            self.robot.get_contacts(with_entity=self.blocking_obstacle)
        )
        contacting = contacts > 0
        if contacting and not self._last_contacting:
            self._kinematic_contacts += 1
        self._last_contacting = contacting
        self._after_scene_step()

    def move_to(self, target_xy: tuple[float, float]) -> MotionResult:
        return self._motion.move_to(target_xy)

    def wait_steps(self, count: int) -> None:
        if count < 0:
            raise ValueError("wait count cannot be negative")
        if self._skid is not None:
            self._skid.stop_wheels()
        for _ in range(count):
            if self._skid is not None:
                self._skid.simulation_step()
            else:
                self._kinematic_scene_step()

    def _mounted_camera_pose(
        self,
    ) -> tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]:
        pose = self.current_pose
        forward = (math.cos(pose.yaw), math.sin(pose.yaw))
        position = (
            pose.x + 0.15 * forward[0],
            pose.y + 0.15 * forward[1],
            0.48,
        )
        lookat = (
            position[0] + 2.0 * forward[0],
            position[1] + 2.0 * forward[1],
            0.25,
        )
        return position, lookat, (0.0, 0.0, 1.0)

    def capture_raw(
        self,
        *,
        viewpoint: str,
        viewpoint_xy: tuple[float, float],
        predicted_coverage: float,
    ) -> RawEvidenceFrame:
        camera_pos, lookat, up = self._mounted_camera_pose()
        self.sensor_camera.set_pose(pos=camera_pos, lookat=lookat, up=up)
        rgb, depth, segmentation, _ = self.sensor_camera.render(
            rgb=True,
            depth=True,
            segmentation=True,
            colorize_seg=False,
            force_render=True,
        )
        rgb_array = np.ascontiguousarray(np.asarray(rgb))
        depth_array = np.ascontiguousarray(np.asarray(depth))
        segmentation_array = np.ascontiguousarray(np.asarray(segmentation))
        if segmentation_array.ndim == 3 and segmentation_array.shape[-1] == 1:
            segmentation_array = segmentation_array[..., 0]
        roi = project_risk_region_roi(
            camera_pos=camera_pos,
            camera_lookat=lookat,
            up=up,
            resolution=self.SENSOR_RESOLUTION,
            vertical_fov_degrees=self.SENSOR_FOV,
        )
        expected_depth = math.dist(camera_pos, (0.8, 0.0, 0.30))
        return RawEvidenceFrame(
            rgb=rgb_array,
            depth=depth_array,
            segmentation=segmentation_array,
            risk_roi=roi,
            expected_clear_depth=expected_depth,
            obstacle_segmentation_idx=self.obstacle_segmentation_idx,
            target_segmentation_idx=self.target_segmentation_idx,
            target_reference_pixels=max(1, roi.pixels),
            viewpoint=viewpoint,
            viewpoint_xy=viewpoint_xy,
            predicted_coverage=predicted_coverage,
            capture_step=self.current_step,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._skid is not None:
            self._skid.stop_wheels()
        if self.video_camera is not None and self.video_output is not None:
            self.video_camera.stop_recording(
                save_to_filename=str(self.video_output), fps=30
            )


__all__ = ("GenesisEpisodeRuntime", "project_risk_region_roi")
