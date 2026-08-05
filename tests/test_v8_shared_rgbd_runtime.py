"""Additive V8 shared-RGB-D A/B runtime tests (CPU, no frozen artifacts)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v7_vision_claims import (  # noqa: E402
    VisionProposal,
    propose_vision_spatial_rgbd,
    propose_vision_spatial_rgbd_ab_shared,
    vision_proposal_to_claim_v2,
)
from v8_spatial_runtime import (  # noqa: E402
    SpatialConformal,
    predict_spatial,
    predict_spatial_ab_shared,
)
from v8_seg_v3_model import SpatialRGBDSegV3  # noqa: E402


class _SharedForwardSpy:
    def __init__(self) -> None:
        self.shared_calls = 0
        self.assume_shared_rgbd: bool | None = None

    @staticmethod
    def _forward(x: torch.Tensor, geom: torch.Tensor) -> dict[str, torch.Tensor | str]:
        mask_mean = x[:, 4:5].mean(dim=(1, 2, 3))
        corridor_b = geom[:, 7]
        p_blocked = (0.1 + 0.6 * mask_mean + 0.2 * corridor_b).clamp(0.0, 1.0)
        return {
            "p_blocked": p_blocked,
            "visibility": 0.4 + 0.2 * mask_mean,
            "quality": 0.7 + 0.1 * corridor_b,
            "uncertainty": 0.3 - 0.1 * mask_mean,
            "backend": "unit-spy",
        }

    def __call__(
        self, x: torch.Tensor, geom: torch.Tensor
    ) -> dict[str, torch.Tensor | str]:
        return self._forward(x, geom)

    def forward_ab_shared(
        self,
        x_a: torch.Tensor,
        geom_a: torch.Tensor,
        x_b: torch.Tensor,
        geom_b: torch.Tensor,
        *,
        assume_shared_rgbd: bool = True,
    ) -> tuple[dict[str, torch.Tensor | str], dict[str, torch.Tensor | str]]:
        self.shared_calls += 1
        self.assume_shared_rgbd = assume_shared_rgbd
        return self._forward(x_a, geom_a), self._forward(x_b, geom_b)


def _conformal() -> SpatialConformal:
    return SpatialConformal(
        coverage_target=0.95,
        include_blocked_if_p_blocked_ge=0.7,
        include_clear_if_p_blocked_le=0.3,
        q_blocked=0.0,
        q_clear=0.0,
        artifact_sha256="conformal-sha",
        path="unit.json",
        raw={},
    )


def _bundle(model: object, *, is_seg_v3: bool = True) -> dict[str, object]:
    return {
        "model": model,
        "checkpoint_sha256": "checkpoint-sha",
        "conformal": _conformal(),
        "conformal_artifact_sha256": "conformal-sha",
        "model_id": "look-twice-v8-vision/spatial_rgbd_seg_v3/3",
        "preprocessing_version": "seg-v3-unit",
        "device": "cpu",
        "backend": "unit-spy",
        "fallback_used": False,
        "is_seg_v3": is_seg_v3,
    }


def _frame() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.zeros((24, 32, 3), dtype=np.float32)
    depth = np.ones((24, 32), dtype=np.float32)
    mask_a = np.zeros((24, 32), dtype=np.float32)
    mask_b = np.ones((24, 32), dtype=np.float32)
    return rgb, depth, mask_a, mask_b


class SharedSpatialRuntimeTests(unittest.TestCase):
    def test_lightweight_seg_v3_shared_is_numerically_identical(self) -> None:
        torch.manual_seed(7)
        model = SpatialRGBDSegV3(
            pretrained_backbone=False,
            force_lightweight=True,
        ).eval()
        bundle = _bundle(model)
        bundle["backend"] = model.backend
        rng = np.random.default_rng(7)
        rgb = rng.random((40, 56, 3), dtype=np.float32)
        depth = rng.random((40, 56), dtype=np.float32)
        mask_a = np.zeros((40, 56), dtype=np.float32)
        mask_a[:, :28] = 1.0
        mask_b = 1.0 - mask_a
        pose = {"x": -0.4, "y": 0.1, "yaw": -0.2}

        expected_a = predict_spatial(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask=mask_a,
            pose=pose,
            corridor_id="corridor_a",
        )
        expected_b = predict_spatial(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask=mask_b,
            pose=pose,
            corridor_id="corridor_b",
        )
        actual_a, actual_b = predict_spatial_ab_shared(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask_a=mask_a,
            corridor_mask_b=mask_b,
            pose_a=pose,
            pose_b=pose,
        )

        self.assertEqual(actual_a, expected_a)
        self.assertEqual(actual_b, expected_b)

    def test_shared_forward_matches_two_independent_predictions(self) -> None:
        model = _SharedForwardSpy()
        bundle = _bundle(model)
        rgb, depth, mask_a, mask_b = _frame()
        pose = {"x": -0.5, "y": 0.0, "yaw": 0.1}

        expected_a = predict_spatial(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask=mask_a,
            pose=pose,
            corridor_id="corridor_a",
        )
        expected_b = predict_spatial(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask=mask_b,
            pose=pose,
            corridor_id="corridor_b",
        )
        actual_a, actual_b = predict_spatial_ab_shared(
            bundle,
            rgb=rgb,
            depth=depth,
            corridor_mask_a=mask_a,
            corridor_mask_b=mask_b,
            pose_a=pose,
            pose_b=pose,
        )

        self.assertEqual(actual_a, expected_a)
        self.assertEqual(actual_b, expected_b)
        self.assertEqual(model.shared_calls, 1)
        self.assertTrue(model.assume_shared_rgbd)
        self.assertEqual(actual_a["prediction_set"], ["clear"])
        self.assertEqual(actual_b["prediction_set"], ["blocked"])
        self.assertEqual(actual_a["value"], "clear")
        self.assertEqual(actual_b["value"], "blocked")
        self.assertFalse(actual_a["fallback_used"])
        self.assertFalse(actual_b["reads_oracle"])

    def test_non_seg_v3_and_missing_shared_method_fail_closed(self) -> None:
        rgb, depth, mask_a, mask_b = _frame()
        with self.assertRaisesRegex(RuntimeError, "requires a seg-v3"):
            predict_spatial_ab_shared(
                _bundle(_SharedForwardSpy(), is_seg_v3=False),
                rgb=rgb,
                depth=depth,
                corridor_mask_a=mask_a,
                corridor_mask_b=mask_b,
            )
        with self.assertRaisesRegex(RuntimeError, "does not expose forward_ab_shared"):
            predict_spatial_ab_shared(
                _bundle(object()),
                rgb=rgb,
                depth=depth,
                corridor_mask_a=mask_a,
                corridor_mask_b=mask_b,
            )


class SharedVisionProposalTests(unittest.TestCase):
    def test_existing_single_corridor_helper_keeps_default_audit_shape(self) -> None:
        bundle = _bundle(_SharedForwardSpy())
        rgb, depth, mask_a, _ = _frame()
        pred = {
            "p_blocked": 0.1,
            "p_clear": 0.9,
            "visibility": 0.71,
            "quality": 0.81,
            "uncertainty": 0.11,
            "prediction_set": ["clear"],
            "value": "clear",
            "tensor_device": "cpu",
            "model_id": bundle["model_id"],
            "preprocessing_version": bundle["preprocessing_version"],
            "checkpoint_sha256": bundle["checkpoint_sha256"],
            "conformal_artifact_sha256": bundle["conformal_artifact_sha256"],
        }
        meta = {"corridor_id": "corridor_a", "capture": "single"}
        with patch(
            "v8_spatial_runtime.load_spatial_runtime", return_value=bundle
        ), patch("v8_spatial_runtime.predict_spatial", return_value=pred):
            proposal = propose_vision_spatial_rgbd(
                rgb,
                depth=depth,
                corridor_mask=mask_a,
                meta=meta,
                checkpoint="frozen.pt",
                conformal_artifact="frozen-conformal.json",
                device="cpu",
            )

        self.assertFalse(proposal.shared_rgbd_backbone)
        self.assertNotIn("shared_rgbd_backbone", proposal.features)
        self.assertNotIn("shared_rgbd_backbone", proposal.to_dict())
        self.assertEqual(proposal.value, "clear")
        self.assertEqual(proposal.prediction_set, ("clear",))
        self.assertEqual(proposal.checkpoint_sha256, "checkpoint-sha")

    def test_shared_helper_returns_two_audited_proposals(self) -> None:
        bundle = _bundle(_SharedForwardSpy())
        rgb, depth, mask_a, mask_b = _frame()
        pred_a = {
            "p_blocked": 0.1,
            "p_clear": 0.9,
            "visibility": 0.71,
            "quality": 0.81,
            "uncertainty": 0.11,
            "prediction_set": ["clear"],
            "value": "clear",
            "tensor_device": "cpu",
            "model_id": bundle["model_id"],
            "preprocessing_version": bundle["preprocessing_version"],
            "checkpoint_sha256": bundle["checkpoint_sha256"],
            "conformal_artifact_sha256": bundle["conformal_artifact_sha256"],
        }
        pred_b = {**pred_a, "p_blocked": 0.9, "p_clear": 0.1}
        pred_b.update(prediction_set=["blocked"], value="blocked")

        with (
            patch(
                "v8_spatial_runtime.load_spatial_runtime", return_value=bundle
            ) as load_runtime,
            patch(
                "v8_spatial_runtime.predict_spatial_ab_shared",
                return_value=(pred_a, pred_b),
            ) as shared_predict,
        ):
            proposal_a, proposal_b = propose_vision_spatial_rgbd_ab_shared(
                rgb,
                depth=depth,
                corridor_mask_a=mask_a,
                corridor_mask_b=mask_b,
                meta_a={"corridor_id": "corridor_a", "capture": "same"},
                meta_b={"corridor_id": "corridor_b", "capture": "same"},
                checkpoint="frozen.pt",
                conformal_artifact="frozen-conformal.json",
                device="cpu",
            )

        load_runtime.assert_called_once()
        shared_predict.assert_called_once()
        self.assertEqual((proposal_a.value, proposal_b.value), ("clear", "blocked"))
        self.assertEqual(proposal_a.prediction_set, ("clear",))
        self.assertEqual(proposal_b.prediction_set, ("blocked",))
        for proposal in (proposal_a, proposal_b):
            self.assertTrue(proposal.shared_rgbd_backbone)
            self.assertEqual(proposal.features["shared_rgbd_backbone"], 1.0)
            self.assertTrue(proposal.checkpoint_loaded)
            self.assertFalse(proposal.fallback_used)
            self.assertEqual(proposal.checkpoint_sha256, "checkpoint-sha")
            self.assertEqual(proposal.to_dict()["shared_rgbd_backbone"], True)

    def test_shared_helper_requires_explicit_masks_and_seg_v3(self) -> None:
        rgb, depth, mask_a, mask_b = _frame()
        with self.assertRaisesRegex(ValueError, "explicit A/B corridor masks"):
            propose_vision_spatial_rgbd_ab_shared(
                rgb,
                depth=depth,
                corridor_mask_a=None,
                corridor_mask_b=mask_b,
                checkpoint="frozen.pt",
                conformal_artifact="frozen-conformal.json",
                device="cpu",
            )

        with patch(
            "v8_spatial_runtime.load_spatial_runtime",
            return_value=_bundle(_SharedForwardSpy(), is_seg_v3=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "requires a seg-v3"):
                propose_vision_spatial_rgbd_ab_shared(
                    rgb,
                    depth=depth,
                    corridor_mask_a=mask_a,
                    corridor_mask_b=mask_b,
                    checkpoint="legacy.pt",
                    conformal_artifact="legacy-conformal.json",
                    device="cpu",
                )

    def test_default_claim_roots_unchanged_and_override_is_explicit(self) -> None:
        proposal = VisionProposal(
            value="clear",
            confidence=0.9,
            quality=0.8,
            visibility=0.7,
            model_id="unit-model",
            input_sha256="a" * 64,
            backend="torch_spatial_rgbd",
            features={},
        )
        default_claim = vision_proposal_to_claim_v2(
            proposal,
            agent_id="scout",
            corridor_id="corridor_a",
            step=7,
        )
        self.assertFalse(proposal.shared_rgbd_backbone)
        self.assertNotIn("shared_rgbd_backbone", proposal.to_dict())
        self.assertEqual(default_claim.capture_root_id, "vision-scout-aaaaaaaaaaaa")
        self.assertEqual(default_claim.device_root_id, "rgb-scout-aaaaaaaaaaaa")

        shared_claim = vision_proposal_to_claim_v2(
            proposal,
            agent_id="scout",
            corridor_id="corridor_b",
            step=7,
            capture_root_id="physical-capture-7",
            device_root_id="physical-capture-7",
        )
        self.assertEqual(shared_claim.capture_root_id, "physical-capture-7")
        self.assertEqual(shared_claim.device_root_id, "physical-capture-7")
        self.assertEqual(shared_claim.communication_root_id, "physical-capture-7")


if __name__ == "__main__":
    unittest.main()
