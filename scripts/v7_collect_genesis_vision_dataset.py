#!/usr/bin/env python3
"""Collect homology-aligned Genesis RGB for V7 vision calibration.

World-seed isolated splits (default):
  train       96000–96999
  validation  97000–97199
  calibration 97200–97499
  locked_test 98000–98299

Per world: 2 corridors × (carrier front + up to 4 scout side views).
Offline labels from oracle corridor blocked flags only.
Rejects worlds with world_alignment_passed=false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_SPLITS = {
    "train": (96000, 96999),
    "validation": (97000, 97199),
    "calibration": (97200, 97499),
    "locked_test": (98000, 98299),
}


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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crop_roi(rgb: np.ndarray, frac: tuple[float, float, float, float] = (0.25, 0.75, 0.30, 0.70)) -> np.ndarray:
    """Center-band crop approximating corridor ROI (y0,y1,x0,x1 fractions)."""
    arr = np.asarray(rgb)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    h, w = arr.shape[:2]
    y0, y1 = int(frac[0] * h), int(frac[1] * h)
    x0, x1 = int(frac[2] * w), int(frac[3] * w)
    crop = arr[y0:y1, x0:x1]
    return np.ascontiguousarray(crop)


def _resize_96(rgb: np.ndarray) -> np.ndarray:
    """Nearest-neighbor resize to 96×96 float32 RGB in [0,1]."""
    arr = np.asarray(rgb)
    if arr.dtype != np.float32 and arr.dtype != np.float64:
        arr = arr.astype(np.float32)
        if arr.max() > 1.5:
            arr = arr / 255.0
    else:
        arr = arr.astype(np.float32)
        if arr.max() > 1.5:
            arr = arr / 255.0
    h, w = arr.shape[:2]
    ys = np.linspace(0, h - 1, 96).astype(int)
    xs = np.linspace(0, w - 1, 96).astype(int)
    return np.ascontiguousarray(arr[ys][:, xs])


def collect_world(
    *,
    seed: int,
    profile: str,
    split: str,
    out_dir: Path,
    device: str,
    git_commit: str,
) -> dict:
    from v6_scenario import CARRIER_ID, SCOUT_ID, sample_v6_scenario

    scenario = sample_v6_scenario(profile, seed)
    import genesis as gs

    # Fresh process should call gs.init once; worker entry does.
    from v6_genesis_runtime import V6GenesisRuntime

    runtime = V6GenesisRuntime(scenario, motion_backend="kinematic", device=device)
    samples_meta = []
    try:
        audit = runtime.world_alignment_audit()
        if not audit.get("world_alignment_passed"):
            return {
                "seed": seed,
                "split": split,
                "skipped": True,
                "reason": "world_alignment_failed",
                "audit": audit,
                "n_samples": 0,
            }

        oracle = scenario.oracle_context
        public = scenario.public_context
        corridors = ["corridor_a", "corridor_b"]
        labels = {
            "corridor_a": "blocked" if oracle["corridor_a_blocked_initial"] else "clear",
            "corridor_b": "blocked" if oracle["corridor_b_blocked_initial"] else "clear",
        }

        # Carrier front: observe each corridor label from same pose (shared front).
        # Capture once; emit two samples with respective offline labels (honest:
        # front view is ambiguous; still record for training coverage).
        front_xy = (-0.5, 0.0)
        runtime.move_agent_to(CARRIER_ID, front_xy, allow_without_admit=True, admitted=False)
        raw = runtime.capture_raw(
            agent_id=CARRIER_ID,
            viewpoint="carrier_initial_front",
            viewpoint_xy=front_xy,
            predicted_coverage=0.55,
        )
        rgb = np.asarray(raw.rgb)
        crop = _crop_roi(rgb)
        small = _resize_96(crop)
        phys = audit.get("physical_obstacle_pose")
        for cid in corridors:
            sample_id = f"{split}__{seed}__{cid}__carrier_front"
            rel = Path(split) / f"{sample_id}.npz"
            path = out_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, small)
            raw_sha = _sha256_bytes(np.ascontiguousarray(rgb).tobytes())
            meta = {
                "sample_id": sample_id,
                "split": split,
                "seed": seed,
                "profile": profile,
                "corridor_id": cid,
                "viewpoint": "carrier_initial_front",
                "agent_id": CARRIER_ID,
                "offline_label": labels[cid],
                "image_path": str(rel),
                "image_sha256": _sha256_bytes(small.tobytes()),
                "raw_rgb_sha256": raw_sha,
                "git_commit": git_commit,
                "physical_obstacle_pose": phys,
                "oracle_obstacle_pose": audit.get("oracle_obstacle_pose"),
                "world_alignment_passed": True,
                "roi": "center_band_0.25-0.75_0.30-0.70",
                "resolution": [96, 96],
            }
            (out_dir / split / f"{sample_id}.json").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )
            samples_meta.append(meta)

        # Scout side views per corridor (4 each from public candidates).
        for vp in public.get("candidate_viewpoints") or []:
            if not vp.get("reachable", True):
                continue
            cid = str(vp.get("corridor_id") or "")
            if cid not in labels:
                continue
            name = str(vp["name"])
            xy = (float(vp["xy"][0]), float(vp["xy"][1]))
            runtime.move_agent_to(SCOUT_ID, xy, allow_without_admit=True, admitted=False)
            raw = runtime.capture_raw(
                agent_id=SCOUT_ID,
                viewpoint=name,
                viewpoint_xy=xy,
                predicted_coverage=float(vp.get("predicted_coverage") or 0.75),
            )
            rgb = np.asarray(raw.rgb)
            crop = _crop_roi(rgb)
            small = _resize_96(crop)
            sample_id = f"{split}__{seed}__{cid}__{name.replace('/', '_')}"
            rel = Path(split) / f"{sample_id}.npy"
            path = out_dir / rel
            np.save(path, small)
            meta = {
                "sample_id": sample_id,
                "split": split,
                "seed": seed,
                "profile": profile,
                "corridor_id": cid,
                "viewpoint": name,
                "agent_id": SCOUT_ID,
                "offline_label": labels[cid],
                "image_path": str(rel),
                "image_sha256": _sha256_bytes(small.tobytes()),
                "raw_rgb_sha256": _sha256_bytes(np.ascontiguousarray(rgb).tobytes()),
                "git_commit": git_commit,
                "physical_obstacle_pose": runtime.world_alignment_audit().get(
                    "physical_obstacle_pose"
                ),
                "oracle_obstacle_pose": audit.get("oracle_obstacle_pose"),
                "world_alignment_passed": True,
                "roi": "center_band_0.25-0.75_0.30-0.70",
                "resolution": [96, 96],
            }
            (out_dir / split / f"{sample_id}.json").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )
            samples_meta.append(meta)

        return {
            "seed": seed,
            "split": split,
            "skipped": False,
            "n_samples": len(samples_meta),
            "label_counts": {
                "clear": sum(1 for m in samples_meta if m["offline_label"] == "clear"),
                "blocked": sum(1 for m in samples_meta if m["offline_label"] == "blocked"),
            },
            "world_alignment_passed": True,
        }
    finally:
        runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--profile", default="independent-noise")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "validation", "calibration", "locked_test"],
    )
    parser.add_argument("--max-worlds-per-split", type=int, default=0, help="0=all")
    # Worker mode: single seed in this process (fresh Genesis).
    parser.add_argument("--worker-seed", type=int, default=None)
    parser.add_argument("--worker-split", default=None)
    args = parser.parse_args()

    git_commit = _git_commit()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.worker_seed is not None:
        assert args.worker_split
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        result = collect_world(
            seed=args.worker_seed,
            profile=args.profile,
            split=args.worker_split,
            out_dir=args.out_dir,
            device=args.device,
            git_commit=git_commit,
        )
        print(json.dumps(result), flush=True)
        return 0 if not result.get("skipped") else 1

    # Orchestrator: spawn one process per world seed.
    summary = {
        "schema_version": "look-twice.v7-genesis-vision-dataset/v1",
        "git_commit": git_commit,
        "profile": args.profile,
        "device": args.device,
        "splits": {},
    }
    for split in args.splits:
        if split not in DEFAULT_SPLITS:
            raise SystemExit(f"unknown split: {split}")
        lo, hi = DEFAULT_SPLITS[split]
        seeds = list(range(lo, hi + 1))
        if args.max_worlds_per_split > 0:
            seeds = seeds[: args.max_worlds_per_split]
        (args.out_dir / split).mkdir(parents=True, exist_ok=True)
        ok = 0
        skipped = 0
        n_samples = 0
        for seed in seeds:
            stem = f"{split}__{seed}"
            # Resume: if any sample json for seed exists, skip world.
            existing = list((args.out_dir / split).glob(f"{split}__{seed}__*.json"))
            if existing:
                ok += 1
                n_samples += len(existing)
                print(f"SKIP existing {stem} n={len(existing)}", flush=True)
                continue
            cmd = [
                args.python,
                str(Path(__file__).resolve()),
                "--out-dir",
                str(args.out_dir),
                "--device",
                args.device,
                "--profile",
                args.profile,
                "--worker-seed",
                str(seed),
                "--worker-split",
                split,
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            env.setdefault("PYOPENGL_PLATFORM", "egl")
            log = args.out_dir / split / f"_world_{seed}.log"
            with log.open("w", encoding="utf-8") as handle:
                proc = subprocess.run(
                    cmd,
                    cwd=str(ROOT),
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            # Parse last JSON line from log
            text = log.read_text(encoding="utf-8", errors="replace")
            line = ""
            for ln in reversed(text.splitlines()):
                if ln.strip().startswith("{"):
                    line = ln.strip()
                    break
            if not line:
                skipped += 1
                print(f"FAIL {stem} rc={proc.returncode}", flush=True)
                continue
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                print(f"BADJSON {stem}", flush=True)
                continue
            if result.get("skipped"):
                skipped += 1
                print(f"SKIP align {stem}", flush=True)
            else:
                ok += 1
                n_samples += int(result.get("n_samples") or 0)
                print(
                    f"OK {stem} n={result.get('n_samples')} labels={result.get('label_counts')}",
                    flush=True,
                )
        summary["splits"][split] = {
            "seed_range": [lo, hi],
            "worlds_requested": len(seeds),
            "worlds_ok": ok,
            "worlds_skipped": skipped,
            "n_samples": n_samples,
        }

    # Manifest SHA over all sample json paths.
    paths = sorted(str(p.relative_to(args.out_dir)) for p in args.out_dir.rglob("*.json") if p.name.count("__") >= 2)
    manifest = "\n".join(paths) + "\n"
    man_path = args.out_dir / "manifest_paths.txt"
    man_path.write_text(manifest, encoding="utf-8")
    summary["manifest_sha256"] = _sha256_bytes(manifest.encode("utf-8"))
    summary["n_manifest_entries"] = len(paths)
    (args.out_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
