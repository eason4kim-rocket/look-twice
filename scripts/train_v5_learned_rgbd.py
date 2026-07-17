#!/usr/bin/env python3
"""Train and evaluate the lightweight Look Twice RGB-D classifier on ROCm."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd import MODEL_SCHEMA, build_model


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"manifest must contain a non-empty list: {path}")
    return payload


def dataset_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def load_arrays(records: list[dict[str, Any]], root: Path) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    labels: list[int] = []
    for record in records:
        sample = root / record["sample_path"]
        if hashlib.sha256(sample.read_bytes()).hexdigest() != record["sample_sha256"]:
            raise ValueError(f"sample hash mismatch: {sample}")
        with np.load(sample) as data:
            features.append(np.asarray(data["x"], dtype=np.float32))
            labels.append(int(data["y"]))
    return np.stack(features), np.asarray(labels, dtype=np.float32)


def metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    predicted = probabilities >= 0.5
    truth = labels >= 0.5
    eps = 1e-7
    return {
        "n": float(len(labels)),
        "accuracy": float(np.mean(predicted == truth)),
        "balanced_accuracy": float(
            0.5 * (np.mean(predicted[truth]) + np.mean(~predicted[~truth]))
        ),
        "brier": float(np.mean((probabilities - labels) ** 2)),
        "log_loss": float(
            -np.mean(labels * np.log(probabilities + eps) + (1 - labels) * np.log(1 - probabilities + eps))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--train-manifest", type=Path, required=True)
    parser.add_argument("--validation-manifest", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1707)
    args = parser.parse_args()

    import torch

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    manifests = [args.train_manifest, args.validation_manifest, args.test_manifest]
    train_records, val_records, test_records = map(load_manifest, manifests)
    train_x, train_y = load_arrays(train_records, args.dataset_root)
    val_x, val_y = load_arrays(val_records, args.dataset_root)
    test_x, test_y = load_arrays(test_records, args.dataset_root)
    train_tensor = torch.from_numpy(train_x).to(args.device)
    train_labels = torch.from_numpy(train_y).to(args.device)
    val_tensor = torch.from_numpy(val_x).to(args.device)
    test_tensor = torch.from_numpy(test_x).to(args.device)

    model = build_model(torch).to(args.device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    best_state = None
    best_val = math.inf
    patience = 12
    stale = 0
    history: list[dict[str, float]] = []
    for epoch in range(args.epochs):
        model.train()
        permutation = torch.randperm(len(train_tensor), device=args.device)
        total = 0.0
        for start in range(0, len(train_tensor), args.batch_size):
            idx = permutation[start : start + args.batch_size]
            batch = train_tensor[idx].clone()
            # Deterministic-seed stochastic sensor augmentation, all on ROCm.
            brightness = 0.85 + 0.30 * torch.rand((len(idx), 1, 1, 1), device=args.device)
            batch[:, :3] = (batch[:, :3] * brightness + 0.025 * torch.randn_like(batch[:, :3])).clamp(0, 1)
            dropout = torch.rand_like(batch[:, 3]) < 0.04
            batch[:, 3][dropout] = 0.0
            batch[:, 4][dropout] = 0.0
            logits = model(batch).squeeze(1)
            loss = loss_fn(logits, train_labels[idx])
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total += float(loss.item()) * len(idx)
        model.eval()
        with torch.no_grad():
            val_logits = model(val_tensor).squeeze(1)
            val_loss = float(loss_fn(val_logits, torch.from_numpy(val_y).to(args.device)).item())
        history.append({"epoch": float(epoch), "train_loss": total / len(train_tensor), "validation_loss": val_loss})
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is None:
        raise RuntimeError("training did not produce a checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        val_p = torch.sigmoid(model(val_tensor).squeeze(1)).cpu().numpy()
        test_p = torch.sigmoid(model(test_tensor).squeeze(1)).cpu().numpy()
    report = {
        "schema_version": MODEL_SCHEMA,
        "device": args.device,
        "torch": torch.__version__,
        "rocm": torch.version.hip,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "seed": args.seed,
        "epochs_completed": len(history),
        "best_validation_loss": best_val,
        "dataset_sha256": dataset_sha256(manifests),
        "split_sizes": {"train": len(train_y), "validation": len(val_y), "test": len(test_y)},
        "validation": metrics(val_p, val_y),
        "test": metrics(test_p, test_y),
        "history": history,
    }
    checkpoint = {
        "schema_version": MODEL_SCHEMA,
        "state_dict": best_state,
        "training": {k: report[k] for k in ("device", "torch", "rocm", "gpu", "seed", "dataset_sha256", "split_sizes")},
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.model_output)
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("split_sizes", "validation", "test", "gpu", "epochs_completed")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
