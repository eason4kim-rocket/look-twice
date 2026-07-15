"""从结构化运行 JSON 生成 Look Twice 俯视轨迹图。"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


POINTS = {
    "start": (-2.0, 0.0),
    "inspection_left": (-0.6, 1.2),
    "inspection_right": (-0.6, -1.2),
    "detour": (0.8, 1.5),
    "goal": (2.0, 0.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    config = data["configuration"]
    trajectory = data["trajectory"]

    figure, axis = plt.subplots(figsize=(9, 6))
    axis.set_aspect("equal")
    axis.set_xlim(-2.5, 2.5)
    axis.set_ylim(-1.8, 2.0)
    axis.grid(alpha=0.25)
    axis.set_xlabel("x")
    axis.set_ylabel("y")

    axis.add_patch(
        Rectangle(
            (-0.25, -0.6),
            0.5,
            1.2,
            facecolor="#777777",
            alpha=0.55,
            label="occluder",
        )
    )
    axis.add_patch(
        Rectangle(
            (0.4, -0.4),
            0.8,
            0.8,
            fill=False,
            edgecolor="#d62728",
            linestyle="--",
            linewidth=1.5,
            label="inspected region",
        )
    )
    if config["scenario"] == "blocked":
        axis.add_patch(
            Rectangle(
                (0.55, -0.25),
                0.5,
                0.5,
                facecolor="#d62728",
                alpha=0.7,
                label="blocking obstacle",
            )
        )

    point_colors = {
        "start": "#1f77b4",
        "inspection_left": "#ffbf00",
        "inspection_right": "#ff7f0e",
        "detour": "#9467bd",
        "goal": "#2ca02c",
    }
    for name, (x, y) in POINTS.items():
        axis.scatter(x, y, s=75, color=point_colors[name], zorder=4)
        axis.annotate(name, (x, y), xytext=(5, 7), textcoords="offset points")

    xs = [point["x"] for point in trajectory]
    ys = [point["y"] for point in trajectory]
    axis.plot(xs, ys, color="#0066cc", linewidth=2.5, label="robot trajectory")

    for index, evidence in enumerate(data["evidence"], start=1):
        x, y = POINTS[evidence["viewpoint"]]
        label = (
            f"E{index}: {evidence['result']} "
            f"({evidence['confidence']:.2f})"
        )
        offset_y = 20 + 16 * (index - 1)
        axis.annotate(
            label,
            (x, y),
            xytext=(12, offset_y),
            textcoords="offset points",
            fontsize=8,
            arrowprops={"arrowstyle": "->", "alpha": 0.5},
        )

    title = (
        f"{config['policy']} | scenario={config['scenario']} | "
        f"noise={config['noise_profile']} ({config.get('noise_rate', 0.0)})\n"
        f"belief={data['outcome']['belief_status']} | "
        f"observations={data['metrics']['observation_count']} | "
        f"path={data['metrics']['path_length']:.2f}"
    )
    axis.set_title(title)
    axis.legend(loc="upper right", fontsize=8)
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
