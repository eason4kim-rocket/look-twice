"""Heuristic cross-agent evidence repair policy (oracle-free).

NBV scoring uses only public corridor geometry and candidate coordinates.
Lateral alignment prefers same-side views of the target corridor and penalizes
cross-corridor contamination (standing beside the other lane while claiming
to inspect this one). No oracle, obstacle truth, or future images.
"""

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

# Collocated candidates within this distance (m) are deduped.
_COLLOCATE_EPS = 0.12
# Lateral scale (m) for alignment / contamination soft distances.
_LATERAL_SCALE = 0.55


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


def corridor_center_xy(
    public: Mapping[str, Any], corridor_id: str
) -> tuple[float, float] | None:
    """Public map geometry only: corridor region midpoint."""
    for corridor in public.get("corridors") or []:
        if str(corridor.get("id")) != corridor_id:
            continue
        region = corridor.get("region")
        if not region or len(region) < 4:
            return None
        cx = 0.5 * (float(region[0]) + float(region[1]))
        cy = 0.5 * (float(region[2]) + float(region[3]))
        return (cx, cy)
    return None


def lateral_alignment_metrics(
    action: EvidenceAction,
    public: Mapping[str, Any],
) -> dict[str, Any]:
    """Score how well a viewpoint sits on the target corridor's lateral side.

    alignment ∈ [0,1]: higher when view y matches target corridor y-half and
    is near the corridor centerline in y.
    contamination ∈ [0,1]: higher when the view is closer to another corridor
    than to the labeled target (cross-lane contamination risk).
    """
    if action.kind != "side_view" or not action.corridor_id:
        return {
            "alignment_score": 0.0,
            "contamination_risk": 0.0,
            "same_side": None,
            "target_center_y": None,
            "view_y": float(action.target_xy[1]) if action.target_xy else None,
            "reason": "non_side_view",
        }
    center = corridor_center_xy(public, action.corridor_id)
    if center is None:
        return {
            "alignment_score": 0.0,
            "contamination_risk": 0.0,
            "same_side": None,
            "target_center_y": None,
            "view_y": float(action.target_xy[1]),
            "reason": "missing_corridor_geometry",
        }
    cy = float(center[1])
    vy = float(action.target_xy[1])
    if abs(cy) < 1e-6:
        same_side = abs(vy) < 0.35
    else:
        same_side = (cy < 0 and vy < 0) or (cy > 0 and vy > 0)
    dist_y = abs(vy - cy)
    proximity = math.exp(-dist_y / _LATERAL_SCALE)
    if same_side:
        alignment = min(1.0, 0.40 + 0.60 * proximity)
    else:
        alignment = 0.12 * proximity

    contamination = 0.0
    nearest_other: str | None = None
    nearest_other_dy = float("inf")
    for corridor in public.get("corridors") or []:
        oid = str(corridor.get("id") or "")
        if not oid or oid == action.corridor_id:
            continue
        oc = corridor_center_xy(public, oid)
        if oc is None:
            continue
        ocy = float(oc[1])
        dy = abs(vy - ocy)
        if dy < nearest_other_dy:
            nearest_other_dy = dy
            nearest_other = oid
        if dy + 1e-6 < dist_y:
            contamination = max(
                contamination, min(1.0, 1.0 - dy / (_LATERAL_SCALE * 1.4))
            )
        elif dy < _LATERAL_SCALE:
            contamination = max(
                contamination, min(0.75, 0.55 * (1.0 - dy / _LATERAL_SCALE))
            )
    if not same_side:
        contamination = max(contamination, 0.85)

    if same_side and contamination < 0.25:
        reason = (
            f"same_side_aligned target_y={cy:.3f} view_y={vy:.3f} "
            f"align={alignment:.3f}"
        )
    elif not same_side:
        reason = (
            f"cross_side_risk target_y={cy:.3f} view_y={vy:.3f} "
            f"nearest_other={nearest_other} contam={contamination:.3f}"
        )
    else:
        reason = (
            f"partial_align target_y={cy:.3f} view_y={vy:.3f} "
            f"align={alignment:.3f} contam={contamination:.3f}"
        )
    return {
        "alignment_score": float(alignment),
        "contamination_risk": float(contamination),
        "same_side": bool(same_side),
        "target_center_y": cy,
        "view_y": vy,
        "nearest_other_corridor": nearest_other,
        "reason": reason,
    }


def _dedupe_collocated_side_views(
    actions: list[EvidenceAction],
    public: Mapping[str, Any],
) -> list[EvidenceAction]:
    """Keep at most one reachable side_view per physical XY.

    When A/B candidates share the same pose, retain the action whose corridor
    center is laterally closer to that pose (public geometry only).
    """
    side_idx = [i for i, a in enumerate(actions) if a.kind == "side_view"]
    drop: set[int] = set()
    for ii, i in enumerate(side_idx):
        if i in drop:
            continue
        a = actions[i]
        for j in side_idx[ii + 1 :]:
            if j in drop:
                continue
            b = actions[j]
            if math.dist(a.target_xy, b.target_xy) > _COLLOCATE_EPS:
                continue
            ma = lateral_alignment_metrics(a, public)
            mb = lateral_alignment_metrics(b, public)
            score_a = float(ma["alignment_score"]) - float(ma["contamination_risk"])
            score_b = float(mb["alignment_score"]) - float(mb["contamination_risk"])
            if score_a > score_b + 1e-9:
                drop.add(j)
            elif score_b > score_a + 1e-9:
                drop.add(i)
                break
            else:
                if a.name <= b.name:
                    drop.add(j)
                else:
                    drop.add(i)
                    break
    out: list[EvidenceAction] = []
    for i, a in enumerate(actions):
        if i in drop and a.kind == "side_view":
            out.append(
                EvidenceAction(
                    name=a.name,
                    kind=a.kind,
                    observer=a.observer,
                    corridor_id=a.corridor_id,
                    viewpoint=a.viewpoint,
                    target_xy=a.target_xy,
                    predicted_coverage=a.predicted_coverage,
                    predicted_degradation=a.predicted_degradation,
                    physical_risk=a.physical_risk,
                    reachable=False,
                    travel_cost=a.travel_cost,
                )
            )
        else:
            out.append(a)
    return out


