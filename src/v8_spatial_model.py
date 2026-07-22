"""V8 spatially conditioned RGB-D multi-task model (DeepLabV3-R50 primary).

Inputs (runtime-legal):
  RGB, noisy depth, target corridor mask, geometry features.

Labels (train-only, never runtime):
  clean entity obstacle mask, offline corridor blocked flag, visibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

PREPROCESSING_VERSION = "v8-spatial-rgbd-deeplabv3r50-maskedpool-v2"
MODEL_ID = "look-twice-v8-vision/spatial_rgbd_deeplabv3_r50_masked/2"
INPUT_SIZE = 256
GEOM_DIM = 12  # xyz(3)+yaw_sin_cos(2)+range(1)+corridor_onehot(2)+pad


def rgb_depth_mask_to_tensor(
    rgb: Any,
    depth: Any,
    corridor_mask: Any,
    *,
    size: int = INPUT_SIZE,
) -> torch.Tensor:
    """Stack RGB(3)+depth(1)+mask(1) → (5,H,W) float32 in [0,1]-ish."""
    rgb_a = np.asarray(rgb, dtype=np.float32)
    if rgb_a.ndim == 2:
        rgb_a = np.stack([rgb_a, rgb_a, rgb_a], axis=-1)
    if rgb_a.shape[-1] > 3:
        rgb_a = rgb_a[..., :3]
    if rgb_a.max() > 1.5:
        rgb_a = rgb_a / 255.0
    d = np.asarray(depth, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    # Normalize depth robustly (invalid/zero → 0).
    finite = np.isfinite(d) & (d > 1e-4)
    d_norm = np.zeros_like(d, dtype=np.float32)
    if finite.any():
        med = float(np.median(d[finite]))
        d_norm[finite] = np.clip(d[finite] / max(med * 2.0, 1e-3), 0.0, 1.0)
    m = np.asarray(corridor_mask, dtype=np.float32)
    if m.ndim == 3:
        m = m[..., 0]
    m = (m > 0.5).astype(np.float32)

    def _resize(arr: np.ndarray) -> np.ndarray:
        h, w = arr.shape[:2]
        ys = np.linspace(0, h - 1, size).astype(int)
        xs = np.linspace(0, w - 1, size).astype(int)
        if arr.ndim == 2:
            return np.ascontiguousarray(arr[ys][:, xs])
        return np.ascontiguousarray(arr[ys][:, xs])

    rgb_r = _resize(rgb_a)
    d_r = _resize(d_norm)
    m_r = _resize(m)
    x = np.concatenate(
        [rgb_r.transpose(2, 0, 1), d_r[None, ...], m_r[None, ...]], axis=0
    )
    return torch.from_numpy(x.copy()).float()


def geometry_vector(
    *,
    camera_xyz: tuple[float, float, float] = (0.0, 0.0, 0.5),
    yaw: float = 0.0,
    range_to_entry: float = 1.0,
    corridor_id: str = "corridor_a",
) -> torch.Tensor:
    one_a = 1.0 if corridor_id.endswith("a") else 0.0
    one_b = 1.0 if corridor_id.endswith("b") else 0.0
    vec = [
        float(camera_xyz[0]),
        float(camera_xyz[1]),
        float(camera_xyz[2]),
        float(np.sin(yaw)),
        float(np.cos(yaw)),
        float(range_to_entry),
        one_a,
        one_b,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    return torch.tensor(vec[:GEOM_DIM], dtype=torch.float32)


class DepthEncoder(nn.Module):
    def __init__(self, in_ch: int = 1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, 32, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(16),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class _LightweightRGBSeg(nn.Module):
    """CI/CPU fallback when torchvision is unavailable."""

    def __init__(self) -> None:
        super().__init__()
        self.enc = nn.Sequential(
            nn.Conv2d(3, 32, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 3, padding=1),
            nn.ReLU(inplace=True),
        )
        self.head = nn.Conv2d(128, 1, 1)

    def forward(self, rgb: torch.Tensor) -> torch.Tensor:
        h, w = rgb.shape[-2:]
        feat = self.enc(rgb)
        logits = self.head(feat)
        return F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False)


class SpatialRGBDModelGlobalPool(nn.Module):
    """LEGACY Day3 global-pool model (NO-GO). Kept only to load frozen best.pt for RCA.

    Do not train new models with this class.
    """

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
        self.uses_masked_pooling_only = False
        if not force_lightweight:
            try:
                from torchvision.models.segmentation import deeplabv3_resnet50

                weights = "DEFAULT" if pretrained_backbone else None
                try:
                    self.rgb_seg = deeplabv3_resnet50(weights=weights, num_classes=21)
                except Exception:
                    self.rgb_seg = deeplabv3_resnet50(weights=None, num_classes=21)
                self.rgb_seg.classifier = nn.Sequential(
                    self.rgb_seg.classifier[0],
                    self.rgb_seg.classifier[1],
                    self.rgb_seg.classifier[2],
                    self.rgb_seg.classifier[3],
                    nn.Conv2d(256, 1, 1),
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
            self.backend = "lightweight"
        self.depth_enc = DepthEncoder(in_ch=2)
        self.geom_mlp = nn.Sequential(
            nn.Linear(GEOM_DIM, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 64),
            nn.ReLU(inplace=True),
        )
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.fuse = nn.Sequential(
            nn.Linear(256 + 128 + 64, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.1),
        )
        self.head_blocked = nn.Linear(256, 1)
        self.head_visibility = nn.Linear(256, 1)
        self.head_quality = nn.Linear(256, 1)
        self.head_uncertainty = nn.Linear(256, 1)
        self._feat_proj = nn.Conv2d(1, 256, 1)

    def _rgb_seg_logits(self, rgb: torch.Tensor) -> torch.Tensor:
        if self.rgb_seg is not None:
            return self.rgb_seg(rgb)["out"]
        assert self.rgb_light is not None
        return self.rgb_light(rgb)

    def forward(
        self, x5: torch.Tensor, geom: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        rgb = x5[:, 0:3]
        depth_mask = x5[:, 3:5]
        seg_out = self._rgb_seg_logits(rgb)
        depth_feat = self.depth_enc(depth_mask)
        depth_g = self.global_pool(depth_feat).flatten(1)
        seg_g = self.global_pool(self._feat_proj(torch.sigmoid(seg_out))).flatten(1)
        g = self.geom_mlp(geom)
        fused = self.fuse(torch.cat([seg_g, depth_g, g], dim=1))
        p_logit = self.head_blocked(fused).squeeze(-1)
        return {
            "seg_logits": seg_out,
            "p_blocked_logit": p_logit,
            "p_blocked": torch.sigmoid(p_logit),
            "visibility": torch.sigmoid(self.head_visibility(fused)).squeeze(-1),
            "quality": torch.sigmoid(self.head_quality(fused)).squeeze(-1),
            "uncertainty": torch.sigmoid(self.head_uncertainty(fused)).squeeze(-1),
            "backend": self.backend,
        }


class SpatialRGBDModel(nn.Module):
    """DeepLabV3-R50 RGB-D with explicit corridor masked pooling for traversability.

    p_blocked reads only target-region features (no whole-image global shortcut).
    Falls back to a small conv encoder if torchvision is not installed (unit tests).
    """

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
        if not force_lightweight:
            try:
                from torchvision.models.segmentation import deeplabv3_resnet50

                weights = "DEFAULT" if pretrained_backbone else None
                try:
                    self.rgb_seg = deeplabv3_resnet50(weights=weights, num_classes=21)
                except Exception:
                    self.rgb_seg = deeplabv3_resnet50(weights=None, num_classes=21)
                self.rgb_seg.classifier = nn.Sequential(
                    self.rgb_seg.classifier[0],
                    self.rgb_seg.classifier[1],
                    self.rgb_seg.classifier[2],
                    self.rgb_seg.classifier[3],
                    nn.Conv2d(256, 1, 1),
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
            self.backend = "lightweight"

        # Depth encoder sees depth only (mask applied via explicit masked pooling).
        self.depth_enc = DepthEncoder(in_ch=1)
        self.geom_mlp = nn.Sequential(
            nn.Linear(GEOM_DIM, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 32),
            nn.ReLU(inplace=True),
        )
        # Feature proj on obstacle probability map (still masked-pooled, never global).
        self._feat_proj = nn.Conv2d(1, 128, 1)
        # Traversability reads ONLY region-conditioned features:
        #   masked RGB-seg feat (128) + depth_feat masked (128) + region scalars (4) + geom (32)
        trav_in = 128 + 128 + 4 + 32
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
        # Explicitly no whole-image global path for p_blocked.
        self.uses_masked_pooling_only = True

    def _rgb_seg_logits(self, rgb: torch.Tensor) -> torch.Tensor:
        if self.rgb_seg is not None:
            return self.rgb_seg(rgb)["out"]
        assert self.rgb_light is not None
        return self.rgb_light(rgb)

    @staticmethod
    def _masked_mean(
        feat: torch.Tensor, mask: torch.Tensor, eps: float = 1e-6
    ) -> torch.Tensor:
        """feat (B,C,H,W), mask (B,1,H,W) → (B,C) mean over masked pixels."""
        if mask.shape[-2:] != feat.shape[-2:]:
            mask = F.interpolate(mask, size=feat.shape[-2:], mode="nearest")
        w = mask.clamp(0, 1)
        num = (feat * w).sum(dim=(2, 3))
        den = w.sum(dim=(2, 3)).clamp_min(eps)
        return num / den

    def forward(
        self,
        x5: torch.Tensor,
        geom: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """
        x5: (B,5,H,W) = RGB(3)+depth(1)+mask(1)
        geom: (B,GEOM_DIM)

        p_blocked is computed from target-corridor masked features only.
        """
        rgb = x5[:, 0:3]
        depth = x5[:, 3:4]
        mask = x5[:, 4:5]
        seg_out = self._rgb_seg_logits(rgb)
        if seg_out.shape[-2:] != mask.shape[-2:]:
            mask_s = F.interpolate(mask, size=seg_out.shape[-2:], mode="nearest")
            depth_s = F.interpolate(
                depth, size=seg_out.shape[-2:], mode="bilinear", align_corners=False
            )
        else:
            mask_s = mask
            depth_s = depth

        seg_prob = torch.sigmoid(seg_out)
        # Mask obstacle logits/probs to target corridor only (for pooling).
        seg_masked = seg_prob * mask_s
        feat = self._feat_proj(seg_masked)
        feat_m = self._masked_mean(feat, mask_s)

        depth_feat = self.depth_enc(depth)  # (B,128,16,16) typically
        # resize mask to depth_feat grid
        depth_m = self._masked_mean(depth_feat, mask)

        # Region scalars: obstacle mass, mean depth, mask coverage, depth-valid proxy
        denom = mask_s.sum(dim=(2, 3)).clamp_min(1e-6)
        region_obst = (seg_prob * mask_s).sum(dim=(2, 3)) / denom  # (B,1)
        region_depth = (depth_s * mask_s).sum(dim=(2, 3)) / denom
        mask_frac = mask_s.mean(dim=(2, 3))  # (B,1)
        # depth validity ≈ fraction of mask with depth > small threshold
        valid = ((depth_s > 1e-3).float() * mask_s).sum(dim=(2, 3)) / denom
        scalars = torch.cat(
            [region_obst, region_depth, mask_frac, valid], dim=1
        )  # (B,4)

        g = self.geom_mlp(geom)
        trav_in = torch.cat([feat_m, depth_m, scalars, g], dim=1)
        fused = self.trav_fuse(trav_in)
        p_logit = self.head_blocked(fused).squeeze(-1)
        vis = torch.sigmoid(self.head_visibility(fused)).squeeze(-1)
        quality = torch.sigmoid(self.head_quality(fused)).squeeze(-1)
        unc = torch.sigmoid(self.head_uncertainty(fused)).squeeze(-1)
        return {
            "seg_logits": seg_out,
            "p_blocked_logit": p_logit,
            "p_blocked": torch.sigmoid(p_logit),
            "visibility": vis,
            "quality": quality,
            "uncertainty": unc,
            "backend": self.backend,
            "region_obst": region_obst.squeeze(-1),
            "mask_frac": mask_frac.squeeze(-1),
            "uses_masked_pooling_only": torch.ones(
                p_logit.shape[0], device=p_logit.device
            ),
        }


def dice_bce_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """logits/target (B,1,H,W) or (B,H,W)."""
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits.squeeze(1)
    if target.ndim == 4 and target.shape[1] == 1:
        target = target.squeeze(1)
    target = target.float()
    bce = F.binary_cross_entropy_with_logits(logits, target)
    probs = torch.sigmoid(logits)
    inter = (probs * target).sum(dim=(1, 2))
    denom = probs.sum(dim=(1, 2)) + target.sum(dim=(1, 2)) + 1e-6
    dice = 1.0 - (2.0 * inter / denom).mean()
    return 0.5 * bce + 0.5 * dice


def focal_bce_loss(
    logit: torch.Tensor, target: torch.Tensor, *, gamma: float = 2.0
) -> torch.Tensor:
    target = target.float()
    p = torch.sigmoid(logit)
    ce = F.binary_cross_entropy_with_logits(logit, target, reduction="none")
    p_t = p * target + (1 - p) * (1 - target)
    loss = ((1 - p_t) ** gamma) * ce
    return loss.mean()


@dataclass
class MultiTaskLossWeights:
    seg: float = 0.40
    trav: float = 0.30
    vis: float = 0.15
    quality: float = 0.10
    cal: float = 0.05


def multitask_loss(
    out: dict[str, torch.Tensor],
    *,
    seg_target: torch.Tensor,
    blocked_target: torch.Tensor,
    visibility_target: torch.Tensor,
    quality_target: torch.Tensor | None = None,
    weights: MultiTaskLossWeights | None = None,
) -> tuple[torch.Tensor, dict[str, float]]:
    w = weights or MultiTaskLossWeights()
    l_seg = dice_bce_loss(out["seg_logits"], seg_target)
    l_trav = focal_bce_loss(out["p_blocked_logit"], blocked_target)
    l_vis = F.smooth_l1_loss(out["visibility"], visibility_target.float())
    if quality_target is None:
        quality_target = visibility_target
    l_q = F.smooth_l1_loss(out["quality"], quality_target.float())
    # Calibration regularizer: push uncertainty up when prediction is wrong (train-only).
    with torch.no_grad():
        wrong = (
            (out["p_blocked"] > 0.5).float() - blocked_target.float()
        ).abs()
    l_cal = F.smooth_l1_loss(out["uncertainty"], wrong.clamp(0, 1))
    total = (
        w.seg * l_seg
        + w.trav * l_trav
        + w.vis * l_vis
        + w.quality * l_q
        + w.cal * l_cal
    )
    parts = {
        "seg": float(l_seg.detach()),
        "trav": float(l_trav.detach()),
        "vis": float(l_vis.detach()),
        "quality": float(l_q.detach()),
        "cal": float(l_cal.detach()),
        "total": float(total.detach()),
    }
    return total, parts


__all__ = (
    "PREPROCESSING_VERSION",
    "MODEL_ID",
    "INPUT_SIZE",
    "GEOM_DIM",
    "SpatialRGBDModel",
    "SpatialRGBDModelGlobalPool",
    "rgb_depth_mask_to_tensor",
    "geometry_vector",
    "dice_bce_loss",
    "focal_bce_loss",
    "MultiTaskLossWeights",
    "multitask_loss",
)
