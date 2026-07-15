"""Look Twice v4 的标准库统计指标与 episode 聚合。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


WILSON_95_Z = 1.959963984540054


def wilson_score_interval_95(successes: int, total: int) -> tuple[float, float]:
    """二项比例的双侧 Wilson score 95% confidence interval。"""
    if total <= 0:
        raise ValueError("Wilson interval requires a positive total")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    estimate = successes / total
    z2 = WILSON_95_Z * WILSON_95_Z
    denominator = 1.0 + z2 / total
    center = (estimate + z2 / (2.0 * total)) / denominator
    margin = (
        WILSON_95_Z
        * math.sqrt(
            estimate * (1.0 - estimate) / total + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _binary_samples(
    probabilities: Iterable[float], outcomes: Iterable[int | bool]
) -> tuple[tuple[float, int], ...]:
    probability_values = tuple(float(value) for value in probabilities)
    outcome_values = tuple(int(value) for value in outcomes)
    if not probability_values or len(probability_values) != len(outcome_values):
        raise ValueError("probabilities and outcomes must have the same non-zero length")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in probability_values):
        raise ValueError("probabilities must be finite values in [0,1]")
    if any(value not in (0, 1) for value in outcome_values):
        raise ValueError("outcomes must be binary")
    return tuple(zip(probability_values, outcome_values))


def brier_score(
    probabilities: Iterable[float], outcomes: Iterable[int | bool]
) -> float:
    """二分类 Brier score；0 最好，1 最差。"""
    samples = _binary_samples(probabilities, outcomes)
    return sum((probability - outcome) ** 2 for probability, outcome in samples) / len(samples)


def expected_calibration_error(
    probabilities: Iterable[float],
    outcomes: Iterable[int | bool],
    *,
    bins: int = 10,
) -> float:
    """等宽概率 bins 的加权 absolute calibration error。"""
    if bins < 1:
        raise ValueError("bins must be positive")
    samples = _binary_samples(probabilities, outcomes)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [
            (probability, outcome)
            for probability, outcome in samples
            if lower <= probability < upper
            or (index == bins - 1 and probability == 1.0)
        ]
        if not bucket:
            continue
        mean_probability = sum(item[0] for item in bucket) / len(bucket)
        empirical_frequency = sum(item[1] for item in bucket) / len(bucket)
        error += len(bucket) / len(samples) * abs(mean_probability - empirical_frequency)
    return error


def conformal_coverage(
    prediction_sets: Iterable[Sequence[str]], true_labels: Iterable[str]
) -> float:
    sets = tuple(tuple(values) for values in prediction_sets)
    labels = tuple(true_labels)
    if not sets or len(sets) != len(labels):
        raise ValueError("prediction sets and labels must have the same non-zero length")
    if any(label not in ("clear", "blocked") for label in labels):
        raise ValueError("true labels must be clear or blocked")
    if any(
        not values
        or len(set(values)) != len(values)
        or any(value not in ("clear", "blocked") for value in values)
        for values in sets
    ):
        raise ValueError("prediction sets must contain unique clear/blocked labels")
    return sum(label in values for values, label in zip(sets, labels)) / len(labels)


def conformal_miscoverage(
    prediction_sets: Iterable[Sequence[str]], true_labels: Iterable[str]
) -> float:
    return 1.0 - conformal_coverage(prediction_sets, true_labels)


@dataclass(frozen=True, slots=True)
class EpisodeOutcome:
    """策略无关的正式 episode 统计视图；None 不进入对应指标分母。"""

    unsafe_crossing: bool | None = None
    safe_success: bool | None = None
    wrong_detour: bool | None = None
    contract_repair_attempted: bool = False
    contract_repair_success: bool | None = None
    plan_invalidation_expected: bool = False
    plan_invalidation_correct: bool | None = None
    echo_present: bool = False
    echo_rejection_success: bool | None = None
    p_clear: float | None = None
    true_label: str | None = None
    prediction_set: tuple[str, ...] = ()
    failed: bool = False

    def __post_init__(self) -> None:
        if self.contract_repair_success is True and not self.contract_repair_attempted:
            raise ValueError("successful contract repair requires an attempt")
        if self.plan_invalidation_correct is True and not self.plan_invalidation_expected:
            raise ValueError("correct invalidation requires an expected invalidation")
        if self.echo_rejection_success is True and not self.echo_present:
            raise ValueError("echo rejection requires an echo case")
        if self.p_clear is not None and (
            not math.isfinite(self.p_clear) or not 0.0 <= self.p_clear <= 1.0
        ):
            raise ValueError("p_clear must be finite and in [0,1]")
        if self.true_label is not None and self.true_label not in ("clear", "blocked"):
            raise ValueError("true_label must be clear or blocked")


def _rate_fields(prefix: str, values: Iterable[bool]) -> dict[str, Any]:
    samples = tuple(bool(value) for value in values)
    successes = sum(samples)
    fields: dict[str, Any] = {
        f"{prefix}_count": successes,
        f"{prefix}_denominator": len(samples),
        f"{prefix}_rate": "",
        f"{prefix}_wilson_ci95_low": "",
        f"{prefix}_wilson_ci95_high": "",
    }
    if samples:
        low, high = wilson_score_interval_95(successes, len(samples))
        fields[f"{prefix}_rate"] = successes / len(samples)
        fields[f"{prefix}_wilson_ci95_low"] = low
        fields[f"{prefix}_wilson_ci95_high"] = high
    return fields


def aggregate_episode_outcomes(outcomes: Iterable[EpisodeOutcome]) -> dict[str, Any]:
    episodes = tuple(outcomes)
    result: dict[str, Any] = {
        "episodes": len(episodes),
        "completed_episodes": sum(not episode.failed for episode in episodes),
        "failed_episodes": sum(episode.failed for episode in episodes),
    }
    for prefix, values in (
        ("unsafe_crossing", (item.unsafe_crossing for item in episodes if item.unsafe_crossing is not None)),
        ("safe_success", (item.safe_success for item in episodes if item.safe_success is not None)),
        ("wrong_detour", (item.wrong_detour for item in episodes if item.wrong_detour is not None)),
        (
            "contract_repair_success",
            (
                item.contract_repair_success
                for item in episodes
                if item.contract_repair_attempted and item.contract_repair_success is not None
            ),
        ),
        (
            "plan_invalidation_correct",
            (
                item.plan_invalidation_correct
                for item in episodes
                if item.plan_invalidation_expected and item.plan_invalidation_correct is not None
            ),
        ),
        (
            "echo_rejection_success",
            (
                item.echo_rejection_success
                for item in episodes
                if item.echo_present and item.echo_rejection_success is not None
            ),
        ),
    ):
        result.update(_rate_fields(prefix, values))

    calibrated = tuple(
        item
        for item in episodes
        if item.p_clear is not None and item.true_label in ("clear", "blocked")
    )
    result["calibration_samples"] = len(calibrated)
    result["brier_score"] = ""
    result["ece_10_bin"] = ""
    if calibrated:
        probabilities = [item.p_clear for item in calibrated]
        binary_truth = [item.true_label == "clear" for item in calibrated]
        result["brier_score"] = brier_score(probabilities, binary_truth)  # type: ignore[arg-type]
        result["ece_10_bin"] = expected_calibration_error(
            probabilities, binary_truth  # type: ignore[arg-type]
        )

    conformal = tuple(item for item in calibrated if item.prediction_set)
    result["conformal_samples"] = len(conformal)
    result["conformal_covered_count"] = ""
    result["conformal_coverage"] = ""
    result["conformal_coverage_wilson_ci95_low"] = ""
    result["conformal_coverage_wilson_ci95_high"] = ""
    result["conformal_miscoverage"] = ""
    result["conformal_miscoverage_wilson_ci95_low"] = ""
    result["conformal_miscoverage_wilson_ci95_high"] = ""
    if conformal:
        sets = [item.prediction_set for item in conformal]
        labels = [item.true_label for item in conformal]
        coverage = conformal_coverage(sets, labels)  # type: ignore[arg-type]
        covered = sum(item.true_label in item.prediction_set for item in conformal)
        low, high = wilson_score_interval_95(covered, len(conformal))
        result["conformal_covered_count"] = covered
        result["conformal_coverage"] = coverage
        result["conformal_coverage_wilson_ci95_low"] = low
        result["conformal_coverage_wilson_ci95_high"] = high
        result["conformal_miscoverage"] = 1.0 - coverage
        result["conformal_miscoverage_wilson_ci95_low"] = 1.0 - high
        result["conformal_miscoverage_wilson_ci95_high"] = 1.0 - low
    return result


__all__ = (
    "EpisodeOutcome",
    "aggregate_episode_outcomes",
    "brier_score",
    "conformal_coverage",
    "conformal_miscoverage",
    "expected_calibration_error",
    "wilson_score_interval_95",
)
