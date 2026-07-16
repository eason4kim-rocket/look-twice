"""Look Twice v4 closed loop: Claim → Contract → repair → physical action."""

from __future__ import annotations

import math
import subprocess
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from purify_bridge import PurifyBridge
from repair_planner import BeliefGap, RepairPlanner, build_planning_context
from v4_claims import (
    ClaimScope,
    RobotClaim,
    build_robot_claim,
    canonical_sha256,
)
from v4_conformal import CalibrationArtifact, SeedRange
from v4_evidence import (
    SENSOR_VERSION,
    EvidenceCapture,
    process_evidence_frame,
)
from v4_motion import MotionResult
from v4_perception import ClaimProvenance, build_static_map_claim
from v4_policies import (
    POLICY_PURIFY_ACTIVE,
    POLICY_PURIFY_PASSIVE,
    POLICIES,
    PolicyDecision,
    decision_from_gate_receipt,
    evaluate_policy,
    get_policy_descriptor,
)
from v4_runtime import EpisodeRuntime
from v4_scenario import PROFILES, ScenarioSample


EPISODE_SCHEMA = "look-twice.episode/v4"
ACTION_CONTRACT_SCHEMA = "purify.robotics.action-contract/v1"
ID_PROFILES = tuple(profile for profile in PROFILES if profile != "ood-severity")
ABLATIONS = (
    "none",
    "no-ttl",
    "no-lineage-collapse",
    "no-conformal-calibration",
    "no-conflict-gate",
    "no-active-repair",
    "no-plan-invalidation",
)


def git_commit() -> str:
    import os

    pinned = os.environ.get("LOOK_TWICE_GIT_COMMIT", "").strip()
    if pinned and len(pinned) == 40 and all(
        character in "0123456789abcdef" for character in pinned
    ):
        return pinned
    pin_file = Path(__file__).resolve().parents[1] / ".git_commit"
    if pin_file.is_file():
        value = pin_file.read_text(encoding="utf-8").strip()
        if len(value) == 40 and all(
            character in "0123456789abcdef" for character in value
        ):
            return value
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def smoke_calibration_artifact(commit: str | None = None) -> CalibrationArtifact:
    """A clearly-labelled CI fixture; formal runs must load a fitted artifact."""
    dataset = {
        "purpose": "synthetic-ci-smoke-only",
        "profiles": list(ID_PROFILES),
        "seeds": [30000, 30049],
    }
    return CalibrationArtifact(
        artifact_id="cal_smoke_fixture_v4",
        alpha=0.05,
        class_quantiles={"clear": 0.25, "blocked": 0.25},
        applicable_profiles=ID_PROFILES,
        min_noise_intensity=0.0,
        max_noise_intensity=0.75,
        sensor_versions=(SENSOR_VERSION,),
        git_commit=commit or git_commit(),
        dataset_sha256=canonical_sha256(dataset),
        seed_ranges=(SeedRange(30000, 30049),),
    )


def cross_region_contract() -> dict[str, Any]:
    return {
        "schema_version": ACTION_CONTRACT_SCHEMA,
        "contract_id": "cross-inspection-region-v4",
        "action": "cross_region",
        "fact_id": "region:inspection-region",
        "predicate": "traversable",
        "scope": {
            "robot_id": "look-twice-amr",
            "payload_id": "payload-small",
            "region_id": "inspection-region",
        },
        "required_prediction_set": ["clear"],
        "max_evidence_age": 60,
        "min_distinct_measurement_roots": 2,
        "max_modality_skew": 2,
        "max_unresolved_conflicts": 0,
        "require_calibration_applicable": True,
    }


def detour_contract() -> dict[str, Any]:
    contract = cross_region_contract()
    contract.update(
        {
            "contract_id": "detour-inspection-region-v4",
            "action": "take_detour",
            "required_prediction_set": ["blocked"],
        }
    )
    return contract


