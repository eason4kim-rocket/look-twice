"""Deterministic Purify-contract-progress next-best-view policy.

The selector is deliberately small and runtime-only.  It consumes the latest
Purify Go GateReceipt for each corridor, the effective Python/Go decisions,
public map geometry, current robot positions, and the already constructed
public candidate actions.  Its remaining inputs are online state derived from
executed observations: confirmed-blocked corridors, consumed side-view counts,
and the current observation/side budgets.  It never reads a scenario seed,
oracle state, future observation, clean segmentation, or noise realization.

Corridor choice is driven first by repair-step debt derived from the *Go*
``distinct_measurement_roots`` clause, then by calibrated ``p_blocked`` and
projected travel -- never by Python's multi-modality root count.  Root debt and
the conservative repair-step debt are emitted separately for audit.  Explicit
blocked/hard-deny states and malformed or absent receipts are fail-closed.
Once a repairable corridor is chosen, safe/adequate side views are ordered by
physical travel distance; when two roots are still needed, a two-view path is
evaluated.
"""

from __future__ import annotations

import itertools
import math
import re
from dataclasses import dataclass
from typing import Any, Collection, Mapping, Sequence

from v6_contracts import ALLOWED_EVIDENCE_ACTIONS
from v6_repair import EvidenceAction

POLICY_ARTIFACT_ID = "v8-contract-progress-nbv/1"
_GO_RECEIPT_SCHEMA = "purify.robotics.gate-receipt/v1"
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")

FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "oracle",
        "oracle_context",
        "oracle_state",
        "ground_truth",
        "truth",
        "seed",
        "scenario_seed",
        "noise_realization",
        "true_noise_realization",
        "future_image",
        "future_observation",
        "external_event",
        "retry_outcome",
        "true_obstacle_xy",
        "clean_segmentation",
    }
)

_HARD_DECISION_REASONS = frozenset(
    {
        "calibration_not_applicable",
        "evidence_conflict",
        "modality_conflict",
        "prediction_blocked",
        "purify_go_missing",
        "unknown_observer",
        "unknown_root",
    }
)
_REQUIRED_GO_CLAUSES = (
    "prediction_set",
    "evidence_age",
    "distinct_measurement_roots",
    "modality_skew",
    "unresolved_conflicts",
    "calibration_applicable",
    "scope_match",
)
_HARD_FAILED_CLAUSES = frozenset(
    {
        "evidence_age",
        "modality_skew",
        "unresolved_conflicts",
        "calibration_applicable",
        "scope_match",
    }
)
_CORRIDORS = ("corridor_a", "corridor_b")
_POSITION_EPS = 1e-6


@dataclass(frozen=True, slots=True)
class _ContractProgress:
    corridor_id: str
    roots_actual: int
    roots_required: int
    go_measurement_root_debt: int
    repair_step_debt: int
    go_p_blocked: float | None
    failed_clause_count: int
    hard_reasons: tuple[str, ...]
    receipt_sha256: str | None

    @property
    def hard_denied(self) -> bool:
        return bool(self.hard_reasons)


def _assert_no_forbidden_keys(value: Any, *, path: str) -> None:
    """Recursively reject oracle-like keys in every mapping input."""
    if isinstance(value, Mapping):
        bad = sorted(
            str(key)
            for key in value
            if str(key).strip().lower() in FORBIDDEN_RUNTIME_KEYS
        )
        if bad:
            raise ValueError(f"forbidden contract-progress input at {path}: {bad}")
        for key, child in value.items():
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _assert_corridor_key_domain(value: Mapping[str, Any], *, path: str) -> None:
    unknown = sorted(str(key) for key in value if str(key) not in _CORRIDORS)
    if unknown:
        raise ValueError(f"unknown contract-progress corridor at {path}: {unknown}")


