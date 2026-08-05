"""V8 spatial RGB-D runtime: load frozen checkpoint + conformal, fail-closed predict.

Runtime-legal inputs only: RGB, noisy depth, corridor mask, geometry.
Never reads clean seg / oracle / offline labels.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from v8_spatial_model import (
    MODEL_ID,
    PREPROCESSING_VERSION,
    SpatialRGBDModel,
    geometry_vector,
    rgb_depth_mask_to_tensor,
)

_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class SpatialConformal:
    coverage_target: float
    include_blocked_if_p_blocked_ge: float
    include_clear_if_p_blocked_le: float
    q_blocked: float
    q_clear: float
    artifact_sha256: str
    path: str
    raw: dict[str, Any]

    def predict_set(self, p_blocked: float) -> tuple[str, ...]:
        include_b = p_blocked >= self.include_blocked_if_p_blocked_ge
        include_c = p_blocked <= self.include_clear_if_p_blocked_le
        s: list[str] = []
        if include_c:
            s.append("clear")
        if include_b:
            s.append("blocked")
        if not s:
            return ("clear", "blocked")
        return tuple(s)

    def value_from_set(self, pred_set: tuple[str, ...]) -> str:
        if pred_set == ("clear",):
            return "clear"
        if pred_set == ("blocked",):
            return "blocked"
        return "inconclusive"


def load_conformal_artifact(path: str | Path) -> SpatialConformal:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    thr = raw.get("thresholds") or raw
    sha = raw.get("artifact_sha256") or file_sha256(p)
    return SpatialConformal(
        coverage_target=float(thr.get("coverage_target", raw.get("coverage_target", 0.95))),
        include_blocked_if_p_blocked_ge=float(thr["include_blocked_if_p_blocked_ge"]),
        include_clear_if_p_blocked_le=float(thr["include_clear_if_p_blocked_le"]),
        q_blocked=float(thr.get("q_blocked", 0.0)),
        q_clear=float(thr.get("q_clear", 0.0)),
        artifact_sha256=str(sha),
        path=str(p),
        raw=raw,
    )


def load_spatial_checkpoint(
    checkpoint: str | Path,
    *,
    device: str = "cuda:0",
    force_lightweight: bool = False,
    legacy_global_pool: bool | None = None,
) -> tuple[Any, str, dict[str, Any]]:
    from v8_spatial_model import SpatialRGBDModelGlobalPool

    path = Path(checkpoint)
    sha = file_sha256(path)
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state") or ckpt.get("state_dict") or ckpt
    mid = str(ckpt.get("model_id") or "")
    # Seg-v3 ROI-gated decoder (independent of masked SpatialRGBDModel).
    is_seg_v3 = bool(
        ckpt.get("uses_roi_gated_decoder")
        or "seg_v3" in mid
        or "spatial_rgbd_seg_v3" in mid
        or ("fuse_conv.0.weight" in state and "trav_fuse.0.weight" in state)
        or ("fuse_conv.0.weight" in state and "head_blocked.weight" in state)
    )
    # Auto-detect legacy Day3 global-pool checkpoints (NO-GO RCA).
    if legacy_global_pool is None:
        legacy_global_pool = (not is_seg_v3) and (
            any(
                k.startswith("fuse.")
                or k == "global_pool.weight"
                or k.startswith("global_pool")
                for k in state
            )
            or ("fuse.0.weight" in state)
        )
    if is_seg_v3:
        from v8_seg_v3_model import SpatialRGBDSegV3

        model = SpatialRGBDSegV3(
            pretrained_backbone=False,
            force_lightweight=force_lightweight,
        )
    elif legacy_global_pool:
        model = SpatialRGBDModelGlobalPool(
            pretrained_backbone=False,
            force_lightweight=force_lightweight,
        )
    else:
        model = SpatialRGBDModel(
            pretrained_backbone=False,
            force_lightweight=force_lightweight,
        )
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    meta = {
        "epoch": ckpt.get("epoch"),
        "backend_ckpt": ckpt.get("backend"),
        "model_id_ckpt": ckpt.get("model_id"),
        "preprocessing_version_ckpt": ckpt.get("preprocessing_version"),
        "val": ckpt.get("val"),
        "runtime_backend": model.backend,
        "device": device,
        "legacy_global_pool": bool(legacy_global_pool),
        "is_seg_v3": bool(is_seg_v3),
        "uses_masked_pooling_only": bool(
            getattr(model, "uses_masked_pooling_only", False)
        ),
        "uses_roi_gated_decoder": bool(
            getattr(model, "uses_roi_gated_decoder", False)
        ),
    }
    return model, sha, meta


def load_spatial_runtime(
    *,
    checkpoint: str | Path,
    conformal_artifact: str | Path,
    device: str = "cuda:0",
) -> dict[str, Any]:
    key = (str(checkpoint), str(device), str(conformal_artifact))
    if key in _CACHE:
        return _CACHE[key]
    model, ckpt_sha, meta = load_spatial_checkpoint(checkpoint, device=device)
    if meta["runtime_backend"] != "deeplabv3_resnet50":
        raise RuntimeError(
            f"expected deeplabv3_resnet50 backend, got {meta['runtime_backend']}"
        )
    if not str(device).startswith("cuda"):
        raise RuntimeError(f"Day4 smoke requires cuda device, got {device}")
    if not torch.cuda.is_available():
        raise RuntimeError("cuda requested but torch.cuda.is_available() is False")
    conformal = load_conformal_artifact(conformal_artifact)
    # pin one param device check
    pdev = next(model.parameters()).device
    if pdev.type != "cuda":
        raise RuntimeError(f"model parameters not on cuda: {pdev}")
    # Prefer checkpoint-stamped IDs for seg-v3 / versioned freezes.
    mid = meta.get("model_id_ckpt") or MODEL_ID
    ppv = meta.get("preprocessing_version_ckpt") or PREPROCESSING_VERSION
    if meta.get("is_seg_v3"):
        try:
            from v8_seg_v3_model import (
                MODEL_ID as SEG_V3_MODEL_ID,
                PREPROCESSING_VERSION as SEG_V3_PP,
            )

            mid = meta.get("model_id_ckpt") or SEG_V3_MODEL_ID
            ppv = meta.get("preprocessing_version_ckpt") or SEG_V3_PP
        except Exception:
            pass
    bundle = {
        "model": model,
        "checkpoint_sha256": ckpt_sha,
        "conformal": conformal,
        "conformal_artifact_sha256": conformal.artifact_sha256,
        "checkpoint_meta": meta,
        "model_id": mid,
        "preprocessing_version": ppv,
        "device": device,
        "backend": model.backend,
        "fallback_used": False,
        "is_seg_v3": bool(meta.get("is_seg_v3")),
    }
    _CACHE[key] = bundle
    return bundle


def _prepare_geometry(
    *,
    device: str,
    geom: torch.Tensor | None,
    pose: Mapping[str, Any] | None,
    corridor_id: str,
) -> torch.Tensor:
    if geom is None:
        pose = pose or {}
        geom = geometry_vector(
            camera_xyz=(
                float(pose.get("x", 0.0)),
                float(pose.get("y", 0.0)),
                0.5,
            ),
            yaw=float(pose.get("yaw", 0.0)),
            range_to_entry=1.0,
            corridor_id=corridor_id,
        )
    return geom.unsqueeze(0).to(device) if geom.ndim == 1 else geom.to(device)


def _prediction_from_output(
    bundle: Mapping[str, Any],
    out: Mapping[str, Any],
) -> dict[str, Any]:
    device = str(bundle["device"])
    conf: SpatialConformal = bundle["conformal"]  # type: ignore[assignment]
    p_blocked = float(out["p_blocked"].reshape(-1)[0].item())
    pred_set = conf.predict_set(p_blocked)
    value = conf.value_from_set(pred_set)
    return {
        "p_blocked": p_blocked,
        "p_clear": 1.0 - p_blocked,
        "visibility": float(out["visibility"].reshape(-1)[0].item()),
        "quality": float(out["quality"].reshape(-1)[0].item()),
        "uncertainty": float(out["uncertainty"].reshape(-1)[0].item()),
        "prediction_set": list(pred_set),
        "value": value,
        "backend": bundle["backend"],
        "tensor_device": device,
        "model_id": bundle["model_id"],
        "preprocessing_version": bundle["preprocessing_version"],
        "checkpoint_sha256": bundle["checkpoint_sha256"],
        "conformal_artifact_sha256": bundle["conformal_artifact_sha256"],
        "fallback_used": False,
        "reads_clean_segmentation": False,
        "reads_oracle": False,
    }


@torch.no_grad()
def predict_spatial(
    bundle: Mapping[str, Any],
    *,
    rgb: Any,
    depth: Any,
    corridor_mask: Any,
    geom: torch.Tensor | None = None,
    pose: Mapping[str, Any] | None = None,
    corridor_id: str = "corridor_a",
) -> dict[str, Any]:
    device = str(bundle["device"])
    model: SpatialRGBDModel = bundle["model"]  # type: ignore[assignment]
    x5 = rgb_depth_mask_to_tensor(rgb, depth, corridor_mask).unsqueeze(0).to(device)
    g = _prepare_geometry(
        device=device,
        geom=geom,
        pose=pose,
        corridor_id=corridor_id,
    )
    out = model(x5, g)
    return _prediction_from_output(bundle, out)


@torch.no_grad()
def predict_spatial_ab_shared(
    bundle: Mapping[str, Any],
    *,
    rgb: Any,
    depth: Any,
    corridor_mask_a: Any,
    corridor_mask_b: Any,
    geom_a: torch.Tensor | None = None,
    geom_b: torch.Tensor | None = None,
    pose_a: Mapping[str, Any] | None = None,
    pose_b: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Predict corridor A/B from one RGB-D capture and one shared backbone pass.

    This additive helper is deliberately restricted to the frozen seg-v3
    architecture.  Older spatial checkpoints do not expose the audited
    ``forward_ab_shared`` path and therefore fail closed instead of silently
    falling back to two independent forwards.
    """
    if not bool(bundle.get("is_seg_v3")):
        raise RuntimeError(
            "shared A/B RGB-D prediction requires a seg-v3 runtime bundle"
        )

    model = bundle["model"]
    forward_ab_shared = getattr(model, "forward_ab_shared", None)
    if not callable(forward_ab_shared):
        raise RuntimeError(
            "seg-v3 runtime model does not expose forward_ab_shared (fail-closed)"
        )

    device = str(bundle["device"])
    x_a = rgb_depth_mask_to_tensor(rgb, depth, corridor_mask_a).unsqueeze(0).to(device)
    x_b = rgb_depth_mask_to_tensor(rgb, depth, corridor_mask_b).unsqueeze(0).to(device)
    g_a = _prepare_geometry(
        device=device,
        geom=geom_a,
        pose=pose_a,
        corridor_id="corridor_a",
    )
    g_b = _prepare_geometry(
        device=device,
        geom=geom_b,
        pose=pose_b,
        corridor_id="corridor_b",
    )
    out_a, out_b = forward_ab_shared(
        x_a,
        g_a,
        x_b,
        g_b,
        assume_shared_rgbd=True,
    )
    return (
        _prediction_from_output(bundle, out_a),
        _prediction_from_output(bundle, out_b),
    )


__all__ = (
    "SpatialConformal",
    "file_sha256",
    "load_conformal_artifact",
    "load_spatial_checkpoint",
    "load_spatial_runtime",
    "predict_spatial",
    "predict_spatial_ab_shared",
    "MODEL_ID",
    "PREPROCESSING_VERSION",
)
