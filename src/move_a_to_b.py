import math
import time
import genesis as gs
import torch


def main() -> None:
    # 1. 初始化 Genesis：使用 AMD GPU 运行仿真。
    gs.init(
        backend=gs.amdgpu,
        logging_level="warning",
    )

    # 2. 创建仿真场景。
    # dt 是每个仿真步代表的时间；这里关闭重力，避免简化机器人上下移动。
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
    # 当前机器人只是一个固定箱子，不包含轮子和真实动力学。
    # 后续通过 robot.set_pos() 直接更新它的位置。
    robot = scene.add_entity(
        gs.morphs.Box(
            size=(0.4, 0.3, 0.2),
            pos=(-2.0, 0.0, 0.1),
            fixed=True,
        )
    )

    # 场景中的实体添加完成后，必须 build 才能开始仿真。
    scene.build()

    # 4. 定义导航任务的起点和终点，只使用 x、y 两个坐标。
    start_xy = torch.tensor([-2.0, 0.0], device="cuda:0")
    goal_xy = torch.tensor([2.0, 0.0], device="cuda:0")

    # 5. 运动参数。
    # 每个循环最多前进 speed * dt = 0.016 米。
    # 当机器人和目标的距离小于 tolerance 时，认为已经到达。
    speed = 0.8
    dt = 0.02
    tolerance = 0.05

    # current_xy 是导航逻辑中的当前位置。
    current_xy = start_xy.clone()

    start_time = time.perf_counter()

    for step in range(1000):
        # 6. 计算“当前位置 -> 目标点”的方向和剩余距离。
        delta = goal_xy - current_xy
        distance = torch.linalg.norm(delta).item()

        if distance < tolerance:
            print(f"Goal reached at step={step}")
            break

        # 将方向向量归一化，然后沿该方向前进一步。
        direction = delta / torch.linalg.norm(delta)
        current_xy = current_xy + direction * speed * dt

        # 7. 把二维导航位置转换为 Genesis 使用的三维位置。
        # z 固定为 0.1，使箱子保持在地面上方的正确高度。
        pos = torch.tensor(
            [current_xy[0], current_xy[1], 0.1],
            device="cuda:0",
        )

        # 直接设置简化机器人的位置，再推进一个仿真步。
        robot.set_pos(pos)
        scene.step()

        # 每 50 步打印一次位置和剩余距离，便于观察运动过程。
        if step % 50 == 0:
            print(
                f"step={step:03d} "
                f"x={current_xy[0].item():.3f} "
                f"y={current_xy[1].item():.3f} "
                f"distance={distance:.3f}"
            )

    # 8. 输出最终位置、耗时和到目标的最终距离。
    elapsed = time.perf_counter() - start_time
    final_pos = robot.get_pos()

    print("Final position:", final_pos)
    print(f"Elapsed: {elapsed:.3f}s")
    print(
        "Final distance:",
        math.hypot(
            final_pos[0].item() - goal_xy[0].item(),
            final_pos[1].item() - goal_xy[1].item(),
        ),
    )


if __name__ == "__main__":
    main()
