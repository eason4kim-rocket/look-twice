import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_motion import (
    DifferentialDriveControlLaw,
    KinematicMotionController,
    Pose2D,
    SkidSteerMotionController,
    wrap_angle,
)


class MotionControlTests(unittest.TestCase):
    def test_wrap_angle(self) -> None:
        self.assertAlmostEqual(wrap_angle(3 * math.pi), -math.pi)
        self.assertAlmostEqual(wrap_angle(-3 * math.pi), -math.pi)

    def test_control_turns_toward_target(self) -> None:
        command = DifferentialDriveControlLaw().command(Pose2D(0, 0, 0), (0, 1))
        self.assertGreater(command.angular_velocity, 0)
        self.assertLess(command.left_wheel_velocity, command.right_wheel_velocity)

    def test_kinematic_controller_reaches_waypoint_without_teleport(self) -> None:
        state = {"pose": Pose2D(-2.0, 0.0, 0.0), "steps": 0}

        controller = KinematicMotionController(
            get_pose=lambda: state["pose"],
            apply_pose=lambda pose: state.__setitem__("pose", pose),
            simulation_step=lambda: state.__setitem__("steps", state["steps"] + 1),
            obstacle_contact_count=lambda: 0,
            dt=0.02,
            maximum_steps=1000,
        )
        result = controller.move_to((-0.6, 1.2))
        self.assertTrue(result.reached)
        self.assertLess(math.dist((result.final_pose.x, result.final_pose.y), (-0.6, 1.2)), 0.08)
        self.assertGreater(result.elapsed_steps, 100)
        self.assertGreater(len(result.trajectory), 20)
        self.assertEqual(state["steps"], result.elapsed_steps)

    def test_contact_stops_motion(self) -> None:
        state = {"pose": Pose2D(0.0, 0.0, 0.0), "steps": 0}

        def advance() -> None:
            state["steps"] += 1

        controller = KinematicMotionController(
            get_pose=lambda: state["pose"],
            apply_pose=lambda pose: state.__setitem__("pose", pose),
            simulation_step=advance,
            obstacle_contact_count=lambda: int(state["steps"] >= 3),
            maximum_steps=100,
        )
        result = controller.move_to((2.0, 0.0))
        self.assertFalse(result.reached)
        self.assertEqual(result.reason, "obstacle_contact")
        self.assertEqual(result.collision_count, 1)

    def test_controller_settles_requested_final_heading(self) -> None:
        state = {"pose": Pose2D(0.0, 0.0, 0.0)}
        controller = KinematicMotionController(
            get_pose=lambda: state["pose"],
            apply_pose=lambda pose: state.__setitem__("pose", pose),
            simulation_step=lambda: None,
            obstacle_contact_count=lambda: 0,
            final_heading_provider=lambda target: math.pi / 2.0,
            dt=0.02,
            maximum_steps=1000,
        )
        result = controller.move_to((0.5, 0.0))
        self.assertTrue(result.reached)
        self.assertLess(
            abs(wrap_angle(result.final_pose.yaw - math.pi / 2.0)), 0.06
        )
        self.assertTrue(
            any(control["linear_velocity"] == 0.0 for control in result.controls)
        )

    def test_skid_steer_controller_emits_four_wheel_targets(self) -> None:
        state = {"pose": Pose2D(0.0, 0.0, 0.0), "command": (0.0,) * 4}

        def apply(values: tuple[float, float, float, float]) -> None:
            state["command"] = values

        def step() -> None:
            left = (state["command"][0] + state["command"][1]) / 2.0
            right = (state["command"][2] + state["command"][3]) / 2.0
            radius, track, dt = 0.07, 0.34, 0.02
            linear = radius * (left + right) / 2.0
            angular = radius * (right - left) / track
            pose = state["pose"]
            yaw = wrap_angle(pose.yaw + angular * dt)
            state["pose"] = Pose2D(
                pose.x + linear * math.cos(yaw) * dt,
                pose.y + linear * math.sin(yaw) * dt,
                yaw,
            )

        controller = SkidSteerMotionController(
            get_pose=lambda: state["pose"],
            apply_wheel_velocities=apply,
            stop_wheels=lambda: apply((0.0,) * 4),
            simulation_step=step,
            obstacle_contact_count=lambda: 0,
            maximum_steps=1000,
        )
        result = controller.move_to((1.0, 0.8))
        self.assertTrue(result.reached)
        self.assertEqual(state["command"], (0.0,) * 4)
        self.assertGreater(len(result.controls), 10)

    def test_already_at_target_records_non_empty_trace(self) -> None:
        pose = Pose2D(0.5, -0.25, 0.1)

        def apply_pose(next_pose: Pose2D) -> None:
            raise AssertionError(f"should not move when already at target: {next_pose}")

        controller = KinematicMotionController(
            get_pose=lambda: pose,
            apply_pose=apply_pose,
            simulation_step=lambda: None,
            obstacle_contact_count=lambda: 0,
            maximum_steps=50,
        )
        result = controller.move_to((0.5, -0.25))
        self.assertTrue(result.reached)
        self.assertEqual(result.reason, "reached")
        self.assertGreaterEqual(len(result.trajectory), 1)
        self.assertGreaterEqual(len(result.controls), 1)
        self.assertEqual(result.trajectory[0]["x"], pose.x)
        self.assertEqual(result.controls[0]["linear_velocity"], 0.0)


if __name__ == "__main__":
    unittest.main()
