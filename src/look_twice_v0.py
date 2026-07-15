import math
import time
from enum import Enum, auto

import genesis as gs
import torch


class MissionState(Enum):
    GO_TO_INSPECTION = auto()
    INSPECT = auto()
    GO_TO_GOAL = auto()
    FINISHED = auto()


def move_toward(
    current_xy: torch.Tensor,
    target_xy: torch.Tensor,
    speed: float,
    dt: float,
) -> torch.Tensor:
    delta = target_xy - current_xy
    distance = torch.linalg.norm(delta)

    if distance.item() == 0:
        return current_xy

    max_step = speed * dt

    if distance.item() <= max_step:
        return target_xy.clone()

    direction = delta / distance
    return current_xy + direction * max_step


def distance_between(a: torch.Tensor, b: torch.Tensor) -> float:
    return torch.linalg.norm(a - b).item()


def main() -> None:
    gs.init(
        backend=gs.amdgpu,
        logging_level="warning",
    )

    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(
            dt=0.02,
            gravity=(0.0, 0.0, 0.0),
        ),
    )

    scene.add_entity(gs.morphs.Plane())

    robot = scene.add_entity(
        gs.morphs.Box(
            size=(0.4, 0.3, 0.2),
            pos=(-2.0, 0.0, 0.1),
            fixed=True,
        )
    )

    # 遮挡物：位于主路径附近
    scene.add_entity(
        gs.morphs.Box(
            size=(0.5, 1.2, 1.0),
            pos=(0.0, 0.0, 0.5),
            fixed=True,
        )
    )

    scene.build()

    device = torch.device("cuda:0")

    start_xy = torch.tensor([-2.0, 0.0], device=device)
    inspection_xy = torch.tensor([-0.6, 1.2], device=device)
    goal_xy = torch.tensor([2.0, 0.0], device=device)

    current_xy = start_xy.clone()

    speed = 0.8
    dt = 0.02
    tolerance = 0.05
    inspection_steps_required = 40

    state = MissionState.GO_TO_INSPECTION
    inspection_steps = 0
    region_status = "unknown"

    start_time = time.perf_counter()

    for step in range(2000):
        if state == MissionState.GO_TO_INSPECTION:
            target_xy = inspection_xy

            current_xy = move_toward(
                current_xy,
                target_xy,
                speed,
                dt,
            )

            if distance_between(current_xy, inspection_xy) < tolerance:
                state = MissionState.INSPECT
                print(f"[step={step}] Reached inspection viewpoint")

        elif state == MissionState.INSPECT:
            inspection_steps += 1

            if inspection_steps == 1:
                print(
                    f"[step={step}] Inspecting occluded region..."
                )

            if inspection_steps >= inspection_steps_required:
                region_status = "clear"
                state = MissionState.GO_TO_GOAL

                print(
                    f"[step={step}] Region revised: "
                    f"unknown -> {region_status}"
                )

        elif state == MissionState.GO_TO_GOAL:
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
                break

        elif state == MissionState.FINISHED:
            break

        pos = torch.tensor(
            [
                current_xy[0].item(),
                current_xy[1].item(),
                0.1,
            ],
            device=device,
        )

        robot.set_pos(pos)
        scene.step()

        if step % 50 == 0:
            print(
                f"step={step:04d} "
                f"state={state.name:<16} "
                f"x={current_xy[0].item():.3f} "
                f"y={current_xy[1].item():.3f} "
                f"region={region_status}"
            )

    elapsed = time.perf_counter() - start_time
    final_pos = robot.get_pos()

    print()
    print("Final mission state:", state.name)
    print("Final region status:", region_status)
    print("Final position:", final_pos)
    print(
        "Distance to goal:",
        math.hypot(
            final_pos[0].item() - goal_xy[0].item(),
            final_pos[1].item() - goal_xy[1].item(),
        ),
    )
    print(f"Elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()
