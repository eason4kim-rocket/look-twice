from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import time
from collections import Counter
from dataclasses import asdict, replace
from enum import Enum, auto
from pathlib import Path

import genesis as gs
import numpy as np
import torch

from belief import BeliefStatus, Observation, RegionBelief
from perception import analyze_rgbd_segmentation, save_sensor_artifacts
from viewpoint import (
    DEFAULT_CANDIDATES,
    Rectangle,
    ViewpointCandidate,
    ViewpointPlanner,
)


class MissionState(Enum):
    # Look Twice 的任务阶段。
    GO_TO_INSPECTION = auto()
    INSPECT = auto()
    GO_TO_SECOND_INSPECTION = auto()
    GO_TO_REINSPECTION = auto()
    VERIFY_BEFORE_CROSSING = auto()
    GO_TO_DETOUR = auto()
    GO_TO_GOAL = auto()
    FINISHED = auto()


def move_toward(
    current_xy: torch.Tensor,
    target_xy: torch.Tensor,
    speed: float,
    dt: float,
) -> torch.Tensor:
    """计算从当前位置朝目标移动一步后得到的新二维位置。"""
    delta = target_xy - current_xy
    distance = torch.linalg.norm(delta)

    if distance.item() == 0:
        return current_xy

    # 单个循环允许移动的最大距离。
    max_step = speed * dt

    # 剩余距离不足一步时直接落在目标上，避免越过目标点。
    if distance.item() <= max_step:
        return target_xy.clone()

    direction = delta / distance
    return current_xy + direction * max_step


def distance_between(a: torch.Tensor, b: torch.Tensor) -> float:
    """返回两个二维位置之间的欧氏距离。"""
    return torch.linalg.norm(a - b).item()


def observe_region_geometry(blocking_obstacle) -> tuple[str, float]:
    """根据受检区域内是否存在阻挡物返回观察结果。"""
    if blocking_obstacle is None:
        return "clear", 1.0

    obstacle_pos = blocking_obstacle.get_pos()
    obstacle_x = obstacle_pos[0].item()
    obstacle_y = obstacle_pos[1].item()

    obstacle_in_region = (
        0.4 <= obstacle_x <= 1.2
        and -0.4 <= obstacle_y <= 0.4
    )
    return ("blocked", 1.0) if obstacle_in_region else ("clear", 1.0)


def observe_region_camera(
    camera,
    viewpoint: str,
    evidence_dir: Path | None,
    observation_index: int,
) -> tuple[str, float, str | None, int]:
    """从 Genesis 相机 RGB 图像中的红色障碍像素形成证据。"""
    camera_positions = {
        "inspection_left": (-0.6, 1.2, 0.8),
        # 第二观察点向前错开，绕过中央遮挡体获得互补视野。
        "inspection_right": (0.0, -1.2, 0.8),
    }
    camera.set_pose(
        pos=camera_positions[viewpoint],
        lookat=(0.8, 0.0, 0.25),
        up=(0.0, 0.0, 1.0),
    )
    rgb = np.asarray(camera.render(rgb=True, force_render=True)[0])

    # 场景中只有受检障碍使用低绿、低蓝的红色材质。
    red_mask = (
        (rgb[..., 0] > 130)
        & (rgb[..., 1] < 100)
        & (rgb[..., 2] < 100)
    )
    red_pixel_count = int(red_mask.sum())
    result = "blocked" if red_pixel_count >= 30 else "clear"

    # 30 像素是最低可见证据；像素越多，blocked 置信度越高。
    # clear 场景没有红色实体，因此零红像素作为强 clear 证据。
    if result == "blocked":
        confidence = min(1.0, 0.8 + red_pixel_count / 5000.0)
    else:
        confidence = max(0.8, 1.0 - red_pixel_count / 30.0)

    artifact = None
    if evidence_dir is not None:
        from PIL import Image

        evidence_dir.mkdir(parents=True, exist_ok=True)
        image_path = evidence_dir / (
            f"observation_{observation_index:02d}_{viewpoint}.png"
        )
        Image.fromarray(rgb).save(image_path)
        artifact = str(image_path)

    return result, confidence, artifact, red_pixel_count


def apply_observation_noise(
    true_result: str,
    base_confidence: float,
    noise_profile: str,
    observation_index: int,
    noise_rate: float,
    rng: random.Random,
) -> tuple[str, float]:
    """使用可复现的噪声配置生成观察结果和置信度。"""
    should_flip = (
        noise_profile == "first-flip" and observation_index == 0
    ) or (
        noise_profile == "alternating" and observation_index % 2 == 0
    ) or (
        noise_profile == "random" and rng.random() < noise_rate
    )

    if not should_flip:
        return true_result, base_confidence

    flipped_result = "blocked" if true_result == "clear" else "clear"
    confidence = 0.6 if noise_profile != "random" else 0.9
    return flipped_result, confidence


