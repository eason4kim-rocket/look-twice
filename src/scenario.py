"""Look Twice v3 的可复现连续场景随机化。"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioSample:
    """由 seed 唯一决定的一次实验世界；真值仅供仿真与评估使用。"""

    profile: str
    seed: int
    initial_blocked: bool
    obstacle_xy: tuple[float, float]
    obstacle_size: tuple[float, float, float]
    occluder_xy: tuple[float, float]
    occluder_size: tuple[float, float, float]
    dynamic_event: str
    event_delay: int
    unreachable_viewpoints: tuple[str, ...]
    noise_severity: float
    depth_noise_scale: float
    segmentation_noise_scale: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILES = (
    "static-mixed",
    "view-dependent-occlusion",
    "segmentation-degradation",
    "depth-degradation",
    "dynamic-change",
)


def sample_scenario(profile: str, seed: int) -> ScenarioSample:
    """生成配对实验场景；不同策略使用同一 profile/seed 即得到同一世界。"""
    if profile not in PROFILES:
        raise ValueError(f"Unsupported v3 profile: {profile}")
    rng = random.Random(seed)

    # 对 clear/blocked 做 seed 奇偶分层，保证每两个配对 seed 都覆盖两类真值；
    # 其余几何、事件与噪声仍由连续随机变量生成。
    rng.random()  # 保持后续随机序列与早期 v3 开发结果可比较。
    initial_blocked = bool(seed % 2)
    obstacle_xy = (rng.uniform(0.62, 0.98), rng.uniform(-0.22, 0.22))
    obstacle_size = (
        rng.uniform(0.35, 0.62),
        rng.uniform(0.35, 0.62),
        rng.uniform(0.35, 0.65),
    )
    occluder_xy = (rng.uniform(-0.12, 0.12), rng.uniform(-0.50, 0.50))
    occluder_size = (0.5, rng.uniform(0.95, 1.45), 1.0)
    noise_severity = rng.uniform(0.12, 0.32)
    depth_scale = 1.0
    segmentation_scale = 1.0
    dynamic_event = "none"
    event_delay = rng.randint(40, 75)

    if profile == "view-dependent-occlusion":
        occluder_xy = (rng.uniform(-0.18, 0.18), rng.uniform(-0.72, 0.72))
        occluder_size = (0.5, rng.uniform(1.35, 1.95), 1.0)
        noise_severity = rng.uniform(0.25, 0.48)
    elif profile == "segmentation-degradation":
        noise_severity = rng.uniform(0.48, 0.82)
        segmentation_scale = rng.uniform(1.35, 1.75)
        depth_scale = 0.55
    elif profile == "depth-degradation":
        noise_severity = rng.uniform(0.48, 0.82)
        depth_scale = rng.uniform(1.35, 1.75)
        segmentation_scale = 0.65
    elif profile == "dynamic-change":
        dynamic_event = "clears" if initial_blocked else "appears"
        noise_severity = rng.uniform(0.20, 0.45)

    # 约三分之一场景封闭一个候选点，且永不封闭全部候选点。
    candidate_names = ("left_near", "left_far", "right_near", "right_far")
    unreachable = ()
    if rng.random() < 0.34:
        unreachable = (candidate_names[rng.randrange(len(candidate_names))],)

    return ScenarioSample(
        profile=profile,
        seed=seed,
        initial_blocked=initial_blocked,
        obstacle_xy=obstacle_xy,
        obstacle_size=obstacle_size,
        occluder_xy=occluder_xy,
        occluder_size=occluder_size,
        dynamic_event=dynamic_event,
        event_delay=event_delay,
        unreachable_viewpoints=unreachable,
        noise_severity=noise_severity,
        depth_noise_scale=depth_scale,
        segmentation_noise_scale=segmentation_scale,
    )
