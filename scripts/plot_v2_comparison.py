"""绘制 Look Twice v2 动态安全性与主动观察成本。"""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


POLICIES = (
    "single-shot",
    "majority-vote",
    "purify-fixed",
    "purify-active",
)
LABELS = ("Single Shot", "Majority Vote", "Purify Fixed", "Purify Active")
COLORS = ("#d62728", "#9467bd", "#ff7f0e", "#1f77b4")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.input.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    lookup = {(row["policy"], row["profile"]): row for row in rows}

    dynamic_safe = [
        100 * float(lookup[(policy, "dynamic-appears")]["safe_success_rate"])
        for policy in POLICIES
    ]
    dynamic_observations = [
        float(lookup[(policy, "dynamic-appears")]["avg_observation_count"])
        for policy in POLICIES
    ]
    high_occlusion_observations = [
        float(lookup[(policy, "high-occlusion")]["avg_observation_count"])
        for policy in POLICIES
    ]

    x = np.arange(len(POLICIES))
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(x, dynamic_safe, color=COLORS)
    axes[0].set_title("Dynamic obstacle: safe success")
    axes[0].set_ylabel("Rate (%)")
    axes[0].set_ylim(0, 105)
    for index, value in enumerate(dynamic_safe):
        axes[0].text(index, value + 2, f"{value:.0f}%", ha="center")

    width = 0.36
    axes[1].bar(
        x - width / 2,
        dynamic_observations,
        width,
        label="Dynamic appears",
        color="#1f77b4",
    )
    axes[1].bar(
        x + width / 2,
        high_occlusion_observations,
        width,
        label="High occlusion",
        color="#7f7f7f",
    )
    axes[1].set_title("Observation cost")
    axes[1].set_ylabel("Average observations")
    axes[1].legend()

    for axis in axes:
        axis.set_xticks(x, LABELS, rotation=15, ha="right")
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("Look Twice v2: temporal evidence gating on AMD GPU")
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
