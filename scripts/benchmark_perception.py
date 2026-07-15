"""对比 CPU 与 AMD ROCm 上批量 RGB-D/segmentation 证据 kernel。"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))]


def benchmark_device(torch, device: str, batch: int, warmup: int, iterations: int) -> dict:
    height, width = 240, 320
    generator = torch.Generator(device="cpu").manual_seed(1234 + batch)
    host_rgb = torch.randint(0, 256, (batch, height, width, 3), generator=generator, dtype=torch.uint8)
    host_depth = torch.rand((batch, height, width), generator=generator, dtype=torch.float32) * 4.0
    host_seg = torch.randint(0, 8, (batch, height, width), generator=generator, dtype=torch.int64)

    def kernel(rgb, depth, segmentation):
        obstacle = segmentation == 6
        target = segmentation == 7
        support = obstacle.sum(dim=(1, 2))
        visible = target.sum(dim=(1, 2)).float() / float(height * width)
        valid_depth = torch.where(torch.isfinite(depth), depth, torch.zeros_like(depth))
        depth_mean = valid_depth.mean(dim=(1, 2))
        rgb_mean = rgb.float().mean(dim=(1, 2))
        return support.float().mean() + visible.mean() + depth_mean.mean() + rgb_mean.mean()

    resident_rgb = host_rgb.to(device)
    resident_depth = host_depth.to(device)
    resident_seg = host_seg.to(device)
    for _ in range(warmup):
        kernel(resident_rgb, resident_depth, resident_seg)
    if device.startswith("cuda"):
        torch.cuda.synchronize()

    kernel_times = []
    end_to_end_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        value = kernel(resident_rgb, resident_depth, resident_seg)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        kernel_times.append((time.perf_counter() - start) * 1000.0)

        start = time.perf_counter()
        rgb = host_rgb.to(device, copy=True)
        depth = host_depth.to(device, copy=True)
        segmentation = host_seg.to(device, copy=True)
        value = kernel(rgb, depth, segmentation)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        _ = value.item()
        end_to_end_times.append((time.perf_counter() - start) * 1000.0)

    median_ms = statistics.median(kernel_times)
    return {
        "device": device,
        "batch_size": batch,
        "warmup_iterations": warmup,
        "timed_iterations": iterations,
        "kernel_median_ms": median_ms,
        "kernel_p95_ms": percentile(kernel_times, 0.95),
        "kernel_observations_per_second": 1000.0 * batch / median_ms,
        "end_to_end_median_ms": statistics.median(end_to_end_times),
        "end_to_end_p95_ms": percentile(end_to_end_times, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[1, 8, 32, 128])
    args = parser.parse_args()
    import torch

    devices = ["cpu"]
    if torch.cuda.is_available():
        devices.append("cuda:0")
    rows = [
        benchmark_device(torch, device, batch, args.warmup, args.iterations)
        for device in devices
        for batch in args.batch_sizes
    ]
    payload = {
        "torch": torch.__version__,
        "rocm": torch.version.hip,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "resolution": [320, 240],
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
