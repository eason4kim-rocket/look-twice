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
from v6_motion import MultiAgentKinematicRuntime, build_runtime_from_scenario
from v6_repair import choose_evidence_action
from v6_scenario import CARRIER_ID, PAYLOAD_ID, SCOUT_ID, V6ScenarioSample

EPISODE_SCHEMA = "look-twice.episode/v6"
POLICIES = ("naive", "purify-passive", "purify-active")
CLAIMS_MODE_SYNTHETIC = "synthetic_multi_agent_v6"
CLAIMS_MODE_GENESIS = "genesis_rgbd_multi_agent_v6"


@dataclass
class V6EpisodeConfig:
    policy: str = "purify-active"
    ttl_steps: int = 2000
    max_observations: int = 6
    max_replans: int = 3
    device: str = "cpu"
    prefer_rgbd_claims: bool = True

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

    policy = config.policy
    is_naive = policy == "naive"
    allows_repair = policy == "purify-active"
    requires_gate = policy in ("purify-passive", "purify-active")

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
        if use_rgbd:
            from v5_rgbd_claims import process_genesis_observation

            raw = runtime.capture_raw(
                agent_id=agent_id,
                viewpoint=viewpoint_name,
                viewpoint_xy=target_xy,
                predicted_coverage=predicted_coverage,
            )
            v1_claims, audit = process_genesis_observation(
                raw,
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
        capture_index += 1
        observations += 1
        visited.add(viewpoint_name)
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

    def evaluate_all() -> dict[str, Any]:
        decisions = {}
        for cid, contract in contracts.items():
            dec = evaluate_corridor_contract(
                claims, contract, current_step=runtime.current_step
            )
            decisions[cid] = dec
            gate_receipts.append(dec.to_wire())
        return decisions

    decisions = evaluate_all()
    admitted_any = any(d.admitted for d in decisions.values())

    # Active repair loop
    if requires_gate and not admitted_any and allows_repair:
        repair_attempted = True
        for _ in range(config.max_observations):
            # Prefer the best denied corridor's gaps (corridor_a first).
            primary = decisions.get("corridor_a") or next(iter(decisions.values()))
            gaps = [g.get("reason", "insufficient_roots") for g in primary.belief_gaps]
            if not gaps:
                gaps = list(primary.reasons) or ["insufficient_roots"]
            carrier_xy = (
                runtime.pose_of(CARRIER_ID).x,
                runtime.pose_of(CARRIER_ID).y,
            )
            scout_xy = (runtime.pose_of(SCOUT_ID).x, runtime.pose_of(SCOUT_ID).y)
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
        dec = evaluate_corridor_contract(
            claims, contracts[cid], current_step=runtime.current_step
        )
        gate_receipts.append(dec.to_wire())
        return bool(dec.admitted)

    # Choose admitted corridor, else safest detour.
    for cid, dec in decisions.items():
        if dec.admitted and cid not in invalidated_corridors:
            selected_corridor = cid
            break

    def cross_corridor(cid: str, *, force: bool = False) -> bool:
        nonlocal unsafe, route_mode, selected_corridor
        contract = contracts[cid]
        region = next(c["region"] for c in public["corridors"] if c["id"] == cid)
        entry = (float(region[0]) - 0.05, 0.5 * (float(region[2]) + float(region[3])))
        mid = (0.5 * (float(region[0]) + float(region[1])), entry[1])
        exit_xy = (float(region[1]) + 0.1, entry[1])
        admitted = force or live_admit(cid)
        if requires_gate and not admitted and not force:
            return False
        for target, label in ((entry, "entry"), (mid, "mid"), (exit_xy, "exit")):
            # Absolute schedule may flip the world mid-crossing.
            if apply_due_world_events() and cid in invalidated_corridors and not force:
                selected_corridor = None
                return False
            res = runtime.move_agent_to(
                CARRIER_ID,
                target,
                risk_gated=True,
                allow_without_admit=is_naive or force,
                admitted=(force or live_admit(cid)),
            )
            motion_segments.append(res.to_dict())
            if not res.reached:
                return False
            # Unsafe if truth blocked while in corridor.
            if scenario.truth_corridor_blocked(cid, runtime.current_step):
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
                primary = next(iter(decisions.values()))
                gaps = [
                    g.get("reason", "insufficient_roots") for g in primary.belief_gaps
                ] or list(primary.reasons) or ["insufficient_roots"]
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
            "distinct_capture_roots": len(
                {c.capture_root_id for c in claims if c.has_known_measurement_root}
            ),
            "elapsed_seconds": elapsed,
            "outcome": outcome,
            "policy": policy,
            "claims_mode": claims_mode,
            "device": config.device,
        },
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
