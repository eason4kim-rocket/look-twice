#!/usr/bin/env python3
"""Train tiny corridor vision head on synthetic RGB labels (GPU-friendly).

Labels are synthetic cue labels for the proxy head bootstrap — not oracle world
blocked flags from scenarios. Checkpoint intended for outputs/v7/ on remote GPU.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v7_vision_claims import synthetic_rgb_for_label


class TinyCorridorHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(3, 8, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(8, 16, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.fc = nn.Linear(16, 3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.net(x).flatten(1))


def _batch(labels: list[str], seed: int, device: str) -> tuple[torch.Tensor, torch.Tensor]:
    label_to_i = {"clear": 0, "blocked": 1, "inconclusive": 2}
    xs = []
    ys = []
    rng = np.random.default_rng(seed)
    for i, lab in enumerate(labels):
        rgb = synthetic_rgb_for_label(lab, seed=int(rng.integers(0, 1_000_000)) + i)
        ys_idx = np.linspace(0, rgb.shape[0] - 1, 32).astype(int)
        xs_idx = np.linspace(0, rgb.shape[1] - 1, 32).astype(int)
        small = rgb[ys_idx][:, xs_idx]
        xs.append(small.transpose(2, 0, 1))
        ys.append(label_to_i[lab])
    x = torch.tensor(np.stack(xs), dtype=torch.float32, device=device)
    y = torch.tensor(ys, dtype=torch.long, device=device)
    return x, y


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batches-per-epoch", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    model = TinyCorridorHead().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    labels_cycle = ["clear", "blocked", "inconclusive"]
    history = []
    for ep in range(args.epochs):
        total = 0.0
        correct = 0
        n = 0
        for b in range(args.batches_per_epoch):
            labs = [labels_cycle[(ep + b + i) % 3] for i in range(args.batch_size)]
            x, y = _batch(labs, seed=ep * 1000 + b, device=device)
            logits = model(x)
            loss = F.cross_entropy(logits, y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
            pred = logits.argmax(dim=1)
            correct += int((pred == y).sum().item())
            n += int(y.numel())
        hist = {
            "epoch": ep + 1,
            "loss": total / max(1, args.batches_per_epoch),
            "acc": correct / max(1, n),
        }
        history.append(hist)
        if (ep + 1) % 10 == 0 or ep == 0:
            print(hist, flush=True)

    ckpt = args.out_dir / "best.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "model": "TinyCorridorHead",
            "label_order": ["clear", "blocked", "inconclusive"],
            "history": history,
        },
        ckpt,
    )
    meta = {
        "checkpoint": str(ckpt),
        "device": device,
        "epochs": args.epochs,
        "final_acc": history[-1]["acc"] if history else None,
        "final_loss": history[-1]["loss"] if history else None,
    }
    (args.out_dir / "train_summary.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
