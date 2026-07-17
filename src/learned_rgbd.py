"""Lightweight learned RGB-D obstacle sensor for Look Twice v5.

The online model receives RGB, depth, and a depth-validity mask. Simulator
segmentation is never part of the model input; it remains an offline oracle.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from v4_perception import ImageROI

MODEL_SCHEMA = "look-twice.learned-rgbd/v1"
INPUT_CHANNELS = 5
DEFAULT_IMAGE_SIZE = 64


def _nearest_indices(length: int, output_length: int) -> np.ndarray:
    if length < 1 or output_length < 1:
        raise ValueError("resize dimensions must be positive")
    return np.rint(np.linspace(0, length - 1, output_length)).astype(np.int64)


def preprocess_rgbd(
    *,
    rgb: np.ndarray,
    depth: np.ndarray,
    risk_roi: ImageROI,
    expected_clear_depth: float,
    image_size: int = DEFAULT_IMAGE_SIZE,
) -> np.ndarray:
    """Crop the projected risk ROI and return a finite ``5×H×W`` tensor.

    Channels are RGB in [0, 1], clipped depth/expected-depth in [0, 1], and a
    binary validity mask. Invalid depth is represented only by the mask.
    """
    rgb_array = np.asarray(rgb)
    depth_array = np.asarray(depth)
    if rgb_array.ndim != 3 or rgb_array.shape[2] < 3:
        raise ValueError("rgb must have shape H×W×3 (or more channels)")
    if depth_array.ndim != 2 or depth_array.shape != rgb_array.shape[:2]:
        raise ValueError("depth must have shape H×W matching rgb")
    if not np.isfinite(expected_clear_depth) or expected_clear_depth <= 0.0:
        raise ValueError("expected_clear_depth must be finite and positive")
    if image_size < 8:
        raise ValueError("image_size must be at least 8")

    x0, y0, x1, y1 = (
        risk_roi.x_min,
        risk_roi.y_min,
        risk_roi.x_max,
        risk_roi.y_max,
    )
    if not (0 <= x0 < x1 <= rgb_array.shape[1] and 0 <= y0 < y1 <= rgb_array.shape[0]):
        raise ValueError("risk ROI lies outside the RGB-D frame")
    rgb_crop = np.ascontiguousarray(rgb_array[y0:y1, x0:x1, :3])
    depth_crop = np.ascontiguousarray(depth_array[y0:y1, x0:x1])
    ys = _nearest_indices(rgb_crop.shape[0], image_size)
    xs = _nearest_indices(rgb_crop.shape[1], image_size)
    rgb_resized = rgb_crop[ys[:, None], xs[None, :]].astype(np.float32) / 255.0
    depth_resized = depth_crop[ys[:, None], xs[None, :]].astype(np.float32)
    valid = np.isfinite(depth_resized) & (depth_resized > 0.0)
    depth_ratio = np.zeros_like(depth_resized, dtype=np.float32)
    depth_ratio[valid] = np.clip(
        depth_resized[valid] / float(expected_clear_depth), 0.0, 2.0
    ) / 2.0
    channels = np.concatenate(
        (
            np.moveaxis(rgb_resized, -1, 0),
            depth_ratio[None, ...],
            valid.astype(np.float32)[None, ...],
        ),
        axis=0,
    )
    output = np.ascontiguousarray(channels, dtype=np.float32)
    if output.shape != (INPUT_CHANNELS, image_size, image_size):
        raise AssertionError(f"unexpected learned RGB-D shape: {output.shape}")
    if not np.isfinite(output).all():
        raise AssertionError("learned RGB-D preprocessing produced non-finite values")
    return output


def array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(str(tuple(value.shape)).encode("ascii"))
    digest.update(value.tobytes())
    return digest.hexdigest()


def build_model(torch: Any, *, input_channels: int = INPUT_CHANNELS):
    """Small CNN suitable for ROCm training and low-latency inference."""
    return torch.nn.Sequential(
        torch.nn.Conv2d(input_channels, 16, 5, stride=2, padding=2),
        torch.nn.BatchNorm2d(16),
        torch.nn.ReLU(),
        torch.nn.Conv2d(16, 32, 3, stride=2, padding=1),
        torch.nn.BatchNorm2d(32),
        torch.nn.ReLU(),
        torch.nn.Conv2d(32, 64, 3, stride=2, padding=1),
        torch.nn.BatchNorm2d(64),
        torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool2d((1, 1)),
        torch.nn.Flatten(),
        torch.nn.Linear(64, 1),
    )


def load_checkpoint(path: Path, *, device: str = "cpu") -> tuple[Any, dict[str, Any]]:
    import torch

    checkpoint = torch.load(path, map_location=device, weights_only=False)
    if checkpoint.get("schema_version") != MODEL_SCHEMA:
        raise ValueError("unsupported learned RGB-D checkpoint schema")
    model = build_model(torch).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


__all__ = (
    "DEFAULT_IMAGE_SIZE",
    "INPUT_CHANNELS",
    "MODEL_SCHEMA",
    "array_sha256",
    "build_model",
    "load_checkpoint",
    "preprocess_rgbd",
)
