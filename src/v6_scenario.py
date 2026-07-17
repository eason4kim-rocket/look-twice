"""v6 dual-corridor warehouse worlds (carrier + scout)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any


PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "dynamic-change",
    "time-skew",
    "comm-fault",
)

CARRIER_ID = "carrier"
SCOUT_ID = "scout"
PAYLOAD_ID = "payload_loaded"

# Geometry in meters (map frame).
CORRIDOR_A = {
    "id": "corridor_a",
    "region": (0.4, 1.6, -0.55, -0.05),  # min_x,max_x,min_y,max_y
    "width": 0.95,
}
CORRIDOR_B = {
    "id": "corridor_b",
    "region": (0.4, 1.6, 0.05, 0.55),
    "width": 0.95,
}
CARRIER_START = (-2.0, 0.0)
SCOUT_START = (-1.6, 1.2)
GOAL_XY = (2.8, 0.0)
MISSION_DEADLINE = 3000


def _stable_seed(seed: int, namespace: str) -> int:
    payload = f"look-twice-v6:{seed}:{namespace}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") % (2**31)


def _rng(seed: int, namespace: str) -> random.Random:
    return random.Random(_stable_seed(seed, namespace))


def _viewpoints_for(corridor_id: str, y_sign: float) -> list[dict[str, Any]]:
    # Four side views relative to a corridor.
    base_x = [-0.3, -0.9, -0.3, -0.9]
    base_y = [0.95, 1.35, -0.95, -1.35]
    names = ["left_near", "left_far", "right_near", "right_far"]
    out = []
    for name, bx, by in zip(names, base_x, base_y):
        # Shift slightly by corridor sign so A/B views differ.
        yy = by if corridor_id == "corridor_b" else by * -1.0 if abs(by) > 0.5 else by
        if corridor_id == "corridor_a" and by > 0:
            yy = -abs(by)
        if corridor_id == "corridor_b" and by < 0:
            yy = abs(by)
        out.append(
            {
                "name": f"{corridor_id}/{name}",
                "corridor_id": corridor_id,
                "xy": [bx, yy * y_sign if False else yy],
                "reachable": True,
                "predicted_coverage": 0.78 if "near" in name else 0.70,
                "predicted_degradation": 0.18 if "near" in name else 0.26,
                "physical_risk": 0.05 if "near" in name else 0.10,
            }
        )
    return out


@dataclass(frozen=True, slots=True)
class V6ScenarioSample:
    profile: str
    seed: int
    public_context: dict[str, Any]
    oracle_context: dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return f"v6:{self.profile}:{self.seed}"

    def truth_corridor_blocked(self, corridor_id: str, step: int) -> bool:
        key = f"{corridor_id}_blocked_initial"
        initial = bool(self.oracle_context[key])
        event = self.oracle_context.get("external_event") or {}
        if (
            event
            and int(event.get("step", -1)) >= 0
            and step >= int(event["step"])
            and event.get("corridor_id") == corridor_id
        ):
            return bool(event.get("to_blocked", initial))
        return initial

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "look-twice.scenario/v6",
            "scenario_id": self.scenario_id,
            "profile": self.profile,
            "seed": self.seed,
            "public_context": self.public_context,
            "oracle_context": self.oracle_context,
        }


def sample_v6_scenario(profile: str, seed: int) -> V6ScenarioSample:
    if profile not in PROFILES:
        raise ValueError(f"unsupported v6 profile: {profile}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative int")

    world = _rng(seed, "warehouse")
    # Paired clear/blocked mix: seed parity biases corridor_a; corridor_b inverted often.
    a_blocked = bool(seed % 2)
    b_blocked = not a_blocked if seed % 5 != 0 else bool(world.random() < 0.4)
    noise = 0.30 + 0.15 * (seed % 5) / 4.0
    if profile == "independent-noise":
        noise = 0.22 + 0.1 * (seed % 3) / 2.0
    if profile == "shared-occlusion":
        noise = 0.45 + 0.1 * (seed % 3) / 2.0

    viewpoints = _viewpoints_for("corridor_a", 1.0) + _viewpoints_for("corridor_b", 1.0)
    # Make one far view occasionally unreachable.
    if seed % 7 == 3:
        viewpoints[3]["reachable"] = False

    carrier_width = 0.55
    scout_width = 0.32
    payload_width = 0.50

    external_event: dict[str, Any] | None = None
    if profile == "dynamic-change":
        flip_corridor = "corridor_a" if not a_blocked else "corridor_b"
        external_event = {
            "step": 900 + (seed % 50),
            "corridor_id": flip_corridor,
            "to_blocked": True,
            "kind": "corridor_block_appear",
        }

    comm = {
        "delay_steps": 0,
        "drop_rate": 0.0,
        "echo_fanout": 1,
        "reorder": False,
    }
    if profile == "comm-fault":
        comm = {
            "delay_steps": 15 + seed % 20,
            "drop_rate": 0.15,
            "echo_fanout": 1 + seed % 3,
            "reorder": True,
        }
    if profile == "evidence-echo":
        comm = {
            "delay_steps": 5,
            "drop_rate": 0.0,
            "echo_fanout": 100,  # stress multiplicity without new roots
            "reorder": False,
        }
    if profile == "time-skew":
        comm["delay_steps"] = 35 + seed % 10

    public = {
        "carrier_id": CARRIER_ID,
        "scout_id": SCOUT_ID,
        "payload_id": PAYLOAD_ID,
        "carrier_start_xy": list(CARRIER_START),
        "scout_start_xy": list(SCOUT_START),
        "goal_xy": list(GOAL_XY),
        "corridors": [dict(CORRIDOR_A), dict(CORRIDOR_B)],
        "candidate_viewpoints": viewpoints,
        "carrier_width": carrier_width,
        "scout_width": scout_width,
        "payload_width": payload_width,
        "mission_deadline": MISSION_DEADLINE,
        "max_observations": 6,
        "max_replans": 3,
        "evidence_age_limit": 80,
        "communication_delay_limit": 40,
        "min_distinct_capture_roots": 2,
        "declared_noise_intensity": min(0.75, noise),
        "sensor_version": "look-twice-rgbd-multi-agent-v6/1",
        "profile_label": profile,
        "communication": comm,
        "known_static_map": {
            "map_version": "static-map-v6",
            "declared_noise_intensity": min(0.75, noise),
            "sensor_version": "look-twice-rgbd-multi-agent-v6/1",
        },
    }
    oracle = {
        "corridor_a_blocked_initial": a_blocked,
        "corridor_b_blocked_initial": b_blocked,
        "external_event": external_event,
        "true_noise_realization": noise,
        "profile": profile,
        "seed": seed,
        # Oracle only — never online.
        "true_obstacle_xy": [1.0, -0.3 if a_blocked else 0.3],
    }
    return V6ScenarioSample(profile, seed, public, oracle)


__all__ = (
    "PROFILES",
    "CARRIER_ID",
    "SCOUT_ID",
    "PAYLOAD_ID",
    "MISSION_DEADLINE",
    "V6ScenarioSample",
    "sample_v6_scenario",
)
