"""在 CPU 或 ROCm PyTorch Tensor 上模拟视角相关 RGB-D/分割退化。"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SensorNoiseConfig:
    severity: float
    depth_scale: float = 1.0
    segmentation_scale: float = 1.0
    rgb_scale: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be between 0 and 1")


@dataclass(frozen=True)
class CorruptedObservation:
    rgb: np.ndarray
    depth: np.ndarray
    segmentation: np.ndarray
    derived_seed: int
    device: str
    gpu_time_ms: float
    viewpoint_distance: float
    predicted_visibility: float
    degradation: float
    parameters: dict[str, float]

    def audit_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("rgb")
        result.pop("depth")
        result.pop("segmentation")
        return result


def derive_observation_seed(seed: int, observation_index: int, viewpoint: str) -> int:
    payload = f"look-twice-v3:{seed}:{observation_index}:{viewpoint}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (2**31)


def predict_degradation(
    *, severity: float, distance: float, predicted_visibility: float
) -> float:
    """仅用已知视角几何预测传感器退化，不读取未知障碍真值。"""
    distance_factor = min(1.0, max(0.0, distance / 4.0))
    visibility_loss = 1.0 - min(1.0, max(0.0, predicted_visibility))
    return min(1.0, severity * (0.35 + 0.35 * distance_factor + 0.55 * visibility_loss))


def corrupt_rgbd_segmentation(
    *,
    rgb: np.ndarray,
    depth: np.ndarray,
    segmentation: np.ndarray,
    obstacle_segmentation_idx: int,
    target_segmentation_idx: int,
    config: SensorNoiseConfig,
    seed: int,
    observation_index: int,
    viewpoint: str,
    viewpoint_xy: tuple[float, float],
    target_xy: tuple[float, float],
    predicted_visibility: float,
    device: str = "cpu",
) -> CorruptedObservation:
    """污染原始传感器数组；所有随机采样和形态学操作均在目标设备执行。"""
    import torch
    import torch.nn.functional as functional

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(f"Requested sensor corruption device is unavailable: {device}")

    derived_seed = derive_observation_seed(seed, observation_index, viewpoint)
    generator = torch.Generator(device=device)
    generator.manual_seed(derived_seed)
    distance = math.dist(viewpoint_xy, target_xy)
    degradation = predict_degradation(
        severity=config.severity,
        distance=distance,
        predicted_visibility=predicted_visibility,
    )
    depth_sigma = (0.002 + 0.035 * degradation * distance) * config.depth_scale
    depth_dropout = min(0.65, 0.015 + 0.42 * degradation * config.depth_scale)
    segmentation_dropout = min(
        0.75, 0.01 + 0.48 * degradation * config.segmentation_scale
    )
    # 稀疏误检必须保持在“有限证据”范围，不能让整幅背景随机噪声轻易越过
    # perception 的 obstacle pixel 阈值。
    false_positive_rate = min(
        0.00020, 0.00001 + 0.00012 * degradation * config.segmentation_scale
    )
    rgb_noise_sigma = (1.5 + 22.0 * degradation) * config.rgb_scale
    brightness = 1.0 - 0.30 * degradation

    start = time.perf_counter()
    start_event = end_event = None
    if device.startswith("cuda"):
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)
        start_event.record()

    rgb_tensor = torch.as_tensor(
        np.ascontiguousarray(rgb), device=device, dtype=torch.float32
    )
    depth_tensor = torch.as_tensor(
        np.ascontiguousarray(depth), device=device, dtype=torch.float32
    ).clone()
    seg_tensor = torch.as_tensor(
        np.ascontiguousarray(segmentation), device=device, dtype=torch.int64
    ).clone()

    rgb_noise = torch.randn(
        rgb_tensor.shape, generator=generator, device=device, dtype=torch.float32
    ) * rgb_noise_sigma
    rgb_tensor = torch.clamp((rgb_tensor - 127.5) * brightness + 127.5 + rgb_noise, 0, 255)

    finite_depth = torch.isfinite(depth_tensor)
    depth_noise = torch.randn(
        depth_tensor.shape, generator=generator, device=device, dtype=torch.float32
    ) * depth_sigma
    depth_tensor[finite_depth] += depth_noise[finite_depth]
    depth_random = torch.rand(depth_tensor.shape, generator=generator, device=device)
    depth_tensor[finite_depth & (depth_random < depth_dropout)] = torch.nan

    obstacle_mask = seg_tensor == int(obstacle_segmentation_idx)
    target_mask = seg_tensor == int(target_segmentation_idx)
    kernel_size = 3 if degradation < 0.55 else 5
    padding = kernel_size // 2
    if degradation > 0.12:
        obstacle_float = obstacle_mask.float()[None, None]
        target_float = target_mask.float()[None, None]
        # 障碍 mask 做腐蚀以模拟漏检，目标 mask 做轻微膨胀/腐蚀交替模拟边界误差。
        obstacle_mask = (
            1.0
            - functional.max_pool2d(
                1.0 - obstacle_float,
                kernel_size=kernel_size,
                stride=1,
                padding=padding,
            )
        )[0, 0] > 0.5
        if derived_seed % 2:
            target_mask = functional.max_pool2d(
                target_float, kernel_size=kernel_size, stride=1, padding=padding
            )[0, 0] > 0.5
        else:
            target_mask = (
                1.0
                - functional.max_pool2d(
                    1.0 - target_float,
                    kernel_size=kernel_size,
                    stride=1,
                    padding=padding,
                )
            )[0, 0] > 0.5

    seg_random = torch.rand(seg_tensor.shape, generator=generator, device=device)
    obstacle_mask &= seg_random >= segmentation_dropout
    target_mask &= seg_random >= segmentation_dropout * 0.55
    background = ~(
        (seg_tensor == int(obstacle_segmentation_idx))
        | (seg_tensor == int(target_segmentation_idx))
    )
    false_positive = background & (seg_random < false_positive_rate)
    corrupted_seg = seg_tensor.clone()
    corrupted_seg[seg_tensor == int(obstacle_segmentation_idx)] = 0
    corrupted_seg[seg_tensor == int(target_segmentation_idx)] = 0
    corrupted_seg[target_mask] = int(target_segmentation_idx)
    corrupted_seg[obstacle_mask | false_positive] = int(obstacle_segmentation_idx)

    if end_event is not None and start_event is not None:
        end_event.record()
        torch.cuda.synchronize()
        elapsed_ms = float(start_event.elapsed_time(end_event))
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000.0

    return CorruptedObservation(
        rgb=rgb_tensor.to(torch.uint8).cpu().numpy(),
        depth=depth_tensor.cpu().numpy(),
        segmentation=corrupted_seg.cpu().numpy(),
        derived_seed=derived_seed,
        device=str(seg_tensor.device),
        gpu_time_ms=elapsed_ms,
        viewpoint_distance=distance,
        predicted_visibility=predicted_visibility,
        degradation=degradation,
        parameters={
            "depth_sigma": depth_sigma,
            "depth_dropout": depth_dropout,
            "segmentation_dropout": segmentation_dropout,
            "false_positive_rate": false_positive_rate,
            "rgb_noise_sigma": rgb_noise_sigma,
            "brightness": brightness,
            "kernel_size": float(kernel_size),
        },
    )
