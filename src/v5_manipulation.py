"""Proxy manipulation helpers (no dexterous hand).

Grasp success is a geometric attach test: end-effector near object and
commanded close, then a lift height check. Used by synthetic and Genesis adapters.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from v4_claims import ClaimScope, build_robot_claim, canonical_sha256
from v4_motion import Pose2D


@dataclass(frozen=True, slots=True)
class GraspProxyResult:
    success: bool
    reason: str
    ee_xy: tuple[float, float]
    object_xy: tuple[float, float]
    distance: float
    lifted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def end_effector_xy(pose: Pose2D, arm_offset: float = 0.27) -> tuple[float, float]:
    """Forward-facing fixed arm tip in the base frame."""
    return (
        pose.x + arm_offset * math.cos(pose.yaw),
        pose.y + arm_offset * math.sin(pose.yaw),
    )


def evaluate_proxy_grasp(
    pose: Pose2D,
    object_xy: tuple[float, float],
    *,
    close_command: bool,
    grasp_radius: float = 0.22,
    lift_command: bool = True,
) -> GraspProxyResult:
    ee = end_effector_xy(pose)
    distance = math.hypot(ee[0] - object_xy[0], ee[1] - object_xy[1])
    if not close_command:
        return GraspProxyResult(False, "gripper_open", ee, object_xy, distance, False)
    if distance > grasp_radius:
        return GraspProxyResult(False, "out_of_reach", ee, object_xy, distance, False)
    if not lift_command:
        return GraspProxyResult(False, "no_lift", ee, object_xy, distance, False)
    return GraspProxyResult(True, "attached_and_lifted", ee, object_xy, distance, True)


def build_workspace_claim(
    *,
    clear: bool,
    confidence: float,
    observed_step: int,
    valid_until_step: int,
    capture_root_id: str,
    device_root_id: str = "look-twice-amr-arm",
    quality: float = 0.85,
    scope: ClaimScope | None = None,
):
    """Geometric/workspace claim for pick_proxy (not oracle world truth)."""
    scope = scope or ClaimScope(
        robot_id="look-twice-amr",
        payload_id="payload-small",
        region_id="grasp-zone",
    )
    artifact = canonical_sha256(
        {
            "kind": "workspace_geometry",
            "clear": clear,
            "capture_root_id": capture_root_id,
            "step": observed_step,
        }
    )
    return build_robot_claim(
        fact_id="region:grasp-zone",
        predicate="graspable",
        value="clear" if clear else "blocked",
        confidence=max(0.0, min(1.0, confidence)),
        observed_step=observed_step,
        valid_until_step=valid_until_step,
        modality="workspace_geometry",
        device_root_id=device_root_id,
        capture_root_id=capture_root_id,
        calibration_id="look-twice-rgbd-v5/1",
        pose_version="base-link-v5",
        model_id="proxy-workspace-v5",
        artifact_sha256=artifact,
        parent_claim_ids=(),
        quality=quality,
        visibility=0.9 if clear else 0.5,
        temporal_skew=0,
        scope=scope,
    )


__all__ = (
    "GraspProxyResult",
    "end_effector_xy",
    "evaluate_proxy_grasp",
    "build_workspace_claim",
)
