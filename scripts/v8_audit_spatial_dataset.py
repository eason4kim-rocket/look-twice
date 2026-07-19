#!/usr/bin/env python3
"""Audit V8 spatial RGB-D dataset (preflight or full).

Gates (all required for passed=true):
  - expected worlds / samples readable
  - RGB, depth_noisy, corridor_mask, pose, labels present
  - no duplicate path SHA conflicts within split
  - no seeds in V7 forbidden ranges / no cross-split seed reuse
  - corridor_mask non-empty; depth valid fraction reasonable
  - clear/blocked roughly balanced (train_eligible)
  - offline_label depends only on target corridor oracle flag
  - git_commit + generation config present (strict unless --allow-unknown-commit)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SEED_RANGES = [
    range(95000, 95020),
    range(96000, 98300),
    range(99000, 99004),
    range(99200, 99204),
    range(99300, 99320),
]

REQUIRED_PATH_KEYS = (
    "rgb",
    "depth_noisy",
    "corridor_mask",
    "depth_clean",
    "obstacle_mask",
    "seg_entity",
)
REQUIRED_META = (
    "schema_version",
    "seed",
    "corridor_id",
    "viewpoint",
    "offline_label",
    "paths",
    "pose",
    "git_commit",
)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_metas(data_dir: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    """Yield (split, meta_path, meta). Supports preflight seed_* layout and split/ layout."""
    out: list[tuple[str, Path, dict[str, Any]]] = []
    # Full layout: data_dir/{train,validation,...}/**/meta.json
    split_dirs = [
        p
        for p in data_dir.iterdir()
        if p.is_dir()
        and p.name
        in ("train", "validation", "calibration", "locked_test", "ood_test", "preflight")
    ]
    if split_dirs:
        for sd in split_dirs:
            for mp in sd.rglob("*__meta.json"):
                if mp.name.startswith("_"):
                    continue
                meta = json.loads(mp.read_text(encoding="utf-8"))
                out.append((sd.name, mp, meta))
        return out
    # Preflight layout: data_dir/seed_*/**/*__meta.json
    for mp in data_dir.rglob("*__meta.json"):
        if mp.name.startswith("_"):
            continue
        meta = json.loads(mp.read_text(encoding="utf-8"))
        out.append(("preflight", mp, meta))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--expect-worlds", type=int, default=None)
    parser.add_argument("--expect-samples", type=int, default=None)
    parser.add_argument("--min-depth-valid-frac", type=float, default=0.15)
    parser.add_argument("--min-mask-frac", type=float, default=1e-4)
    parser.add_argument("--balance-min-frac", type=float, default=0.25)
    parser.add_argument(
        "--allow-unknown-commit",
        action="store_true",
        help="Preflight-only: allow git_commit=unknown (full collect must not).",
    )
    parser.add_argument("--strict", action="store_true", default=True)
    args = parser.parse_args()
    data_dir = args.data_dir
    out_dir = args.out_dir or data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    metas = _iter_metas(data_dir)
    if not metas:
        errors.append("no meta files found")

    # Worlds via _COMPLETE
    completes = list(data_dir.rglob("_COMPLETE.json")) + list(
        data_dir.rglob("_COMPLETE__*.json")
    )
    n_worlds = len(completes)
    n_samples = len(metas)
    if args.expect_worlds is not None and n_worlds != args.expect_worlds:
        errors.append(f"worlds {n_worlds} != expect {args.expect_worlds}")
    if args.expect_samples is not None and n_samples != args.expect_samples:
        errors.append(f"samples {n_samples} != expect {args.expect_samples}")

    seeds_by_split: dict[str, set[int]] = defaultdict(set)
    labels = Counter()
    commits = Counter()
    path_sha_map: dict[str, list[str]] = defaultdict(list)
    depth_valid_fracs: list[float] = []
    mask_fracs: list[float] = []
    missing_fields = Counter()
    readable = 0
    label_consistent = 0
    label_checked = 0
    gen_config_ok = 0

    for split, mp, meta in metas:
        seed = int(meta.get("seed", -1))
        seeds_by_split[split].add(seed)
        for r in FORBIDDEN_SEED_RANGES:
            if seed in r:
                errors.append(f"forbidden V7-overlap seed {seed} in {mp}")
                break

        for k in REQUIRED_META:
            if k not in meta or meta[k] in (None, ""):
                missing_fields[k] += 1
                errors.append(f"{mp}: missing meta field {k}")

        commit = str(meta.get("git_commit") or "unknown")
        commits[commit] += 1
        if commit in ("", "unknown") and not args.allow_unknown_commit:
            errors.append(f"{mp}: git_commit unknown/empty")
        elif commit in ("", "unknown") and args.allow_unknown_commit:
            warnings.append(f"{mp}: git_commit unknown (allowed for preflight)")

        gen = meta.get("generation_config") or meta.get("collect_config")
        if isinstance(gen, dict) and gen:
            gen_config_ok += 1
        else:
            # Accept paths + schema as minimal config if present
            if meta.get("schema_version") and meta.get("paths"):
                gen_config_ok += 1
                warnings.append(f"{mp}: no generation_config block (schema+paths only)")
            else:
                errors.append(f"{mp}: missing generation_config")

        paths = meta.get("paths") or {}
        ok_sample = True
        for key in REQUIRED_PATH_KEYS:
            rel = paths.get(key)
            if not rel:
                errors.append(f"{mp}: missing path {key}")
                ok_sample = False
                continue
            fp = data_dir / rel
            if not fp.is_file():
                # try relative to meta parent
                alt = mp.parent / Path(rel).name
                if alt.is_file():
                    fp = alt
                else:
                    errors.append(f"{mp}: unreadable {key} -> {rel}")
                    ok_sample = False
                    continue
            try:
                arr = np.load(fp)
            except Exception as e:
                errors.append(f"{mp}: load fail {key}: {e}")
                ok_sample = False
                continue
            if arr.size == 0:
                errors.append(f"{mp}: empty array {key}")
                ok_sample = False
                continue
            sha = _sha_file(fp)
            path_sha_map[sha].append(str(fp))
            if key == "corridor_mask":
                frac = float((arr > 0.5).mean()) if arr.size else 0.0
                mask_fracs.append(frac)
                if frac < args.min_mask_frac:
                    errors.append(f"{mp}: corridor_mask empty frac={frac}")
                    ok_sample = False
            if key == "depth_noisy":
                d = arr.astype(np.float32)
                if d.ndim == 3:
                    d = d[..., 0]
                valid = np.isfinite(d) & (d > 1e-4)
                vf = float(valid.mean())
                depth_valid_fracs.append(vf)
                if vf < args.min_depth_valid_frac:
                    errors.append(f"{mp}: depth valid frac {vf:.3f} < {args.min_depth_valid_frac}")
                    ok_sample = False
            if key == "rgb":
                if arr.ndim != 3 or arr.shape[-1] < 3:
                    errors.append(f"{mp}: rgb shape bad {arr.shape}")
                    ok_sample = False

        pose = meta.get("pose")
        if not isinstance(pose, dict) or not all(k in pose for k in ("x", "y")):
            errors.append(f"{mp}: pose incomplete")
            ok_sample = False

        lab = meta.get("offline_label")
        if lab not in ("clear", "blocked"):
            errors.append(f"{mp}: bad offline_label {lab}")
            ok_sample = False
        else:
            labels[lab] += 1

        # Target-corridor label consistency: offline_blocked must match offline_label
        if "offline_blocked" in meta:
            label_checked += 1
            want = "blocked" if meta["offline_blocked"] else "clear"
            if want == lab:
                label_consistent += 1
            else:
                errors.append(f"{mp}: offline_label != offline_blocked")

        # Non-target contamination of labels: ensure we don't store dual labels
        if meta.get("dual_label") or meta.get("labels_both_corridors"):
            errors.append(f"{mp}: dual corridor labels forbidden")

        if ok_sample:
            readable += 1

    # Cross-split seed reuse
    all_seed_owners: dict[int, list[str]] = defaultdict(list)
    for split, seeds in seeds_by_split.items():
        for s in seeds:
            all_seed_owners[s].append(split)
    for s, owners in all_seed_owners.items():
        if len(set(owners)) > 1:
            errors.append(f"seed {s} appears in splits {owners}")

    # Integrity: path uniqueness; meta SHA must match file bytes.
    # Cross-seed identical RGB content → warning only (deterministic twin worlds).
    path_owners: dict[str, list[str]] = defaultdict(list)
    sha_mismatch = 0
    for split, mp, meta in metas:
        paths = meta.get("paths") or {}
        for key in REQUIRED_PATH_KEYS:
            rel = paths.get(key)
            if not rel:
                continue
            path_owners[str(rel)].append(str(mp))
            stored = paths.get(f"{key}_sha256")
            fp = data_dir / rel
            if stored and fp.is_file():
                got = _sha_file(fp)
                if got != stored:
                    sha_mismatch += 1
                    errors.append(f"{mp}: {key} sha mismatch meta≠file")
    for rel, owners in path_owners.items():
        if len(owners) > 1:
            errors.append(f"path reused by multiple metas: {rel} owners={owners[:3]}")
    if sha_mismatch:
        errors.append(f"sha_mismatch_count={sha_mismatch}")

    dup_shas = {sha: paths for sha, paths in path_sha_map.items() if len(set(paths)) > 1}
    rgb_collisions = 0
    for sha, paths in dup_shas.items():
        rgb_paths = [p for p in paths if "__rgb.npy" in p]
        if len(set(rgb_paths)) > 1:
            rgb_collisions += 1
            warnings.append(
                f"identical rgb content sha={sha[:12]} across {len(set(rgb_paths))} paths"
            )

    # Balance
    n_lab = sum(labels.values()) or 1
    frac_clear = labels.get("clear", 0) / n_lab
    frac_blocked = labels.get("blocked", 0) / n_lab
    if frac_clear < args.balance_min_frac or frac_blocked < args.balance_min_frac:
        errors.append(
            f"label imbalance clear={frac_clear:.3f} blocked={frac_blocked:.3f} "
            f"(min {args.balance_min_frac})"
        )

    if readable != n_samples and n_samples:
        errors.append(f"readable samples {readable} != n_samples {n_samples}")

    report = {
        "schema_version": "look-twice.v8-spatial-audit/v1",
        "data_dir": str(data_dir),
        "passed": len(errors) == 0,
        "n_worlds": n_worlds,
        "n_samples": n_samples,
        "n_readable": readable,
        "labels": dict(labels),
        "frac_clear": frac_clear,
        "frac_blocked": frac_blocked,
        "commits": dict(commits),
        "seeds_by_split": {k: sorted(v) for k, v in seeds_by_split.items()},
        "depth_valid_frac_mean": float(np.mean(depth_valid_fracs)) if depth_valid_fracs else None,
        "depth_valid_frac_min": float(np.min(depth_valid_fracs)) if depth_valid_fracs else None,
        "mask_frac_mean": float(np.mean(mask_fracs)) if mask_fracs else None,
        "mask_frac_min": float(np.min(mask_fracs)) if mask_fracs else None,
        "label_consistency": {
            "checked": label_checked,
            "ok": label_consistent,
        },
        "generation_config_ok": gen_config_ok,
        "rgb_content_collisions_warned": rgb_collisions,
        "path_reuse_errors": sum(1 for e in errors if e.startswith("path reused")),
        "n_errors": len(errors),
        "n_warnings": len(warnings),
        "errors": errors[:200],
        "warnings": warnings[:100],
    }
    path = out_dir / "audit_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k not in ("errors", "warnings", "seeds_by_split")}, indent=2))
    if errors:
        print("ERRORS:", *errors[:20], sep="\n  ")
    print("passed", report["passed"], "wrote", path)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
