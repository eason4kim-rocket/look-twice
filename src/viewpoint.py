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


DEFAULT_CANDIDATES = (
    ViewpointCandidate("left_near", (-0.6, 1.2)),
    ViewpointCandidate("left_far", (-0.2, 1.7)),
    ViewpointCandidate("right_near", (0.0, -1.2)),
    ViewpointCandidate("right_far", (0.4, -1.7)),
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
