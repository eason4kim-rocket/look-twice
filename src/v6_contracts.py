"""Carrier corridor contracts + evidence-request authorization (Python gate)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import (
    SENSOR_VERSION_V6,
    RobotClaimV2,
    collapse_echo_claims,
    distinct_capture_roots,
)

CARRIER_ID = "carrier"
PAYLOAD_ID = "payload_loaded"
PREDICATE = "carrier_traversable"


@dataclass(frozen=True, slots=True)
class CorridorContract:
    corridor_id: str
    action: str = "cross_corridor"
    predicate: str = PREDICATE
    evidence_age_limit: int = 80
    min_distinct_capture_roots: int = 2
    communication_delay_limit: int = 40
    max_unresolved_conflicts: int = 0
    calibration_id: str = SENSOR_VERSION_V6
    robot_id: str = CARRIER_ID
    payload_id: str = PAYLOAD_ID

    def scope(self) -> ClaimScope:
        return ClaimScope(self.robot_id, self.payload_id, self.corridor_id)

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GateDecision:
    admitted: bool
    corridor_id: str
    reasons: tuple[str, ...]
    belief_gaps: tuple[dict[str, Any], ...]
    measurement_root_ids: tuple[str, ...]
    claim_count: int
    distinct_capture_roots: int
    p_blocked: float
    receipt_sha256: str
    valid_until_step: int
    current_step: int

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema_version": "look-twice.gate-receipt/v6",
            "admitted": self.admitted,
            "corridor_id": self.corridor_id,
            "action": "cross_corridor",
            "reasons": list(self.reasons),
            "belief_gaps": list(self.belief_gaps),
            "measurement_root_ids": list(self.measurement_root_ids),
            "claim_count": self.claim_count,
            "distinct_capture_roots": self.distinct_capture_roots,
            "p_blocked": self.p_blocked,
            "receipt_sha256": self.receipt_sha256,
            "valid_until_step": self.valid_until_step,
            "evaluated_step": self.current_step,
            "decision": "admit" if self.admitted else "deny",
        }


@dataclass(frozen=True, slots=True)
class EvidenceRequestReceipt:
    receipt_id: str
    authorized: bool
    selected_observer: str | None
    target_viewpoint: str | None
    target_fact_id: str | None
    target_scope: dict[str, str] | None
    expected_gap_repairs: tuple[str, ...]
    policy_artifact_id: str
    candidate_ranking_sha256: str
    physical_risk: float
    valid_until_step: int
    receipt_sha256: str
    reasons: tuple[str, ...] = ()

    def to_wire(self) -> dict[str, Any]:
        return {
            "schema_version": "look-twice.evidence-request-receipt/v1",
            "receipt_id": self.receipt_id,
            "authorized": self.authorized,
            "selected_observer": self.selected_observer,
            "target_viewpoint": self.target_viewpoint,
            "target_fact_id": self.target_fact_id,
            "target_scope": self.target_scope,
            "expected_gap_repairs": list(self.expected_gap_repairs),
            "policy_artifact_id": self.policy_artifact_id,
            "candidate_ranking_sha256": self.candidate_ranking_sha256,
            "physical_risk": self.physical_risk,
            "valid_until_step": self.valid_until_step,
            "receipt_sha256": self.receipt_sha256,
            "reasons": list(self.reasons),
        }


def _scope_matches(claim: RobotClaimV2, contract: CorridorContract) -> bool:
    scope = claim.scope
    return (
        scope.robot_id == contract.robot_id
        and scope.payload_id == contract.payload_id
        and scope.region_id == contract.corridor_id
        and claim.intended_actor_id == contract.robot_id
        and claim.predicate == contract.predicate
    )


def filter_contract_claims(
    claims: Sequence[RobotClaimV2],
    contract: CorridorContract,
    *,
    current_step: int,
) -> tuple[tuple[RobotClaimV2, ...], tuple[str, ...]]:
    """Return (usable claims, reject reasons accumulated)."""
    collapsed = collapse_echo_claims(claims)
    usable: list[RobotClaimV2] = []
    reasons: list[str] = []
    for claim in collapsed:
        if not _scope_matches(claim, contract):
            reasons.append("scope_mismatch")
            continue
        if claim.observer_agent_id in ("", "unknown"):
            reasons.append("unknown_observer")
            continue
        if not claim.has_known_measurement_root:
            reasons.append("unknown_root")
            continue
        # Exact calibration version match — v5 ids must not authorize v6 contracts.
        if claim.calibration_id != contract.calibration_id:
            reasons.append("calibration_not_applicable")
            continue
        if not claim.is_fresh_at(current_step):
            reasons.append("stale")
            continue
        delay = max(0, claim.received_step - claim.observed_step)
        if delay > contract.communication_delay_limit:
            reasons.append("communication_delay")
            continue
        age = max(0, current_step - claim.observed_step)
        if age > contract.evidence_age_limit:
            reasons.append("evidence_age")
            continue
        usable.append(claim)
    return tuple(usable), tuple(dict.fromkeys(reasons))


# Residual deny-class gaps that block cross_corridor (fail closed).
_DENY_CLASS_REASONS = frozenset(
    {
        "insufficient_roots",
        "shared_root",
        "evidence_conflict",
        "low_coverage",
        "stale",
        "communication_delay",
        "scope_mismatch",
        "calibration_not_applicable",
        "prediction_blocked",
        "unknown_root",
        "unknown_observer",
        "evidence_age",
        "prediction_not_clear",
    }
)


def evaluate_corridor_contract(
    claims: Sequence[RobotClaimV2],
    contract: CorridorContract,
    *,
    current_step: int,
) -> GateDecision:
    usable, reject_reasons = filter_contract_claims(
        claims, contract, current_step=current_step
    )
    clear_claims = tuple(c for c in usable if c.value == "clear")
    blocked_claims = tuple(c for c in usable if c.value == "blocked")
    # Contract prediction_set must be {clear}: only *clear* capture roots count.
    clear_roots = distinct_capture_roots(clear_claims)
    values = [c.value for c in usable]
    clear_n = len(clear_claims)
    blocked_n = len(blocked_claims)
    conflicts = 1 if clear_n > 0 and blocked_n > 0 else 0
    decisive = {v for v in values if v != "inconclusive"}

    gaps: list[dict[str, Any]] = []
    reasons: list[str] = list(reject_reasons)

    if len(clear_roots) < contract.min_distinct_capture_roots:
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "insufficient_roots",
                "detail": (
                    f"need>={contract.min_distinct_capture_roots} clear roots "
                    f"got {len(clear_roots)}"
                ),
            }
        )
        reasons.append("insufficient_roots")
    if conflicts > contract.max_unresolved_conflicts:
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "evidence_conflict",
                "detail": "clear and blocked both present",
            }
        )
        reasons.append("evidence_conflict")
    # Shared-root style among clear support.
    if (
        clear_n > max(1, len(clear_roots))
        and len(clear_roots) < contract.min_distinct_capture_roots
    ):
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "shared_root",
                "detail": "clear claim multiplicity exceeds independent clear roots",
            }
        )
        reasons.append("shared_root")
    # Coverage quality of clear support only (inconclusives do not pad quality).
    low_cov = (not clear_claims) or any(
        c.visibility < 0.35 or c.quality < 0.35 for c in clear_claims
    )
    if low_cov:
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "low_coverage",
                "detail": "clear evidence thin, empty, or low quality/visibility",
            }
        )
        reasons.append("low_coverage")
    # prediction_set must be exactly {clear} among decisive (non-inconclusive) values.
    if decisive and decisive != {"clear"}:
        gaps.append(
            {
                "schema_version": "purify.robotics.belief-gap/v1",
                "reason": "prediction_not_clear",
                "detail": f"decisive prediction set {sorted(decisive)} != ['clear']",
            }
        )
        reasons.append("prediction_not_clear")
    if blocked_n >= 1 and clear_n == 0:
        reasons.append("prediction_blocked")

    reasons = list(dict.fromkeys(reasons))
    # Admit only with enough *clear* independent roots, pure clear prediction set,
    # and no residual deny-class BeliefGaps.
    admitted = (
        len(clear_roots) >= contract.min_distinct_capture_roots
        and conflicts == 0
        and blocked_n == 0
        and clear_n >= contract.min_distinct_capture_roots
        and decisive == {"clear"}
        and not any(r in _DENY_CLASS_REASONS for r in reasons)
    )
    if admitted:
        # Fail-closed invariant: admit ⇒ no residual deny-class gaps/reasons.
        gaps = []
        reasons = []

    p_blocked = 0.15 if admitted else (0.85 if blocked_n else 0.55)
    body = {
        "corridor_id": contract.corridor_id,
        "admitted": admitted,
        "clear_roots": list(clear_roots),
        "step": current_step,
        "reasons": reasons,
    }
    receipt = canonical_sha256(body)
    return GateDecision(
        admitted=admitted,
        corridor_id=contract.corridor_id,
        reasons=tuple(reasons),
        belief_gaps=tuple(gaps),
        measurement_root_ids=clear_roots,
        claim_count=len(usable),
        distinct_capture_roots=len(clear_roots),
        p_blocked=p_blocked,
        receipt_sha256=receipt,
        valid_until_step=current_step + contract.evidence_age_limit,
        current_step=current_step,
    )


ALLOWED_EVIDENCE_ACTIONS = frozenset(
    {
        "carrier_recapture_corridor_a",
        "carrier_recapture_corridor_b",
        "scout_a_left_near",
        "scout_a_left_far",
        "scout_a_right_near",
        "scout_a_right_far",
        "scout_b_left_near",
        "scout_b_left_far",
        "scout_b_right_near",
        "scout_b_right_far",
        "wait_and_recapture",
        "safe_fallback",
    }
)


def authorize_evidence_request(
    *,
    belief_gaps: Sequence[str] | Sequence[Mapping[str, Any]],
    selected_action: Mapping[str, Any] | None,
    current_step: int,
    observations_taken: int,
    replans_taken: int,
    max_observations: int = 6,
    max_replans: int = 3,
    policy_artifact_id: str = "heuristic-v6/1",
    candidate_ranking: Sequence[Mapping[str, Any]] = (),
    physical_risk_limit: float = 0.35,
) -> EvidenceRequestReceipt:
    gaps: list[str] = []
    for g in belief_gaps:
        if isinstance(g, Mapping):
            gaps.append(str(g.get("reason", "unknown")))
        else:
            gaps.append(str(g))
    gaps_t = tuple(dict.fromkeys(gaps))
    ranking_sha = canonical_sha256(list(candidate_ranking))
    reasons: list[str] = []

    if observations_taken >= max_observations:
        reasons.append("max_observations_reached")
    if replans_taken >= max_replans and selected_action and str(selected_action.get("kind")) == "side_view":
        reasons.append("max_replans_reached")
    if not gaps_t:
        reasons.append("no_belief_gap")
    if selected_action is None:
        reasons.append("no_selected_action")
        body = {
            "authorized": False,
            "step": current_step,
            "reasons": reasons,
            "ranking": ranking_sha,
        }
        rid = f"evr_{canonical_sha256(body)[:20]}"
        return EvidenceRequestReceipt(
            receipt_id=rid,
            authorized=False,
            selected_observer=None,
            target_viewpoint=None,
            target_fact_id=None,
            target_scope=None,
            expected_gap_repairs=gaps_t,
            policy_artifact_id=policy_artifact_id,
            candidate_ranking_sha256=ranking_sha,
            physical_risk=0.0,
            valid_until_step=current_step + 40,
            receipt_sha256=canonical_sha256(body),
            reasons=tuple(reasons),
        )

    name = str(selected_action.get("name") or "")
    if name not in ALLOWED_EVIDENCE_ACTIONS:
        reasons.append("unknown_action")
    risk = float(selected_action.get("physical_risk") or 0.0)
    if risk > physical_risk_limit:
        reasons.append("physical_risk")
    if selected_action.get("reachable") is False:
        reasons.append("unreachable")
    # Action must address gap.
    kind = str(selected_action.get("kind") or "")
    if kind == "safe_fallback":
        # Always authorize as non-crossing fallback label.
        authorized = "max_observations_reached" not in reasons
    else:
        authorized = not reasons

    observer = str(selected_action.get("observer") or "")
    viewpoint = str(selected_action.get("viewpoint") or name)
    corridor = str(selected_action.get("corridor_id") or "")
    scope = None
    if corridor:
        scope = {
            "robot_id": CARRIER_ID,
            "payload_id": PAYLOAD_ID,
            "region_id": corridor,
        }
    body = {
        "authorized": authorized,
        "name": name,
        "observer": observer,
        "viewpoint": viewpoint,
        "step": current_step,
        "reasons": reasons,
        "ranking": ranking_sha,
        "policy": policy_artifact_id,
    }
    rid = f"evr_{canonical_sha256(body)[:20]}"
    return EvidenceRequestReceipt(
        receipt_id=rid,
        authorized=authorized,
        selected_observer=observer or None,
        target_viewpoint=viewpoint or None,
        target_fact_id=f"region:{corridor}" if corridor else None,
        target_scope=scope,
        expected_gap_repairs=gaps_t,
        policy_artifact_id=policy_artifact_id,
        candidate_ranking_sha256=ranking_sha,
        physical_risk=risk,
        valid_until_step=current_step + 40,
        receipt_sha256=canonical_sha256(body),
        reasons=tuple(reasons),
    )


__all__ = (
    "CorridorContract",
    "GateDecision",
    "EvidenceRequestReceipt",
    "ALLOWED_EVIDENCE_ACTIONS",
    "evaluate_corridor_contract",
    "filter_contract_claims",
    "authorize_evidence_request",
    "CARRIER_ID",
    "PAYLOAD_ID",
    "PREDICATE",
)