@dataclass(frozen=True, slots=True)
class EpisodeConfig:
    policy: str
    device: str = "cpu"
    max_observations: int = 4
    max_replans: int = 2
    # Corridor return + gate approach often exceed 60 sim steps after admit;
    # short TTL flipped clear admits into repair_budget_exhausted wrong-detours.
    ttl_steps: int = 240
    evidence_dir: Path | None = None
    ablation: str = "none"

    def __post_init__(self) -> None:
        if self.policy not in POLICIES:
            raise ValueError(f"unsupported v4 policy: {self.policy}")
        if self.max_observations < 1 or self.max_replans < 0 or self.ttl_steps < 1:
            raise ValueError("episode limits must be positive")
        if self.ablation not in ABLATIONS:
            raise ValueError(f"unsupported ablation: {self.ablation}")
        if self.ablation != "none" and self.policy != POLICY_PURIFY_ACTIVE:
            raise ValueError("v4 component ablations require policy purify-active")


def _viewpoint_utility(
    candidate: Mapping[str, Any], start_xy: tuple[float, float]
) -> tuple[float, str]:
    distance = min(1.0, math.dist(start_xy, candidate["xy"]) / 4.0)
    value = (
        0.55 * float(candidate["predicted_coverage"])
        - 0.25 * distance
        - 0.30 * float(candidate["predicted_degradation"])
        - 0.50 * float(candidate["physical_risk"])
    )
    return value, str(candidate["name"])


def ordered_reachable_viewpoints(
    public_context: Mapping[str, Any], start_xy: tuple[float, float]
) -> list[Mapping[str, Any]]:
    """Return reachable viewpoints sorted by the frozen initial utility."""
    reachable = [
        candidate
        for candidate in public_context["candidate_viewpoints"]
        if candidate["reachable"]
    ]
    return sorted(
        reachable,
        key=lambda candidate: _viewpoint_utility(candidate, start_xy),
        reverse=True,
    )


def select_initial_viewpoint(
    public_context: Mapping[str, Any], start_xy: tuple[float, float]
):
    ordered = ordered_reachable_viewpoints(public_context, start_xy)
    return ordered[0] if ordered else None


def _candidate_by_name(public_context: Mapping[str, Any], name: str):
    for candidate in public_context["candidate_viewpoints"]:
        if candidate["name"] == name:
            return candidate
    raise KeyError(name)


def _blocked_is_qualified(receipt: Mapping[str, Any]) -> bool:
    if receipt.get("prediction_set") != ["blocked"]:
        return False
    if receipt.get("calibration_applicable") is not True:
        return False
    if receipt.get("unresolved_conflicts") != 0:
        return False
    for clause in receipt.get("clauses", ()):
        if clause.get("clause") == "prediction_set":
            continue
        if clause.get("passed") is not True:
            return False
    return True


def _receipt_gap_reasons(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(gap.get("reason"))
            for gap in receipt.get("belief_gaps", ())
            if gap.get("reason")
        )
    )


