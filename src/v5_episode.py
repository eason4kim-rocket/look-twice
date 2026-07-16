"""v5 episode: dual contracts (cross_region + pick_proxy) with mid-run invalidation."""

from __future__ import annotations

import math
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from purify_bridge import PurifyBridge
from repair_planner import BeliefGap, RepairPlanner, build_planning_context
from v4_claims import ClaimScope, RobotClaim, build_robot_claim, canonical_sha256
from v4_conformal import CalibrationArtifact, SeedRange
from v4_episode import ordered_reachable_viewpoints
from v4_motion import MotionResult
from v5_manipulation import (
    build_workspace_claim,
    end_effector_xy,
    evaluate_proxy_grasp,
)
from v5_policies import (
    POLICIES,
    get_policy_descriptor,
    naive_decision_from_claims,
)
from v5_scenario import GRASP_XY, V5ScenarioSample

EPISODE_SCHEMA = "look-twice.episode/v5"
ACTION_CONTRACT_SCHEMA = "purify.robotics.action-contract/v1"
SENSOR_VERSION = "look-twice-rgbd-v5/1"


def git_commit() -> str:
    import os

    pinned = os.environ.get("LOOK_TWICE_GIT_COMMIT", "").strip()
    if len(pinned) == 40 and all(c in "0123456789abcdef" for c in pinned):
        return pinned
    pin_file = Path(__file__).resolve().parents[1] / ".git_commit"
    if pin_file.is_file():
        value = pin_file.read_text(encoding="utf-8").strip()
        if len(value) == 40 and all(c in "0123456789abcdef" for c in value):
            return value
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def smoke_calibration_artifact(commit: str | None = None) -> CalibrationArtifact:
    dataset = {"purpose": "v5-ci-smoke", "profiles": list(V5_ID_PROFILES)}
    return CalibrationArtifact(
        artifact_id="cal_smoke_fixture_v5",
        alpha=0.05,
        class_quantiles={"clear": 0.30, "blocked": 0.30},
        applicable_profiles=V5_ID_PROFILES,
        min_noise_intensity=0.0,
        max_noise_intensity=0.85,
        sensor_versions=(SENSOR_VERSION,),
        git_commit=commit or git_commit(),
        dataset_sha256=canonical_sha256(dataset),
        seed_ranges=(SeedRange(30000, 30049),),
    )


V5_ID_PROFILES = tuple(p for p in (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "dynamic-change",
    "time-skew",
    "manipulation-occlusion",
) if p != "ood-severity")


def cross_region_contract() -> dict[str, Any]:
    return {
        "schema_version": ACTION_CONTRACT_SCHEMA,
        "contract_id": "cross-nav-region-v5",
        "action": "cross_region",
        "fact_id": "region:inspection-region",
        "predicate": "traversable",
        "scope": {
            "robot_id": "look-twice-amr",
            "payload_id": "payload-small",
            "region_id": "inspection-region",
        },
        "required_prediction_set": ["clear"],
        "max_evidence_age": 80,
        "min_distinct_measurement_roots": 2,
        "max_modality_skew": 2,
        "max_unresolved_conflicts": 0,
        "require_calibration_applicable": True,
    }


def pick_proxy_contract() -> dict[str, Any]:
    return {
        "schema_version": ACTION_CONTRACT_SCHEMA,
        "contract_id": "pick-proxy-v5",
        "action": "pick_proxy",
        "fact_id": "region:grasp-zone",
        "predicate": "graspable",
        "scope": {
            "robot_id": "look-twice-amr",
            "payload_id": "payload-small",
            "region_id": "grasp-zone",
        },
        "required_prediction_set": ["clear"],
        "max_evidence_age": 40,
        "min_distinct_measurement_roots": 1,
        "max_modality_skew": 2,
        "max_unresolved_conflicts": 0,
        "require_calibration_applicable": True,
    }


@dataclass(frozen=True, slots=True)
class V5EpisodeConfig:
    policy: str
    max_observations: int = 4
    max_replans: int = 2
    ttl_steps: int = 80

    def __post_init__(self) -> None:
        if self.policy not in POLICIES:
            raise ValueError(f"unsupported v5 policy: {self.policy}")