def _validated_confirmed_blocked(value: Collection[str]) -> frozenset[str]:
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError("confirmed_blocked must be a corridor collection")
    blocked: set[str] = set()
    for corridor_id in value:
        if not isinstance(corridor_id, str) or corridor_id not in _CORRIDORS:
            raise ValueError(
                "confirmed_blocked contains an unknown contract-progress corridor"
            )
        blocked.add(corridor_id)
    return frozenset(blocked)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _finite_xy(value: Sequence[Any], *, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be an xy pair")
    xy = (float(value[0]), float(value[1]))
    if not all(math.isfinite(v) for v in xy):
        raise ValueError(f"{name} must contain finite coordinates")
    return xy


def _int_clause_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        if float(value) != float(number):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number >= 0 else None


def _decision_reasons(decision: Any) -> set[str]:
    reasons = _field(decision, "reasons", ()) or ()
    return {str(reason) for reason in reasons}


def _decision_admitted(decision: Any) -> bool:
    effective = _field(decision, "effective_admit", None)
    if effective is not None:
        return bool(effective)
    return bool(_field(decision, "admitted", False))


def _clauses_by_name(
    receipt: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    clauses = receipt.get("clauses")
    if not isinstance(clauses, (list, tuple)):
        return {}, set()
    result: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        name = str(clause.get("clause") or "")
        if not name:
            continue
        if name in result:
            duplicates.add(name)
        else:
            result[name] = clause
    return result, duplicates


def _contract_progress(
    corridor_id: str,
    *,
    receipt: Mapping[str, Any] | None,
    decision: Any,
    confirmed_blocked: Collection[str],
) -> _ContractProgress:
    hard: list[str] = []
    if corridor_id in confirmed_blocked:
        hard.append("confirmed_blocked")
    if decision is None:
        hard.append("missing_effective_decision")
    else:
        decision_cid = str(_field(decision, "corridor_id", corridor_id) or corridor_id)
        if decision_cid != corridor_id:
            hard.append("decision_scope_mismatch")
        hard.extend(sorted(_decision_reasons(decision) & _HARD_DECISION_REASONS))

    if not isinstance(receipt, Mapping):
        hard.append("missing_go_receipt")
        return _ContractProgress(
            corridor_id=corridor_id,
            roots_actual=0,
            roots_required=0,
            go_measurement_root_debt=10**6,
            repair_step_debt=10**6,
            go_p_blocked=None,
            failed_clause_count=10**6,
            hard_reasons=tuple(dict.fromkeys(hard)),
            receipt_sha256=None,
        )

    if receipt.get("schema_version") != _GO_RECEIPT_SCHEMA:
        hard.append("invalid_go_receipt_schema")
    if receipt.get("_purify_invoked") is not True:
        hard.append("go_not_invoked")
    if str(receipt.get("decision") or "").lower() == "error" or receipt.get("error"):
        hard.append("go_error")
    raw_receipt_sha256 = receipt.get("receipt_sha256")
    receipt_sha256 = (
        str(raw_receipt_sha256)
        if isinstance(raw_receipt_sha256, str)
        and _SHA256_RE.fullmatch(raw_receipt_sha256)
        else None
    )
    if receipt_sha256 is None:
        hard.append("missing_or_malformed_go_receipt_sha256")
    if receipt.get("calibration_applicable") is not True:
        hard.append("top_level_calibration_not_applicable")

    raw_p_blocked = receipt.get("p_blocked")
    go_p_blocked: float | None = None
    if isinstance(raw_p_blocked, bool) or not isinstance(raw_p_blocked, (int, float)):
        hard.append("missing_or_malformed_go_p_blocked")
    else:
        go_p_blocked = float(raw_p_blocked)
        if not math.isfinite(go_p_blocked) or not 0.0 <= go_p_blocked <= 1.0:
            hard.append("go_p_blocked_out_of_range")
            go_p_blocked = None

    scope = receipt.get("scope")
    if not isinstance(scope, Mapping):
        hard.append("missing_go_scope")
    else:
        if str(scope.get("region_id") or "") != corridor_id:
            hard.append("go_scope_region_mismatch")
        if scope.get("robot_id") != "carrier":
            hard.append("go_scope_robot_mismatch")
        if scope.get("payload_id") != "payload_loaded":
            hard.append("go_scope_payload_mismatch")

    clauses, duplicate_clauses = _clauses_by_name(receipt)
    for clause_name in _REQUIRED_GO_CLAUSES:
        if clause_name not in clauses:
            hard.append(f"missing_go_clause:{clause_name}")
            continue
        if clause_name in duplicate_clauses:
            hard.append(f"duplicate_go_clause:{clause_name}")
        passed = clauses[clause_name].get("passed")
        if not isinstance(passed, bool):
            hard.append(f"malformed_go_clause_passed:{clause_name}")
        elif passed is False and clause_name in _HARD_FAILED_CLAUSES:
            hard.append(f"go_clause_failed:{clause_name}")

    roots_clause = clauses.get("distinct_measurement_roots")
    actual = _int_clause_value(
        roots_clause.get("actual") if roots_clause is not None else None
    )
    required = _int_clause_value(
        roots_clause.get("required") if roots_clause is not None else None
    )
    if actual is None or required is None or required <= 0:
        hard.append("malformed_go_root_clause")
        actual = 0 if actual is None else actual
        required = 0 if required is None else required

    prediction_set = receipt.get("prediction_set")
    if not isinstance(prediction_set, (list, tuple, set, frozenset)):
        hard.append("missing_go_prediction_set")
        prediction_labels: set[str] = set()
    else:
        prediction_labels = {str(label) for label in prediction_set}
        if not prediction_labels or not prediction_labels <= {"clear", "blocked"}:
            hard.append("malformed_go_prediction_set")
        elif "clear" not in prediction_labels:
            hard.append("go_prediction_blocked")

    prediction_clause = clauses.get("prediction_set")
    if prediction_clause is not None:
        clause_actual = prediction_clause.get("actual")
        if isinstance(clause_actual, (list, tuple, set, frozenset)):
            clause_labels = {str(label) for label in clause_actual}
            if clause_labels != prediction_labels:
                hard.append("go_prediction_clause_mismatch")
        else:
            hard.append("malformed_go_prediction_clause")

    failed_clause_names: list[str] = []
    for name, clause in clauses.items():
        if clause.get("passed") is False:
            failed_clause_names.append(name)

    root_debt = max(0, required - actual)
    repair_step_debt = root_debt
    # A denying contract with all currently required roots can still need one
    # fresh, correctly scoped view to resolve prediction/scope/age uncertainty.
    if repair_step_debt == 0 and (
        not _decision_admitted(decision)
        or prediction_labels != {"clear"}
        or bool(failed_clause_names)
    ):
        repair_step_debt = 1

    return _ContractProgress(
        corridor_id=corridor_id,
        roots_actual=actual,
        roots_required=required,
        go_measurement_root_debt=root_debt,
        repair_step_debt=repair_step_debt,
        go_p_blocked=go_p_blocked,
        failed_clause_count=len(failed_clause_names),
        hard_reasons=tuple(dict.fromkeys(hard)),
        receipt_sha256=receipt_sha256,
    )


def _public_viewpoints(public: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for raw in public.get("candidate_viewpoints") or ():
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name") or "")
        if name:
            result[name] = raw
    return result


def _coerce_action(value: EvidenceAction | Mapping[str, Any]) -> EvidenceAction | None:
    if isinstance(value, EvidenceAction):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        return EvidenceAction(
            name=str(value.get("name") or ""),
            kind=str(value.get("kind") or ""),
            observer=str(value.get("observer") or ""),
            corridor_id=str(value.get("corridor_id") or ""),
            viewpoint=str(value.get("viewpoint") or value.get("name") or ""),
            target_xy=_finite_xy(value.get("target_xy"), name="candidate.target_xy"),
            predicted_coverage=float(value.get("predicted_coverage") or 0.0),
            predicted_degradation=float(value.get("predicted_degradation") or 0.0),
            physical_risk=float(value.get("physical_risk") or 0.0),
            reachable=bool(value.get("reachable", False)),
            travel_cost=float(value.get("travel_cost") or 0.0),
        )
    except (TypeError, ValueError, OverflowError):
        return None


def _validated_side_actions(
    candidates: Sequence[EvidenceAction | Mapping[str, Any]],
    *,
    public: Mapping[str, Any],
    min_coverage: float,
    max_physical_risk: float,
) -> tuple[list[EvidenceAction], dict[str, str]]:
    public_views = _public_viewpoints(public)
    actions: list[EvidenceAction] = []
    reject_reasons: dict[str, str] = {}
    for raw in candidates:
        action = _coerce_action(raw)
        name = str(_field(raw, "name", "") or "")
        if action is None:
            if name:
                reject_reasons[name] = "malformed_candidate"
            continue
        if (
            action.name not in ALLOWED_EVIDENCE_ACTIONS
            or action.kind != "side_view"
            or action.observer != "scout"
            or action.corridor_id not in _CORRIDORS
        ):
            reject_reasons[action.name] = "not_public_scout_side_view"
            continue
        public_view = public_views.get(action.viewpoint)
        if public_view is None:
            reject_reasons[action.name] = "viewpoint_not_in_public_geometry"
            continue
        if action.viewpoint.startswith("corridor_a/"):
            viewpoint_cid = "corridor_a"
            expected_action_name = "scout_a_" + action.viewpoint.split("/", 1)[1]
        elif action.viewpoint.startswith("corridor_b/"):
            viewpoint_cid = "corridor_b"
            expected_action_name = "scout_b_" + action.viewpoint.split("/", 1)[1]
        else:
            reject_reasons[action.name] = "malformed_public_viewpoint_scope"
            continue
        public_cid = str(public_view.get("corridor_id") or viewpoint_cid)
        if public_cid != action.corridor_id:
            reject_reasons[action.name] = "candidate_scope_mismatch"
            continue
        if viewpoint_cid != public_cid or action.name != expected_action_name:
            reject_reasons[action.name] = "candidate_name_scope_mismatch"
            continue
        try:
            public_xy = _finite_xy(public_view.get("xy"), name="public viewpoint xy")
        except (TypeError, ValueError, OverflowError):
            reject_reasons[action.name] = "malformed_public_geometry"
            continue
        if math.dist(action.target_xy, public_xy) > _POSITION_EPS:
            reject_reasons[action.name] = "candidate_geometry_mismatch"
            continue
        public_coverage = float(
            public_view.get("predicted_coverage", action.predicted_coverage)
        )
        public_risk = float(public_view.get("physical_risk", action.physical_risk))
        if not action.reachable or not bool(public_view.get("reachable", True)):
            reject_reasons[action.name] = "unreachable_or_visited"
            continue
        if not math.isfinite(public_coverage) or public_coverage < min_coverage:
            reject_reasons[action.name] = "coverage_below_floor"
            continue
        if (
            not math.isfinite(public_risk)
            or public_risk < 0.0
            or public_risk > max_physical_risk
        ):
            reject_reasons[action.name] = "physical_risk_above_limit"
            continue
        # Use the public geometry/risk/coverage values, not caller-supplied
        # alternatives, in the selected action and authorization receipt.
        actions.append(
            EvidenceAction(
                name=action.name,
                kind=action.kind,
                observer=action.observer,
                corridor_id=action.corridor_id,
                viewpoint=action.viewpoint,
                target_xy=public_xy,
                predicted_coverage=public_coverage,
                predicted_degradation=float(
                    public_view.get(
                        "predicted_degradation", action.predicted_degradation
                    )
                ),
                physical_risk=public_risk,
                reachable=True,
                travel_cost=action.travel_cost,
            )
        )
    return actions, reject_reasons


def _unique_physical_actions(actions: Sequence[EvidenceAction]) -> list[EvidenceAction]:
    unique: list[EvidenceAction] = []
    for action in sorted(actions, key=lambda item: item.name):
        if any(
            math.dist(action.target_xy, other.target_xy) <= 0.10 for other in unique
        ):
            continue
        unique.append(action)
    return unique


def _best_sequence(
    actions: Sequence[EvidenceAction],
    *,
    start_xy: tuple[float, float],
    steps: int,
) -> tuple[tuple[EvidenceAction, ...], float] | None:
    if steps <= 0:
        return ((), 0.0)
    physical = _unique_physical_actions(actions)
    if len(physical) < steps:
        return None
    ranked: list[
        tuple[float, float, float, tuple[str, ...], tuple[EvidenceAction, ...]]
    ] = []
    for sequence in itertools.permutations(physical, steps):
        cursor = start_xy
        distance = 0.0
        for action in sequence:
            distance += math.dist(cursor, action.target_xy)
            cursor = action.target_xy
        ranked.append(
            (
                distance,
                sum(action.physical_risk for action in sequence),
                -sum(action.predicted_coverage for action in sequence),
                tuple(action.name for action in sequence),
                sequence,
            )
        )
    ranked.sort(key=lambda item: item[:4])
    best = ranked[0]
    return best[4], best[0]


def _fallback_action(
    candidates: Sequence[EvidenceAction | Mapping[str, Any]],
) -> EvidenceAction | None:
    for raw in candidates:
        action = _coerce_action(raw)
        if action is not None and action.name == "safe_fallback":
            return action
    return None


def choose_contract_progress_action(
    *,
    latest_go_receipts: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Any],
    confirmed_blocked: Collection[str],
    side_obs_per_corridor: Mapping[str, int],
    public: Mapping[str, Any],
    carrier_xy: tuple[float, float],
    scout_xy: tuple[float, float],
    candidates: Sequence[EvidenceAction | Mapping[str, Any]],
    observations_taken: int,
    max_observations: int,
    max_side_per_corridor: int = 2,
    min_coverage: float = 0.65,
    max_physical_risk: float = 0.35,
) -> tuple[EvidenceAction | None, list[dict[str, Any]]]:
    """Choose a fail-closed, travel-aware contract-progress observation.

    The function is pure: it mutates none of its inputs and performs no I/O.
    Allowed runtime inputs are the latest online Go receipts/effective
    decisions, online-claim-derived ``confirmed_blocked``, public geometry and
    candidate actions, current robot positions, ``observations_taken`` /
    ``max_observations``, and ``side_obs_per_corridor`` /
    ``max_side_per_corridor``.  Coverage/risk thresholds are fixed public
    policy parameters.  The returned ranking is an audit record suitable for
    hashing into an ``EvidenceRequestReceipt``.
    """
    if not isinstance(latest_go_receipts, Mapping):
        raise ValueError("latest_go_receipts must be a mapping")
    if not isinstance(decisions, Mapping):
        raise ValueError("decisions must be a mapping")
    if not isinstance(side_obs_per_corridor, Mapping):
        raise ValueError("side_obs_per_corridor must be a mapping")
    _assert_corridor_key_domain(latest_go_receipts, path="latest_go_receipts")
    _assert_corridor_key_domain(decisions, path="decisions")
    _assert_corridor_key_domain(side_obs_per_corridor, path="side_obs_per_corridor")
    _assert_no_forbidden_keys(latest_go_receipts, path="latest_go_receipts")
    _assert_no_forbidden_keys(decisions, path="decisions")
    _assert_no_forbidden_keys(public, path="public")
    _assert_no_forbidden_keys(candidates, path="candidates")
    confirmed_blocked = _validated_confirmed_blocked(confirmed_blocked)
    carrier_xy = _finite_xy(carrier_xy, name="carrier_xy")
    scout_xy = _finite_xy(scout_xy, name="scout_xy")
    del carrier_xy  # Explicitly validated; only the scout travels for side views.

    if (
        isinstance(observations_taken, bool)
        or isinstance(max_observations, bool)
        or not isinstance(observations_taken, int)
        or not isinstance(max_observations, int)
        or observations_taken < 0
        or max_observations < 0
    ):
        raise ValueError("observation counts must be non-negative")
    if isinstance(max_side_per_corridor, bool) or not isinstance(
        max_side_per_corridor, int
    ) or max_side_per_corridor <= 0:
        raise ValueError("max_side_per_corridor must be positive")
    if not (0.0 <= min_coverage <= 1.0):
        raise ValueError("min_coverage must be in [0, 1]")
    if not (0.0 <= max_physical_risk <= 1.0):
        raise ValueError("max_physical_risk must be in [0, 1]")

    public_corridors = {
        str(item.get("id") or "")
        for item in (public.get("corridors") or ())
        if isinstance(item, Mapping)
    }
    side_actions, rejected = _validated_side_actions(
        candidates,
        public=public,
        min_coverage=min_coverage,
        max_physical_risk=max_physical_risk,
    )
    progress: dict[str, _ContractProgress] = {}
    sequences: dict[str, tuple[tuple[EvidenceAction, ...], float]] = {}
    remaining_observations = max(0, max_observations - observations_taken)

    for corridor_id in _CORRIDORS:
        receipt = latest_go_receipts.get(corridor_id)
        state = _contract_progress(
            corridor_id,
            receipt=receipt if isinstance(receipt, Mapping) else None,
            decision=decisions.get(corridor_id),
            confirmed_blocked=confirmed_blocked,
        )
        extra_hard = list(state.hard_reasons)
        if corridor_id not in public_corridors:
            extra_hard.append("corridor_not_in_public_geometry")
        side_count = _int_clause_value(side_obs_per_corridor.get(corridor_id, 0))
        if side_count is None:
            side_count = max_side_per_corridor
            extra_hard.append("malformed_side_observation_count")

        steps = state.repair_step_debt
        if steps <= 0:
            extra_hard.append("contract_already_complete")
        if steps > remaining_observations:
            extra_hard.append("insufficient_observation_budget")
        if side_count + steps > max_side_per_corridor:
            extra_hard.append("insufficient_side_view_budget")

        state = _ContractProgress(
            corridor_id=state.corridor_id,
            roots_actual=state.roots_actual,
            roots_required=state.roots_required,
            go_measurement_root_debt=state.go_measurement_root_debt,
            repair_step_debt=state.repair_step_debt,
            go_p_blocked=state.go_p_blocked,
            failed_clause_count=state.failed_clause_count,
            hard_reasons=tuple(dict.fromkeys(extra_hard)),
            receipt_sha256=state.receipt_sha256,
        )
        progress[corridor_id] = state
        if state.hard_denied:
            continue
        corridor_actions = [
            action for action in side_actions if action.corridor_id == corridor_id
        ]
        sequence = _best_sequence(
            corridor_actions,
            start_xy=scout_xy,
            steps=min(2, state.repair_step_debt),
        )
        if sequence is not None:
            sequences[corridor_id] = sequence

    corridor_order = sorted(
        sequences,
        key=lambda corridor_id: (
            progress[corridor_id].repair_step_debt,
            float(progress[corridor_id].go_p_blocked),
            sequences[corridor_id][1],
            progress[corridor_id].failed_clause_count,
            int(side_obs_per_corridor.get(corridor_id, 0)),
            corridor_id,
        ),
    )
    selected_corridor = corridor_order[0] if corridor_order else None
    selected: EvidenceAction | None = None
    selected_sequence: tuple[EvidenceAction, ...] = ()
    if selected_corridor is not None:
        selected_sequence = sequences[selected_corridor][0]
        selected = selected_sequence[0] if selected_sequence else None

    ranking: list[dict[str, Any]] = []
    for raw in candidates:
        action = _coerce_action(raw)
        if action is None or action.kind != "side_view":
            continue
        state = progress.get(action.corridor_id)
        eligible = bool(
            state is not None
            and not state.hard_denied
            and action.name not in rejected
            and action.corridor_id in sequences
        )
        sequence = sequences.get(action.corridor_id)
        projected_names = (
            [item.name for item in sequence[0]] if sequence is not None else []
        )
        current_distance = math.dist(scout_xy, action.target_xy)
        reason = rejected.get(action.name)
        if reason is None and state is not None and state.hard_denied:
            reason = "fail_closed:" + ",".join(state.hard_reasons)
        if reason is None and action.corridor_id not in sequences:
            reason = "no_feasible_contract_completion_sequence"
        if reason is None:
            reason = "eligible_contract_progress_side_view"
        item = {
            "action": action.to_dict(),
            "utility": (
                -(
                    2.0 * float(state.repair_step_debt)
                    + float(state.go_p_blocked or 0.0)
                )
                if state is not None
                else -1e9
            ),
            "eligible": eligible,
            "policy_artifact_id": POLICY_ARTIFACT_ID,
            "go_receipt_sha256": state.receipt_sha256 if state else None,
            "go_distinct_roots_actual": state.roots_actual if state else None,
            "go_distinct_roots_required": state.roots_required if state else None,
            "go_p_blocked": state.go_p_blocked if state else None,
            "go_measurement_root_debt": (
                state.go_measurement_root_debt if state else None
            ),
            "repair_step_debt": state.repair_step_debt if state else None,
            "estimated_contract_completion_debt": (
                state.repair_step_debt if state else None
            ),
            "failed_go_clause_count": state.failed_clause_count if state else None,
            "current_travel_distance": current_distance,
            "projected_sequence_distance": sequence[1] if sequence else None,
            "projected_sequence": projected_names,
            "selection_reason": reason,
        }
        if selected is not None and action.name == selected.name:
            item["chosen"] = True
            item["selection_reason"] = (
                "chosen_min_contract_debt_then_go_p_then_travel; "
                f"root_debt={state.go_measurement_root_debt}; "
                f"repair_step_debt={state.repair_step_debt}; "
                f"go_p_blocked={state.go_p_blocked:.9f}; "
                f"sequence={projected_names}; distance={sequence[1]:.6f}"
            )
        ranking.append(item)

    ranking.sort(
        key=lambda item: (
            not bool(item.get("chosen")),
            not bool(item.get("eligible")),
            0 if item["action"].get("corridor_id") == selected_corridor else 1,
            float(item.get("current_travel_distance") or math.inf),
            str(item["action"].get("name") or ""),
        )
    )

    if selected is not None:
        return selected, ranking

    fallback = _fallback_action(candidates)
    if fallback is None:
        return None, ranking
    fallback_item = {
        "action": fallback.to_dict(),
        "utility": 0.0,
        "eligible": True,
        "chosen": True,
        "policy_artifact_id": POLICY_ARTIFACT_ID,
        "go_measurement_root_debt": None,
        "repair_step_debt": None,
        "estimated_contract_completion_debt": None,
        "selection_reason": "fail_closed_no_repairable_go_contract",
        "corridor_fail_closed_reasons": {
            corridor_id: list(state.hard_reasons)
            for corridor_id, state in sorted(progress.items())
        },
    }
    return fallback, [fallback_item, *ranking]


__all__ = (
    "FORBIDDEN_RUNTIME_KEYS",
    "POLICY_ARTIFACT_ID",
    "choose_contract_progress_action",
)
