"""Heuristic cross-agent evidence repair policy (oracle-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from v6_contracts import ALLOWED_EVIDENCE_ACTIONS


FORBIDDEN_PLANNER_KEYS = frozenset(
    {
        "oracle",
        "ground_truth",
        "truth",
        "seed",
        "noise_realization",
        "future_observation",
        "external_event",
        "true_obstacle_xy",
        "clean_segmentation",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceAction:
    name: str
    kind: str  # side_view | same_view | wait | safe_fallback
    observer: str
    corridor_id: str
    viewpoint: str
    target_xy: tuple[float, float]
    predicted_coverage: float
    predicted_degradation: float
    physical_risk: float
    reachable: bool
    travel_cost: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "observer": self.observer,
            "corridor_id": self.corridor_id,
            "viewpoint": self.viewpoint,
            "target_xy": list(self.target_xy),
            "predicted_coverage": self.predicted_coverage,
            "predicted_degradation": self.predicted_degradation,
            "physical_risk": self.physical_risk,
            "reachable": self.reachable,
            "travel_cost": self.travel_cost,
            "wait_steps": 20 if self.kind == "wait" else 0,
        }


def assert_public_planner_context(public: Mapping[str, Any]) -> None:
    bad = set(public) & FORBIDDEN_PLANNER_KEYS
    if bad:
        raise ValueError(f"planner context contains forbidden keys: {sorted(bad)}")
    nested = public.get("known_static_map")
    if isinstance(nested, Mapping):
        bad2 = set(nested) & FORBIDDEN_PLANNER_KEYS
        if bad2:
            raise ValueError(
                f"planner known_static_map contains forbidden keys: {sorted(bad2)}"
            )


def build_candidate_actions(
    public: Mapping[str, Any],
    *,
    carrier_xy: tuple[float, float],
    scout_xy: tuple[float, float],
    visited: set[str],
) -> list[EvidenceAction]:
    assert_public_planner_context(public)
    actions: list[EvidenceAction] = []
    # Carrier recapture actions
    for corridor in public["corridors"]:
        cid = str(corridor["id"])
        # Recapture slightly before corridor entry.
        region = corridor["region"]
        xy = (float(region[0]) - 0.15, 0.5 * (float(region[2]) + float(region[3])))
        name = f"carrier_recapture_{cid}"
        if name not in ALLOWED_EVIDENCE_ACTIONS:
            continue
        actions.append(
            EvidenceAction(
                name=name,
                kind="same_view",
                observer="carrier",
                corridor_id=cid,
                viewpoint=name,
                target_xy=xy,
                predicted_coverage=0.72,
                predicted_degradation=0.2,
                physical_risk=0.08,
                reachable=True,
                travel_cost=min(1.0, math.dist(carrier_xy, xy) / 4.0),
            )
        )
    # Scout side views
    for vp in public["candidate_viewpoints"]:
        vname = str(vp["name"])
        # Map corridor_a/left_near -> scout_a_left_near
        if vname.startswith("corridor_a/"):
            short = vname.split("/", 1)[1]
            aname = f"scout_a_{short}"
            observer = "scout"
            corridor_id = "corridor_a"
        elif vname.startswith("corridor_b/"):
            short = vname.split("/", 1)[1]
            aname = f"scout_b_{short}"
            observer = "scout"
            corridor_id = "corridor_b"
        else:
            continue
        if aname not in ALLOWED_EVIDENCE_ACTIONS:
            continue
        xy = (float(vp["xy"][0]), float(vp["xy"][1]))
        reachable = bool(vp.get("reachable", True)) and aname not in visited
        # Geometric revisit: already at pose.
        if math.dist(scout_xy, xy) <= 0.10 and aname in visited:
            reachable = False
        actions.append(
            EvidenceAction(
                name=aname,
                kind="side_view",
                observer=observer,
                corridor_id=corridor_id,
                viewpoint=vname,
                target_xy=xy,
                predicted_coverage=float(vp.get("predicted_coverage", 0.75)),
                predicted_degradation=float(vp.get("predicted_degradation", 0.2)),
                physical_risk=float(vp.get("physical_risk", 0.08)),
                reachable=reachable,
                travel_cost=min(1.0, math.dist(scout_xy, xy) / 4.0),
            )
        )
    actions.append(
        EvidenceAction(
            name="wait_and_recapture",
            kind="wait",
            observer="carrier",
            corridor_id="",
            viewpoint="wait_and_recapture",
            target_xy=carrier_xy,
            predicted_coverage=0.55,
            predicted_degradation=0.25,
            physical_risk=0.0,
            reachable=True,
            travel_cost=0.0,
        )
    )
    actions.append(
        EvidenceAction(
            name="safe_fallback",
            kind="safe_fallback",
            observer="carrier",
            corridor_id="",
            viewpoint="safe_fallback",
            target_xy=carrier_xy,
            predicted_coverage=0.0,
            predicted_degradation=1.0,
            physical_risk=0.0,
            reachable=True,
            travel_cost=0.0,
        )
    )
    return actions


def score_action(
    action: EvidenceAction,
    *,
    gap_reasons: Sequence[str],
    visited: set[str],
) -> float:
    """Public heuristic utility — no oracle."""
    if not action.reachable and action.kind != "safe_fallback":
        return -1.0
    reasons = set(gap_reasons)
    base = 0.0
    if action.kind == "side_view":
        base = 0.85
        if "insufficient_roots" in reasons or "shared_root" in reasons:
            base += 0.35
        if "low_coverage" in reasons:
            base += 0.15 * action.predicted_coverage
        if action.observer == "scout":
            base += 0.20  # independence preference
    elif action.kind == "same_view":
        base = 0.35
        if "time_skew" in reasons or "stale" in reasons:
            base += 0.25
    elif action.kind == "wait":
        base = 0.25
    elif action.kind == "safe_fallback":
        base = 0.05
    if action.name in visited:
        base -= 0.35
    base -= 0.25 * action.travel_cost
    base -= 0.30 * action.physical_risk
    base -= 0.10 * action.predicted_degradation
    return base


def choose_evidence_action(
    public: Mapping[str, Any],
    *,
    gap_reasons: Sequence[str],
    carrier_xy: tuple[float, float],
    scout_xy: tuple[float, float],
    visited: set[str],
    observations_taken: int,
    max_observations: int,
) -> tuple[EvidenceAction | None, list[dict[str, Any]]]:
    if observations_taken >= max_observations:
        fb = next(
            a
            for a in build_candidate_actions(
                public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=visited
            )
            if a.name == "safe_fallback"
        )
        return fb, [{"action": fb.to_dict(), "utility": 0.05, "eligible": True}]

    candidates = build_candidate_actions(
        public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=visited
    )
    ranked: list[dict[str, Any]] = []
    for action in candidates:
        util = score_action(action, gap_reasons=gap_reasons, visited=visited)
        eligible = action.reachable or action.kind == "safe_fallback"
        ranked.append(
            {
                "action": action.to_dict(),
                "utility": util,
                "eligible": eligible,
            }
        )
    ranked.sort(key=lambda r: (not r["eligible"], -float(r["utility"]), r["action"]["name"]))
    for item in ranked:
        if item["eligible"] and float(item["utility"]) > 0.0:
            # Reconstruct EvidenceAction
            ad = item["action"]
            selected = EvidenceAction(
                name=ad["name"],
                kind=ad["kind"],
                observer=ad["observer"],
                corridor_id=ad["corridor_id"],
                viewpoint=ad["viewpoint"],
                target_xy=tuple(ad["target_xy"]),
                predicted_coverage=ad["predicted_coverage"],
                predicted_degradation=ad["predicted_degradation"],
                physical_risk=ad["physical_risk"],
                reachable=ad["reachable"],
                travel_cost=ad["travel_cost"],
            )
            return selected, ranked
    # Fallback
    fb = next(a for a in candidates if a.name == "safe_fallback")
    return fb, ranked


__all__ = (
    "EvidenceAction",
    "FORBIDDEN_PLANNER_KEYS",
    "assert_public_planner_context",
    "build_candidate_actions",
    "score_action",
    "choose_evidence_action",
)
