"""v6 dual-agent closed loop: carrier transport under Purify-governed evidence repair."""

from __future__ import annotations

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
    "purify-active-learned",
    "purify-active-dagger",
    "purify-random",
)
CLAIMS_MODE_SYNTHETIC = "synthetic_multi_agent_v6"
CLAIMS_MODE_GENESIS = "genesis_rgbd_multi_agent_v6"
ACTIVE_REPAIR_POLICIES = frozenset(
    {
        "purify-active",
        "purify-active-learned",
        "purify-active-dagger",
        "purify-random",
    }
)
GATED_POLICIES = frozenset(
    {
        "purify-passive",
        "purify-active",
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
                device_root_id=f"rgbd-{agent_id}-01",
                capture_root_id=str(claim.capture_root_id),
                calibration_id=SENSOR_VERSION_V6,
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
                calibration_id=SENSOR_VERSION_V6,
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

    contracts = {
        c["id"]: CorridorContract(
            corridor_id=c["id"],
            evidence_age_limit=int(public.get("evidence_age_limit") or 80),
            min_distinct_capture_roots=int(public.get("min_distinct_capture_roots") or 2),
            communication_delay_limit=int(public.get("communication_delay_limit") or 40),
        )
        for c in public["corridors"]
    }

    claims: list[RobotClaimV2] = []
    gate_receipts: list[dict[str, Any]] = []
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

    policy = config.policy
    is_naive = policy == "naive"
    allows_repair = policy in ACTIVE_REPAIR_POLICIES
    requires_gate = policy in GATED_POLICIES
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
            )
        # Optional v7 vision proposer (appends; does not replace geometry claims).
        if config.vision_enabled:
            from v7_vision_claims import (
                propose_vision,
                synthetic_rgb_for_label,
                vision_proposal_to_claim_v2,
            )

            rgb = None
            depth = None
            vision_source = "synthetic_rgb_proxy"
            if raw_frame is not None:
                rgb = getattr(raw_frame, "rgb", None)
                depth = getattr(raw_frame, "depth", None)
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
            vision_device = (
                config.device if str(config.device).startswith("cuda") else "cpu"
            )
            # Formal torch mode is fail-closed: missing ckpt/conformal or load
            # mismatch raises and fails the episode (no silent heuristic).
            prop = propose_vision(
                rgb,
                depth=depth,
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
                },
            )
            root_kind = _vision_root_kind(agent_id, viewpoint_name, capture_index)
            vclaim = vision_proposal_to_claim_v2(
                prop,
                agent_id=agent_id,
                corridor_id=corridor_id,
                step=runtime.current_step,
                ttl=config.ttl_steps,
                capture_root_id=(
                    f"vision-{root_kind}-{agent_id}-{capture_index}-"
                    f"{prop.input_sha256[:10]}"
                ),
            )
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

    def evaluate_all() -> dict[str, Any]:
        decisions = {}
        for cid, contract in contracts.items():
            dec = _evaluate_gate(
                claims, contract, current_step=runtime.current_step, config=config
            )
            decisions[cid] = dec
            gate_receipts.append(dec.to_wire())
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
            if policy in ("purify-active-learned", "purify-active-dagger") and learned_model is not None:
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
                selected_action=selected.to_dict() if selected else None,
                current_step=runtime.current_step,
                observations_taken=observations,
                replans_taken=replan_count,
                max_observations=config.max_observations,
                max_replans=config.max_replans,
                candidate_ranking=ranking,
            )
            evidence_requests.append(receipt.to_wire())
            repair_decisions.append(
                {
                    "selected": None if selected is None else selected.to_dict(),
                    "ranking_head": ranking[:5],
                    "authorized": receipt.authorized,
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
                    selected_action=selected.to_dict() if selected else None,
                    current_step=runtime.current_step,
                    observations_taken=observations,
                    replans_taken=replan_count,
                    max_observations=config.max_observations,
                    max_replans=config.max_replans,
                    candidate_ranking=ranking,
                )
                evidence_requests.append(receipt.to_wire())
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
    env = dict(runtime.environment())
    env["claims_mode"] = claims_mode
    env["rgbd_observation_count"] = len(rgbd_audits)
    env["communication"] = inbox.stats()
    env["device"] = config.device

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
    ) if vision_audits_only and config.vision_backend == "torch_corridor_head" else False
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
