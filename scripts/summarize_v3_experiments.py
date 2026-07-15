"""汇总 v3 配对实验，并给出比例指标的 Wilson 95% 置信区间。"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    z = 1.959963984540054
    estimate = successes / total
    denominator = 1.0 + z * z / total
    center = (estimate + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(
        estimate * (1.0 - estimate) / total + z * z / (4.0 * total * total)
    ) / denominator
    return center - margin, center + margin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.runs.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["policy"], row["profile"])].append(row)

    output_rows = []
    for (policy, profile), group in sorted(groups.items()):
        total = len(group)
        safe = sum(row["safe_success"].lower() == "true" for row in group)
        unsafe = sum(row["unsafe_crossing"].lower() == "true" for row in group)
        low, high = wilson_interval(safe, total)
        def numeric(value: str) -> float:
            if value.lower() == "true":
                return 1.0
            if value.lower() == "false":
                return 0.0
            return float(value)

        mean = lambda key: sum(numeric(row[key]) for row in group) / total
        output_rows.append(
            {
                "policy": policy,
                "profile": profile,
                "episodes": total,
                "safe_success_rate": safe / total,
                "safe_ci95_low": low,
                "safe_ci95_high": high,
                "unsafe_crossing_rate": unsafe / total,
                "avg_wrong_detour": mean("wrong_detour"),
                "avg_observations": mean("observation_count"),
                "avg_replans": mean("replan_count"),
                "avg_path_length": mean("path_length"),
                "avg_brier_score": mean("brier_score"),
                "avg_final_entropy": mean("final_entropy"),
                "avg_information_gain_per_meter": mean("information_gain_per_meter"),
                "avg_sensor_corruption_ms": mean("avg_sensor_corruption_ms"),
                "avg_perception_ms": mean("avg_perception_ms"),
                "unresolved_gate_entries": sum(
                    int(float(row["unresolved_gate_entries"])) for row in group
                ),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)
    print("aggregate:", args.output)


if __name__ == "__main__":
    main()
