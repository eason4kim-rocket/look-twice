#!/usr/bin/env python3
"""Day-1 ROCm feasibility: DeepLabV3 RGB-D multi-task forward/backward + throughput.

Does not touch V7 locked data. Writes outputs/v8/rocm-feasibility/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v8_spatial_model import (  # noqa: E402
    GEOM_DIM,
    INPUT_SIZE,
    SpatialRGBDModel,
    multitask_loss,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "v8" / "rocm-feasibility")
    parser.add_argument("--batches", type=int, default=20)
    parser.add_argument(
        "--batch-sizes",
        type=int,
        nargs="+",
        default=[1, 8, 32],
    )
    parser.add_argument("--pretrained", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    device = args.device
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        print("CUDA unavailable; using cpu")
        device = "cpu"

    report: dict = {
        "schema_version": "look-twice.v8-rocm-feasibility/v1",
        "torch": torch.__version__,
        "hip": getattr(torch.version, "hip", None),
        "device": device,
        "input_size": INPUT_SIZE,
        "batch_results": [],
        "ok": False,
    }
    if torch.cuda.is_available():
        report["gpu_name"] = torch.cuda.get_device_name(0)

    model = SpatialRGBDModel(pretrained_backbone=bool(args.pretrained)).to(device)
    model.train()
    opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    n_params = sum(p.numel() for p in model.parameters())
    report["n_params"] = n_params
    print(f"params={n_params}", flush=True)

    amp = str(device).startswith("cuda")
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=amp)
    except Exception:
        scaler = torch.cuda.amp.GradScaler(enabled=amp)

    for bs in args.batch_sizes:
        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        x = torch.rand(bs, 5, INPUT_SIZE, INPUT_SIZE, device=device)
        geom = torch.randn(bs, GEOM_DIM, device=device)
        seg_t = (torch.rand(bs, 1, INPUT_SIZE, INPUT_SIZE, device=device) > 0.7).float()
        blocked = (torch.rand(bs, device=device) > 0.5).float()
        vis = torch.rand(bs, device=device)

        # Warmup
        for _ in range(3):
            with torch.autocast(device_type="cuda" if amp else "cpu", enabled=amp):
                out = model(x, geom)
                loss, _ = multitask_loss(
                    out,
                    seg_target=seg_t,
                    blocked_target=blocked,
                    visibility_target=vis,
                )
            opt.zero_grad(set_to_none=True)
            if amp:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            else:
                loss.backward()
                opt.step()

        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(args.batches):
            with torch.autocast(device_type="cuda" if amp else "cpu", enabled=amp):
                out = model(x, geom)
                loss, parts = multitask_loss(
                    out,
                    seg_target=seg_t,
                    blocked_target=blocked,
                    visibility_target=vis,
                )
            opt.zero_grad(set_to_none=True)
            if amp:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            else:
                loss.backward()
                opt.step()
        if str(device).startswith("cuda"):
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        ips = (args.batches * bs) / max(elapsed, 1e-9)
        ms_per = 1000.0 * elapsed / max(args.batches, 1)
        row = {
            "batch_size": bs,
            "batches": args.batches,
            "elapsed_s": elapsed,
            "images_per_s": ips,
            "ms_per_batch": ms_per,
            "last_loss": parts,
            "seg_out_shape": list(out["seg_logits"].shape),
        }
        report["batch_results"].append(row)
        print(json.dumps(row), flush=True)

    # Inference-only p95 estimate at bs=1
    model.eval()
    x1 = torch.rand(1, 5, INPUT_SIZE, INPUT_SIZE, device=device)
    g1 = torch.randn(1, GEOM_DIM, device=device)
    times = []
    with torch.no_grad():
        for _ in range(50):
            if str(device).startswith("cuda"):
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            _ = model(x1, g1)
            if str(device).startswith("cuda"):
                torch.cuda.synchronize()
            times.append(time.perf_counter() - t0)
    times_ms = sorted(t * 1000 for t in times)
    p95 = times_ms[int(0.95 * (len(times_ms) - 1))]
    report["inference_bs1_ms"] = {
        "p50": times_ms[len(times_ms) // 2],
        "p95": p95,
        "mean": sum(times_ms) / len(times_ms),
    }
    report["ok"] = True
    report["meets_p95_50ms_goal"] = p95 < 50.0
    path = args.output_dir / "feasibility_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("wrote", path)
    print("p95_ms", p95, "goal_ok", report["meets_p95_50ms_goal"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
