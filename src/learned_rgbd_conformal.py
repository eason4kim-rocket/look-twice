"""Cluster-aware class-conditional conformal calibration for learned RGB-D."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Mapping


def finite_sample_quantile(scores: Iterable[float], alpha: float) -> float:
    values = sorted(float(value) for value in scores)
    if not values:
        raise ValueError("conformal scores cannot be empty")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values):
        raise ValueError("conformal scores must be finite probabilities")
    rank = min(len(values), math.ceil((len(values) + 1) * (1.0 - alpha)))
    return values[rank - 1]


def fit_clustered_thresholds(
    rows: Iterable[Mapping[str, float | int]], alpha: float
) -> dict[str, float]:
    """Fit per-class thresholds from each world's worst viewpoint score."""
    per_seed: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in rows:
        seed = int(row["seed"])
        label = int(row["label_blocked"])
        probability = float(row["p_blocked"])
        if label not in (0, 1) or not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("invalid calibration row")
        p_true = probability if label else 1.0 - probability
        per_seed[(seed, label)].append(1.0 - p_true)
    by_class: dict[int, list[float]] = defaultdict(list)
    for (_, label), scores in per_seed.items():
        by_class[label].append(max(scores))
    if not by_class[0] or not by_class[1]:
        raise ValueError("both classes require calibration worlds")
    return {
        "clear": finite_sample_quantile(by_class[0], alpha),
        "blocked": finite_sample_quantile(by_class[1], alpha),
        "clear_worlds": float(len(by_class[0])),
        "blocked_worlds": float(len(by_class[1])),
    }


def prediction_set(
    p_blocked: float, *, clear_threshold: float, blocked_threshold: float
) -> tuple[str, ...]:
    probability = float(p_blocked)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("p_blocked must be a finite probability")
    labels: list[str] = []
    if probability <= clear_threshold:  # 1 - p(clear) == p(blocked)
        labels.append("clear")
    if 1.0 - probability <= blocked_threshold:
        labels.append("blocked")
    return tuple(labels)


def coverage_metrics(
    rows: Iterable[Mapping[str, float | int]],
    *,
    clear_threshold: float,
    blocked_threshold: float,
) -> dict[str, float]:
    materialized = list(rows)
    if not materialized:
        raise ValueError("evaluation rows cannot be empty")
    covered = singleton = correct_singleton = empty = 0
    class_total = {0: 0, 1: 0}
    class_covered = {0: 0, 1: 0}
    sizes = 0
    for row in materialized:
        label = int(row["label_blocked"])
        expected = "blocked" if label else "clear"
        labels = prediction_set(
            float(row["p_blocked"]),
            clear_threshold=clear_threshold,
            blocked_threshold=blocked_threshold,
        )
        sizes += len(labels)
        class_total[label] += 1
        is_covered = expected in labels
        covered += int(is_covered)
        class_covered[label] += int(is_covered)
        empty += int(not labels)
        singleton += int(len(labels) == 1)
        correct_singleton += int(len(labels) == 1 and is_covered)
    n = len(materialized)
    return {
        "n": float(n),
        "coverage": covered / n,
        "clear_coverage": class_covered[0] / max(1, class_total[0]),
        "blocked_coverage": class_covered[1] / max(1, class_total[1]),
        "average_set_size": sizes / n,
        "singleton_rate": singleton / n,
        "singleton_accuracy": correct_singleton / max(1, singleton),
        "empty_rate": empty / n,
    }


__all__ = (
    "coverage_metrics",
    "finite_sample_quantile",
    "fit_clustered_thresholds",
    "prediction_set",
)
