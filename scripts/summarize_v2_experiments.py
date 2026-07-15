"""汇总 Look Twice v2 对照实验。"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.runs.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["policy"], row["profile"])].append(row)

    output_rows = []
    for (policy, profile), group in sorted(groups.items()):
        count = len(group)

        def mean(field: str) -> float:
            return sum(float(row[field]) for row in group) / count

        def mean_bool(field: str) -> float:
            return sum(row[field].lower() == "true" for row in group) / count

        output_rows.append(
            {
                "policy": policy,
                "profile": profile,
                "episodes": count,
                "safe_success_rate": mean_bool("safe_success"),
                "unsafe_crossing_rate": mean_bool("unsafe_crossing"),
                "wrong_detour_rate": mean_bool("wrong_detour"),
                "avg_observation_count": mean("observation_count"),
                "avg_replan_count": mean("replan_count"),
                "avg_path_length": mean("path_length"),
                "avg_gpu_perception_ms": mean("avg_gpu_perception_ms"),
                "avg_visible_fraction": mean("avg_visible_fraction"),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"wrote {len(output_rows)} aggregate rows to {args.output}")


if __name__ == "__main__":
    main()