def _motion_record(label: str, start_step: int, result: MotionResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["label"] = label
    payload["start_step"] = start_step
    payload["end_step"] = start_step + result.elapsed_steps
    payload["trajectory"] = [
        {**point, "global_step": start_step + int(point["step"])}
        for point in payload["trajectory"]
    ]
    payload["controls"] = [
        {**control, "global_step": start_step + int(control["step"])}
        for control in payload["controls"]
    ]
    return payload


def run_v4_episode(
    *,
    scenario: ScenarioSample,
    runtime: EpisodeRuntime,
    calibration: CalibrationArtifact,
    config: EpisodeConfig,
    bridge: PurifyBridge | None = None,
) -> dict[str, Any]:
    """Run one paired episode.  Only the evaluator receives ``oracle_context``."""
    if scenario.profile not in PROFILES:
        raise ValueError("invalid scenario profile")
    descriptor = get_policy_descriptor(config.policy)
    if descriptor.requires_go_gate and bridge is None:
        raise ValueError(f"{config.policy} requires a live PurifyBridge")

    started = time.perf_counter()
    contract = cross_region_contract()
    blocked_contract = detour_contract()
    if config.ablation == "no-ttl":
        contract["max_evidence_age"] = 10**9
        blocked_contract["max_evidence_age"] = 10**9
    if config.ablation == "no-conflict-gate":
        contract["max_unresolved_conflicts"] = 10**6
        blocked_contract["max_unresolved_conflicts"] = 10**6
    gate_calibration = calibration
    if config.ablation == "no-conformal-calibration":
        gate_calibration = replace(
            calibration,
            artifact_id=calibration.artifact_id + "-fixed-threshold-ablation",
            class_quantiles={"clear": 0.18, "blocked": 0.18},
        )
    public_context = scenario.public_context
    planner = RepairPlanner(
        max_observations=config.max_observations,
        max_replans=config.max_replans,
    )
    all_claims: list[RobotClaim] = []
    captures: list[EvidenceCapture] = []
    oracle_observations: list[dict[str, Any]] = []
    gate_receipts: list[dict[str, Any]] = []
    invalidation_receipts: list[dict[str, Any]] = []
    repair_decisions: list[dict[str, Any]] = []
    policy_decisions: list[dict[str, Any]] = []
    motion_segments: list[dict[str, Any]] = []
    visited_actions: set[str] = set()
    route: list[str] = ["start"]
    replan_count = 0
    repair_attempted = False
    repair_success = False
    last_gate: dict[str, Any] | None = None
    last_plan_gate: dict[str, Any] | None = None
    current_viewpoint: Mapping[str, Any] | None = None
    last_capture: EvidenceCapture | None = None
    submitted_gate_claims: dict[str, RobotClaim] = {}

    map_scope = ClaimScope("look-twice-amr", "payload-small", "inspection-region")
    map_claim = build_static_map_claim(
        map_record=public_context["known_static_map"],
        value="clear",
        confidence=0.65,
        provenance=ClaimProvenance(
            fact_id="region:inspection-region",
            predicate="traversable",
            observed_step=0,
            valid_until_step=(10**9 if config.ablation == "no-ttl" else 180),
            device_root_id="static-map-server",
            capture_root_id="map:v4",
            calibration_id=SENSOR_VERSION,
            pose_version="map-frame-v4",
            scope=map_scope,
        ),
        map_version="static-map-v4",
    )
    all_claims.append(map_claim)

    def move(target_xy: tuple[float, float], label: str) -> MotionResult:
        start_step = runtime.current_step
        result = runtime.move_to(target_xy)
        motion_segments.append(_motion_record(label, start_step, result))
        route.append(label)
        return result

    def observe(
        candidate: Mapping[str, Any],
        *,
        action_kind: str,
        wait_steps: int = 10,
    ) -> EvidenceCapture:
        nonlocal current_viewpoint, last_capture
        target_xy = (float(candidate["xy"][0]), float(candidate["xy"][1]))
        movement = move(target_xy, str(candidate["name"]))
        if not movement.reached:
            raise RuntimeError(
                f"failed to reach evidence viewpoint {candidate['name']}: {movement.reason}"
            )
        runtime.wait_steps(wait_steps)
        raw = runtime.capture_raw(
            viewpoint=str(candidate["name"]),
            viewpoint_xy=target_xy,
            predicted_coverage=float(candidate["predicted_coverage"]),
        )
        capture = process_evidence_frame(
            raw,
            scenario,
            observation_index=len(captures),
            repair_action_kind=action_kind,
            device=config.device,
            ttl_steps=(10**9 if config.ablation == "no-ttl" else config.ttl_steps),
            evidence_dir=config.evidence_dir,
        )
        captures.append(capture)
        all_claims.extend(capture.claims)
        visited_actions.add(str(candidate["name"]))
        oracle_observations.append(
            {
                "capture_root_id": capture.capture_root_id,
                "observed_step": capture.observed_step,
                "true_label": (
                    "blocked"
                    if scenario.truth_blocked_at(capture.observed_step)
                    else "clear"
                ),
                "scenario_id": scenario.scenario_id,
            }
        )
        current_viewpoint = candidate
        last_capture = capture
        return capture

    def claims_for_gate() -> tuple[RobotClaim, ...]:
        if config.ablation != "no-lineage-collapse":
            submitted = tuple(all_claims)
        else:
            transformed: list[RobotClaim] = []
            for claim in all_claims:
                if not claim.is_physical_measurement:
                    transformed.append(claim)
                    continue
                transformed.append(
                    build_robot_claim(
                        fact_id=claim.fact_id,
                        predicate=claim.predicate,
                        value=claim.value,
                        confidence=claim.confidence,
                        observed_step=claim.observed_step,
                        valid_until_step=claim.valid_until_step,
                        modality=claim.modality,
                        device_root_id=claim.device_root_id,
                        capture_root_id=f"lineage-ablation:{claim.claim_id}",
                        calibration_id=claim.calibration_id,
                        pose_version=claim.pose_version,
                        model_id=claim.model_id + "+no-lineage",
                        artifact_sha256=canonical_sha256(
                            {"ablation": "no-lineage-collapse", "claim_id": claim.claim_id}
                        ),
                        parent_claim_ids=(),
                        quality=claim.quality,
                        visibility=claim.visibility,
                        temporal_skew=claim.temporal_skew,
                        scope=claim.scope,
                    )
                )
            submitted = tuple(transformed)
        for claim in submitted:
            submitted_gate_claims[claim.claim_id] = claim
        return submitted

    def evaluate_current() -> PolicyDecision:
        nonlocal last_gate, last_plan_gate
        if descriptor.requires_go_gate:
            assert bridge is not None and last_capture is not None
            receipt = bridge.evaluate_action(
                claims=claims_for_gate(),
                contract=contract,
                calibration=gate_calibration,
                current_step=runtime.current_step,
                profile=scenario.profile,
                noise_intensity=last_capture.corruption.declared_noise_intensity,
                sensor_version=last_capture.corruption.sensor_version,
            )
            gate_receipts.append(receipt)
            last_gate = receipt
            if _blocked_is_qualified(receipt):
                blocked_receipt = bridge.evaluate_action(
                    claims=claims_for_gate(),
                    contract=blocked_contract,
                    calibration=gate_calibration,
                    current_step=runtime.current_step,
                    profile=scenario.profile,
                    noise_intensity=last_capture.corruption.declared_noise_intensity,
                    sensor_version=last_capture.corruption.sensor_version,
                )
                gate_receipts.append(blocked_receipt)
                if blocked_receipt.get("admitted") is True:
                    last_plan_gate = blocked_receipt
                decision = PolicyDecision(
                    action="safe_fallback",
                    resolved_value="blocked",
                    prediction_set=("blocked",),
                    reason="qualified_blocked_requires_detour",
                    diagnostics={
                        "receipt_id": receipt["receipt_id"],
                        "receipt_sha256": receipt["receipt_sha256"],
                        "safe_fallback": False,
                    },
                )
            else:
                decision = decision_from_gate_receipt(
                    config.policy,
                    gate_receipt=receipt,
                    current_step=runtime.current_step,
                )
                if receipt.get("admitted") is True:
                    last_plan_gate = receipt
        else:
            decision = evaluate_policy(
                config.policy,
                claims=all_claims,
                calibration=calibration,
                current_step=runtime.current_step,
            )
        policy_decisions.append(
            {"step": runtime.current_step, **decision.to_dict()}
        )
        return decision

    def repair_until_decisive(initial: PolicyDecision) -> PolicyDecision:
        nonlocal replan_count, repair_attempted, repair_success
        decision = initial
        while decision.action == "observe":
            if len(captures) >= config.max_observations:
                return PolicyDecision(
                    "safe_fallback",
                    "unresolved",
                    ("clear", "blocked"),
                    "repair_budget_exhausted",
                    {"safe_fallback": True},
                )
            assert last_gate is not None and current_viewpoint is not None
            gap_reasons = list(_receipt_gap_reasons(last_gate))
            # The core reports low_coverage when every prior Claim is stale and
            # therefore no usable root remains.  That is an absence-of-freshness
            # gap, not evidence that the current physical viewpoint is poor.
            # Keep the causes distinct so TTL repair can use a local recapture.
            if (
                "stale" in gap_reasons
                and "low_coverage" in gap_reasons
                and not last_gate.get("measurement_root_ids")
            ):
                gap_reasons.remove("low_coverage")
            gap = BeliefGap.from_reasons(gap_reasons)
            context = build_planning_context(
                public_context=public_context,
                current_step=runtime.current_step,
                current_xy=(runtime.current_pose.x, runtime.current_pose.y),
                current_viewpoint_name=str(current_viewpoint["name"]),
                current_predicted_coverage=float(
                    current_viewpoint["predicted_coverage"]
                ),
                current_predicted_degradation=float(
                    current_viewpoint["predicted_degradation"]
                ),
                current_physical_risk=float(current_viewpoint["physical_risk"]),
                visited_actions=visited_actions,
                observations_taken=len(captures),
                replans_taken=replan_count,
            )
            planned = planner.choose(gap, context)
            repair_decisions.append(
                {"step": runtime.current_step, "belief_gap": list(gap.reasons), **planned.to_dict()}
            )
            if planned.selected_action is None:
                return PolicyDecision(
                    "safe_fallback",
                    "unresolved",
                    ("clear", "blocked"),
                    planned.reason,
                    {"safe_fallback": True},
                )
            repair_attempted = True
            action = planned.selected_action
            if action.kind == "side_view":
                replan_count += 1
            visited_actions.add(action.name)
            if action.wait_steps:
                runtime.wait_steps(action.wait_steps)
            if action.kind == "side_view":
                candidate = _candidate_by_name(public_context, action.name)
            else:
                candidate = current_viewpoint
            try:
                observe(candidate, action_kind=action.kind)
            except RuntimeError as exc:
                # A blocked side view is a failed repair attempt, not a process crash.
                return PolicyDecision(
                    "safe_fallback",
                    "unresolved",
                    ("clear", "blocked"),
                    "repair_viewpoint_unreachable",
                    {"safe_fallback": True, "viewpoint_error": str(exc)},
                )
            decision = evaluate_current()
            if decision.action != "observe":
                repair_success = True
        return decision

    start_xy = (runtime.current_pose.x, runtime.current_pose.y)
    ordered_initials = ordered_reachable_viewpoints(public_context, start_xy)
    if not ordered_initials:
        final_decision = PolicyDecision(
            "safe_fallback",
            "unresolved",
            ("clear", "blocked"),
            "no_reachable_viewpoint",
            {"safe_fallback": True},
        )
    else:
        # Prefer the planner ranking, then fall back through remaining reachable
        # viewpoints so a single kinematic contact does not abort the episode.
        attempt_errors: list[str] = []
        observed = False
        for candidate in ordered_initials:
            try:
                observe(candidate, action_kind="initial")
                observed = True
                break
            except RuntimeError as exc:
                attempt_errors.append(str(exc))
        if not observed:
            final_decision = PolicyDecision(
                "safe_fallback",
                "unresolved",
                ("clear", "blocked"),
                "no_reachable_viewpoint",
                {
                    "safe_fallback": True,
                    "viewpoint_errors": attempt_errors,
                },
            )
        else:
            final_decision = evaluate_current()
            if descriptor.allows_repair and config.ablation != "no-active-repair":
                final_decision = repair_until_decisive(final_decision)
            elif final_decision.action == "observe":
                final_decision = PolicyDecision(
                    "safe_fallback",
                    "unresolved",
                    ("clear", "blocked"),
                    "active_repair_ablation",
                    {"safe_fallback": True},
                )

    # Move to the route commitment boundary.  An admitted receipt is checked
    # again there; expiry produces a signed invalidation before any crossing.
    used_detour = final_decision.action != "cross_region"
    plan_invalidation_expected = False
    plan_invalidation_correct: bool | None = None
    if final_decision.action == "cross_region":
        # Side-view repairs leave the chassis off-corridor. A straight cut to the
        # gate crosses the standing occluder slab near x≈0. Retreat behind it
        # (x≈-1.8), re-center y, then advance along the lane.
        cy = float(runtime.current_pose.y)
        move((-1.85, cy), "corridor_retreat_x")
        move((-1.85, 0.0), "corridor_recenter_y")
        move((-0.55, 0.0), "corridor_stage")
        boundary = move((0.30, 0.0), "pre_cross_gate")
        if not boundary.reached:
            final_decision = PolicyDecision(
                "safe_fallback",
                "unresolved",
                ("clear", "blocked"),
                "pre_gate_unreachable",
                {"safe_fallback": True},
            )
            used_detour = True
        elif descriptor.requires_go_gate and last_plan_gate is not None:
            # The sensor is rigidly mounted on the chassis, so after reaching
            # the boundary a local recapture means the current pose—not a trip
            # back to the previous named side viewpoint.
            current_viewpoint = {
                "name": "pre_cross_gate",
                "xy": [runtime.current_pose.x, runtime.current_pose.y],
                "reachable": True,
                "predicted_coverage": 0.90,
                "predicted_degradation": 0.16,
                "physical_risk": 0.03,
            }
            assert bridge is not None
            plan_invalidation_expected = runtime.current_step > int(
                last_plan_gate["valid_until_step"]
            )
            if config.ablation == "no-plan-invalidation":
                invalidation = {
                    "invalidated": False,
                    "reasons": ["ablation_disabled"],
                    "previous_receipt_sha256": last_plan_gate["receipt_sha256"],
                }
                plan_invalidation_correct = not plan_invalidation_expected
            else:
                invalidation = bridge.invalidate_plan(
                    previous_receipt=last_plan_gate,
                    current_step=runtime.current_step,
                    triggering_claims=(),
                )
                plan_invalidation_correct = bool(invalidation["invalidated"]) == bool(
                    plan_invalidation_expected
                )
            invalidation_receipts.append(invalidation)
            if invalidation["invalidated"]:
                if descriptor.allows_repair:
                    # Local recapture at the gate before spending remaining budget
                    # on distant side views (capability: keep clear admits alive).
                    if len(captures) < config.max_observations:
                        try:
                            observe(current_viewpoint, action_kind="same_view")
                        except RuntimeError:
                            pass
                    stale_decision = evaluate_current()
                    if stale_decision.action == "observe":
                        final_decision = repair_until_decisive(stale_decision)
                    else:
                        final_decision = stale_decision
                    used_detour = final_decision.action != "cross_region"
                else:
                    final_decision = PolicyDecision(
                        "safe_fallback",
                        "unresolved",
                        ("clear", "blocked"),
                        "plan_invalidated_without_active_repair",
                        {"safe_fallback": True},
                    )
                    used_detour = True

    elif (
        final_decision.resolved_value == "blocked"
        and descriptor.requires_go_gate
        and last_plan_gate is not None
    ):
        boundary = move((0.30, 0.0), "pre_detour_gate")
        if boundary.reached:
            current_viewpoint = {
                "name": "pre_detour_gate",
                "xy": [runtime.current_pose.x, runtime.current_pose.y],
                "reachable": True,
                "predicted_coverage": 0.90,
                "predicted_degradation": 0.16,
                "physical_risk": 0.03,
            }
            assert bridge is not None
            plan_invalidation_expected = runtime.current_step > int(
                last_plan_gate["valid_until_step"]
            )
            if config.ablation == "no-plan-invalidation":
                invalidation = {
                    "invalidated": False,
                    "reasons": ["ablation_disabled"],
                    "previous_receipt_sha256": last_plan_gate["receipt_sha256"],
                }
                plan_invalidation_correct = not plan_invalidation_expected
            else:
                invalidation = bridge.invalidate_plan(
                    previous_receipt=last_plan_gate,
                    current_step=runtime.current_step,
                    triggering_claims=(),
                )
                plan_invalidation_correct = bool(invalidation["invalidated"]) == bool(
                    plan_invalidation_expected
                )
            invalidation_receipts.append(invalidation)
            if invalidation["invalidated"] and descriptor.allows_repair:
                # Capability/safety: a qualified-blocked plan that only expired by
                # TTL must not flip to cross from a near-gate recapture on static
                # profiles (false clear depth near the obstacle → unsafe). Only
                # dynamic-change is allowed to re-open crossing after blocked.
                if scenario.profile != "dynamic-change":
                    final_decision = PolicyDecision(
                        "safe_fallback",
                        "blocked",
                        ("blocked",),
                        "blocked_plan_expired_keep_detour",
                        {"safe_fallback": True},
                    )
                    used_detour = True
                else:
                    stale_decision = evaluate_current()
                    final_decision = repair_until_decisive(stale_decision)
                    used_detour = final_decision.action != "cross_region"
        else:
            final_decision = PolicyDecision(
                "safe_fallback",
                "unresolved",
                ("clear", "blocked"),
                "pre_detour_gate_unreachable",
                {"safe_fallback": True},
            )

    unsafe_crossing = False
    mission_success = True
    if final_decision.action == "cross_region":
        before_collision = runtime.collision_count
        crossing = move((0.85, 0.0), "cross_region")
        unsafe_crossing = (
            runtime.collision_count > before_collision
            or scenario.truth_blocked_at(runtime.current_step)
        )
        mission_success = crossing.reached and not unsafe_crossing
        if mission_success:
            mission_success = move((2.0, 0.0), "goal").reached
    else:
        used_detour = True
        # Same retreat as admitted-cross staging: after side-view repair the
        # chassis may sit behind the FOV occluder; cut-through detours fail and
        # make active look worse than naive on safe_success despite safer gates.
        cy = float(runtime.current_pose.y)
        if abs(cy) > 0.45 or float(runtime.current_pose.x) > -0.8:
            move((-1.85, cy), "detour_retreat_x")
            move((-1.85, 0.0), "detour_recenter_y")
        for target, label in (
            ((-0.05, 1.25), "detour_entry"),
            ((0.90, 1.50), "detour_waypoint"),
            ((2.0, 0.0), "goal"),
        ):
            movement = move(target, label)
            if not movement.reached:
                mission_success = False
                break

    final_truth = "blocked" if scenario.truth_blocked_at(runtime.current_step) else "clear"
    wrong_detour = used_detour and final_truth == "clear"
    last_prediction_set = list(final_decision.prediction_set)
    p_clear = None
    if last_gate is not None:
        p_clear = 1.0 - float(last_gate["p_blocked"])
        last_prediction_set = list(last_gate["prediction_set"])
    elif "p_clear" in final_decision.diagnostics:
        p_clear = float(final_decision.diagnostics["p_clear"])

    echo_present = scenario.profile == "evidence-echo"
    echo_rejection_success: bool | None = None
    if echo_present and descriptor.requires_go_gate:
        discounted_reasons = [
            item.get("reason", "")
            for receipt in gate_receipts
            for item in receipt.get("discounted_claims", ())
        ]
        echo_rejection_success = any(
            reason.startswith("artifact_duplicate_of:")
            for reason in discounted_reasons
        )

    elapsed = time.perf_counter() - started
    path_length = sum(float(segment["path_length"]) for segment in motion_segments)
    result = {
        "schema_version": EPISODE_SCHEMA,
        "git_commit": git_commit(),
        "configuration": {
            **asdict(config),
            "evidence_dir": str(config.evidence_dir) if config.evidence_dir else None,
            "alpha": calibration.alpha,
            "calibration_artifact_id": calibration.artifact_id,
        },
        "scenario": scenario.to_dict(),
        "environment": runtime.environment,
        "action_contracts": [contract, blocked_contract],
        "calibration_artifact": calibration.to_wire(),
        "gate_calibration_artifact": gate_calibration.to_wire(),
        "claims": [claim.to_wire() for claim in all_claims],
        "gate_submitted_claims": [
            submitted_gate_claims[claim_id].to_wire()
            for claim_id in sorted(submitted_gate_claims)
        ],
        "evidence": [capture.online_record() for capture in captures],
        "gate_receipts": gate_receipts,
        "repair_decisions": repair_decisions,
        "plan_invalidation_receipts": invalidation_receipts,
        "policy_decisions": policy_decisions,
        "motion_segments": motion_segments,
        "oracle": {
            "scenario": scenario.oracle_context,
            "observations": oracle_observations,
        },
        "metrics": {
            "unsafe_crossing": unsafe_crossing,
            "safe_success": mission_success and not unsafe_crossing,
            "wrong_detour": wrong_detour,
            "contract_repair_attempted": repair_attempted,
            "contract_repair_success": repair_success if repair_attempted else None,
            "plan_invalidation_expected": plan_invalidation_expected,
            "plan_invalidation_correct": plan_invalidation_correct,
            "echo_present": echo_present,
            "echo_rejection_success": echo_rejection_success,
            "p_clear": p_clear,
            "true_label": final_truth,
            "prediction_set": last_prediction_set,
            "observation_count": len(captures),
            "replan_count": replan_count,
            "path_length": path_length,
            "collision_count": runtime.collision_count,
            "elapsed_seconds": elapsed,
            "simulation_steps": runtime.current_step,
        },
        "outcome": {
            "mission_success": mission_success,
            "route": route,
            "used_detour": used_detour,
            "decision": final_decision.to_dict(),
            "safe_fallback": (
                used_detour and final_decision.resolved_value == "unresolved"
            ),
            "final_truth": final_truth,
        },
    }
    return result


__all__ = (
    "EPISODE_SCHEMA",
    "ABLATIONS",
    "EpisodeConfig",
    "cross_region_contract",
    "detour_contract",
    "ordered_reachable_viewpoints",
    "run_v4_episode",
    "select_initial_viewpoint",
    "smoke_calibration_artifact",
)
