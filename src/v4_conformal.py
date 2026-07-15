"""Look Twice v4 的 class-conditional split conformal 校准。"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from v4_claims import canonical_json, canonical_sha256


CALIBRATION_SCHEMA = "purify.robotics.calibration.v1"
LABELS = ("clear", "blocked")


@dataclass(frozen=True, slots=True)
class CalibrationSample:
    seed: int
    profile: str
    noise_intensity: float
    sensor_version: str
    true_label: str
    p_clear: float

    def __post_init__(self) -> None:
        if self.seed < 0 or not self.profile or not self.sensor_version:
            raise ValueError("calibration sample identifiers are invalid")
        if self.true_label not in LABELS:
            raise ValueError(f"unsupported calibration label: {self.true_label}")
        for name in ("noise_intensity", "p_clear"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SeedRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid seed range")

    def to_wire(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CalibrationContext:
    profile: str
    noise_intensity: float
    sensor_version: str


@dataclass(frozen=True, slots=True)
class ApplicabilityResult:
    applicable: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ConformalPrediction:
    prediction_set: tuple[str, ...]
    applicable: bool
    applicability_reason: str
    p_clear: float
    nonconformity_scores: dict[str, float]
    class_quantiles: dict[str, float]
    calibration_artifact_id: str

    @property
    def unresolved(self) -> bool:
        return len(self.prediction_set) != 1

    def to_wire(self) -> dict[str, Any]:
        result = asdict(self)
        result["prediction_set"] = list(self.prediction_set)
        return result


@dataclass(frozen=True, slots=True)
class CalibrationArtifact:
    artifact_id: str
    alpha: float
    class_quantiles: dict[str, float]
    applicable_profiles: tuple[str, ...]
    min_noise_intensity: float
    max_noise_intensity: float
    sensor_versions: tuple[str, ...]
    git_commit: str
    dataset_sha256: str
    seed_ranges: tuple[SeedRange, ...]
    schema_version: str = CALIBRATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != CALIBRATION_SCHEMA:
            raise ValueError(f"unsupported calibration schema: {self.schema_version}")
        if not self.artifact_id or not self.git_commit:
            raise ValueError("artifact_id and git_commit must be non-empty")
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1")
        if set(self.class_quantiles) != set(LABELS):
            raise ValueError("class_quantiles must contain clear and blocked")
        for quantile in self.class_quantiles.values():
            if not math.isfinite(quantile) or not 0.0 <= quantile <= 1.0:
                raise ValueError("class quantiles must be finite and between 0 and 1")
        if not self.applicable_profiles or not self.sensor_versions:
            raise ValueError("profiles and sensor versions must be non-empty")
        if not 0.0 <= self.min_noise_intensity <= self.max_noise_intensity <= 1.0:
            raise ValueError("invalid applicable noise range")
        if len(self.dataset_sha256) != 64:
            raise ValueError("dataset_sha256 must be a SHA-256 digest")

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "alpha": self.alpha,
            "class_quantiles": dict(sorted(self.class_quantiles.items())),
            "applicable_profiles": list(self.applicable_profiles),
            "min_noise_intensity": self.min_noise_intensity,
            "max_noise_intensity": self.max_noise_intensity,
            "sensor_versions": list(self.sensor_versions),
            "git_commit": self.git_commit,
            "dataset_sha256": self.dataset_sha256,
            "seed_ranges": [seed_range.to_wire() for seed_range in self.seed_ranges],
        }

    @classmethod
    def from_wire(cls, payload: Mapping[str, Any]) -> "CalibrationArtifact":
        values = dict(payload)
        values["applicable_profiles"] = tuple(values["applicable_profiles"])
        values["sensor_versions"] = tuple(values["sensor_versions"])
        values["seed_ranges"] = tuple(
            item if isinstance(item, SeedRange) else SeedRange(**item)
            for item in values.get("seed_ranges", ())
        )
        values["class_quantiles"] = dict(values["class_quantiles"])
        return cls(**values)

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.to_wire())

    def check_applicability(self, context: CalibrationContext) -> ApplicabilityResult:
        if context.profile not in self.applicable_profiles:
            return ApplicabilityResult(False, "profile_not_calibrated")
        if context.sensor_version not in self.sensor_versions:
            return ApplicabilityResult(False, "sensor_version_mismatch")
        if not math.isfinite(context.noise_intensity):
            return ApplicabilityResult(False, "noise_intensity_invalid")
        if not self.min_noise_intensity <= context.noise_intensity <= self.max_noise_intensity:
            return ApplicabilityResult(False, "noise_intensity_out_of_range")
        return ApplicabilityResult(True, "applicable")

    def predict(
        self,
        *,
        p_clear: float,
        context: CalibrationContext,
    ) -> ConformalPrediction:
        if not math.isfinite(p_clear) or not 0.0 <= p_clear <= 1.0:
            raise ValueError("p_clear must be finite and between 0 and 1")
        applicability = self.check_applicability(context)
        scores = {"clear": 1.0 - p_clear, "blocked": p_clear}
        if not applicability.applicable:
            prediction_set = LABELS
        else:
            selected = tuple(
                label
                for label in LABELS
                if scores[label] <= self.class_quantiles[label] + 1e-12
            )
            # 空集合不能支持动作；统一提升为可审计的 unresolved 集合。
            prediction_set = selected or LABELS
        return ConformalPrediction(
            prediction_set=prediction_set,
            applicable=applicability.applicable,
            applicability_reason=applicability.reason,
            p_clear=p_clear,
            nonconformity_scores=scores,
            class_quantiles=dict(self.class_quantiles),
            calibration_artifact_id=self.artifact_id,
        )

    def save(self, path: Path) -> None:
        path.write_text(canonical_json(self.to_wire()) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CalibrationArtifact":
        return cls.from_wire(json.loads(path.read_text(encoding="utf-8")))


def finite_sample_quantile(scores: Iterable[float], alpha: float) -> float:
    """Split conformal 的 ceil((n+1)(1-alpha)) 有限样本分位数。"""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    ordered = sorted(float(score) for score in scores)
    if not ordered:
        raise ValueError("at least one score is required")
    if any(not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in ordered):
        raise ValueError("scores must be finite and between 0 and 1")
    rank = min(len(ordered), math.ceil((len(ordered) + 1) * (1.0 - alpha)))
    return ordered[rank - 1]


def _contiguous_seed_ranges(seeds: Iterable[int]) -> tuple[SeedRange, ...]:
    unique = sorted(set(seeds))
    if not unique:
        return ()
    ranges: list[SeedRange] = []
    start = previous = unique[0]
    for seed in unique[1:]:
        if seed != previous + 1:
            ranges.append(SeedRange(start, previous))
            start = seed
        previous = seed
    ranges.append(SeedRange(start, previous))
    return tuple(ranges)


def fit_class_conditional_calibration(
    samples: Iterable[CalibrationSample],
    *,
    git_commit: str,
    alpha: float = 0.05,
) -> CalibrationArtifact:
    """从独立 calibration split 生成版本化、可哈希的 Artifact。"""
    records = sorted(
        tuple(samples),
        key=lambda sample: (
            sample.profile,
            sample.seed,
            sample.sensor_version,
            sample.true_label,
            sample.p_clear,
        ),
    )
    if not records:
        raise ValueError("calibration samples cannot be empty")
    scores: dict[str, list[float]] = {label: [] for label in LABELS}
    for sample in records:
        p_true = sample.p_clear if sample.true_label == "clear" else 1.0 - sample.p_clear
        scores[sample.true_label].append(1.0 - p_true)
    if any(not values for values in scores.values()):
        raise ValueError("class-conditional calibration requires both labels")

    dataset_wire = [sample.to_wire() for sample in records]
    dataset_sha = canonical_sha256(dataset_wire)
    artifact = CalibrationArtifact(
        artifact_id="pending",
        alpha=alpha,
        class_quantiles={
            label: finite_sample_quantile(values, alpha) for label, values in scores.items()
        },
        applicable_profiles=tuple(sorted({sample.profile for sample in records})),
        min_noise_intensity=min(sample.noise_intensity for sample in records),
        max_noise_intensity=max(sample.noise_intensity for sample in records),
        sensor_versions=tuple(sorted({sample.sensor_version for sample in records})),
        git_commit=git_commit,
        dataset_sha256=dataset_sha,
        seed_ranges=_contiguous_seed_ranges(sample.seed for sample in records),
    )
    wire = artifact.to_wire()
    wire.pop("artifact_id")
    return replace(artifact, artifact_id=f"cal_{canonical_sha256(wire)[:24]}")
