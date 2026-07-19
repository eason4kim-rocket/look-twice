"""V8 spatial model unit tests (CPU, no Genesis, no locked data)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v8_spatial_model import (
    GEOM_DIM,
    INPUT_SIZE,
    SpatialRGBDModel,
    geometry_vector,
    multitask_loss,
    rgb_depth_mask_to_tensor,
)


class V8SpatialModelTests(unittest.TestCase):
    def test_tensor_stack_shape(self) -> None:
        rgb = np.random.rand(120, 160, 3).astype(np.float32)
        depth = np.random.rand(120, 160).astype(np.float32) * 3.0
        mask = np.zeros((120, 160), dtype=np.float32)
        mask[40:80, 40:120] = 1.0
        x = rgb_depth_mask_to_tensor(rgb, depth, mask, size=64)
        self.assertEqual(tuple(x.shape), (5, 64, 64))

    def test_forward_and_loss_cpu(self) -> None:
        model = SpatialRGBDModel(pretrained_backbone=False, force_lightweight=True)
        model.train()
        b, h = 2, 128
        x = torch.rand(b, 5, h, h)
        geom = torch.randn(b, GEOM_DIM)
        out = model(x, geom)
        self.assertEqual(out["seg_logits"].shape[0], b)
        self.assertEqual(out["seg_logits"].shape[-2:], (h, h))
        self.assertEqual(out["p_blocked"].shape, (b,))
        self.assertEqual(out["backend"], "lightweight")
        seg_t = (torch.rand(b, 1, h, h) > 0.5).float()
        blocked = torch.tensor([0.0, 1.0])
        vis = torch.tensor([0.7, 0.4])
        loss, parts = multitask_loss(
            out, seg_target=seg_t, blocked_target=blocked, visibility_target=vis
        )
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertIn("total", parts)

    def test_geometry_vector_corridor_onehot(self) -> None:
        ga = geometry_vector(corridor_id="corridor_a")
        gb = geometry_vector(corridor_id="corridor_b")
        self.assertEqual(ga.shape[0], GEOM_DIM)
        self.assertGreater(float(ga[6]), float(gb[6]))
        self.assertGreater(float(gb[7]), float(ga[7]))

    def test_no_v7_seed_overlap_constant(self) -> None:
        # Import preflight forbidden ranges
        sys.path.insert(0, str(ROOT / "scripts"))
        from v8_collect_spatial_rgbd_preflight import FORBIDDEN_SEED_RANGES, _assert_seed_allowed

        for s in (95000, 96000, 98000, 99000, 99200, 99300):
            with self.assertRaises(ValueError):
                _assert_seed_allowed(s)
        _assert_seed_allowed(100000)


if __name__ == "__main__":
    unittest.main()
