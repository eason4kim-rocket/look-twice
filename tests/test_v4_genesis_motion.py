import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_genesis_motion import quaternion_wxyz_to_yaw, skid_steer_urdf_path
from v4_genesis_runtime import project_risk_region_roi


class GenesisMotionAdapterTests(unittest.TestCase):
    def test_quaternion_to_yaw(self) -> None:
        half = math.pi / 4.0
        self.assertAlmostEqual(
            quaternion_wxyz_to_yaw((math.cos(half), 0, 0, math.sin(half))),
            math.pi / 2.0,
        )

    def test_robot_asset_exists(self) -> None:
        self.assertTrue(skid_steer_urdf_path().is_file())

    def test_known_risk_region_projects_to_nonempty_camera_roi(self) -> None:
        roi = project_risk_region_roi(
            camera_pos=(-0.45, 1.15, 0.48),
            camera_lookat=(0.8, 0.0, 0.25),
            up=(0.0, 0.0, 1.0),
            resolution=(320, 240),
            vertical_fov_degrees=60.0,
        )
        self.assertGreater(roi.pixels, 100)
        self.assertLess(roi.x_min, roi.x_max)
        self.assertLess(roi.y_min, roi.y_max)


if __name__ == "__main__":
    unittest.main()
