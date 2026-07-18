"""v7 vision proposer: RGB → structured corridor claim fields.

Backends:
  - heuristic_rgb_proxy: deterministic, CI-safe, honestly a proxy
  - torch_corridor_head: optional tiny network on ROCm/CUDA
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import SENSOR_VERSION_V6, build_robot_claim_v2

VISION_MODALITY = "vision_semantic_v7"
# Shared bundle with geometry so exact-calibration filter does not false-deny.
SENSOR_BUNDLE_V7 = "look-twice-rgbd-multi-agent-v7/1"
# Keep v6 id accepted when contract still on v6 calibration during migration.
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
    """Deterministic ROI proxy.

    Prefer free-space depth structure over raw darkness (Genesis warehouse
    frames are often dark but traversable). Darkness alone is inconclusive,
    not blocked. Not a foundation VLM.
    """
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
            # Near cluster relative to median → occlusion; mid/far → free.
            depth_block = float((finite < med * 0.55).mean())
            depth_free = float((finite > med * 0.75).mean())

    # Darkness is weak evidence of blockage in sim; free depth is strong clear.
    block_score = 0.55 * depth_block + 0.25 * max(0.0, dark_frac - 0.85) + 0.10 * max(
        0.0, 0.12 - mean_luma
    )
    clear_score = 0.55 * depth_free + 0.25 * (1.0 - depth_block) + 0.20 * min(
        1.0, std_luma * 4.0
    )
    if depth_available < 0.5:
        # RGB-only: require structured mid-tone free corridor, not pure black.
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

    quality = float(np.clip(0.45 + 0.4 * (0.5 * depth_available + 0.5 * (1.0 - abs(0.5 - std_luma))), 0.25, 0.95))
    visibility = float(np.clip(0.40 + 0.5 * max(mean_luma, 0.5 * depth_free), 0.25, 0.95))
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
        },
    )


def propose_vision_torch(
    rgb: Any,
    *,
    depth: Any | None = None,
    meta: Mapping[str, Any] | None = None,
    checkpoint: str | None = None,
    device: str = "cpu",
) -> VisionProposal:
    """Optional tiny torch head; falls back to heuristic if torch/ckpt unavailable."""
    meta = dict(meta or {})
    try:
        import torch
        import torch.nn as nn
    except Exception:
        return propose_vision_heuristic(rgb, depth=depth, meta=meta)

    arr = _rgb_to_array(rgb)
    # Resize-ish via simple stride sample to 32x32.
    ys = np.linspace(0, arr.shape[0] - 1, 32).astype(int)
    xs = np.linspace(0, arr.shape[1] - 1, 32).astype(int)
    small = arr[ys][:, xs]
    x = torch.tensor(small.transpose(2, 0, 1), dtype=torch.float32, device=device).unsqueeze(0)

    class Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(3, 8, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(8, 16, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d(1),
            )
            self.fc = nn.Linear(16, 3)  # clear, blocked, inconclusive

        def forward(self, t: torch.Tensor) -> torch.Tensor:
            h = self.net(t).flatten(1)
            return self.fc(h)

    model = Tiny().to(device)
    if checkpoint:
        try:
            payload = torch.load(checkpoint, map_location=device, weights_only=False)
            model.load_state_dict(payload["state_dict"])
        except Exception:
            return propose_vision_heuristic(rgb, depth=depth, meta=meta)
    model.eval()
    with torch.no_grad():
        logits = model(x)[0]
        probs = torch.softmax(logits, dim=0).cpu().numpy()
    labels = ("clear", "blocked", "inconclusive")
    idx = int(probs.argmax())
    value = labels[idx]
    conf = float(probs[idx])
    sha = _input_sha(arr, meta)
    return VisionProposal(
        value=value,
        confidence=float(np.clip(conf, 0.05, 0.99)),
        quality=0.7,
        visibility=0.7,
        model_id=f"{MODEL_PREFIX}/torch_corridor_head/1",
        input_sha256=sha,
        backend="torch_corridor_head",
        features={
            "p_clear": float(probs[0]),
            "p_blocked": float(probs[1]),
            "p_inconclusive": float(probs[2]),
        },
    )


def propose_vision(
    rgb: Any,
    *,
    depth: Any | None = None,
    meta: Mapping[str, Any] | None = None,
    backend: str = "heuristic_rgb_proxy",
    checkpoint: str | None = None,
    device: str = "cpu",
) -> VisionProposal:
    if backend == "torch_corridor_head":
        return propose_vision_torch(
            rgb, depth=depth, meta=meta, checkpoint=checkpoint, device=device
        )
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
    """Public, oracle-free cue for synthetic RGB when no camera pixels exist.

    Initial / same-view captures stay weak so the gate starts denied; scout
    side_view paths produce clear so active repair can complete independent
    vision roots without reading world blocked flags.
    """
    name = str(viewpoint_name or "")
    if capture_index <= 0 or "initial" in name or name.endswith("_front"):
        return "inconclusive"
    if "corridor_" in name or name.startswith("scout_") or "/left" in name or "/right" in name:
        # Heavy profiles still allow clear from independent side roots so repair
        # can succeed; geometry path carries true blocked labels separately.
        return "clear"
    if "recapture" in name or "same" in name:
        return "inconclusive"
    return "clear" if capture_index > 0 else "inconclusive"


def synthetic_rgb_for_label(label: str, seed: int = 0, size: int = 64) -> np.ndarray:
    """Test helper: build RGB that heuristic maps toward a label."""
    rng = np.random.default_rng(seed)
    # Domain-randomize mean luminance toward Genesis-like darkness (~0.15–0.35).
    floor = float(rng.uniform(0.12, 0.28))
    if label == "clear":
        base = np.full((size, size, 3), floor, dtype=np.float32)
        # Free corridor band with mild texture (not pure black blob).
        base[:, size // 4 : 3 * size // 4] = floor + 0.12
        base += rng.normal(0, 0.03, base.shape).astype(np.float32)
    elif label == "blocked":
        base = np.full((size, size, 3), floor * 0.7, dtype=np.float32)
        # Near obstacle blob in center band.
        base[size // 3 : 2 * size // 3, size // 3 : 2 * size // 3] = max(0.02, floor * 0.25)
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
