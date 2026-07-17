"""v6 multi-agent Robot Claim v2 + lineage helpers.

v1 wire remains parseable. v2 adds observer/intended actor, received_step,
and communication_root_id. Oracle / world-truth fields are rejected.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

from v4_claims import (
    CLAIM_VALUES,
    PHYSICAL_MODALITIES,
    UNKNOWN_ROOTS,
    ClaimScope,
    LineageSummary,
    RobotClaim,
    _SHA256_RE,
    canonical_sha256,
    summarize_lineage,
)

ROBOT_CLAIM_V2_SCHEMA = "look-twice.robot-claim/v2"
SENSOR_VERSION_V6 = "look-twice-rgbd-multi-agent-v6/1"
FORBIDDEN_CLAIM_KEYS = frozenset(
    {
        "oracle",
        "ground_truth",
        "truth",
        "world_truth",
        "future_observation",
        "noise_realization",
        "obstacle_xy",
        "clean_segmentation",
    }
)


@dataclass(frozen=True, slots=True)
class RobotClaimV2:
    """Audit-grade claim with multi-agent provenance."""

    claim_id: str
    fact_id: str
    predicate: str
    value: str
    confidence: float
    observed_step: int
    valid_until_step: int
    modality: str
    device_root_id: str
    capture_root_id: str
    calibration_id: str
    pose_version: str
    model_id: str
    artifact_sha256: str
    observer_agent_id: str
    intended_actor_id: str
    received_step: int
    communication_root_id: str
    parent_claim_ids: tuple[str, ...] = ()
    communication_path: tuple[str, ...] = ()
    quality: float = 1.0
    visibility: float = 1.0
    temporal_skew: int = 0
    scope: ClaimScope = ClaimScope("carrier", "payload_loaded", "corridor_a")
    schema_version: str = ROBOT_CLAIM_V2_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version not in (ROBOT_CLAIM_V2_SCHEMA, "look-twice.robot-claim/v1"):
            raise ValueError(f"unsupported claim schema: {self.schema_version}")
        for name in (
            "claim_id",
            "fact_id",
            "predicate",
            "modality",
            "calibration_id",
            "pose_version",
            "model_id",
            "observer_agent_id",
            "intended_actor_id",
            "device_root_id",
            "capture_root_id",
            "communication_root_id",
        ):
            if not str(getattr(self, name)):
                raise ValueError(f"{name} must be non-empty")
        if self.value not in CLAIM_VALUES:
            raise ValueError(f"unsupported claim value: {self.value}")
        for name in ("confidence", "quality", "visibility"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")
        if self.observed_step < 0 or self.received_step < 0:
            raise ValueError("steps must be non-negative")
        if self.received_step < self.observed_step:
            raise ValueError("received_step cannot precede observed_step")
        if self.valid_until_step < self.observed_step:
            raise ValueError("valid_until_step cannot precede observed_step")
        if not _SHA256_RE.fullmatch(self.artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 hex digest")
        if self.claim_id in self.parent_claim_ids:
            raise ValueError("a claim cannot be its own parent")

    def to_wire(self) -> dict[str, Any]:
        result = asdict(self)
        result["parent_claim_ids"] = list(self.parent_claim_ids)
        result["communication_path"] = list(self.communication_path)
        result["scope"] = self.scope.to_wire()
        return result

    def to_v1_robot_claim(self) -> RobotClaim:
        """Project to v1 for bridges that only accept v1 schemas."""
        return RobotClaim(
            claim_id=self.claim_id,
            fact_id=self.fact_id,
            predicate=self.predicate,
            value=self.value,
            confidence=self.confidence,
            observed_step=self.observed_step,
            valid_until_step=self.valid_until_step,
            modality=self.modality,
            device_root_id=self.device_root_id,
            capture_root_id=self.capture_root_id,
            calibration_id=self.calibration_id,
            pose_version=self.pose_version,
            model_id=self.model_id,
            artifact_sha256=self.artifact_sha256,
            parent_claim_ids=self.parent_claim_ids,
            quality=self.quality,
            visibility=self.visibility,
            temporal_skew=self.temporal_skew,
            scope=self.scope,
        )

    def is_fresh_at(self, current_step: int) -> bool:
        # Freshness is always by observed_step validity, never by receive time.
        return self.observed_step <= current_step <= self.valid_until_step

    @property
    def is_physical_measurement(self) -> bool:
        return self.modality in PHYSICAL_MODALITIES

    @property
    def has_known_measurement_root(self) -> bool:
        return (
            self.is_physical_measurement
            and self.capture_root_id.lower() not in UNKNOWN_ROOTS
        )


def build_robot_claim_v2(
    *,
    fact_id: str,
    predicate: str,
    value: str,
    confidence: float,
    observed_step: int,
    valid_until_step: int,
    modality: str,
    device_root_id: str,
    capture_root_id: str,
    calibration_id: str,
    pose_version: str,
    model_id: str,
    artifact_sha256: str,
    observer_agent_id: str,
    intended_actor_id: str,
    received_step: int | None = None,
    communication_root_id: str | None = None,
    parent_claim_ids: Iterable[str] = (),
    communication_path: Iterable[str] = (),
    quality: float = 1.0,
    visibility: float = 1.0,
    temporal_skew: int = 0,
    scope: ClaimScope | None = None,
) -> RobotClaimV2:
    recv = observed_step if received_step is None else int(received_step)
    comm_root = communication_root_id or capture_root_id
    scope = scope or ClaimScope(intended_actor_id, "payload_loaded", "corridor_a")
    parents = tuple(sorted(parent_claim_ids))
    path = tuple(communication_path)
    temporary = RobotClaimV2(
        claim_id="pending",
        fact_id=fact_id,
        predicate=predicate,
        value=value,
        confidence=confidence,
        observed_step=observed_step,
        valid_until_step=valid_until_step,
        modality=modality,
        device_root_id=device_root_id,
        capture_root_id=capture_root_id,
        calibration_id=calibration_id,
        pose_version=pose_version,
        model_id=model_id,
        artifact_sha256=artifact_sha256,
        observer_agent_id=observer_agent_id,
        intended_actor_id=intended_actor_id,
        received_step=recv,
        communication_root_id=comm_root,
        parent_claim_ids=parents,
        communication_path=path,
        quality=quality,
        visibility=visibility,
        temporal_skew=temporal_skew,
        scope=scope,
    )
    body = temporary.to_wire()
    body.pop("claim_id")
    claim_id = f"clm_{canonical_sha256(body)[:24]}"
    return replace(temporary, claim_id=claim_id)


def claim_v2_from_wire(payload: Mapping[str, Any]) -> RobotClaimV2:
    unknown = set(payload) - set(RobotClaimV2.__dataclass_fields__)
    bad = unknown | (set(payload) & FORBIDDEN_CLAIM_KEYS)
    if bad:
        raise ValueError(f"unknown or forbidden RobotClaim fields: {sorted(bad)}")
    values = dict(payload)
    values["parent_claim_ids"] = tuple(values.get("parent_claim_ids") or ())
    values["communication_path"] = tuple(values.get("communication_path") or ())
    if "scope" in values and not isinstance(values["scope"], ClaimScope):
        values["scope"] = ClaimScope(**values["scope"])
    # v1 compatibility defaults
    values.setdefault("observer_agent_id", values.get("scope", ClaimScope("carrier", "p", "r")).robot_id if isinstance(values.get("scope"), ClaimScope) else "carrier")
    if isinstance(values.get("scope"), ClaimScope):
        values.setdefault("intended_actor_id", values["scope"].robot_id)
    values.setdefault("received_step", values.get("observed_step", 0))
    values.setdefault(
        "communication_root_id", values.get("capture_root_id", "unknown")
    )
    values.setdefault("schema_version", ROBOT_CLAIM_V2_SCHEMA)
    return RobotClaimV2(**values)


def upgrade_v1_to_v2(
    claim: RobotClaim,
    *,
    observer_agent_id: str,
    intended_actor_id: str | None = None,
    received_step: int | None = None,
    communication_root_id: str | None = None,
) -> RobotClaimV2:
    actor = intended_actor_id or claim.scope.robot_id
    return build_robot_claim_v2(
        fact_id=claim.fact_id,
        predicate=claim.predicate,
        value=claim.value,
        confidence=claim.confidence,
        observed_step=claim.observed_step,
        valid_until_step=claim.valid_until_step,
        modality=claim.modality,
        device_root_id=claim.device_root_id,
        capture_root_id=claim.capture_root_id,
        calibration_id=claim.calibration_id,
        pose_version=claim.pose_version,
        model_id=claim.model_id,
        artifact_sha256=claim.artifact_sha256,
        observer_agent_id=observer_agent_id,
        intended_actor_id=actor,
        received_step=received_step if received_step is not None else claim.observed_step,
        communication_root_id=communication_root_id or claim.capture_root_id,
        parent_claim_ids=claim.parent_claim_ids,
        quality=claim.quality,
        visibility=claim.visibility,
        temporal_skew=claim.temporal_skew,
        scope=claim.scope,
    )


def collapse_echo_claims(claims: Sequence[RobotClaimV2]) -> tuple[RobotClaimV2, ...]:
    """Collapse identical communication/capture roots; multiplicity does not admit."""
    best: dict[tuple[str, str, str], RobotClaimV2] = {}
    order: list[tuple[str, str, str]] = []
    for claim in claims:
        key = (
            claim.communication_root_id,
            claim.capture_root_id,
            claim.artifact_sha256,
        )
        if key not in best:
            best[key] = claim
            order.append(key)
        else:
            # Keep earliest observation / earliest receive for audit stability.
            prev = best[key]
            if (claim.observed_step, claim.received_step, claim.claim_id) < (
                prev.observed_step,
                prev.received_step,
                prev.claim_id,
            ):
                best[key] = claim
    return tuple(best[k] for k in order)


def summarize_v2_lineage(claims: Iterable[RobotClaimV2]) -> LineageSummary:
    return summarize_lineage(c.to_v1_robot_claim() for c in claims)


def distinct_capture_roots(claims: Iterable[RobotClaimV2]) -> tuple[str, ...]:
    roots: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        if not claim.has_known_measurement_root:
            continue
        if claim.capture_root_id in seen:
            continue
        seen.add(claim.capture_root_id)
        roots.append(claim.capture_root_id)
    return tuple(roots)


__all__ = (
    "ROBOT_CLAIM_V2_SCHEMA",
    "SENSOR_VERSION_V6",
    "RobotClaimV2",
    "build_robot_claim_v2",
    "claim_v2_from_wire",
    "upgrade_v1_to_v2",
    "collapse_echo_claims",
    "summarize_v2_lineage",
    "distinct_capture_roots",
)
