"""离线渲染所有候选视角，构建 Learned NBV 的 train/val/test JSONL。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


PROFILES = (
    "static-mixed",
    "view-dependent-occlusion",
    "segmentation-degradation",
    "depth-degradation",
    "dynamic-change",
)
SPLITS = {"train": 0, "validation": 10000, "test": 20000}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-scenes", type=int, default=200)
    parser.add_argument("--validation-scenes", type=int, default=50)
    parser.add_argument("--test-scenes", type=int, default=100)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--entrypoint", default="src/look_twice_v3.py")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    counts = {
        "train": args.train_scenes,
        "validation": args.validation_scenes,
        "test": args.test_scenes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    episode_dir = args.output_dir / "episodes"
    episode_dir.mkdir(exist_ok=True)
    jobs = []
    for split, offset in SPLITS.items():
        for index in range(counts[split]):
            seed = offset + index
            profile = PROFILES[index % len(PROFILES)]
            episode_path = episode_dir / f"{split}-{seed}.json"
            jobs.append((split, index, seed, profile, episode_path))

    def complete(path: Path) -> bool:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("schema_version") == 3 and bool(payload.get("oracle_labels"))

    def run_job(job) -> str:
        split, index, seed, profile, episode_path = job
        if not complete(episode_path):
            subprocess.run(
                [
                    args.python,
                    args.entrypoint,
                    "--profile",
                    profile,
                    "--policy",
                    "purify-information-gain",
                    "--seed",
                    str(seed),
                    "--collect-oracle-labels",
                    "--json-output",
                    str(episode_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        return f"{split}: {index + 1}/{counts[split]}"

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_job, job) for job in jobs]
        for future in as_completed(futures):
            print(future.result(), flush=True)

    for split in SPLITS:
        dataset_path = args.output_dir / f"{split}.jsonl"
        with dataset_path.open("w", encoding="utf-8") as dataset:
            split_jobs = sorted(
                (job for job in jobs if job[0] == split), key=lambda job: job[1]
            )
            for _, _, _, _, episode_path in split_jobs:
                payload = json.loads(episode_path.read_text(encoding="utf-8"))
                for record in payload["oracle_labels"]:
                    dataset.write(json.dumps(record, ensure_ascii=False) + "\n")
        print("dataset:", dataset_path)


if __name__ == "__main__":
    main()
