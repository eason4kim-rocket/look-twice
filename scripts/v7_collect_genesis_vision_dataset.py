#!/usr/bin/env python3
"""Collect homology-aligned Genesis RGB for V7 vision calibration (v2).

Fixes vs preflight invalid collect:
  - No dual-label of one carrier_front RGB as A and B (front is audit-only
    or corridor-oriented with distinct ROI; train uses scout side views).
  - Images saved via np.save with path ending .npy (np.save does not append).
  - Resume only when world ``_COMPLETE.json`` exists and expected samples exist.
  - Parallel workers via --workers.

World-seed isolated splits (default):
  train       96000–96999
  validation  97000–97199
  calibration 97200–97499
  locked_test 98000–98299
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

# Expected scout side-view count when all 4×2 reachable (8). Front audit separate.
EXPECTED_SIDE_VIEWS = 8
SCHEMA = "look-twice.v7-genesis-vision-dataset/v2"


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


def _save_npy(path: Path, arr: np.ndarray) -> Path:
    """Save array; path must end with .npy. Returns actual path written."""
    path = Path(path)
    if path.suffix != ".npy":
        path = path.with_suffix(".npy")
    path.parent.mkdir(parents=True, exist_ok=True)
    # np.save appends .npy only if suffix missing; we force .npy above.
    np.save(str(path), arr)
    if not path.is_file():
        # Defensive: some numpy versions if path given without checking
        alt = Path(str(path) + ".npy")
        if alt.is_file():
            return alt
        raise FileNotFoundError(f"np.save failed to create {path}")
    return path


def _crop_roi(
    rgb: np.ndarray,
    frac: tuple[float, float, float, float],
) -> np.ndarray:
    """Crop with (y0,y1,x0,x1) fractions."""
    arr = np.asarray(rgb)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    h, w = arr.shape[:2]
    y0, y1 = int(frac[0] * h), int(frac[1] * h)
    x0, x1 = int(frac[2] * w), int(frac[3] * w)
    y0, y1 = max(0, y0), min(h, max(y0 + 2, y1))
    x0, x1 = max(0, x0), min(w, max(x0 + 2, x1))
    return np.ascontiguousarray(arr[y0:y1, x0:x1])


def _corridor_roi_frac(corridor_id: str) -> tuple[float, float, float, float]:
    """Independent horizontal ROI bias per corridor (image-space).

    Corridor A is south (negative y in map); B is north. From carrier looking +x,
    map-y maps roughly to image vertical. Use distinct vertical bands so A/B
    front samples are not identical crops of one frame.
    """
    # (y0, y1, x0, x1) — y is image row.
    if corridor_id == "corridor_a":
        return (0.45, 0.90, 0.28, 0.72)  # lower band
    return (0.10, 0.55, 0.28, 0.72)  # upper band


def _side_roi_frac() -> tuple[float, float, float, float]:
    return (0.30, 0.75, 0.28, 0.72)


def _resize_96(rgb: np.ndarray) -> np.ndarray:
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


def _write_sample(
    *,
    out_dir: Path,
    split: str,
    seed: int,
    profile: str,
    corridor_id: str,
    viewpoint: str,
    agent_id: str,
    offline_label: str,
    small: np.ndarray,
    raw_rgb: np.ndarray,
    git_commit: str,
    phys: object,
    oracle_pose: object,
    roi_desc: str,
    train_eligible: bool,
) -> dict:
    safe_vp = viewpoint.replace("/", "_")
    sample_id = f"{split}__{seed}__{corridor_id}__{safe_vp}"
    rel = Path(split) / f"{sample_id}.npy"
    path = _save_npy(out_dir / rel, small)
    # Ensure image_path matches on-disk file relative to out_dir
    rel = path.relative_to(out_dir)
    meta = {
        "sample_id": sample_id,
        "schema_version": SCHEMA,
        "split": split,
        "seed": seed,
        "profile": profile,
        "corridor_id": corridor_id,
        "viewpoint": viewpoint,
        "agent_id": agent_id,
        "offline_label": offline_label,
        "image_path": str(rel).replace("\\", "/"),
        "image_sha256": _sha256_bytes(np.ascontiguousarray(small).tobytes()),
        "raw_rgb_sha256": _sha256_bytes(np.ascontiguousarray(raw_rgb).tobytes()),
        "git_commit": git_commit,
        "physical_obstacle_pose": phys,
        "oracle_obstacle_pose": oracle_pose,
        "world_alignment_passed": True,
        "roi": roi_desc,
        "resolution": [96, 96],
        "train_eligible": bool(train_eligible),
        "audit_only": not bool(train_eligible),
    }
    meta_path = out_dir / split / f"{sample_id}.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # Verify path exists and sha matches reload
    reloaded = np.load(out_dir / meta["image_path"])
    reload_sha = _sha256_bytes(np.ascontiguousarray(reloaded).tobytes())
    if reload_sha != meta["image_sha256"]:
        raise RuntimeError(f"sha mismatch after save: {sample_id}")
    return meta


def world_complete_path(out_dir: Path, split: str, seed: int) -> Path:
    return out_dir / split / f"_COMPLETE__{seed}.json"


def expected_train_viewpoints(public: dict) -> list[tuple[str, str, tuple[float, float], float]]:
    """Return list of (corridor_id, viewpoint_name, xy, coverage) for train-eligible side views."""
    out = []
    for vp in public.get("candidate_viewpoints") or []:
        if not vp.get("reachable", True):
            continue
        cid = str(vp.get("corridor_id") or "")
        if cid not in ("corridor_a", "corridor_b"):
            continue
        name = str(vp["name"])
        xy = (float(vp["xy"][0]), float(vp["xy"][1]))
        cov = float(vp.get("predicted_coverage") or 0.75)
        out.append((cid, name, xy, cov))
    return out


def collect_world(
    *,
    seed: int,
    profile: str,
    split: str,
    out_dir: Path,
    device: str,
    git_commit: str,
    include_front_audit: bool = True,
) -> dict:
    from v6_scenario import CARRIER_ID, SCOUT_ID, sample_v6_scenario

    scenario = sample_v6_scenario(profile, seed)
    from v6_genesis_runtime import V6GenesisRuntime

    runtime = V6GenesisRuntime(scenario, motion_backend="kinematic", device=device)
    samples_meta: list[dict] = []
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
                "complete": False,
            }

        oracle = scenario.oracle_context
        public = scenario.public_context
        labels = {
            "corridor_a": "blocked" if oracle["corridor_a_blocked_initial"] else "clear",
            "corridor_b": "blocked" if oracle["corridor_b_blocked_initial"] else "clear",
        }
        phys = audit.get("physical_obstacle_pose")
        oracle_pose = audit.get("oracle_obstacle_pose")

        # --- Train-eligible: scout side views only (one viewpoint → one label) ---
        side_plan = expected_train_viewpoints(public)
        seen_raw_sha: dict[str, str] = {}  # raw_sha -> offline_label
        seen_img_sha: dict[str, str] = {}
        last_pose: tuple[float, float] | None = None
        move_fail = 0
        dup_skip = 0
        for cid, name, xy, cov in side_plan:
            res = runtime.move_agent_to(
                SCOUT_ID, xy, allow_without_admit=True, admitted=False
            )
            pose = runtime.pose_of(SCOUT_ID)
            if not res.reached:
                move_fail += 1
                continue
            if last_pose is not None:
                dist = float(np.hypot(pose.x - last_pose[0], pose.y - last_pose[1]))
                # Must have actually relocated between distinct viewpoints.
                if dist < 0.08:
                    move_fail += 1
                    continue
            last_pose = (float(pose.x), float(pose.y))
            raw = runtime.capture_raw(
                agent_id=SCOUT_ID,
                viewpoint=name,
                viewpoint_xy=xy,
                predicted_coverage=cov,
            )
            rgb = np.asarray(raw.rgb)
            # Reject near-blank frames (common when camera/pose desync).
            if float(np.asarray(rgb, dtype=np.float32).std()) < 1e-3:
                dup_skip += 1
                continue
            frac = _side_roi_frac()
            crop = _crop_roi(rgb, frac)
            small = _resize_96(crop)
            if float(small.std()) < 1e-3:
                dup_skip += 1
                continue
            raw_sha = _sha256_bytes(np.ascontiguousarray(rgb).tobytes())
            img_sha = _sha256_bytes(np.ascontiguousarray(small).tobytes())
            lab = labels[cid]
            # Hard reject: same pixels already labeled differently (corruption).
            if raw_sha in seen_raw_sha and seen_raw_sha[raw_sha] != lab:
                dup_skip += 1
                continue
            if img_sha in seen_img_sha and seen_img_sha[img_sha] != lab:
                dup_skip += 1
                continue
            # Same pixels same label: still skip second copy (no duplicate training).
            if raw_sha in seen_raw_sha or img_sha in seen_img_sha:
                dup_skip += 1
                continue
            seen_raw_sha[raw_sha] = lab
            seen_img_sha[img_sha] = lab
            meta = _write_sample(
                out_dir=out_dir,
                split=split,
                seed=seed,
                profile=profile,
                corridor_id=cid,
                viewpoint=name,
                agent_id=SCOUT_ID,
                offline_label=lab,
                small=small,
                raw_rgb=rgb,
                git_commit=git_commit,
                phys=phys,
                oracle_pose=oracle_pose,
                roi_desc=f"side_y{frac[0]}-{frac[1]}_x{frac[2]}-{frac[3]}",
                train_eligible=True,
            )
            meta["capture_pose_xy"] = [float(pose.x), float(pose.y)]
            meta["target_xy"] = [float(xy[0]), float(xy[1])]
            # rewrite meta with pose fields
            (out_dir / split / f"{meta['sample_id']}.json").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )
            samples_meta.append(meta)

        # --- Audit-only carrier front: independent pose + independent ROI per corridor ---
        if include_front_audit:
            for cid, y_off in (("corridor_a", -0.30), ("corridor_b", 0.30)):
                front_xy = (-0.5, y_off)
                res = runtime.move_agent_to(
                    CARRIER_ID, front_xy, allow_without_admit=True, admitted=False
                )
                if not res.reached:
                    continue
                pose = runtime.pose_of(CARRIER_ID)
                raw = runtime.capture_raw(
                    agent_id=CARRIER_ID,
                    viewpoint=f"carrier_front_{cid}",
                    viewpoint_xy=front_xy,
                    predicted_coverage=0.55,
                )
                rgb = np.asarray(raw.rgb)
                frac = _corridor_roi_frac(cid)
                crop = _crop_roi(rgb, frac)
                small = _resize_96(crop)
                # Front is audit-only; still avoid writing conflict sha into dataset.
                img_sha = _sha256_bytes(np.ascontiguousarray(small).tobytes())
                lab = labels[cid]
                if img_sha in seen_img_sha and seen_img_sha[img_sha] != lab:
                    continue
                meta = _write_sample(
                    out_dir=out_dir,
                    split=split,
                    seed=seed,
                    profile=profile,
                    corridor_id=cid,
                    viewpoint=f"carrier_front_{cid}",
                    agent_id=CARRIER_ID,
                    offline_label=lab,
                    small=small,
                    raw_rgb=rgb,
                    git_commit=git_commit,
                    phys=phys,
                    oracle_pose=oracle_pose,
                    roi_desc=f"front_{cid}_y{frac[0]}-{frac[1]}_x{frac[2]}-{frac[3]}",
                    train_eligible=False,
                )
                meta["capture_pose_xy"] = [float(pose.x), float(pose.y)]
                (out_dir / split / f"{meta['sample_id']}.json").write_text(
                    json.dumps(meta, indent=2) + "\n", encoding="utf-8"
                )
                samples_meta.append(meta)

        train_n = sum(1 for m in samples_meta if m.get("train_eligible"))
        # Complete only if enough unique train samples and both labels present when world has both.
        need = max(4, min(EXPECTED_SIDE_VIEWS, len(side_plan)))
        complete = train_n >= need and move_fail < len(side_plan)
        if labels["corridor_a"] != labels["corridor_b"]:
            # Mixed world: need at least one clear and one blocked train sample.
            tr_clear = sum(
                1
                for m in samples_meta
                if m.get("train_eligible") and m["offline_label"] == "clear"
            )
            tr_blk = sum(
                1
                for m in samples_meta
                if m.get("train_eligible") and m["offline_label"] == "blocked"
            )
            if tr_clear < 1 or tr_blk < 1:
                complete = False

        result = {
            "seed": seed,
            "split": split,
            "skipped": False,
            "n_samples": len(samples_meta),
            "n_train_eligible": train_n,
            "n_side_planned": len(side_plan),
            "move_fail": move_fail,
            "dup_skip": dup_skip,
            "label_counts": {
                "clear": sum(1 for m in samples_meta if m["offline_label"] == "clear"),
                "blocked": sum(1 for m in samples_meta if m["offline_label"] == "blocked"),
            },
            "train_label_counts": {
                "clear": sum(
                    1
                    for m in samples_meta
                    if m.get("train_eligible") and m["offline_label"] == "clear"
                ),
                "blocked": sum(
                    1
                    for m in samples_meta
                    if m.get("train_eligible") and m["offline_label"] == "blocked"
                ),
            },
            "world_alignment_passed": True,
            "complete": complete,
            "schema_version": SCHEMA,
        }
        if complete:
            world_complete_path(out_dir, split, seed).write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
        else:
            # Do not leave partial worlds that resume/audit would mis-count.
            _purge_seed_samples(out_dir, split, seed)
        return result
    finally:
        runtime.close()


def _purge_seed_samples(out_dir: Path, split: str, seed: int) -> int:
    """Remove all sample artifacts for a seed (incomplete/conflict cleanup)."""
    n = 0
    d = out_dir / split
    if not d.is_dir():
        return 0
    for p in list(d.glob(f"{split}__{seed}__*")):
        p.unlink(missing_ok=True)
        n += 1
    world_complete_path(out_dir, split, seed).unlink(missing_ok=True)
    return n


def _run_one_world(
    *,
    python: str,
    out_dir: Path,
    device: str,
    profile: str,
    split: str,
    seed: int,
) -> dict:
    complete = world_complete_path(out_dir, split, seed)
    if complete.is_file():
        try:
            return {**json.loads(complete.read_text(encoding="utf-8")), "resumed": True}
        except json.JSONDecodeError:
            pass
    cmd = [
        python,
        str(Path(__file__).resolve()),
        "--out-dir",
        str(out_dir),
        "--device",
        device,
        "--profile",
        profile,
        "--worker-seed",
        str(seed),
        "--worker-split",
        split,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("PYOPENGL_PLATFORM", "egl")
    log = out_dir / split / f"_world_{seed}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
        )
    text = log.read_text(encoding="utf-8", errors="replace")
    line = ""
    for ln in reversed(text.splitlines()):
        if ln.strip().startswith("{"):
            line = ln.strip()
            break
    if not line:
        return {
            "seed": seed,
            "split": split,
            "skipped": True,
            "reason": f"no_json_rc={proc.returncode}",
            "complete": False,
        }
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {
            "seed": seed,
            "split": split,
            "skipped": True,
            "reason": "bad_json",
            "complete": False,
        }


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
    parser.add_argument("--workers", type=int, default=1, help="parallel world processes")
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
        return 0 if result.get("complete") else 1

    summary = {
        "schema_version": SCHEMA,
        "git_commit": git_commit,
        "profile": args.profile,
        "device": args.device,
        "workers": args.workers,
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
        n_train = 0

        def _job(seed: int) -> tuple[int, dict]:
            r = _run_one_world(
                python=args.python,
                out_dir=args.out_dir,
                device=args.device,
                profile=args.profile,
                split=split,
                seed=seed,
            )
            return seed, r

        workers = max(1, int(args.workers))
        if workers == 1:
            results = [_job(s) for s in seeds]
        else:
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(_job, s) for s in seeds]
                for fut in concurrent.futures.as_completed(futs):
                    results.append(fut.result())
            results.sort(key=lambda t: t[0])

        for seed, result in results:
            stem = f"{split}__{seed}"
            if result.get("resumed"):
                ok += 1
                n_samples += int(result.get("n_samples") or 0)
                n_train += int(result.get("n_train_eligible") or 0)
                print(f"RESUME {stem} n={result.get('n_samples')}", flush=True)
            elif result.get("skipped") or not result.get("complete"):
                skipped += 1
                print(
                    f"FAIL {stem} reason={result.get('reason')} complete={result.get('complete')}",
                    flush=True,
                )
            else:
                ok += 1
                n_samples += int(result.get("n_samples") or 0)
                n_train += int(result.get("n_train_eligible") or 0)
                print(
                    f"OK {stem} n={result.get('n_samples')} train={result.get('n_train_eligible')} "
                    f"labels={result.get('train_label_counts')}",
                    flush=True,
                )
        summary["splits"][split] = {
            "seed_range": [lo, hi],
            "worlds_requested": len(seeds),
            "worlds_ok": ok,
            "worlds_failed": skipped,
            "n_samples": n_samples,
            "n_train_eligible": n_train,
        }

    # Manifest: train-eligible sample json only for training checksum.
    train_paths = []
    all_paths = []
    for p in sorted(args.out_dir.rglob("*.json")):
        if p.name.startswith("_"):
            continue
        if p.name.count("__") < 2:
            continue
        rel = str(p.relative_to(args.out_dir))
        all_paths.append(rel)
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
            if meta.get("train_eligible"):
                train_paths.append(rel)
        except json.JSONDecodeError:
            pass
    (args.out_dir / "manifest_all_paths.txt").write_text(
        "\n".join(all_paths) + "\n", encoding="utf-8"
    )
    (args.out_dir / "manifest_train_eligible_paths.txt").write_text(
        "\n".join(train_paths) + "\n", encoding="utf-8"
    )
    summary["manifest_all_sha256"] = _sha256_bytes(
        ("\n".join(all_paths) + "\n").encode("utf-8")
    )
    summary["manifest_train_sha256"] = _sha256_bytes(
        ("\n".join(train_paths) + "\n").encode("utf-8")
    )
    summary["n_manifest_all"] = len(all_paths)
    summary["n_manifest_train_eligible"] = len(train_paths)
    (args.out_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
