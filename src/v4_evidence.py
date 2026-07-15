"""Auditable v4 evidence captures and deterministic stress injection.

The online side of this module returns only corrupted sensor products and
``RobotClaim`` objects.  Clean arrays and world truth stay in the simulator's
oracle record and are never passed to the Purify core or repair planner.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from v4_claims import ClaimScope, RobotClaim, build_robot_claim, canonical_sha256
from v4_perception import (
    ClaimProvenance,
    ImageROI,
    analyze_depth_geometry,
    analyze_semantic_proxy,
    depth_result_to_claim,
    semantic_result_to_claim,
)
from v4_scenario import ScenarioSample


SENSOR_VERSION = "look-twice-rgbd-v4/1"
DEPTH_INDEX = 7
TARGET_INDEX = 11


def _stable_seed(*parts: object) -> int:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, float(value)))


@dataclass(frozen=True, slots=True)
class RawEvidenceFrame:
    rgb: np.ndarray
    depth: np.ndarray
    segmentation: np.ndarray
    risk_roi: ImageROI
    expected_clear_depth: float
    obstacle_segmentation_idx: int
    target_segmentation_idx: int
    target_reference_pixels: int
    viewpoint: str
    viewpoint_xy: tuple[float, float]
    predicted_coverage: float
    capture_step: int


@dataclass(frozen=True, slots=True)
class CorruptionAudit:
    profile: str
    derived_seed: int
    device: str
    processing_time_ms: float
    declared_noise_intensity: float
    depth_sigma: float
    depth_dropout: float
    semantic_dropout: float
    shared_occlusion_fraction: float
    structured_dropout_fraction: float
    sensor_version: str
    repair_action_kind: str

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceCapture:
    viewpoint: str
    viewpoint_xy: tuple[float, float]
    observed_step: int
    capture_root_id: str
    device_root_id: str
    claims: tuple[RobotClaim, ...]
    corruption: CorruptionAudit
    depth_result: Mapping[str, Any]
    semantic_result: Mapping[str, Any]
    raw_artifact_sha256: Mapping[str, str]
    corrupted_artifact_sha256: Mapping[str, str]
    artifact_paths: Mapping[str, str]

    def online_record(self) -> dict[str, Any]:
        """Return the auditable record that may be consumed online."""
        return {
            "viewpoint": self.viewpoint,
            "viewpoint_xy": list(self.viewpoint_xy),
            "observed_step": self.observed_step,
            "capture_root_id": self.capture_root_id,
            "device_root_id": self.device_root_id,
            "claims": [claim.to_wire() for claim in self.claims],
            "corruption": self.corruption.to_wire(),
            "depth_result": dict(self.depth_result),
            "semantic_result": dict(self.semantic_result),
            "raw_artifact_sha256": dict(self.raw_artifact_sha256),
            "corrupted_artifact_sha256": dict(self.corrupted_artifact_sha256),
            "artifact_paths": dict(self.artifact_paths),
        }


def _array_sha(array: np.ndarray, kind: str) -> str:
    contiguous = np.ascontiguousarray(array)
    return canonical_sha256(
        {
            "kind": kind,
            "dtype": contiguous.dtype.str,
            "shape": list(contiguous.shape),
            "bytes_sha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
        }
    )


def _effective_fault_strength(
    scenario: ScenarioSample,
    *,
    observation_index: int,
    repair_action_kind: str,
    predicted_coverage: float,
) -> tuple[float, float]:
    fault = scenario.fault_realization
    depth = fault.depth_severity
    semantic = fault.semantic_severity
    # A diagnostic side view or explicitly synchronised recapture can repair a
    # view-/timing-dependent fault, but never pretends to repair OOD severity.
    if observation_index > 0 and scenario.profile != "ood-severity":
        if repair_action_kind == "side_view":
            depth *= 0.34
            semantic *= 0.34
        elif repair_action_kind in {"same_view", "wait"}:
            depth *= 0.62
            semantic *= 0.62
    visibility_penalty = 0.35 * (1.0 - _clamp(predicted_coverage))
    return _clamp(depth + visibility_penalty), _clamp(semantic + visibility_penalty)


def _numpy_corrupt(
    frame: RawEvidenceFrame,
    scenario: ScenarioSample,
    *,
    observation_index: int,
    repair_action_kind: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, CorruptionAudit]:
    fault = scenario.fault_realization
    seed = _stable_seed(
        "look-twice-v4-evidence",
        scenario.seed,
        scenario.profile,
        observation_index,
        frame.viewpoint,
        repair_action_kind,
    )
    rng = np.random.default_rng(seed)
    depth_strength, semantic_strength = _effective_fault_strength(
        scenario,
        observation_index=observation_index,
        repair_action_kind=repair_action_kind,
        predicted_coverage=frame.predicted_coverage,
    )
    started = time.perf_counter()
    rgb = np.asarray(frame.rgb, dtype=np.float32).copy()
    depth = np.asarray(frame.depth, dtype=np.float32).copy()
    segmentation = np.asarray(frame.segmentation, dtype=np.int64).copy()

    distance = math.dist(frame.viewpoint_xy, (0.8, 0.0))
    depth_sigma = 0.002 + 0.028 * depth_strength * max(0.5, distance)
    depth_dropout = _clamp(0.01 + 0.38 * depth_strength, 0.0, 0.72)
    semantic_dropout = _clamp(0.01 + 0.48 * semantic_strength, 0.0, 0.80)
    valid = np.isfinite(depth) & (depth > 0.0)
    depth[valid] += rng.normal(0.0, depth_sigma, size=int(valid.sum())).astype(np.float32)
    depth[rng.random(depth.shape) < depth_dropout] = np.nan

    obstacle = segmentation == frame.obstacle_segmentation_idx
    target = segmentation == frame.target_segmentation_idx
    semantic_random = rng.random(segmentation.shape)
    obstacle &= semantic_random >= semantic_dropout
    target &= semantic_random >= 0.55 * semantic_dropout
    segmentation[
        (segmentation == frame.obstacle_segmentation_idx)
        | (segmentation == frame.target_segmentation_idx)
    ] = 0
    segmentation[target] = frame.target_segmentation_idx
    segmentation[obstacle] = frame.obstacle_segmentation_idx

    shared_fraction = 0.0
    if scenario.profile == "shared-occlusion" and repair_action_kind != "side_view":
        shared_fraction = fault.shared_occlusion_fraction
        width = int(round(depth.shape[1] * shared_fraction))
        x0 = max(0, (depth.shape[1] - width) // 2)
        x1 = min(depth.shape[1], x0 + width)
        depth[:, x0:x1] = np.nan
        segmentation[:, x0:x1] = 0

    structured_fraction = 0.0
    if scenario.profile == "structured-depth-dropout" and repair_action_kind != "side_view":
        structured_fraction = fault.structured_depth_dropout_fraction
        y0 = int(depth.shape[0] * fault.structured_depth_dropout_band[0])
        y1 = int(math.ceil(depth.shape[0] * fault.structured_depth_dropout_band[1]))
        depth[max(0, y0) : min(depth.shape[0], y1), :] = np.nan

    brightness = 1.0 - 0.24 * fault.rgb_severity
    rgb = np.clip(
        (rgb - 127.5) * brightness
        + 127.5
        + rng.normal(0.0, 2.0 + 16.0 * fault.rgb_severity, size=rgb.shape),
        0,
        255,
    ).astype(np.uint8)
    declared = _clamp(max(depth_strength, semantic_strength))
    sensor_version = SENSOR_VERSION
    if scenario.profile == "pose-calibration-drift" and observation_index == 0:
        sensor_version = SENSOR_VERSION + "+pose-drift"
    elapsed = (time.perf_counter() - started) * 1000.0
    return (
        rgb,
        depth,
        segmentation,
        CorruptionAudit(
            profile=scenario.profile,
            derived_seed=seed,
            device="cpu",
            processing_time_ms=elapsed,
            declared_noise_intensity=declared,
            depth_sigma=depth_sigma,
            depth_dropout=depth_dropout,
            semantic_dropout=semantic_dropout,
            shared_occlusion_fraction=shared_fraction,
            structured_dropout_fraction=structured_fraction,
            sensor_version=sensor_version,
            repair_action_kind=repair_action_kind,
        ),
    )


def _torch_corrupt(
    frame: RawEvidenceFrame,
    scenario: ScenarioSample,
    *,
    observation_index: int,
    repair_action_kind: str,
    device: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, CorruptionAudit]:
    """ROCm path: stochastic degradation and profile overlays stay on GPU."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(f"requested evidence device is unavailable: {device}")
    fault = scenario.fault_realization
    seed = _stable_seed(
        "look-twice-v4-evidence",
        scenario.seed,
        scenario.profile,
        observation_index,
        frame.viewpoint,
        repair_action_kind,
    ) % (2**63 - 1)
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    depth_strength, semantic_strength = _effective_fault_strength(
        scenario,
        observation_index=observation_index,
        repair_action_kind=repair_action_kind,
        predicted_coverage=frame.predicted_coverage,
    )
    distance = math.dist(frame.viewpoint_xy, (0.8, 0.0))
    depth_sigma = 0.002 + 0.028 * depth_strength * max(0.5, distance)
    depth_dropout = _clamp(0.01 + 0.38 * depth_strength, 0.0, 0.72)
    semantic_dropout = _clamp(0.01 + 0.48 * semantic_strength, 0.0, 0.80)
    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)
    start_event.record()
    rgb = torch.as_tensor(np.ascontiguousarray(frame.rgb), device=device, dtype=torch.float32)
    depth = torch.as_tensor(np.ascontiguousarray(frame.depth), device=device, dtype=torch.float32).clone()
    segmentation = torch.as_tensor(
        np.ascontiguousarray(frame.segmentation), device=device, dtype=torch.int64
    ).clone()
    valid = torch.isfinite(depth) & (depth > 0.0)
    depth += torch.randn(depth.shape, generator=generator, device=device) * depth_sigma
    depth[valid & (torch.rand(depth.shape, generator=generator, device=device) < depth_dropout)] = torch.nan
    random_field = torch.rand(segmentation.shape, generator=generator, device=device)
    obstacle = (segmentation == frame.obstacle_segmentation_idx) & (random_field >= semantic_dropout)
    target = (segmentation == frame.target_segmentation_idx) & (random_field >= 0.55 * semantic_dropout)
    segmentation[(segmentation == frame.obstacle_segmentation_idx) | (segmentation == frame.target_segmentation_idx)] = 0
    segmentation[target] = frame.target_segmentation_idx
    segmentation[obstacle] = frame.obstacle_segmentation_idx

    shared_fraction = 0.0
    if scenario.profile == "shared-occlusion" and repair_action_kind != "side_view":
        shared_fraction = fault.shared_occlusion_fraction
        width = int(round(depth.shape[1] * shared_fraction))
        x0 = max(0, (depth.shape[1] - width) // 2)
        x1 = min(depth.shape[1], x0 + width)
        depth[:, x0:x1] = torch.nan
        segmentation[:, x0:x1] = 0
    structured_fraction = 0.0
    if scenario.profile == "structured-depth-dropout" and repair_action_kind != "side_view":
        structured_fraction = fault.structured_depth_dropout_fraction
        y0 = int(depth.shape[0] * fault.structured_depth_dropout_band[0])
        y1 = int(math.ceil(depth.shape[0] * fault.structured_depth_dropout_band[1]))
        depth[max(0, y0) : min(depth.shape[0], y1), :] = torch.nan
    brightness = 1.0 - 0.24 * fault.rgb_severity
    rgb = torch.clamp(
        (rgb - 127.5) * brightness
        + 127.5
        + torch.randn(rgb.shape, generator=generator, device=device)
        * (2.0 + 16.0 * fault.rgb_severity),
        0,
        255,
    )
    end_event.record()
    torch.cuda.synchronize()
    elapsed = float(start_event.elapsed_time(end_event))
    declared = _clamp(max(depth_strength, semantic_strength))
    sensor_version = SENSOR_VERSION
    if scenario.profile == "pose-calibration-drift" and observation_index == 0:
        sensor_version = SENSOR_VERSION + "+pose-drift"
    return (
        rgb.to(torch.uint8).cpu().numpy(),
        depth.cpu().numpy(),
        segmentation.cpu().numpy(),
        CorruptionAudit(
            profile=scenario.profile,
            derived_seed=seed,
            device=str(depth.device),
            processing_time_ms=elapsed,
            declared_noise_intensity=declared,
            depth_sigma=depth_sigma,
            depth_dropout=depth_dropout,
            semantic_dropout=semantic_dropout,
            shared_occlusion_fraction=shared_fraction,
            structured_dropout_fraction=structured_fraction,
            sensor_version=sensor_version,
            repair_action_kind=repair_action_kind,
        ),
    )


def _save_arrays(
    output_dir: Path | None,
    stem: str,
    *,
    raw_rgb: np.ndarray,
    raw_depth: np.ndarray,
    raw_segmentation: np.ndarray,
    rgb: np.ndarray,
    depth: np.ndarray,
    segmentation: np.ndarray,
) -> dict[str, str]:
    if output_dir is None:
        return {}
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name, array in (
        ("raw_rgb", raw_rgb),
        ("raw_depth", raw_depth),
        ("raw_segmentation", raw_segmentation),
        ("corrupted_rgb", rgb),
        ("corrupted_depth", depth),
        ("corrupted_segmentation", segmentation),
    ):
        path = output_dir / f"{stem}_{name}.npy"
        np.save(path, np.ascontiguousarray(array), allow_pickle=False)
        paths[name] = str(path)
    return paths


def process_evidence_frame(
    frame: RawEvidenceFrame,
    scenario: ScenarioSample,
    *,
    observation_index: int,
    repair_action_kind: str = "initial",
    device: str = "cpu",
    ttl_steps: int = 60,
    evidence_dir: Path | None = None,
) -> EvidenceCapture:
    """Corrupt one raw frame, derive independent claims, and attach lineage."""
    if ttl_steps < 1 or observation_index < 0:
        raise ValueError("ttl_steps must be positive and observation_index non-negative")
    if device.startswith("cuda"):
        rgb, depth, segmentation, audit = _torch_corrupt(
            frame,
            scenario,
            observation_index=observation_index,
            repair_action_kind=repair_action_kind,
            device=device,
        )
    else:
        rgb, depth, segmentation, audit = _numpy_corrupt(
            frame,
            scenario,
            observation_index=observation_index,
            repair_action_kind=repair_action_kind,
        )

    capture_root = f"capture:{scenario.paired_world_id}:{observation_index}:{frame.viewpoint}"
    if (
        scenario.profile == "shared-occlusion"
        and observation_index == 0
        and scenario.fault_realization.shared_cause_id
    ):
        capture_root = scenario.fault_realization.shared_cause_id
    device_root = "rgbd-front-01"
    semantic_lag = 0
    depth_valid_until = frame.capture_step + ttl_steps
    semantic_valid_until = depth_valid_until
    if scenario.profile == "time-skew" and observation_index == 0:
        semantic_lag = scenario.fault_realization.semantic_lag_steps
        # The lagged frame has a deliberately narrow validity window; a new
        # synchronous capture can replace it instead of carrying skew forever.
        semantic_valid_until = frame.capture_step + 2
    scope = ClaimScope("look-twice-amr", "payload-small", "inspection-region")
    common = dict(
        fact_id="region:inspection-region",
        predicate="traversable",
        device_root_id=device_root,
        capture_root_id=capture_root,
        # The claim names the exact sensor/calibration bundle that produced it;
        # the runtime context must name the same version for applicability.
        calibration_id=audit.sensor_version,
        pose_version=("pose-drift" if audit.sensor_version != SENSOR_VERSION else "pose-v4"),
        scope=scope,
    )
    depth_result = analyze_depth_geometry(
        depth=depth,
        roi=frame.risk_roi,
        expected_clear_depth=frame.expected_clear_depth,
        device=device,
    )
    semantic_result = analyze_semantic_proxy(
        segmentation=segmentation,
        obstacle_segmentation_idx=frame.obstacle_segmentation_idx,
        target_segmentation_idx=frame.target_segmentation_idx,
        target_reference_pixels=frame.target_reference_pixels,
        device=device,
    )
    depth_claim = depth_result_to_claim(
        depth_result,
        ClaimProvenance(
            observed_step=frame.capture_step,
            valid_until_step=depth_valid_until,
            temporal_skew=0,
            **common,
        ),
    )
    semantic_claim = semantic_result_to_claim(
        semantic_result,
        ClaimProvenance(
            observed_step=max(0, frame.capture_step - semantic_lag),
            valid_until_step=semantic_valid_until,
            temporal_skew=semantic_lag,
            **common,
        ),
    )
    claims: list[RobotClaim] = [depth_claim, semantic_claim]
    if scenario.profile == "evidence-echo" and observation_index == 0:
        for index in range(scenario.fault_realization.evidence_echo_count):
            claims.append(
                build_robot_claim(
                    fact_id=semantic_claim.fact_id,
                    predicate=semantic_claim.predicate,
                    value=semantic_claim.value,
                    confidence=semantic_claim.confidence,
                    observed_step=semantic_claim.observed_step,
                    valid_until_step=semantic_claim.valid_until_step,
                    modality=semantic_claim.modality,
                    device_root_id=semantic_claim.device_root_id,
                    capture_root_id=semantic_claim.capture_root_id,
                    calibration_id=semantic_claim.calibration_id,
                    pose_version=semantic_claim.pose_version,
                    model_id=f"evidence-echo-router-{index}",
                    artifact_sha256=semantic_claim.artifact_sha256,
                    parent_claim_ids=(semantic_claim.claim_id,),
                    quality=semantic_claim.quality,
                    visibility=semantic_claim.visibility,
                    temporal_skew=semantic_claim.temporal_skew,
                    scope=semantic_claim.scope,
                )
            )
    stem = f"capture_{observation_index:02d}_{frame.viewpoint}"
    paths = _save_arrays(
        evidence_dir,
        stem,
        raw_rgb=frame.rgb,
        raw_depth=frame.depth,
        raw_segmentation=frame.segmentation,
        rgb=rgb,
        depth=depth,
        segmentation=segmentation,
    )
    return EvidenceCapture(
        viewpoint=frame.viewpoint,
        viewpoint_xy=frame.viewpoint_xy,
        observed_step=frame.capture_step,
        capture_root_id=capture_root,
        device_root_id=device_root,
        claims=tuple(claims),
        corruption=audit,
        depth_result=depth_result.to_wire(),
        semantic_result=semantic_result.to_wire(),
        raw_artifact_sha256={
            "rgb": _array_sha(frame.rgb, "raw-rgb"),
            "depth": _array_sha(frame.depth, "raw-depth"),
            "segmentation": _array_sha(frame.segmentation, "raw-segmentation"),
        },
        corrupted_artifact_sha256={
            "rgb": _array_sha(rgb, "corrupted-rgb"),
            "depth": _array_sha(depth, "corrupted-depth"),
            "segmentation": _array_sha(segmentation, "corrupted-segmentation"),
        },
        artifact_paths=paths,
    )


class SyntheticEvidenceSource:
    """Deterministic CPU fixture for CI; formal results must use Genesis."""

    def __init__(self, *, width: int = 160, height: int = 120) -> None:
        if width < 80 or height < 60:
            raise ValueError("synthetic frame is too small")
        self.width = width
        self.height = height

    def raw_frame(
        self,
        *,
        scenario: ScenarioSample,
        viewpoint: str,
        viewpoint_xy: tuple[float, float],
        predicted_coverage: float,
        capture_step: int,
    ) -> RawEvidenceFrame:
        rgb = np.full((self.height, self.width, 3), 118, dtype=np.uint8)
        depth = np.full((self.height, self.width), 3.0, dtype=np.float32)
        segmentation = np.zeros((self.height, self.width), dtype=np.int32)
        roi = ImageROI(
            self.width * 3 // 10,
            self.height // 4,
            self.width * 7 // 10,
            self.height * 3 // 4,
        )
        roi_width = roi.x_max - roi.x_min
        roi_height = roi.y_max - roi.y_min
        visible_rows = max(1, int(round(roi_height * _clamp(predicted_coverage))))
        target_y0 = roi.y_min + max(0, (roi_height - visible_rows) // 2)
        target_y1 = min(roi.y_max, target_y0 + visible_rows)
        segmentation[target_y0:target_y1, roi.x_min : roi.x_max] = TARGET_INDEX
        rgb[target_y0:target_y1, roi.x_min : roi.x_max] = (35, 165, 65)
        if scenario.truth_blocked_at(capture_step):
            obstacle_width = max(12, roi_width // 2)
            obstacle_height = max(12, roi_height // 2)
            x0 = (roi.x_min + roi.x_max - obstacle_width) // 2
            y0 = (roi.y_min + roi.y_max - obstacle_height) // 2
            x1, y1 = x0 + obstacle_width, y0 + obstacle_height
            depth[y0:y1, x0:x1] = 1.55
            segmentation[y0:y1, x0:x1] = DEPTH_INDEX
            rgb[y0:y1, x0:x1] = (190, 65, 40)
        return RawEvidenceFrame(
            rgb=rgb,
            depth=depth,
            segmentation=segmentation,
            risk_roi=roi,
            expected_clear_depth=3.0,
            obstacle_segmentation_idx=DEPTH_INDEX,
            target_segmentation_idx=TARGET_INDEX,
            target_reference_pixels=roi_width * roi_height,
            viewpoint=viewpoint,
            viewpoint_xy=viewpoint_xy,
            predicted_coverage=predicted_coverage,
            capture_step=capture_step,
        )


__all__ = (
    "CorruptionAudit",
    "EvidenceCapture",
    "RawEvidenceFrame",
    "SENSOR_VERSION",
    "SyntheticEvidenceSource",
    "process_evidence_frame",
)
