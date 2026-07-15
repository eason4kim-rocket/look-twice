"""Look Twice v3：噪声、动态场景和信息增益主动感知的完整闭环。"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Optional

import genesis as gs
import numpy as np
import torch

from belief import BeliefStatus, Observation, ProbabilisticRegionBelief
from perception import analyze_rgbd_segmentation, save_sensor_artifacts
from scenario import PROFILES, ScenarioSample, sample_scenario
from sensor_noise import SensorNoiseConfig, corrupt_rgbd_segmentation
from learned_nbv import LearnedNBVScorer, feature_vector
from viewpoint import (
    DEFAULT_CANDIDATES,
    InformationGainViewpointPlanner,
    Rectangle,
    ViewpointCandidate,
    ViewpointPlanner,
    binary_entropy,
)


POLICIES = (
    "single-shot",
    "fixed-multiview",
    "purify-fixed",
    "purify-random",
    "purify-information-gain",
    "purify-learned",
)
ACTIVE_POLICIES = {
    "purify-fixed",
    "purify-random",
    "purify-information-gain",
    "purify-learned",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="static-mixed")
    parser.add_argument("--policy", choices=POLICIES, default="purify-information-gain")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--belief-ttl", type=int, default=60)
    parser.add_argument("--max-observations", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--video-stride", type=int, default=5)
    parser.add_argument("--noise-severity", type=float)
    parser.add_argument("--collect-oracle-labels", action="store_true")
    parser.add_argument("--learned-model", type=Path)
    args = parser.parse_args()
    if args.belief_ttl < 1 or args.max_observations < 1 or args.video_stride < 1:
        parser.error("TTL, max observations and video stride must be positive")
    if args.noise_severity is not None and not 0.0 <= args.noise_severity <= 1.0:
        parser.error("--noise-severity must be between 0 and 1")
    if args.policy == "purify-learned" and args.learned_model is None:
        parser.error("--policy purify-learned requires --learned-model")
    return args


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def obstacle_is_active(entity) -> bool:
    position = entity.get_pos()
    return 0.3 <= position[0].item() <= 1.3 and abs(position[1].item()) <= 0.6


def run_episode(args: argparse.Namespace) -> dict[str, Any]:
    gs.init(backend=gs.amdgpu, logging_level="warning")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(f"Requested device unavailable: {args.device}")
    device = torch.device(args.device)
    sample = sample_scenario(args.profile, args.seed)
    severity = sample.noise_severity if args.noise_severity is None else args.noise_severity
    noise_config = SensorNoiseConfig(
        severity=severity,
        depth_scale=sample.depth_noise_scale,
        segmentation_scale=sample.segmentation_noise_scale,
    )

    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(dt=0.02, gravity=(0.0, 0.0, 0.0)),
        vis_options=gs.options.VisOptions(segmentation_level="entity"),
    )
    scene.add_entity(gs.morphs.Plane())
    robot = scene.add_entity(
        gs.morphs.Box(size=(0.4, 0.3, 0.2), pos=(-2.0, 0.0, 0.1), fixed=True),
        surface=gs.surfaces.Default(color=(0.1, 0.45, 0.95)),
    )
    occluder = scene.add_entity(
        gs.morphs.Box(
            size=sample.occluder_size,
            pos=(sample.occluder_xy[0], sample.occluder_xy[1], 0.5),
            fixed=True,
        ),
        surface=gs.surfaces.Default(color=(0.45, 0.45, 0.45)),
    )
    target_patch = scene.add_entity(
        gs.morphs.Box(
            size=(0.8, 0.8, 0.02),
            pos=(0.8, 0.0, 0.015),
            fixed=True,
            collision=False,
        ),
        surface=gs.surfaces.Default(color=(0.15, 0.65, 0.25)),
    )
    inactive_position = (-10.0, 0.0, sample.obstacle_size[2] / 2.0)
    active_position = (
        sample.obstacle_xy[0],
        sample.obstacle_xy[1],
        sample.obstacle_size[2] / 2.0,
    )
    obstacle_rng = random.Random(args.seed + 991)
    obstacle_color = tuple(obstacle_rng.uniform(0.08, 0.92) for _ in range(3))
    blocking_obstacle = scene.add_entity(
        gs.morphs.Box(
            size=sample.obstacle_size,
            pos=active_position if sample.initial_blocked else inactive_position,
            fixed=True,
        ),
        surface=gs.surfaces.Default(color=obstacle_color),
    )
    sensor_camera = scene.add_camera(
        res=(320, 240),
        pos=(-0.6, 1.2, 0.8),
        lookat=(0.8, 0.0, 0.25),
        up=(0.0, 0.0, 1.0),
        fov=60,
        GUI=False,
    )
    video_camera = None
    if args.video_output:
        video_camera = scene.add_camera(
            res=(640, 480),
            pos=(0.0, 0.0, 8.0),
            lookat=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            fov=43,
            GUI=False,
        )
    scene.build()
    segmentation_index_by_entity = {
        entity_key: segmentation_idx
        for segmentation_idx, entity_key in scene.visualizer.segmentation_idx_dict.items()
    }
    obstacle_segmentation_idx = segmentation_index_by_entity[blocking_obstacle.idx]
    target_segmentation_idx = segmentation_index_by_entity[target_patch.idx]
    if video_camera:
        video_camera.start_recording()

    candidates = {candidate.name: candidate for candidate in DEFAULT_CANDIDATES}
    fixed_order = ["left_near", "right_near", "left_far", "right_far"]
    target_region = Rectangle(0.4, 1.2, -0.4, 0.4)
    occluder_rect = Rectangle(
        sample.occluder_xy[0] - sample.occluder_size[0] / 2.0,
        sample.occluder_xy[0] + sample.occluder_size[0] / 2.0,
        sample.occluder_xy[1] - sample.occluder_size[1] / 2.0,
        sample.occluder_xy[1] + sample.occluder_size[1] / 2.0,
    )
    visibility_planner = ViewpointPlanner()
    information_planner = InformationGainViewpointPlanner()
    learned_scorer = (
        LearnedNBVScorer(args.learned_model, args.device)
        if args.policy == "purify-learned"
        else None
    )
    policy_rng = random.Random(args.seed + 2027)
    belief = ProbabilisticRegionBelief(max_age_steps=args.belief_ttl)
    visited: set[str] = set()
    unreachable = set(sample.unreachable_viewpoints)
    initial_viewpoint_name: Optional[str] = None

    current_xy = torch.tensor([-2.0, 0.0], device=device)
    trajectory: list[dict[str, Any]] = [{"step": 0, "x": -2.0, "y": 0.0}]
    viewpoint_evaluations: list[dict[str, Any]] = []
    action_decisions: list[dict[str, Any]] = []
    dynamic_events: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    risk_entries: list[dict[str, Any]] = []
    oracle_labels: list[dict[str, Any]] = []
    route = ["start"]
    step = 0
    path_length = 0.0
    viewpoint_travel = 0.0
    event_due_step: Optional[int] = None
    event_completed = False
    stale_count = 0
    replan_count = 0
    start_time = time.perf_counter()

    def apply_event_if_due() -> None:
        nonlocal event_completed
        if event_due_step is None or event_completed or step < event_due_step:
            return
        if sample.dynamic_event == "appears":
            blocking_obstacle.set_pos(torch.tensor(active_position, device=device))
            event_name = "obstacle_appeared"
        elif sample.dynamic_event == "clears":
            blocking_obstacle.set_pos(torch.tensor(inactive_position, device=device))
            event_name = "obstacle_cleared"
        else:
            return
        event_completed = True
        dynamic_events.append({"step": step, "event": event_name})

    def simulation_step() -> None:
        nonlocal step
        apply_event_if_due()
        robot.set_pos(torch.tensor([current_xy[0].item(), current_xy[1].item(), 0.1], device=device))
        scene.step()
        if video_camera and step % args.video_stride == 0:
            video_camera.render()
        step += 1
        trajectory.append(
            {"step": step, "x": current_xy[0].item(), "y": current_xy[1].item()}
        )

    def move_to(target: tuple[float, float], label: str) -> float:
        nonlocal current_xy, path_length
        destination = torch.tensor(target, device=device)
        moved = 0.0
        while torch.linalg.norm(destination - current_xy).item() > 0.045:
            delta = destination - current_xy
            distance = torch.linalg.norm(delta)
            increment = min(0.016, distance.item())
            current_xy = current_xy + delta / distance * increment
            moved += increment
            path_length += increment
            simulation_step()
            if step > 5000:
                raise RuntimeError("v3 episode exceeded 5000 simulation steps")
        route.append(label)
        return moved

    def wait_steps(count: int) -> None:
        for _ in range(count):
            simulation_step()

    def ranking_for_current_position() -> list:
        return information_planner.rank(
            current_xy=(current_xy[0].item(), current_xy[1].item()),
            target_region=target_region,
            occluders=[occluder_rect],
            visited=visited,
            unreachable=unreachable,
            p_blocked=belief.p_blocked,
            severity=severity,
        )

    def probe_candidate(score, decision_id: str) -> dict[str, Any]:
        """数据集模式专用：渲染候选点，但绝不把结果反馈给在线规划器。"""
        candidate = candidates[score.name]
        sensor_camera.set_pose(
            pos=(candidate.xy[0], candidate.xy[1], candidate.camera_z),
            lookat=(0.8, 0.0, 0.25),
            up=(0.0, 0.0, 1.0),
        )
        rgb, depth, segmentation, _ = sensor_camera.render(
            rgb=True,
            depth=True,
            segmentation=True,
            colorize_seg=False,
            force_render=True,
        )
        corrupted = corrupt_rgbd_segmentation(
            rgb=np.asarray(rgb),
            depth=np.asarray(depth),
            segmentation=np.asarray(segmentation),
            obstacle_segmentation_idx=obstacle_segmentation_idx,
            target_segmentation_idx=target_segmentation_idx,
            config=noise_config,
            seed=args.seed,
            observation_index=len(evidence_records),
            viewpoint=candidate.name,
            viewpoint_xy=candidate.xy,
            target_xy=(0.8, 0.0),
            predicted_visibility=score.expected_visibility,
            device=args.device,
        )
        perception = analyze_rgbd_segmentation(
            rgb=corrupted.rgb,
            depth=corrupted.depth,
            segmentation=corrupted.segmentation,
            obstacle_segmentation_idx=obstacle_segmentation_idx,
            target_segmentation_idx=target_segmentation_idx,
            target_reference_pixels=candidate.target_reference_pixels,
            device=args.device,
        )
        weight = max(
            0.10,
            min(
                1.0,
                (1.0 - corrupted.degradation)
                * max(0.25, perception.visible_fraction),
            ),
        )
        posterior_log_odds = belief.log_odds
        if perception.result == "inconclusive":
            posterior_log_odds *= 0.90
        else:
            reliability = min(0.995, max(0.505, perception.confidence))
            contribution = math.log(reliability / (1.0 - reliability)) * weight
            posterior_log_odds += (
                contribution if perception.result == "blocked" else -contribution
            )
        posterior_probability = 1.0 / (1.0 + math.exp(-posterior_log_odds))
        actual_gain = max(
            0.0, belief.entropy - binary_entropy(posterior_probability)
        )
        return {
            "decision_id": decision_id,
            "profile": args.profile,
            "seed": args.seed,
            "candidate": candidate.name,
            "features": feature_vector(
                p_blocked=belief.p_blocked,
                entropy=belief.entropy,
                observation_count=len(belief.evidence),
                score=score,
            ),
            "label": actual_gain
            - 0.25 * score.travel_cost
            - 0.20 * score.revisit_penalty,
            "actual_information_gain": actual_gain,
            "heuristic_utility": score.utility,
            "observed_result": perception.result,
            "truth_blocked": obstacle_is_active(blocking_obstacle),
        }

    def choose_viewpoint(reason: str, allow_revisit: bool = False) -> Optional[ViewpointCandidate]:
        nonlocal initial_viewpoint_name
        ranking = ranking_for_current_position()
        available = [
            name for name in fixed_order if name not in unreachable and (allow_revisit or name not in visited)
        ]
        selected: Optional[ViewpointCandidate] = None
        learned_scores: dict[str, float] = {}
        decision_id = f"{args.profile}:{args.seed}:{len(viewpoint_evaluations)}"
        if args.collect_oracle_labels:
            oracle_labels.extend(
                probe_candidate(score, decision_id)
                for score in ranking
                if score.reachable
            )
        if reason == "initial":
            # 公平对照：所有策略共享同一个、只使用已知静态遮挡地图的首视角。
            selected, _ = visibility_planner.choose(
                current_xy=(current_xy[0].item(), current_xy[1].item()),
                target_region=target_region,
                occluders=[occluder_rect],
                visited=set(unreachable),
            )
            initial_viewpoint_name = selected.name if selected else None
        elif args.policy == "purify-learned":
            for score in ranking:
                if score.reachable and (allow_revisit or score.name not in visited):
                    learned_scores[score.name] = learned_scorer.score(
                        feature_vector(
                            p_blocked=belief.p_blocked,
                            entropy=belief.entropy,
                            observation_count=len(belief.evidence),
                            score=score,
                        )
                    )
            if learned_scores:
                selected = candidates[max(learned_scores, key=learned_scores.get)]
        elif args.policy == "purify-information-gain":
            selected, _ = information_planner.choose(
                current_xy=(current_xy[0].item(), current_xy[1].item()),
                target_region=target_region,
                occluders=[occluder_rect],
                visited=set() if allow_revisit else visited,
                unreachable=unreachable,
                p_blocked=belief.p_blocked,
                severity=severity,
            )
        elif args.policy == "purify-random" and available:
            selected = candidates[policy_rng.choice(available)]
        elif args.policy == "purify-fixed":
            name = initial_viewpoint_name
            selected = candidates[name] if name else None
        elif available:
            selected = candidates[available[0]]
        viewpoint_evaluations.append(
            {
                "step": step,
                "reason": reason,
                "policy": args.policy,
                "selected": selected.name if selected else None,
                "ranking": [item.to_dict() for item in ranking],
                "learned_scores": learned_scores,
            }
        )
        return selected

    def observe(candidate: ViewpointCandidate) -> Observation:
        nonlocal viewpoint_travel
        viewpoint_travel += move_to(candidate.xy, candidate.name)
        visited.add(candidate.name)
        wait_steps(10)
        sensor_camera.set_pose(
            pos=(candidate.xy[0], candidate.xy[1], candidate.camera_z),
            lookat=(0.8, 0.0, 0.25),
            up=(0.0, 0.0, 1.0),
        )
        rgb, depth, segmentation, _ = sensor_camera.render(
            rgb=True,
            depth=True,
            segmentation=True,
            colorize_seg=False,
            force_render=True,
        )
        raw_rgb = np.asarray(rgb)
        raw_depth = np.asarray(depth)
        raw_segmentation = np.asarray(segmentation)
        ranking = ranking_for_current_position()
        score = next(item for item in ranking if item.name == candidate.name)
        corrupted = corrupt_rgbd_segmentation(
            rgb=raw_rgb,
            depth=raw_depth,
            segmentation=raw_segmentation,
            obstacle_segmentation_idx=obstacle_segmentation_idx,
            target_segmentation_idx=target_segmentation_idx,
            config=noise_config,
            seed=args.seed,
            observation_index=len(evidence_records),
            viewpoint=candidate.name,
            viewpoint_xy=candidate.xy,
            target_xy=(0.8, 0.0),
            predicted_visibility=score.expected_visibility,
            device=args.device,
        )
        raw_artifacts: dict[str, str] = {}
        corrupted_artifacts: dict[str, str] = {}
        if args.evidence_dir:
            index = len(evidence_records)
            raw_artifacts = save_sensor_artifacts(
                rgb=raw_rgb,
                depth=raw_depth,
                segmentation=raw_segmentation,
                output_dir=args.evidence_dir,
                stem=f"observation_{index:02d}_{candidate.name}_raw",
            )
            corrupted_artifacts = save_sensor_artifacts(
                rgb=corrupted.rgb,
                depth=corrupted.depth,
                segmentation=corrupted.segmentation,
                output_dir=args.evidence_dir,
                stem=f"observation_{index:02d}_{candidate.name}_corrupted",
            )
        perception = analyze_rgbd_segmentation(
            rgb=corrupted.rgb,
            depth=corrupted.depth,
            segmentation=corrupted.segmentation,
            obstacle_segmentation_idx=obstacle_segmentation_idx,
            target_segmentation_idx=target_segmentation_idx,
            target_reference_pixels=candidate.target_reference_pixels,
            device=args.device,
        )
        perception = replace(perception, artifact_paths=corrupted_artifacts)
        evidence_weight = max(
            0.10,
            min(1.0, (1.0 - corrupted.degradation) * max(0.25, perception.visible_fraction)),
        )
        observation = Observation(
            viewpoint=candidate.name,
            result=perception.result,
            confidence=perception.confidence,
            step=step,
            source="camera-rgbd-corrupted",
            artifact=corrupted_artifacts.get("rgb"),
            metadata={
                "perception": perception.to_dict(),
                "corruption": corrupted.audit_dict(),
                "raw_artifacts": raw_artifacts,
                "truth_blocked_at_observation": obstacle_is_active(blocking_obstacle),
            },
        )
        entropy_before = belief.entropy
        belief.add_observation(observation, evidence_weight=evidence_weight)
        evidence_records.append(
            {
                **asdict(observation),
                "evidence_weight": evidence_weight,
                "belief_after": belief.snapshot(),
                "realized_information_gain": max(0.0, entropy_before - belief.entropy),
            }
        )
        print(
            f"[step={step}] {candidate.name}: result={perception.result} "
            f"conf={perception.confidence:.3f} weight={evidence_weight:.3f} "
            f"p_blocked={belief.p_blocked:.3f} H={belief.entropy:.3f} "
            f"device={perception.device}"
        )
        return observation

    def collect_decision(reason: str) -> str:
        """返回 clear/blocked；无充分证据时只返回安全的 blocked。"""
        observations_this_round: list[Observation] = []
        while len(observations_this_round) < args.max_observations:
            allow_revisit = args.policy == "purify-fixed" or reason.startswith("stale")
            candidate = choose_viewpoint(reason, allow_revisit=allow_revisit)
            if candidate is None:
                break
            observation = observe(candidate)
            observations_this_round.append(observation)
            if args.policy == "single-shot":
                return observation.result if observation.result in {"clear", "blocked"} else "blocked"
            if args.policy == "fixed-multiview" and len(observations_this_round) >= 3:
                counts = Counter(
                    item.result for item in observations_this_round if item.result in {"clear", "blocked"}
                )
                return "clear" if counts["clear"] > counts["blocked"] else "blocked"
            if args.policy in ACTIVE_POLICIES:
                if belief.is_action_allowed("go_to_goal"):
                    return "clear"
                if belief.is_action_allowed("go_to_detour"):
                    return "blocked"
            if args.policy in ACTIVE_POLICIES and args.policy != "purify-fixed":
                replan_reason = "uncertain_evidence"
                action_decisions.append(
                    {"step": step, "action": "reinspect", "allowed": True, "reason": replan_reason}
                )
        action_decisions.append(
            {"step": step, "action": "safe_detour", "allowed": True, "reason": "unresolved"}
        )
        return "blocked"

    decision = collect_decision("initial")
    if sample.dynamic_event != "none":
        event_due_step = step + sample.event_delay
        dynamic_events.append(
            {"step": step, "event": "scheduled", "due": event_due_step, "kind": sample.dynamic_event}
        )
    action_decisions.append({"step": step, "action": decision, "allowed": True, "phase": "initial"})

    # 在风险区或绕行承诺之前移动到决策边界；动态事件在真实仿真步中触发。
    if decision == "clear":
        move_to((-0.15, 0.0), "pre_gate")
    else:
        move_to((-0.10, 1.05), "pre_detour_gate")

    if args.policy in ACTIVE_POLICIES:
        previous_status = belief.status
        belief.refresh_status(step)
        if belief.status == BeliefStatus.STALE:
            stale_count += 1
            replan_count += 1
            action_decisions.append(
                {"step": step, "action": "commit_route", "allowed": False, "reason": "stale"}
            )
            decision = collect_decision("stale_before_commit")
        elif previous_status in {BeliefStatus.UNCERTAIN, BeliefStatus.STALE}:
            decision = "blocked"

    used_detour = decision != "clear"
    unsafe_crossing = False
    if decision == "clear":
        gate_allowed = args.policy not in ACTIVE_POLICIES or belief.is_action_allowed(
            "go_to_goal", current_step=step
        )
        action_decisions.append(
            {"step": step, "action": "cross_risk_gate", "allowed": gate_allowed}
        )
        if not gate_allowed:
            used_detour = True
            decision = "blocked"

    if decision == "clear":
        move_to((0.8, 0.0), "passage")
        truth_blocked = obstacle_is_active(blocking_obstacle)
        unsafe_crossing = truth_blocked
        risk_entries.append(
            {
                "step": step,
                "belief_status": belief.status.value,
                "p_blocked": belief.p_blocked,
                "truth_blocked": truth_blocked,
                "gate_enforced": args.policy in ACTIVE_POLICIES,
            }
        )
    else:
        move_to((0.8, 1.5), "detour")
    move_to((2.0, 0.0), "goal")

    elapsed = time.perf_counter() - start_time
    if video_camera:
        args.video_output.parent.mkdir(parents=True, exist_ok=True)
        video_camera.stop_recording(save_to_filename=str(args.video_output), fps=30)

    final_truth_blocked = obstacle_is_active(blocking_obstacle)
    brier_values = [
        (entry["belief_after"]["p_blocked"] - float(entry["metadata"]["truth_blocked_at_observation"])) ** 2
        for entry in evidence_records
    ]
    information_gain = sum(item["realized_information_gain"] for item in evidence_records)
    corruption_times = [item["metadata"]["corruption"]["gpu_time_ms"] for item in evidence_records]
    perception_times = [item["metadata"]["perception"]["gpu_time_ms"] for item in evidence_records]
    unresolved_gate_entries = sum(
        1
        for entry in risk_entries
        if entry["gate_enforced"]
        and entry["belief_status"] in {"unknown", "uncertain", "stale", "provisional_clear", "provisional_blocked"}
    )
    result = {
        "schema_version": 3,
        "git_commit": git_commit(),
        "configuration": {
            "profile": args.profile,
            "policy": args.policy,
            "seed": args.seed,
            "belief_ttl": args.belief_ttl,
            "max_observations": args.max_observations,
            "sensor_mode": "camera-rgbd-corrupted",
            "device": args.device,
            "learned_model": str(args.learned_model) if args.learned_model else None,
        },
        "scenario_sample": sample.to_dict(),
        "noise_config": asdict(noise_config),
        "environment": {
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "rocm": torch.version.hip,
            "torch": torch.__version__,
            "genesis": gs.__version__,
            "backend": "gs.amdgpu",
        },
        "evidence": evidence_records,
        "belief_trace": belief.calibration_trace,
        "viewpoint_evaluations": viewpoint_evaluations,
        "oracle_labels": oracle_labels,
        "action_decisions": action_decisions,
        "dynamic_events": dynamic_events,
        "risk_entries": risk_entries,
        "trajectory": trajectory,
        "metrics": {
            "mission_success": math.dist((current_xy[0].item(), current_xy[1].item()), (2.0, 0.0)) < 0.06,
            "safe_success": not unsafe_crossing,
            "unsafe_crossing": unsafe_crossing,
            "wrong_detour": used_detour and not final_truth_blocked,
            "observation_count": len(evidence_records),
            "replan_count": replan_count + sum(1 for item in action_decisions if item["action"] == "reinspect"),
            "stale_count": stale_count,
            "path_length": path_length,
            "viewpoint_travel": viewpoint_travel,
            "brier_score": sum(brier_values) / len(brier_values) if brier_values else 0.25,
            "final_entropy": belief.entropy,
            "information_gain_per_meter": information_gain / max(viewpoint_travel, 1e-9),
            "unresolved_gate_entries": unresolved_gate_entries,
            "dynamic_intercepted": bool(sample.dynamic_event == "appears" and event_completed and not unsafe_crossing),
            "avg_sensor_corruption_ms": sum(corruption_times) / len(corruption_times),
            "avg_perception_ms": sum(perception_times) / len(perception_times),
            "elapsed_seconds": elapsed,
            "simulation_steps": step,
        },
        "outcome": {
            "belief": belief.snapshot(),
            "route": route,
            "used_detour": used_detour,
            "final_truth_blocked": final_truth_blocked,
        },
    }
    print(
        f"finished policy={args.policy} profile={args.profile} seed={args.seed} "
        f"safe={not unsafe_crossing} observations={len(evidence_records)} "
        f"path={path_length:.2f} device={args.device}"
    )
    return result


def main() -> None:
    args = parse_args()
    result = run_episode(args)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("JSON output:", args.json_output)


if __name__ == "__main__":
    main()