def run_v2(args: argparse.Namespace, rng: random.Random) -> None:
    """运行 RGB-D、Next-Best-View 与时效准入闭环。"""
    if args.sensor_mode != "camera-rgbd":
        raise SystemExit("Look Twice v2 requires --sensor-mode camera-rgbd")

    gs.init(backend=gs.amdgpu, logging_level="warning")
    device = torch.device("cuda:0")
    active_policy = args.policy == "purify-active"
    viewpoint_policy = (
        "fixed" if args.policy == "purify-fixed" else args.viewpoint_policy
    )

    occluder_shift = 0.0
    occluder_size_y = 1.2
    if args.scenario == "shifted-occluder":
        occluder_shift = -0.4 if args.seed % 2 == 0 else 0.4
    elif args.scenario == "high-occlusion":
        occluder_size_y = 1.8

    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(
            dt=0.02,
            gravity=(0.0, 0.0, 0.0),
        ),
        vis_options=gs.options.VisOptions(segmentation_level="entity"),
    )
    scene.add_entity(gs.morphs.Plane())
    robot = scene.add_entity(
        gs.morphs.Box(
            size=(0.4, 0.3, 0.2),
            pos=(-2.0, 0.0, 0.1),
            fixed=True,
        ),
        surface=gs.surfaces.Default(color=(0.1, 0.45, 0.95)),
    )
    scene.add_entity(
        gs.morphs.Box(
            size=(0.5, occluder_size_y, 1.0),
            pos=(0.0, occluder_shift, 0.5),
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

    starts_blocked = args.scenario in {
        "blocked",
        "dynamic-clears",
        "shifted-occluder",
        "high-occlusion",
    }
    inactive_obstacle_position = (-10.0, 0.0, 0.25)
    obstacle_position = (
        (0.8, 0.0, 0.25) if starts_blocked else inactive_obstacle_position
    )
    color_rng = random.Random(args.seed + 991)
    obstacle_color = tuple(color_rng.uniform(0.1, 0.9) for _ in range(3))
    blocking_obstacle = scene.add_entity(
        gs.morphs.Box(
            size=(0.5, 0.5, 0.5),
            pos=obstacle_position,
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
    if args.video_output is not None:
        for candidate in DEFAULT_CANDIDATES:
            scene.add_entity(
                gs.morphs.Box(
                    size=(0.12, 0.12, 0.05),
                    pos=(candidate.xy[0], candidate.xy[1], 0.025),
                    fixed=True,
                    collision=False,
                ),
                surface=gs.surfaces.Default(color=(1.0, 0.65, 0.0)),
            )
        video_camera = scene.add_camera(
            res=(640, 480),
            pos=(0.0, 0.0, 8.0),
            lookat=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            fov=43,
            GUI=False,
        )

    scene.build()
    # render() 返回紧凑 segmentation index，而不是 Entity.idx。
    segmentation_index_by_entity = {
        entity_key: segmentation_idx
        for segmentation_idx, entity_key
        in scene.visualizer.segmentation_idx_dict.items()
    }
    obstacle_segmentation_idx = segmentation_index_by_entity[
        blocking_obstacle.idx
    ]
    target_segmentation_idx = segmentation_index_by_entity[target_patch.idx]
    if video_camera is not None:
        video_camera.start_recording()

    start_xy = torch.tensor([-2.0, 0.0], device=device)
    passage_xy = torch.tensor([0.8, 0.0], device=device)
    detour_xy = torch.tensor([0.8, 1.5], device=device)
    goal_xy = torch.tensor([2.0, 0.0], device=device)
    current_xy = start_xy.clone()
    target_region = Rectangle(0.4, 1.2, -0.4, 0.4)
    occluders = [
        Rectangle(
            -0.25,
            0.25,
            occluder_shift - occluder_size_y / 2,
            occluder_shift + occluder_size_y / 2,
        )
    ]
    planner = ViewpointPlanner()
    candidates = {candidate.name: candidate for candidate in DEFAULT_CANDIDATES}
    fixed_order = ["left_near", "right_near", "left_far", "right_far"]
    visited: set[str] = set()
    viewpoint_evaluations: list[dict] = []

    def choose_viewpoint(step: int, reason: str) -> ViewpointCandidate | None:
        if viewpoint_policy == "fixed":
            selected = next(
                (candidates[name] for name in fixed_order if name not in visited),
                None,
            )
            ranking = planner.rank(
                current_xy=(current_xy[0].item(), current_xy[1].item()),
                target_region=target_region,
                occluders=occluders,
                visited=visited,
            )
        else:
            selected, ranking = planner.choose(
                current_xy=(current_xy[0].item(), current_xy[1].item()),
                target_region=target_region,
                occluders=occluders,
                visited=visited,
            )
        viewpoint_evaluations.append(
            {
                "step": step,
                "reason": reason,
                "selected": selected.name if selected else None,
                "ranking": [item.to_dict() for item in ranking],
            }
        )
        return selected

    selected_viewpoint = choose_viewpoint(-1, "initial")
    if selected_viewpoint is None:
        raise RuntimeError("No initial inspection viewpoint is available")
    active_target_xy = torch.tensor(selected_viewpoint.xy, device=device)
    current_viewpoint = selected_viewpoint.name

    state = MissionState.GO_TO_INSPECTION
    inspection_steps = 0
    belief = RegionBelief(
        confirmation_threshold=0.8,
        max_age_steps=args.belief_ttl if active_policy else None,
    )
    region_status = belief.status.value
    belief_lifecycle = [{"step": -1, "status": region_status}]
    action_decisions: list[dict] = []
    state_transitions = [{"step": -1, "from": None, "to": state.name}]
    trajectory = [{"step": -1, "x": -2.0, "y": 0.0}]
    route_parts = ["start"]
    dynamic_events: list[dict] = []
    risk_entries: list[dict] = []
    event_due_step = None
    event_completed = False
    risk_gate_passed = False
    passed_region = False
    used_detour = False
    unsafe_crossing = False
    stale_count = 0
    replan_count = 0
    path_length = 0.0
    speed, dt, tolerance = 0.8, 0.02, 0.05
    inspection_interval_steps = 20
    start_time = time.perf_counter()

    for step in range(4000):
        state_before = state
        position_before = current_xy.clone()

        if event_due_step is not None and step >= event_due_step and not event_completed:
            if args.scenario == "dynamic-appears":
                new_position = torch.tensor([0.8, 0.0, 0.25], device=device)
                event_name = "obstacle_appeared"
            else:
                new_position = torch.tensor(inactive_obstacle_position, device=device)
                event_name = "obstacle_cleared"
            blocking_obstacle.set_pos(new_position)
            event_completed = True
            dynamic_events.append({"step": step, "event": event_name})
            print(f"[step={step}] Dynamic event: {event_name}")

        if state in {
            MissionState.GO_TO_INSPECTION,
            MissionState.GO_TO_SECOND_INSPECTION,
            MissionState.GO_TO_REINSPECTION,
        }:
            current_xy = move_toward(current_xy, active_target_xy, speed, dt)
            if distance_between(current_xy, active_target_xy) < tolerance:
                visited.add(current_viewpoint)
                route_parts.append(current_viewpoint)
                inspection_steps = 0
                state = MissionState.INSPECT
                print(f"[step={step}] Reached viewpoint: {current_viewpoint}")

        elif state == MissionState.INSPECT:
            inspection_steps += 1
            if inspection_steps == 1:
                print(f"[step={step}] Inspecting with RGB-D sensor...")
            if inspection_steps % inspection_interval_steps == 0:
                candidate = candidates[current_viewpoint]
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
                perception = analyze_rgbd_segmentation(
                    rgb=np.asarray(rgb),
                    depth=np.asarray(depth),
                    segmentation=np.asarray(segmentation),
                    obstacle_segmentation_idx=obstacle_segmentation_idx,
                    target_segmentation_idx=target_segmentation_idx,
                    target_reference_pixels=candidate.target_reference_pixels,
                    device="cuda:0",
                )
                if args.evidence_dir is not None:
                    stem = f"observation_{len(belief.evidence):02d}_{current_viewpoint}"
                    artifacts = save_sensor_artifacts(
                        rgb=np.asarray(rgb),
                        depth=np.asarray(depth),
                        segmentation=np.asarray(segmentation),
                        output_dir=args.evidence_dir,
                        stem=stem,
                    )
                    perception = replace(perception, artifact_paths=artifacts)

                observed_result, confidence = perception.result, perception.confidence
                if perception.result in {"clear", "blocked"}:
                    observed_result, confidence = apply_observation_noise(
                        perception.result,
                        perception.confidence,
                        args.noise_profile,
                        len(belief.evidence),
                        args.noise_rate,
                        rng,
                    )
                observation = Observation(
                    viewpoint=current_viewpoint,
                    result=observed_result,
                    confidence=confidence,
                    step=step,
                    source="camera-rgbd",
                    artifact=perception.artifact_paths.get("rgb"),
                    metadata=perception.to_dict(),
                )
                previous_status = belief.status
                belief.add_observation(observation)
                region_status = belief.status.value
                if previous_status != belief.status:
                    belief_lifecycle.append({"step": step, "status": region_status})
                print(
                    f"[step={step}] RGB-D evidence: result={observed_result} "
                    f"confidence={confidence:.3f} obstacle_pixels="
                    f"{perception.support_pixels} visibility="
                    f"{perception.visible_fraction:.3f} device={perception.device}"
                )

                if (
                    args.scenario in {"dynamic-appears", "dynamic-clears"}
                    and event_due_step is None
                    and belief.status
                    in {BeliefStatus.CONFIRMED_CLEAR, BeliefStatus.CONFIRMED_BLOCKED}
                ):
                    event_due_step = step + args.event_delay
                    dynamic_events.append(
                        {"step": step, "event": "scheduled", "due": event_due_step}
                    )

                decision_result = None
                if args.policy == "single-shot":
                    decision_result = (
                        observation.result
                        if observation.result in {"clear", "blocked"}
                        else "blocked"
                    )
                elif args.policy == "majority-vote" and len(belief.evidence) >= 3:
                    counts = Counter(
                        item.result
                        for item in belief.evidence[:3]
                        if item.result in {"clear", "blocked"}
                    )
                    decision_result = (
                        "clear" if counts["clear"] > counts["blocked"] else "blocked"
                    )
                elif args.policy in {"purify", "purify-fixed", "purify-active"}:
                    if belief.is_action_allowed("go_to_goal"):
                        decision_result = "clear"
                    elif belief.is_action_allowed("go_to_detour"):
                        decision_result = "blocked"

                if decision_result == "clear":
                    state = MissionState.GO_TO_GOAL
                    risk_gate_passed = not active_policy
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": True}
                    )
                elif decision_result == "blocked":
                    state = MissionState.GO_TO_DETOUR
                    used_detour = True
                    action_decisions.append(
                        {"step": step, "action": "go_to_detour", "allowed": True}
                    )
                elif belief.status == BeliefStatus.UNCERTAIN:
                    next_viewpoint = choose_viewpoint(step, "uncertain_evidence")
                    if next_viewpoint is None or args.policy in {
                        "single-shot",
                        "majority-vote",
                    }:
                        state = MissionState.GO_TO_DETOUR
                        used_detour = True
                        action_decisions.append(
                            {"step": step, "action": "safe_detour", "allowed": True}
                        )
                    else:
                        selected_viewpoint = next_viewpoint
                        current_viewpoint = next_viewpoint.name
                        active_target_xy = torch.tensor(next_viewpoint.xy, device=device)
                        state = MissionState.GO_TO_SECOND_INSPECTION
                        replan_count += 1
                        action_decisions.append(
                            {"step": step, "action": "reinspect", "allowed": True}
                        )
                else:
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": False}
                    )

        elif state == MissionState.VERIFY_BEFORE_CROSSING:
            allowed = belief.is_action_allowed("go_to_goal", current_step=step)
            region_status = belief.status.value
            action_decisions.append(
                {"step": step, "action": "cross_risk_gate", "allowed": allowed}
            )
            if allowed:
                risk_gate_passed = True
                risk_entries.append(
                    {"step": step, "belief": belief.status.value, "allowed": True}
                )
                state = MissionState.GO_TO_GOAL
            else:
                if belief.status == BeliefStatus.STALE:
                    stale_count += 1
                    belief_lifecycle.append({"step": step, "status": "stale"})
                next_viewpoint = choose_viewpoint(step, "stale_before_crossing")
                if next_viewpoint is None:
                    state = MissionState.GO_TO_DETOUR
                    used_detour = True
                else:
                    current_viewpoint = next_viewpoint.name
                    active_target_xy = torch.tensor(next_viewpoint.xy, device=device)
                    state = MissionState.GO_TO_REINSPECTION
                    replan_count += 1

        elif state == MissionState.GO_TO_DETOUR:
            if args.scenario == "dynamic-clears" and active_policy:
                if not belief.is_action_allowed("go_to_detour", current_step=step):
                    region_status = belief.status.value
                    if belief.status == BeliefStatus.STALE:
                        stale_count += 1
                        belief_lifecycle.append({"step": step, "status": "stale"})
                    next_viewpoint = choose_viewpoint(step, "stale_detour_evidence")
                    if next_viewpoint is not None:
                        current_viewpoint = next_viewpoint.name
                        active_target_xy = torch.tensor(next_viewpoint.xy, device=device)
                        state = MissionState.GO_TO_REINSPECTION
                        replan_count += 1
                        continue
            current_xy = move_toward(current_xy, detour_xy, speed, dt)
            if distance_between(current_xy, detour_xy) < tolerance:
                route_parts.append("detour")
                risk_gate_passed = True
                state = MissionState.GO_TO_GOAL

        elif state == MissionState.GO_TO_GOAL:
            approaching_risk_region = (
                not used_detour
                and not passed_region
                and distance_between(current_xy, passage_xy) <= 0.75
            )
            if active_policy and not risk_gate_passed and approaching_risk_region:
                state = MissionState.VERIFY_BEFORE_CROSSING
            else:
                navigation_target = (
                    goal_xy if used_detour or passed_region else passage_xy
                )
                current_xy = move_toward(
                    current_xy,
                    navigation_target,
                    speed,
                    dt,
                )
                obstacle_now = observe_region_geometry(blocking_obstacle)[0] == "blocked"
                entered_risk_region = (
                    0.4 <= current_xy[0].item() <= 1.2
                    and abs(current_xy[1].item()) <= 0.4
                )
                if entered_risk_region and obstacle_now and not used_detour:
                    unsafe_crossing = True
                if (
                    not used_detour
                    and not passed_region
                    and distance_between(current_xy, passage_xy) < tolerance
                ):
                    passed_region = True
                    route_parts.append("passage")
                elif distance_between(current_xy, goal_xy) < tolerance:
                    route_parts.append("goal")
                    state = MissionState.FINISHED

        elif state == MissionState.FINISHED:
            break

        if state != state_before:
            state_transitions.append(
                {"step": step, "from": state_before.name, "to": state.name}
            )
        path_length += distance_between(position_before, current_xy)
        robot.set_pos(
            torch.tensor(
                [current_xy[0].item(), current_xy[1].item(), 0.1],
                device=device,
            )
        )
        scene.step()
        if video_camera is not None and step % args.video_stride == 0:
            video_camera.render()
        trajectory.append(
            {"step": step, "x": current_xy[0].item(), "y": current_xy[1].item()}
        )
        if step % 50 == 0:
            print(
                f"step={step:04d} state={state.name:<24} "
                f"x={current_xy[0].item():.3f} y={current_xy[1].item():.3f} "
                f"region={region_status}"
            )

    elapsed = time.perf_counter() - start_time
    final_pos = robot.get_pos()
    if video_camera is not None:
        args.video_output.parent.mkdir(parents=True, exist_ok=True)
        video_camera.stop_recording(save_to_filename=str(args.video_output), fps=30)

    final_distance = distance_between(final_pos[:2], goal_xy)
    mission_success = state == MissionState.FINISHED and final_distance < tolerance
    final_obstacle_blocked = observe_region_geometry(blocking_obstacle)[0] == "blocked"
    wrong_detour = used_detour and not final_obstacle_blocked
    gpu_times = [
        item.metadata["gpu_time_ms"]
        for item in belief.evidence
        if item.metadata and "gpu_time_ms" in item.metadata
    ]
    print()
    print("Final mission state:", state.name)
    print("Final belief:", belief.status.value)
    print("Route:", " -> ".join(route_parts))
    print("Unsafe crossing:", unsafe_crossing)
    print("GPU perception device: cuda:0")
    print(f"Elapsed: {elapsed:.3f}s")

    if args.json_output is not None:
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            git_commit = "unknown"
        result = {
            "schema_version": 2,
            "git_commit": git_commit,
            "configuration": {
                "scenario": args.scenario,
                "policy": args.policy,
                "sensor_mode": args.sensor_mode,
                "viewpoint_policy": viewpoint_policy,
                "belief_ttl": args.belief_ttl,
                "event_delay": args.event_delay,
                "seed": args.seed,
                "noise_profile": args.noise_profile,
                "noise_rate": args.noise_rate,
                "obstacle_color": obstacle_color,
            },
            "environment": {
                "gpu": torch.cuda.get_device_name(0),
                "rocm": torch.version.hip,
                "torch": torch.__version__,
                "genesis": gs.__version__,
                "backend": "gs.amdgpu",
                "perception_device": "cuda:0",
            },
            "evidence": [asdict(item) for item in belief.evidence],
            "belief_lifecycle": belief_lifecycle,
            "viewpoint_evaluations": viewpoint_evaluations,
            "action_decisions": action_decisions,
            "dynamic_events": dynamic_events,
            "risk_entries": risk_entries,
            "state_transitions": state_transitions,
            "trajectory": trajectory,
            "metrics": {
                "mission_success": mission_success,
                "safe_success": mission_success and not unsafe_crossing,
                "unsafe_crossing": unsafe_crossing,
                "wrong_detour": wrong_detour,
                "observation_count": len(belief.evidence),
                "replan_count": replan_count,
                "stale_count": stale_count,
                "path_length": path_length,
                "final_distance": final_distance,
                "elapsed_seconds": elapsed,
                "simulation_steps": trajectory[-1]["step"] + 1,
                "avg_gpu_perception_ms": (
                    sum(gpu_times) / len(gpu_times) if gpu_times else 0.0
                ),
                "avg_visible_fraction": (
                    sum(
                        item.metadata["visible_fraction"]
                        for item in belief.evidence
                        if item.metadata
                    )
                    / len(gpu_times)
                    if gpu_times
                    else 0.0
                ),
            },
            "outcome": {
                "mission_state": state.name,
                "belief_status": belief.status.value,
                "route": route_parts,
            },
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("JSON output:", args.json_output)


def main() -> None:
    # 命令行参数选择场景真值，不再直接告诉机器人观察结论。
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=(
            "clear",
            "blocked",
            "dynamic-appears",
            "dynamic-clears",
            "shifted-occluder",
            "high-occlusion",
        ),
        default="clear",
        help="选择受检区域的场景真值",
    )
    parser.add_argument(
        "--policy",
        choices=(
            "single-shot",
            "majority-vote",
            "purify",
            "purify-fixed",
            "purify-active",
        ),
        default="purify",
        help="选择对照决策策略",
    )
    parser.add_argument(
        "--sensor-mode",
        choices=("geometry", "camera", "camera-rgbd"),
        default="geometry",
        help="geometry 读取场景实体；camera 从 Genesis RGB 图像形成证据",
    )
    parser.add_argument(
        "--viewpoint-policy",
        choices=("fixed", "next-best"),
        default="next-best",
        help="选择固定观察顺序或 Next-Best-View",
    )
    parser.add_argument(
        "--belief-ttl",
        type=int,
        default=60,
        help="confirmed belief 的有效仿真步数",
    )
    parser.add_argument(
        "--event-delay",
        type=int,
        default=40,
        help="首次确认后触发动态事件的延迟步数",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        help="保存每次相机观察的原始 RGB 证据图",
    )
    parser.add_argument(
        "--noise-profile",
        choices=("none", "first-flip", "alternating", "random"),
        default="none",
        help="选择可复现的观察噪声",
    )
    parser.add_argument(
        "--noise-rate",
        type=float,
        default=0.0,
        help="random 噪声配置下单次观察翻转概率",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="实验随机种子（为后续随机噪声保留）",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="将结构化运行结果写入指定 JSON 文件",
    )
    parser.add_argument(
        "--video-output",
        type=Path,
        help="使用 Genesis 顶视相机保存 MP4 演示视频",
    )
    parser.add_argument(
        "--video-stride",
        type=int,
        default=5,
        help="每隔多少个仿真步渲染一帧",
    )
    args = parser.parse_args()
    if not 0.0 <= args.noise_rate <= 1.0:
        parser.error("--noise-rate must be between 0 and 1")
    if args.video_stride < 1:
        parser.error("--video-stride must be at least 1")
    if args.belief_ttl < 1:
        parser.error("--belief-ttl must be at least 1")
    if args.event_delay < 1:
        parser.error("--event-delay must be at least 1")
    rng = random.Random(args.seed)

    v2_requested = (
        args.sensor_mode == "camera-rgbd"
        or args.scenario not in {"clear", "blocked"}
        or args.policy in {"purify-fixed", "purify-active"}
    )
    if v2_requested:
        run_v2(args, rng)
        return

    # 1. 初始化 Genesis：使用 AMD GPU 运行仿真。
    gs.init(
        backend=gs.amdgpu,
        logging_level="warning",
    )

    # 2. 创建无重力场景，专注验证二维导航和状态机逻辑。
    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(
            dt=0.02,
            gravity=(0.0, 0.0, 0.0),
        ),
    )

    # 添加地面。
    scene.add_entity(gs.morphs.Plane())

    # 3. 创建简化机器人。
    # 它是一个固定箱子，通过 set_pos() 直接移动，不是真实轮式模型。
    robot = scene.add_entity(
        gs.morphs.Box(
            size=(0.4, 0.3, 0.2),
            pos=(-2.0, 0.0, 0.1),
            fixed=True,
        ),
        surface=gs.surfaces.Default(color=(0.1, 0.45, 0.95)),
    )

    # 4. 添加遮挡物：位于起点到终点的主路径附近。
    # camera 模式会真实渲染它造成的遮挡，而不是读取其坐标。
    scene.add_entity(
        gs.morphs.Box(
            size=(0.5, 1.2, 1.0),
            pos=(0.0, 0.0, 0.5),
            fixed=True,
        ),
        surface=gs.surfaces.Default(color=(0.45, 0.45, 0.45)),
    )

    # blocked 场景会在受检区域内创建一个真实的 Genesis 实体。
    # clear 场景中没有这个阻挡物。
    blocking_obstacle = None
    if args.scenario == "blocked":
        blocking_obstacle = scene.add_entity(
            gs.morphs.Box(
                size=(0.5, 0.5, 0.5),
                pos=(0.8, 0.0, 0.25),
                fixed=True,
            ),
            surface=gs.surfaces.Default(color=(0.85, 0.15, 0.15)),
        )

    sensor_camera = None
    if args.sensor_mode == "camera":
        sensor_camera = scene.add_camera(
            res=(320, 240),
            pos=(-0.6, 1.2, 0.8),
            lookat=(0.8, 0.0, 0.25),
            up=(0.0, 0.0, 1.0),
            fov=60,
            GUI=False,
        )

    camera = None
    if args.video_output is not None:
        marker_specs = (
            ((-2.0, 0.0, 0.025), (0.1, 0.45, 0.95)),
            ((-0.6, 1.2, 0.025), (1.0, 0.75, 0.0)),
            ((0.0, -1.2, 0.025), (1.0, 0.4, 0.0)),
            ((0.8, 1.5, 0.025), (0.55, 0.25, 0.75)),
            ((2.0, 0.0, 0.025), (0.1, 0.7, 0.2)),
        )
        for marker_pos, marker_color in marker_specs:
            scene.add_entity(
                gs.morphs.Box(
                    size=(0.12, 0.12, 0.05),
                    pos=marker_pos,
                    fixed=True,
                    collision=False,
                ),
                surface=gs.surfaces.Default(color=marker_color),
            )

        camera = scene.add_camera(
            res=(640, 480),
            pos=(0.0, 0.0, 8.0),
            lookat=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            fov=43,
            GUI=False,
        )

    # 所有实体添加完成后构建场景。
    scene.build()
    if camera is not None:
        camera.start_recording()

    device = torch.device("cuda:0")

    # 5. 定义起点、左右观察点、绕行点和最终目标点。
    start_xy = torch.tensor([-2.0, 0.0], device=device)
    inspection_left_xy = torch.tensor([-0.6, 1.2], device=device)
    inspection_right_xy = torch.tensor([0.0, -1.2], device=device)
    detour_xy = torch.tensor([0.8, 1.5], device=device)
    goal_xy = torch.tensor([2.0, 0.0], device=device)

    current_xy = start_xy.clone()
    trajectory = [
        {"step": -1, "x": start_xy[0].item(), "y": start_xy[1].item()}
    ]
    path_length = 0.0

    # 6. 运动和观察参数。
    # 每步最多移动 speed * dt = 0.016 米。
    # 到达目标点附近 tolerance 范围内即认为到达。
    # 每间隔 20 个仿真步获取一条观察证据。
    speed = 0.8
    dt = 0.02
    tolerance = 0.05
    inspection_interval_steps = 20

    # 7. 初始化任务状态。
    # region_status 表示机器人对前方区域的认知，初始为 unknown。
    state = MissionState.GO_TO_INSPECTION
    inspection_steps = 0
    current_viewpoint = "inspection_left"
    visited_second_inspection = False
    used_detour = False
    belief = RegionBelief(confirmation_threshold=0.8)
    region_status = belief.status.value
    belief_lifecycle = [{"step": -1, "status": region_status}]
    action_decisions: list[dict] = []
    state_transitions = [
        {"step": -1, "from": None, "to": state.name}
    ]

    start_time = time.perf_counter()

    for step in range(2000):
        state_before = state
        position_before = current_xy.clone()

        if state == MissionState.GO_TO_INSPECTION:
            # 阶段一：主动前往更好的观察位置。
            target_xy = inspection_left_xy

            current_xy = move_toward(
                current_xy,
                target_xy,
                speed,
                dt,
            )

            if distance_between(current_xy, inspection_left_xy) < tolerance:
                state = MissionState.INSPECT
                print(f"[step={step}] Reached inspection viewpoint")

        elif state == MissionState.INSPECT:
            # 阶段二：停在观察点，累计模拟观察时间。
            inspection_steps += 1

            if inspection_steps == 1:
                print(
                    f"[step={step}] Inspecting occluded region..."
                )

            if inspection_steps % inspection_interval_steps == 0:
                # geometry 用于快速对照；camera 使用真实渲染图像形成证据。
                artifact = None
                red_pixel_count = None
                if args.sensor_mode == "camera":
                    (
                        true_result,
                        base_confidence,
                        artifact,
                        red_pixel_count,
                    ) = observe_region_camera(
                        sensor_camera,
                        current_viewpoint,
                        args.evidence_dir,
                        len(belief.evidence),
                    )
                else:
                    true_result, base_confidence = observe_region_geometry(
                        blocking_obstacle
                    )
                observed_result, confidence = apply_observation_noise(
                    true_result,
                    base_confidence,
                    args.noise_profile,
                    len(belief.evidence),
                    args.noise_rate,
                    rng,
                )
                observation = Observation(
                    viewpoint=current_viewpoint,
                    result=observed_result,
                    confidence=confidence,
                    step=step,
                    source=args.sensor_mode,
                    artifact=artifact,
                )
                previous_status = belief.status
                belief.add_observation(observation)
                region_status = belief.status.value

                print(
                    f"[step={step}] Evidence added: "
                    f"result={observation.result} "
                    f"confidence={observation.confidence:.2f}"
                )
                if red_pixel_count is not None:
                    print(
                        f"[step={step}] Camera evidence: "
                        f"red_pixels={red_pixel_count} artifact={artifact}"
                    )
                print(
                    f"[step={step}] Belief revised: "
                    f"{previous_status.value} -> {region_status}"
                )
                if belief.status != previous_status:
                    belief_lifecycle.append(
                        {"step": step, "status": region_status}
                    )

                decision_result = None
                if args.policy == "single-shot":
                    decision_result = observation.result
                elif args.policy == "majority-vote":
                    if len(belief.evidence) >= 3:
                        result_counts = Counter(
                            item.result for item in belief.evidence[:3]
                        )
                        decision_result = result_counts.most_common(1)[0][0]
                elif belief.is_action_allowed("go_to_goal"):
                    decision_result = "clear"
                elif belief.is_action_allowed("go_to_detour"):
                    decision_result = "blocked"

                if decision_result == "clear":
                    state = MissionState.GO_TO_GOAL
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": True}
                    )
                    print(f"[step={step}] Policy decision: GO_TO_GOAL")
                elif decision_result == "blocked":
                    state = MissionState.GO_TO_DETOUR
                    used_detour = True
                    action_decisions.append(
                        {"step": step, "action": "go_to_detour", "allowed": True}
                    )
                    print(f"[step={step}] Policy decision: GO_TO_DETOUR")
                elif (
                    args.policy == "purify"
                    and
                    belief.status == BeliefStatus.UNCERTAIN
                    and current_viewpoint == "inspection_left"
                ):
                    state = MissionState.GO_TO_SECOND_INSPECTION
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": False}
                    )
                    action_decisions.append(
                        {"step": step, "action": "reinspect", "allowed": True}
                    )
                    print(
                        f"[step={step}] Evidence conflict: "
                        "moving to second inspection viewpoint"
                    )
                elif (
                    args.policy == "purify"
                    and
                    belief.status == BeliefStatus.UNCERTAIN
                    and current_viewpoint == "inspection_right"
                ):
                    state = MissionState.GO_TO_DETOUR
                    used_detour = True
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": False}
                    )
                    action_decisions.append(
                        {"step": step, "action": "safe_detour", "allowed": True}
                    )
                    print(
                        f"[step={step}] Action gate: direct passage denied; "
                        "safe detour selected"
                    )
                else:
                    action_decisions.append(
                        {"step": step, "action": "go_to_goal", "allowed": False}
                    )
                    print(f"[step={step}] Action gate: high-risk action denied")

        elif state == MissionState.GO_TO_SECOND_INSPECTION:
            # 证据冲突时，机器人主动移动到右侧观察点。
            current_xy = move_toward(
                current_xy,
                inspection_right_xy,
                speed,
                dt,
            )

            if distance_between(current_xy, inspection_right_xy) < tolerance:
                current_viewpoint = "inspection_right"
                visited_second_inspection = True
                inspection_steps = 0
                state = MissionState.INSPECT
                print(f"[step={step}] Reached second inspection viewpoint")

        elif state == MissionState.GO_TO_DETOUR:
            # 阶段三（blocked 路线）：先前往绕行点。
            target_xy = detour_xy

            current_xy = move_toward(
                current_xy,
                target_xy,
                speed,
                dt,
            )

            if distance_between(current_xy, detour_xy) < tolerance:
                state = MissionState.GO_TO_GOAL
                print(f"[step={step}] Detour waypoint reached")

        elif state == MissionState.GO_TO_GOAL:
            # 阶段四：clear 时直接来这里；blocked 时经过绕行点后再来这里。
            target_xy = goal_xy

            current_xy = move_toward(
                current_xy,
                target_xy,
                speed,
                dt,
            )

            if distance_between(current_xy, goal_xy) < tolerance:
                state = MissionState.FINISHED
                print(f"[step={step}] Goal reached")

        elif state == MissionState.FINISHED:
            # 阶段五：任务结束，不再推进导航逻辑。
            break

        if state != state_before:
            state_transitions.append(
                {"step": step, "from": state_before.name, "to": state.name}
            )

        path_length += distance_between(position_before, current_xy)

        # 8. 将二维导航位置转换为三维位置；z 固定为机器人半高 0.1。
        pos = torch.tensor(
            [
                current_xy[0].item(),
                current_xy[1].item(),
                0.1,
            ],
            device=device,
        )

        # 将逻辑位置写入 Genesis 机器人实体，并推进一个仿真步。
        robot.set_pos(pos)
        scene.step()
        if camera is not None and step % args.video_stride == 0:
            camera.render()
        trajectory.append(
            {
                "step": step,
                "x": current_xy[0].item(),
                "y": current_xy[1].item(),
            }
        )

        # 每 50 步打印任务状态、机器人位置和区域认知状态。
        if step % 50 == 0:
            print(
                f"step={step:04d} "
                f"state={state.name:<16} "
                f"x={current_xy[0].item():.3f} "
                f"y={current_xy[1].item():.3f} "
                f"region={region_status}"
            )

    # 9. 输出任务结束时的状态、位置、目标距离和运行耗时。
    elapsed = time.perf_counter() - start_time
    final_pos = robot.get_pos()

    if camera is not None:
        args.video_output.parent.mkdir(parents=True, exist_ok=True)
        camera.stop_recording(
            save_to_filename=str(args.video_output),
            fps=30,
        )

    print()
    print("Final mission state:", state.name)
    print("Final region status:", region_status)
    print("Scenario:", args.scenario)
    print("Policy:", args.policy)
    print("Sensor mode:", args.sensor_mode)
    print("Noise profile:", args.noise_profile)
    print("Noise rate:", args.noise_rate)
    print("Seed:", args.seed)
    print("Evidence:")
    for observation in belief.evidence:
        print(
            f"  viewpoint={observation.viewpoint} "
            f"result={observation.result} "
            f"confidence={observation.confidence:.2f} "
            f"step={observation.step}"
        )

    route_parts = ["start", "inspection_left"]
    if visited_second_inspection:
        route_parts.append("inspection_right")
    if used_detour:
        route_parts.append("detour")
    route_parts.append("goal")
    route_summary = " -> ".join(route_parts)

    print("Route taken:", route_summary)
    print("Final position:", final_pos)
    print(
        "Distance to goal:",
        math.hypot(
            final_pos[0].item() - goal_xy[0].item(),
            final_pos[1].item() - goal_xy[1].item(),
        ),
    )
    print(f"Elapsed: {elapsed:.3f}s")

    if args.json_output is not None:
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            git_commit = "unknown"

        result = {
            "schema_version": 1,
            "git_commit": git_commit,
            "configuration": {
                "scenario": args.scenario,
                "policy": args.policy,
                "seed": args.seed,
                "noise_profile": args.noise_profile,
                "noise_rate": args.noise_rate,
                "sensor_mode": args.sensor_mode,
                "evidence_dir": (
                    str(args.evidence_dir) if args.evidence_dir else None
                ),
            },
            "environment": {
                "gpu": torch.cuda.get_device_name(0),
                "rocm": torch.version.hip,
                "torch": torch.__version__,
                "genesis": gs.__version__,
                "backend": "gs.amdgpu",
            },
            "evidence": [asdict(item) for item in belief.evidence],
            "belief_lifecycle": belief_lifecycle,
            "action_decisions": action_decisions,
            "state_transitions": state_transitions,
            "trajectory": trajectory,
            "metrics": {
                "mission_success": (
                    state == MissionState.FINISHED
                    and distance_between(final_pos[:2], goal_xy) < tolerance
                ),
                "unsafe_crossing": (
                    args.scenario == "blocked" and not used_detour
                ),
                "wrong_detour": (
                    args.scenario == "clear" and used_detour
                ),
                "safe_success": (
                    state == MissionState.FINISHED
                    and distance_between(final_pos[:2], goal_xy) < tolerance
                    and not (args.scenario == "blocked" and not used_detour)
                ),
                "final_distance": distance_between(final_pos[:2], goal_xy),
                "path_length": path_length,
                "observation_count": len(belief.evidence),
                "elapsed_seconds": elapsed,
                "simulation_steps": trajectory[-1]["step"] + 1,
            },
            "outcome": {
                "mission_state": state.name,
                "belief_status": belief.status.value,
                "route": route_parts,
            },
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print("JSON output:", args.json_output)


if __name__ == "__main__":
    main()
