"""V8 spatial RGB-D claim builder (runtime-legal fields only)."""

from __future__ import annotations

from typing import Any, Mapping

from v4_claims import ClaimScope
from v6_claims import SENSOR_VERSION_V6, build_robot_claim_v2
from v7_vision_claims import VISION_MODALITY

SENSOR_BUNDLE_V8 = "look-twice-rgbd-spatial-v8/1"
MODEL_PREFIX = "look-twice-v8-vision"


def spatial_proposal_to_claim_v2(
    *,
    value: str,
    confidence: float,
    quality: float,
    visibility: float,
    model_id: str,
    artifact_sha256: str,
    agent_id: str,
    corridor_id: str,
    step: int,
    ttl: int = 2000,
    capture_root_id: str | None = None,
    p_blocked: float | None = None,
    uncertainty: float | None = None,
) -> Any:
    """Build RobotClaimV2; RGB-D same capture → single measurement root."""
    root = capture_root_id or f"spatial-v8-{agent_id}-{artifact_sha256[:12]}"
    claim = build_robot_claim_v2(
        fact_id=f"region:{corridor_id}",
        predicate="carrier_traversable",
        value=value,
        confidence=confidence,
        observed_step=step,
        valid_until_step=step + ttl,
        modality="vision_spatial_rgbd_v8",
        device_root_id=f"rgbd-{agent_id}-01",
        capture_root_id=root,
        calibration_id=SENSOR_BUNDLE_V8,
        pose_version="base-link-v8",
        model_id=model_id,
        artifact_sha256=artifact_sha256,
        observer_agent_id=agent_id,
        intended_actor_id="carrier",
        received_step=step,
        communication_root_id=root,
        quality=quality,
        visibility=visibility,
        scope=ClaimScope("carrier", "payload_loaded", corridor_id),
    )
    return claim


def runtime_meta_from_prediction(
    pred: Mapping[str, Any],
    *,
    corridor_id: str,
    viewpoint: str,
) -> dict[str, Any]:
    return {
        "kind": "spatial_rgbd_proposal_v8",
        "corridor_id": corridor_id,
        "viewpoint": viewpoint,
        "p_blocked": pred.get("p_blocked"),
        "visibility": pred.get("visibility"),
        "quality": pred.get("quality"),
        "uncertainty": pred.get("uncertainty"),
        "value": pred.get("value"),
        "prediction_set": pred.get("prediction_set"),
        "fallback_used": False,
        "reads_clean_segmentation": False,
        "modality": "vision_spatial_rgbd_v8",
    }


__all__ = (
    "SENSOR_BUNDLE_V8",
    "MODEL_PREFIX",
    "VISION_MODALITY",
    "spatial_proposal_to_claim_v2",
    "runtime_meta_from_prediction",
)
