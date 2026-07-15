"""Look Twice 的确定性 Next-Best-View 规划器。"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class Rectangle:
    min_x: float
    max_x: float
    min_y: float
    max_y: float


@dataclass(frozen=True)
class ViewpointCandidate:
    name: str
    xy: tuple[float, float]
    camera_z: float = 0.8
    target_reference_pixels: int = 800


@dataclass(frozen=True)
class ViewpointScore:
    name: str
    expected_visibility: float
    travel_cost: float
    revisit_penalty: float
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InformationGainScore:
    name: str
    expected_visibility: float
    expected_information_gain: float
    predicted_degradation: float
    travel_cost: float
    revisit_penalty: float
    reachable: bool
    utility: float

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CANDIDATES = (
    ViewpointCandidate("left_near", (-0.6, 1.2), target_reference_pixels=808),
    ViewpointCandidate("left_far", (-0.2, 1.7), target_reference_pixels=2329),
    ViewpointCandidate("right_near", (0.0, -1.2), target_reference_pixels=5163),
    ViewpointCandidate("right_far", (0.4, -1.7), target_reference_pixels=3654),
)


def _segment_intersects_rectangle(
    start: tuple[float, float],
    end: tuple[float, float],
    rectangle: Rectangle,
) -> bool:
    """Liang-Barsky 线段裁剪：判断视线是否穿过遮挡矩形。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    p = (-dx, dx, -dy, dy)
    q = (
        start[0] - rectangle.min_x,
        rectangle.max_x - start[0],
        start[1] - rectangle.min_y,
        rectangle.max_y - start[1],
    )
    lower, upper = 0.0, 1.0
    for p_value, q_value in zip(p, q):
        if abs(p_value) < 1e-12:
            if q_value < 0:
                return False
            continue
        ratio = q_value / p_value
        if p_value < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return False
    return upper > 0.02 and lower < 0.98


def estimate_visibility(
    viewpoint_xy: tuple[float, float],
    target_region: Rectangle,
    occluders: Iterable[Rectangle],
    samples_per_axis: int = 9,
) -> float:
    """向目标区域均匀发射二维射线，估计未被遮挡的区域比例。"""
    visible = 0
    total = samples_per_axis * samples_per_axis
    for ix in range(samples_per_axis):
        x = target_region.min_x + (target_region.max_x - target_region.min_x) * (
            ix + 0.5
        ) / samples_per_axis
        for iy in range(samples_per_axis):
            y = target_region.min_y + (
                target_region.max_y - target_region.min_y
            ) * (iy + 0.5) / samples_per_axis
            if not any(
                _segment_intersects_rectangle(viewpoint_xy, (x, y), occluder)
                for occluder in occluders
            ):
                visible += 1
    return visible / total


class ViewpointPlanner:
    def __init__(
        self,
        candidates: tuple[ViewpointCandidate, ...] = DEFAULT_CANDIDATES,
        travel_weight: float = 0.25,
        revisit_weight: float = 0.40,
    ) -> None:
        self.candidates = candidates
        self.travel_weight = travel_weight
        self.revisit_weight = revisit_weight

    def rank(
        self,
        *,
        current_xy: tuple[float, float],
        target_region: Rectangle,
        occluders: Iterable[Rectangle],
        visited: set[str],
    ) -> list[ViewpointScore]:
        scores = []
        for candidate in self.candidates:
            visibility = estimate_visibility(
                candidate.xy,
                target_region,
                occluders,
            )
            distance = math.dist(current_xy, candidate.xy)
            travel_cost = min(1.0, distance / 4.0)
            revisit_penalty = 1.0 if candidate.name in visited else 0.0
            score = (
                visibility
                - self.travel_weight * travel_cost
                - self.revisit_weight * revisit_penalty
            )
            scores.append(
                ViewpointScore(
                    name=candidate.name,
                    expected_visibility=visibility,
                    travel_cost=travel_cost,
                    revisit_penalty=revisit_penalty,
                    score=score,
                )
            )
        return sorted(scores, key=lambda item: (-item.score, item.name))

    def choose(
        self,
        *,
        current_xy: tuple[float, float],
        target_region: Rectangle,
        occluders: Iterable[Rectangle],
        visited: set[str],
        minimum_visibility: float = 0.15,
    ) -> tuple[Optional[ViewpointCandidate], list[ViewpointScore]]:
        ranking = self.rank(
            current_xy=current_xy,
            target_region=target_region,
            occluders=occluders,
            visited=visited,
        )
        by_name = {candidate.name: candidate for candidate in self.candidates}
        for item in ranking:
            if (
                item.name not in visited
                and item.expected_visibility >= minimum_visibility
            ):
                return by_name[item.name], ranking
        return None, ranking


