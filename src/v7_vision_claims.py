"""v7 vision proposer: RGB → structured corridor claim fields.

Backends:
  - heuristic_rgb_proxy: deterministic, CI-safe, honestly a proxy
  - torch_corridor_head: GenesisCorridorHead + conformal (fail-closed)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import SENSOR_VERSION_V6, build_robot_claim_v2

VISION_MODALITY = "vision_semantic_v7"
SENSOR_BUNDLE_V7 = "look-twice-rgbd-multi-agent-v7/1"
SENSOR_BUNDLE_COMPAT = SENSOR_VERSION_V6
MODEL_PREFIX = "look-twice-v7-vision"


@dataclass(frozen=True, slots=True)
class VisionProposal:
    value: str  # clear | blocked | inconclusive
    confidence: float
    quality: float
    visibility: float
    model_id: str
    input_sha256: str
    backend: str
    features: dict[str, float]
    # Runtime integration audit (torch path fills these; heuristic leaves defaults)
    tensor_device: str = "cpu"
    checkpoint_sha256: str | None = None
    conformal_artifact_sha256: str | None = None
    preprocessing_version: str | None = None
    fallback_used: bool = False
    p_blocked: float | None = None
    prediction_set: tuple[str, ...] = ()
    checkpoint_loaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "quality": self.quality,
            "visibility": self.visibility,
            "model_id": self.model_id,
            "input_sha256": self.input_sha256,
            "backend": self.backend,
            "features": dict(self.features),
            "tensor_device": self.tensor_device,
            "checkpoint_sha256": self.checkpoint_sha256,
            "conformal_artifact_sha256": self.conformal_artifact_sha256,
            "preprocessing_version": self.preprocessing_version,
            "fallback_used": bool(self.fallback_used),
            "p_blocked": self.p_blocked,
            "prediction_set": list(self.prediction_set),
            "checkpoint_loaded": bool(self.checkpoint_loaded),
        }


def _rgb_to_array(rgb: Any) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.dtype != np.float32 and arr.dtype != np.float64:
        arr = arr.astype(np.float32)
        if arr.max() > 1.5:
            arr = arr / 255.0
    else:
        arr = arr.astype(np.float32)
        if arr.max() > 1.5:
            arr = arr / 255.0
    return np.ascontiguousarray(arr)


def _input_sha(rgb: np.ndarray, meta: Mapping[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(rgb.tobytes())
    h.update(canonical_sha256(dict(meta)).encode("utf-8"))
    return h.hexdigest()


def propose_vision_heuristic(
    rgb: Any,
    *,
    depth: Any | None = None,
    meta: Mapping[str, Any] | None = None,
) -> VisionProposal:
    """Deterministic ROI proxy (not the formal Genesis vision model)."""
    meta = dict(meta or {})
    arr = _rgb_to_array(rgb)
    h, w = arr.shape[:2]
    y0, y1 = int(0.35 * h), int(0.70 * h)
    x0, x1 = int(0.30 * w), int(0.70 * w)
    roi = arr[y0:y1, x0:x1]
    if roi.size == 0:
        roi = arr
    gray = roi.mean(axis=-1)
    mean_luma = float(gray.mean())
    std_luma = float(gray.std())
    dark_frac = float((gray < 0.25).mean())

    depth_block = 0.0
    depth_free = 0.0
    depth_available = 0.0
    if depth is not None:
        d = np.asarray(depth, dtype=np.float32)
        if d.shape[:2] == arr.shape[:2]:
            droi = d[y0:y1, x0:x1]
        else:
            droi = d
        finite = droi[np.isfinite(droi) & (droi > 1e-4)]
        if finite.size:
            depth_available = 1.0
            med = float(np.median(finite))
            depth_block = float((finite < med * 0.55).mean())
            depth_free = float((finite > med * 0.75).mean())

    block_score = 0.55 * depth_block + 0.25 * max(0.0, dark_frac - 0.85) + 0.10 * max(
        0.0, 0.12 - mean_luma
    )
    clear_score = 0.55 * depth_free + 0.25 * (1.0 - depth_block) + 0.20 * min(
        1.0, std_luma * 4.0
    )
    if depth_available < 0.5:
        block_score = 0.45 * dark_frac + 0.20 * max(0.0, 0.15 - mean_luma)
        clear_score = 0.50 * (1.0 - dark_frac) + 0.30 * min(1.0, mean_luma / 0.35)

    if block_score >= 0.50 and block_score > clear_score + 0.05:
        value = "blocked"
        confidence = min(0.95, 0.55 + block_score)
    elif clear_score >= 0.48 and clear_score >= block_score:
        value = "clear"
        confidence = min(0.95, 0.50 + clear_score * 0.45)
    else:
        value = "inconclusive"
        confidence = 0.45 + 0.2 * (1.0 - abs(block_score - clear_score))

    quality = float(
        np.clip(
            0.45
            + 0.4 * (0.5 * depth_available + 0.5 * (1.0 - abs(0.5 - std_luma))),
            0.25,
            0.95,
        )
    )
    visibility = float(
        np.clip(0.40 + 0.5 * max(mean_luma, 0.5 * depth_free), 0.25, 0.95)
    )
    sha = _input_sha(arr, meta)
    return VisionProposal(
        value=value,
        confidence=float(np.clip(confidence, 0.05, 0.99)),
        quality=quality,
        visibility=visibility,
        model_id=f"{MODEL_PREFIX}/heuristic_rgb_proxy/1",
        input_sha256=sha,
        backend="heuristic_rgb_proxy",
        features={
            "mean_luma": mean_luma,
            "std_luma": std_luma,
            "dark_frac": dark_frac,
            "depth_block": depth_block,
            "depth_free": depth_free,
            "block_score": block_score,
            "clear_score": clear_score,
            "fallback_used": 0.0,
        },
        tensor_device="cpu",
        fallback_used=False,
        checkpoint_loaded=False,
        prediction_set=(value,) if value in ("clear", "blocked") else ("clear", "blocked"),
    )


# Module-level cache: (ckpt, device, conformal_path) → loaded objects
_TORCH_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


def _load_torch_runtime(
    *,
    checkpoint: str,
    conformal_artifact: str,
    device: str,
) -> dict[str, Any]:
    key = (str(checkpoint), str(device), str(conformal_artifact))
    if key in _TORCH_CACHE:
        return _TORCH_CACHE[key]
    from v7_vision_model import (
        MODEL_ID,
        PREPROCESSING_VERSION,
        load_conformal_artifact,
        load_genesis_corridor_head,
    )

    model, ckpt_sha, meta = load_genesis_corridor_head(checkpoint, device=device)
    conformal = load_conformal_artifact(conformal_artifact)
    bundle = {
        "model": model,
        "checkpoint_sha256": ckpt_sha,
        "conformal": conformal,
        "conformal_artifact_sha256": conformal.artifact_sha256,
        "checkpoint_meta": meta,
        "model_id": MODEL_ID,
        "preprocessing_version": PREPROCESSING_VERSION,
        "device": device,
    }
    _TORCH_CACHE[key] = bundle
    return bundle


def propose_vision_torch(
    rgb: Any,
    *,
    depth: Any | None = None,
    meta: Mapping[str, Any] | None = None,
    checkpoint: str | None = None,
    conformal_artifact: str | None = None,
    device: str = "cpu",
    allow_fallback: bool = False,
) -> VisionProposal:
    """GenesisCorridorHead + conformal. Fail-closed unless allow_fallback=True.

    Formal / torch mode must set allow_fallback=False (default for torch backend
    entry via propose_vision).
    """
    meta = dict(meta or {})
    if not checkpoint:
        if allow_fallback:
            return propose_vision_heuristic(rgb, depth=depth, meta=meta)
        raise FileNotFoundError(
            "torch_corridor_head requires --vision-checkpoint (fail-closed)"
        )
    if not conformal_artifact:
        if allow_fallback:
            return propose_vision_heuristic(rgb, depth=depth, meta=meta)
        raise FileNotFoundError(
            "torch_corridor_head requires --vision-conformal-artifact (fail-closed)"
        )

    try:
        bundle = _load_torch_runtime(
            checkpoint=checkpoint,
            conformal_artifact=conformal_artifact,
            device=device,
        )
    except Exception:
        if allow_fallback:
            return propose_vision_heuristic(rgb, depth=depth, meta=meta)
        raise

    from v7_vision_model import predict_label, preprocess_rgb_for_model

    already_96 = bool(meta.get("already_96"))
    pred = predict_label(
        bundle["model"],
        rgb,
        bundle["conformal"],
        device=device,
        already_96=already_96,
    )
    small = preprocess_rgb_for_model(rgb, already_96=already_96)
    sha = _input_sha(small, meta)
    value = pred["value"]
    p_blocked = float(pred["p_blocked"])
    pred_set = tuple(pred["prediction_set"])
    conf = p_blocked if value == "blocked" else (1.0 - p_blocked if value == "clear" else 0.5)
    conf = float(np.clip(max(conf, 0.05), 0.05, 0.99))
    return VisionProposal(
        value=value,
        confidence=conf,
        quality=0.85 if value != "inconclusive" else 0.55,
        visibility=0.80 if value != "inconclusive" else 0.50,
        model_id=str(bundle["model_id"]),
        input_sha256=sha,
        backend="torch_corridor_head",
        features={
            "p_blocked": p_blocked,
            "p_clear": float(pred["p_clear"]),
            "prediction_set_clear": 1.0 if "clear" in pred_set else 0.0,
            "prediction_set_blocked": 1.0 if "blocked" in pred_set else 0.0,
            "fallback_used": 0.0,
            "checkpoint_loaded": 1.0,
            "include_blocked_if_p_blocked_ge": bundle[
                "conformal"
            ].include_blocked_if_p_blocked_ge,
            "include_clear_if_p_blocked_le": bundle[
                "conformal"
            ].include_clear_if_p_blocked_le,
        },
        tensor_device=str(device),
        checkpoint_sha256=str(bundle["checkpoint_sha256"]),
        conformal_artifact_sha256=str(bundle["conformal_artifact_sha256"]),
        preprocessing_version=str(bundle["preprocessing_version"]),
        fallback_used=False,
        p_blocked=p_blocked,
        prediction_set=pred_set,
        checkpoint_loaded=True,
    )


def propose_vision(
    rgb: Any,
    *,
    depth: Any | None = None,
    meta: Mapping[str, Any] | None = None,
    backend: str = "heuristic_rgb_proxy",
    checkpoint: str | None = None,
    conformal_artifact: str | None = None,
    device: str = "cpu",
    allow_heuristic_fallback: bool = False,
) -> VisionProposal:
    """Dispatch vision backend.

    torch_corridor_head is fail-closed by default (no silent heuristic fallback).
    """
    if backend == "torch_corridor_head":
        return propose_vision_torch(
            rgb,
            depth=depth,
            meta=meta,
            checkpoint=checkpoint,
            conformal_artifact=conformal_artifact,
            device=device,
            allow_fallback=bool(allow_heuristic_fallback),
        )
    if backend != "heuristic_rgb_proxy":
        raise ValueError(f"unknown vision backend: {backend}")
    return propose_vision_heuristic(rgb, depth=depth, meta=meta)


def vision_proposal_to_claim_v2(
    proposal: VisionProposal,
    *,
    agent_id: str,
    corridor_id: str,
    step: int,
    ttl: int = 2000,
    capture_root_id: str | None = None,
    calibration_id: str = SENSOR_BUNDLE_COMPAT,
    intended_actor_id: str = "carrier",
) -> Any:
    """Build RobotClaimV2 from a vision proposal."""
    root = capture_root_id or f"vision-{agent_id}-{proposal.input_sha256[:12]}"
    return build_robot_claim_v2(
        fact_id=f"region:{corridor_id}",
        predicate="carrier_traversable",
        value=proposal.value,
        confidence=proposal.confidence,
        observed_step=step,
        valid_until_step=step + ttl,
        modality=VISION_MODALITY,
        device_root_id=f"rgb-{agent_id}-01",
        capture_root_id=root,
        calibration_id=calibration_id,
        pose_version="base-link-v7",
        model_id=proposal.model_id,
        artifact_sha256=proposal.input_sha256,
        observer_agent_id=agent_id,
        intended_actor_id=intended_actor_id,
        received_step=step,
        communication_root_id=root,
        quality=proposal.quality,
        visibility=proposal.visibility,
        scope=ClaimScope(intended_actor_id, "payload_loaded", corridor_id),
    )


def viewpoint_vision_cue(
    *,
    viewpoint_name: str,
    capture_index: int,
    seed: int,
    profile: str = "",
) -> str:
    """Public, oracle-free cue for synthetic RGB when no camera pixels exist."""
    name = str(viewpoint_name or "")
    if capture_index <= 0 or "initial" in name or name.endswith("_front"):
        return "inconclusive"
    if (
        "corridor_" in name
        or name.startswith("scout_")
        or "/left" in name
        or "/right" in name
    ):
        return "clear"
    if "recapture" in name or "same" in name:
        return "inconclusive"
    return "clear" if capture_index > 0 else "inconclusive"


def synthetic_rgb_for_label(label: str, seed: int = 0, size: int = 64) -> np.ndarray:
    """Test helper: build RGB that heuristic maps toward a label."""
    rng = np.random.default_rng(seed)
    floor = float(rng.uniform(0.12, 0.28))
    if label == "clear":
        base = np.full((size, size, 3), floor, dtype=np.float32)
        base[:, size // 4 : 3 * size // 4] = floor + 0.12
        base += rng.normal(0, 0.03, base.shape).astype(np.float32)
    elif label == "blocked":
        base = np.full((size, size, 3), floor * 0.7, dtype=np.float32)
        base[size // 3 : 2 * size // 3, size // 3 : 2 * size // 3] = max(
            0.02, floor * 0.25
        )
        base += rng.normal(0, 0.02, base.shape).astype(np.float32)
    else:
        base = np.full((size, size, 3), floor + 0.05, dtype=np.float32)
        base += rng.normal(0, 0.05, base.shape).astype(np.float32)
    return np.clip(base, 0.0, 1.0)


__all__ = (
    "VISION_MODALITY",
    "SENSOR_BUNDLE_V7",
    "SENSOR_BUNDLE_COMPAT",
    "VisionProposal",
    "propose_vision",
    "propose_vision_heuristic",
    "propose_vision_torch",
    "vision_proposal_to_claim_v2",
    "synthetic_rgb_for_label",
    "viewpoint_vision_cue",
)
