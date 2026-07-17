#!/usr/bin/env python3
"""Collect one frozen learned RGB-D split without merging global manifests."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

from run_v5_learned_rgbd_collection import (
    FULL_SPLITS,
    Job,
    profile_for_seed,
    run_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(FULL_SPLITS), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    seeds = FULL_SPLITS[args.split]
    jobs = [
        Job(args.split, profile_for_seed(seed, seeds.start), seed)
        for seed in seeds
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    logs = args.output_dir / "logs"
    results = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers
    ) as executor:
        futures = [
            executor.submit(run_job, root, args.output_dir, logs, job)
            for job in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result), flush=True)
    failed = sum(item["status"] == "failed" for item in results)
    print(
        json.dumps(
            {
                "split": args.split,
                "worlds": len(results),
                "ok": sum(item["status"] == "ok" for item in results),
                "skipped": sum(
                    item["status"] == "skipped" for item in results
                ),
                "failed": failed,
            }
        ),
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