def binary_entropy(probability: float) -> float:
    probability = min(1.0 - 1e-12, max(1e-12, probability))
    return -probability * math.log2(probability) - (1.0 - probability) * math.log2(
        1.0 - probability
    )


def expected_information_gain(
    prior_blocked: float,
    reliability: float,
) -> float:
    """二元对称传感器模型下，一次候选观察的期望熵下降。"""
    prior = min(1.0 - 1e-9, max(1e-9, prior_blocked))
    reliability = min(1.0 - 1e-9, max(0.5, reliability))
    p_observe_blocked = prior * reliability + (1.0 - prior) * (1.0 - reliability)
    posterior_if_blocked = prior * reliability / p_observe_blocked
    p_observe_clear = 1.0 - p_observe_blocked
    posterior_if_clear = prior * (1.0 - reliability) / p_observe_clear
    expected_posterior_entropy = (
        p_observe_blocked * binary_entropy(posterior_if_blocked)
        + p_observe_clear * binary_entropy(posterior_if_clear)
    )
    return max(0.0, binary_entropy(prior) - expected_posterior_entropy)


class InformationGainViewpointPlanner:
    """v3 NBV：以预期熵下降、移动成本、重访和传感器退化共同评分。"""

    def __init__(
        self,
        candidates: tuple[ViewpointCandidate, ...] = DEFAULT_CANDIDATES,
        travel_weight: float = 0.25,
        revisit_weight: float = 0.20,
        degradation_weight: float = 0.30,
    ) -> None:
        self.candidates = candidates
        self.travel_weight = travel_weight
        self.revisit_weight = revisit_weight
        self.degradation_weight = degradation_weight

    def rank(
        self,
        *,
        current_xy: tuple[float, float],
        target_region: Rectangle,
        occluders: Iterable[Rectangle],
        visited: set[str],
        unreachable: set[str],
        p_blocked: float,
        severity: float,
    ) -> list[InformationGainScore]:
        from sensor_noise import predict_degradation

        target_xy = (
            (target_region.min_x + target_region.max_x) / 2.0,
            (target_region.min_y + target_region.max_y) / 2.0,
        )
        scores = []
        for candidate in self.candidates:
            visibility = estimate_visibility(candidate.xy, target_region, occluders)
            target_distance = math.dist(candidate.xy, target_xy)
            degradation = predict_degradation(
                severity=severity,
                distance=target_distance,
                predicted_visibility=visibility,
            )
            reliability = 0.5 + 0.5 * visibility * (1.0 - degradation)
            information_gain = expected_information_gain(p_blocked, reliability)
            travel_cost = min(1.0, math.dist(current_xy, candidate.xy) / 4.0)
            revisit_penalty = 1.0 if candidate.name in visited else 0.0
            reachable = candidate.name not in unreachable
            utility = (
                information_gain
                - self.travel_weight * travel_cost
                - self.revisit_weight * revisit_penalty
                - self.degradation_weight * degradation
            )
            if not reachable:
                # 使用有限哨兵，保证结构化结果符合严格 JSON 标准。
                utility = -1.0e9
            scores.append(
                InformationGainScore(
                    name=candidate.name,
                    expected_visibility=visibility,
                    expected_information_gain=information_gain,
                    predicted_degradation=degradation,
                    travel_cost=travel_cost,
                    revisit_penalty=revisit_penalty,
                    reachable=reachable,
                    utility=utility,
                )
            )
        return sorted(scores, key=lambda item: (-item.utility, item.name))

    def choose(
        self,
        *,
        allow_revisit: bool = False,
        **kwargs: object,
    ) -> tuple[Optional[ViewpointCandidate], list[InformationGainScore]]:
        ranking = self.rank(**kwargs)
        candidates = {item.name: item for item in self.candidates}
        for item in ranking:
            if (
                item.reachable
                and (allow_revisit or item.name not in kwargs["visited"])
                and math.isfinite(item.utility)
            ):
                return candidates[item.name], ranking
        return None, ranking
