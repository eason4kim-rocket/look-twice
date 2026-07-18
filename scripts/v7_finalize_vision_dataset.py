#!/usr/bin/env python3
"""Post-collection gate for V7 Genesis vision dataset (do not train until pass).

Checks:
  1. Expected world completes (default 1800 = 1000+200+300+300)
  2. audit --fix passed
  3. clear/blocked balance per split (train-eligible)
  4. conflict SHA / path / image SHA / alignment / incomplete
  5. Immutable manifests + dataset SHA256
  6. Provenance: git commits seen on sample metadata

Does not start training.
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

EXPECTED = {
    "train": 1000,
    "validation": 200,
    "calibration": 300,
    "locked_test": 300,
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
    parser.add_argument("--out-dir", type=Path, default=None, help="report dir (default data-dir)")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-audit-subprocess", action="store_true")
    args = parser.parse_args()
    root = args.data_dir
    out = args.out_dir or root
    out.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    complete_by_split: dict[str, int] = {}
    for split, need in EXPECTED.items():
        n = len(list((root / split).glob("_COMPLETE__*.json"))) if (root / split).is_dir() else 0
        complete_by_split[split] = n
        if n != need:
            errors.append(f"{split}: complete worlds {n} != expected {need}")

    total_complete = sum(complete_by_split.values())
    if total_complete != sum(EXPECTED.values()):
        errors.append(f"total complete {total_complete} != 1800")

    # Run audit --fix
    audit_report = {}
    if not args.skip_audit_subprocess:
        cmd = [
            args.python,
            str(ROOT / "scripts" / "v7_audit_vision_dataset.py"),
            "--data-dir",
            str(root),
            "--train-eligible-only",
            "--fix",
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        audit_path = root / "audit_report.json"
        if audit_path.is_file():
            audit_report = json.loads(audit_path.read_text(encoding="utf-8"))
        if not audit_report.get("passed"):
            errors.append("audit_report.passed is false")
            if proc.returncode != 0:
                errors.append(f"audit rc={proc.returncode}")
    else:
        audit_path = root / "audit_report.json"
        if audit_path.is_file():
            audit_report = json.loads(audit_path.read_text(encoding="utf-8"))
            if not audit_report.get("passed"):
                errors.append("audit_report.passed is false")

    # Per-split clear/blocked on train_eligible
    split_labels: dict[str, Counter] = defaultdict(Counter)
    commits: Counter = Counter()
    train_paths: list[str] = []
    all_paths: list[str] = []
    for jp in sorted(root.rglob("*.json")):
        if jp.name.startswith("_") or jp.name.count("__") < 2:
            continue
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"bad json {jp}")
            continue
        rel = str(jp.relative_to(root))
        all_paths.append(rel)
        if meta.get("train_eligible") is False:
            continue
        split = str(meta.get("split") or "?")
        lab = str(meta.get("offline_label") or "?")
        split_labels[split][lab] += 1
        commits[str(meta.get("git_commit") or "unknown")] += 1
        train_paths.append(rel)
        if not meta.get("world_alignment_passed", False):
            errors.append(f"alignment false {meta.get('sample_id')}")

    for split in EXPECTED:
        c = split_labels.get(split, Counter())
        n = sum(c.values())
        if n == 0:
            errors.append(f"{split}: no train_eligible samples")
            continue
        fc = c.get("clear", 0) / n
        fb = c.get("blocked", 0) / n
        if fc < 0.20 or fb < 0.20:
            errors.append(f"{split}: imbalanced clear={fc:.3f} blocked={fb:.3f}")

    # Immutable manifests
    all_txt = "\n".join(all_paths) + "\n"
    train_txt = "\n".join(train_paths) + "\n"
    (out / "manifest_all_paths.txt").write_text(all_txt, encoding="utf-8")
    (out / "manifest_train_eligible_paths.txt").write_text(train_txt, encoding="utf-8")
    # Dataset content fingerprint: sorted train image sha256 from meta
    img_shas = []
    for rel in train_paths:
        meta = json.loads((root / rel).read_text(encoding="utf-8"))
        img_shas.append(f"{meta.get('image_sha256','')}\t{meta.get('image_path','')}")
    img_shas.sort()
    content_manifest = "\n".join(img_shas) + "\n"
    (out / "manifest_train_image_sha256.txt").write_text(content_manifest, encoding="utf-8")

    dataset_sha = {
        "manifest_all_sha256": _sha_text(all_txt),
        "manifest_train_paths_sha256": _sha_text(train_txt),
        "manifest_train_image_sha256": _sha_text(content_manifest),
        "n_all_meta": len(all_paths),
        "n_train_eligible_meta": len(train_paths),
    }
    (out / "dataset_sha256.json").write_text(
        json.dumps(dataset_sha, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "schema_version": "look-twice.v7-vision-dataset-finalize/v1",
        "data_dir": str(root),
        "expected_worlds": EXPECTED,
        "complete_by_split": complete_by_split,
        "total_complete": total_complete,
        "split_label_counts_train_eligible": {
            k: dict(v) for k, v in split_labels.items()
        },
        "collector_git_commits": dict(commits),
        "dataset_sha256": dataset_sha,
        "audit_passed": bool(audit_report.get("passed")),
        "audit_summary": {
            k: audit_report.get(k)
            for k in (
                "n_train_eligible",
                "conflict_sha_groups",
                "incomplete_worlds",
                "frac_clear",
                "frac_blocked",
                "discriminable_hint",
                "balance_ok",
            )
        },
        "errors": errors,
        "passed": len(errors) == 0,
        "next_steps": [
            "train on train split only",
            "select model on validation",
            "calibrate thresholds on calibration",
            "24-ep smoke on non-locked seeds",
            "freeze model+thresholds+SHA",
            "locked vision test once",
            "120 closed-loop matrix",
            "formal_result_eligible decision",
        ],
        "frozen_closed_loop_claim": "53% full-chain homology matrix remains freeze until vision upgrade",
    }
    (out / "finalize_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
