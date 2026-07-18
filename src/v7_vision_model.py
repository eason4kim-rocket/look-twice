"""Shared Genesis corridor vision model + preprocessing (train/cal/runtime).

Must stay the single source of truth for:
  - GenesisCorridorHead architecture
  - ROI crop + 96×96 resize used at collection time
  - blocked logit → sigmoid p_blocked
  - conformal prediction-set mapping
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

PREPROCESSING_VERSION = "v7-genesis-roi-side-0.30-0.75-0.28-0.72-resize96-v1"
# Side-view ROI fractions (y0,y1,x0,x1) — must match v7_collect_genesis_vision_dataset.
SIDE_ROI_FRAC = (0.30, 0.75, 0.28, 0.72)
INPUT_SIZE = 96
MODEL_ID = "look-twice-v7-vision/genesis_corridor_head/2"


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rgb_to_float01(rgb: Any) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] > 3:
        arr = arr[..., :3]
    arr = arr.astype(np.float32)
    if arr.max() > 1.5:
        arr = arr / 255.0
    return np.ascontiguousarray(arr)


def crop_roi(
    rgb: np.ndarray,
    frac: tuple[float, float, float, float] = SIDE_ROI_FRAC,
) -> np.ndarray:
    """Crop with (y0,y1,x0,x1) fractions — identical to dataset collector."""
    arr = rgb_to_float01(rgb)
    h, w = arr.shape[:2]
    y0, y1 = int(frac[0] * h), int(frac[1] * h)
    x0, x1 = int(frac[2] * w), int(frac[3] * w)
    y0, y1 = max(0, y0), min(h, max(y0 + 2, y1))
    x0, x1 = max(0, x0), min(w, max(x0 + 2, x1))
    return np.ascontiguousarray(arr[y0:y1, x0:x1])


def resize_96(rgb: np.ndarray, size: int = INPUT_SIZE) -> np.ndarray:
    """Nearest-neighbor resize to size×size float32 RGB in [0,1]."""
    arr = rgb_to_float01(rgb)
    h, w = arr.shape[:2]
    ys = np.linspace(0, h - 1, size).astype(int)
    xs = np.linspace(0, w - 1, size).astype(int)
    return np.ascontiguousarray(arr[ys][:, xs])


def preprocess_rgb_for_model(
    rgb: Any,
    *,
    already_96: bool = False,
    roi_frac: tuple[float, float, float, float] = SIDE_ROI_FRAC,
) -> np.ndarray:
    """Full pipeline: optional ROI crop → 96×96.

    Dataset .npy files are already cropped+resized (already_96=True).
    Runtime Genesis frames use crop+resize.
    """
    arr = rgb_to_float01(rgb)
    if already_96 and arr.shape[0] == INPUT_SIZE and arr.shape[1] == INPUT_SIZE:
        return arr
    # If already 96 but not flagged, still ok to resize from self.
    if arr.shape[0] == INPUT_SIZE and arr.shape[1] == INPUT_SIZE and already_96:
        return arr
    crop = crop_roi(arr, roi_frac)
    return resize_96(crop)


# Real class (torch optional at import for pure-numpy preprocess tests)
try:
    import torch
    import torch.nn as nn

    class GenesisCorridorHead(nn.Module):
        """96×96 RGB → blocked logit (Conv32/64/128). Shared train/cal/runtime."""

        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, 3, stride=2, padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(32, 64, 3, stride=2, padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(64, 128, 3, stride=2, padding=1),
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d(1),
            )
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(128, 64),
                nn.ReLU(inplace=True),
                nn.Linear(64, 1),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.head(self.features(x)).squeeze(-1)

except Exception:  # pragma: no cover
    GenesisCorridorHead = None  # type: ignore[misc, assignment]


@dataclass(frozen=True, slots=True)
class ConformalThresholds:
    include_blocked_if_p_blocked_ge: float
    include_clear_if_p_blocked_le: float
    coverage_target: float
    source_path: str
    artifact_sha256: str

    def prediction_set(self, p_blocked: float) -> tuple[str, ...]:
        include_b = p_blocked >= self.include_blocked_if_p_blocked_ge
        include_c = p_blocked <= self.include_clear_if_p_blocked_le
        if include_b and include_c:
            return ("clear", "blocked")
        if include_b:
            return ("blocked",)
        if include_c:
            return ("clear",)
        return ("clear", "blocked")  # empty → treat as inconclusive set

    def value_from_p(self, p_blocked: float) -> str:
        ps = self.prediction_set(p_blocked)
        if ps == ("blocked",):
            return "blocked"
        if ps == ("clear",):
            return "clear"
        return "inconclusive"


def load_conformal_artifact(path: str | Path) -> ConformalThresholds:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"conformal artifact missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"conformal artifact corrupt: {path}: {e}") from e
    thr = payload.get("thresholds") or payload.get("runtime_rule") or {}
    # Prefer thresholds block
    if "include_blocked_if_p_blocked_ge" in (payload.get("thresholds") or {}):
        thr = payload["thresholds"]
    elif "include_blocked_if_p_blocked_ge" in (payload.get("runtime_rule") or {}):
        thr = payload["runtime_rule"]
    try:
        t_b = float(thr["include_blocked_if_p_blocked_ge"])
        t_c = float(thr.get("include_clear_if_p_blocked_le"))
        if "include_clear_if_p_blocked_le" not in thr and "include_clear_if_p_clear_ge" in thr:
            # p_clear >= t  ⇔  p_blocked <= 1-t
            t_c = 1.0 - float(thr["include_clear_if_p_clear_ge"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"conformal thresholds incomplete in {path}: {e}") from e
    if not (0.0 <= t_c < t_b <= 1.0):
        raise ValueError(
            f"invalid conformal bounds clear_le={t_c} blocked_ge={t_b} in {path}"
        )
    return ConformalThresholds(
        include_blocked_if_p_blocked_ge=t_b,
        include_clear_if_p_blocked_le=t_c,
        coverage_target=float((payload.get("thresholds") or {}).get("coverage_target") or 0.95),
        source_path=str(path),
        artifact_sha256=file_sha256(path),
    )


def load_genesis_corridor_head(
    checkpoint: str | Path,
    *,
    device: str = "cpu",
) -> tuple[Any, str, dict[str, Any]]:
    """Load GenesisCorridorHead from best.pt. Fail closed on mismatch."""
    if GenesisCorridorHead is None:
        raise RuntimeError("torch is required for GenesisCorridorHead")
    import torch

    path = Path(checkpoint)
    if not path.is_file():
        raise FileNotFoundError(f"vision checkpoint missing: {path}")
    ckpt_sha = file_sha256(path)
    try:
        payload = torch.load(path, map_location=device, weights_only=False)
    except Exception as e:
        raise RuntimeError(f"failed to load checkpoint {path}: {e}") from e
    state = payload.get("state_dict") if isinstance(payload, dict) else None
    if not isinstance(state, dict):
        raise RuntimeError(f"checkpoint missing state_dict: {path}")
    model = GenesisCorridorHead().to(device)
    try:
        model.load_state_dict(state, strict=True)
    except Exception as e:
        raise RuntimeError(
            f"checkpoint state_dict does not match GenesisCorridorHead: {e}"
        ) from e
    model.eval()
    meta = {
        "checkpoint": str(path),
        "checkpoint_sha256": ckpt_sha,
        "model": payload.get("model") if isinstance(payload, dict) else None,
        "best_val_balanced_accuracy": (
            payload.get("best_val_balanced_accuracy") if isinstance(payload, dict) else None
        ),
    }
    return model, ckpt_sha, meta


def predict_p_blocked(
    model: Any,
    rgb: Any,
    *,
    device: str = "cpu",
    already_96: bool = False,
) -> float:
    """Return sigmoid(p_blocked) for one RGB frame."""
    import torch

    small = preprocess_rgb_for_model(rgb, already_96=already_96)
    x = torch.from_numpy(small.transpose(2, 0, 1).copy()).float().unsqueeze(0).to(device)
    with torch.no_grad():
        logit = model(x)
        if logit.ndim > 0:
            logit = logit.reshape(-1)[0]
        return float(torch.sigmoid(logit).item())


def predict_label(
    model: Any,
    rgb: Any,
    conformal: ConformalThresholds,
    *,
    device: str = "cpu",
    already_96: bool = False,
) -> dict[str, Any]:
    p = predict_p_blocked(model, rgb, device=device, already_96=already_96)
    value = conformal.value_from_p(p)
    pred_set = list(conformal.prediction_set(p))
    return {
        "value": value,
        "p_blocked": p,
        "p_clear": 1.0 - p,
        "prediction_set": pred_set,
        "preprocessing_version": PREPROCESSING_VERSION,
    }


__all__ = (
    "PREPROCESSING_VERSION",
    "SIDE_ROI_FRAC",
    "INPUT_SIZE",
    "MODEL_ID",
    "GenesisCorridorHead",
    "ConformalThresholds",
    "file_sha256",
    "rgb_to_float01",
    "crop_roi",
    "resize_96",
    "preprocess_rgb_for_model",
    "load_conformal_artifact",
    "load_genesis_corridor_head",
    "predict_p_blocked",
    "predict_label",
)
