"""v7 corridor contracts: v6 rules + geometry↔vision modality conflict."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from v6_claims import RobotClaimV2, distinct_capture_roots
from v6_contracts import (
    CorridorContract,
    GateDecision,
    evaluate_corridor_contract,
    filter_contract_claims,
)
from v7_vision_claims import VISION_MODALITY

GEOMETRY_MODALITIES = frozenset(
    {
        "depth_geometry",
        "simulated_semantic_sensor",
        "learned_rgbd_semantic",
    }
)
VISION_MODALITIES = frozenset({VISION_MODALITY})


@dataclass(frozen=True, slots=True)
class CorridorContractV7(CorridorContract):
    """Extends v6 contract with vision requirements."""

    require_vision_clear_root: bool = False
    enforce_modality_conflict: bool = True


def _values_by_class(
    claims: Sequence[RobotClaimV2],
) -> tuple[set[str], set[str], tuple[str, ...], tuple[str, ...]]:
    geo = [c for c in claims if c.modality in GEOMETRY_MODALITIES]
    vis = [c for c in claims if c.modality in VISION_MODALITIES]
    geo_vals = {c.value for c in geo if c.value != "inconclusive"}
    vis_vals = {c.value for c in vis if c.value != "inconclusive"}
    geo_clear_roots = distinct_capture_roots([c for c in geo if c.value == "clear"])
    vis_clear_roots = distinct_capture_roots([c for c in vis if c.value == "clear"])
    return geo_vals, vis_vals, geo_clear_roots, vis_clear_roots


def evaluate_corridor_contract_v7(
    claims: Sequence[RobotClaimV2],
    contract: CorridorContract | CorridorContractV7,
    *,
    current_step: int,
) -> GateDecision:
    """v6 evaluation plus modality conflict and optional vision root."""
    base = evaluate_corridor_contract(claims, contract, current_step=current_step)
    require_vision = bool(getattr(contract, "require_vision_clear_root", False))
    enforce_conflict = bool(getattr(contract, "enforce_modality_conflict", True))

    usable, _ = filter_contract_claims(claims, contract, current_step=current_step)
    geo_vals, vis_vals, _geo_roots, vis_clear_roots = _values_by_class(usable)

    gaps = list(base.belief_gaps)
    reasons = list(base.reasons)
    admitted = base.admitted

    if enforce_conflict and geo_vals and vis_vals:
        # Conflict if one modality is clear-only decisive and the other blocked.
        geo_clear = geo_vals == {"clear"}
        geo_blocked = "blocked" in geo_vals
        vis_clear = vis_vals == {"clear"}
        vis_blocked = "blocked" in vis_vals
        conflict = (geo_clear and vis_blocked) or (vis_clear and geo_blocked)
        if conflict:
            admitted = False
            reasons.append("modality_conflict")
            gaps.append(
                {
                    "schema_version": "purify.robotics.belief-gap/v1",
                    "reason": "modality_conflict",
                    "detail": f"geometry_vals={sorted(geo_vals)} vision_vals={sorted(vis_vals)}",
                }
            )

    if require_vision and len(vis_clear_roots) < 1:
        admitted = False
        reasons.append("missing_vision_root")
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "missing_vision_root",
                "detail": "policy requires at least one vision clear capture root",
            }
        )

    reasons = list(dict.fromkeys(reasons))
    if admitted:
        gaps = []
        reasons = []

    return GateDecision(
        admitted=admitted,
        corridor_id=base.corridor_id,
        reasons=tuple(reasons),
        belief_gaps=tuple(gaps),
        measurement_root_ids=base.measurement_root_ids,
        claim_count=base.claim_count,
        distinct_capture_roots=base.distinct_capture_roots,
        p_blocked=0.15 if admitted else max(base.p_blocked, 0.7),
        receipt_sha256=base.receipt_sha256 if admitted == base.admitted else base.receipt_sha256,
        valid_until_step=base.valid_until_step,
        current_step=base.current_step,
    )


__all__ = (
    "GEOMETRY_MODALITIES",
    "VISION_MODALITIES",
    "CorridorContractV7",
    "evaluate_corridor_contract_v7",
)
