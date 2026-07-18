#!/usr/bin/env python3
"""Audit V7 Genesis vision dataset integrity (pre-train gate).

Fails if:
  - same image_sha256 maps to conflicting offline labels
  - image_path missing / unreadable / sha mismatch
  - split seed ranges overlap
  - world incomplete (no _COMPLETE for claimed world)
  - train_eligible samples include dual-use of identical front RGB for A/B
  - world_alignment_passed is false on any sample
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SPLITS = {
    "train": (96000, 96999),
    "validation": (97000, 97199),
    "calibration": (97200, 97499),
    "locked_test": (98000, 98299),
}


def _sha(arr: np.ndarray) -> str:
    import hashlib

    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def _purge_conflict_and_orphan(root: Path) -> dict:
    """Remove incomplete-world orphans and any SHA with conflicting labels."""
    by_sha: dict[str, list[Path]] = defaultdict(list)
    metas: list[tuple[Path, dict]] = []
    for jp in root.rglob("*.json"):
        if jp.name.startswith("_") or jp.name.count("__") < 2:
            continue
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        metas.append((jp, meta))
        by_sha[str(meta.get("image_sha256") or "")].append(jp)

    removed = 0
    # Conflict SHAs
    bad_sha = set()
    for sha, paths in by_sha.items():
        if not sha:
            continue
        labels = set()
        for p in paths:
            try:
                labels.add(json.loads(p.read_text(encoding="utf-8")).get("offline_label"))
            except Exception:
                pass
        if len(labels) > 1:
            bad_sha.add(sha)
    for sha in bad_sha:
        for jp in by_sha[sha]:
            meta = json.loads(jp.read_text(encoding="utf-8"))
            img = root / meta.get("image_path", "")
            if img.is_file():
                img.unlink(missing_ok=True)
            jp.unlink(missing_ok=True)
            removed += 1

    # Orphans: samples for seed without COMPLETE
    for jp, meta in list(metas):
        if not jp.is_file():
            continue
        split = str(meta.get("split") or "")
        seed = int(meta.get("seed") or -1)
        if not (root / split / f"_COMPLETE__{seed}.json").is_file():
            img = root / meta.get("image_path", "")
            if img.is_file():
                img.unlink(missing_ok=True)
            jp.unlink(missing_ok=True)
            removed += 1
    return {"removed_files": removed, "conflict_shas": len(bad_sha)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--train-eligible-only", action="store_true")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove conflict-SHA samples and incomplete-world orphans, then re-audit",
    )
    args = parser.parse_args()
    root = args.data_dir

    fix_report = None
    if args.fix:
        fix_report = _purge_conflict_and_orphan(root)

    errors: list[str] = []
    warnings: list[str] = []
    samples: list[dict] = []
    by_sha: dict[str, list[dict]] = defaultdict(list)
    seeds_by_split: dict[str, set[int]] = defaultdict(set)

    for jp in sorted(root.rglob("*.json")):
        if jp.name.startswith("_COMPLETE"):
            continue
        if jp.name.startswith("_world") or jp.name.startswith("dataset"):
            continue
        if jp.name.count("__") < 2:
            continue
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"bad json {jp}: {e}")
            continue
        if args.train_eligible_only and not meta.get("train_eligible", True):
            continue
        samples.append(meta)
        split = str(meta.get("split") or "")
        seed = int(meta.get("seed") or -1)
        seeds_by_split[split].add(seed)
        sha = str(meta.get("image_sha256") or "")
        by_sha[sha].append(meta)

        if not meta.get("world_alignment_passed", False):
            errors.append(f"alignment false: {meta.get('sample_id')}")

        img_rel = meta.get("image_path")
        if not img_rel:
            errors.append(f"missing image_path: {meta.get('sample_id')}")
            continue
        img_path = root / img_rel
        if not img_path.is_file():
            errors.append(f"missing file {img_path} for {meta.get('sample_id')}")
            continue
        if not str(img_rel).endswith(".npy"):
            errors.append(f"image_path not .npy: {img_rel}")
        try:
            arr = np.load(img_path)
            got = _sha(arr)
            if sha and got != sha:
                errors.append(
                    f"sha mismatch {meta.get('sample_id')}: meta={sha[:12]} disk={got[:12]}"
                )
        except Exception as e:
            errors.append(f"unreadable {img_path}: {e}")

    # Conflicting labels on same pixels
    conflict_pairs = 0
    for sha, group in by_sha.items():
        if not sha:
            errors.append("empty image_sha256 present")
            continue
        labels = {g.get("offline_label") for g in group}
        if len(labels) > 1:
            conflict_pairs += 1
            errors.append(
                f"conflict sha={sha[:16]} labels={sorted(labels)} "
                f"ids={[g.get('sample_id') for g in group[:4]]}"
            )

    # Split seed overlap
    splits = list(seeds_by_split.keys())
    for i, a in enumerate(splits):
        for b in splits[i + 1 :]:
            inter = seeds_by_split[a] & seeds_by_split[b]
            if inter:
                errors.append(f"seed overlap {a}∩{b}: {sorted(inter)[:10]}")

    # Range check vs defaults
    for split, seeds in seeds_by_split.items():
        if split in DEFAULT_SPLITS:
            lo, hi = DEFAULT_SPLITS[split]
            bad = [s for s in seeds if s < lo or s > hi]
            if bad:
                errors.append(f"seeds outside range for {split}: {bad[:5]}")

    # COMPLETE markers for each seed seen
    incomplete_worlds = 0
    for split, seeds in seeds_by_split.items():
        for seed in seeds:
            comp = root / split / f"_COMPLETE__{seed}.json"
            if not comp.is_file():
                incomplete_worlds += 1
                errors.append(f"missing _COMPLETE__{seed}.json in {split}")

    # Train eligible: no carrier_front dual issues (should be side views only ideally)
    train_samples = [s for s in samples if s.get("train_eligible", True)]
    front_train = [s for s in train_samples if "front" in str(s.get("viewpoint") or "")]
    if front_train:
        warnings.append(
            f"{len(front_train)} train_eligible front samples (prefer scout-only train)"
        )

    # Label balance on train-eligible
    n_clear = sum(1 for s in train_samples if s.get("offline_label") == "clear")
    n_blocked = sum(1 for s in train_samples if s.get("offline_label") == "blocked")
    n_train = len(train_samples)
    frac_c = n_clear / max(1, n_train)
    frac_b = n_blocked / max(1, n_train)

    # Simple pixel discriminability: mean luma blocked vs clear on train
    luma_c, luma_b = [], []
    for s in train_samples[:500]:
        try:
            arr = np.load(root / s["image_path"]).astype(np.float32)
            if arr.max() > 1.5:
                arr = arr / 255.0
            m = float(arr.mean())
            if s["offline_label"] == "clear":
                luma_c.append(m)
            else:
                luma_b.append(m)
        except Exception:
            pass
    mean_c = float(np.mean(luma_c)) if luma_c else None
    mean_b = float(np.mean(luma_b)) if luma_b else None
    sep = abs(mean_c - mean_b) if mean_c is not None and mean_b is not None else None

    report = {
        "schema_version": "look-twice.v7-vision-dataset-audit/v1",
        "data_dir": str(root),
        "n_samples": len(samples),
        "n_train_eligible": n_train,
        "n_unique_sha": len([s for s in by_sha if s]),
        "label_counts_train": {"clear": n_clear, "blocked": n_blocked},
        "frac_clear": frac_c,
        "frac_blocked": frac_b,
        "mean_luma_clear": mean_c,
        "mean_luma_blocked": mean_b,
        "mean_luma_separation": sep,
        "conflict_sha_groups": conflict_pairs,
        "incomplete_worlds": incomplete_worlds,
        "n_errors": len(errors),
        "n_warnings": len(warnings),
        "errors": errors[:50],
        "warnings": warnings[:20],
        "fix_report": fix_report,
        "passed": len(errors) == 0 and conflict_pairs == 0 and incomplete_worlds == 0,
        "discriminable_hint": bool(sep is not None and sep > 0.01),
        "balance_ok": bool(frac_c >= 0.2 and frac_b >= 0.2 and n_train >= 20),
    }
    out = root / "audit_report.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
