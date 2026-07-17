"""Look Twice v4 的不可变机器人证据声明与谱系工具。

本模块是比赛仓库中的公开 wire contract，不依赖私有 Purify 实现。在线
Claim 刻意不包含场景真值；真值只能由调用方写入独立的评估记录。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping


ROBOT_CLAIM_SCHEMA = "look-twice.robot-claim/v1"
CLAIM_VALUES = frozenset(("clear", "blocked", "inconclusive"))
PHYSICAL_MODALITIES = frozenset(
    ("depth_geometry", "simulated_semantic_sensor", "learned_rgbd_semantic")
)
UNKNOWN_ROOTS = frozenset(("", "unknown", "unavailable", "none"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> str:
    """返回跨 Python/Go 可复算的紧凑 canonical JSON。"""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ClaimScope:
    """Claim 适用的机器人、载荷与空间区域。"""

    robot_id: str
    payload_id: str
    region_id: str

    def __post_init__(self) -> None:
        if not self.robot_id or not self.payload_id or not self.region_id:
            raise ValueError("scope identifiers must be non-empty")

    def to_wire(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RobotClaim:
    """一个来源、时间和派生关系均可审计的机器人 Claim。"""

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
    parent_claim_ids: tuple[str, ...] = ()
    quality: float = 1.0
    visibility: float = 1.0
    temporal_skew: int = 0
    scope: ClaimScope = ClaimScope("robot", "default", "region")
    schema_version: str = ROBOT_CLAIM_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != ROBOT_CLAIM_SCHEMA:
            raise ValueError(f"unsupported claim schema: {self.schema_version}")
        for name in (
            "claim_id",
            "fact_id",
            "predicate",
            "modality",
            "calibration_id",
            "pose_version",
            "model_id",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} must be non-empty")
        if self.value not in CLAIM_VALUES:
            raise ValueError(f"unsupported claim value: {self.value}")
        for name in ("confidence", "quality", "visibility"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")
        if self.observed_step < 0:
            raise ValueError("observed_step must be non-negative")
        if self.valid_until_step < self.observed_step:
            raise ValueError("valid_until_step cannot precede observed_step")
        if self.temporal_skew < 0:
            raise ValueError("temporal_skew must be non-negative")
        if not _SHA256_RE.fullmatch(self.artifact_sha256):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 hex digest")
        if len(set(self.parent_claim_ids)) != len(self.parent_claim_ids):
            raise ValueError("parent_claim_ids must not contain duplicates")
        if self.claim_id in self.parent_claim_ids:
            raise ValueError("a claim cannot be its own parent")

    def to_wire(self) -> dict[str, Any]:
        result = asdict(self)
        result["parent_claim_ids"] = list(self.parent_claim_ids)
        result["scope"] = self.scope.to_wire()
        return result

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "RobotClaim":
        expected = {field for field in cls.__dataclass_fields__}
        unknown = set(payload) - expected
        if unknown:
            # 特别阻止 oracle/ground_truth 被悄悄混入在线证据。
            raise ValueError(f"unknown RobotClaim fields: {sorted(unknown)}")
        values = dict(payload)
        values["parent_claim_ids"] = tuple(values.get("parent_claim_ids", ()))
        if "scope" in values and not isinstance(values["scope"], ClaimScope):
            values["scope"] = ClaimScope(**values["scope"])
        return cls(**values)

    @property
    def is_physical_measurement(self) -> bool:
        return self.modality in PHYSICAL_MODALITIES

    @property
    def has_known_measurement_root(self) -> bool:
        return (
            self.is_physical_measurement
            and self.capture_root_id.lower() not in UNKNOWN_ROOTS
        )

    def is_fresh(self, current_step: int) -> bool:
        return self.observed_step <= current_step <= self.valid_until_step


def build_robot_claim(
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
    parent_claim_ids: Iterable[str] = (),
    quality: float = 1.0,
    visibility: float = 1.0,
    temporal_skew: int = 0,
    scope: ClaimScope = ClaimScope("robot", "default", "region"),
) -> RobotClaim:
    """用 Claim 内容生成稳定 ID；重复构造不会伪造一份新证据。"""
    parent_ids = tuple(sorted(parent_claim_ids))
    temporary = RobotClaim(
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
        parent_claim_ids=parent_ids,
        quality=quality,
        visibility=visibility,
        temporal_skew=temporal_skew,
        scope=scope,
    )
    body = temporary.to_wire()
    body.pop("claim_id")
    claim_id = f"clm_{canonical_sha256(body)[:24]}"
    return replace(temporary, claim_id=claim_id)


@dataclass(frozen=True, slots=True)
class LineageSummary:
    """去重后的谱系摘要；同 capture 内的多模态只算一个 measurement root。"""

    accepted_claim_ids: tuple[str, ...]
    discounted_claim_ids: tuple[str, ...]
    measurement_root_ids: tuple[str, ...]
    device_root_ids: tuple[str, ...]
    unknown_root_claim_ids: tuple[str, ...]

    @property
    def distinct_measurement_roots(self) -> int:
        return len(self.measurement_root_ids)


def summarize_lineage(claims: Iterable[RobotClaim]) -> LineageSummary:
    """折叠相同 artifact，并安全地排除 root 未知和 static map。"""
    ordered = sorted(
        claims,
        key=lambda claim: (
            claim.artifact_sha256,
            -claim.quality,
            -claim.confidence,
            claim.claim_id,
        ),
    )
    seen_artifacts: set[str] = set()
    accepted: list[RobotClaim] = []
    discounted: list[str] = []
    for claim in ordered:
        if claim.artifact_sha256 in seen_artifacts:
            discounted.append(claim.claim_id)
            continue
        seen_artifacts.add(claim.artifact_sha256)
        accepted.append(claim)

    measurement_roots: set[str] = set()
    device_roots: set[str] = set()
    unknown: list[str] = []
    for claim in accepted:
        if not claim.is_physical_measurement:
            continue
        if not claim.has_known_measurement_root:
            unknown.append(claim.claim_id)
            continue
        measurement_roots.add(claim.capture_root_id)
        if claim.device_root_id.lower() not in UNKNOWN_ROOTS:
            device_roots.add(claim.device_root_id)

    return LineageSummary(
        accepted_claim_ids=tuple(sorted(claim.claim_id for claim in accepted)),
        discounted_claim_ids=tuple(sorted(discounted)),
        measurement_root_ids=tuple(sorted(measurement_roots)),
        device_root_ids=tuple(sorted(device_roots)),
        unknown_root_claim_ids=tuple(sorted(unknown)),
    )
