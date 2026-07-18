#!/usr/bin/env python3
"""Dump 99002-class false-blocked vision diagnostics (honest failure cases).

For each (profile, seed) re-captures Genesis RGB at A/B side viewpoints,
runs the calibrated torch head + conformal, and saves:
  - raw RGB .npy
  - 96×96 ROI .npy
  - meta JSON (p_blocked, prediction_set, pose, oracle labels)

Does NOT retrain, retune thresholds, or open locked_test.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--conformal-artifact", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--cases",
        nargs="+",
        default=[
            "independent-noise:99002",
            "shared-occlusion:99002",
            "evidence-echo:99002",
        ],
        help="profile:seed pairs",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    import genesis as gs

    from v6_genesis_runtime import V6GenesisRuntime
    from v6_scenario import sample_v6_scenario
    from v7_vision_model import (
        load_conformal_artifact,
        load_genesis_corridor_head,
        predict_label,
        preprocess_rgb_for_model,
    )

    gs.init(backend=gs.amdgpu, logging_level="warning")
    model, ckpt_sha, _ = load_genesis_corridor_head(
        args.checkpoint, device=args.device
    )
    conformal = load_conformal_artifact(args.conformal_artifact)

    index: list[dict] = []
    for case in args.cases:
        profile, seed_s = case.split(":")
        seed = int(seed_s)
        scenario = sample_v6_scenario(profile, seed)
        oracle = scenario.oracle_context
        public = scenario.public_context
        case_dir = args.out_dir / f"{profile}__{seed}"
        case_dir.mkdir(parents=True, exist_ok=True)
        runtime = V6GenesisRuntime(
            scenario, motion_backend="kinematic", device=args.device
        )
        try:
            case_rows = []
            for vp in public.get("candidate_viewpoints") or []:
                vname = str(vp["name"])
                if not (
                    vname.startswith("corridor_a/") or vname.startswith("corridor_b/")
                ):
                    continue
                corridor = (
                    "corridor_a" if vname.startswith("corridor_a/") else "corridor_b"
                )
                xy = (float(vp["xy"][0]), float(vp["xy"][1]))
                move = runtime.move_agent_to(
                    "scout", xy, risk_gated=False, allow_without_admit=True
                )
                if not move.reached:
                    print(f"skip unreachable {vname}", flush=True)
                    continue
                runtime.wait_steps(2)
                frame = runtime.capture_raw(
                    agent_id="scout",
                    viewpoint=vname,
                    viewpoint_xy=xy,
                    predicted_coverage=float(vp.get("predicted_coverage", 0.75)),
                )
                rgb = np.asarray(frame.rgb, dtype=np.float32)
                if rgb.max() > 1.5:
                    rgb = rgb / 255.0
                roi96 = preprocess_rgb_for_model(rgb, already_96=False)
                pred = predict_label(
                    model, rgb, conformal, device=args.device, already_96=False
                )
                oracle_blocked = bool(
                    oracle.get(
                        f"{corridor}_blocked_initial",
                        oracle.get(f"{corridor}_blocked", False),
                    )
                )
                offline_label = "blocked" if oracle_blocked else "clear"
                stem = vname.replace("/", "__")
                raw_path = case_dir / f"{stem}__raw.npy"
                roi_path = case_dir / f"{stem}__roi96.npy"
                np.save(raw_path, rgb)
                np.save(roi_path, roi96)
                pose = None
                if hasattr(runtime, "_poses") and "scout" in runtime._poses:
                    p = runtime._poses["scout"]
                    pose = {
                        "x": float(p.x),
                        "y": float(p.y),
                        "yaw": float(getattr(p, "yaw", 0.0)),
                    }
                row = {
                    "profile": profile,
                    "seed": seed,
                    "viewpoint": vname,
                    "corridor_id": corridor,
                    "target_xy": list(xy),
                    "oracle_blocked": oracle_blocked,
                    "offline_label": offline_label,
                    "p_blocked": pred["p_blocked"],
                    "prediction_set": pred["prediction_set"],
                    "value": pred["value"],
                    "false_blocked": (
                        offline_label == "clear" and pred["value"] == "blocked"
                    ),
                    "false_clear": (
                        offline_label == "blocked" and pred["value"] == "clear"
                    ),
                    "pose": pose,
                    "raw_path": str(raw_path.relative_to(args.out_dir)),
                    "roi96_path": str(roi_path.relative_to(args.out_dir)),
                    "raw_shape": list(rgb.shape),
                    "roi96_shape": list(roi96.shape),
                }
                (case_dir / f"{stem}__meta.json").write_text(
                    json.dumps(row, indent=2) + "\n", encoding="utf-8"
                )
                case_rows.append(row)
                print(json.dumps(row), flush=True)

            summary = {
                "profile": profile,
                "seed": seed,
                "oracle": {
                    "corridor_a_blocked": bool(
                        oracle.get(
                            "corridor_a_blocked_initial",
                            oracle.get("corridor_a_blocked"),
                        )
                    ),
                    "corridor_b_blocked": bool(
                        oracle.get(
                            "corridor_b_blocked_initial",
                            oracle.get("corridor_b_blocked"),
                        )
                    ),
                },
                "checkpoint_sha256": ckpt_sha,
                "conformal_artifact_sha256": conformal.artifact_sha256,
                "n_views": len(case_rows),
                "false_blocked_views": [
                    r["viewpoint"] for r in case_rows if r["false_blocked"]
                ],
                "views": case_rows,
            }
            (case_dir / "case_summary.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
            index.append(summary)
        finally:
            runtime.close()

    bundle = {
        "schema_version": "look-twice.v7-vision-false-blocked-diagnostics/v1",
        "note": (
            "Honest failure cases: model false-blocked on clear corridor "
            "(fail-closed detour). Not a contract wiring bug. Do not retune "
            "thresholds or retrain from these smoke seeds."
        ),
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": ckpt_sha,
        "conformal_artifact": str(args.conformal_artifact),
        "conformal_artifact_sha256": conformal.artifact_sha256,
        "cases": index,
    }
    (args.out_dir / "diagnostics_index.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", args.out_dir / "diagnostics_index.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
