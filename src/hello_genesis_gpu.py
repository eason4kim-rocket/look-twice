import time
import genesis as gs


def main() -> None:
    gs.init(
        backend=gs.amdgpu,
        logging_level="info",
    )

    scene = gs.Scene(
        show_viewer=False,
        sim_options=gs.options.SimOptions(
            dt=0.01,
        ),
    )

    scene.add_entity(gs.morphs.Plane())

    box = scene.add_entity(
        gs.morphs.Box(
            size=(0.4, 0.4, 0.4),
            pos=(0.0, 0.0, 1.0),
        )
    )

    scene.build()

    start = time.perf_counter()

    for step in range(500):
        scene.step()

        if step % 100 == 0:
            print(f"step={step}, position={box.get_pos()}")

    elapsed = time.perf_counter() - start

    print(f"Finished 500 steps in {elapsed:.3f}s")
    print(f"Simulation throughput: {500 / elapsed:.1f} steps/s")
    print("Final box position:", box.get_pos())


if __name__ == "__main__":
    main()
