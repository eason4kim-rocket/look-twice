"""将逐回合 CSV 汇总为按策略和噪声率分组的指标。"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.runs.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["policy"], row["noise_rate"])].append(row)

    def rate(group: list[dict[str, str]], field: str) -> float:
        return sum(row[field] == "True" for row in group) / len(group)

    def mean(group: list[dict[str, str]], field: str) -> float:
        return sum(float(row[field]) for row in group) / len(group)

    summary = []
    for (policy, noise_rate), group in sorted(groups.items()):
        summary.append(
            {
                "policy": policy,
                "noise_rate": noise_rate,
                "run_count": len(group),
                "safe_success_rate": rate(group, "safe_success"),
                "unsafe_crossing_rate": rate(group, "unsafe_crossing"),
                "wrong_detour_rate": rate(group, "wrong_detour"),
                "avg_observation_count": mean(group, "observation_count"),
                "avg_path_length": mean(group, "path_length"),
                "avg_elapsed_seconds": mean(group, "elapsed_seconds"),
                "avg_simulation_steps": mean(group, "simulation_steps"),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"summarized {len(rows)} runs into {len(summary)} groups")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
