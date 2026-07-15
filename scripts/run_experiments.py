"""批量运行 Look Twice 对照实验，支持中断后续跑。"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


POLICIES = ("single-shot", "majority-vote", "purify")
SCENARIOS = ("clear", "blocked")
NOISE_RATES = (0.0, 0.1, 0.2, 0.3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-count", type=int, default=20)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--entrypoint", default="src/look_twice_v0.py")
    return parser.parse_args()


def is_complete(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("metrics", {}).get("mission_success"))


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    run_count = 0
    skipped_count = 0
    for policy in POLICIES:
        for scenario in SCENARIOS:
            for noise_rate in NOISE_RATES:
                for seed in range(args.seed_count):
                    filename = (
                        f"{policy}__{scenario}__noise-{noise_rate:.1f}"
                        f"__seed-{seed:02d}.json"
                    )
                    output_path = raw_dir / filename
                    if is_complete(output_path):
                        skipped_count += 1
                        continue

                    command = [
                        args.python,
                        args.entrypoint,
                        "--policy",
                        policy,
                        "--scenario",
                        scenario,
                        "--noise-profile",
                        "random",
                        "--noise-rate",
                        str(noise_rate),
                        "--seed",
                        str(seed),
                        "--json-output",
                        str(output_path),
                    ]
                    subprocess.run(
                        command,
                        check=True,
                        stdout=subprocess.DEVNULL,
                    )
                    run_count += 1
                    print(f"completed {filename}", flush=True)

    rows = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        config = data["configuration"]
        metrics = data["metrics"]
        rows.append(
            {
                "file": path.name,
                **config,
                "mission_success": metrics["mission_success"],
                "safe_success": metrics["safe_success"],
                "unsafe_crossing": metrics["unsafe_crossing"],
                "wrong_detour": metrics["wrong_detour"],
                "observation_count": metrics["observation_count"],
                "path_length": metrics["path_length"],
                "elapsed_seconds": metrics["elapsed_seconds"],
                "simulation_steps": metrics["simulation_steps"],
            }
        )

    summary_path = args.output_dir / "runs.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"finished: new={run_count} skipped={skipped_count} total={len(rows)}"
    )
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
