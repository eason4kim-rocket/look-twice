#!/usr/bin/env python3
"""Resume-safe paired Genesis collection for the learned RGB-D sensor."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "dynamic-change",
    "repair-required",
)
FULL_SPLITS = {
    "train": range(10000, 10200),
    "calibration": range(30000, 30050),
    "validation": range(40000, 40040),
    "test": range(50000, 50100),
}
SMOKE_SPLITS = {
    "train": range(10000, 10004),
    "calibration": range(30000, 30002),
    "validation": range(40000, 40002),
    "test": range(50000, 50002),
}


@dataclass(frozen=True, slots=True)
class Job:
    split: str
    profile: str
    seed: int

    @property
    def stem(self) -> str:
        return f"{self.split}__{self.profile}__{self.seed}"


def profile_for_seed(seed: int, split_start: int) -> str:
    """Consecutive clear/blocked seed pairs share one profile."""
    return PROFILES[((seed - split_start) // 2) % len(PROFILES)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fragment_path(output: Path, job: Job) -> Path:
    return output / f"manifest__{job.stem}.json"


def fragment_is_complete(output: Path, job: Job) -> bool:
    path = fragment_path(output, job)
    if not path.is_file():
        return False
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        return bool(records) and all(
            (output / row["sample_path"]).is_file()
            and sha256(output / row["sample_path"]) == row["sample_sha256"]
            for row in records
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def run_job(root: Path, output: Path, logs: Path, job: Job) -> dict[str, Any]:
    if fragment_is_complete(output, job):
        return {"job": job.stem, "status": "skipped", "seconds": 0.0}
    command = [
        sys.executable,
        str(root / "scripts" / "collect_v5_learned_rgbd_scene.py"),
        "--profile",
        job.profile,
        "--seed",
        str(job.seed),
        "--split",
        job.split,
        "--output-dir",
        str(output),
    ]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    elapsed = time.perf_counter() - started
    logs.mkdir(parents=True, exist_ok=True)
    (logs / f"{job.stem}.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    status = "ok" if completed.returncode == 0 and fragment_is_complete(output, job) else "failed"
    return {
        "job": job.stem,
        "status": status,
        "seconds": elapsed,
        "returncode": completed.returncode,
    }


def merge_manifests(output: Path, jobs: list[Job]) -> dict[str, int]:
    counts: dict[str, int] = {}
    split_seeds: dict[str, set[int]] = {}
    for split in sorted({job.split for job in jobs}):
        records: list[dict[str, Any]] = []
        seeds: set[int] = set()
        for job in sorted((item for item in jobs if item.split == split), key=lambda x: x.seed):
            rows = json.loads(fragment_path(output, job).read_text(encoding="utf-8"))
            records.extend(rows)
            seeds.add(job.seed)
        (output / f"manifest_{split}.json").write_text(
            json.dumps(records, indent=2) + "\n", encoding="utf-8"
        )
        counts[split] = len(records)
        split_seeds[split] = seeds
    names = sorted(split_seeds)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = split_seeds[left] & split_seeds[right]
            if overlap:
                raise RuntimeError(f"seed leakage between {left} and {right}: {sorted(overlap)}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        parser.error("workers must be 1 or 2 for Genesis camera stability")
    root = Path(__file__).resolve().parents[1]
    split_spec = SMOKE_SPLITS if args.mode == "smoke" else FULL_SPLITS
    jobs = [
        Job(split, profile_for_seed(seed, seeds.start), seed)
        for split, seeds in split_spec.items()
        for seed in seeds
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logs = args.output_dir / "logs"
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_job, root, args.output_dir, logs, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
    failed = [row for row in results if row["status"] == "failed"]
    counts = {} if failed else merge_manifests(args.output_dir, jobs)
    summary = {
        "schema_version": "look-twice.learned-rgbd-collection/v1",
        "mode": args.mode,
        "workers": args.workers,
        "worlds": len(jobs),
        "ok": sum(row["status"] == "ok" for row in results),
        "skipped": sum(row["status"] == "skipped" for row in results),
        "failed": len(failed),
        "sample_counts": counts,
        "profiles": list(PROFILES),
        "split_seed_ranges": {
            name: [values.start, values.stop - 1] for name, values in split_spec.items()
        },
        "wall_seconds": time.perf_counter() - started,
        "results": sorted(results, key=lambda row: row["job"]),
    }
    (args.output_dir / "collection_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in ("worlds", "ok", "skipped", "failed", "sample_counts", "wall_seconds")}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