def build_candidate_actions(
    public: Mapping[str, Any],
    *,
    carrier_xy: tuple[float, float],
    scout_xy: tuple[float, float],
    visited: set[str],
) -> list[EvidenceAction]:
    assert_public_planner_context(public)
    actions: list[EvidenceAction] = []
    for corridor in public["corridors"]:
        cid = str(corridor["id"])
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
    for vp in public["candidate_viewpoints"]:
        vname = str(vp["name"])
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
        already = aname in visited or vname in visited
        reachable = bool(vp.get("reachable", True)) and not already
        if math.dist(scout_xy, xy) <= 0.10:
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
    actions = _dedupe_collocated_side_views(actions, public)
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
    public: Mapping[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Public heuristic utility — no oracle.

    Returns (utility, audit) including lateral alignment scores.
    """
    audit: dict[str, Any] = {
        "alignment_score": 0.0,
        "contamination_risk": 0.0,
        "selection_reason": "base",
    }
    if not action.reachable and action.kind != "safe_fallback":
        audit["selection_reason"] = "unreachable"
        return -1.0, audit
    reasons = set(gap_reasons)
    base = 0.0
    if action.kind == "side_view":
        base = 0.85
        if "insufficient_roots" in reasons or "shared_root" in reasons:
            base += 0.35
        if "low_coverage" in reasons:
            base += 0.15 * action.predicted_coverage
        if (
            "missing_vision_root" in reasons
            or "missing_side_view_vision_root" in reasons
            or "modality_conflict" in reasons
        ):
            base += 0.45
        if action.observer == "scout":
            base += 0.20
        for r in reasons:
            if str(r).startswith("target_corridor:") and action.corridor_id:
                target = str(r).split(":", 1)[1]
                if action.corridor_id == target:
                    base += 0.55
                else:
                    base -= 0.25
            if str(r).startswith("confirmed_blocked:") and action.corridor_id:
                blocked_cid = str(r).split(":", 1)[1]
                if action.corridor_id == blocked_cid:
                    base -= 0.80
                else:
                    base += 0.40
        if public is not None:
            lat = lateral_alignment_metrics(action, public)
            audit.update(lat)
            audit["selection_reason"] = str(lat.get("reason") or "lateral")
            base += 0.85 * float(lat["alignment_score"])
            base -= 1.10 * float(lat["contamination_risk"])
            cy = lat.get("target_center_y")
            vy = lat.get("view_y")
            if cy is not None and vy is not None:
                if float(cy) < 0 and float(vy) < 0:
                    base += 0.35
                elif float(cy) > 0 and float(vy) > 0:
                    base += 0.35
                elif float(cy) * float(vy) < 0:
                    base -= 0.55
    elif action.kind == "same_view":
        base = 0.35
        if "time_skew" in reasons or "stale" in reasons:
            base += 0.25
        audit["selection_reason"] = "same_view"
    elif action.kind == "wait":
        base = 0.25
        audit["selection_reason"] = "wait"
    elif action.kind == "safe_fallback":
        base = 0.05
        audit["selection_reason"] = "safe_fallback"
    if action.name in visited:
        base -= 0.35
    base -= 0.25 * action.travel_cost
    base -= 0.30 * action.physical_risk
    base -= 0.10 * action.predicted_degradation
    return base, audit


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
        return fb, [
            {
                "action": fb.to_dict(),
                "utility": 0.05,
                "eligible": True,
                "alignment_score": 0.0,
                "contamination_risk": 0.0,
                "selection_reason": "max_observations_safe_fallback",
            }
        ]

    candidates = build_candidate_actions(
        public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=visited
    )
    ranked: list[dict[str, Any]] = []
    for action in candidates:
        util, audit = score_action(
            action, gap_reasons=gap_reasons, visited=visited, public=public
        )
        eligible = action.reachable or action.kind == "safe_fallback"
        ranked.append(
            {
                "action": action.to_dict(),
                "utility": util,
                "eligible": eligible,
                "alignment_score": audit.get("alignment_score", 0.0),
                "contamination_risk": audit.get("contamination_risk", 0.0),
                "same_side": audit.get("same_side"),
                "selection_reason": audit.get("selection_reason"),
                "target_center_y": audit.get("target_center_y"),
                "view_y": audit.get("view_y"),
            }
        )
    ranked.sort(
        key=lambda r: (
            not r["eligible"],
            -float(r["utility"]),
            -float(r.get("alignment_score") or 0.0),
            r["action"]["name"],
        )
    )
    for item in ranked:
        if item["eligible"] and float(item["utility"]) > 0.0:
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
            item["chosen"] = True
            item["selection_reason"] = (
                f"chosen_utility={item['utility']:.3f}; "
                f"{item.get('selection_reason') or ''}"
            )
            return selected, ranked
    fb = next(a for a in candidates if a.name == "safe_fallback")
    return fb, ranked


__all__ = (
    "EvidenceAction",
    "FORBIDDEN_PLANNER_KEYS",
    "assert_public_planner_context",
    "build_candidate_actions",
    "corridor_center_xy",
    "lateral_alignment_metrics",
    "score_action",
    "choose_evidence_action",
)
