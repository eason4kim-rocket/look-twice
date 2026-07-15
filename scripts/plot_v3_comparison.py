"""绘制 v3 动态安全性、路径成本和单位移动信息增益。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


POLICIES = (
    "single-shot",
    "fixed-multiview",
    "purify-fixed",
    "purify-random",
    "purify-information-gain",
)
LABELS = ("Single", "Fixed Multi", "Purify Fixed", "Random NBV", "Info-Gain NBV")
COLORS = ("#d62728", "#9467bd", "#ff7f0e", "#7f7f7f", "#1f77b4")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.input.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    lookup = {(row["policy"], row["profile"]): row for row in rows}
    dynamic_safe = [
        100.0 * float(lookup[(policy, "dynamic-change")]["safe_success_rate"])
        for policy in POLICIES
    ]
    all_profile_path = [
        np.mean(
            [
                float(row["avg_path_length"])
                for row in rows
                if row["policy"] == policy
            ]
        )
        for policy in POLICIES
    ]
    information = [
        np.mean(
            [
                float(row["avg_information_gain_per_meter"])
                for row in rows
                if row["policy"] == policy
            ]
        )
        for policy in POLICIES
    ]

    x = np.arange(len(POLICIES))
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    axes[0].bar(x, dynamic_safe, color=COLORS)
    axes[0].set_title("Dynamic-change safe success")
    axes[0].set_ylabel("Rate (%)")
    axes[0].set_ylim(0, 105)
    axes[1].bar(x, all_profile_path, color=COLORS)
    axes[1].set_title("Mean path across profiles")
    axes[1].set_ylabel("Path length")
    axes[2].bar(x, information, color=COLORS)
    axes[2].set_title("Evidence efficiency")
    axes[2].set_ylabel("Information gain / meter")
    for axis in axes:
        axis.set_xticks(x, LABELS, rotation=20, ha="right")
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("Look Twice v3: noisy active perception on AMD GPU")
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)
    print("saved:", args.output)


if __name__ == "__main__":
    main()
