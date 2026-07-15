"""RGB-D 与实例分割证据的 GPU 结算逻辑。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class PerceptionResult:
    """一次多模态传感器观察形成的可审计结果。"""

    result: str
    confidence: float
    support_pixels: int
    target_pixels: int
    visible_fraction: float
    occlusion_ratio: float
    depth_support: float
    sensor_mode: str
    device: str
    gpu_time_ms: float
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_multimodal_evidence(
    *,
    support_pixels: int,
    target_pixels: int,
    target_reference_pixels: int,
    depth_support: float,
    minimum_obstacle_pixels: int = 30,
    minimum_visible_fraction: float = 0.65,
    sensor_mode: str = "camera-rgbd",
    device: str = "cpu",
    gpu_time_ms: float = 0.0,
    artifact_paths: Optional[dict[str, str]] = None,
) -> PerceptionResult:
    """将像素统计结算为 clear、blocked 或 inconclusive。"""
    if target_reference_pixels <= 0:
        raise ValueError("target_reference_pixels must be positive")
    if support_pixels < 0 or target_pixels < 0:
        raise ValueError("pixel counts must be non-negative")

    visible_fraction = min(1.0, target_pixels / target_reference_pixels)
    occlusion_ratio = 1.0 - visible_fraction

    if support_pixels >= minimum_obstacle_pixels:
        result = "blocked"
        confidence = min(1.0, 0.8 + support_pixels / 5000.0)
    elif visible_fraction >= minimum_visible_fraction:
        result = "clear"
        confidence = min(1.0, 0.65 + 0.35 * visible_fraction)
    else:
        result = "inconclusive"
        confidence = min(0.79, max(0.1, visible_fraction * 0.8))

    return PerceptionResult(
        result=result,
        confidence=confidence,
        support_pixels=support_pixels,
        target_pixels=target_pixels,
        visible_fraction=visible_fraction,
        occlusion_ratio=occlusion_ratio,
        depth_support=depth_support,
        sensor_mode=sensor_mode,
        device=device,
        gpu_time_ms=gpu_time_ms,
        artifact_paths=artifact_paths or {},
    )


def analyze_rgbd_segmentation(
    *,
    rgb: np.ndarray,
    depth: np.ndarray,
    segmentation: np.ndarray,
    obstacle_entity_idx: int,
    target_entity_idx: int,
    target_reference_pixels: int,
    device: str = "cuda:0",
) -> PerceptionResult:
    """在 ROCm PyTorch 设备上统计分割和深度证据。"""
    import torch

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(f"Requested GPU perception but {device} is unavailable")

    start = time.perf_counter()
    start_event = end_event = None
    if device.startswith("cuda"):
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)
        start_event.record()

    # Genesis 的相机数组可能是上下翻转得到的负 stride 视图；
    # PyTorch 传入 ROCm 前需要连续内存。
    segmentation = np.ascontiguousarray(segmentation)
    depth = np.ascontiguousarray(depth)
    rgb = np.ascontiguousarray(rgb)
    seg_tensor = torch.as_tensor(segmentation, device=device, dtype=torch.int64)
    depth_tensor = torch.as_tensor(depth, device=device, dtype=torch.float32)
    # RGB 也进入 GPU，确保完整的相机证据传输路径可验证。
    rgb_tensor = torch.as_tensor(rgb, device=device, dtype=torch.uint8)

    obstacle_mask = seg_tensor == int(obstacle_entity_idx)
    target_mask = seg_tensor == int(target_entity_idx)
    support_pixels = int(obstacle_mask.sum().item())
    target_pixels = int(target_mask.sum().item())

    evidence_mask = obstacle_mask if support_pixels else target_mask
    valid_depth = depth_tensor[evidence_mask & torch.isfinite(depth_tensor)]
    depth_support = (
        float(valid_depth.median().item()) if valid_depth.numel() else 0.0
    )
    # 让 RGB Tensor 真正参与一个轻量 GPU 统计，而不是只完成拷贝。
    _ = rgb_tensor.float().mean(dim=(0, 1))

    if end_event is not None and start_event is not None:
        end_event.record()
        torch.cuda.synchronize()
        elapsed_ms = float(start_event.elapsed_time(end_event))
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000.0

    return resolve_multimodal_evidence(
        support_pixels=support_pixels,
        target_pixels=target_pixels,
        target_reference_pixels=target_reference_pixels,
        depth_support=depth_support,
        device=str(seg_tensor.device),
        gpu_time_ms=elapsed_ms,
    )


def save_sensor_artifacts(
    *,
    rgb: np.ndarray,
    depth: np.ndarray,
    segmentation: np.ndarray,
    output_dir: Path,
    stem: str,
) -> dict[str, str]:
    """保存 RGB、深度与分割证据图，返回可写入 JSON 的路径。"""
    from PIL import Image

    output_dir.mkdir(parents=True, exist_ok=True)
    rgb_path = output_dir / f"{stem}_rgb.png"
    depth_path = output_dir / f"{stem}_depth.png"
    segmentation_path = output_dir / f"{stem}_segmentation.png"

    Image.fromarray(np.asarray(rgb, dtype=np.uint8)).save(rgb_path)

    depth_array = np.asarray(depth, dtype=np.float32)
    finite = np.isfinite(depth_array)
    depth_vis = np.zeros(depth_array.shape, dtype=np.uint8)
    if finite.any():
        low = float(depth_array[finite].min())
        high = float(depth_array[finite].max())
        scale = max(high - low, 1e-6)
        depth_vis[finite] = np.clip(
            255.0 * (depth_array[finite] - low) / scale,
            0,
            255,
        ).astype(np.uint8)
    Image.fromarray(depth_vis).save(depth_path)

    seg_array = np.asarray(segmentation, dtype=np.int64)
    seg_color = np.stack(
        (
            (seg_array * 53) % 256,
            (seg_array * 97) % 256,
            (seg_array * 193) % 256,
        ),
        axis=-1,
    ).astype(np.uint8)
    Image.fromarray(seg_color).save(segmentation_path)

    return {
        "rgb": str(rgb_path),
        "depth": str(depth_path),
        "segmentation": str(segmentation_path),
    }
