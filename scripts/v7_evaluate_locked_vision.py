#!/usr/bin/env python3
"""One-shot frozen locked-test evaluator for Genesis corridor vision.

Hard rules:
  - Load existing best.pt + conformal_artifact.json only
  - Never recompute conformal thresholds
  - Read only the locked_test split (when --split locked_test)
  - Atomic LOCKED_TEST_OPENED.json before any locked sample load
  - No --force, no retune knobs
  - Single output report; refuse if output dir already opened

Use --split validation (or a fixture dir) to exercise the code path without
opening locked_test. Opening locked_test requires split=locked_test and creates
the open seal.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from v7_vision_model import (  # noqa: E402
    file_sha256,
    load_conformal_artifact,
    load_genesis_corridor_head,
)
from v7_train_genesis_vision_head import (  # type: ignore  # noqa: E402
    CorridorRGBDataset,
    balanced_accuracy,
)

# Frozen hard gates (pre-registered).
EXPECTED_N = 2283
EXPECTED_MODEL_SHA = "385aa7b78197909e548cd39907bb21c3059987a4465c1d366ab221968636bcc9"
EXPECTED_CONFORMAL_SHA = "44f564633b6e2a303dd796380d8c300f41f0abce60124ee7f36f48feec0e7333"
EXPECTED_DATASET_SHA = "abfa99c309e03a009256da5fb1e6265a71eaf5508a6d3160fe5c3c1c87cb270e"

GATES = {
    "n": EXPECTED_N,
    "balanced_accuracy_decisive_min": 0.85,
    "blocked_recall_min": 0.90,
    "false_clear_rate_max": 0.05,
    "coverage_min": 0.95,
    "frac_clear_min": 0.20,
    "frac_blocked_min": 0.20,
}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _env_versions(device: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pytorch": torch.__version__,
        "hip": getattr(torch.version, "hip", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "device": device,
    }
    if torch.cuda.is_available():
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception as e:  # pragma: no cover
            info["gpu_name_error"] = str(e)
    return info


def apply_frozen_sets(
    p_blocked: np.ndarray,
    *,
    include_blocked_if_p_blocked_ge: float,
    include_clear_if_p_blocked_le: float,
) -> list[str]:
    """Map probabilities with frozen thresholds (no recomputation)."""
    out: list[str] = []
    tb = float(include_blocked_if_p_blocked_ge)
    tc = float(include_clear_if_p_blocked_le)
    for p in p_blocked:
        include_b = float(p) >= tb
        include_c = float(p) <= tc
        if include_b and include_c:
            out.append("inconclusive")
        elif include_b:
            out.append("blocked")
        elif include_c:
            out.append("clear")
        else:
            out.append("inconclusive")
    return out


@torch.no_grad()
def collect_probs(model: Any, dataset: CorridorRGBDataset, device: str) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    ys: list[float] = []
    ps: list[float] = []
    for i in range(len(dataset)):
        x, y = dataset[i]
        logit = model(x.unsqueeze(0).to(device))
        if hasattr(logit, "ndim") and logit.ndim > 0:
            logit = logit.reshape(-1)[0]
        p_blocked = float(torch.sigmoid(logit).item())
        ys.append(float(y.item()))
        ps.append(p_blocked)
    return np.asarray(ys, dtype=np.float64), np.asarray(ps, dtype=np.float64)


def metrics_from_sets(y: np.ndarray, pred: list[str]) -> dict[str, Any]:
    y_pred = np.array(
        [1 if p == "blocked" else 0 if p == "clear" else -1 for p in pred],
        dtype=np.int32,
    )
    decisive = y_pred >= 0
    true_b = y >= 0.5
    true_c = ~true_b
    if decisive.any():
        ba = float(balanced_accuracy(y[decisive], y_pred[decisive].astype(np.float32)))
        # false clear among ALL true blocked (not only decisive), matching cal script
        false_clear = float(((y_pred == 0) & true_b).sum() / max(1, int(true_b.sum())))
        blocked_recall = float(((y_pred == 1) & true_b).sum() / max(1, int(true_b.sum())))
    else:
        ba = 0.0
        false_clear = 1.0
        blocked_recall = 0.0

    # Confusion on decisive only
    tp = int(((y_pred == 1) & true_b & decisive).sum())
    fn = int(((y_pred == 0) & true_b & decisive).sum())
    fp = int(((y_pred == 1) & true_c & decisive).sum())
    tn = int(((y_pred == 0) & true_c & decisive).sum())
    # Abstention (inconclusive) breakdown
    abst_b = int(((y_pred < 0) & true_b).sum())
    abst_c = int(((y_pred < 0) & true_c).sum())

    counts = {
        "clear": pred.count("clear"),
        "blocked": pred.count("blocked"),
        "inconclusive": pred.count("inconclusive"),
    }
    n = len(pred)
    covered = 0
    for yi, pi in zip(y, pred):
        if pi == "inconclusive":
            covered += 1
        elif pi == "blocked" and yi >= 0.5:
            covered += 1
        elif pi == "clear" and yi < 0.5:
            covered += 1

    return {
        "n": n,
        "balanced_accuracy_decisive": ba,
        "blocked_recall": blocked_recall,
        "false_clear_rate": false_clear,
        "coverage": covered / max(1, n),
        "label_hist": counts,
        "frac_clear": counts["clear"] / max(1, n),
        "frac_blocked": counts["blocked"] / max(1, n),
        "frac_inconclusive": counts["inconclusive"] / max(1, n),
        "confusion_decisive": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "abstention": {
            "n": counts["inconclusive"],
            "true_blocked": abst_b,
            "true_clear": abst_c,
        },
        "prediction_histogram": counts,
        "n_true_blocked": int(true_b.sum()),
        "n_true_clear": int(true_c.sum()),
        "n_decisive": int(decisive.sum()),
    }


def evaluate_gates(
    metrics: dict[str, Any],
    *,
    model_sha: str,
    conformal_sha: str,
    dataset_sha: str,
    thresholds_recomputed: bool,
    locked_test_runs: int,
    enforce_n: bool,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    if enforce_n:
        checks["n_exact"] = int(metrics["n"]) == EXPECTED_N
    else:
        checks["n_exact"] = True  # dry-run / validation path
        checks["n_exact_skipped"] = True  # type: ignore[assignment]
    checks["balanced_accuracy_decisive"] = (
        float(metrics["balanced_accuracy_decisive"]) >= GATES["balanced_accuracy_decisive_min"]
    )
    checks["blocked_recall"] = float(metrics["blocked_recall"]) >= GATES["blocked_recall_min"]
    checks["false_clear_rate"] = float(metrics["false_clear_rate"]) <= GATES["false_clear_rate_max"]
    checks["coverage"] = float(metrics["coverage"]) >= GATES["coverage_min"]
    checks["frac_clear"] = float(metrics["frac_clear"]) >= GATES["frac_clear_min"]
    checks["frac_blocked"] = float(metrics["frac_blocked"]) >= GATES["frac_blocked_min"]
    checks["model_sha_match"] = model_sha == EXPECTED_MODEL_SHA
    checks["conformal_sha_match"] = conformal_sha == EXPECTED_CONFORMAL_SHA
    checks["dataset_sha_match"] = dataset_sha == EXPECTED_DATASET_SHA
    checks["thresholds_recomputed_false"] = thresholds_recomputed is False
    checks["locked_test_runs_one"] = locked_test_runs == 1
    # Drop marker keys from all()
    hard = {k: v for k, v in checks.items() if k != "n_exact_skipped"}
    if not enforce_n:
        hard.pop("n_exact", None)
        hard["n_exact"] = True
    return {
        "checks": checks,
        "passed": all(bool(v) for k, v in checks.items() if k != "n_exact_skipped"),
    }


def load_dataset_sha(data_dir: Path) -> str:
    path = data_dir / "dataset_sha256.json"
    if not path.is_file():
        raise FileNotFoundError(f"dataset_sha256.json missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    sha = payload.get("manifest_all_sha256")
    if not sha:
        raise ValueError(f"manifest_all_sha256 missing in {path}")
    return str(sha)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--conformal-artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--split",
        default="locked_test",
        choices=("locked_test", "validation", "calibration", "train"),
        help="Use validation/calibration for dry-run; locked_test is the formal open.",
    )
    parser.add_argument("--expected-runtime-commit", default="")
    parser.add_argument("--expected-dataset-sha", default=EXPECTED_DATASET_SHA)
    parser.add_argument(
        "--expected-model-sha",
        default=EXPECTED_MODEL_SHA,
        help=argparse.SUPPRESS,  # frozen; not a retune knob
    )
    parser.add_argument(
        "--expected-conformal-sha",
        default=EXPECTED_CONFORMAL_SHA,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    # No --force anywhere.
    out = args.output_dir
    seal = out / "LOCKED_TEST_OPENED.json"
    report_path = out / "locked_test_report.json"
    is_locked = args.split == "locked_test"

    if out.exists() and any(out.iterdir()):
        # Formal open is one-shot: refuse non-empty output directory.
        if is_locked or seal.is_file() or report_path.is_file():
            print(
                f"REFUSING: output directory already exists/non-empty: {out}",
                file=sys.stderr,
            )
            return 3

    out.mkdir(parents=True, exist_ok=True)

    # Verify artifact digests before any sample load.
    ckpt_sha = file_sha256(args.checkpoint)
    conf_sha = file_sha256(args.conformal_artifact)
    dataset_sha = load_dataset_sha(args.data_dir)

    if args.expected_model_sha and ckpt_sha != args.expected_model_sha:
        print(f"REFUSING: model SHA mismatch {ckpt_sha} != {args.expected_model_sha}", file=sys.stderr)
        return 4
    if args.expected_conformal_sha and conf_sha != args.expected_conformal_sha:
        print(
            f"REFUSING: conformal SHA mismatch {conf_sha} != {args.expected_conformal_sha}",
            file=sys.stderr,
        )
        return 4
    if args.expected_dataset_sha and dataset_sha != args.expected_dataset_sha:
        print(
            f"REFUSING: dataset SHA mismatch {dataset_sha} != {args.expected_dataset_sha}",
            file=sys.stderr,
        )
        return 4

    started = time.perf_counter()
    started_iso = datetime.now(timezone.utc).isoformat()

    if is_locked:
        # Atomic open seal BEFORE reading any locked sample.
        if seal.is_file():
            print(f"REFUSING: locked test already opened: {seal}", file=sys.stderr)
            return 3
        open_payload = {
            "schema_version": "look-twice.v7-locked-test-open/v1",
            "opened_at_utc": started_iso,
            "split": "locked_test",
            "runtime_commit": args.expected_runtime_commit or None,
            "checkpoint": str(args.checkpoint),
            "checkpoint_sha256": ckpt_sha,
            "conformal_artifact": str(args.conformal_artifact),
            "conformal_artifact_sha256": conf_sha,
            "dataset_dir": str(args.data_dir),
            "dataset_manifest_all_sha256": dataset_sha,
            "locked_test_runs": 1,
            "thresholds_recomputed": False,
            "note": "One-shot open. Second run is forbidden.",
        }
        _atomic_write_json(seal, open_payload)
        print(f"LOCKED_TEST_OPENED {seal}", flush=True)

    device = args.device
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        print("WARNING: cuda requested but unavailable; falling back to cpu", flush=True)
        device = "cpu"

    # Load frozen model + conformal (no threshold recomputation).
    model, loaded_ckpt_sha, ckpt_meta = load_genesis_corridor_head(
        args.checkpoint, device=device
    )
    assert loaded_ckpt_sha == ckpt_sha
    conformal = load_conformal_artifact(args.conformal_artifact)
    thr = {
        "include_blocked_if_p_blocked_ge": conformal.include_blocked_if_p_blocked_ge,
        "include_clear_if_p_blocked_le": conformal.include_clear_if_p_blocked_le,
        "coverage_target": conformal.coverage_target,
    }
    thresholds_recomputed = False

    # Only now load the split.
    dataset = CorridorRGBDataset(args.data_dir, args.split, augment=False)
    y, p_blocked = collect_probs(model, dataset, device)
    pred = apply_frozen_sets(
        p_blocked,
        include_blocked_if_p_blocked_ge=thr["include_blocked_if_p_blocked_ge"],
        include_clear_if_p_blocked_le=thr["include_clear_if_p_blocked_le"],
    )
    m = metrics_from_sets(y, pred)

    locked_test_runs = 1 if is_locked else 0
    gate = evaluate_gates(
        m,
        model_sha=ckpt_sha,
        conformal_sha=conf_sha,
        dataset_sha=dataset_sha,
        thresholds_recomputed=thresholds_recomputed,
        locked_test_runs=1 if is_locked else 1,  # path check uses 1; formal only when locked
        enforce_n=is_locked,
    )
    # For non-locked dry runs, locked_test_runs gate is not meaningful for pass.
    if not is_locked:
        gate["checks"]["locked_test_runs_one"] = True
        gate["passed"] = all(
            bool(v) for k, v in gate["checks"].items() if k not in ("n_exact_skipped",)
        ) and (
            # dry-run: still require SHA + quality if n allows, but n_exact may be skipped
            True
        )
        # Recompute passed without requiring exact n
        dry_checks = dict(gate["checks"])
        dry_checks["n_exact"] = True
        dry_checks["locked_test_runs_one"] = True
        gate["passed"] = all(
            bool(v) for k, v in dry_checks.items() if k != "n_exact_skipped"
        )
        gate["checks"] = dry_checks
        gate["dry_run"] = True

    elapsed = time.perf_counter() - started
    report: dict[str, Any] = {
        "schema_version": "look-twice.v7-locked-vision-report/v1",
        "passed": bool(gate["passed"]) if is_locked else bool(gate.get("passed")),
        "split": args.split,
        "is_formal_locked_run": is_locked,
        "thresholds_recomputed": thresholds_recomputed,
        "locked_test_runs": 1 if is_locked else 0,
        "runtime_commit": args.expected_runtime_commit or None,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": ckpt_sha,
        "conformal_artifact": str(args.conformal_artifact),
        "conformal_artifact_sha256": conf_sha,
        "dataset_dir": str(args.data_dir),
        "dataset_manifest_all_sha256": dataset_sha,
        "frozen_thresholds": thr,
        "checkpoint_meta": {
            "model": ckpt_meta.get("model"),
            "best_val_balanced_accuracy": ckpt_meta.get("best_val_balanced_accuracy"),
        },
        "environment": _env_versions(device),
        "timing": {
            "started_at_utc": started_iso,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
        },
        "metrics": m,
        "gates": GATES if is_locked else {**GATES, "n_enforced": False},
        "gate_checks": gate["checks"],
        "prediction_histogram": m["prediction_histogram"],
        "confusion_decisive": m["confusion_decisive"],
        "abstention": m["abstention"],
        "n_samples": m["n"],
        "note": (
            "Formal one-shot locked evaluation"
            if is_locked
            else "Dry-run path (not formal locked open)"
        ),
    }
    if is_locked:
        report["passed"] = bool(gate["passed"])

    # For dry-run, write a differently named report to avoid looking formal.
    if is_locked:
        _atomic_write_json(report_path, report)
        print(json.dumps({"passed": report["passed"], "n": m["n"], "path": str(report_path)}, indent=2))
    else:
        dry_path = out / f"{args.split}_dry_run_report.json"
        _atomic_write_json(dry_path, report)
        print(json.dumps({"dry_run": True, "passed": report["passed"], "n": m["n"], "path": str(dry_path)}, indent=2))

    if is_locked:
        return 0 if report["passed"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
