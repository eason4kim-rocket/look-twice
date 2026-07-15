"""Deterministic comparison policies for Look Twice v4.

The four Python baselines consume only ``RobotClaim`` objects, one
``CalibrationArtifact``, and the current simulation step.  They never accept a
scenario sample, seed, oracle label, future observation, or realised noise.
The two Purify policies are descriptors around the Go GateReceipt: Python does
not reimplement the reference core's admission logic.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from v4_claims import RobotClaim, UNKNOWN_ROOTS
from v4_conformal import CalibrationArtifact, LABELS


POLICY_NAIVE_MAJORITY = "naive-majority"
POLICY_V3_LOGODDS = "v3-logodds"
POLICY_CONFORMAL_ONLY = "conformal-only"
POLICY_LINEAGE_ONLY = "lineage-only"
POLICY_PURIFY_PASSIVE = "purify-passive"
POLICY_PURIFY_ACTIVE = "purify-active"

POLICIES = (
    POLICY_NAIVE_MAJORITY,
    POLICY_V3_LOGODDS,
    POLICY_CONFORMAL_ONLY,
    POLICY_LINEAGE_ONLY,
    POLICY_PURIFY_PASSIVE,
    POLICY_PURIFY_ACTIVE,
)

ACTIONS = ("cross_region", "safe_fallback", "observe")
RESOLVED_VALUES = ("clear", "blocked", "unresolved")
UNRESOLVED_SET = ("clear", "blocked")
FIXED_CLEAR_THRESHOLD = 0.82
FIXED_BLOCKED_THRESHOLD = 0.18

_FORBIDDEN_GATE_KEYS = frozenset(
    {
        "oracle",
        "oracle_context",
        "truth",
        "ground_truth",
        "future_observation",
        "noise_realization",
        "fault_realization",
    }
)


@dataclass(frozen=True)
class PolicyDescriptor:
    name: str
    backend: str
    lineage_collapse: bool
    conformal_calibration: bool
    requires_go_gate: bool
    allows_repair: bool


POLICY_DESCRIPTORS: dict[str, PolicyDescriptor] = {
    POLICY_NAIVE_MAJORITY: PolicyDescriptor(
        POLICY_NAIVE_MAJORITY, "python", False, False, False, False
    ),
    POLICY_V3_LOGODDS: PolicyDescriptor(
        POLICY_V3_LOGODDS, "python", False, False, False, False
    ),
    POLICY_CONFORMAL_ONLY: PolicyDescriptor(
        POLICY_CONFORMAL_ONLY, "python", False, True, False, False
    ),
    POLICY_LINEAGE_ONLY: PolicyDescriptor(
        POLICY_LINEAGE_ONLY, "python", True, False, False, False
    ),
    POLICY_PURIFY_PASSIVE: PolicyDescriptor(
        POLICY_PURIFY_PASSIVE, "go-gate", True, True, True, False
    ),
    POLICY_PURIFY_ACTIVE: PolicyDescriptor(
        POLICY_PURIFY_ACTIVE, "go-gate", True, True, True, True
    ),
}


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    resolved_value: str
    prediction_set: tuple[str, ...]
    reason: str
    diagnostics: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"unsupported policy action: {self.action}")
        if self.resolved_value not in RESOLVED_VALUES:
            raise ValueError(f"unsupported resolved value: {self.resolved_value}")
        if not self.prediction_set or not set(self.prediction_set) <= set(LABELS):
            raise ValueError("prediction_set must contain clear and/or blocked")
        if self.action == "cross_region" and not (
            self.resolved_value == "clear" and self.prediction_set == ("clear",)
        ):
            raise ValueError("unresolved or blocked evidence cannot cross the region")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["prediction_set"] = list(self.prediction_set)
        result["diagnostics"] = dict(self.diagnostics)
        return result


@dataclass(frozen=True)
class _PreparedClaims:
    fresh: tuple[RobotClaim, ...]
    stale_ids: tuple[str, ...]
    future_ids: tuple[str, ...]
    fresh_physical: tuple[RobotClaim, ...]
    calibration_applicable: bool
    calibration_reason: str


def get_policy_descriptor(policy: str) -> PolicyDescriptor:
    try:
        return POLICY_DESCRIPTORS[policy]
    except KeyError as exc:
        raise ValueError(f"unsupported v4 policy: {policy}") from exc


def _prepare_claims(
    claims: Iterable[RobotClaim],
    calibration: CalibrationArtifact,
    current_step: int,
) -> _PreparedClaims:
    if not isinstance(calibration, CalibrationArtifact):
        raise TypeError("calibration must be a CalibrationArtifact")
    if current_step < 0:
        raise ValueError("current_step must be non-negative")
    materialised = tuple(claims)
    if any(not isinstance(claim, RobotClaim) for claim in materialised):
        raise TypeError("policies accept only RobotClaim inputs")
    ordered = tuple(sorted(materialised, key=lambda claim: claim.claim_id))
    fresh: list[RobotClaim] = []
    stale: list[str] = []
    future: list[str] = []
    for claim in ordered:
        if claim.observed_step > current_step:
            future.append(claim.claim_id)
        elif claim.valid_until_step < current_step:
            stale.append(claim.claim_id)
        else:
            fresh.append(claim)
    fresh_physical = tuple(claim for claim in fresh if claim.is_physical_measurement)

    # RobotClaim v1 has no profile or realised-noise field by design.  At this
    # baseline layer, the only applicability statement it can prove is that all
    # physical claims identify a sensor/calibration version admitted by the
    # artifact.  The full profile/range check remains in the Go Gate context.
    allowed_versions = set(calibration.sensor_versions) | {calibration.artifact_id}
    unknown_versions = sorted(
        {
            claim.calibration_id
            for claim in fresh_physical
            if claim.calibration_id not in allowed_versions
        }
    )
    calibration_applicable = bool(fresh_physical) and not unknown_versions
    if not fresh_physical:
        calibration_reason = "no_fresh_physical_evidence"
    elif unknown_versions:
        calibration_reason = "sensor_version_not_calibrated"
    else:
        calibration_reason = "applicable_by_claim_version"
    return _PreparedClaims(
        fresh=tuple(fresh),
        stale_ids=tuple(sorted(stale)),
        future_ids=tuple(sorted(future)),
        fresh_physical=fresh_physical,
        calibration_applicable=calibration_applicable,
        calibration_reason=calibration_reason,
    )


def _base_diagnostics(
    policy: str,
    prepared: _PreparedClaims,
    current_step: int,
) -> dict[str, Any]:
    return {
        "policy": policy,
        "current_step": current_step,
        "fresh_claim_ids": [claim.claim_id for claim in prepared.fresh],
        "fresh_physical_claim_ids": [
            claim.claim_id for claim in prepared.fresh_physical
        ],
        "stale_claim_ids": list(prepared.stale_ids),
        "future_claim_ids": list(prepared.future_ids),
        "calibration_applicable": prepared.calibration_applicable,
        "calibration_reason": prepared.calibration_reason,
        "oracle_inputs_used": False,
    }


def _fail_closed(
    *,
    reason: str,
    diagnostics: Mapping[str, Any],
    prediction_set: tuple[str, ...] = UNRESOLVED_SET,
) -> PolicyDecision:
    return PolicyDecision(
        action="safe_fallback",
        resolved_value="unresolved",
        prediction_set=prediction_set,
        reason=reason,
        diagnostics=diagnostics,
    )


def _decision_from_value(
    value: str,
    *,
    reason: str,
    diagnostics: Mapping[str, Any],
    prediction_set: tuple[str, ...] | None = None,
) -> PolicyDecision:
    if value == "clear":
        final_set = prediction_set or ("clear",)
        if final_set != ("clear",):
            return _fail_closed(
                reason="unresolved_prediction_set",
                diagnostics=diagnostics,
                prediction_set=final_set,
            )
        return PolicyDecision(
            "cross_region", "clear", final_set, reason, diagnostics
        )
    if value == "blocked":
        return PolicyDecision(
            "safe_fallback",
            "blocked",
            prediction_set or ("blocked",),
            reason,
            diagnostics,
        )
    return _fail_closed(
        reason=reason,
        diagnostics=diagnostics,
        prediction_set=prediction_set or UNRESOLVED_SET,
    )


def _claim_log_odds(claim: RobotClaim) -> float:
    if claim.value == "inconclusive":
        return 0.0
    confidence = min(1.0 - 1e-9, max(1e-9, claim.confidence))
    magnitude = math.log(confidence / (1.0 - confidence))
    return magnitude if claim.value == "blocked" else -magnitude


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        denominator = 1.0 + math.exp(-value)
        return 1.0 / denominator
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def _fixed_value(p_clear: float) -> str:
    if p_clear >= FIXED_CLEAR_THRESHOLD:
        return "clear"
    if p_clear <= FIXED_BLOCKED_THRESHOLD:
        return "blocked"
    return "unresolved"


def _meaningful_claims(claims: Iterable[RobotClaim]) -> tuple[RobotClaim, ...]:
    return tuple(claim for claim in claims if claim.value in LABELS)


def _naive_majority(
    prepared: _PreparedClaims, diagnostics: dict[str, Any]
) -> PolicyDecision:
    meaningful = _meaningful_claims(prepared.fresh)
    votes = {
        "clear": sum(claim.value == "clear" for claim in meaningful),
        "blocked": sum(claim.value == "blocked" for claim in meaningful),
    }
    diagnostics["votes"] = votes
    diagnostics["counted_claim_ids"] = [claim.claim_id for claim in meaningful]
    diagnostics["lineage_collapsed"] = False
    if not prepared.fresh_physical:
        return _fail_closed(reason="no_fresh_physical_evidence", diagnostics=diagnostics)
    if votes["clear"] == votes["blocked"]:
        return _fail_closed(reason="majority_tie", diagnostics=diagnostics)
    value = "clear" if votes["clear"] > votes["blocked"] else "blocked"
    return _decision_from_value(
        value, reason=f"majority_{value}", diagnostics=diagnostics
    )


def _uncollapsed_log_odds(
    prepared: _PreparedClaims, diagnostics: dict[str, Any]
) -> tuple[float, float]:
    meaningful = _meaningful_claims(prepared.fresh)
    contributions: list[dict[str, Any]] = []
    total = 0.0
    for claim in meaningful:
        contribution = _claim_log_odds(claim)
        # Static map is a context prior, never a physical measurement root.
        weight = 0.5 if claim.modality == "static_map" else 1.0
        contribution *= weight
        total += contribution
        contributions.append(
            {
                "claim_id": claim.claim_id,
                "modality": claim.modality,
                "weight": weight,
                "log_odds_blocked": contribution,
            }
        )
    p_blocked = _sigmoid(total)
    diagnostics.update(
        {
            "lineage_collapsed": False,
            "claim_contributions": contributions,
            "log_odds_blocked": total,
            "p_blocked": p_blocked,
            "p_clear": 1.0 - p_blocked,
        }
    )
    return total, 1.0 - p_blocked


def _v3_logodds(
    prepared: _PreparedClaims, diagnostics: dict[str, Any]
) -> PolicyDecision:
    if not prepared.fresh_physical:
        return _fail_closed(reason="no_fresh_physical_evidence", diagnostics=diagnostics)
    _, p_clear = _uncollapsed_log_odds(prepared, diagnostics)
    value = _fixed_value(p_clear)
    return _decision_from_value(
        value,
        reason=("fixed_threshold_" + value),
        diagnostics=diagnostics,
    )


def _prediction_set(
    p_clear: float, calibration: CalibrationArtifact
) -> tuple[str, ...]:
    scores = {"clear": 1.0 - p_clear, "blocked": p_clear}
    selected = tuple(
        label
        for label in LABELS
        if scores[label] <= calibration.class_quantiles[label] + 1e-12
    )
    return selected or UNRESOLVED_SET


def _conformal_only(
    prepared: _PreparedClaims,
    calibration: CalibrationArtifact,
    diagnostics: dict[str, Any],
) -> PolicyDecision:
    if not prepared.calibration_applicable:
        return _fail_closed(
            reason="calibration_not_applicable", diagnostics=diagnostics
        )
    _, p_clear = _uncollapsed_log_odds(prepared, diagnostics)
    prediction_set = _prediction_set(p_clear, calibration)
    diagnostics["prediction_set"] = list(prediction_set)
    diagnostics["calibration_artifact_id"] = calibration.artifact_id
    value = prediction_set[0] if len(prediction_set) == 1 else "unresolved"
    return _decision_from_value(
        value,
        reason=(
            "conformal_singleton_" + value
            if value != "unresolved"
            else "conformal_unresolved"
        ),
        diagnostics=diagnostics,
        prediction_set=prediction_set,
    )


def _deduplicate_artifacts(
    claims: Iterable[RobotClaim],
) -> tuple[tuple[RobotClaim, ...], tuple[str, ...]]:
    ordered = sorted(
        claims,
        key=lambda claim: (
            claim.artifact_sha256,
            -claim.quality,
            -claim.confidence,
            claim.claim_id,
        ),
    )
    accepted: list[RobotClaim] = []
    discounted: list[str] = []
    seen: set[str] = set()
    for claim in ordered:
        if claim.artifact_sha256 in seen:
            discounted.append(claim.claim_id)
            continue
        seen.add(claim.artifact_sha256)
        accepted.append(claim)
    return tuple(accepted), tuple(sorted(discounted))


def _lineage_log_odds(
    prepared: _PreparedClaims, diagnostics: dict[str, Any]
) -> tuple[float, float, int]:
    meaningful = _meaningful_claims(prepared.fresh)
    accepted, artifact_duplicates = _deduplicate_artifacts(meaningful)
    roots: dict[str, list[RobotClaim]] = {}
    map_claims: list[RobotClaim] = []
    unknown_root_ids: list[str] = []
    for claim in accepted:
        if claim.modality == "static_map":
            map_claims.append(claim)
            continue
        if (
            not claim.is_physical_measurement
            or claim.capture_root_id.lower() in UNKNOWN_ROOTS
            or claim.device_root_id.lower() in UNKNOWN_ROOTS
        ):
            unknown_root_ids.append(claim.claim_id)
            continue
        roots.setdefault(claim.capture_root_id, []).append(claim)

    total = 0.0
    root_contributions: list[dict[str, Any]] = []
    for root_id in sorted(roots):
        claims_in_root = sorted(roots[root_id], key=lambda claim: claim.claim_id)
        contribution = sum(_claim_log_odds(claim) for claim in claims_in_root) / len(
            claims_in_root
        )
        total += contribution
        root_contributions.append(
            {
                "measurement_root_id": root_id,
                "claim_ids": [claim.claim_id for claim in claims_in_root],
                "log_odds_blocked": contribution,
            }
        )
    map_contributions: list[dict[str, Any]] = []
    for claim in sorted(map_claims, key=lambda item: item.claim_id):
        contribution = 0.5 * _claim_log_odds(claim)
        total += contribution
        map_contributions.append(
            {"claim_id": claim.claim_id, "log_odds_blocked": contribution}
        )
    p_blocked = _sigmoid(total)
    diagnostics.update(
        {
            "lineage_collapsed": True,
            "artifact_duplicate_claim_ids": list(artifact_duplicates),
            "unknown_root_claim_ids": sorted(unknown_root_ids),
            "measurement_root_ids": sorted(roots),
            "distinct_measurement_roots": len(roots),
            "root_contributions": root_contributions,
            "static_map_prior_contributions": map_contributions,
            "log_odds_blocked": total,
            "p_blocked": p_blocked,
            "p_clear": 1.0 - p_blocked,
        }
    )
    return total, 1.0 - p_blocked, len(roots)


def _lineage_only(
    prepared: _PreparedClaims, diagnostics: dict[str, Any]
) -> PolicyDecision:
    _, p_clear, root_count = _lineage_log_odds(prepared, diagnostics)
    if root_count == 0:
        return _fail_closed(reason="no_known_physical_root", diagnostics=diagnostics)
    value = _fixed_value(p_clear)
    return _decision_from_value(
        value,
        reason=("lineage_fixed_threshold_" + value),
        diagnostics=diagnostics,
    )


def evaluate_policy(
    policy: str,
    *,
    claims: Iterable[RobotClaim],
    calibration: CalibrationArtifact,
    current_step: int,
) -> PolicyDecision:
    """Evaluate a Python baseline or fail closed until a Go receipt is supplied."""
    descriptor = get_policy_descriptor(policy)
    prepared = _prepare_claims(claims, calibration, current_step)
    diagnostics = _base_diagnostics(policy, prepared, current_step)
    if descriptor.requires_go_gate:
        diagnostics["requires_go_gate"] = True
        diagnostics["allows_repair"] = descriptor.allows_repair
        return _fail_closed(reason="go_gate_receipt_required", diagnostics=diagnostics)

    # A stale-only evidence set and a declared sensor/calibration version outside
    # the artifact cannot authorize crossing in any comparison policy.
    if not prepared.fresh_physical:
        reason = "stale_evidence" if prepared.stale_ids else "no_fresh_physical_evidence"
        return _fail_closed(reason=reason, diagnostics=diagnostics)
    if not prepared.calibration_applicable:
        return _fail_closed(
            reason="calibration_not_applicable", diagnostics=diagnostics
        )
    if policy == POLICY_NAIVE_MAJORITY:
        return _naive_majority(prepared, diagnostics)
    if policy == POLICY_V3_LOGODDS:
        return _v3_logodds(prepared, diagnostics)
    if policy == POLICY_CONFORMAL_ONLY:
        return _conformal_only(prepared, calibration, diagnostics)
    if policy == POLICY_LINEAGE_ONLY:
        return _lineage_only(prepared, diagnostics)
    raise AssertionError(f"unhandled policy descriptor: {policy}")


def _assert_gate_receipt_safe(receipt: Mapping[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key).lower()
                if key in _FORBIDDEN_GATE_KEYS:
                    raise ValueError(f"gate receipt contains forbidden key: {path}{key}")
                walk(child, f"{path}{key}.")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, f"{path}{index}.")

    walk(receipt, "")


def decision_from_gate_receipt(
    policy: str,
    *,
    gate_receipt: Mapping[str, Any],
    current_step: int,
) -> PolicyDecision:
    """Convert a Go GateReceipt to the shared policy decision without re-fusing."""
    descriptor = get_policy_descriptor(policy)
    if not descriptor.requires_go_gate:
        raise ValueError("gate receipts are only valid for Purify policies")
    if current_step < 0:
        raise ValueError("current_step must be non-negative")
    _assert_gate_receipt_safe(gate_receipt)
    prediction_set = tuple(gate_receipt.get("prediction_set", ()))
    if not prediction_set or not set(prediction_set) <= set(LABELS):
        prediction_set = UNRESOLVED_SET
    diagnostics = {
        "policy": policy,
        "backend": "go-gate",
        "receipt_id": gate_receipt.get("receipt_id"),
        "receipt_sha256": gate_receipt.get("receipt_sha256"),
        "admitted": gate_receipt.get("admitted") is True,
        "calibration_applicable": gate_receipt.get("calibration_applicable") is True,
        "valid_until_step": gate_receipt.get("valid_until_step"),
        "belief_gaps": list(gate_receipt.get("belief_gaps", ())),
        "measurement_root_ids": list(
            gate_receipt.get("measurement_root_ids", ())
        ),
        "oracle_inputs_used": False,
    }
    valid_until = gate_receipt.get("valid_until_step")
    if not isinstance(valid_until, int) or current_step > valid_until:
        return _fail_closed(reason="gate_receipt_stale", diagnostics=diagnostics)
    if gate_receipt.get("calibration_applicable") is not True:
        if descriptor.allows_repair:
            return PolicyDecision(
                "observe",
                "unresolved",
                UNRESOLVED_SET,
                "calibration_not_applicable",
                diagnostics,
            )
        return _fail_closed(
            reason="calibration_not_applicable", diagnostics=diagnostics
        )
    admitted = gate_receipt.get("admitted") is True
    if admitted and prediction_set == ("clear",):
        return PolicyDecision(
            "cross_region",
            "clear",
            prediction_set,
            "go_gate_admitted",
            diagnostics,
        )
    if admitted:
        return _fail_closed(reason="invalid_admitted_receipt", diagnostics=diagnostics)
    if descriptor.allows_repair:
        return PolicyDecision(
            "observe",
            "unresolved",
            prediction_set if len(prediction_set) > 1 else UNRESOLVED_SET,
            "go_gate_denied_repair_allowed",
            diagnostics,
        )
    return _fail_closed(
        reason="go_gate_denied_passive", diagnostics=diagnostics, prediction_set=prediction_set
    )


__all__ = (
    "POLICIES",
    "POLICY_DESCRIPTORS",
    "PolicyDecision",
    "PolicyDescriptor",
    "decision_from_gate_receipt",
    "evaluate_policy",
    "get_policy_descriptor",
)

