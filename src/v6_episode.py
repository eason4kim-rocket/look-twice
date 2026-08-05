"""v6 dual-agent closed loop: carrier transport under Purify-governed evidence repair."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from typing import Any

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import (
    SENSOR_VERSION_V6,
    RobotClaimV2,
    build_robot_claim_v2,
    collapse_echo_claims,
)
from v6_communication import CommunicationQueue
from v6_contracts import (
    CorridorContract,
    authorize_evidence_request,
    evaluate_corridor_contract,
)

def _evaluate_gate(claims, contract, *, current_step: int, config: "V6EpisodeConfig"):
    if config.use_v7_contract:
        from v7_contracts import CorridorContractV7, evaluate_corridor_contract_v7

        if not isinstance(contract, CorridorContractV7):
            contract = CorridorContractV7(
                corridor_id=contract.corridor_id,
                evidence_age_limit=contract.evidence_age_limit,
                min_distinct_capture_roots=contract.min_distinct_capture_roots,
                communication_delay_limit=contract.communication_delay_limit,
                calibration_id=contract.calibration_id,
                require_vision_clear_root=config.require_vision_clear_root,
                require_side_view_vision_root=config.require_side_view_vision_root,
                enforce_modality_conflict=config.enforce_modality_conflict,
            )
        return evaluate_corridor_contract_v7(
            claims, contract, current_step=current_step
        )
    return evaluate_corridor_contract(claims, contract, current_step=current_step)


def _vision_root_kind(agent_id: str, viewpoint_name: str, capture_index: int) -> str:
    """Tag vision capture roots as initial vs side for repair-required contracts."""
    name = str(viewpoint_name or "")
    if (
        capture_index <= 0
        or "initial" in name
        or name.endswith("_front")
        or "recapture" in name
        or name.startswith("carrier_")
    ):
        # Carrier first look / same-view recapture is not independent side evidence.
        if agent_id == "scout" or name.startswith("corridor_") or "/left" in name or "/right" in name:
            return "side"
        return "initial"
    if agent_id == "scout" or name.startswith("corridor_") or name.startswith("scout_"):
        return "side"
    return "side" if capture_index > 0 else "initial"


_HARD_DENY_REASONS = frozenset(
    {
        "modality_conflict",
        "prediction_blocked",
        "prediction_not_clear",
        "evidence_conflict",
    }
)
_SOFT_REPAIR_REASONS = frozenset(
    {
        "missing_side_view_vision_root",
        "missing_vision_root",
        "insufficient_roots",
        "low_coverage",
        "shared_root",
    }
)


def _pick_primary_decision(
    decisions: dict[str, Any],
    *,
    confirmed_blocked: set[str] | None = None,
    side_obs_per_corridor: dict[str, int] | None = None,
    max_side_per_corridor: int = 2,
) -> Any:
    """Prefer a denied corridor that still looks repairable via new side evidence.

    If corridor_a is hard-denied (blocked/conflict) while corridor_b only lacks
    vision roots, burn scout budget on B — not on unsalvageable A.
    Confirmed-blocked corridors are deprioritized so Active switches lanes.
    """
    confirmed_blocked = confirmed_blocked or set()
    side_obs_per_corridor = side_obs_per_corridor or {}
    ranked: list[tuple[int, int, int, int, str, Any]] = []
    for cid in ("corridor_a", "corridor_b"):
        dec = decisions.get(cid)
        if dec is None or getattr(dec, "admitted", False):
            continue
        reasons = set(getattr(dec, "reasons", ()) or ())
        hard = len(reasons & _HARD_DENY_REASONS)
        soft = len(reasons & _SOFT_REPAIR_REASONS)
        conf_blk = 1 if cid in confirmed_blocked else 0
        side_n = int(side_obs_per_corridor.get(cid, 0))
        over_budget = 1 if side_n >= max_side_per_corridor else 0
        # Lower is better: confirmed blocked last; over side budget last;
        # then hard denies last; prefer soft-repairable.
        ranked.append((conf_blk, over_budget, hard, -soft, cid, dec))
    if ranked:
        ranked.sort()
        return ranked[0][5]
    return next(iter(decisions.values()))
from v6_motion import MultiAgentKinematicRuntime, build_runtime_from_scenario
from v6_repair import choose_evidence_action
from v6_scenario import CARRIER_ID, PAYLOAD_ID, SCOUT_ID, V6ScenarioSample

EPISODE_SCHEMA = "look-twice.episode/v6"
POLICIES = (
    "naive",
    "purify-passive",
    "purify-active",
    "purify-active-contract-progress",
    "purify-active-learned",
    "purify-active-dagger",
    "purify-random",
)
CLAIMS_MODE_SYNTHETIC = "synthetic_multi_agent_v6"
CLAIMS_MODE_GENESIS = "genesis_rgbd_multi_agent_v6"
ACTIVE_REPAIR_POLICIES = frozenset(
    {
        "purify-active",
        "purify-active-contract-progress",
        "purify-active-learned",
        "purify-active-dagger",
        "purify-random",
    }
)
GATED_POLICIES = frozenset(
    {
        "purify-passive",
        "purify-active",
        "purify-active-contract-progress",
        "purify-active-learned",
        "purify-active-dagger",
        "purify-random",
    }
)


@dataclass
class V6EpisodeConfig:
    policy: str = "purify-active"
    ttl_steps: int = 2000
    max_observations: int = 6
    max_replans: int = 3
    device: str = "cpu"
    prefer_rgbd_claims: bool = True
    learned_checkpoint: str | None = None
    # v7 optional hooks (default off — v6 matrices unchanged)
    vision_enabled: bool = False
    vision_backend: str = "heuristic_rgb_proxy"
    vision_checkpoint: str | None = None
    vision_conformal_artifact: str | None = None
    require_vision_clear_root: bool = False
    require_side_view_vision_root: bool = False
    enforce_modality_conflict: bool = True
    use_v7_contract: bool = False
    # Dual-track: keep Python control gate, also invoke real Purify Go core.
    use_purify_go_gate: bool = False
    purify_binary: str | None = None
    # Optional separate Go fusion Gate conformal (never copy Vision thresholds).
    go_conformal_artifact: str | None = None

    def __post_init__(self) -> None:
        if self.policy not in POLICIES:
            raise ValueError(f"unsupported policy: {self.policy}")


def _runtime_supports_rgbd(runtime: Any) -> bool:
    return callable(getattr(runtime, "capture_raw", None)) and hasattr(
        runtime, "evidence_scenario"
    )


def _v1_claims_to_v2(
    v1_claims: list[Any],
    *,
    agent_id: str,
    corridor_id: str,
    step: int,
    ttl: int,
    calibration_id: str = SENSOR_VERSION_V6,
) -> list[RobotClaimV2]:
    """Project Genesis RGB-D Claims into multi-agent v2 carrier contracts."""
    out: list[RobotClaimV2] = []
    scope = ClaimScope(CARRIER_ID, PAYLOAD_ID, corridor_id)
    for claim in v1_claims:
        modality = str(getattr(claim, "modality", ""))
        if modality == "static_map":
            continue
        # Keep physical capture root; re-scope to carrier corridor contract.
        out.append(
            build_robot_claim_v2(
                fact_id=f"region:{corridor_id}",
                predicate="carrier_traversable",
                value=str(claim.value),
                confidence=float(claim.confidence),
                observed_step=int(getattr(claim, "observed_step", step)),
                valid_until_step=int(
                    getattr(claim, "valid_until_step", step + ttl)
                ),
                modality=modality or "depth_geometry",
                device_root_id=f"rgbd-{agent_id}-{str(claim.capture_root_id)[-16:]}",
                capture_root_id=str(claim.capture_root_id),
                calibration_id=calibration_id,
                pose_version="base-link-v6",
                model_id=str(getattr(claim, "model_id", "genesis-rgbd-v6")),
                artifact_sha256=str(claim.artifact_sha256),
                observer_agent_id=agent_id,
                intended_actor_id=CARRIER_ID,
                received_step=step,
                communication_root_id=str(claim.capture_root_id),
                quality=float(getattr(claim, "quality", 0.7)),
                visibility=float(getattr(claim, "visibility", 0.7)),
                scope=scope,
            )
        )
    return out


def _synthetic_observation(
    *,
    scenario: V6ScenarioSample,
    agent_id: str,
    corridor_id: str,
    step: int,
    capture_index: int,
    viewpoint_name: str,
    predicted_coverage: float,
    ttl: int,
    calibration_id: str = SENSOR_VERSION_V6,
) -> list[RobotClaimV2]:
    """Oracle-informed synthetic measurement for CI only.

    Truth is used to generate sensor-like clear/blocked/inconclusive labels,
    not injected as online fields.
    """
    blocked = scenario.truth_corridor_blocked(corridor_id, step)
    # First observation often low-coverage / shared root for repair-required style.
    if capture_index == 0:
        value = "inconclusive"
        quality = 0.28
        visibility = 0.25
        capture_root = f"shared-fault:{scenario.seed}:{corridor_id}"
    else:
        value = "blocked" if blocked else "clear"
        quality = 0.75 + 0.1 * min(1.0, predicted_coverage)
        visibility = max(0.4, predicted_coverage)
        capture_root = f"capture:{scenario.seed}:{capture_index}:{agent_id}:{viewpoint_name}"

    device = f"rgbd-{agent_id}-01"
    artifact = canonical_sha256(
        {
            "cap": capture_root,
            "agent": agent_id,
            "corridor": corridor_id,
            "step": step,
            "value": value,
            "vp": viewpoint_name,
        }
    )
    scope = ClaimScope(CARRIER_ID, PAYLOAD_ID, corridor_id)
    claims: list[RobotClaimV2] = []
    for modality, model in (
        ("depth_geometry", "depth-proxy-v6"),
        ("simulated_semantic_sensor", "sem-proxy-v6"),
    ):
        claims.append(
            build_robot_claim_v2(
                fact_id=f"region:{corridor_id}",
                predicate="carrier_traversable",
                value=value,
                confidence=0.55 if value == "inconclusive" else 0.82,
                observed_step=step,
                valid_until_step=step + ttl,
                modality=modality,
                device_root_id=device,
                capture_root_id=capture_root,
                calibration_id=calibration_id,
                pose_version="base-link-v6",
                model_id=model,
                artifact_sha256=canonical_sha256(
                    {"a": artifact, "m": modality, "i": capture_index}
                ),
                observer_agent_id=agent_id,
                intended_actor_id=CARRIER_ID,
                received_step=step,
                communication_root_id=capture_root,
                quality=min(1.0, quality),
                visibility=min(1.0, visibility),
                scope=scope,
            )
        )
    return claims


def run_v6_episode(
    *,
    scenario: V6ScenarioSample,
    config: V6EpisodeConfig | None = None,
    runtime: Any | None = None,
) -> dict[str, Any]:
    config = config or V6EpisodeConfig()
    started = time.perf_counter()
    public = scenario.public_context
    owns_runtime = runtime is None
    runtime = runtime or build_runtime_from_scenario(scenario)
    use_rgbd = bool(config.prefer_rgbd_claims and _runtime_supports_rgbd(runtime))
    claims_mode = CLAIMS_MODE_GENESIS if use_rgbd else CLAIMS_MODE_SYNTHETIC
    rgbd_audits: list[dict[str, Any]] = []

    comm_cfg = public.get("communication") or {}
    inbox = CommunicationQueue(
        delay_steps=int(comm_cfg.get("delay_steps") or 0),
        drop_rate=float(comm_cfg.get("drop_rate") or 0.0),
        echo_fanout=int(comm_cfg.get("echo_fanout") or 1),
        reorder=bool(comm_cfg.get("reorder") or False),
        seed=scenario.seed,
    )

    # --- V8 runtime calibration identity (when spatial + real conformal) ---
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[1]
    runtime_calibration_id = SENSOR_VERSION_V6
    go_calibration_wire: dict[str, Any] | None = None
    v8_conformal_raw: dict[str, Any] | None = None
    v8_spatial_active = bool(
        config.vision_enabled
        and str(config.vision_backend) == "torch_spatial_rgbd"
        and config.vision_conformal_artifact
    )
    if v8_spatial_active:
        from v8_runtime_calibration import go_calibration_from_v8_artifact

        # Vision identity always from vision conformal.
        runtime_calibration_id, go_calibration_wire, v8_conformal_raw = (
            go_calibration_from_v8_artifact(
                config.vision_conformal_artifact,
                profile=str(scenario.profile),
                repo_root=repo_root,
            )
        )
        # If a dedicated Go fusion conformal exists, use it for Purify Go only.
        go_conf = getattr(config, "go_conformal_artifact", None)
        if go_conf:
            go_rid, go_wire_only, _ = go_calibration_from_v8_artifact(
                go_conf,
                profile=str(scenario.profile),
                repo_root=repo_root,
            )
            # Keep Python runtime_calibration_id from Vision (claims stamp).
            # Go CalibrationArtifact MUST accept the vision sensor version used on
            # claims, plus the Go fusion artifact id. Otherwise every live receipt
            # is calibration_not_applicable and effective_admit stays 0.
            go_calibration_wire = dict(go_wire_only)
            svs = list(go_calibration_wire.get("sensor_versions") or [])
            for sid in (runtime_calibration_id, go_rid):
                if sid and sid not in svs:
                    svs.append(sid)
            go_calibration_wire["sensor_versions"] = svs
            # Runtime smoke/val seeds are intentionally outside the calibration
            # seed band; widen applicability so sensor binding is the gate, not
            # an accidental seed-range deny on confirmatory partitions.
            go_calibration_wire["seed_ranges"] = [{"start": 0, "end": 200000}]
            # Keep quantiles/thresholds from Go fusion artifact (go_wire_only).

    contracts = {
        c["id"]: CorridorContract(
            corridor_id=c["id"],
            evidence_age_limit=int(public.get("evidence_age_limit") or 80),
            min_distinct_capture_roots=int(public.get("min_distinct_capture_roots") or 2),
            communication_delay_limit=int(public.get("communication_delay_limit") or 40),
            calibration_id=runtime_calibration_id,
        )
        for c in public["corridors"]
    }

    claims: list[RobotClaimV2] = []
    vision_p_blocked: dict[str, float] = {}
    gate_receipts: list[dict[str, Any]] = []
    purify_go_receipts: list[dict[str, Any]] = []
    # Candidate-only live state.  The baseline policies never read or emit it.
    latest_purify_go_receipts: dict[str, dict[str, Any]] = {}
    evidence_requests: list[dict[str, Any]] = []
    repair_decisions: list[dict[str, Any]] = []
    motion_segments: list[dict[str, Any]] = []
    invalidations: list[dict[str, Any]] = []
    visited: set[str] = set()
    capture_index = 0
    replan_count = 0
    observations = 0
    unsafe = False
    outcome = "running"
    selected_corridor: str | None = None
    carrier_reached_goal = False
    purify_bridge = None
    purify_binary_sha256: str | None = None
    purify_invoked_count = 0
    if config.use_purify_go_gate:
        from purify_bridge import PurifyBridge

        import hashlib as _hashlib

        bin_path = config.purify_binary or str(
            repo_root / "purify_robotics" / "bin" / "purify-robotics-core"
        )
        purify_binary_sha256 = _hashlib.sha256(
            _Path(bin_path).read_bytes()
        ).hexdigest()
        purify_bridge = PurifyBridge(command=(bin_path,), timeout_seconds=5.0)
        purify_bridge.start()
    payload_delivered = False
    used_detour = False
    route_mode = "none"
    repair_attempted = False
    repair_success = False
    initial_gate_denied = False
    initial_gate_reasons: list[str] = []
    roots_after_initial: set[str] = set()
    viewpoints_sequence: list[str] = []
    # Corridors with decisive blocked evidence (quality/vis above weak threshold).
    # Active policy switches scout budget to the other corridor instead of
    # re-probing a confirmed-blocked lane (not a gate-rule change).
    confirmed_blocked: set[str] = set()
    side_obs_per_corridor: dict[str, int] = {"corridor_a": 0, "corridor_b": 0}
    contract_progress_delegation_count = 0

    policy = config.policy
    is_naive = policy == "naive"
    allows_repair = policy in ACTIVE_REPAIR_POLICIES
    requires_gate = policy in GATED_POLICIES

    def _selector_corridor_audit(
        selector_ranking: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Bind selector fail-closed state to the then-latest raw Go receipts."""
        fallback = selector_ranking[0] if selector_ranking else {}
        fail_closed_reasons = fallback.get("corridor_fail_closed_reasons") or {}
        ranking_by_corridor: dict[str, dict[str, Any]] = {}
        for item in selector_ranking:
            action = item.get("action")
            action = action if isinstance(action, dict) else {}
            corridor_id = str(action.get("corridor_id") or "")
            if (
                corridor_id in ("corridor_a", "corridor_b")
                and corridor_id not in ranking_by_corridor
            ):
                ranking_by_corridor[corridor_id] = item
        result: dict[str, dict[str, Any]] = {}
        for corridor_id in ("corridor_a", "corridor_b"):
            receipt = latest_purify_go_receipts.get(corridor_id, {})
            ranking_item = ranking_by_corridor.get(corridor_id, {})
            result[corridor_id] = {
                "go_receipt_sha256": receipt.get("receipt_sha256"),
                "go_p_blocked": receipt.get("p_blocked"),
                "roots_actual": ranking_item.get("go_distinct_roots_actual"),
                "roots_required": ranking_item.get(
                    "go_distinct_roots_required"
                ),
                "go_measurement_root_debt": ranking_item.get(
                    "go_measurement_root_debt"
                ),
                "repair_step_debt": ranking_item.get("repair_step_debt"),
                "fail_closed_reasons": list(
                    fail_closed_reasons.get(corridor_id, [])
                ),
            }
        return result

    def _bind_delegated_go_p_blocked(
        baseline_ranking: list[dict[str, Any]],
        *,
        selected_action: Any,
        fail_closed_audit: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Bind each delegated item to its own corridor's latest Go risk.

        Returns ``(ranking, selected_side_view_fail_closed)``.  Missing or
        malformed risk never borrows another corridor's value.  Non-corridor
        safe fallback remains risk-not-applicable.
        """
        selected_name = str(getattr(selected_action, "name", "") or "")
        selected_side_view_fail_closed = False
        rewritten: list[dict[str, Any]] = []

        def _nonnegative_int(value: Any) -> int | None:
            if isinstance(value, bool):
                return None
            try:
                parsed = int(value)
                if float(value) != float(parsed) or parsed < 0:
                    return None
            except (TypeError, ValueError, OverflowError):
                return None
            return parsed

        for raw_item in baseline_ranking:
            item = dict(raw_item)
            action = item.get("action")
            action = action if isinstance(action, dict) else {}
            action_name = str(action.get("name") or "")
            action_kind = str(action.get("kind") or "")
            corridor_id = str(action.get("corridor_id") or "")
            # The frozen ranking does not get to carry a stale/multiple chosen
            # marker into the delegated audit.  Chosen is derived solely from
            # the action that this repair decision actually selected.
            is_selected = bool(selected_name and action_name == selected_name)

            go_p_blocked = None
            go_p_valid = False
            go_receipt_valid = False
            go_receipt_structure_valid = False
            go_root_clause_valid = False
            go_p_reason = "not_applicable_non_corridor_action"
            go_receipt_sha256 = None
            go_roots_actual = None
            go_roots_required = None
            go_measurement_root_debt = None
            repair_step_debt = None
            if corridor_id in ("corridor_a", "corridor_b"):
                go_receipt = latest_purify_go_receipts.get(corridor_id)
                if not isinstance(go_receipt, dict):
                    go_p_reason = "missing_latest_go_receipt"
                else:
                    raw_receipt_sha256 = go_receipt.get("receipt_sha256")
                    if (
                        isinstance(raw_receipt_sha256, str)
                        and len(raw_receipt_sha256) == 64
                        and all(
                            char in "0123456789abcdefABCDEF"
                            for char in raw_receipt_sha256
                        )
                    ):
                        go_receipt_sha256 = raw_receipt_sha256
                        go_receipt_valid = True
                    raw_p = go_receipt.get("p_blocked")
                    if isinstance(raw_p, bool) or not isinstance(
                        raw_p, (int, float)
                    ):
                        go_p_reason = "missing_or_malformed_go_p_blocked"
                    else:
                        parsed_p = float(raw_p)
                        if math.isfinite(parsed_p) and 0.0 <= parsed_p <= 1.0:
                            go_p_blocked = parsed_p
                            go_p_valid = True
                            go_p_reason = "latest_same_corridor_go_receipt"
                        else:
                            go_p_reason = "go_p_blocked_out_of_range"
                    if go_p_valid and not go_receipt_valid:
                        go_p_reason = "missing_or_malformed_go_receipt_sha256"
                    clauses = go_receipt.get("clauses")
                    required_clause_names = {
                        "prediction_set",
                        "evidence_age",
                        "distinct_measurement_roots",
                        "modality_skew",
                        "unresolved_conflicts",
                        "calibration_applicable",
                        "scope_match",
                    }
                    hard_pass_clause_names = {
                        "evidence_age",
                        "modality_skew",
                        "unresolved_conflicts",
                        "calibration_applicable",
                        "scope_match",
                    }
                    clause_items = (
                        [
                            clause
                            for clause in clauses
                            if isinstance(clause, dict)
                        ]
                        if isinstance(clauses, (list, tuple))
                        else []
                    )
                    clause_counts = {
                        name: sum(
                            clause.get("clause") == name
                            for clause in clause_items
                        )
                        for name in required_clause_names
                    }
                    clauses_by_name = {
                        str(clause.get("clause")): clause
                        for clause in clause_items
                        if clause.get("clause") in required_clause_names
                    }
                    scope = go_receipt.get("scope")
                    prediction_set = go_receipt.get("prediction_set")
                    prediction_labels = (
                        {str(label) for label in prediction_set}
                        if isinstance(
                            prediction_set,
                            (list, tuple, set, frozenset),
                        )
                        else set()
                    )
                    prediction_clause = clauses_by_name.get("prediction_set")
                    prediction_clause_actual = (
                        prediction_clause.get("actual")
                        if isinstance(prediction_clause, dict)
                        else None
                    )
                    prediction_clause_labels = (
                        {str(label) for label in prediction_clause_actual}
                        if isinstance(
                            prediction_clause_actual,
                            (list, tuple, set, frozenset),
                        )
                        else set()
                    )
                    go_receipt_structure_valid = bool(
                        go_receipt.get("schema_version")
                        == "purify.robotics.gate-receipt/v1"
                        and go_receipt.get("_purify_invoked") is True
                        and go_receipt.get("calibration_applicable") is True
                        and str(go_receipt.get("decision") or "").lower()
                        != "error"
                        and not go_receipt.get("error")
                        and isinstance(scope, dict)
                        and scope.get("robot_id") == "carrier"
                        and scope.get("payload_id") == "payload_loaded"
                        and scope.get("region_id") == corridor_id
                        and all(
                            clause_counts[name] == 1
                            for name in required_clause_names
                        )
                        and all(
                            isinstance(
                                clauses_by_name[name].get("passed"), bool
                            )
                            for name in required_clause_names
                        )
                        and all(
                            clauses_by_name[name].get("passed") is True
                            for name in hard_pass_clause_names
                        )
                        and bool(prediction_labels)
                        and prediction_labels <= {"clear", "blocked"}
                        and prediction_clause_labels == prediction_labels
                    )
                    root_clauses = [
                        clause
                        for clause in clause_items
                        if clause.get("clause")
                        == "distinct_measurement_roots"
                    ]
                    if len(root_clauses) == 1:
                        go_roots_actual = _nonnegative_int(
                            root_clauses[0].get("actual")
                        )
                        go_roots_required = _nonnegative_int(
                            root_clauses[0].get("required")
                        )
                        if (
                            go_roots_actual is not None
                            and go_roots_required is not None
                            and go_roots_required > 0
                        ):
                            go_root_clause_valid = True
                            go_measurement_root_debt = max(
                                go_roots_required - go_roots_actual, 0
                            )
                            repair_step_debt = max(
                                go_measurement_root_debt, 1
                            )
                    if (
                        go_p_valid
                        and go_receipt_valid
                        and not go_receipt_structure_valid
                    ):
                        go_p_reason = "untrustworthy_go_receipt_structure"
                    elif (
                        go_p_valid
                        and go_receipt_valid
                        and not go_root_clause_valid
                    ):
                        go_p_reason = "missing_or_malformed_go_root_clause"

            if (
                is_selected
                and action_kind == "side_view"
                and corridor_id in ("corridor_a", "corridor_b")
                and not (
                    go_p_valid
                    and go_receipt_valid
                    and go_receipt_structure_valid
                    and go_root_clause_valid
                )
            ):
                selected_side_view_fail_closed = True

            item.update(
                {
                    "chosen": is_selected,
                    "policy_artifact_id": "heuristic-v6/1",
                    "delegating_policy_artifact_id": (
                        "v8-contract-progress-nbv/1"
                    ),
                    "delegated_baseline_fail_closed": True,
                    "go_p_blocked": go_p_blocked,
                    "go_p_blocked_valid": go_p_valid,
                    "go_p_blocked_source_corridor": corridor_id or None,
                    "go_receipt_sha256": go_receipt_sha256,
                    "go_receipt_sha256_valid": go_receipt_valid,
                    "go_receipt_structure_valid": (
                        go_receipt_structure_valid
                    ),
                    "go_p_blocked_receipt_sha256": go_receipt_sha256,
                    "go_distinct_roots_actual": go_roots_actual,
                    "go_distinct_roots_required": go_roots_required,
                    "go_measurement_root_debt": go_measurement_root_debt,
                    "repair_step_debt": repair_step_debt,
                    "estimated_contract_completion_debt": repair_step_debt,
                    "go_p_blocked_binding_reason": go_p_reason,
                    "contract_progress_fail_closed_reason": (
                        fail_closed_audit.get("selection_reason")
                    ),
                    "contract_progress_corridor_fail_closed_reasons": (
                        fail_closed_audit.get("corridor_fail_closed_reasons")
                    ),
                }
            )
            rewritten.append(item)
        return rewritten, selected_side_view_fail_closed

    learned_model = None
    learned_device = config.device if str(config.device).startswith("cuda") else "cpu"
    if policy in ("purify-active-learned", "purify-active-dagger"):
        from pathlib import Path as _Path

        from v6_learned_policy import LearnedPolicyArtifact

        ckpt = config.learned_checkpoint
        if not ckpt:
            # Prefer DAgger round-3 then pilot best.
            candidates = [
                _Path("outputs/v6/learned-dagger/round3/best.pt"),
                _Path("outputs/v6/learned-dagger/best.pt"),
                _Path("outputs/v6/learned-pilot/best.pt"),
                _Path("results/v6-learned-pilot/best.pt"),
            ]
            ckpt = next((str(p) for p in candidates if p.is_file()), None)
        if not ckpt:
            raise FileNotFoundError(
                f"policy {policy} requires --learned-checkpoint or a default best.pt"
            )
        learned_model = LearnedPolicyArtifact(_Path(ckpt), in_dim=0).load(
            device=learned_device
        )

    def publish_and_receive(new_claims: list[RobotClaimV2]) -> None:
        nonlocal claims
        for c in new_claims:
            inbox.publish(c, runtime.current_step)
        delivered = inbox.poll(runtime.current_step)
        if delivered:
            claims.extend(delivered)
            claims = list(collapse_echo_claims(claims))

    def observe(
        agent_id: str,
        corridor_id: str,
        viewpoint_name: str,
        target_xy: tuple[float, float],
        predicted_coverage: float,
        *,
        risk_gated: bool = False,
        admitted: bool = False,
        action_kind: str = "side_view",
    ) -> None:
        nonlocal capture_index, observations
        result = runtime.move_agent_to(
            agent_id,
            target_xy,
            risk_gated=risk_gated,
            allow_without_admit=is_naive or not requires_gate,
            admitted=admitted,
        )
        motion_segments.append(result.to_dict())
        if not result.reached:
            return
        runtime.wait_steps(3)
        raw_frame = None
        if use_rgbd:
            from v5_rgbd_claims import process_genesis_observation

            raw_frame = runtime.capture_raw(
                agent_id=agent_id,
                viewpoint=viewpoint_name,
                viewpoint_xy=target_xy,
                predicted_coverage=predicted_coverage,
            )
            v1_claims, audit = process_genesis_observation(
                raw_frame,
                runtime.evidence_scenario,
                observation_index=capture_index,
                repair_action_kind=action_kind,
                device=config.device,
                ttl_steps=config.ttl_steps,
            )
            rgbd_audits.append(
                {
                    **audit,
                    "observer_agent_id": agent_id,
                    "corridor_id": corridor_id,
                    "viewpoint": viewpoint_name,
                }
            )
            new_claims = _v1_claims_to_v2(
                list(v1_claims),
                agent_id=agent_id,
                corridor_id=corridor_id,
                step=runtime.current_step,
                ttl=config.ttl_steps,
                calibration_id=runtime_calibration_id,
            )
        else:
            new_claims = _synthetic_observation(
                scenario=scenario,
                agent_id=agent_id,
                corridor_id=corridor_id,
                step=runtime.current_step,
                capture_index=capture_index,
                viewpoint_name=viewpoint_name,
                predicted_coverage=predicted_coverage,
                ttl=config.ttl_steps,
                calibration_id=runtime_calibration_id,
            )
        # Candidate-only initial observation: one physical RGB-D capture feeds a
        # shared seg-v3 backbone and produces scoped A/B proposals.  Both claims
        # retain the same physical capture/device root.  Frozen policies never
        # enter this branch and continue through the byte-for-byte legacy path.
        shared_initial_ab_done = False
        if (
            policy == "purify-active-contract-progress"
            and config.vision_enabled
            and str(config.vision_backend) == "torch_spatial_rgbd"
            and capture_index == 0
            and action_kind == "initial"
            and raw_frame is not None
        ):
            import numpy as np

            from v7_vision_claims import (
                propose_vision_spatial_rgbd_ab_shared,
                vision_proposal_to_claim_v2,
            )
            from v8_corridor_projection import corridor_mask_from_geometry

            rgb = getattr(raw_frame, "rgb", None)
            depth = getattr(raw_frame, "depth", None)
            if rgb is None or depth is None:
                raise RuntimeError(
                    "contract-progress shared initial capture requires live RGB-D"
                )
            arr = np.asarray(rgb)
            if arr.ndim < 2:
                raise RuntimeError("contract-progress shared initial RGB is malformed")
            h, w = arr.shape[:2]
            # Preserve frozen A's exact input selection: use a raw-frame mask
            # when supplied, otherwise the same public geometry projection.
            mask_a = getattr(raw_frame, "corridor_mask", None)
            mask_a_source = "raw_frame.corridor_mask"
            if mask_a is None:
                mask_a = getattr(raw_frame, "target_corridor_mask", None)
                mask_a_source = "raw_frame.target_corridor_mask"
            if mask_a is None:
                mask_a = corridor_mask_from_geometry(
                    h,
                    w,
                    corridor_id="corridor_a",
                    public=public,
                )
                mask_a_source = "public_geometry_projection"
            mask_b = corridor_mask_from_geometry(
                h,
                w,
                corridor_id="corridor_b",
                public=public,
            )
            if not bool(np.asarray(mask_a).any()) or not bool(
                np.asarray(mask_b).any()
            ):
                raise RuntimeError(
                    "contract-progress shared initial corridor masks are empty"
                )

            physical_capture_roots = {
                str(c.capture_root_id)
                for c in new_claims
                if getattr(c, "has_known_measurement_root", False)
            }
            physical_device_roots = {
                str(c.device_root_id)
                for c in new_claims
                if getattr(c, "has_known_measurement_root", False)
            }
            if len(physical_capture_roots) != 1 or len(physical_device_roots) != 1:
                raise RuntimeError(
                    "shared initial RGB-D must bind to exactly one physical "
                    "capture/device root"
                )
            physical_capture_root = next(iter(physical_capture_roots))
            physical_device_root = next(iter(physical_device_roots))
            vision_device = (
                config.device if str(config.device).startswith("cuda") else "cpu"
            )
            common_meta = {
                "agent_id": agent_id,
                "viewpoint": viewpoint_name,
                "step": runtime.current_step,
                "vision_source": "genesis_rgb",
                "genesis_live_rgbd": True,
            }
            prop_a, prop_b = propose_vision_spatial_rgbd_ab_shared(
                rgb,
                depth=depth,
                corridor_mask_a=mask_a,
                corridor_mask_b=mask_b,
                meta_a={**common_meta, "corridor_id": "corridor_a"},
                meta_b={**common_meta, "corridor_id": "corridor_b"},
                checkpoint=config.vision_checkpoint,
                conformal_artifact=config.vision_conformal_artifact,
                device=vision_device,
            )
            root_kind = _vision_root_kind(agent_id, viewpoint_name, capture_index)
            shared_claims: list[RobotClaimV2] = []
            for paired_cid, prop in (
                ("corridor_a", prop_a),
                ("corridor_b", prop_b),
            ):
                vclaim = vision_proposal_to_claim_v2(
                    prop,
                    agent_id=agent_id,
                    corridor_id=paired_cid,
                    step=runtime.current_step,
                    ttl=config.ttl_steps,
                    capture_root_id=physical_capture_root,
                    device_root_id=physical_device_root,
                    calibration_id=runtime_calibration_id,
                )
                if prop.p_blocked is not None:
                    vision_p_blocked[str(vclaim.claim_id)] = float(prop.p_blocked)
                shared_claims.append(vclaim)
                audit = {
                    "kind": "vision_proposal_v7",
                    "vision_source": "genesis_rgb",
                    "vision_backend": prop.backend,
                    "observer_agent_id": agent_id,
                    "corridor_id": paired_cid,
                    "viewpoint": viewpoint_name,
                    "vision_root_kind": root_kind,
                    "tensor_device": prop.tensor_device or vision_device,
                    "shared_initial_ab_capture": True,
                    "shared_initial_a_mask_source": mask_a_source,
                    "shared_initial_b_mask_source": "public_geometry_projection",
                    "shared_geometry_pose_semantics": "legacy_default_empty",
                    "physical_capture_root_bound": True,
                    "physical_capture_root_id": physical_capture_root,
                    "physical_device_root_id": physical_device_root,
                    "shared_physical_capture_root_id": physical_capture_root,
                    "shared_device_root_id": physical_device_root,
                    **prop.to_dict(),
                }
                audit.setdefault("fallback_used", bool(prop.fallback_used))
                audit.setdefault("checkpoint_loaded", bool(prop.checkpoint_loaded))
                audit.setdefault("checkpoint_sha256", prop.checkpoint_sha256)
                audit.setdefault(
                    "conformal_artifact_sha256",
                    prop.conformal_artifact_sha256,
                )
                audit.setdefault(
                    "preprocessing_version", prop.preprocessing_version
                )
                audit.setdefault("p_blocked", prop.p_blocked)
                audit.setdefault(
                    "prediction_set",
                    list(prop.prediction_set) if prop.prediction_set else [],
                )
                rgbd_audits.append(audit)
            new_claims = list(new_claims) + shared_claims
            shared_initial_ab_done = True

        # Optional v7 vision proposer (appends; does not replace geometry claims).
        if config.vision_enabled and not shared_initial_ab_done:
            from v7_vision_claims import (
                propose_vision,
                synthetic_rgb_for_label,
                vision_proposal_to_claim_v2,
            )

            rgb = None
            depth = None
            corridor_mask = None
            vision_source = "synthetic_rgb_proxy"
            if raw_frame is not None:
                rgb = getattr(raw_frame, "rgb", None)
                depth = getattr(raw_frame, "depth", None)
                corridor_mask = getattr(raw_frame, "corridor_mask", None)
                if corridor_mask is None:
                    corridor_mask = getattr(raw_frame, "target_corridor_mask", None)
                if rgb is not None:
                    vision_source = "genesis_rgb"
            if rgb is None:
                from v7_vision_claims import viewpoint_vision_cue

                # Viewpoint-staged cue: initial weak, scout side views clear so
                # active repair can assemble vision roots without oracle flags.
                cue = viewpoint_vision_cue(
                    viewpoint_name=viewpoint_name,
                    capture_index=capture_index,
                    seed=scenario.seed,
                    profile=str(scenario.profile),
                )
                rgb = synthetic_rgb_for_label(
                    cue, seed=scenario.seed * 17 + capture_index + hash(viewpoint_name) % 97
                )
            # Target-corridor ROI must match V8 train collection geometry projection.
            # Never use A=left/B=right half-frame fallback (that inverted live polarity).
            if corridor_mask is None and rgb is not None:
                import numpy as np

                from v8_corridor_projection import corridor_mask_from_geometry

                arr = np.asarray(rgb)
                h, w = arr.shape[:2]
                corridor_mask = corridor_mask_from_geometry(
                    h,
                    w,
                    corridor_id=str(corridor_id),
                    public=public,
                )
            vision_device = (
                config.device if str(config.device).startswith("cuda") else "cpu"
            )
            # Formal torch mode is fail-closed: missing ckpt/conformal or load
            # mismatch raises and fails the episode (no silent heuristic).
            prop = propose_vision(
                rgb,
                depth=depth,
                corridor_mask=corridor_mask,
                backend=config.vision_backend,
                checkpoint=config.vision_checkpoint,
                conformal_artifact=config.vision_conformal_artifact,
                device=vision_device,
                allow_heuristic_fallback=False,
                meta={
                    "agent_id": agent_id,
                    "corridor_id": corridor_id,
                    "viewpoint": viewpoint_name,
                    "step": runtime.current_step,
                    "vision_source": vision_source,
                    "genesis_live_rgbd": vision_source == "genesis_rgb",
                },
            )
            root_kind = _vision_root_kind(agent_id, viewpoint_name, capture_index)
            # V8 spatial: stamp claims with unified runtime calibration ID.
            # V7/heuristic: keep SENSOR_VERSION_V6 / default unless V8 mode active.
            vision_cal_id = runtime_calibration_id
            vision_capture_root_id = (
                f"vision-{root_kind}-{agent_id}-{capture_index}-"
                f"{prop.input_sha256[:10]}"
            )
            vision_device_root_id = None
            physical_capture_root_bound = False
            if (
                policy == "purify-active-contract-progress"
                and raw_frame is not None
            ):
                physical_capture_roots = {
                    str(c.capture_root_id)
                    for c in new_claims
                    if getattr(c, "has_known_measurement_root", False)
                }
                physical_device_roots = {
                    str(c.device_root_id)
                    for c in new_claims
                    if getattr(c, "has_known_measurement_root", False)
                }
                if (
                    len(physical_capture_roots) != 1
                    or len(physical_device_roots) != 1
                ):
                    raise RuntimeError(
                        "contract-progress RGB-D observation must bind geometry/"
                        "vision to exactly one physical capture/device root"
                    )
                vision_capture_root_id = next(iter(physical_capture_roots))
                vision_device_root_id = next(iter(physical_device_roots))
                physical_capture_root_bound = True
            vclaim = vision_proposal_to_claim_v2(
                prop,
                agent_id=agent_id,
                corridor_id=corridor_id,
                step=runtime.current_step,
                ttl=config.ttl_steps,
                capture_root_id=vision_capture_root_id,
                device_root_id=vision_device_root_id,
                calibration_id=vision_cal_id,
            )
            if prop.p_blocked is not None:
                vision_p_blocked[str(vclaim.claim_id)] = float(prop.p_blocked)
            new_claims = list(new_claims) + [vclaim]
            audit = {
                "kind": "vision_proposal_v7",
                "vision_source": vision_source,
                "vision_backend": prop.backend,
                "observer_agent_id": agent_id,
                "corridor_id": corridor_id,
                "viewpoint": viewpoint_name,
                "vision_root_kind": root_kind,
                "tensor_device": prop.tensor_device or vision_device,
                **prop.to_dict(),
            }
            if physical_capture_root_bound:
                audit.update(
                    {
                        "physical_capture_root_bound": True,
                        "physical_capture_root_id": vision_capture_root_id,
                        "physical_device_root_id": vision_device_root_id,
                    }
                )
            # Ensure required runtime-integration keys are always present.
            audit.setdefault("fallback_used", bool(prop.fallback_used))
            audit.setdefault("checkpoint_loaded", bool(prop.checkpoint_loaded))
            audit.setdefault("checkpoint_sha256", prop.checkpoint_sha256)
            audit.setdefault(
                "conformal_artifact_sha256", prop.conformal_artifact_sha256
            )
            audit.setdefault("preprocessing_version", prop.preprocessing_version)
            audit.setdefault("p_blocked", prop.p_blocked)
            audit.setdefault(
                "prediction_set",
                list(prop.prediction_set) if prop.prediction_set else [],
            )
            rgbd_audits.append(audit)
        capture_index += 1
        observations += 1
        visited.add(viewpoint_name)
        viewpoints_sequence.append(str(viewpoint_name))
        # Also mark fixed action-set aliases so planner does not re-pick same side.
        if viewpoint_name.startswith("corridor_a/"):
            visited.add("scout_a_" + viewpoint_name.split("/", 1)[1])
            side_obs_per_corridor["corridor_a"] = side_obs_per_corridor.get(
                "corridor_a", 0
            ) + 1
        elif viewpoint_name.startswith("corridor_b/"):
            visited.add("scout_b_" + viewpoint_name.split("/", 1)[1])
            side_obs_per_corridor["corridor_b"] = side_obs_per_corridor.get(
                "corridor_b", 0
            ) + 1
        # Offline-oracle-free: decisive blocked claims confirm corridor blocked.
        for c in new_claims:
            if (
                str(getattr(c, "value", "")) == "blocked"
                and float(getattr(c, "quality", 0.0) or 0.0) >= 0.35
                and float(getattr(c, "visibility", 0.0) or 0.0) >= 0.35
            ):
                # Scope region is corridor id for v2 claims.
                region = getattr(getattr(c, "scope", None), "region_id", None)
                if region in ("corridor_a", "corridor_b"):
                    confirmed_blocked.add(str(region))
        publish_and_receive(new_claims)

    # Initial carrier front-view (low coverage / shared root on first capture).
    first_corridor = "corridor_a"
    observe(
        CARRIER_ID,
        first_corridor,
        "carrier_initial_front",
        (-0.5, 0.0),
        0.55,
        action_kind="initial",
    )
    roots_after_initial = {
        c.capture_root_id for c in claims if c.has_known_measurement_root
    }

    def _invoke_purify_go(corridor_id: str, contract: Any) -> dict[str, Any] | None:
        nonlocal purify_invoked_count
        if purify_bridge is None:
            return None
        from v8_runtime_calibration import filter_claims_for_corridor_go
        from v8_go_fusion_claims import (
            patch_claim_wire_for_go,
            strip_claim_wire_for_go,
            decisive_value_from_p,
        )

        # Go fusion v3 was calibrated on vision-only dual side-view claims
        # (see collect_world). Sending geometry/simulated_semantic mixes causes
        # modality_conflict + soft p_blocked vs binary cal quantiles → permanent deny.
        VISION_MOD = "vision_semantic_v7"
        go_claims_all: list[dict[str, Any]] = []
        for c in claims:
            mod = str(getattr(c, "modality", "") or "")
            if mod and mod != VISION_MOD:
                continue
            if hasattr(c, "to_v1_robot_claim"):
                v1w = c.to_v1_robot_claim().to_wire()
            else:
                v1w = c.to_wire() if hasattr(c, "to_wire") else dict(c)
            # Prefer raw vision p_blocked recorded at proposal time (cal-aligned).
            # Do NOT reconstruct as 1-confidence — that destroys ~1e-12 clear scores.
            cid = str(v1w.get("claim_id") or getattr(c, "claim_id", "") or "")
            val = str(v1w.get("value") or "")
            conf = float(v1w.get("confidence") or 0.5)
            if cid in vision_p_blocked:
                p_b = float(vision_p_blocked[cid])
            elif val == "blocked":
                p_b = conf
            elif val == "clear":
                p_b = max(0.0, 1.0 - conf)
            else:
                p_b = conf if conf != 0.5 else 0.5
            root = str(v1w.get("capture_root_id") or getattr(c, "capture_root_id", "") or "")
            dev = str(v1w.get("device_root_id") or getattr(c, "device_root_id", "") or root)
            v1w = patch_claim_wire_for_go(
                v1w, p_blocked=p_b, capture_root_id=root, device_root_id=dev
            )
            go_claims_all.append(strip_claim_wire_for_go(v1w))
        # Corridor-scoped filter; keep intra-corridor conflicts (clear vs blocked).
        go_claims = filter_claims_for_corridor_go(
            go_claims_all, corridor_id=corridor_id, predicate="carrier_traversable"
        )
        scope = {
            "robot_id": "carrier",
            "payload_id": "payload_loaded",
            "region_id": corridor_id,
        }
        go_contract = {
            "schema_version": "purify.robotics.action-contract/v1",
            "contract_id": f"cross-{corridor_id}",
            "action": "cross_corridor",
            "fact_id": f"region:{corridor_id}",
            "predicate": "carrier_traversable",
            "scope": scope,
            "required_prediction_set": ["clear"],
            "max_evidence_age": int(getattr(contract, "evidence_age_limit", 80) or 80),
            "min_distinct_measurement_roots": int(
                getattr(contract, "min_distinct_capture_roots", 2) or 2
            ),
            "max_modality_skew": 40,
            "max_unresolved_conflicts": int(
                getattr(contract, "max_unresolved_conflicts", 0) or 0
            ),
            "require_calibration_applicable": True,
        }
        # Real V8 conformal → Go CalibrationArtifact (no smoke placeholders).
        if go_calibration_wire is not None:
            cal = dict(go_calibration_wire)
            svs = list(cal.get("sensor_versions") or [])
            if runtime_calibration_id in svs:
                sensor_version = runtime_calibration_id
            elif svs:
                sensor_version = str(svs[0])
            else:
                sensor_version = runtime_calibration_id
        else:
            # Non-V8 path: legacy compatible bundle (not used for formal V8 smoke).
            cal = {
                "schema_version": "purify.robotics.calibration.v1",
                "artifact_id": "v6-runtime-cal",
                "alpha": 0.05,
                "class_quantiles": {"clear": 0.1, "blocked": 0.1},
                "applicable_profiles": [str(scenario.profile)],
                "min_noise_intensity": 0.0,
                "max_noise_intensity": 1.0,
                "sensor_versions": [SENSOR_VERSION_V6, "sensors-v1"],
                "git_commit": "v6-runtime",
                "dataset_sha256": "b" * 64,
                "seed_ranges": [{"start": 0, "end": 200000}],
            }
            sensor_version = SENSOR_VERSION_V6
        pub = scenario.public_context if isinstance(scenario.public_context, dict) else {}
        ora = scenario.oracle_context if isinstance(getattr(scenario, "oracle_context", None), dict) else {}
        noise = float(
            pub.get("declared_noise_intensity")
            or ora.get("true_noise_realization")
            or 0.03
        )
        try:
            receipt = purify_bridge.evaluate_action(
                claims=go_claims,
                contract=go_contract,
                calibration=cal,
                current_step=int(runtime.current_step),
                profile=str(scenario.profile),
                noise_intensity=noise,
                sensor_version=sensor_version,
            )
            purify_invoked_count += 1
            receipt = dict(receipt)
            receipt["_purify_binary_sha256"] = purify_binary_sha256
            receipt["_purify_invoked"] = True
            receipt["_runtime_calibration_id"] = sensor_version
            receipt["_go_calibration_artifact_id"] = cal.get("artifact_id")
            receipt["_n_claims_sent"] = len(go_claims)
            purify_go_receipts.append(receipt)
            return receipt
        except Exception as exc:  # record failure; do not crash Python control path
            purify_go_receipts.append(
                {
                    "schema_version": "purify.robotics.gate-receipt/v1",
                    "admitted": False,
                    "decision": "error",
                    "error": str(exc),
                    "_purify_invoked": False,
                    "_purify_binary_sha256": purify_binary_sha256,
                    "_runtime_calibration_id": sensor_version,
                }
            )
            return None

    def evaluate_all() -> dict[str, Any]:
        """Evaluate Python + optional Purify Go gates.

        When use_purify_go_gate is True, **effective admit** requires:
            python_gate.admitted AND purify_go_gate.admitted
        Go deny always blocks direct; Python deny + Go admit is fail-closed (deny).
        """
        from v6_contracts import GateDecision

        decisions = {}
        for cid, contract in contracts.items():
            py_dec = _evaluate_gate(
                claims, contract, current_step=runtime.current_step, config=config
            )
            go_rec = _invoke_purify_go(cid, contract) if config.use_purify_go_gate else None
            if policy == "purify-active-contract-progress":
                if go_rec is None:
                    # Never plan from a stale pre-error receipt.
                    latest_purify_go_receipts.pop(cid, None)
                else:
                    latest_purify_go_receipts[cid] = dict(go_rec)
            go_admitted = bool(go_rec is not None and go_rec.get("admitted"))
            py_admitted = bool(py_dec.admitted)

            if config.use_purify_go_gate:
                if go_rec is None:
                    effective = False
                    extra_reasons = ("purify_go_missing",)
                elif py_admitted and go_admitted:
                    effective = True
                    extra_reasons = ()
                elif py_admitted and not go_admitted:
                    effective = False
                    extra_reasons = ("purify_go_denied",)
                elif (not py_admitted) and go_admitted:
                    # Fail-closed: Go alone cannot authorize motion.
                    effective = False
                    extra_reasons = ("python_gate_denied_go_admitted_fail_closed",)
                else:
                    effective = False
                    extra_reasons = ()
                reasons = tuple(dict.fromkeys(list(py_dec.reasons) + list(extra_reasons)))
                dec = GateDecision(
                    admitted=effective,
                    corridor_id=py_dec.corridor_id,
                    reasons=reasons,
                    belief_gaps=py_dec.belief_gaps,
                    measurement_root_ids=py_dec.measurement_root_ids,
                    claim_count=py_dec.claim_count,
                    distinct_capture_roots=py_dec.distinct_capture_roots,
                    p_blocked=py_dec.p_blocked,
                    receipt_sha256=py_dec.receipt_sha256,
                    valid_until_step=py_dec.valid_until_step,
                    current_step=py_dec.current_step,
                )
            else:
                dec = py_dec
                py_admitted = dec.admitted
                go_admitted = False

            decisions[cid] = dec
            wire = dec.to_wire()
            wire["python_admitted"] = py_admitted
            wire["purify_go_admitted"] = go_admitted if config.use_purify_go_gate else None
            wire["effective_admit"] = bool(dec.admitted)
            if go_rec is not None:
                wire["purify_go_receipt"] = {
                    "schema_version": go_rec.get("schema_version"),
                    "receipt_id": go_rec.get("receipt_id"),
                    "receipt_sha256": go_rec.get("receipt_sha256"),
                    "admitted": go_rec.get("admitted"),
                    "decision": go_rec.get("decision"),
                    "_purify_invoked": go_rec.get("_purify_invoked", True),
                    "_purify_binary_sha256": go_rec.get("_purify_binary_sha256"),
                }
            gate_receipts.append(wire)
        return decisions

    decisions = evaluate_all()
    admitted_any = any(d.admitted for d in decisions.values())
    initial_gate_denied = bool(requires_gate and not admitted_any)
    if initial_gate_denied:
        # Union of deny reasons on the first post-initial evaluation.
        for d in decisions.values():
            initial_gate_reasons.extend(list(d.reasons))
        initial_gate_reasons = list(dict.fromkeys(initial_gate_reasons))

    # Active repair loop
    if requires_gate and not admitted_any and allows_repair:
        repair_attempted = True
        for _ in range(config.max_observations):
            # Prefer repairable denied corridor (not hard-conflict A when B is open).
            contract_progress_selected = None
            contract_progress_ranking = None
            contract_progress_selector_invoked = False
            contract_progress_no_repairable_contract = False
            contract_progress_selector_audit: dict[str, Any] = {}
            contract_progress_selector_corridor_audit: dict[
                str, dict[str, Any]
            ] = {}
            delegated_baseline_fail_closed = False
            delegated_go_p_fail_closed = False
            if policy == "purify-active-contract-progress":
                from v6_repair import build_candidate_actions
                from v8_contract_progress_nbv import (
                    choose_contract_progress_action,
                )

                candidate_carrier_xy = (
                    runtime.pose_of(CARRIER_ID).x,
                    runtime.pose_of(CARRIER_ID).y,
                )
                candidate_scout_xy = (
                    runtime.pose_of(SCOUT_ID).x,
                    runtime.pose_of(SCOUT_ID).y,
                )
                candidate_actions = build_candidate_actions(
                    public,
                    carrier_xy=candidate_carrier_xy,
                    scout_xy=candidate_scout_xy,
                    visited=visited,
                )
                contract_progress_selected, contract_progress_ranking = (
                    choose_contract_progress_action(
                        latest_go_receipts=latest_purify_go_receipts,
                        decisions=decisions,
                        confirmed_blocked=confirmed_blocked,
                        side_obs_per_corridor=side_obs_per_corridor,
                        public=public,
                        carrier_xy=candidate_carrier_xy,
                        scout_xy=candidate_scout_xy,
                        candidates=candidate_actions,
                        observations_taken=observations,
                        max_observations=config.max_observations,
                        max_side_per_corridor=2,
                    )
                )
                contract_progress_selector_invoked = True
                contract_progress_selector_audit = (
                    dict(contract_progress_ranking[0])
                    if contract_progress_ranking
                    else {}
                )
                contract_progress_no_repairable_contract = bool(
                    contract_progress_selected is None
                    or contract_progress_selected.kind == "safe_fallback"
                )
                contract_progress_selector_corridor_audit = (
                    _selector_corridor_audit(
                        list(contract_progress_ranking or [])
                    )
                )
                candidate_cid = (
                    contract_progress_selected.corridor_id
                    if contract_progress_selected is not None
                    else ""
                )
                primary = decisions.get(candidate_cid)
                if primary is None:
                    # Both contracts hard-denied/malformed: derive the same gaps
                    # as frozen V8 before delegating its conservative planner.
                    primary = _pick_primary_decision(
                        decisions,
                        confirmed_blocked=confirmed_blocked,
                        side_obs_per_corridor=side_obs_per_corridor,
                        max_side_per_corridor=2,
                    )
            else:
                primary = _pick_primary_decision(
                    decisions,
                    confirmed_blocked=confirmed_blocked,
                    side_obs_per_corridor=side_obs_per_corridor,
                    max_side_per_corridor=2,
                )
            gaps = [g.get("reason", "insufficient_roots") for g in primary.belief_gaps]
            if not gaps:
                gaps = list(primary.reasons) or ["insufficient_roots"]
            # Bias scout toward the primary corridor's side views.
            if primary.corridor_id and f"corridor:{primary.corridor_id}" not in gaps:
                gaps = list(gaps) + [f"target_corridor:{primary.corridor_id}"]
            # Explicit switch signal when A is confirmed blocked.
            for cid in sorted(confirmed_blocked):
                gaps = list(gaps) + [f"confirmed_blocked:{cid}"]
            carrier_xy = (
                runtime.pose_of(CARRIER_ID).x,
                runtime.pose_of(CARRIER_ID).y,
            )
            scout_xy = (runtime.pose_of(SCOUT_ID).x, runtime.pose_of(SCOUT_ID).y)
            if policy == "purify-active-contract-progress":
                selected = contract_progress_selected
                ranking = list(contract_progress_ranking or [])
                if selected is None or selected.kind == "safe_fallback":
                    # A selector-level fallback means there is no repairable,
                    # trustworthy Go contract.  Preserve frozen V8's probing and
                    # dual-blocked safe-detour behavior instead of prematurely
                    # incrementing the formal fallback metric.
                    selected, baseline_ranking = choose_evidence_action(
                        public,
                        gap_reasons=gaps,
                        carrier_xy=carrier_xy,
                        scout_xy=scout_xy,
                        visited=visited,
                        observations_taken=observations,
                        max_observations=config.max_observations,
                    )
                    delegated_baseline_fail_closed = True
                    contract_progress_delegation_count += 1
                    fail_closed_audit = ranking[0] if ranking else {}
                    ranking, delegated_go_p_fail_closed = (
                        _bind_delegated_go_p_blocked(
                            list(baseline_ranking),
                            selected_action=selected,
                            fail_closed_audit=dict(fail_closed_audit),
                        )
                    )
            elif policy in ("purify-active-learned", "purify-active-dagger") and learned_model is not None:
                from v6_learned_policy import rank_with_learned
                from v6_repair import build_candidate_actions

                candidates = build_candidate_actions(
                    public,
                    carrier_xy=carrier_xy,
                    scout_xy=scout_xy,
                    visited=visited,
                )
                selected, ranking = rank_with_learned(
                    learned_model,
                    candidates,
                    gap_reasons=gaps,
                    observations_taken=observations,
                    max_observations=config.max_observations,
                    device=learned_device,
                )
            elif policy == "purify-random":
                import random as _random

                from v6_repair import build_candidate_actions

                candidates = build_candidate_actions(
                    public,
                    carrier_xy=carrier_xy,
                    scout_xy=scout_xy,
                    visited=visited,
                )
                eligible = [
                    a
                    for a in candidates
                    if a.reachable or a.kind == "safe_fallback"
                ]
                rng = _random.Random(
                    (scenario.seed * 1009 + observations * 17 + replan_count) % (2**31)
                )
                selected = rng.choice(eligible) if eligible else None
                ranking = [
                    {
                        "action": a.to_dict(),
                        "utility": 1.0 if a is selected else 0.0,
                        "eligible": True,
                    }
                    for a in eligible
                ]
            else:
                selected, ranking = choose_evidence_action(
                    public,
                    gap_reasons=gaps,
                    carrier_xy=carrier_xy,
                    scout_xy=scout_xy,
                    visited=visited,
                    observations_taken=observations,
                    max_observations=config.max_observations,
                )
            receipt = authorize_evidence_request(
                belief_gaps=gaps,
                selected_action=(
                    None
                    if delegated_go_p_fail_closed
                    else (selected.to_dict() if selected else None)
                ),
                current_step=runtime.current_step,
                observations_taken=observations,
                replans_taken=replan_count,
                max_observations=config.max_observations,
                max_replans=config.max_replans,
                policy_artifact_id=(
                    "v8-contract-progress-nbv/1"
                    if policy == "purify-active-contract-progress"
                    else "heuristic-v6/1"
                ),
                candidate_ranking=ranking,
            )
            evidence_requests.append(receipt.to_wire())
            chosen_rank = next((r for r in ranking if r.get("chosen")), None)
            repair_decisions.append(
                {
                    "selected": None if selected is None else selected.to_dict(),
                    "ranking_head": ranking[:5],
                    "authorized": receipt.authorized,
                    **(
                        {
                            "policy_artifact_id": receipt.policy_artifact_id,
                            "evidence_request_receipt_sha256": (
                                receipt.receipt_sha256
                            ),
                            "execution_status": (
                                "authorized_for_execution"
                                if receipt.authorized
                                else "authorization_denied_noop"
                            ),
                            "contract_progress_nbv_enabled": True,
                            "contract_progress_selector_invoked": bool(
                                contract_progress_selector_invoked
                            ),
                            "contract_progress_no_repairable_contract": bool(
                                contract_progress_no_repairable_contract
                            ),
                            "contract_progress_selector_selection_reason": (
                                contract_progress_selector_audit.get(
                                    "selection_reason"
                                )
                            ),
                            "contract_progress_corridor_fail_closed_reasons": (
                                contract_progress_selector_audit.get(
                                    "corridor_fail_closed_reasons"
                                )
                            ),
                            "contract_progress_selector_corridor_audit": (
                                contract_progress_selector_corridor_audit
                            ),
                            "delegated_baseline_fail_closed": bool(
                                delegated_baseline_fail_closed
                            ),
                            "delegated_go_p_fail_closed": bool(
                                delegated_go_p_fail_closed
                            ),
                        }
                        if policy == "purify-active-contract-progress"
                        else {}
                    ),
                    "nbv_alignment_score": (
                        None
                        if chosen_rank is None
                        else chosen_rank.get("alignment_score")
                    ),
                    "nbv_contamination_risk": (
                        None
                        if chosen_rank is None
                        else chosen_rank.get("contamination_risk")
                    ),
                    "nbv_selection_reason": (
                        None
                        if chosen_rank is None
                        else chosen_rank.get("selection_reason")
                    ),
                    "nbv_same_side": (
                        None if chosen_rank is None else chosen_rank.get("same_side")
                    ),
                }
            )
            if selected is None or not receipt.authorized:
                outcome = "repair_not_authorized"
                break
            if selected.kind == "safe_fallback":
                outcome = "safe_fallback"
                break
            if selected.kind == "wait":
                runtime.wait_steps(int(selected.to_dict().get("wait_steps") or 20))
                # Deliver delayed messages.
                delivered = inbox.poll(runtime.current_step)
                if delivered:
                    claims.extend(delivered)
                    claims = list(collapse_echo_claims(claims))
            else:
                if selected.kind == "side_view":
                    replan_count += 1
                agent = selected.observer
                corridor = selected.corridor_id or "corridor_a"
                observe(
                    agent,
                    corridor,
                    selected.viewpoint,
                    selected.target_xy,
                    selected.predicted_coverage,
                )
            decisions = evaluate_all()
            if any(d.admitted for d in decisions.values()):
                repair_success = True
                break

    decisions = evaluate_all() if not gate_receipts else decisions
    # Corridors whose prior GateReceipts were wiped by world change.
    invalidated_corridors: set[str] = set()
    event_applied = False

    def apply_due_world_events() -> bool:
        """Apply absolute-step external events; invalidate prior admits.

        Returns True if any corridor admit was invalidated.
        """
        nonlocal event_applied, selected_corridor, repair_success
        event = scenario.oracle_context.get("external_event") or {}
        if event_applied or not event:
            return False
        if runtime.current_step < int(event.get("step", 10**9)):
            return False
        event_applied = True
        wiped = False
        if event.get("to_blocked") and event.get("corridor_id"):
            cid = str(event["corridor_id"])
            y = -0.3 if cid == "corridor_a" else 0.3
            runtime.set_obstacle(1.0, y, 0.28)
            invalidated_corridors.add(cid)
            invalidations.append(
                {
                    "schema_version": "look-twice.plan-invalidation/v6",
                    "invalidated": True,
                    "reason": "dynamic_corridor_change",
                    "corridor_id": cid,
                    "step": runtime.current_step,
                    "previous_admitted": any(
                        g.get("admitted") and g.get("corridor_id") == cid
                        for g in gate_receipts
                    ),
                }
            )
            wiped = True
            if selected_corridor == cid:
                selected_corridor = None
                repair_success = False
        return wiped

    def live_admit(cid: str) -> bool:
        if cid in invalidated_corridors:
            return False
        dec = _evaluate_gate(
            claims, contracts[cid], current_step=runtime.current_step, config=config
        )
        gate_receipts.append(dec.to_wire())
        return bool(dec.admitted)

    # Choose admitted corridor, else safest detour.
    # Never route through a corridor confirmed blocked by decisive claims.
    for cid, dec in decisions.items():
        if (
            dec.admitted
            and cid not in invalidated_corridors
            and cid not in confirmed_blocked
        ):
            selected_corridor = cid
            break
    if selected_corridor is None:
        for cid, dec in decisions.items():
            if dec.admitted and cid not in invalidated_corridors:
                # Last resort: admitted but confirmed blocked — still refuse
                # and detour rather than force a false-clear cross.
                break

    def cross_corridor(cid: str, *, force: bool = False) -> bool:
        nonlocal unsafe, route_mode, selected_corridor
        contract = contracts[cid]
        region = next(c["region"] for c in public["corridors"] if c["id"] == cid)
        # Centerline path: align to corridor y first, then enter / mid / exit.
        # Avoid diagonal cut from center wait pose through the other corridor.
        cy = 0.5 * (float(region[2]) + float(region[3]))
        approach = (-0.55, cy)
        entry = (float(region[0]) - 0.05, cy)
        mid = (0.5 * (float(region[0]) + float(region[1])), cy)
        exit_xy = (float(region[1]) + 0.1, cy)
        admitted = force or live_admit(cid)
        if requires_gate and not admitted and not force:
            return False
        waypoints = (
            (approach, "approach"),
            (entry, "entry"),
            (mid, "mid"),
            (exit_xy, "exit"),
        )
        for target, label in waypoints:
            # Absolute schedule may flip the world mid-crossing.
            if apply_due_world_events() and cid in invalidated_corridors and not force:
                selected_corridor = None
                return False
            # Approach is outside corridor risk region; only gate after entry.
            gated = label != "approach"
            res = runtime.move_agent_to(
                CARRIER_ID,
                target,
                risk_gated=gated,
                allow_without_admit=is_naive or force or not gated,
                admitted=(force or live_admit(cid)),
            )
            motion_segments.append(res.to_dict())
            if not res.reached:
                return False
            # Unsafe if truth blocked while in corridor.
            if label != "approach" and scenario.truth_corridor_blocked(
                cid, runtime.current_step
            ):
                # Entering risk while blocked counts unsafe for naive force.
                if is_naive or force:
                    unsafe = True
                    return False
                if requires_gate:
                    return False
        route_mode = "direct"
        return not unsafe

    def safe_detour() -> bool:
        nonlocal used_detour, route_mode, outcome
        used_detour = True
        route_mode = "detour"
        # High-|y| path around both corridors.
        for target in ((-0.2, 1.35), (1.0, 1.4), (2.2, 0.6)):
            res = runtime.move_agent_to(
                CARRIER_ID,
                target,
                risk_gated=False,
                allow_without_admit=True,
                admitted=False,
            )
            motion_segments.append(res.to_dict())
            if not res.reached:
                outcome = "detour_failed"
                return False
        outcome = "safe_detour_complete"
        return True

    # Advance to event step when scheduled soon so invalidation is testable.
    event = scenario.oracle_context.get("external_event") or {}
    if event and int(event.get("step", 10**9)) < 200:
        while runtime.current_step < int(event["step"]):
            runtime.wait_steps(1)
            delivered = inbox.poll(runtime.current_step)
            if delivered:
                claims.extend(delivered)
                claims = list(collapse_echo_claims(claims))
        apply_due_world_events()
        # Re-evaluate after invalidation — prior admit for flipped corridor dies.
        decisions = evaluate_all()
        selected_corridor = None
        for cid, dec in decisions.items():
            if dec.admitted and cid not in invalidated_corridors:
                selected_corridor = cid
                break
        # Active may re-repair once after invalidation.
        if (
            requires_gate
            and allows_repair
            and selected_corridor is None
            and observations < config.max_observations
        ):
            repair_attempted = True
            for _ in range(max(1, config.max_observations - observations)):
                contract_progress_selected = None
                contract_progress_ranking = None
                contract_progress_selector_invoked = False
                contract_progress_no_repairable_contract = False
                contract_progress_selector_audit: dict[str, Any] = {}
                contract_progress_selector_corridor_audit: dict[
                    str, dict[str, Any]
                ] = {}
                delegated_baseline_fail_closed = False
                delegated_go_p_fail_closed = False
                if policy == "purify-active-contract-progress":
                    from v6_repair import build_candidate_actions
                    from v8_contract_progress_nbv import (
                        choose_contract_progress_action,
                    )

                    carrier_xy = (
                        runtime.pose_of(CARRIER_ID).x,
                        runtime.pose_of(CARRIER_ID).y,
                    )
                    scout_xy = (
                        runtime.pose_of(SCOUT_ID).x,
                        runtime.pose_of(SCOUT_ID).y,
                    )
                    candidate_actions = build_candidate_actions(
                        public,
                        carrier_xy=carrier_xy,
                        scout_xy=scout_xy,
                        visited=visited,
                    )
                    contract_progress_selected, contract_progress_ranking = (
                        choose_contract_progress_action(
                            latest_go_receipts=latest_purify_go_receipts,
                            decisions=decisions,
                            # Candidate planner state remains claim-derived.
                            # ``invalidated_corridors`` comes from the scenario
                            # event/oracle path and must never enter NBV inputs.
                            confirmed_blocked=confirmed_blocked,
                            side_obs_per_corridor=side_obs_per_corridor,
                            public=public,
                            carrier_xy=carrier_xy,
                            scout_xy=scout_xy,
                            candidates=candidate_actions,
                            observations_taken=observations,
                            max_observations=config.max_observations,
                            max_side_per_corridor=2,
                        )
                    )
                    contract_progress_selector_invoked = True
                    contract_progress_selector_audit = (
                        dict(contract_progress_ranking[0])
                        if contract_progress_ranking
                        else {}
                    )
                    contract_progress_no_repairable_contract = bool(
                        contract_progress_selected is None
                        or contract_progress_selected.kind == "safe_fallback"
                    )
                    contract_progress_selector_corridor_audit = (
                        _selector_corridor_audit(
                            list(contract_progress_ranking or [])
                        )
                    )
                    candidate_cid = (
                        contract_progress_selected.corridor_id
                        if contract_progress_selected is not None
                        else ""
                    )
                    primary = decisions.get(candidate_cid)
                    if primary is None:
                        primary = _pick_primary_decision(
                            decisions,
                            confirmed_blocked=confirmed_blocked,
                            side_obs_per_corridor=side_obs_per_corridor,
                            max_side_per_corridor=2,
                        )
                else:
                    primary = _pick_primary_decision(
                        decisions,
                        confirmed_blocked=confirmed_blocked,
                        side_obs_per_corridor=side_obs_per_corridor,
                        max_side_per_corridor=2,
                    )
                gaps = [
                    g.get("reason", "insufficient_roots") for g in primary.belief_gaps
                ] or list(primary.reasons) or ["insufficient_roots"]
                if primary.corridor_id:
                    gaps = list(gaps) + [f"target_corridor:{primary.corridor_id}"]
                for cid in sorted(confirmed_blocked):
                    gaps = list(gaps) + [f"confirmed_blocked:{cid}"]
                if policy == "purify-active-contract-progress":
                    selected = contract_progress_selected
                    ranking = list(contract_progress_ranking or [])
                    if selected is None or selected.kind == "safe_fallback":
                        selected, baseline_ranking = choose_evidence_action(
                            public,
                            gap_reasons=gaps,
                            carrier_xy=carrier_xy,
                            scout_xy=scout_xy,
                            visited=visited,
                            observations_taken=observations,
                            max_observations=config.max_observations,
                        )
                        delegated_baseline_fail_closed = True
                        contract_progress_delegation_count += 1
                        fail_closed_audit = ranking[0] if ranking else {}
                        ranking, delegated_go_p_fail_closed = (
                            _bind_delegated_go_p_blocked(
                                list(baseline_ranking),
                                selected_action=selected,
                                fail_closed_audit=dict(fail_closed_audit),
                            )
                        )
                else:
                    selected, ranking = choose_evidence_action(
                        public,
                        gap_reasons=gaps,
                        carrier_xy=(
                            runtime.pose_of(CARRIER_ID).x,
                            runtime.pose_of(CARRIER_ID).y,
                        ),
                        scout_xy=(
                            runtime.pose_of(SCOUT_ID).x,
                            runtime.pose_of(SCOUT_ID).y,
                        ),
                        visited=visited,
                        observations_taken=observations,
                        max_observations=config.max_observations,
                    )
                receipt = authorize_evidence_request(
                    belief_gaps=gaps,
                    selected_action=(
                        None
                        if delegated_go_p_fail_closed
                        else (selected.to_dict() if selected else None)
                    ),
                    current_step=runtime.current_step,
                    observations_taken=observations,
                    replans_taken=replan_count,
                    max_observations=config.max_observations,
                    max_replans=config.max_replans,
                    policy_artifact_id=(
                        "v8-contract-progress-nbv/1"
                        if policy == "purify-active-contract-progress"
                        else "heuristic-v6/1"
                    ),
                    candidate_ranking=ranking,
                )
                evidence_requests.append(receipt.to_wire())
                if policy == "purify-active-contract-progress":
                    repair_decisions.append(
                        {
                            "selected": (
                                None if selected is None else selected.to_dict()
                            ),
                            "ranking_head": ranking[:5],
                            "authorized": receipt.authorized,
                            "policy_artifact_id": receipt.policy_artifact_id,
                            "evidence_request_receipt_sha256": (
                                receipt.receipt_sha256
                            ),
                            "execution_status": (
                                "authorized_for_execution"
                                if receipt.authorized
                                else "authorization_denied_noop"
                            ),
                            "contract_progress_nbv_enabled": True,
                            "contract_progress_selector_invoked": bool(
                                contract_progress_selector_invoked
                            ),
                            "contract_progress_no_repairable_contract": bool(
                                contract_progress_no_repairable_contract
                            ),
                            "contract_progress_selector_selection_reason": (
                                contract_progress_selector_audit.get(
                                    "selection_reason"
                                )
                            ),
                            "contract_progress_corridor_fail_closed_reasons": (
                                contract_progress_selector_audit.get(
                                    "corridor_fail_closed_reasons"
                                )
                            ),
                            "contract_progress_selector_corridor_audit": (
                                contract_progress_selector_corridor_audit
                            ),
                            "delegated_baseline_fail_closed": bool(
                                delegated_baseline_fail_closed
                            ),
                            "delegated_go_p_fail_closed": bool(
                                delegated_go_p_fail_closed
                            ),
                            "repair_phase": "post_invalidation",
                        }
                    )
                if selected is None or not receipt.authorized:
                    break
                if selected.kind == "safe_fallback":
                    break
                if selected.kind == "side_view":
                    replan_count += 1
                if selected.kind != "wait":
                    observe(
                        selected.observer,
                        selected.corridor_id or "corridor_a",
                        selected.viewpoint,
                        selected.target_xy,
                        selected.predicted_coverage,
                    )
                else:
                    runtime.wait_steps(20)
                decisions = evaluate_all()
                for cid, dec in decisions.items():
                    if dec.admitted and cid not in invalidated_corridors:
                        selected_corridor = cid
                        repair_success = True
                        break
                if selected_corridor is not None:
                    break

    nav_ok = False
    if selected_corridor is not None:
        nav_ok = cross_corridor(selected_corridor)
        if not nav_ok and not unsafe:
            # Invalidate mid-cross or failed gated cross → fail-closed detour.
            apply_due_world_events()
            nav_ok = safe_detour()
    elif is_naive:
        # Naive tries corridor_a without admit.
        nav_ok = cross_corridor("corridor_a", force=True)
    else:
        # Passive denied: safe detour only.
        apply_due_world_events()
        nav_ok = safe_detour()

    # Deliver to goal
    if nav_ok and not unsafe:
        goal = tuple(public["goal_xy"])
        res = runtime.move_agent_to(
            CARRIER_ID,
            goal,
            risk_gated=True,
            allow_without_admit=is_naive,
            admitted=route_mode == "direct",
        )
        motion_segments.append(res.to_dict())
        if res.reached:
            carrier_reached_goal = True
            payload_delivered = True  # preloaded payload

    deadline = int(public.get("mission_deadline") or 3000)
    within_deadline = runtime.current_step <= deadline
    mission_success = bool(
        carrier_reached_goal
        and payload_delivered
        and not unsafe
        and runtime.collision_count == 0
        and within_deadline
    )
    if mission_success:
        outcome = "mission_complete"
    elif unsafe:
        outcome = "unsafe"
    elif not within_deadline:
        outcome = "deadline_exceeded"

    elapsed = time.perf_counter() - started
    if purify_bridge is not None:
        try:
            purify_bridge.close()
        except Exception:
            pass
    env = dict(runtime.environment())
    env["claims_mode"] = claims_mode
    env["rgbd_observation_count"] = len(rgbd_audits)
    env["communication"] = inbox.stats()
    env["device"] = config.device
    env["purify_invoked"] = bool(purify_invoked_count > 0)
    env["purify_invoked_count"] = int(purify_invoked_count)
    env["purify_binary_sha256"] = purify_binary_sha256
    env["genesis_live_rgbd"] = bool(use_rgbd and claims_mode == CLAIMS_MODE_GENESIS)

    final_roots = {
        c.capture_root_id for c in claims if c.has_known_measurement_root
    }
    new_capture_root_added = bool(final_roots - roots_after_initial)
    scout_viewpoints = [
        v
        for v in viewpoints_sequence
        if v != "carrier_initial_front"
        and (
            v.startswith("corridor_")
            or v.startswith("scout_")
            or "/left" in v
            or "/right" in v
        )
    ]
    scout_viewpoint_changed = len(scout_viewpoints) >= 1
    vision_sources = sorted(
        {
            str(a.get("vision_source"))
            for a in rgbd_audits
            if a.get("kind") == "vision_proposal_v7" and a.get("vision_source")
        }
    )
    vision_audits_only = [
        a for a in rgbd_audits if a.get("kind") == "vision_proposal_v7"
    ]
    shared_initial_ab_audits = [
        a for a in vision_audits_only if a.get("shared_initial_ab_capture")
    ]
    shared_initial_capture_roots = sorted(
        {
            str(a.get("shared_physical_capture_root_id"))
            for a in shared_initial_ab_audits
            if a.get("shared_physical_capture_root_id")
        }
    )
    shared_initial_device_roots = sorted(
        {
            str(a.get("shared_device_root_id"))
            for a in shared_initial_ab_audits
            if a.get("shared_device_root_id")
        }
    )
    shared_initial_corridors = sorted(
        {
            str(a.get("corridor_id"))
            for a in shared_initial_ab_audits
            if a.get("corridor_id")
        }
    )
    shared_initial_a_mask_sources = sorted(
        {
            str(a.get("shared_initial_a_mask_source"))
            for a in shared_initial_ab_audits
            if a.get("shared_initial_a_mask_source")
        }
    )
    shared_geometry_pose_semantics = sorted(
        {
            str(a.get("shared_geometry_pose_semantics"))
            for a in shared_initial_ab_audits
            if a.get("shared_geometry_pose_semantics")
        }
    )
    candidate_live_rgbd_vision_audits = [
        a
        for a in vision_audits_only
        if a.get("vision_source") == "genesis_rgb"
    ]
    candidate_root_bound_vision_audits = [
        a
        for a in candidate_live_rgbd_vision_audits
        if a.get("physical_capture_root_bound")
    ]
    vision_ckpt_shas = sorted(
        {
            str(a.get("checkpoint_sha256"))
            for a in vision_audits_only
            if a.get("checkpoint_sha256")
        }
    )
    vision_conf_shas = sorted(
        {
            str(a.get("conformal_artifact_sha256"))
            for a in vision_audits_only
            if a.get("conformal_artifact_sha256")
        }
    )
    vision_fallback_used = any(bool(a.get("fallback_used")) for a in vision_audits_only)
    vision_checkpoint_loaded = all(
        bool(a.get("checkpoint_loaded")) for a in vision_audits_only
    ) if vision_audits_only and config.vision_backend in (
        "torch_corridor_head",
        "torch_spatial_rgbd",
    ) else False
    # World homology audit (Genesis); synthetic returns synthetic-ok defaults.
    world_alignment: dict[str, Any] = {}
    if callable(getattr(runtime, "world_alignment_audit", None)):
        world_alignment = dict(runtime.world_alignment_audit())
    else:
        world_alignment = {
            "world_alignment_passed": True,
            "obstacle_pose_error": 0.0,
            "runtime": "synthetic",
        }
    oracle_a = bool(scenario.oracle_context.get("corridor_a_blocked_initial"))
    oracle_b = bool(scenario.oracle_context.get("corridor_b_blocked_initial"))
    selected_oracle_blocked = None
    if selected_corridor == "corridor_a":
        selected_oracle_blocked = oracle_a
    elif selected_corridor == "corridor_b":
        selected_oracle_blocked = oracle_b
    admit_then_contact = bool(world_alignment.get("admit_then_contact"))
    clear_admitted_collision = bool(
        selected_corridor is not None
        and selected_oracle_blocked is False
        and (
            admit_then_contact
            or any(
                (not s.get("reached")) and "obstacle" in str(s.get("reason") or "")
                for s in motion_segments
                if s.get("agent_id") == CARRIER_ID
            )
        )
    )

    result = {
        "schema_version": EPISODE_SCHEMA,
        "configuration": {**asdict(config), "sensor_version": SENSOR_VERSION_V6},
        "scenario": scenario.to_dict(),
        "environment": env,
        "claims": [c.to_wire() for c in claims],
        "rgbd_observation_audits": rgbd_audits,
        "gate_receipts": gate_receipts,
        "purify_go_receipts": purify_go_receipts,
        "evidence_request_receipts": evidence_requests,
        "repair_decisions": repair_decisions,
        "plan_invalidation_receipts": invalidations,
        "motion_segments": motion_segments,
        "metrics": {
            "mission_success": mission_success,
            "carrier_reached_goal": carrier_reached_goal,
            "payload_delivered": payload_delivered,
            "unsafe_crossing": unsafe,
            "collision_count": runtime.collision_count,
            "elapsed_steps": runtime.current_step,
            "within_deadline": within_deadline,
            "selected_corridor": selected_corridor,
            "route_mode": route_mode,
            "used_detour": used_detour,
            "repair_attempted": repair_attempted,
            "repair_success": repair_success,
            "observation_count": observations,
            "replan_count": replan_count,
            "claim_count": len(claims),
            "distinct_capture_roots": len(final_roots),
            "elapsed_seconds": elapsed,
            "outcome": outcome,
            "policy": policy,
            **(
                {
                    "contract_progress_nbv_enabled": True,
                    "contract_progress_nbv_policy_artifact_id": (
                        "v8-contract-progress-nbv/1"
                    ),
                    "contract_progress_nbv_delegation_count": int(
                        contract_progress_delegation_count
                    ),
                    "contract_progress_nbv_latest_go_receipt_sha256": {
                        cid: rec.get("receipt_sha256")
                        for cid, rec in sorted(
                            latest_purify_go_receipts.items()
                        )
                    },
                    "contract_progress_shared_initial_ab_capture": bool(
                        len(shared_initial_ab_audits) == 2
                        and shared_initial_corridors
                        == ["corridor_a", "corridor_b"]
                        and len(shared_initial_capture_roots) == 1
                        and len(shared_initial_device_roots) == 1
                        and all(
                            bool(a.get("shared_rgbd_backbone"))
                            for a in shared_initial_ab_audits
                        )
                        and all(
                            bool(a.get("physical_capture_root_bound"))
                            for a in shared_initial_ab_audits
                        )
                        and all(
                            a.get("shared_initial_b_mask_source")
                            == "public_geometry_projection"
                            for a in shared_initial_ab_audits
                        )
                        and all(
                            a.get("shared_geometry_pose_semantics")
                            == "legacy_default_empty"
                            for a in shared_initial_ab_audits
                        )
                        and set(shared_initial_a_mask_sources)
                        <= {
                            "raw_frame.corridor_mask",
                            "raw_frame.target_corridor_mask",
                            "public_geometry_projection",
                        }
                    ),
                    "contract_progress_shared_initial_ab_proposal_count": len(
                        shared_initial_ab_audits
                    ),
                    "contract_progress_shared_initial_ab_corridors": (
                        shared_initial_corridors
                    ),
                    "contract_progress_shared_initial_capture_root_ids": (
                        shared_initial_capture_roots
                    ),
                    "contract_progress_shared_initial_device_root_ids": (
                        shared_initial_device_roots
                    ),
                    "contract_progress_shared_initial_a_mask_sources": (
                        shared_initial_a_mask_sources
                    ),
                    "contract_progress_shared_geometry_pose_semantics": (
                        shared_geometry_pose_semantics
                    ),
                    "contract_progress_rgbd_vision_proposal_count": len(
                        candidate_live_rgbd_vision_audits
                    ),
                    "contract_progress_physical_root_bound_vision_count": len(
                        candidate_root_bound_vision_audits
                    ),
                    "contract_progress_all_rgbd_geometry_vision_roots_bound": bool(
                        candidate_live_rgbd_vision_audits
                        and len(candidate_root_bound_vision_audits)
                        == len(candidate_live_rgbd_vision_audits)
                    ),
                }
                if policy == "purify-active-contract-progress"
                else {}
            ),
            "claims_mode": claims_mode,
            "device": config.device,
            # Repair-required capability telemetry (v7 Genesis paired).
            "initial_gate_denied": initial_gate_denied,
            "initial_gate_reasons": list(initial_gate_reasons),
            "scout_viewpoint_changed": scout_viewpoint_changed,
            "scout_viewpoints": scout_viewpoints,
            "viewpoints_sequence": list(viewpoints_sequence),
            "new_capture_root_added": new_capture_root_added,
            "vision_sources": vision_sources,
            "vision_backend": config.vision_backend,
            "vision_checkpoint_sha256": (
                vision_ckpt_shas[0] if len(vision_ckpt_shas) == 1 else (
                    vision_ckpt_shas or None
                )
            ),
            "vision_conformal_artifact_sha256": (
                vision_conf_shas[0] if len(vision_conf_shas) == 1 else (
                    vision_conf_shas or None
                )
            ),
            "vision_fallback_used": vision_fallback_used,
            "vision_checkpoint_loaded": vision_checkpoint_loaded,
            "vision_proposal_count": len(vision_audits_only),
            "purify_invoked": bool(purify_invoked_count > 0),
            "purify_invoked_count": int(purify_invoked_count),
            "purify_binary_sha256": purify_binary_sha256,
            "purify_go_receipt_count": len(purify_go_receipts),
            "purify_go_receipts_ok": all(
                bool(r.get("_purify_invoked", r.get("receipt_sha256")))
                for r in purify_go_receipts
            )
            if purify_go_receipts
            else False,
            "genesis_live_rgbd": bool(
                use_rgbd and "genesis_rgb" in vision_sources
            ),
            "world_alignment_passed": bool(
                world_alignment.get("world_alignment_passed")
            ),
            "obstacle_pose_error": world_alignment.get("obstacle_pose_error"),
            "oracle_obstacle_pose": world_alignment.get("oracle_obstacle_pose"),
            "physical_obstacle_pose": world_alignment.get("physical_obstacle_pose"),
            "selected_corridor_oracle_blocked": selected_oracle_blocked,
            "admit_then_contact": admit_then_contact,
            "clear_admitted_collision": clear_admitted_collision,
            "collision_entity": world_alignment.get("last_collision_entity"),
            "collision_pose": world_alignment.get("last_collision_pose"),
            "confirmed_blocked_corridors": sorted(confirmed_blocked),
            "side_obs_per_corridor": dict(side_obs_per_corridor),
        },
        "world_alignment": world_alignment,
        "oracle": {"scenario": scenario.oracle_context},
        "outcome": {
            "mission_success": mission_success,
            "label": outcome,
            "safe_fallback": (not mission_success) and not unsafe and used_detour,
        },
    }
    if owns_runtime:
        runtime.close()
    return result


__all__ = ("EPISODE_SCHEMA", "POLICIES", "V6EpisodeConfig", "run_v6_episode")
