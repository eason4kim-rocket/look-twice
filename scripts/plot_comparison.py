"""从汇总 CSV 生成三策略安全性与观察成本对比图。"""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


POLICIES = ("single-shot", "majority-vote", "purify")
COLORS = {
    "single-shot": "#d62728",
    "majority-vote": "#9467bd",
    "purify": "#1f77b4",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.input.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for policy in POLICIES:
        policy_rows = sorted(
            (row for row in rows if row["policy"] == policy),
            key=lambda row: float(row["noise_rate"]),
        )
        noise_rates = [float(row["noise_rate"]) for row in policy_rows]
        safe_success = [
            100.0 * float(row["safe_success_rate"]) for row in policy_rows
        ]
        observations = [
            float(row["avg_observation_count"]) for row in policy_rows
        ]
        axes[0].plot(
            noise_rates,
            safe_success,
            marker="o",
            linewidth=2,
            color=COLORS[policy],
            label=policy,
        )
        axes[1].plot(
            noise_rates,
            observations,
            marker="o",
            linewidth=2,
            color=COLORS[policy],
            label=policy,
        )

    axes[0].set_title("Safe task success")
    axes[0].set_ylabel("Rate (%)")
    axes[0].set_ylim(0, 105)
    axes[1].set_title("Observation cost")
    axes[1].set_ylabel("Average observations")
    for axis in axes:
        axis.set_xlabel("Observation noise rate")
        axis.set_xticks((0.0, 0.1, 0.2, 0.3))
        axis.grid(alpha=0.3)
        axis.legend()

    figure.suptitle("Look Twice policy comparison")
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180)
    plt.close(figure)
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
