"""Look Twice v4 stress scenarios with a strict planner/oracle boundary.

The simulator owns :attr:`ScenarioSample.oracle_context`.  Online planners must
receive only :attr:`ScenarioSample.public_context`; that view deliberately omits
the seed, profile, world truth, future events, and realised sensor faults.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Mapping


PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "pose-calibration-drift",
    "structured-depth-dropout",
    "dynamic-change",
    "ood-severity",
)

SIMULATION_DT_SECONDS = 0.02
CALIBRATED_SEVERITY_RANGE = (0.0, 0.75)
TARGET_REGION = (0.4, 1.2, -0.4, 0.4)
SIDE_VIEWPOINTS: tuple[tuple[str, tuple[float, float]], ...] = (
    ("left_near", (-0.6, 1.2)),
    ("left_far", (-0.2, 1.7)),
    ("right_near", (0.0, -1.2)),
    ("right_far", (0.4, -1.7)),
)

# A public context is rejected before it reaches the repair planner if any of
# these keys appears at any nesting level.  Predicted degradation is allowed;
# realised degradation/noise is not.
FORBIDDEN_PLANNER_KEYS = frozenset(
    {
        "seed",
        "profile",
        "oracle",
        "oracle_context",
        "truth",
        "initial_blocked",
        "blocked_truth",
        "obstacle_xy",
        "obstacle_size",
        "fault",
        "fault_realization",
        "noise_realization",
        "realization_seed",
        "dynamic_event",
        "external_event",
        "event_step",
        "event_time_seconds",
        "future_observation",
    }
)


def _stable_seed(seed: int, namespace: str) -> int:
    payload = f"look-twice-v4:{seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _rng(seed: int, namespace: str) -> random.Random:
    return random.Random(_stable_seed(seed, namespace))


def _stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, value))


def _segment_intersects_rectangle(
    start: tuple[float, float],
    end: tuple[float, float],
    rectangle: tuple[float, float, float, float],
) -> bool:
    """Return whether a 2-D line segment crosses an axis-aligned rectangle."""
    min_x, max_x, min_y, max_y = rectangle
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    p = (-dx, dx, -dy, dy)
    q = (
        start[0] - min_x,
        max_x - start[0],
        start[1] - min_y,
        max_y - start[1],
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


def _estimate_visibility(
    viewpoint_xy: tuple[float, float],
    occluder_rectangle: tuple[float, float, float, float],
    samples_per_axis: int = 7,
) -> float:
    min_x, max_x, min_y, max_y = TARGET_REGION
    visible = 0
    total = samples_per_axis * samples_per_axis
    for x_index in range(samples_per_axis):
        x = min_x + (max_x - min_x) * (x_index + 0.5) / samples_per_axis
        for y_index in range(samples_per_axis):
            y = min_y + (max_y - min_y) * (y_index + 0.5) / samples_per_axis
            if not _segment_intersects_rectangle(
                viewpoint_xy, (x, y), occluder_rectangle
            ):
                visible += 1
    return visible / total


def _predicted_degradation(
    *, viewpoint_xy: tuple[float, float], predicted_coverage: float
) -> float:
    """Public model prior; this never uses the realised profile or noise."""
    target_xy = (0.8, 0.0)
    distance_factor = _clamp(math.dist(viewpoint_xy, target_xy) / 4.0)
    visibility_loss = 1.0 - _clamp(predicted_coverage)
    prior_severity = 0.35
    return _clamp(
        prior_severity
        * (0.35 + 0.35 * distance_factor + 0.55 * visibility_loss)
    )


@dataclass(frozen=True)
class ExternalEvent:
    """A simulator event scheduled on the absolute simulation clock."""

    kind: str
    absolute_step: int | None
    absolute_time_seconds: float | None
    from_blocked: bool
    to_blocked: bool
    clock: str = "simulation_step"
    schedule: str = "absolute"

    def is_due(self, current_step: int) -> bool:
        return self.absolute_step is not None and current_step >= self.absolute_step


@dataclass(frozen=True)
class FaultRealization:
    """Exact injected fault parameters, visible only to simulation/evaluation."""

    depth_severity: float
    semantic_severity: float
    rgb_severity: float
    shared_cause_id: str | None
    shared_occlusion_fraction: float
    evidence_echo_count: int
    semantic_lag_steps: int
    pose_drift_xy: tuple[float, float]
    pose_drift_yaw_degrees: float
    structured_depth_dropout_fraction: float
    structured_depth_dropout_band: tuple[float, float]
    outside_calibration_domain: bool
    depth_realization_seed: int
    semantic_realization_seed: int
    rgb_realization_seed: int


@dataclass(frozen=True)
class ScenarioSample:
    """A paired base world plus one profile-specific stress realization."""

    profile: str
    seed: int
    scenario_id: str
    paired_world_id: str
    initial_blocked: bool
    obstacle_xy: tuple[float, float]
    obstacle_size: tuple[float, float, float]
    occluder_xy: tuple[float, float]
    occluder_size: tuple[float, float, float]
    unreachable_viewpoints: tuple[str, ...]
    fault_realization: FaultRealization
    external_event: ExternalEvent

    @property
    def public_context(self) -> dict[str, Any]:
        """Return only state a real online planner is allowed to use."""
        half_x = self.occluder_size[0] / 2.0
        half_y = self.occluder_size[1] / 2.0
        occluder_rectangle = (
            self.occluder_xy[0] - half_x,
            self.occluder_xy[0] + half_x,
            self.occluder_xy[1] - half_y,
            self.occluder_xy[1] + half_y,
        )
        candidates: list[dict[str, Any]] = []
        unreachable = set(self.unreachable_viewpoints)
        for name, xy in SIDE_VIEWPOINTS:
            predicted_coverage = _estimate_visibility(xy, occluder_rectangle)
            predicted_degradation = _predicted_degradation(
                viewpoint_xy=xy,
                predicted_coverage=predicted_coverage,
            )
            candidates.append(
                {
                    "name": name,
                    "xy": [xy[0], xy[1]],
                    "reachable": name not in unreachable,
                    "predicted_coverage": predicted_coverage,
                    "predicted_degradation": predicted_degradation,
                    # This is a static-map route-risk prior, not an observed fault.
                    "physical_risk": 0.05 if "near" in name else 0.08,
                }
            )
        context = {
            "schema_version": "look-twice.v4.public-context/1",
            "paired_world_id": self.paired_world_id,
            "region_id": "inspection_region",
            "known_static_map": {
                "target_region": {
                    "min_x": TARGET_REGION[0],
                    "max_x": TARGET_REGION[1],
                    "min_y": TARGET_REGION[2],
                    "max_y": TARGET_REGION[3],
                },
                "occluder": {
                    "center_xy": [self.occluder_xy[0], self.occluder_xy[1]],
                    "size_xy": [self.occluder_size[0], self.occluder_size[1]],
                },
            },
            "candidate_viewpoints": candidates,
            "sensor_model": {
                "version": "v4-public-degradation-prior/1",
                "prior_severity": 0.35,
                "calibrated_severity_range": list(CALIBRATED_SEVERITY_RANGE),
            },
        }
        assert_public_context_safe(context)
        return context

    @property
    def oracle_context(self) -> dict[str, Any]:
        """Return simulator/evaluation truth.  Never pass this to a planner."""
        return {
            "schema_version": "look-twice.v4.oracle-context/1",
            "scenario_id": self.scenario_id,
            "paired_world_id": self.paired_world_id,
            "profile": self.profile,
            "seed": self.seed,
            "world_truth": {
                "initial_blocked": self.initial_blocked,
                "obstacle_xy": list(self.obstacle_xy),
                "obstacle_size": list(self.obstacle_size),
                "occluder_xy": list(self.occluder_xy),
                "occluder_size": list(self.occluder_size),
            },
            "fault_realization": asdict(self.fault_realization),
            "external_event": asdict(self.external_event),
        }

    def truth_blocked_at(self, step: int) -> bool:
        if step < 0:
            raise ValueError("step must be non-negative")
        if self.external_event.is_due(step):
            return self.external_event.to_blocked
        return self.initial_blocked

    def to_dict(self) -> dict[str, Any]:
        return {
            "public_context": self.public_context,
            "oracle_context": self.oracle_context,
        }


def assert_public_context_safe(context: Mapping[str, Any]) -> None:
    """Reject keys that could reveal truth, future events, or realised noise."""

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key).lower()
                if key in FORBIDDEN_PLANNER_KEYS:
                    raise ValueError(f"planner context contains forbidden key: {path}{key}")
                walk(child, f"{path}{key}.")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, f"{path}{index}.")

    walk(context, "")


def _base_world(seed: int) -> dict[str, Any]:
    """Sample profile-independent geometry so all policies/profiles stay paired."""
    rng = _rng(seed, "paired-base-world")
    initial_blocked = bool(seed % 2)
    obstacle_xy = (rng.uniform(0.62, 0.98), rng.uniform(-0.22, 0.22))
    obstacle_size = (
        rng.uniform(0.35, 0.62),
        rng.uniform(0.35, 0.62),
        rng.uniform(0.35, 0.65),
    )
    occluder_xy = (rng.uniform(-0.12, 0.12), rng.uniform(-0.50, 0.50))
    occluder_size = (0.5, rng.uniform(1.05, 1.65), 1.0)
    unreachable: tuple[str, ...] = ()
    if rng.random() < 0.35:
        unreachable = (SIDE_VIEWPOINTS[rng.randrange(len(SIDE_VIEWPOINTS))][0],)
    payload = json.dumps(
        {
            "seed": seed,
            "initial_blocked": initial_blocked,
            "obstacle_xy": obstacle_xy,
            "obstacle_size": obstacle_size,
            "occluder_xy": occluder_xy,
            "occluder_size": occluder_size,
            "unreachable": unreachable,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "paired_world_id": _stable_id("world", payload),
        "initial_blocked": initial_blocked,
        "obstacle_xy": obstacle_xy,
        "obstacle_size": obstacle_size,
        "occluder_xy": occluder_xy,
        "occluder_size": occluder_size,
        "unreachable_viewpoints": unreachable,
    }


def _fault_realization(profile: str, seed: int, paired_world_id: str) -> FaultRealization:
    rng = _rng(seed, f"fault:{profile}")
    depth_severity = rng.uniform(0.16, 0.34)
    semantic_severity = rng.uniform(0.16, 0.34)
    rgb_severity = rng.uniform(0.12, 0.30)
    shared_cause_id: str | None = None
    shared_occlusion_fraction = 0.0
    evidence_echo_count = 0
    semantic_lag_steps = 0
    pose_drift_xy = (0.0, 0.0)
    pose_drift_yaw_degrees = 0.0
    structured_depth_dropout_fraction = 0.0
    structured_depth_dropout_band = (0.0, 0.0)
    outside_calibration_domain = False

    if profile == "independent-noise":
        depth_severity = rng.uniform(0.20, 0.48)
        semantic_severity = rng.uniform(0.20, 0.48)
    elif profile == "shared-occlusion":
        shared_cause_id = _stable_id("shared-occlusion", paired_world_id)
        shared_occlusion_fraction = rng.uniform(0.48, 0.72)
        depth_severity = semantic_severity = rng.uniform(0.32, 0.55)
    elif profile == "evidence-echo":
        evidence_echo_count = rng.randint(2, 4)
    elif profile == "time-skew":
        semantic_lag_steps = rng.randint(3, 8)
    elif profile == "pose-calibration-drift":
        magnitude_x = rng.uniform(0.08, 0.18)
        magnitude_y = rng.uniform(0.08, 0.18)
        pose_drift_xy = (
            magnitude_x if rng.random() < 0.5 else -magnitude_x,
            magnitude_y if rng.random() < 0.5 else -magnitude_y,
        )
        yaw = rng.uniform(4.0, 10.0)
        pose_drift_yaw_degrees = yaw if rng.random() < 0.5 else -yaw
    elif profile == "structured-depth-dropout":
        structured_depth_dropout_fraction = rng.uniform(0.48, 0.78)
        center = rng.uniform(0.30, 0.70)
        width = rng.uniform(0.18, 0.32)
        structured_depth_dropout_band = (
            _clamp(center - width / 2.0),
            _clamp(center + width / 2.0),
        )
        depth_severity = rng.uniform(0.42, 0.68)
    elif profile == "dynamic-change":
        depth_severity = rng.uniform(0.18, 0.38)
        semantic_severity = rng.uniform(0.18, 0.38)
    elif profile == "ood-severity":
        depth_severity = rng.uniform(0.86, 0.98)
        semantic_severity = rng.uniform(0.86, 0.98)
        rgb_severity = rng.uniform(0.80, 0.96)
        outside_calibration_domain = True

    return FaultRealization(
        depth_severity=depth_severity,
        semantic_severity=semantic_severity,
        rgb_severity=rgb_severity,
        shared_cause_id=shared_cause_id,
        shared_occlusion_fraction=shared_occlusion_fraction,
        evidence_echo_count=evidence_echo_count,
        semantic_lag_steps=semantic_lag_steps,
        pose_drift_xy=pose_drift_xy,
        pose_drift_yaw_degrees=pose_drift_yaw_degrees,
        structured_depth_dropout_fraction=structured_depth_dropout_fraction,
        structured_depth_dropout_band=structured_depth_dropout_band,
        outside_calibration_domain=outside_calibration_domain,
        depth_realization_seed=_stable_seed(seed, f"{profile}:depth"),
        semantic_realization_seed=_stable_seed(seed, f"{profile}:semantic"),
        rgb_realization_seed=_stable_seed(seed, f"{profile}:rgb"),
    )


def _external_event(profile: str, seed: int, initial_blocked: bool) -> ExternalEvent:
    if profile != "dynamic-change":
        return ExternalEvent(
            kind="none",
            absolute_step=None,
            absolute_time_seconds=None,
            from_blocked=initial_blocked,
            to_blocked=initial_blocked,
        )
    rng = _rng(seed, "absolute-external-event")
    absolute_step = 240 + 20 * rng.randrange(0, 6)
    to_blocked = not initial_blocked
    return ExternalEvent(
        kind="obstacle_clears" if initial_blocked else "obstacle_appears",
        absolute_step=absolute_step,
        absolute_time_seconds=absolute_step * SIMULATION_DT_SECONDS,
        from_blocked=initial_blocked,
        to_blocked=to_blocked,
    )


def sample_v4_scenario(profile: str, seed: int) -> ScenarioSample:
    """Sample a deterministic v4 stress scenario.

    The base world is keyed only by ``seed``.  The stress overlay is keyed by
    ``profile`` and ``seed``, enabling paired comparisons without policy timing
    or random-number-consumption effects.
    """
    if profile not in PROFILES:
        raise ValueError(f"Unsupported v4 profile: {profile}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    base = _base_world(seed)
    scenario_id = _stable_id("scenario", f"{base['paired_world_id']}:{profile}")
    return ScenarioSample(
        profile=profile,
        seed=seed,
        scenario_id=scenario_id,
        paired_world_id=base["paired_world_id"],
        initial_blocked=base["initial_blocked"],
        obstacle_xy=base["obstacle_xy"],
        obstacle_size=base["obstacle_size"],
        occluder_xy=base["occluder_xy"],
        occluder_size=base["occluder_size"],
        unreachable_viewpoints=base["unreachable_viewpoints"],
        fault_realization=_fault_realization(profile, seed, base["paired_world_id"]),
        external_event=_external_event(profile, seed, base["initial_blocked"]),
    )


# A short alias mirrors v3's ``sample_scenario`` without changing that module.
sample_scenario = sample_v4_scenario

