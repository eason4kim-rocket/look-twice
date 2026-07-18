#!/usr/bin/env python3
"""Train Genesis RGB corridor head (no synthetic_rgb_for_label).

Expects dataset from v7_collect_genesis_vision_dataset.py:
  out_dir/{train,validation}/... .npy + .json with offline_label clear|blocked

Saves best.pt by validation balanced accuracy.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

ROOT = Path(__file__).resolve().parents[1]


class CorridorRGBDataset(Dataset):
    def __init__(self, root: Path, split: str, augment: bool = False) -> None:
        self.root = root
        self.augment = augment
        self.items: list[dict] = []
        split_dir = root / split
        for jp in sorted(split_dir.glob("*.json")):
            if jp.name.startswith("_"):
                continue
            meta = json.loads(jp.read_text(encoding="utf-8"))
            if meta.get("offline_label") not in ("clear", "blocked"):
                continue
            if not meta.get("world_alignment_passed", True):
                continue
            img = root / meta["image_path"]
            if not img.is_file():
                continue
            self.items.append(meta)
        if not self.items:
            raise FileNotFoundError(f"no samples in {split_dir}")

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        meta = self.items[idx]
        arr = np.load(self.root / meta["image_path"]).astype(np.float32)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.max() > 1.5:
            arr = arr / 255.0
        if self.augment:
            # Photometric only — no geometric crops that erase obstacles.
            if random.random() < 0.8:
                scale = random.uniform(0.75, 1.25)
                arr = np.clip(arr * scale, 0.0, 1.0)
            if random.random() < 0.5:
                arr = np.clip(arr + random.uniform(-0.08, 0.08), 0.0, 1.0)
            if random.random() < 0.3:
                # Mild channel scale (color jitter).
                for c in range(3):
                    arr[..., c] = np.clip(arr[..., c] * random.uniform(0.85, 1.15), 0.0, 1.0)
        x = torch.from_numpy(arr.transpose(2, 0, 1).copy())
        y = torch.tensor(1.0 if meta["offline_label"] == "blocked" else 0.0)
        return x, y


class GenesisCorridorHead(nn.Module):
    """96×96 RGB → blocked logit (user-spec light head)."""

    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x)).squeeze(-1)


def balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    scores = []
    for cls in (0, 1):
        mask = y_true == cls
        if not mask.any():
            continue
        scores.append(float((y_pred[mask] == cls).mean()))
    return float(np.mean(scores)) if scores else 0.0


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> dict:
    model.eval()
    ys, ps = [], []
    for x, y in loader:
        x = x.to(device)
        logit = model(x)
        prob = torch.sigmoid(logit).cpu().numpy()
        ys.append(y.numpy())
        ps.append(prob)
    y_true = np.concatenate(ys)
    p = np.concatenate(ps)
    y_pred = (p >= 0.5).astype(np.float32)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    blocked_recall = tp / max(1, tp + fn)
    false_clear = fn / max(1, tp + fn)  # blocked predicted clear
    return {
        "balanced_accuracy": balanced_accuracy(y_true, y_pred),
        "blocked_recall": blocked_recall,
        "false_clear_rate": false_clear,
        "acc": float((y_pred == y_true).mean()),
        "n": int(y_true.size),
        "n_blocked": int(y_true.sum()),
        "n_clear": int((1 - y_true).sum()),
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--patience", type=int, default=8)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    train_ds = CorridorRGBDataset(args.data_dir, "train", augment=True)
    val_ds = CorridorRGBDataset(args.data_dir, "validation", augment=False)
    labels = [1 if m["offline_label"] == "blocked" else 0 for m in train_ds.items]
    n_pos = max(1, sum(labels))
    n_neg = max(1, len(labels) - sum(labels))
    weights = [1.0 / n_pos if y == 1 else 1.0 / n_neg for y in labels]
    sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=args.num_workers,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers
    )

    model = GenesisCorridorHead().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_weight = torch.tensor([n_neg / n_pos], device=device)
    best_ba = -1.0
    best_path = args.out_dir / "best.pt"
    history = []
    stale = 0

    for ep in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        n_batches = 0
        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)
            logit = model(x)
            loss = F.binary_cross_entropy_with_logits(logit, y, pos_weight=pos_weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += float(loss.item())
            n_batches += 1
        val = evaluate(model, val_loader, device)
        row = {
            "epoch": ep,
            "train_loss": total_loss / max(1, n_batches),
            **{f"val_{k}": v for k, v in val.items() if k != "confusion"},
            "val_confusion": val["confusion"],
        }
        history.append(row)
        print(row, flush=True)
        ba = float(val["balanced_accuracy"])
        if ba > best_ba + 1e-4:
            best_ba = ba
            stale = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "model": "GenesisCorridorHead",
                    "input_size": 96,
                    "label": "blocked_logit",
                    "best_val_balanced_accuracy": best_ba,
                    "history": history,
                    "data_dir": str(args.data_dir),
                },
                best_path,
            )
        else:
            stale += 1
            if stale >= args.patience:
                print(f"early stop at epoch {ep}", flush=True)
                break

    summary = {
        "checkpoint": str(best_path),
        "device": device,
        "best_val_balanced_accuracy": best_ba,
        "train_n": len(train_ds),
        "val_n": len(val_ds),
        "history": history,
        "thresholds_target": {
            "balanced_accuracy": 0.85,
            "blocked_recall": 0.90,
            "false_clear_rate": 0.05,
        },
    }
    (args.out_dir / "train_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "history"}, indent=2))
    return 0 if best_ba >= 0.85 else 2


if __name__ == "__main__":
    raise SystemExit(main())
