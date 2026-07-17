#!/usr/bin/env python3
"""Collect four auditable Genesis RGB-D samples for one v5 world."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd import MODEL_SCHEMA, array_sha256, preprocess_rgbd
from v4_evidence import corrupt_evidence_frame
from v5_scenario import sample_v5_scenario


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--split", choices=("train", "calibration", "validation", "test"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    import genesis as gs
    from v5_genesis_runtime import V5GenesisRuntime

    scenario = sample_v5_scenario(args.profile, args.seed)
    gs.init(backend=gs.amdgpu, logging_level="warning")
    runtime = V5GenesisRuntime(scenario, motion_backend="kinematic")
    samples_dir = args.output_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    try:
        observation_index = 0
        for candidate in scenario.public_context["candidate_viewpoints"]:
            name = str(candidate["name"])
            if not name.startswith(("left_", "right_")) or not candidate["reachable"]:
                continue
            xy = (float(candidate["xy"][0]), float(candidate["xy"][1]))
            motion = runtime.move_to(xy)
            if not motion.reached:
                continue
            runtime.wait_steps(3)
            frame = runtime.capture_raw(
                viewpoint=name,
                viewpoint_xy=xy,
                predicted_coverage=float(candidate["predicted_coverage"]),
            )
            corrupted = corrupt_evidence_frame(
                frame,
                runtime.evidence_scenario,
                observation_index=observation_index,
                repair_action_kind=("initial" if observation_index == 0 else "side_view"),
                device="cuda:0",
            )
            features = preprocess_rgbd(
                rgb=corrupted.rgb,
                depth=corrupted.depth,
                risk_roi=frame.risk_roi,
                expected_clear_depth=frame.expected_clear_depth,
            )
            label = int(scenario.truth_nav_blocked_at(runtime.current_step))
            stem = f"{args.split}__{args.profile}__{args.seed}__{name}"
            sample_path = samples_dir / f"{stem}.npz"
            np.savez_compressed(sample_path, x=features.astype(np.float16), y=np.int64(label))
            records.append(
                {
                    "schema_version": MODEL_SCHEMA,
                    "split": args.split,
                    "profile": args.profile,
                    "seed": args.seed,
                    "viewpoint": name,
                    "viewpoint_xy": list(xy),
                    "capture_step": runtime.current_step,
                    "label_blocked": label,
                    "sample_path": str(sample_path.relative_to(args.output_dir)),
                    "sample_sha256": file_sha256(sample_path),
                    "input_sha256": array_sha256(features),
                    "raw_rgb_sha256": array_sha256(np.asarray(frame.rgb)),
                    "raw_depth_sha256": array_sha256(np.asarray(frame.depth)),
                    "oracle_segmentation_sha256": array_sha256(np.asarray(frame.segmentation)),
                    "corrupted_rgb_sha256": array_sha256(corrupted.rgb),
                    "corrupted_depth_sha256": array_sha256(corrupted.depth),
                    "corruption": corrupted.audit.to_wire(),
                    "expected_clear_depth": float(frame.expected_clear_depth),
                    "risk_roi": {
                        "x_min": frame.risk_roi.x_min,
                        "y_min": frame.risk_roi.y_min,
                        "x_max": frame.risk_roi.x_max,
                        "y_max": frame.risk_roi.y_max,
                    },
                    "motion_path_length": float(motion.path_length),
                    "gpu": runtime.environment.get("gpu"),
                    "genesis": runtime.environment.get("genesis"),
                    "rocm": runtime.environment.get("rocm"),
                }
            )
            observation_index += 1
    finally:
        runtime.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fragment = args.output_dir / f"manifest__{args.split}__{args.profile}__{args.seed}.json"
    fragment.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fragment": str(fragment), "samples": len(records), "labels": [r["label_blocked"] for r in records]}))
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
