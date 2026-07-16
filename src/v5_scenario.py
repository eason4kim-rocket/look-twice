"""v5 paired scenarios: navigation corridor + grasp proxy object.

Oracle fields stay out of public_context. Dynamic events use absolute sim time.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Any

PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "dynamic-change",
    "time-skew",
    "manipulation-occlusion",
)

NAV_REGION = (0.55, 1.05, -0.35, 0.35)  # min_x, max_x, min_y, max_y risk slab
# Leave enough chassis clearance beyond the risk slab and its blocking object.
# With the previous x=1.35 target, a base positioned for the 0.27 m arm still
# overlapped the obstacle even after a geometrically valid side detour.
GRASP_XY = (1.80, 0.0)
GOAL_XY = (2.70, 0.0)
START_XY = (-2.0, 0.0)


def _stable_seed(seed: int, namespace: str) -> int:
    payload = f"look-twice-v5:{seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") % (2**31)


def _rng(seed: int, namespace: str) -> random.Random:
    return random.Random(_stable_seed(seed, namespace))


@dataclass(frozen=True, slots=True)
class V5ScenarioSample:
    profile: str
    seed: int
    public_context: dict[str, Any]
    oracle_context: dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return f"v5:{self.profile}:{self.seed}"

    def truth_nav_blocked_at(self, step: int) -> bool:
        initial = bool(self.oracle_context["nav_blocked_initial"])
        event = self.oracle_context.get("external_event") or {}
        if event and int(event.get("step", -1)) >= 0 and step >= int(event["step"]):
            return bool(event.get("to_blocked", initial))
        return initial

    def truth_grasp_clear_at(self, step: int) -> bool:
        occluded = bool(self.oracle_context["grasp_occluded_initial"])
        event = self.oracle_context.get("grasp_event") or {}
        if event and int(event.get("step", -1)) >= 0 and step >= int(event["step"]):
            return not bool(event.get("to_occluded", occluded))
        return not occluded

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "look-twice.scenario/v5",
            "scenario_id": self.scenario_id,
            "profile": self.profile,
            "seed": self.seed,
            "public_context": self.public_context,
            "oracle_context": self.oracle_context,
        }


def sample_v5_scenario(profile: str, seed: int) -> V5ScenarioSample:
    if profile not in PROFILES:
        raise ValueError(f"unsupported v5 profile: {profile}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative int")

    world_rng = _rng(seed, "paired-world")
    nav_blocked = bool(seed % 2)
    grasp_occluded = profile == "manipulation-occlusion" or (
        profile == "shared-occlusion" and world_rng.random() < 0.35
    )
    noise = 0.35 + 0.15 * (seed % 5) / 4.0
    if profile == "independent-noise":
        noise = 0.25 + 0.1 * (seed % 3) / 2.0

    viewpoints = [
        {
            "name": "left_near",
            "xy": [-0.4, 1.1],
            "reachable": True,
            "predicted_coverage": 0.82,
            "predicted_degradation": 0.18,
            "physical_risk": 0.05,
        },
        {
            "name": "left_far",
            "xy": [-1.2, 1.55],
            "reachable": True,
            "predicted_coverage": 0.74,
            "predicted_degradation": 0.22,
            "physical_risk": 0.08,
        },
        {
            "name": "right_near",
            "xy": [-0.4, -1.1],
            "reachable": True,
            "predicted_coverage": 0.80,
            "predicted_degradation": 0.20,
            "physical_risk": 0.05,
        },
        {
            "name": "right_far",
            "xy": [-1.2, -1.55],
            "reachable": seed % 7 != 3,
            "predicted_coverage": 0.70,
            "predicted_degradation": 0.28,
            "physical_risk": 0.10,
        },
        {
            "name": "grasp_approach",
            "xy": [1.05, 0.0],
            "reachable": True,
            "predicted_coverage": 0.88,
            "predicted_degradation": 0.15,
            "physical_risk": 0.06,
        },
    ]

    external_event: dict[str, Any] | None = None
    grasp_event: dict[str, Any] | None = None
    if profile == "dynamic-change":
        # Absolute schedule — not policy-dependent.  It is intentionally after
        # the common dual-view observation phase and before the usual boundary
        # commitment, so a boundary recapture can detect a real revision.
        external_event = {
            "step": 700 + (seed % 40),
            "to_blocked": not nav_blocked,
            "kind": "nav_slab_flip",
        }
    if profile == "manipulation-occlusion":
        grasp_event = {
            "step": 200 + (seed % 30),
            "to_occluded": False,
            "kind": "grasp_clear_late",
        }

    public = {
        "start_xy": list(START_XY),
        "goal_xy": list(GOAL_XY),
        "grasp_xy": list(GRASP_XY),
        "nav_region": list(NAV_REGION),
        "candidate_viewpoints": viewpoints,
        "known_static_map": {
            "map_version": "static-map-v5",
            "declared_noise_intensity": min(0.75, noise),
            "sensor_version": "look-twice-rgbd-v5/1",
        },
        "declared_noise_intensity": min(0.75, noise),
        "sensor_version": "look-twice-rgbd-v5/1",
        "profile_label": profile,
    }
    oracle = {
        "nav_blocked_initial": nav_blocked,
        "grasp_occluded_initial": grasp_occluded,
        "object_xy": list(GRASP_XY),
        "object_height": 0.08,
        "external_event": external_event,
        "grasp_event": grasp_event,
        "true_noise_realization": noise,
        "profile": profile,
        "seed": seed,
    }
    return V5ScenarioSample(profile, seed, public, oracle)


__all__ = (
    "PROFILES",
    "NAV_REGION",
    "GRASP_XY",
    "GOAL_XY",
    "START_XY",
    "V5ScenarioSample",
    "sample_v5_scenario",
)
