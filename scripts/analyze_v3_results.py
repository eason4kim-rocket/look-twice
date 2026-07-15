"""从 v3 原始 JSON 计算 ECE 与配对 bootstrap 策略差异。"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


def expected_calibration_error(samples: list[tuple[float, float]], bins: int = 10) -> float:
    if not samples:
        return 0.0
    total = len(samples)
    error = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [
            item
            for item in samples
            if low <= item[0] < high or (index == bins - 1 and item[0] == 1.0)
        ]
        if bucket:
            confidence = sum(item[0] for item in bucket) / len(bucket)
            frequency = sum(item[1] for item in bucket) / len(bucket)
            error += len(bucket) / total * abs(confidence - frequency)
    return error


def bootstrap_mean_interval(values: list[float], seed: int = 2026) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    estimates = []
    for _ in range(5000):
        estimates.append(sum(rng.choice(values) for _ in values) / len(values))
    estimates.sort()
    return (
        sum(values) / len(values),
        estimates[int(0.025 * (len(estimates) - 1))],
        estimates[int(0.975 * (len(estimates) - 1))],
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.raw_dir.glob("*.json"))]
    if not payloads:
        raise SystemExit("No v3 JSON files found")

    calibration: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    runs: dict[tuple[str, str, int], dict] = {}
    for payload in payloads:
        config = payload["configuration"]
        key = (config["policy"], config["profile"])
        runs[(config["policy"], config["profile"], int(config["seed"]))] = payload
        for evidence in payload["evidence"]:
            calibration[key].append(
                (
                    float(evidence["belief_after"]["p_blocked"]),
                    float(evidence["metadata"]["truth_blocked_at_observation"]),
                )
            )
    calibration_rows = [
        {
            "policy": policy,
            "profile": profile,
            "evidence_count": len(samples),
            "ece_10_bin": expected_calibration_error(samples),
        }
        for (policy, profile), samples in sorted(calibration.items())
    ]
    write_csv(args.output_dir / "calibration.csv", calibration_rows)

    comparison_rows = []
    active = "purify-information-gain"
    for baseline in ("purify-fixed", "purify-random"):
        profiles = sorted({profile for policy, profile, _ in runs if policy == active})
        for profile in profiles:
            seeds = sorted(
                seed
                for policy, candidate_profile, seed in runs
                if policy == active
                and candidate_profile == profile
                and (baseline, profile, seed) in runs
            )
            for metric in ("safe_success", "observation_count", "path_length", "information_gain_per_meter"):
                differences = [
                    float(runs[(active, profile, seed)]["metrics"][metric])
                    - float(runs[(baseline, profile, seed)]["metrics"][metric])
                    for seed in seeds
                ]
                mean, low, high = bootstrap_mean_interval(differences)
                comparison_rows.append(
                    {
                        "active_policy": active,
                        "baseline": baseline,
                        "profile": profile,
                        "metric": metric,
                        "paired_episodes": len(seeds),
                        "mean_difference": mean,
                        "bootstrap_ci95_low": low,
                        "bootstrap_ci95_high": high,
                    }
                )
    write_csv(args.output_dir / "paired_comparisons.csv", comparison_rows)
    print(f"analyzed {len(payloads)} episodes into {args.output_dir}")


if __name__ == "__main__":
    main()
