"""运行 Look Twice v3 的可续跑、严格配对实验矩阵。"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


POLICIES = (
    "single-shot",
    "fixed-multiview",
    "purify-fixed",
    "purify-random",
    "purify-information-gain",
)
PROFILES = (
    "static-mixed",
    "view-dependent-occlusion",
    "segmentation-degradation",
    "depth-degradation",
    "dynamic-change",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-count", type=int, default=20)
    parser.add_argument("--seed-offset", type=int, default=20000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--entrypoint", default="src/look_twice_v3.py")
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    return parser.parse_args()


def is_complete(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("schema_version") == 3 and bool(
        payload.get("metrics", {}).get("mission_success")
    )


def main() -> None:
    args = parse_args()
    if args.seed_count < 1 or args.workers < 1:
        raise SystemExit("--seed-count and --workers must be positive")
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, list[str]]] = []
    skipped = 0
    for policy in args.policies:
        for profile in args.profiles:
            for index in range(args.seed_count):
                seed = args.seed_offset + index
                name = f"{policy}__{profile}__seed-{seed}.json"
                output = raw_dir / name
                if is_complete(output):
                    skipped += 1
                    continue
                command = [
                    args.python,
                    args.entrypoint,
                    "--policy",
                    policy,
                    "--profile",
                    profile,
                    "--seed",
                    str(seed),
                    "--json-output",
                    str(output),
                ]
                jobs.append((name, command))

    def run_job(job: tuple[str, list[str]]) -> str:
        name, command = job
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        return name

    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_job, job): job[0] for job in jobs}
        for future in as_completed(futures):
            print(f"completed {future.result()}", flush=True)
            completed += 1

    rows = []
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        config, metrics = payload["configuration"], payload["metrics"]
        rows.append({"file": path.name, **config, **metrics})
    if not rows:
        raise SystemExit("No completed v3 episodes found")
    output = args.output_dir / "runs.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"finished: new={completed} skipped={skipped} total={len(rows)}")
    print("summary:", output)


if __name__ == "__main__":
    main()
