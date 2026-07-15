"""从 v3 JSON 绘制随机场景、候选视角、证据和实际轨迹。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


CANDIDATES = {
    "left_near": (-0.6, 1.2),
    "left_far": (-0.2, 1.7),
    "right_near": (0.0, -1.2),
    "right_far": (0.4, -1.7),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    sample = data["scenario_sample"]
    trajectory = data["trajectory"]
    figure, axis = plt.subplots(figsize=(9, 7))
    axis.plot(
        [point["x"] for point in trajectory],
        [point["y"] for point in trajectory],
        color="#1f77b4",
        linewidth=2.3,
        label="robot trajectory",
    )
    axis.add_patch(
        Rectangle(
            (0.4, -0.4),
            0.8,
            0.8,
            facecolor="#2ca02c",
            alpha=0.16,
            edgecolor="#2ca02c",
            label="risk region",
        )
    )
    occluder_xy = sample["occluder_xy"]
    occluder_size = sample["occluder_size"]
    axis.add_patch(
        Rectangle(
            (
                occluder_xy[0] - occluder_size[0] / 2,
                occluder_xy[1] - occluder_size[1] / 2,
            ),
            occluder_size[0],
            occluder_size[1],
            facecolor="#7f7f7f",
            alpha=0.65,
            label="known occluder",
        )
    )
    obstacle_xy = sample["obstacle_xy"]
    obstacle_size = sample["obstacle_size"]
    axis.add_patch(
        Rectangle(
            (
                obstacle_xy[0] - obstacle_size[0] / 2,
                obstacle_xy[1] - obstacle_size[1] / 2,
            ),
            obstacle_size[0],
            obstacle_size[1],
            facecolor="#d62728",
            alpha=0.35,
            label="unknown obstacle truth",
        )
    )
    unreachable = set(sample["unreachable_viewpoints"])
    for name, (x, y) in CANDIDATES.items():
        axis.scatter(
            x,
            y,
            marker="x" if name in unreachable else "o",
            color="#d62728" if name in unreachable else "#ff7f0e",
            s=65,
        )
        axis.text(x + 0.05, y + 0.06, name, fontsize=8)
    for index, evidence in enumerate(data["evidence"]):
        x, y = CANDIDATES[evidence["viewpoint"]]
        belief = evidence["belief_after"]
        axis.annotate(
            f"#{index + 1} {evidence['result']}\np={belief['p_blocked']:.2f}, H={belief['entropy']:.2f}",
            xy=(x, y),
            xytext=(8, 12 + 26 * (index % 2)),
            textcoords="offset points",
            fontsize=8,
            arrowprops={"arrowstyle": "->", "alpha": 0.5},
        )
    axis.scatter(-2.0, 0.0, marker="s", s=80, color="#1f77b4", label="start")
    axis.scatter(2.0, 0.0, marker="*", s=140, color="#2ca02c", label="goal")
    config, metrics = data["configuration"], data["metrics"]
    axis.set_title(
        f"{config['policy']} | {config['profile']} | seed={config['seed']}\n"
        f"safe={metrics['safe_success']} observations={metrics['observation_count']} "
        f"path={metrics['path_length']:.2f}"
    )
    axis.set_xlabel("x")
    axis.set_ylabel("y")
    axis.set_aspect("equal")
    axis.grid(alpha=0.22)
    axis.legend(loc="upper right", fontsize=8)
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)
    print("saved:", args.output)


if __name__ == "__main__":
    main()
