import argparse
import math
import time
from dataclasses import dataclass
from enum import Enum, auto

import genesis as gs
import torch


@dataclass
class Observation:
    """记录机器人在某个观察点获得的一条证据。"""

    viewpoint: str
    result: str
    confidence: float
    step: int


class MissionState(Enum):
    # Look Twice 的任务阶段。
    GO_TO_INSPECTION = auto()
    INSPECT = auto()
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


def observe_region(blocking_obstacle) -> str:
    """根据受检区域内是否存在阻挡物返回观察结果。"""
    if blocking_obstacle is None:
        return "clear"

    obstacle_pos = blocking_obstacle.get_pos()
    obstacle_x = obstacle_pos[0].item()
    obstacle_y = obstacle_pos[1].item()

    obstacle_in_region = (
        0.4 <= obstacle_x <= 1.2
        and -0.4 <= obstacle_y <= 0.4
    )
    return "blocked" if obstacle_in_region else "clear"


def main() -> None:
    # 命令行参数选择场景真值，不再直接告诉机器人观察结论。
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=("clear", "blocked"),
        default="clear",
        help="选择受检区域的场景真值",
    )
    args = parser.parse_args()

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
        )
    )

    # 4. 添加遮挡物：位于起点到终点的主路径附近。
    # 当前版本尚未用传感器读取它，它主要用于表达“被遮挡区域”的场景概念。
    scene.add_entity(
        gs.morphs.Box(
            size=(0.5, 1.2, 1.0),
            pos=(0.0, 0.0, 0.5),
            fixed=True,
        )
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
            )
        )

    # 所有实体添加完成后构建场景。
    scene.build()

    device = torch.device("cuda:0")

    # 5. 定义三个关键导航点：起点、观察点和最终目标点。
    start_xy = torch.tensor([-2.0, 0.0], device=device)
    inspection_xy = torch.tensor([-0.6, 1.2], device=device)
    detour_xy = torch.tensor([0.8, 1.5], device=device)
    goal_xy = torch.tensor([2.0, 0.0], device=device)

    current_xy = start_xy.clone()

    # 6. 运动和观察参数。
    # 每步最多移动 speed * dt = 0.016 米。
    # 到达目标点附近 tolerance 范围内即认为到达。
    # inspection_steps_required 表示机器人在观察点等待的仿真步数。
    speed = 0.8
    dt = 0.02
    tolerance = 0.05
    inspection_steps_required = 40

    # 7. 初始化任务状态。
    # region_status 表示机器人对前方区域的认知，初始为 unknown。
    state = MissionState.GO_TO_INSPECTION
    inspection_steps = 0
    region_status = "unknown"
    evidence: list[Observation] = []

    start_time = time.perf_counter()

    for step in range(2000):
        if state == MissionState.GO_TO_INSPECTION:
            # 阶段一：主动前往更好的观察位置。
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
            # 阶段二：停在观察点，累计模拟观察时间。
            inspection_steps += 1

            if inspection_steps == 1:
                print(
                    f"[step={step}] Inspecting occluded region..."
                )

            if inspection_steps >= inspection_steps_required:
                # 读取 Genesis 场景中的阻挡物实体，生成新观察。
                observation = Observation(
                    viewpoint="inspection",
                    result=observe_region(blocking_obstacle),
                    confidence=1.0,
                    step=step,
                )
                evidence.append(observation)
                region_status = observation.result

                if region_status == "clear":
                    state = MissionState.GO_TO_GOAL
                elif region_status == "blocked":
                    state = MissionState.GO_TO_DETOUR

                print(
                    f"[step={step}] Region revised: "
                    f"unknown -> {region_status}"
                )

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

    print()
    print("Final mission state:", state.name)
    print("Final region status:", region_status)
    print("Evidence:")
    for observation in evidence:
        print(
            f"  viewpoint={observation.viewpoint} "
            f"result={observation.result} "
            f"confidence={observation.confidence:.2f} "
            f"step={observation.step}"
        )

    if region_status == "clear":
        route_summary = "start -> inspection -> goal"
    elif region_status == "blocked":
        route_summary = "start -> inspection -> detour -> goal"
    else:
        route_summary = "incomplete"

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


if __name__ == "__main__":
    main()
