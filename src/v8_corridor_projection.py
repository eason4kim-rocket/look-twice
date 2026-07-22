"""Shared corridor ROI mask projection for V8 train collection and live runtime.

Training and live **must** use this single function. Do not invent alternate
image-space conventions (e.g. A=left half / B=right half).

Convention (world → image):
  - Read corridor world region [x0,x1,y0,y1] from public.corridors
  - center_y = mean(y0, y1)
  - Map center_y via tanh to a vertical fraction of the image
  - Paint a horizontal band (upper/lower) at x in ~[25%, 85%] of width

This matches historical v8_collect_spatial_rgbd_dataset behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def corridor_mask_from_geometry(
    h: int,
    w: int,
    *,
    corridor_id: str,
    public: Mapping[str, Any],
) -> np.ndarray:
    """Return float32 HxW mask in {0,1} for the target corridor ROI.

    Empty mask (all zeros) if corridor_id is unknown — callers must not
    invent a left/right fallback.
    """
    if h <= 0 or w <= 0:
        raise ValueError(f"invalid image size h={h} w={w}")
    mask = np.zeros((int(h), int(w)), dtype=np.float32)
    center = None
    for c in public.get("corridors") or []:
        if c.get("id") == corridor_id:
            reg = c["region"]
            center = 0.5 * (float(reg[2]) + float(reg[3]))
            break
    if center is None:
        return mask
    frac = 0.5 - 0.35 * np.tanh(center / 0.4)
    y0 = int(np.clip(frac - 0.18, 0.05, 0.75) * h)
    y1 = int(np.clip(frac + 0.18, 0.25, 0.95) * h)
    x0, x1 = int(0.25 * w), int(0.85 * w)
    mask[y0:y1, x0:x1] = 1.0
    return mask


# Backward-compatible private alias used by collector historically.
_corridor_mask_from_geometry = corridor_mask_from_geometry


__all__ = (
    "corridor_mask_from_geometry",
    "_corridor_mask_from_geometry",
)