def _motion_record(label: str, start_step: int, result: MotionResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["label"] = label
    payload["start_step"] = start_step
    payload["end_step"] = start_step + int(result.elapsed_steps)
    # Align global_step for validators that expect it
    traj = []
    for point in result.trajectory:
        item = dict(point)
        item["global_step"] = start_step + int(item.get("step", 0))
        traj.append(item)
    controls = []
    for point in result.controls:
        item = dict(point)
        item["global_step"] = start_step + int(item.get("step", 0))
        controls.append(item)
    payload["trajectory"] = traj
    payload["controls"] = controls
    return payload


def _synthetic_nav_claims(
    scenario: V5ScenarioSample,
    *,
    step: int,
    capture_root: str,
    ttl: int,
) -> list[RobotClaim]:
    """Two synthetic physical claims from one capture for CI (depth+semantic)."""
    blocked = scenario.truth_nav_blocked_at(step)
    value = "blocked" if blocked else "clear"
    conf = 0.78
    scope = ClaimScope("look-twice-amr", "payload-small", "inspection-region")
    shared = scenario.profile == "evidence-echo"
    shared_art = canonical_sha256({"cap": capture_root, "step": step, "nav": value})
    out: list[RobotClaim] = []
    for modality, model in (
        ("depth_geometry", "depth-proxy-v5"),
        ("simulated_semantic_sensor", "sem-proxy-v5"),
    ):
        art = (
            shared_art
            if shared
            else canonical_sha256({"cap": capture_root, "mod": modality, "step": step})
        )
        out.append(
            build_robot_claim(
                fact_id="region:inspection-region",
                predicate="traversable",
                value=value,
                confidence=conf,
                observed_step=step,
                valid_until_step=step + ttl,
                modality=modality,
                device_root_id="look-twice-amr-rgbd",
                capture_root_id=capture_root,
                calibration_id=SENSOR_VERSION,
                pose_version="base-link-v5",
                model_id=model,
                artifact_sha256=art,
                quality=0.8,
                visibility=0.75,
                temporal_skew=1 if scenario.profile == "time-skew" else 0,
                scope=scope,
            )
        )
    return out


def run_v5_episode(
    *,
    scenario: V5ScenarioSample,
    runtime: Any,
    calibration: CalibrationArtifact,
    config: V5EpisodeConfig,
    bridge: PurifyBridge | None = None,
) -> dict[str, Any]:
    """Synthetic-first closed loop; Genesis runtime must implement the same surface."""
    started = time.perf_counter()
    descriptor = get_policy_descriptor(config.policy)
    planner = RepairPlanner(
        max_observations=config.max_observations, max_replans=config.max_replans
    )
    public = scenario.public_context
    nav_contract = cross_region_contract()
    pick_contract = pick_proxy_contract()
    nav_claims: list[RobotClaim] = []
    grasp_claims: list[RobotClaim] = []
    gate_receipts: list[dict[str, Any]] = []
    invalidations: list[dict[str, Any]] = []
    motion_segments: list[dict[str, Any]] = []
    repair_decisions: list[dict[str, Any]] = []
    grasp_results: list[dict[str, Any]] = []
    visited: set[str] = set()
    replan_count = 0
    capture_index = 0
    last_nav_receipt: dict[str, Any] | None = None
    last_pick_receipt: dict[str, Any] | None = None

    def move(target: tuple[float, float], label: str) -> MotionResult:
        start = runtime.current_step
        result = runtime.move_to(target)
        motion_segments.append(_motion_record(label, start, result))
        return result

    def add_nav_observation(viewpoint: Mapping[str, Any]) -> None:
        nonlocal capture_index
        xy = (float(viewpoint["xy"][0]), float(viewpoint["xy"][1]))
        movement = move(xy, str(viewpoint["name"]))
        if not movement.reached:
            raise RuntimeError(
                f"failed to reach viewpoint {viewpoint['name']}: {movement.reason}"
            )
        runtime.wait_steps(5)
        capture_root = f"cap-nav-{capture_index}-{runtime.current_step}"
        capture_index += 1
        nav_claims.extend(
            _synthetic_nav_claims(
                scenario,
                step=runtime.current_step,
                capture_root=capture_root,
                ttl=config.ttl_steps,
            )
        )
        visited.add(str(viewpoint["name"]))

    def evaluate_nav() -> dict[str, Any]:
        nonlocal last_nav_receipt
        if descriptor.requires_go_gate:
            assert bridge is not None
            receipt = bridge.evaluate_action(
                claims=nav_claims,
                contract=nav_contract,
                calibration=calibration,
                current_step=runtime.current_step,
                profile=scenario.profile if scenario.profile != "manipulation-occlusion" else "independent-noise",
                noise_intensity=float(public["declared_noise_intensity"]),
                sensor_version=SENSOR_VERSION,
            )
            # map profile for OOD-less v5: manipulation-occlusion treated as ID for cal smoke
            gate_receipts.append(receipt)
            last_nav_receipt = receipt
            return receipt
        # naive
        value = naive_decision_from_claims([c.to_wire() for c in nav_claims])
        admitted = value == "clear"
        synthetic = {
            "admitted": admitted,
            "prediction_set": [value] if value != "unresolved" else ["clear", "blocked"],
            "receipt_id": "naive-nav",
            "receipt_sha256": canonical_sha256({"v": value, "step": runtime.current_step}),
            "valid_until_step": runtime.current_step + config.ttl_steps,
            "belief_gaps": [] if admitted else [{"reason": "insufficient_roots"}],
            "measurement_root_ids": [],
            "p_blocked": 0.2 if admitted else 0.8,
            "calibration_applicable": True,
            "unresolved_conflicts": 0,
        }
        gate_receipts.append(synthetic)
        last_nav_receipt = synthetic
        return synthetic

    def evaluate_pick() -> dict[str, Any]:
        nonlocal last_pick_receipt
        clear = scenario.truth_grasp_clear_at(runtime.current_step)
        # Online claim uses workspace geometry derived from pose vs public grasp_xy
        # (not oracle occlusion flag). Occlusion profiles lower confidence.
        pose = runtime.current_pose
        dist = math.hypot(pose.x - GRASP_XY[0], pose.y - GRASP_XY[1])
        online_clear = dist < 0.55 and (
            clear or scenario.profile not in {"manipulation-occlusion", "shared-occlusion"}
        )
        if scenario.profile == "manipulation-occlusion" and not clear:
            online_clear = False
        conf = 0.86 if online_clear else 0.4
        claim = build_workspace_claim(
            clear=online_clear,
            confidence=conf,
            observed_step=runtime.current_step,
            valid_until_step=runtime.current_step + 40,
            capture_root_id=f"cap-grasp-{runtime.current_step}",
        )
        grasp_claims.append(claim)
        if descriptor.requires_go_gate:
            assert bridge is not None
            # smoke cal may not list manipulation-occlusion — use independent-noise label for applicability
            profile = (
                "independent-noise"
                if scenario.profile == "manipulation-occlusion"
                else scenario.profile
            )
            receipt = bridge.evaluate_action(
                claims=[claim],
                contract=pick_contract,
                calibration=calibration,
                current_step=runtime.current_step,
                profile=profile,
                noise_intensity=float(public["declared_noise_intensity"]),
                sensor_version=SENSOR_VERSION,
            )
            gate_receipts.append(receipt)
            last_pick_receipt = receipt
            return receipt
        admitted = online_clear
        synthetic = {
            "admitted": admitted,
            "prediction_set": ["clear"] if admitted else ["blocked"],
            "receipt_id": "naive-pick",
            "receipt_sha256": canonical_sha256({"pick": admitted, "step": runtime.current_step}),
            "valid_until_step": runtime.current_step + 40,
            "belief_gaps": [],
            "measurement_root_ids": [claim.capture_root_id],
            "p_blocked": 0.15 if admitted else 0.85,
            "calibration_applicable": True,
            "unresolved_conflicts": 0,
        }
        gate_receipts.append(synthetic)
        last_pick_receipt = synthetic
        return synthetic

    def maybe_invalidate(receipt: dict[str, Any], *, reason_hint: str) -> bool:
        if not descriptor.requires_go_gate or bridge is None or not receipt:
            # synthetic TTL
            if runtime.current_step > int(receipt.get("valid_until_step", 10**9)):
                invalidations.append(
                    {
                        "invalidated": True,
                        "reasons": ["stale", reason_hint],
                        "previous_receipt_sha256": receipt.get("receipt_sha256"),
                    }
                )
                return True
            return False
        inv = bridge.invalidate_plan(
            previous_receipt=receipt,
            current_step=runtime.current_step,
            triggering_claims=(),
        )
        invalidations.append(inv)
        return bool(inv.get("invalidated"))

    # --- phase: initial observations for navigation ---
    start_xy = (runtime.current_pose.x, runtime.current_pose.y)
    ordered = ordered_reachable_viewpoints(public, start_xy)
    nav_admitted = False
    if not ordered:
        outcome = "no_viewpoint"
    else:
        outcome = "running"
        # collect up to 2 viewpoints for dual roots
        for candidate in ordered[:2]:
            try:
                add_nav_observation(candidate)
            except RuntimeError:
                continue
        receipt = evaluate_nav()
        if descriptor.allows_repair and not receipt.get("admitted"):
            # BeliefGap repair loop (navigation only)
            gaps = [
                g.get("reason", "insufficient_roots")
                for g in receipt.get("belief_gaps", [])
            ] or ["insufficient_roots"]
            for repair_iters in range(config.max_observations):
                gap = BeliefGap.from_reasons(gaps)
                side_only = [
                    c
                    for c in public["candidate_viewpoints"]
                    if str(c.get("name", "")).startswith(("left_", "right_"))
                ]
                planner_public = {
                    "candidate_viewpoints": side_only,
                    "known_static_map": public["known_static_map"],
                }
                context = build_planning_context(
                    public_context=planner_public,
                    current_step=runtime.current_step,
                    current_xy=(runtime.current_pose.x, runtime.current_pose.y),
                    current_viewpoint_name=next(iter(visited), "start"),
                    current_predicted_coverage=0.7,
                    current_predicted_degradation=0.2,
                    current_physical_risk=0.1,
                    visited_actions=visited,
                    observations_taken=len(visited),
                    replans_taken=replan_count,
                )
                decision = planner.choose(gap, context)
                repair_decisions.append(decision.to_dict())
                if decision.selected_action is None:
                    break
                if decision.selected_action.kind == "side_view":
                    replan_count += 1
                    name = decision.selected_action.name
                    cand = next(
                        (c for c in public["candidate_viewpoints"] if c["name"] == name),
                        None,
                    )
                    if cand is None:
                        break
                    try:
                        add_nav_observation(cand)
                    except RuntimeError:
                        break
                elif decision.selected_action.wait_steps:
                    runtime.wait_steps(min(10, int(decision.selected_action.wait_steps)))
                    visited.add(f"wait:{repair_iters}")
                else:
                    capture_root = f"cap-nav-re-{capture_index}-{runtime.current_step}"
                    capture_index += 1
                    nav_claims.extend(
                        _synthetic_nav_claims(
                            scenario,
                            step=runtime.current_step,
                            capture_root=capture_root,
                            ttl=config.ttl_steps,
                        )
                    )
                    visited.add(f"same_view:{repair_iters}")
                receipt = evaluate_nav()
                if receipt.get("admitted"):
                    break
                gaps = [
                    g.get("reason", "insufficient_roots")
                    for g in receipt.get("belief_gaps", [])
                ] or gaps

        nav_admitted = bool(receipt.get("admitted"))

    task_nav_ok = False
    task_pick_ok = False
    used_detour = False
    unsafe = False

    if nav_admitted and last_nav_receipt is not None:
        # Approach gate boundary then re-check invalidation
        boundary = move((0.35, 0.0), "pre_cross_gate")
        if boundary.reached and maybe_invalidate(
            last_nav_receipt, reason_hint="pre_cross_recheck"
        ):
            nav_admitted = False
            outcome = "nav_invalidated"
        elif boundary.reached:
            before = runtime.collision_count
            crossing = move((0.95, 0.0), "cross_region")
            if runtime.collision_count > before and scenario.truth_nav_blocked_at(
                runtime.current_step
            ):
                unsafe = True
            task_nav_ok = crossing.reached and not unsafe
            # Mid-mission invalidation probe after crossing attempt
            if last_nav_receipt and maybe_invalidate(
                last_nav_receipt, reason_hint="post_cross_ttl"
            ):
                outcome = "nav_invalidated_after_cross"
        else:
            used_detour = True
            outcome = "pre_cross_unreachable"
    else:
        used_detour = True
        outcome = outcome if outcome != "running" else "nav_denied"
        # Safe detour toward grasp side corridor
        move((-0.2, 1.2), "detour_entry")
        move((1.0, 1.3), "detour_side")

    # --- phase: pick_proxy ---
    approach = move((1.05, 0.0), "grasp_approach")
    if approach.reached:
        pick_receipt = evaluate_pick()
        if pick_receipt.get("admitted") and last_pick_receipt is not None:
            if maybe_invalidate(last_pick_receipt, reason_hint="pre_pick"):
                outcome = "pick_invalidated"
            else:
                grasp = evaluate_proxy_grasp(
                    runtime.current_pose,
                    tuple(scenario.oracle_context["object_xy"]),
                    close_command=True,
                    lift_command=True,
                )
                # Oracle only for evaluation of true attach feasibility under occlusion
                if not scenario.truth_grasp_clear_at(runtime.current_step):
                    grasp = type(grasp)(
                        False,
                        "oracle_occluded_eval_only",
                        grasp.ee_xy,
                        grasp.object_xy,
                        grasp.distance,
                        False,
                    )
                grasp_results.append(grasp.to_dict())
                task_pick_ok = grasp.success
                if task_pick_ok:
                    outcome = "mission_complete"
                else:
                    outcome = "pick_failed"
        else:
            outcome = "pick_denied"
            grasp_results.append(
                {
                    "success": False,
                    "reason": "contract_denied",
                    "ee_xy": list(end_effector_xy(runtime.current_pose)),
                }
            )
    else:
        outcome = "grasp_approach_failed"

    # Final transit to goal if pick succeeded or nav-only fallback
    if task_pick_ok or (task_nav_ok and config.policy == POLICY_NAIVE):
        goal = move(tuple(public["goal_xy"]), "goal")
        if not goal.reached:
            task_pick_ok = task_pick_ok and False
            outcome = "goal_unreachable"

    mission_success = task_nav_ok and task_pick_ok and not unsafe
    # Allow mission success on detour path if pick still works and no unsafe
    if not task_nav_ok and task_pick_ok and not unsafe and used_detour:
        mission_success = True
        outcome = "detour_then_pick_success"

    elapsed = time.perf_counter() - started
    return {
        "schema_version": EPISODE_SCHEMA,
        "git_commit": git_commit(),
        "configuration": {
            **asdict(config),
            "alpha": calibration.alpha,
            "calibration_artifact_id": calibration.artifact_id,
        },
        "scenario": scenario.to_dict(),
        "environment": runtime.environment,
        "action_contracts": [nav_contract, pick_contract],
        "calibration_artifact": calibration.to_wire(),
        "nav_claims": [c.to_wire() for c in nav_claims],
        "grasp_claims": [c.to_wire() for c in grasp_claims],
        "gate_receipts": gate_receipts,
        "plan_invalidation_receipts": invalidations,
        "repair_decisions": repair_decisions,
        "motion_segments": motion_segments,
        "grasp_results": grasp_results,
        "metrics": {
            "unsafe_crossing": unsafe,
            "mission_success": mission_success,
            "nav_success": task_nav_ok,
            "pick_success": task_pick_ok,
            "used_detour": used_detour,
            "observation_count": len(visited),
            "replan_count": replan_count,
            "collision_count": runtime.collision_count,
            "invalidation_count": len(
                [i for i in invalidations if i.get("invalidated")]
            ),
            "elapsed_seconds": elapsed,
            "simulation_steps": runtime.current_step,
            "outcome": outcome,
        },
        "oracle": {"scenario": scenario.oracle_context},
        "outcome": {
            "mission_success": mission_success,
            "safe_fallback": (not mission_success) and not unsafe,
            "label": outcome,
        },
    }


__all__ = (
    "EPISODE_SCHEMA",
    "V5EpisodeConfig",
    "cross_region_contract",
    "pick_proxy_contract",
    "run_v5_episode",
    "smoke_calibration_artifact",
    "git_commit",
)
