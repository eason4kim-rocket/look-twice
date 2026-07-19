#!/usr/bin/env python3
"""Finalize V8 spatial dataset: audit + immutable manifests + provenance.

Do not train until passed=true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_WORLDS = {
    "train": 1500,
    "validation": 300,
    "calibration": 300,
    "locked_test": 400,
    "ood_test": 200,
}


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    root = args.data_dir
    out = args.out_dir or root
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    complete_by: dict[str, int] = {}
    for split, need in EXPECTED_WORLDS.items():
        n = len(list((root / split).glob("_COMPLETE__*.json"))) if (root / split).is_dir() else 0
        complete_by[split] = n
        if n != need:
            errors.append(f"{split}: complete {n} != {need}")

    # Run full audit
    audit_cmd = [
        args.python,
        str(ROOT / "scripts" / "v8_audit_spatial_dataset.py"),
        "--data-dir",
        str(root),
        "--out-dir",
        str(out),
        "--expect-worlds",
        str(sum(EXPECTED_WORLDS.values())),
    ]
    proc = subprocess.run(audit_cmd, cwd=str(ROOT), capture_output=True, text=True)
    audit_path = out / "audit_report.json"
    audit = {}
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit.get("passed"):
        errors.append("audit_report.passed is false")
        if proc.returncode != 0:
            errors.append(f"audit rc={proc.returncode} stderr={proc.stderr[-500:]}")

    # Manifests
    all_meta_paths: list[str] = []
    train_eligible_paths: list[str] = []
    train_image_lines: list[str] = []
    commits: Counter = Counter()
    labels_by_split: dict[str, Counter] = defaultdict(Counter)

    for split in EXPECTED_WORLDS:
        sdir = root / split
        if not sdir.is_dir():
            continue
        for mp in sorted(sdir.rglob("*__meta.json")):
            rel = str(mp.relative_to(root))
            all_meta_paths.append(rel)
            meta = json.loads(mp.read_text(encoding="utf-8"))
            commits[str(meta.get("git_commit") or "unknown")] += 1
            lab = meta.get("offline_label")
            if lab in ("clear", "blocked"):
                labels_by_split[split][lab] += 1
            if meta.get("train_eligible", True) and lab in ("clear", "blocked"):
                train_eligible_paths.append(rel)
                img = meta.get("image_path") or (meta.get("paths") or {}).get("rgb")
                if img:
                    fp = root / img
                    if fp.is_file():
                        train_image_lines.append(f"{_sha_file(fp)}  {img}")

    all_meta_paths.sort()
    train_eligible_paths.sort()
    train_image_lines.sort()

    man_all = out / "manifest_all_paths.txt"
    man_train = out / "manifest_train_eligible_paths.txt"
    man_img = out / "manifest_train_image_sha256.txt"
    man_all.write_text("\n".join(all_meta_paths) + "\n", encoding="utf-8")
    man_train.write_text("\n".join(train_eligible_paths) + "\n", encoding="utf-8")
    man_img.write_text("\n".join(train_image_lines) + "\n", encoding="utf-8")

    dataset_sha = {
        "manifest_all_sha256": _sha_file(man_all),
        "manifest_train_paths_sha256": _sha_file(man_train),
        "manifest_train_image_sha256": _sha_file(man_img),
        "n_all_meta": len(all_meta_paths),
        "n_train_eligible_meta": len(train_eligible_paths),
        "n_train_image_sha_lines": len(train_image_lines),
    }
    (out / "dataset_sha256.json").write_text(
        json.dumps(dataset_sha, indent=2) + "\n", encoding="utf-8"
    )

    if "unknown" in commits and commits["unknown"] > 0:
        errors.append(f"unknown git_commit on {commits['unknown']} samples")

    failed = list((root / "failed").rglob("*.json")) if (root / "failed").is_dir() else []
    if failed:
        errors.append(f"failed worlds present: {len(failed)}")

    report = {
        "schema_version": "look-twice.v8-spatial-finalize/v1",
        "passed": len(errors) == 0 and bool(audit.get("passed")),
        "complete_by_split": complete_by,
        "expected_worlds": EXPECTED_WORLDS,
        "labels_by_split": {k: dict(v) for k, v in labels_by_split.items()},
        "commits": dict(commits),
        "dataset_sha256": dataset_sha,
        "audit_passed": bool(audit.get("passed")),
        "n_failed_world_files": len(failed),
        "errors": errors,
        "train_allowed": False,
    }
    report["train_allowed"] = bool(report["passed"])
    (out / "finalize_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
