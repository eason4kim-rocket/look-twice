"""V8-seg-v3: ROI-gated obstacle decoder + masked-pooling traversability.

Runtime-legal inputs: RGB, noisy depth, corridor mask, geometry.
Train-only labels: clean obstacle ∩ corridor mask (never at runtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from v8_spatial_model import (
    GEOM_DIM,
    INPUT_SIZE,
    DepthEncoder,
    _LightweightRGBSeg,
    geometry_vector,
    rgb_depth_mask_to_tensor,
)

PREPROCESSING_VERSION = "v8-spatial-rgbd-seg-v3-roi-gated/v1"
MODEL_ID = "look-twice-v8-vision/spatial_rgbd_seg_v3/3"


class SpatialRGBDSegV3(nn.Module):
    """DeepLab-style RGB encoder + ROI-gated decoder + masked trav head."""

    def __init__(
        self,
        *,
        pretrained_backbone: bool = False,
        force_lightweight: bool = False,
    ) -> None:
        super().__init__()
        self.backend = "lightweight"
        self.rgb_seg = None
        self.rgb_light: nn.Module | None = None
        self.uses_masked_pooling_only = True
        self.uses_roi_gated_decoder = True

        if not force_lightweight:
            try:
                from torchvision.models.segmentation import deeplabv3_resnet50

                weights = "DEFAULT" if pretrained_backbone else None
                try:
                    self.rgb_seg = deeplabv3_resnet50(weights=weights, num_classes=21)
                except Exception:
                    self.rgb_seg = deeplabv3_resnet50(weights=None, num_classes=21)
                # Keep ASPP/classifier trunk; replace final 1x1 with 32-ch features.
                # deeplab classifier is Sequential(ASPP, Conv, BN, ReLU, Conv1x1)
                self.rgb_seg.classifier = nn.Sequential(
                    self.rgb_seg.classifier[0],
                    self.rgb_seg.classifier[1],
                    self.rgb_seg.classifier[2],
                    self.rgb_seg.classifier[3],
                    nn.Conv2d(256, 32, 1),
                )
                if (
                    hasattr(self.rgb_seg, "aux_classifier")
                    and self.rgb_seg.aux_classifier is not None
                ):
                    self.rgb_seg.aux_classifier = None
                self.backend = "deeplabv3_resnet50"
            except Exception:
                self.rgb_seg = None
        if self.rgb_seg is None:
            self.rgb_light = _LightweightRGBSeg()
            # lightweight returns 1-ch logits; wrap as 32 via 1x1
            self._light_proj = nn.Conv2d(1, 32, 1)
            self.backend = "lightweight"
        else:
            self._light_proj = None

        # Fuse RGB feat + depth + mask → ROI-gated obstacle logits
        self.depth_enc = DepthEncoder(in_ch=1)
        self.fuse_conv = nn.Sequential(
            nn.Conv2d(32 + 1 + 1, 64, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
        )
        # Traversability: masked pool of gated obstacle + depth feat + scalars + geom
        self._feat_proj = nn.Conv2d(1, 64, 1)
        self.geom_mlp = nn.Sequential(
            nn.Linear(GEOM_DIM, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 32),
            nn.ReLU(inplace=True),
        )
        trav_in = 64 + 128 + 4 + 32
        self.trav_fuse = nn.Sequential(
            nn.Linear(trav_in, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
        )
        self.head_blocked = nn.Linear(64, 1)
        self.head_visibility = nn.Linear(64, 1)
        self.head_quality = nn.Linear(64, 1)
        self.head_uncertainty = nn.Linear(64, 1)

    def _rgb_feat(self, rgb: torch.Tensor) -> torch.Tensor:
        if self.rgb_seg is not None:
            # After replace, classifier ends with 32-ch — still accessed via forward hack:
            # torchvision deeplab returns {"out": logits}. We need pre-final features.
            # Run backbone+ASPP manually when possible; fallback: use out as feat via 1x1.
            try:
                features = self.rgb_seg.backbone(rgb)
                x = features["out"]
                x = self.rgb_seg.classifier(x)
                return x  # (B,32,H',W')
            except Exception:
                out = self.rgb_seg(rgb)["out"]
                if out.shape[1] == 1:
                    return F.interpolate(
                        out.repeat(1, 32, 1, 1),
                        size=rgb.shape[-2:],
                        mode="bilinear",
                        align_corners=False,
                    )
                return out
        assert self.rgb_light is not None
        logits = self.rgb_light(rgb)
        return self._light_proj(logits)  # type: ignore[misc]

    @staticmethod
    def _masked_mean(feat: torch.Tensor, mask: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
        if mask.shape[-2:] != feat.shape[-2:]:
            mask = F.interpolate(mask, size=feat.shape[-2:], mode="nearest")
        w = mask.clamp(0, 1)
        num = (feat * w).sum(dim=(2, 3))
        den = w.sum(dim=(2, 3)).clamp_min(eps)
        return num / den

    def forward(
        self, x5: torch.Tensor, geom: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """
        x5: (B,5,H,W) = RGB(3)+depth(1)+mask(1)
        Returns seg_logits already ROI-gated (outside corridor suppressed).
        """
        rgb = x5[:, 0:3]
        depth = x5[:, 3:4]
        mask = x5[:, 4:5]
        h, w = rgb.shape[-2:]

        feat = self._rgb_feat(rgb)
        if feat.shape[-2:] != (h, w):
            feat = F.interpolate(feat, size=(h, w), mode="bilinear", align_corners=False)
        depth_s = depth
        mask_s = mask
        if depth_s.shape[-2:] != (h, w):
            depth_s = F.interpolate(depth_s, size=(h, w), mode="bilinear", align_corners=False)
        if mask_s.shape[-2:] != (h, w):
            mask_s = F.interpolate(mask_s, size=(h, w), mode="nearest")

        # Explicit mask channel into decoder; ROI gate after logits.
        fused = torch.cat([feat, depth_s, mask_s], dim=1)
        raw_logits = self.fuse_conv(fused)
        # Force suppress outside corridor (log-space: large negative)
        # logits' = logits * mask + (-20) * (1-mask)
        seg_logits = raw_logits * mask_s + (-20.0) * (1.0 - mask_s)
        seg_prob = torch.sigmoid(seg_logits)

        # Traversability from ROI only
        feat_m = self._masked_mean(self._feat_proj(seg_prob), mask_s)
        depth_feat = self.depth_enc(depth)
        depth_m = self._masked_mean(depth_feat, mask)
        denom = mask_s.sum(dim=(2, 3)).clamp_min(1e-6)
        region_obst = (seg_prob * mask_s).sum(dim=(2, 3)) / denom
        region_depth = (depth_s * mask_s).sum(dim=(2, 3)) / denom
        mask_frac = mask_s.mean(dim=(2, 3))
        valid = ((depth_s > 1e-3).float() * mask_s).sum(dim=(2, 3)) / denom
        scalars = torch.cat([region_obst, region_depth, mask_frac, valid], dim=1)
        g = self.geom_mlp(geom)
        fused_t = self.trav_fuse(torch.cat([feat_m, depth_m, scalars, g], dim=1))
        p_logit = self.head_blocked(fused_t).squeeze(-1)
        return {
            "seg_logits": seg_logits,
            "seg_logits_raw": raw_logits,
            "p_blocked_logit": p_logit,
            "p_blocked": torch.sigmoid(p_logit),
            "visibility": torch.sigmoid(self.head_visibility(fused_t)).squeeze(-1),
            "quality": torch.sigmoid(self.head_quality(fused_t)).squeeze(-1),
            "uncertainty": torch.sigmoid(self.head_uncertainty(fused_t)).squeeze(-1),
            "region_obst": region_obst.squeeze(-1),
            "mask_frac": mask_frac.squeeze(-1),
            "backend": self.backend,
        }

    def _decode_from_feat(
        self,
        *,
        feat: torch.Tensor,
        depth: torch.Tensor,
        depth_feat: torch.Tensor,
        mask: torch.Tensor,
        geom: torch.Tensor,
        h: int,
        w: int,
    ) -> dict[str, torch.Tensor]:
        """ROI-gated decoder + trav heads given shared RGB/depth features."""
        if feat.shape[-2:] != (h, w):
            feat = F.interpolate(feat, size=(h, w), mode="bilinear", align_corners=False)
        depth_s = depth
        mask_s = mask
        if depth_s.shape[-2:] != (h, w):
            depth_s = F.interpolate(depth_s, size=(h, w), mode="bilinear", align_corners=False)
        if mask_s.shape[-2:] != (h, w):
            mask_s = F.interpolate(mask_s, size=(h, w), mode="nearest")
        fused = torch.cat([feat, depth_s, mask_s], dim=1)
        raw_logits = self.fuse_conv(fused)
        seg_logits = raw_logits * mask_s + (-20.0) * (1.0 - mask_s)
        seg_prob = torch.sigmoid(seg_logits)
        feat_m = self._masked_mean(self._feat_proj(seg_prob), mask_s)
        depth_m = self._masked_mean(depth_feat, mask)
        denom = mask_s.sum(dim=(2, 3)).clamp_min(1e-6)
        region_obst = (seg_prob * mask_s).sum(dim=(2, 3)) / denom
        region_depth = (depth_s * mask_s).sum(dim=(2, 3)) / denom
        mask_frac = mask_s.mean(dim=(2, 3))
        valid = ((depth_s > 1e-3).float() * mask_s).sum(dim=(2, 3)) / denom
        scalars = torch.cat([region_obst, region_depth, mask_frac, valid], dim=1)
        g = self.geom_mlp(geom)
        fused_t = self.trav_fuse(torch.cat([feat_m, depth_m, scalars, g], dim=1))
        p_logit = self.head_blocked(fused_t).squeeze(-1)
        return {
            "seg_logits": seg_logits,
            "seg_logits_raw": raw_logits,
            "p_blocked_logit": p_logit,
            "p_blocked": torch.sigmoid(p_logit),
            "visibility": torch.sigmoid(self.head_visibility(fused_t)).squeeze(-1),
            "quality": torch.sigmoid(self.head_quality(fused_t)).squeeze(-1),
            "uncertainty": torch.sigmoid(self.head_uncertainty(fused_t)).squeeze(-1),
            "region_obst": region_obst.squeeze(-1),
            "mask_frac": mask_frac.squeeze(-1),
            "backend": self.backend,
        }

    def forward_ab_shared(
        self,
        x_a: torch.Tensor,
        geom_a: torch.Tensor,
        x_b: torch.Tensor,
        geom_b: torch.Tensor,
        *,
        assume_shared_rgbd: bool = True,
    ) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
        """One RGB DeepLab + one depth encoder for same-capture A/B pair.

        PerCapture dataset uses identical RGB-D for both sides; only mask/geom differ.
        When assume_shared_rgbd=False, concatenates A/B into one batched forward
        (still 2x RGB compute, but one kernel launch).
        """
        rgb_a, depth_a, mask_a = x_a[:, 0:3], x_a[:, 3:4], x_a[:, 4:5]
        mask_b = x_b[:, 4:5]
        if not assume_shared_rgbd:
            x = torch.cat([x_a, x_b], dim=0)
            g = torch.cat([geom_a, geom_b], dim=0)
            out = self.forward(x, g)
            n = x_a.shape[0]
            out_a = {k: (v[:n] if torch.is_tensor(v) else v) for k, v in out.items()}
            out_b = {k: (v[n:] if torch.is_tensor(v) else v) for k, v in out.items()}
            return out_a, out_b
        h, w = rgb_a.shape[-2:]
        feat = self._rgb_feat(rgb_a)
        depth_feat = self.depth_enc(depth_a)
        out_a = self._decode_from_feat(
            feat=feat, depth=depth_a, depth_feat=depth_feat, mask=mask_a, geom=geom_a, h=h, w=w
        )
        out_b = self._decode_from_feat(
            feat=feat, depth=depth_a, depth_feat=depth_feat, mask=mask_b, geom=geom_b, h=h, w=w
        )
        return out_a, out_b


def soft_dice_loss(logits: torch.Tensor, target: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits.squeeze(1)
    if target.ndim == 4 and target.shape[1] == 1:
        target = target.squeeze(1)
    p = torch.sigmoid(logits)
    t = target.float()
    inter = (p * t).sum(dim=(1, 2))
    den = p.sum(dim=(1, 2)) + t.sum(dim=(1, 2)) + eps
    return (1.0 - (2.0 * inter / den)).mean()


def tversky_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    *,
    alpha: float = 0.3,
    beta: float = 0.7,
    eps: float = 1e-6,
) -> torch.Tensor:
    """beta>alpha → penalize false negatives (missed obstacles) more."""
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits.squeeze(1)
    if target.ndim == 4 and target.shape[1] == 1:
        target = target.squeeze(1)
    p = torch.sigmoid(logits)
    t = target.float()
    tp = (p * t).sum(dim=(1, 2))
    fp = (p * (1 - t)).sum(dim=(1, 2))
    fn = ((1 - p) * t).sum(dim=(1, 2))
    tversky = (tp + eps) / (tp + alpha * fp + beta * fn + eps)
    return (1.0 - tversky).mean()


def roi_bce_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    *,
    pos_weight: float = 5.0,
) -> torch.Tensor:
    """BCE only inside corridor ROI, with positive class weight."""
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits.squeeze(1)
        target = target.squeeze(1) if target.ndim == 4 else target
        mask = mask.squeeze(1) if mask.ndim == 4 else mask
    m = mask.float().clamp(0, 1)
    t = target.float()
    # pixel-wise BCE
    pw = torch.tensor([pos_weight], device=logits.device, dtype=logits.dtype)
    # expand for pos weight: F.binary_cross_entropy_with_logits supports pos_weight on last dim for class
    # use manual:
    p = torch.sigmoid(logits)
    bce = -(pos_weight * t * torch.log(p.clamp_min(1e-6)) + (1 - t) * torch.log((1 - p).clamp_min(1e-6)))
    den = m.sum().clamp_min(1.0)
    return (bce * m).sum() / den


def consistency_loss(
    p_blocked: torch.Tensor,
    region_obst: torch.Tensor,
    y_blocked: torch.Tensor,
) -> torch.Tensor:
    """blocked → region_obst high; clear → region_obst low; align with p_blocked."""
    y = y_blocked.float()
    # encourage occupancy when blocked
    loss_b = F.relu(0.15 - region_obst) * y
    loss_c = F.relu(region_obst - 0.05) * (1 - y)
    # p_blocked should correlate with region_obst
    loss_align = F.smooth_l1_loss(p_blocked, region_obst.detach().clamp(0, 1))
    return loss_b.mean() + loss_c.mean() + 0.5 * loss_align


@dataclass
class SegV3LossWeights:
    roi_bce: float = 0.45
    dice: float = 0.30
    tversky: float = 0.10
    trav: float = 0.10
    ab: float = 0.05
    consistency: float = 0.05  # extra on top; user listed 5 terms, we fold consistency lightly


def multitask_seg_v3_loss(
    out: dict[str, torch.Tensor],
    *,
    seg_target: torch.Tensor,
    mask: torch.Tensor,
    blocked_target: torch.Tensor,
    weights: SegV3LossWeights | None = None,
    pos_weight: float = 5.0,
) -> tuple[torch.Tensor, dict[str, float]]:
    w = weights or SegV3LossWeights()
    l_bce = roi_bce_loss(out["seg_logits"], seg_target, mask, pos_weight=pos_weight)
    l_dice = soft_dice_loss(out["seg_logits"], seg_target)
    l_tver = tversky_loss(out["seg_logits"], seg_target, alpha=0.3, beta=0.7)
    l_trav = F.binary_cross_entropy_with_logits(
        out["p_blocked_logit"], blocked_target.float()
    )
    l_cons = consistency_loss(
        out["p_blocked"], out["region_obst"], blocked_target.float()
    )
    total = (
        w.roi_bce * l_bce
        + w.dice * l_dice
        + w.tversky * l_tver
        + w.trav * l_trav
        + w.consistency * l_cons
    )
    parts = {
        "roi_bce": float(l_bce.detach()),
        "dice": float(l_dice.detach()),
        "tversky": float(l_tver.detach()),
        "trav": float(l_trav.detach()),
        "consistency": float(l_cons.detach()),
        "total": float(total.detach()),
    }
    return total, parts


__all__ = (
    "PREPROCESSING_VERSION",
    "MODEL_ID",
    "SpatialRGBDSegV3",
    "soft_dice_loss",
    "tversky_loss",
    "roi_bce_loss",
    "consistency_loss",
    "SegV3LossWeights",
    "multitask_seg_v3_loss",
    "geometry_vector",
    "rgb_depth_mask_to_tensor",
    "INPUT_SIZE",
)
