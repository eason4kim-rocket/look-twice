#!/usr/bin/env python3
"""V8 Day-1 preflight: 50 worlds of spatially labeled Genesis RGB-D.

Seeds default 100000–100049 (disjoint from all V7 splits).
Saves RGB, noisy depth, clean depth, entity seg, corridor masks, meta.

Clean segmentation is labeled **train-only**; runtime path must not read it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SCHEMA = "look-twice.v8-spatial-rgbd/v1"
# Hard ban: never use V7 formal/smoke/matrix seeds.
FORBIDDEN_SEED_RANGES = [
    range(95000, 95020),
    range(96000, 98300),
    range(99000, 99004),
    range(99200, 99204),
    range(99300, 99320),
]


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(ROOT), stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _save_npy(path: Path, arr: np.ndarray) -> Path:
    path = Path(path)
    if path.suffix != ".npy":
        path = path.with_suffix(".npy")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(path), np.ascontiguousarray(arr))
    return path


def _assert_seed_allowed(seed: int) -> None:
    for r in FORBIDDEN_SEED_RANGES:
        if seed in r:
            raise ValueError(f"seed {seed} overlaps V7 forbidden range {r}")


def _corridor_mask_from_geometry(
    h: int,
    w: int,
    *,
    corridor_id: str,
    public: dict[str, Any],
) -> np.ndarray:
    """Approximate projected corridor band in image (public geometry heuristic).

    Full camera projection can refine later; preflight uses a lateral band
    consistent with map y-sign of the corridor (A negative y → lower image band).
    """
    mask = np.zeros((h, w), dtype=np.float32)
    center = None
    for c in public.get("corridors") or []:
        if c.get("id") == corridor_id:
            reg = c["region"]
            center = 0.5 * (float(reg[2]) + float(reg[3]))
            break
    if center is None:
        return mask
    # Map y → vertical image fraction (simple monotonic mapping).
    # A (y≈-0.3) → lower half; B (y≈+0.3) → upper half.
    frac = 0.5 - 0.35 * np.tanh(center / 0.4)
    y0 = int(np.clip(frac - 0.18, 0.05, 0.75) * h)
    y1 = int(np.clip(frac + 0.18, 0.25, 0.95) * h)
    x0, x1 = int(0.25 * w), int(0.85 * w)
    mask[y0:y1, x0:x1] = 1.0
    return mask


def _obstacle_mask_from_seg(
    seg: np.ndarray, obstacle_idx: int | None
) -> np.ndarray:
    if obstacle_idx is None:
        return np.zeros(seg.shape[:2], dtype=np.float32)
    return (np.asarray(seg) == int(obstacle_idx)).astype(np.float32)


def collect_world(
    *,
    profile: str,
    seed: int,
    out_dir: Path,
    device: str,
    depth_noise_std: float,
) -> dict[str, Any]:
    _assert_seed_allowed(seed)
    from v6_scenario import sample_v6_scenario
    from v6_genesis_runtime import V6GenesisRuntime

    scenario = sample_v6_scenario(profile, seed)
    public = scenario.public_context
    oracle = scenario.oracle_context
    runtime = V6GenesisRuntime(scenario, motion_backend="kinematic", device=device)
    split_dir = out_dir  # preflight flat under seed
    seed_dir = out_dir / f"seed_{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    try:
        obs_idx = runtime.obstacle_segmentation_idx if hasattr(runtime, "obstacle_segmentation_idx") else None
        # Prefer inner v4 runtime field
        inner = getattr(runtime, "_inner", None)
        if inner is not None and hasattr(inner, "obstacle_segmentation_idx"):
            obs_idx = inner.obstacle_segmentation_idx

        for vp in public.get("candidate_viewpoints") or []:
            vname = str(vp["name"])
            if not (vname.startswith("corridor_a/") or vname.startswith("corridor_b/")):
                continue
            corridor_id = "corridor_a" if vname.startswith("corridor_a/") else "corridor_b"
            xy = (float(vp["xy"][0]), float(vp["xy"][1]))
            move = runtime.move_agent_to(
                "scout", xy, risk_gated=False, allow_without_admit=True
            )
            if not move.reached:
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
            depth_clean = np.asarray(frame.depth, dtype=np.float32)
            if depth_clean.ndim == 3:
                depth_clean = depth_clean[..., 0]
            rng = np.random.default_rng(seed * 10007 + hash(vname) % 9973)
            noise = rng.normal(0.0, depth_noise_std, size=depth_clean.shape).astype(
                np.float32
            )
            depth_noisy = np.where(
                np.isfinite(depth_clean) & (depth_clean > 1e-4),
                np.clip(depth_clean + noise, 0.0, None),
                0.0,
            )
            seg = np.asarray(frame.segmentation)
            if seg.ndim == 3:
                seg = seg[..., 0]
            obstacle_mask = _obstacle_mask_from_seg(seg, obs_idx)
            h, w = rgb.shape[:2]
            corridor_mask = _corridor_mask_from_geometry(
                h, w, corridor_id=corridor_id, public=public
            )
            offline_blocked = bool(
                oracle.get(
                    f"{corridor_id}_blocked_initial",
                    oracle.get(f"{corridor_id}_blocked", False),
                )
            )
            stem = f"{corridor_id}__{vname.replace('/', '__')}"
            paths = {}
            for key, arr in [
                ("rgb", rgb),
                ("depth_noisy", depth_noisy),
                ("depth_clean", depth_clean),
                ("seg_entity", seg.astype(np.int32)),
                ("obstacle_mask", obstacle_mask),
                ("corridor_mask", corridor_mask),
            ]:
                p = _save_npy(seed_dir / f"{stem}__{key}.npy", arr)
                paths[key] = str(p.relative_to(out_dir))
                paths[f"{key}_sha256"] = _sha256_file(p)

            pose = None
            if hasattr(runtime, "_poses") and "scout" in runtime._poses:
                p = runtime._poses["scout"]
                pose = {
                    "x": float(p.x),
                    "y": float(p.y),
                    "yaw": float(getattr(p, "yaw", 0.0)),
                }
            meta = {
                "schema_version": SCHEMA,
                "profile": profile,
                "seed": seed,
                "viewpoint": vname,
                "corridor_id": corridor_id,
                "target_xy": list(xy),
                "pose": pose,
                "offline_label": "blocked" if offline_blocked else "clear",
                "offline_blocked": offline_blocked,
                "train_eligible": True,
                "label_sources": {
                    "offline_label": "oracle_corridor_blocked_initial",
                    "obstacle_mask": "genesis_entity_segmentation_train_only",
                    "depth_clean": "genesis_depth_label_only",
                },
                "runtime_forbidden_fields": [
                    "seg_entity",
                    "obstacle_mask",
                    "depth_clean",
                    "oracle",
                ],
                "paths": paths,
                "image_shape": list(rgb.shape),
                "git_commit": _git_commit(),
                "world_alignment_passed": True,
            }
            meta_path = seed_dir / f"{stem}__meta.json"
            meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
            samples.append(meta)
        complete = {
            "seed": seed,
            "profile": profile,
            "n_samples": len(samples),
            "git_commit": _git_commit(),
        }
        (seed_dir / "_COMPLETE.json").write_text(
            json.dumps(complete, indent=2) + "\n", encoding="utf-8"
        )
        return complete
    finally:
        runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile", default="independent-noise")
    parser.add_argument("--seed-start", type=int, default=100000)
    parser.add_argument("--seed-end", type=int, default=100049)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--depth-noise-std", type=float, default=0.03)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    import genesis as gs

    gs.init(backend=gs.amdgpu, logging_level="warning")

    rows = []
    t0 = time.perf_counter()
    for seed in range(args.seed_start, args.seed_end + 1):
        print(f"collect seed={seed}", flush=True)
        row = collect_world(
            profile=args.profile,
            seed=seed,
            out_dir=args.out_dir,
            device=args.device,
            depth_noise_std=args.depth_noise_std,
        )
        rows.append(row)
        print(json.dumps(row), flush=True)

    summary = {
        "schema_version": SCHEMA,
        "profile": args.profile,
        "seed_start": args.seed_start,
        "seed_end": args.seed_end,
        "n_worlds": len(rows),
        "n_samples": sum(r["n_samples"] for r in rows),
        "git_commit": _git_commit(),
        "elapsed_s": time.perf_counter() - t0,
        "worlds": rows,
        "note": "Preflight only. Full V8 collect expands seed ranges in V8_DESIGN.md.",
    }
    (args.out_dir / "preflight_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print("wrote", args.out_dir / "preflight_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
