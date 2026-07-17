"""Tests for the learned RGB-D sensor preprocessing and model contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd import INPUT_CHANNELS, array_sha256, preprocess_rgbd
from v4_perception import ImageROI
from v4_evidence import SyntheticEvidenceSource, corrupt_evidence_frame
from v4_scenario import sample_v4_scenario


class LearnedRgbdTests(unittest.TestCase):
    def test_preprocess_is_finite_and_tracks_invalid_depth(self) -> None:
        rgb = np.zeros((24, 32, 3), dtype=np.uint8)
        rgb[..., 0] = 255
        depth = np.full((24, 32), 3.0, dtype=np.float32)
        depth[8:12, 10:15] = np.nan
        result = preprocess_rgbd(
            rgb=rgb,
            depth=depth,
            risk_roi=ImageROI(4, 4, 28, 20),
            expected_clear_depth=3.0,
            image_size=16,
        )
        self.assertEqual(result.shape, (INPUT_CHANNELS, 16, 16))
        self.assertTrue(np.isfinite(result).all())
        self.assertEqual(float(result[0].max()), 1.0)
        self.assertLess(float(result[4].min()), 1.0)

    def test_preprocess_hash_is_deterministic(self) -> None:
        rgb = np.arange(12 * 14 * 3, dtype=np.uint8).reshape(12, 14, 3)
        depth = np.ones((12, 14), dtype=np.float32)
        kwargs = dict(
            rgb=rgb,
            depth=depth,
            risk_roi=ImageROI(1, 2, 13, 11),
            expected_clear_depth=2.0,
            image_size=8,
        )
        self.assertEqual(array_sha256(preprocess_rgbd(**kwargs)), array_sha256(preprocess_rgbd(**kwargs)))

    def test_model_output_shape_when_torch_is_available(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is cloud-only for this test")
        from learned_rgbd import build_model

        model = build_model(torch)
        output = model(torch.zeros((3, INPUT_CHANNELS, 64, 64)))
        self.assertEqual(tuple(output.shape), (3, 1))

    def test_public_corruption_path_is_deterministic_on_cpu(self) -> None:
        scenario = sample_v4_scenario("independent-noise", 10000)
        frame = SyntheticEvidenceSource().raw_frame(
            scenario=scenario,
            viewpoint="left_near",
            viewpoint_xy=(-0.4, 1.1),
            predicted_coverage=0.82,
            capture_step=10,
        )
        first = corrupt_evidence_frame(frame, scenario, observation_index=0)
        second = corrupt_evidence_frame(frame, scenario, observation_index=0)
        self.assertEqual(array_sha256(first.rgb), array_sha256(second.rgb))
        self.assertEqual(array_sha256(first.depth), array_sha256(second.depth))
        self.assertEqual(first.audit.derived_seed, second.audit.derived_seed)

    def test_collection_profile_assignment_pairs_labels(self) -> None:
        scripts = ROOT / "scripts"
        sys.path.insert(0, str(scripts))
        from run_v5_learned_rgbd_collection import profile_for_seed

        self.assertEqual(profile_for_seed(10000, 10000), profile_for_seed(10001, 10000))
        self.assertNotEqual(profile_for_seed(10001, 10000), profile_for_seed(10002, 10000))


if __name__ == "__main__":
    unittest.main()
