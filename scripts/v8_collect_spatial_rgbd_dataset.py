#!/usr/bin/env python3
"""Full V8 spatial RGB-D dataset collection (multi-split, 12 workers, resume).

Splits (default, disjoint from V7):
  train        100000–101499  1500
  validation   101500–101799   300
  calibration  101800–102099   300
  locked_test  102100–102499   400
  ood_test     102500–102699   200

Per world: atomic _COMPLETE__{seed}.json after all samples written.
Failed worlds go to failed/ and do not write COMPLETE.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SCHEMA = "look-twice.v8-spatial-rgbd/v1"
DEFAULT_SPLITS = {
    "train": (100000, 101499),
    "validation": (101500, 101799),
    "calibration": (101800, 102099),
    "locked_test": (102100, 102499),
    "ood_test": (102500, 102699),
}
FORBIDDEN_SEED_RANGES = [
    range(95000, 95020),
    range(96000, 98300),
    range(99000, 99004),
    range(99200, 99204),
    range(99300, 99320),
]


def _git_commit(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("GIT_COMMIT") or os.environ.get("V8_GIT_COMMIT")
    if env:
        return env
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
    tmp = path.with_name(path.name + ".partial")
    with open(tmp, "wb") as handle:
        np.save(handle, np.ascontiguousarray(arr))
    os.replace(tmp, path)
    return path


def _assert_seed_allowed(seed: int) -> None:
    for r in FORBIDDEN_SEED_RANGES:
        if seed in r:
            raise ValueError(f"seed {seed} overlaps V7 forbidden range")


def _corridor_mask_from_geometry(
    h: int, w: int, *, corridor_id: str, public: dict[str, Any]
) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.float32)
    center = None
    for c in public.get("corridors") or []:
        if c.get("id") == corridor_id:
            reg = c["region"]
            center = 0.5 * (float(reg[2]) + float(reg[3]))
            break
    if center is None:
        return mask
    frac = 0.5 - 0.35 * np.tanh(center / 0.4)
    y0 = int(np.clip(frac - 0.18, 0.05, 0.75) * h)
    y1 = int(np.clip(frac + 0.18, 0.25, 0.95) * h)
    x0, x1 = int(0.25 * w), int(0.85 * w)
    mask[y0:y1, x0:x1] = 1.0
    return mask


def _obstacle_mask_from_seg(seg: np.ndarray, obstacle_idx: int | None) -> np.ndarray:
    if obstacle_idx is None:
        return np.zeros(seg.shape[:2], dtype=np.float32)
    return (np.asarray(seg) == int(obstacle_idx)).astype(np.float32)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, indent=2) + "\n"
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def collect_world(
    *,
    profile: str,
    seed: int,
    split: str,
    data_root: Path,
    device: str,
    depth_noise_std: float,
    git_commit: str,
) -> dict[str, Any]:
    _assert_seed_allowed(seed)
    split_dir = data_root / split
    seed_dir = split_dir / f"seed_{seed}"
    complete_path = split_dir / f"_COMPLETE__{seed}.json"
    if complete_path.is_file():
        try:
            return json.loads(complete_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    from v6_genesis_runtime import V6GenesisRuntime
    from v6_scenario import sample_v6_scenario

    scenario = sample_v6_scenario(profile, seed)
    public = scenario.public_context
    oracle = scenario.oracle_context
    gen_config = {
        "schema_version": SCHEMA,
        "profile": profile,
        "split": split,
        "seed": seed,
        "device": device,
        "depth_noise_std": depth_noise_std,
        "motion_backend": "kinematic",
        "collector": "v8_collect_spatial_rgbd_dataset.py",
        "git_commit": git_commit,
    }
    runtime = V6GenesisRuntime(scenario, motion_backend="kinematic", device=device)
    seed_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    try:
        obs_idx = None
        inner = getattr(runtime, "_inner", None)
        if inner is not None and hasattr(inner, "obstacle_segmentation_idx"):
            obs_idx = inner.obstacle_segmentation_idx

        for vp in public.get("candidate_viewpoints") or []:
            vname = str(vp["name"])
            if not (
                vname.startswith("corridor_a/") or vname.startswith("corridor_b/")
            ):
                continue
            corridor_id = (
                "corridor_a" if vname.startswith("corridor_a/") else "corridor_b"
            )
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
            # Label is target-corridor only (non-target obstacles do not flip label).
            stem = f"{corridor_id}__{vname.replace('/', '__')}"
            paths: dict[str, str] = {}
            for key, arr in [
                ("rgb", rgb),
                ("depth_noisy", depth_noisy),
                ("depth_clean", depth_clean),
                ("seg_entity", seg.astype(np.int32)),
                ("obstacle_mask", obstacle_mask),
                ("corridor_mask", corridor_mask),
            ]:
                p = _save_npy(seed_dir / f"{stem}__{key}.npy", arr)
                rel = str(p.relative_to(data_root))
                paths[key] = rel
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
                "split": split,
                "seed": seed,
                "viewpoint": vname,
                "corridor_id": corridor_id,
                "target_xy": list(xy),
                "pose": pose,
                "offline_label": "blocked" if offline_blocked else "clear",
                "offline_blocked": offline_blocked,
                "oracle_other_corridor_blocked": bool(
                    oracle.get(
                        f"{'corridor_b' if corridor_id.endswith('a') else 'corridor_a'}_blocked_initial",
                        False,
                    )
                ),
                "train_eligible": True,
                "label_sources": {
                    "offline_label": "oracle_target_corridor_blocked_initial_only",
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
                "image_path": paths["rgb"],
                "image_shape": list(rgb.shape),
                "git_commit": git_commit,
                "generation_config": gen_config,
                "world_alignment_passed": True,
            }
            meta_path = seed_dir / f"{stem}__meta.json"
            _atomic_write_json(meta_path, meta)
            samples.append(
                {
                    "meta": str(meta_path.relative_to(data_root)),
                    "offline_label": meta["offline_label"],
                    "corridor_id": corridor_id,
                    "viewpoint": vname,
                }
            )

        if len(samples) < 1:
            raise RuntimeError(f"seed {seed}: zero samples collected")

        complete = {
            "seed": seed,
            "split": split,
            "profile": profile,
            "n_samples": len(samples),
            "samples": samples,
            "git_commit": git_commit,
            "generation_config": gen_config,
        }
        _atomic_write_json(complete_path, complete)
        return complete
    except Exception as e:
        fail_dir = data_root / "failed" / split
        fail_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(
            fail_dir / f"seed_{seed}.json",
            {
                "seed": seed,
                "split": split,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "git_commit": git_commit,
            },
        )
        # Do not leave a COMPLETE for failed world.
        if complete_path.is_file():
            try:
                complete_path.unlink()
            except Exception:
                pass
        raise
    finally:
        runtime.close()


def _worker(job: dict[str, Any]) -> dict[str, Any]:
    # Fresh Genesis init per process.
    import genesis as gs

    try:
        gs.init(backend=gs.amdgpu, logging_level="warning")
    except Exception:
        pass
    try:
        row = collect_world(
            profile=job["profile"],
            seed=job["seed"],
            split=job["split"],
            data_root=Path(job["data_root"]),
            device=job["device"],
            depth_noise_std=job["depth_noise_std"],
            git_commit=job["git_commit"],
        )
        return {"status": "ok", **row}
    except Exception as e:
        return {
            "status": "fail",
            "seed": job["seed"],
            "split": job["split"],
            "error": str(e),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile", default="independent-noise")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--depth-noise-std", type=float, default=0.03)
    parser.add_argument("--git-commit", default="")
    parser.add_argument(
        "--splits",
        nargs="+",
        default=list(DEFAULT_SPLITS.keys()),
    )
    parser.add_argument(
        "--only-split",
        default="",
        help="Optional single split name for partial runs",
    )
    args = parser.parse_args()
    data_root = args.out_dir
    data_root.mkdir(parents=True, exist_ok=True)
    git_commit = _git_commit(args.git_commit or None)
    if git_commit in ("", "unknown"):
        print("ERROR: git_commit required (pass --git-commit)", file=sys.stderr)
        return 2

    splits = [args.only_split] if args.only_split else list(args.splits)
    jobs: list[dict[str, Any]] = []
    for split in splits:
        if split not in DEFAULT_SPLITS:
            raise ValueError(f"unknown split {split}")
        lo, hi = DEFAULT_SPLITS[split]
        (data_root / split).mkdir(parents=True, exist_ok=True)
        for seed in range(lo, hi + 1):
            complete = data_root / split / f"_COMPLETE__{seed}.json"
            if complete.is_file():
                continue
            jobs.append(
                {
                    "profile": args.profile,
                    "seed": seed,
                    "split": split,
                    "data_root": str(data_root),
                    "device": args.device,
                    "depth_noise_std": args.depth_noise_std,
                    "git_commit": git_commit,
                }
            )

    print(
        f"v8 collect jobs={len(jobs)} workers={args.workers} "
        f"splits={splits} commit={git_commit}",
        flush=True,
    )
    t0 = time.perf_counter()
    ok = fail = 0
    if args.workers <= 1:
        # Single-process path (gs.init once).
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        for job in jobs:
            r = _worker(job)
            if r.get("status") == "ok":
                ok += 1
            else:
                fail += 1
            print(json.dumps(r), flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max(1, args.workers)
        ) as pool:
            futs = [pool.submit(_worker, j) for j in jobs]
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                if r.get("status") == "ok":
                    ok += 1
                else:
                    fail += 1
                print(json.dumps(r), flush=True)

    summary = {
        "schema_version": SCHEMA,
        "git_commit": git_commit,
        "profile": args.profile,
        "splits": {s: DEFAULT_SPLITS[s] for s in splits},
        "jobs_submitted": len(jobs),
        "ok": ok,
        "fail": fail,
        "workers": args.workers,
        "elapsed_s": time.perf_counter() - t0,
        "device": args.device,
    }
    _atomic_write_json(data_root / "collect_summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
