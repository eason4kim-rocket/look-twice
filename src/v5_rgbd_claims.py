"""v5 RGB-D / segmentation → Depth + Semantic Claims (shipped path).

Separates pure frame→Claim logic from episode I/O so unit tests can feed
arrays without booting Genesis. Genesis path reuses v4 capture + corruption
via ``process_evidence_frame``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from v4_claims import ClaimScope, RobotClaim, build_robot_claim, canonical_sha256
from v4_evidence import (
    SENSOR_VERSION as V4_SENSOR_VERSION,
    EvidenceCapture,
    RawEvidenceFrame,
    process_evidence_frame,
)
from v4_perception import (
    ClaimProvenance,
    ImageROI,
    analyze_depth_geometry,
    analyze_semantic_proxy,
    depth_result_to_claim,
    semantic_result_to_claim,
)

CLAIMS_MODE_SYNTHETIC = "synthetic_modality_proxies"
CLAIMS_MODE_GENESIS_RGBD = "genesis_rgbd_depth_semantic"


def claims_from_depth_and_segmentation(
    *,
    depth: np.ndarray,
    segmentation: np.ndarray,
    risk_roi: ImageROI,
    expected_clear_depth: float,
    obstacle_segmentation_idx: int,
    target_segmentation_idx: int,
    target_reference_pixels: int,
    observed_step: int,
    valid_until_step: int,
    capture_root_id: str,
    device: str = "cpu",
    calibration_id: str = V4_SENSOR_VERSION,
    pose_version: str = "pose-v4",
) -> tuple[RobotClaim, RobotClaim, dict[str, Any]]:
    """Build Depth + Semantic Claims from arrays using shipped perception helpers.

    This is the unit-testable core of RGB-D claim construction (no Genesis).
    """
    depth_result = analyze_depth_geometry(
        depth=np.asarray(depth),
        roi=risk_roi,
        expected_clear_depth=float(expected_clear_depth),
        device=device,
    )
    semantic_result = analyze_semantic_proxy(
        segmentation=np.asarray(segmentation),
        obstacle_segmentation_idx=int(obstacle_segmentation_idx),
        target_segmentation_idx=int(target_segmentation_idx),
        target_reference_pixels=int(target_reference_pixels),
        device=device,
    )
    scope = ClaimScope("look-twice-amr", "payload-small", "inspection-region")
    common = dict(
        fact_id="region:inspection-region",
        predicate="traversable",
        device_root_id="rgbd-front-01",
        capture_root_id=capture_root_id,
        calibration_id=calibration_id,
        pose_version=pose_version,
        scope=scope,
    )
    depth_claim = depth_result_to_claim(
        depth_result,
        ClaimProvenance(
            observed_step=observed_step,
            valid_until_step=valid_until_step,
            temporal_skew=0,
            **common,
        ),
    )
    semantic_claim = semantic_result_to_claim(
        semantic_result,
        ClaimProvenance(
            observed_step=observed_step,
            valid_until_step=valid_until_step,
            temporal_skew=0,
            **common,
        ),
    )
    audit = {
        "claims_mode": CLAIMS_MODE_GENESIS_RGBD,
        "depth_result": depth_result.to_wire(),
        "semantic_result": semantic_result.to_wire(),
        "capture_root_id": capture_root_id,
        "sensor_version": calibration_id,
    }
    return depth_claim, semantic_claim, audit


def process_genesis_observation(
    frame: RawEvidenceFrame,
    evidence_scenario: Any,
    *,
    observation_index: int,
    repair_action_kind: str = "initial",
    device: str = "cpu",
    ttl_steps: int = 2000,
    evidence_dir: Path | None = None,
) -> tuple[Sequence[RobotClaim], dict[str, Any]]:
    """Full v4 pipeline: corrupt frame → depth/semantic Claims + capture audit."""
    capture: EvidenceCapture = process_evidence_frame(
        frame,
        evidence_scenario,
        observation_index=observation_index,
        repair_action_kind=repair_action_kind,
        device=device,
        ttl_steps=ttl_steps,
        evidence_dir=evidence_dir,
    )
    corruption_wire = capture.corruption.to_wire()
    audit = {
        "claims_mode": CLAIMS_MODE_GENESIS_RGBD,
        "viewpoint": capture.viewpoint,
        "viewpoint_xy": list(capture.viewpoint_xy),
        "observed_step": capture.observed_step,
        "capture_root_id": capture.capture_root_id,
        "device_root_id": capture.device_root_id,
        "depth_result": dict(capture.depth_result),
        "semantic_result": dict(capture.semantic_result),
        "corruption": corruption_wire,
        "sensor_version": str(corruption_wire.get("sensor_version", V4_SENSOR_VERSION)),
        "claim_ids": [c.claim_id for c in capture.claims],
        "claim_values": [c.value for c in capture.claims],
        "claim_modalities": [c.modality for c in capture.claims],
    }
    return tuple(capture.claims), audit


def runtime_supports_rgbd_claims(runtime: Any) -> bool:
    """True when runtime can capture raw RGB-D/seg and supply a v4 evidence scenario."""
    return callable(getattr(runtime, "capture_raw", None)) and hasattr(
        runtime, "evidence_scenario"
    )


__all__ = (
    "CLAIMS_MODE_GENESIS_RGBD",
    "CLAIMS_MODE_SYNTHETIC",
    "V4_SENSOR_VERSION",
    "claims_from_depth_and_segmentation",
    "process_genesis_observation",
    "runtime_supports_rgbd_claims",
)
