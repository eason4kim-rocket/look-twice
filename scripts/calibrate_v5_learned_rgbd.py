#!/usr/bin/env python3
"""Fit clustered conformal thresholds and evaluate frozen RGB-D splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd import MODEL_SCHEMA, load_checkpoint
from learned_rgbd_conformal import coverage_metrics, fit_clustered_thresholds


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def infer_manifest(
    *, model: Any, manifest: Path, dataset_root: Path, device: str
) -> list[dict[str, Any]]:
    import torch

    records = json.loads(manifest.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    model.eval()
    for start in range(0, len(records), 128):
        batch_records = records[start : start + 128]
        arrays: list[np.ndarray] = []
        for record in batch_records:
            sample = dataset_root / record["sample_path"]
            if sha256(sample) != record["sample_sha256"]:
                raise ValueError(f"sample hash mismatch: {sample}")
            with np.load(sample) as data:
                arrays.append(np.asarray(data["x"], dtype=np.float32))
        tensor = torch.from_numpy(np.stack(arrays)).to(device)
        with torch.no_grad():
            probabilities = torch.sigmoid(model(tensor).squeeze(1)).cpu().tolist()
        for record, probability in zip(batch_records, probabilities):
            rows.append(
                {
                    "seed": int(record["seed"]),
                    "profile": record["profile"],
                    "viewpoint": record["viewpoint"],
                    "label_blocked": int(record["label_blocked"]),
                    "p_blocked": float(probability),
                    "sample_sha256": record["sample_sha256"],
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--calibration-manifest", type=Path, required=True)
    parser.add_argument("--validation-manifest", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--artifact-output", type=Path, required=True)
    parser.add_argument("--evaluation-output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    model, checkpoint = load_checkpoint(args.model, device=args.device)
    if checkpoint.get("schema_version") != MODEL_SCHEMA:
        raise ValueError("checkpoint schema mismatch")
    calibration = infer_manifest(
        model=model,
        manifest=args.calibration_manifest,
        dataset_root=args.dataset_root,
        device=args.device,
    )
    validation = infer_manifest(
        model=model,
        manifest=args.validation_manifest,
        dataset_root=args.dataset_root,
        device=args.device,
    )
    test = infer_manifest(
        model=model,
        manifest=args.test_manifest,
        dataset_root=args.dataset_root,
        device=args.device,
    )
    thresholds = fit_clustered_thresholds(calibration, args.alpha)
    clear = thresholds["clear"]
    blocked = thresholds["blocked"]
    artifact = {
        "schema_version": "look-twice.learned-rgbd-conformal/v1",
        "alpha": args.alpha,
        "method": "class-conditional split conformal; per-seed worst-view cluster score",
        "thresholds": thresholds,
        "model_sha256": sha256(args.model),
        "calibration_manifest_sha256": sha256(args.calibration_manifest),
        "calibration_rows": len(calibration),
        "calibration_seed_range": [
            min(row["seed"] for row in calibration),
            max(row["seed"] for row in calibration),
        ],
    }
    evaluation = {
        "schema_version": "look-twice.learned-rgbd-conformal-evaluation/v1",
        "artifact": artifact,
        "validation": coverage_metrics(
            validation, clear_threshold=clear, blocked_threshold=blocked
        ),
        "locked_test": coverage_metrics(
            test, clear_threshold=clear, blocked_threshold=blocked
        ),
        "rows": {"calibration": calibration, "validation": validation, "test": test},
    }
    args.artifact_output.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    args.evaluation_output.parent.mkdir(parents=True, exist_ok=True)
    args.evaluation_output.write_text(json.dumps(evaluation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"thresholds": thresholds, "validation": evaluation["validation"], "locked_test": evaluation["locked_test"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
