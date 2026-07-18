"""Runtime Integration Gate unit tests.

Covers:
  - best.pt loads into GenesisCorridorHead
  - train/runtime preprocessing agree on p_blocked
  - conformal bounds clear / blocked / inconclusive
  - bad checkpoint does not silent-fallback
  - episode audit surfaces model + calibration SHA
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v7_vision_claims import propose_vision, propose_vision_torch  # noqa: E402
from v7_vision_model import (  # noqa: E402
    PREPROCESSING_VERSION,
    ConformalThresholds,
    GenesisCorridorHead,
    file_sha256,
    load_conformal_artifact,
    load_genesis_corridor_head,
    predict_p_blocked,
    preprocess_rgb_for_model,
)

CKPT = ROOT / "results" / "v7-vision-devices-v2" / "model" / "best.pt"
CONF = ROOT / "results" / "v7-vision-devices-v2" / "conformal" / "conformal_artifact.json"
EXPECTED_CKPT_SHA = "385aa7b78197909e548cd39907bb21c3059987a4465c1d366ab221968636bcc9"
EXPECTED_CONF_SHA = "44f564633b6e2a303dd796380d8c300f41f0abce60124ee7f36f48feec0e7333"


def _has_artifacts() -> bool:
    return CKPT.is_file() and CONF.is_file()


@unittest.skipUnless(_has_artifacts(), "vision artifacts not present locally")
class RuntimeIntegrationTests(unittest.TestCase):
    def test_best_pt_loads(self) -> None:
        model, sha, meta = load_genesis_corridor_head(CKPT, device="cpu")
        self.assertEqual(sha, EXPECTED_CKPT_SHA)
        self.assertEqual(sha, file_sha256(CKPT))
        self.assertIsNotNone(model)
        self.assertEqual(meta.get("model"), "GenesisCorridorHead")
        # Forward shape: batch of 2 → 2 logits
        x = torch.zeros(2, 3, 96, 96)
        with torch.no_grad():
            y = model(x)
        self.assertEqual(tuple(y.shape), (2,))

    def test_train_runtime_p_blocked_consistent(self) -> None:
        """Same 96×96 sample → same p_blocked via train-style tensor and runtime path."""
        model, _, _ = load_genesis_corridor_head(CKPT, device="cpu")
        rng = np.random.default_rng(0)
        # Simulate a full-frame RGB; runtime crops ROI then resizes.
        frame = rng.random((240, 320, 3), dtype=np.float32)
        # Runtime path
        p_runtime = predict_p_blocked(model, frame, device="cpu", already_96=False)
        # Train path: already-96 tensor (as dataset .npy would be)
        small = preprocess_rgb_for_model(frame, already_96=False)
        self.assertEqual(small.shape, (96, 96, 3))
        x = torch.from_numpy(small.transpose(2, 0, 1).copy()).float().unsqueeze(0)
        with torch.no_grad():
            p_train = float(torch.sigmoid(model(x)).item())
        self.assertAlmostEqual(p_runtime, p_train, places=6)

        # already_96 flag on same crop must match
        p_96 = predict_p_blocked(model, small, device="cpu", already_96=True)
        self.assertAlmostEqual(p_runtime, p_96, places=6)

    def test_conformal_bounds(self) -> None:
        conf = load_conformal_artifact(CONF)
        self.assertEqual(conf.artifact_sha256, EXPECTED_CONF_SHA)
        # Exact thresholds from calibrated artifact
        self.assertAlmostEqual(conf.include_clear_if_p_blocked_le, 0.2635742992162704, places=9)
        self.assertAlmostEqual(
            conf.include_blocked_if_p_blocked_ge, 0.8950414955615998, places=9
        )
        # Clear bound
        self.assertEqual(conf.value_from_p(0.0), "clear")
        self.assertEqual(conf.value_from_p(conf.include_clear_if_p_blocked_le), "clear")
        self.assertEqual(conf.prediction_set(0.10), ("clear",))
        # Blocked bound
        self.assertEqual(conf.value_from_p(1.0), "blocked")
        self.assertEqual(
            conf.value_from_p(conf.include_blocked_if_p_blocked_ge), "blocked"
        )
        self.assertEqual(conf.prediction_set(0.99), ("blocked",))
        # Middle → inconclusive
        mid = 0.5
        self.assertEqual(conf.value_from_p(mid), "inconclusive")
        self.assertEqual(conf.prediction_set(mid), ("clear", "blocked"))

    def test_bad_checkpoint_no_fallback(self) -> None:
        conf = load_conformal_artifact(CONF)
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.pt"
            # Wrong architecture state_dict
            tiny = torch.nn.Sequential(torch.nn.Linear(3, 3))
            torch.save({"state_dict": tiny.state_dict()}, bad)
            with self.assertRaises(RuntimeError):
                load_genesis_corridor_head(bad, device="cpu")
            rgb = np.random.default_rng(1).random((64, 64, 3), dtype=np.float32)
            with self.assertRaises(RuntimeError):
                propose_vision_torch(
                    rgb,
                    checkpoint=str(bad),
                    conformal_artifact=str(CONF),
                    device="cpu",
                    allow_fallback=False,
                )
            # Missing checkpoint fail-closed
            with self.assertRaises(FileNotFoundError):
                propose_vision(
                    rgb,
                    backend="torch_corridor_head",
                    checkpoint=None,
                    conformal_artifact=str(CONF),
                    allow_heuristic_fallback=False,
                )
            # Missing conformal fail-closed
            with self.assertRaises(FileNotFoundError):
                propose_vision(
                    rgb,
                    backend="torch_corridor_head",
                    checkpoint=str(CKPT),
                    conformal_artifact=None,
                    allow_heuristic_fallback=False,
                )

    def test_torch_proposal_audit_fields(self) -> None:
        rgb = np.random.default_rng(2).random((180, 240, 3), dtype=np.float32)
        prop = propose_vision(
            rgb,
            backend="torch_corridor_head",
            checkpoint=str(CKPT),
            conformal_artifact=str(CONF),
            device="cpu",
            meta={"vision_source": "unit_test"},
        )
        d = prop.to_dict()
        self.assertEqual(d["backend"], "torch_corridor_head")
        self.assertTrue(d["checkpoint_loaded"])
        self.assertFalse(d["fallback_used"])
        self.assertEqual(d["checkpoint_sha256"], EXPECTED_CKPT_SHA)
        self.assertEqual(d["conformal_artifact_sha256"], EXPECTED_CONF_SHA)
        self.assertEqual(d["preprocessing_version"], PREPROCESSING_VERSION)
        self.assertIsInstance(d["p_blocked"], float)
        self.assertIn(d["value"], ("clear", "blocked", "inconclusive"))
        self.assertTrue(d["prediction_set"])
        self.assertEqual(d["tensor_device"], "cpu")

    def test_corrupt_conformal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_conformal_artifact(bad)
            empty = Path(td) / "empty.json"
            empty.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_conformal_artifact(empty)

    def test_conformal_threshold_object_mid(self) -> None:
        thr = ConformalThresholds(
            include_blocked_if_p_blocked_ge=0.9,
            include_clear_if_p_blocked_le=0.2,
            coverage_target=0.95,
            source_path="x",
            artifact_sha256="y",
        )
        self.assertEqual(thr.value_from_p(0.5), "inconclusive")
        self.assertEqual(thr.value_from_p(0.15), "clear")
        self.assertEqual(thr.value_from_p(0.95), "blocked")


class SharedArchitectureTests(unittest.TestCase):
    def test_genesis_corridor_head_is_binary_96(self) -> None:
        self.assertIsNotNone(GenesisCorridorHead)
        m = GenesisCorridorHead()
        n_params = sum(p.numel() for p in m.parameters())
        # Sanity: Conv32/64/128 binary head is far larger than old Tiny Conv8/16 3-class
        self.assertGreater(n_params, 50_000)
        with torch.no_grad():
            out = m(torch.zeros(1, 3, 96, 96))
        self.assertEqual(out.numel(), 1)


if __name__ == "__main__":
    unittest.main()
