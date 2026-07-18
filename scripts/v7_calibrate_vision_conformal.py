#!/usr/bin/env python3
"""Class-conditional conformal calibration for Genesis corridor head.

Calibration split only. Produces thresholds such that prediction sets are:
  {clear}, {blocked}, or {clear,blocked}→runtime inconclusive.

Does not touch locked_test for tuning; optional --eval-locked reports only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from v7_vision_model import GenesisCorridorHead  # noqa: E402
from v7_train_genesis_vision_head import (  # type: ignore  # noqa: E402
    CorridorRGBDataset,
    balanced_accuracy,
)


@torch.no_grad()
def collect_probs(model, dataset, device: str) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    ys, ps = [], []
    for i in range(len(dataset)):
        x, y = dataset[i]
        logit = model(x.unsqueeze(0).to(device))
        p_blocked = float(torch.sigmoid(logit).item())
        ys.append(float(y.item()))
        ps.append(p_blocked)
    return np.asarray(ys), np.asarray(ps)


def conformal_thresholds(
    y: np.ndarray, p_blocked: np.ndarray, coverage: float = 0.95
) -> dict:
    """One-vs-rest scores: for blocked class use p_blocked; for clear use 1-p.

    Nonconformity = 1 - p_true_class. Threshold = quantile on calibration.
    """
    # Blocked samples
    b_mask = y >= 0.5
    c_mask = ~b_mask
    # nonconformity for true class
    nc_blocked = 1.0 - p_blocked[b_mask]
    nc_clear = p_blocked[c_mask]  # 1 - p_clear = p_blocked
    q_b = float(np.quantile(nc_blocked, coverage)) if b_mask.any() else 0.5
    q_c = float(np.quantile(nc_clear, coverage)) if c_mask.any() else 0.5
    # Include class if nonconformity <= q  ⇔  p_class >= 1-q
    t_blocked = 1.0 - q_b  # min p_blocked to include blocked
    t_clear = 1.0 - q_c  # min p_clear = 1-p_blocked to include clear
    # ⇔ p_blocked <= 1 - t_clear to include clear... include clear if p_clear >= t_clear
    # i.e. p_blocked <= 1 - t_clear
    return {
        "coverage_target": coverage,
        "q_blocked": q_b,
        "q_clear": q_c,
        "include_blocked_if_p_blocked_ge": t_blocked,
        "include_clear_if_p_clear_ge": t_clear,
        "include_clear_if_p_blocked_le": 1.0 - t_clear,
        "n_cal_blocked": int(b_mask.sum()),
        "n_cal_clear": int(c_mask.sum()),
    }


def apply_sets(p_blocked: np.ndarray, thr: dict) -> list[str]:
    out = []
    tb = thr["include_blocked_if_p_blocked_ge"]
    tc_le = thr["include_clear_if_p_blocked_le"]
    for p in p_blocked:
        include_b = p >= tb
        include_c = p <= tc_le
        if include_b and include_c:
            out.append("inconclusive")
        elif include_b:
            out.append("blocked")
        elif include_c:
            out.append("clear")
        else:
            out.append("inconclusive")
    return out


def metrics(y: np.ndarray, pred: list[str]) -> dict:
    y_pred = np.array([1 if p == "blocked" else 0 if p == "clear" else -1 for p in pred])
    decisive = y_pred >= 0
    if decisive.any():
        ba = balanced_accuracy(y[decisive], y_pred[decisive].astype(np.float32))
        # false clear among true blocked decisive
        true_b = y >= 0.5
        false_clear = float(
            ((y_pred == 0) & true_b).sum() / max(1, true_b.sum())
        )
        blocked_recall = float(
            ((y_pred == 1) & true_b).sum() / max(1, true_b.sum())
        )
    else:
        ba = 0.0
        false_clear = 1.0
        blocked_recall = 0.0
    counts = {
        "clear": pred.count("clear"),
        "blocked": pred.count("blocked"),
        "inconclusive": pred.count("inconclusive"),
    }
    n = len(pred)
    # coverage: true class in set — for decisive singleton true matches; for
    # inconclusive always covered.
    covered = 0
    for yi, pi in zip(y, pred):
        if pi == "inconclusive":
            covered += 1
        elif pi == "blocked" and yi >= 0.5:
            covered += 1
        elif pi == "clear" and yi < 0.5:
            covered += 1
    return {
        "balanced_accuracy_decisive": ba,
        "blocked_recall": blocked_recall,
        "false_clear_rate": false_clear,
        "coverage": covered / max(1, n),
        "label_hist": counts,
        "frac_clear": counts["clear"] / max(1, n),
        "frac_blocked": counts["blocked"] / max(1, n),
        "frac_inconclusive": counts["inconclusive"] / max(1, n),
        "n": n,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--coverage", type=float, default=0.95)
    parser.add_argument("--eval-locked", action="store_true")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    model = GenesisCorridorHead().to(device)
    payload = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model.load_state_dict(payload["state_dict"])
    model.eval()

    cal_ds = CorridorRGBDataset(args.data_dir, "calibration", augment=False)
    y_cal, p_cal = collect_probs(model, cal_ds, device)
    thr = conformal_thresholds(y_cal, p_cal, coverage=args.coverage)
    pred_cal = apply_sets(p_cal, thr)
    cal_metrics = metrics(y_cal, pred_cal)

    artifact = {
        "schema_version": "look-twice.v7-vision-conformal/v1",
        "checkpoint": str(args.checkpoint),
        "thresholds": thr,
        "calibration_metrics": cal_metrics,
        "runtime_rule": {
            "if_set_clear_blocked": "emit_inconclusive",
            "include_blocked_if_p_blocked_ge": thr["include_blocked_if_p_blocked_ge"],
            "include_clear_if_p_blocked_le": thr["include_clear_if_p_blocked_le"],
        },
    }

    if args.eval_locked:
        lock_ds = CorridorRGBDataset(args.data_dir, "locked_test", augment=False)
        y_l, p_l = collect_probs(model, lock_ds, device)
        pred_l = apply_sets(p_l, thr)
        artifact["locked_test_metrics"] = metrics(y_l, pred_l)
        # locked test is report-only

    path = args.out_dir / "conformal_artifact.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))

    m = cal_metrics
    ok = (
        m["balanced_accuracy_decisive"] >= 0.85
        and m["blocked_recall"] >= 0.90
        and m["false_clear_rate"] <= 0.05
        and m["coverage"] >= 0.95
        and m["frac_clear"] >= 0.20
        and m["frac_blocked"] >= 0.20
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
