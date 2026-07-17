#!/usr/bin/env python3
"""Run the frozen 6×50 learned RGB-D Gate calibration matrix."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "dynamic-change",
    "repair-required",
)
SEEDS = range(30000, 30050)
ROW_SCHEMA = "look-twice.learned-rgbd-gate-calibration-row/v1"


@dataclass(frozen=True, slots=True)
class Job:
    profile: str
    seed: int

    @property
    def stem(self) -> str:
        return f"{self.profile}__{self.seed}"


def valid_row(path: Path, job: Job) -> bool:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        return (
            row["schema_version"] == ROW_SCHEMA
            and row["source_profile"] == job.profile
            and int(row["seed"]) == job.seed
            and row["true_label"] in ("clear", "blocked")
            and 0.0 <= float(row["p_clear"]) <= 1.0
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def run_one(payload: dict[str, Any]) -> dict[str, Any]:
    job = Job(payload["profile"], int(payload["seed"]))
    output = Path(payload["output"])
    if valid_row(output, job):
        return {"job": job.stem, "status": "skipped", "seconds": 0.0}
    command = [
        payload["python"],
        str(ROOT / "scripts" / "collect_v5_learned_gate_scene.py"),
        "--profile",
        job.profile,
        "--seed",
        str(job.seed),
        "--model",
        payload["model"],
        "--learned-calibration",
        payload["learned_calibration"],
        "--purify-bin",
        payload["purify_bin"],
        "--output",
        str(output),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    elapsed = time.perf_counter() - started
    log = Path(payload["log"])
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    ok = completed.returncode == 0 and valid_row(output, job)
    return {
        "job": job.stem,
        "status": "ok" if ok else "failed",
        "seconds": elapsed,
        "returncode": completed.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--learned-calibration", type=Path, required=True)
    parser.add_argument("--purify-bin", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args()
    jobs = [Job(profile, seed) for profile in PROFILES for seed in SEEDS]
    if args.max_jobs > 0:
        jobs = jobs[: args.max_jobs]
    rows = args.output_dir / "rows"
    logs = args.output_dir / "logs"
    work = [
        {
            "profile": job.profile,
            "seed": job.seed,
            "python": args.python,
            "model": str(args.model),
            "learned_calibration": str(args.learned_calibration),
            "purify_bin": str(args.purify_bin),
            "output": str(rows / f"{job.stem}.json"),
            "log": str(logs / f"{job.stem}.log"),
        }
        for job in jobs
    ]
    started = time.perf_counter()
    results = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=args.workers
    ) as executor:
        futures = [executor.submit(run_one, item) for item in work]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
    failed = [item for item in results if item["status"] == "failed"]
    if not failed and len(jobs) == len(PROFILES) * len(SEEDS):
        materialized = [
            json.loads((rows / f"{job.stem}.json").read_text(encoding="utf-8"))
            for job in jobs
        ]
        jsonl = args.output_dir / "calibration.jsonl"
        jsonl.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in materialized),
            encoding="utf-8",
        )
    summary = {
        "schema_version": "look-twice.learned-rgbd-gate-calibration/v1",
        "jobs": len(jobs),
        "ok": sum(item["status"] == "ok" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "failed": len(failed),
        "workers": args.workers,
        "wall_seconds": time.perf_counter() - started,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
