import math
import time
import genesis as gs
import torch


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

    scene.build()

    start_xy = torch.tensor([-2.0, 0.0], device="cuda:0")
    goal_xy = torch.tensor([2.0, 0.0], device="cuda:0")

    speed = 0.8
    dt = 0.02
    tolerance = 0.05

    current_xy = start_xy.clone()

    start_time = time.perf_counter()

    for step in range(1000):
        delta = goal_xy - current_xy
        distance = torch.linalg.norm(delta).item()

        if distance < tolerance:
            print(f"Goal reached at step={step}")
            break

        direction = delta / torch.linalg.norm(delta)
        current_xy = current_xy + direction * speed * dt

        pos = torch.tensor(
            [current_xy[0], current_xy[1], 0.1],
            device="cuda:0",
        )

        robot.set_pos(pos)
        scene.step()

        if step % 50 == 0:
            print(
                f"step={step:03d} "
                f"x={current_xy[0].item():.3f} "
                f"y={current_xy[1].item():.3f} "
                f"distance={distance:.3f}"
            )

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
