import sys
import unittest
import importlib.util
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sensor_noise import SensorNoiseConfig, corrupt_rgbd_segmentation


@unittest.skipUnless(importlib.util.find_spec("torch"), "PyTorch is tested in AMD cloud")
class SensorNoiseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rgb = np.full((32, 48, 3), 128, dtype=np.uint8)
        self.depth = np.full((32, 48), 2.0, dtype=np.float32)
        self.segmentation = np.zeros((32, 48), dtype=np.int64)
        self.segmentation[8:24, 16:32] = 7
        self.segmentation[12:20, 20:28] = 9

    def run_noise(self, severity: float):
        return corrupt_rgbd_segmentation(
            rgb=self.rgb,
            depth=self.depth,
            segmentation=self.segmentation,
            obstacle_segmentation_idx=9,
            target_segmentation_idx=7,
            config=SensorNoiseConfig(severity=severity),
            seed=3,
            observation_index=1,
            viewpoint="left_near",
            viewpoint_xy=(-0.6, 1.2),
            target_xy=(0.8, 0.0),
            predicted_visibility=0.7,
            device="cpu",
        )

    def test_same_seed_is_reproducible(self) -> None:
        first = self.run_noise(0.5)
        second = self.run_noise(0.5)
        np.testing.assert_array_equal(first.rgb, second.rgb)
        np.testing.assert_array_equal(first.segmentation, second.segmentation)
        np.testing.assert_array_equal(np.isnan(first.depth), np.isnan(second.depth))
        self.assertEqual(first.derived_seed, second.derived_seed)

    def test_higher_severity_increases_declared_degradation(self) -> None:
        low = self.run_noise(0.1)
        high = self.run_noise(0.9)
        self.assertGreater(high.degradation, low.degradation)
        self.assertGreater(
            high.parameters["depth_dropout"], low.parameters["depth_dropout"]
        )
        self.assertGreater(
            high.parameters["segmentation_dropout"],
            low.parameters["segmentation_dropout"],
        )

    def test_audit_dict_excludes_large_arrays(self) -> None:
        audit = self.run_noise(0.5).audit_dict()
        self.assertNotIn("rgb", audit)
        self.assertNotIn("depth", audit)
        self.assertNotIn("segmentation", audit)
        self.assertEqual(audit["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
