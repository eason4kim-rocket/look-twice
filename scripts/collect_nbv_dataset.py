"""离线渲染所有候选视角，构建 Learned NBV 的 train/val/test JSONL。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    args = parser.parse_args()
    counts = {
        "train": args.train_scenes,
        "validation": args.validation_scenes,
        "test": args.test_scenes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    episode_dir = args.output_dir / "episodes"
    episode_dir.mkdir(exist_ok=True)
    for split, offset in SPLITS.items():
        dataset_path = args.output_dir / f"{split}.jsonl"
        with dataset_path.open("w", encoding="utf-8") as dataset:
            for index in range(counts[split]):
                seed = offset + index
                profile = PROFILES[index % len(PROFILES)]
                episode_path = episode_dir / f"{split}-{seed}.json"
                if not episode_path.exists():
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
                payload = json.loads(episode_path.read_text(encoding="utf-8"))
                for record in payload["oracle_labels"]:
                    dataset.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"{split}: {index + 1}/{counts[split]}", flush=True)
        print("dataset:", dataset_path)


if __name__ == "__main__":
    main()
