"""Look Twice v4 的独立模态证据提取器。

Depth 分析器只接收深度图与显式风险区 ROI；Semantic 分析器只接收已污染
的 segmentation。两者不会通过共享的在线结论泄漏仿真真值。
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np

from v4_claims import ClaimScope, RobotClaim, build_robot_claim, canonical_json


@dataclass(frozen=True, slots=True)
class ImageROI:
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def validate(self, width: int, height: int) -> None:
        if not (0 <= self.x_min < self.x_max <= width):
            raise ValueError("ROI x bounds are outside the image")
        if not (0 <= self.y_min < self.y_max <= height):
            raise ValueError("ROI y bounds are outside the image")

    @property
    def pixels(self) -> int:
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)

    def to_wire(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ClaimProvenance:
    fact_id: str
    predicate: str
    observed_step: int
    valid_until_step: int
    device_root_id: str
    capture_root_id: str
    calibration_id: str
    pose_version: str
    scope: ClaimScope
    temporal_skew: int = 0


@dataclass(frozen=True, slots=True)
class DepthGeometryResult:
    result: str
    confidence: float
    roi: ImageROI
    roi_pixels: int
    valid_pixels: int
    near_pixels: int
    valid_fraction: float
    near_fraction: float
    median_depth: float | None
    expected_clear_depth: float
    near_depth_threshold: float
    quality: float
    device: str
    processing_time_ms: float
    artifact_sha256: str

    def to_wire(self) -> dict[str, Any]:
        result = asdict(self)
        result["roi"] = self.roi.to_wire()
        return result


@dataclass(frozen=True, slots=True)
class SemanticResult:
    result: str
    confidence: float
    support_pixels: int
    target_pixels: int
    target_reference_pixels: int
    visible_fraction: float
    quality: float
    device: str
    processing_time_ms: float
    artifact_sha256: str

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)


def array_artifact_sha256(array: np.ndarray, *, kind: str) -> str:
    """连同 dtype/shape 计算证据数组摘要，避免仅哈希裸字节的歧义。"""
    contiguous = np.ascontiguousarray(array)
    header = canonical_json(
        {"kind": kind, "dtype": contiguous.dtype.str, "shape": list(contiguous.shape)}
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(header)
    digest.update(b"\x00")
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def mapping_artifact_sha256(value: Mapping[str, Any], *, kind: str) -> str:
    return hashlib.sha256(
        canonical_json({"kind": kind, "value": value}).encode("utf-8")
    ).hexdigest()


def _start_timer(device: str):
    wall_start = time.perf_counter()
    if device.startswith("cuda"):
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(f"Requested v4 perception device is unavailable: {device}")
        start_event = torch.cuda.Event(enable_timing=True)
        end_event = torch.cuda.Event(enable_timing=True)
        start_event.record()
        return wall_start, start_event, end_event
    return wall_start, None, None


def _stop_timer(timer) -> float:
    wall_start, start_event, end_event = timer
    if start_event is not None and end_event is not None:
        import torch

        end_event.record()
        torch.cuda.synchronize()
        return float(start_event.elapsed_time(end_event))
    return (time.perf_counter() - wall_start) * 1000.0


def analyze_depth_geometry(
    *,
    depth: np.ndarray,
    roi: ImageROI,
    expected_clear_depth: float,
    clearance_margin: float = 0.18,
    minimum_valid_fraction: float = 0.65,
    minimum_near_fraction: float = 0.04,
    minimum_near_pixels: int = 12,
    device: str = "cpu",
) -> DepthGeometryResult:
    """只根据风险区深度几何生成证据，不读取 segmentation 或 oracle。"""
    depth_array = np.asarray(depth)
    if depth_array.ndim != 2:
        raise ValueError("depth must be a 2-D array")
    roi.validate(depth_array.shape[1], depth_array.shape[0])
    if expected_clear_depth <= 0.0 or clearance_margin <= 0.0:
        raise ValueError("expected_clear_depth and clearance_margin must be positive")
    if not 0.0 <= minimum_valid_fraction <= 1.0:
        raise ValueError("minimum_valid_fraction must be between 0 and 1")
    if not 0.0 <= minimum_near_fraction <= 1.0 or minimum_near_pixels < 1:
        raise ValueError("near evidence thresholds are invalid")

    artifact_sha = array_artifact_sha256(depth_array, kind="depth")
    timer = _start_timer(device)
    near_threshold = expected_clear_depth - clearance_margin
    if device.startswith("cuda"):
        import torch

        tensor = torch.as_tensor(
            np.ascontiguousarray(depth_array), device=device, dtype=torch.float32
        )
        sample = tensor[roi.y_min : roi.y_max, roi.x_min : roi.x_max]
        valid = torch.isfinite(sample) & (sample > 0.0)
        valid_pixels = int(valid.sum().item())
        near_pixels = int((valid & (sample < near_threshold)).sum().item())
        valid_values = sample[valid]
        median_depth = (
            float(valid_values.median().item()) if valid_values.numel() else None
        )
        actual_device = str(tensor.device)
    else:
        sample = np.asarray(
            depth_array[roi.y_min : roi.y_max, roi.x_min : roi.x_max],
            dtype=np.float32,
        )
        valid = np.isfinite(sample) & (sample > 0.0)
        valid_pixels = int(np.count_nonzero(valid))
        near_pixels = int(np.count_nonzero(valid & (sample < near_threshold)))
        valid_values = sample[valid]
        median_depth = float(np.median(valid_values)) if valid_values.size else None
        actual_device = "cpu"
    valid_fraction = valid_pixels / roi.pixels
    near_fraction = near_pixels / max(1, valid_pixels)

    required_near = max(
        minimum_near_pixels,
        int(math.ceil(max(1, valid_pixels) * minimum_near_fraction)),
    )
    if valid_fraction < minimum_valid_fraction:
        result = "inconclusive"
        confidence = max(0.1, min(0.79, 0.25 + 0.55 * valid_fraction))
    elif near_pixels >= required_near:
        result = "blocked"
        confidence = min(0.99, 0.55 + 0.35 * near_fraction + 0.10 * valid_fraction)
    elif median_depth is not None and median_depth >= near_threshold:
        result = "clear"
        separation = min(1.0, max(0.0, (median_depth - near_threshold) / clearance_margin))
        confidence = min(0.99, 0.60 + 0.25 * valid_fraction + 0.14 * separation)
    else:
        result = "inconclusive"
        confidence = min(0.79, 0.35 + 0.35 * valid_fraction)

    elapsed_ms = _stop_timer(timer)
    quality = min(1.0, valid_fraction * (1.0 - 0.5 * near_fraction))
    return DepthGeometryResult(
        result=result,
        confidence=confidence,
        roi=roi,
        roi_pixels=roi.pixels,
        valid_pixels=valid_pixels,
        near_pixels=near_pixels,
        valid_fraction=valid_fraction,
        near_fraction=near_fraction,
        median_depth=median_depth,
        expected_clear_depth=expected_clear_depth,
        near_depth_threshold=near_threshold,
        quality=quality,
        device=actual_device,
        processing_time_ms=elapsed_ms,
        artifact_sha256=artifact_sha,
    )


def analyze_semantic_proxy(
    *,
    segmentation: np.ndarray,
    obstacle_segmentation_idx: int,
    target_segmentation_idx: int,
    target_reference_pixels: int,
    minimum_obstacle_pixels: int = 30,
    minimum_visible_fraction: float = 0.65,
    device: str = "cpu",
) -> SemanticResult:
    """只根据污染后的 entity segmentation 生成模拟语义传感器 Claim。"""
    segmentation_array = np.asarray(segmentation)
    if segmentation_array.ndim != 2:
        raise ValueError("segmentation must be a 2-D array")
    if target_reference_pixels <= 0 or minimum_obstacle_pixels < 1:
        raise ValueError("semantic pixel thresholds must be positive")
    if not 0.0 <= minimum_visible_fraction <= 1.0:
        raise ValueError("minimum_visible_fraction must be between 0 and 1")

    artifact_sha = array_artifact_sha256(segmentation_array, kind="segmentation")
    timer = _start_timer(device)
    if device.startswith("cuda"):
        import torch

        tensor = torch.as_tensor(
            np.ascontiguousarray(segmentation_array), device=device, dtype=torch.int64
        )
        support_pixels = int((tensor == int(obstacle_segmentation_idx)).sum().item())
        target_pixels = int((tensor == int(target_segmentation_idx)).sum().item())
        pixel_count = int(tensor.numel())
        actual_device = str(tensor.device)
    else:
        support_pixels = int(
            np.count_nonzero(segmentation_array == int(obstacle_segmentation_idx))
        )
        target_pixels = int(
            np.count_nonzero(segmentation_array == int(target_segmentation_idx))
        )
        pixel_count = int(segmentation_array.size)
        actual_device = "cpu"
    visible_fraction = min(1.0, target_pixels / target_reference_pixels)

    if support_pixels >= minimum_obstacle_pixels:
        result = "blocked"
        confidence = min(0.99, 0.75 + support_pixels / max(5000.0, pixel_count))
    elif visible_fraction >= minimum_visible_fraction:
        result = "clear"
        confidence = min(0.99, 0.60 + 0.38 * visible_fraction)
    else:
        result = "inconclusive"
        confidence = min(0.79, max(0.1, 0.20 + 0.55 * visible_fraction))
    elapsed_ms = _stop_timer(timer)
    quality = min(1.0, 0.25 + 0.75 * visible_fraction)
    return SemanticResult(
        result=result,
        confidence=confidence,
        support_pixels=support_pixels,
        target_pixels=target_pixels,
        target_reference_pixels=target_reference_pixels,
        visible_fraction=visible_fraction,
        quality=quality,
        device=actual_device,
        processing_time_ms=elapsed_ms,
        artifact_sha256=artifact_sha,
    )


def depth_result_to_claim(
    result: DepthGeometryResult,
    provenance: ClaimProvenance,
) -> RobotClaim:
    return build_robot_claim(
        fact_id=provenance.fact_id,
        predicate=provenance.predicate,
        value=result.result,
        confidence=result.confidence,
        observed_step=provenance.observed_step,
        valid_until_step=provenance.valid_until_step,
        modality="depth_geometry",
        device_root_id=provenance.device_root_id,
        capture_root_id=provenance.capture_root_id,
        calibration_id=provenance.calibration_id,
        pose_version=provenance.pose_version,
        model_id="depth-geometry-v1",
        artifact_sha256=result.artifact_sha256,
        quality=result.quality,
        visibility=result.valid_fraction,
        temporal_skew=provenance.temporal_skew,
        scope=provenance.scope,
    )


def semantic_result_to_claim(
    result: SemanticResult,
    provenance: ClaimProvenance,
) -> RobotClaim:
    return build_robot_claim(
        fact_id=provenance.fact_id,
        predicate=provenance.predicate,
        value=result.result,
        confidence=result.confidence,
        observed_step=provenance.observed_step,
        valid_until_step=provenance.valid_until_step,
        modality="simulated_semantic_sensor",
        device_root_id=provenance.device_root_id,
        capture_root_id=provenance.capture_root_id,
        calibration_id=provenance.calibration_id,
        pose_version=provenance.pose_version,
        model_id="simulated-semantic-proxy-v1",
        artifact_sha256=result.artifact_sha256,
        quality=result.quality,
        visibility=result.visible_fraction,
        temporal_skew=provenance.temporal_skew,
        scope=provenance.scope,
    )


def build_static_map_claim(
    *,
    map_record: Mapping[str, Any],
    value: str,
    confidence: float,
    provenance: ClaimProvenance,
    map_version: str,
) -> RobotClaim:
    """将静态地图记录作为上下文先验；它不会成为 physical root。"""
    artifact_sha = mapping_artifact_sha256(map_record, kind="static-map")
    return build_robot_claim(
        fact_id=provenance.fact_id,
        predicate=provenance.predicate,
        value=value,
        confidence=confidence,
        observed_step=provenance.observed_step,
        valid_until_step=provenance.valid_until_step,
        modality="static_map",
        device_root_id="static-map-server",
        capture_root_id=f"map:{map_version}",
        calibration_id=provenance.calibration_id,
        pose_version=provenance.pose_version,
        model_id=map_version,
        artifact_sha256=artifact_sha,
        quality=1.0,
        visibility=1.0,
        temporal_skew=provenance.temporal_skew,
        scope=provenance.scope,
    )
