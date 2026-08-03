#!/usr/bin/env python3
"""Benchmark the exact frozen V8 vision checkpoint on a ROCm device.

This is a synthetic, preloaded-tensor model-forward benchmark. It does not
open the locked test set, change model weights, or claim end-to-end simulator
latency. The JSON report pins the checkpoint hash and captures enough runtime
identity for an independent audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_CHECKPOINT_SHA256 = (
    "7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783"
)
BENCHMARK_SEED = 20260803


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src",
        help="Directory containing v8_spatial_runtime.py",
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-sizes", nargs="+", type=int, default=[1, 4, 8])
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def bytes_to_mib(value: int) -> float:
    return value / (1024.0 * 1024.0)


def benchmark_batch(
    *,
    torch: Any,
    model: Any,
    batch_size: int,
    device: str,
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(BENCHMARK_SEED + batch_size)
    x5 = torch.rand(
        (batch_size, 5, 256, 256),
        generator=generator,
        dtype=torch.float32,
    )
    # A deterministic corridor-shaped region. RGB-D remains synthetic and the
    # tensor is copied to the accelerator before timing begins.
    x5[:, 4, :, :] = 0.0
    x5[:, 4, 48:224, 72:184] = 1.0
    geom = torch.zeros((batch_size, 12), dtype=torch.float32)
    geom[:, 2] = 0.5
    geom[:, 4] = 1.0
    geom[:, 5] = 1.0
    geom[:, 6] = 1.0
    x5 = x5.to(device)
    geom = geom.to(device)

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    baseline_allocated = int(torch.cuda.memory_allocated(device))

    with torch.inference_mode():
        for _ in range(warmup):
            model(x5, geom)
        torch.cuda.synchronize(device)

        durations_ms: list[float] = []
        for _ in range(iterations):
            started = time.perf_counter_ns()
            model(x5, geom)
            torch.cuda.synchronize(device)
            durations_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)

    peak_allocated = int(torch.cuda.max_memory_allocated(device))
    peak_reserved = int(torch.cuda.max_memory_reserved(device))
    mean_ms = statistics.fmean(durations_ms)
    result = {
        "batch_size": batch_size,
        "warmup_iterations": warmup,
        "measured_iterations": iterations,
        "precision": "float32",
        "input_shape": [batch_size, 5, 256, 256],
        "geometry_shape": [batch_size, 12],
        "latency_ms": {
            "mean": mean_ms,
            "median_p50": statistics.median(durations_ms),
            "p95": percentile(durations_ms, 0.95),
            "minimum": min(durations_ms),
            "maximum": max(durations_ms),
        },
        "throughput_images_per_second": batch_size / (mean_ms / 1000.0),
        "memory_mib": {
            "baseline_allocated": bytes_to_mib(baseline_allocated),
            "peak_allocated": bytes_to_mib(peak_allocated),
            "peak_reserved": bytes_to_mib(peak_reserved),
            "incremental_peak_allocated": bytes_to_mib(
                max(0, peak_allocated - baseline_allocated)
            ),
        },
    }
    del x5, geom
    torch.cuda.empty_cache()
    return result


def main() -> int:
    args = parse_args()
    if args.warmup < 1 or args.iterations < 2:
        raise SystemExit("warmup must be >= 1 and iterations must be >= 2")
    if any(batch_size < 1 for batch_size in args.batch_sizes):
        raise SystemExit("batch sizes must be positive")
    if not args.checkpoint.is_file():
        raise SystemExit(f"checkpoint not found: {args.checkpoint}")
    if not args.source_dir.is_dir():
        raise SystemExit(f"source directory not found: {args.source_dir}")

    source_dir = str(args.source_dir.resolve())
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)

    import torch

    from v8_spatial_runtime import load_spatial_checkpoint

    if not args.device.startswith("cuda"):
        raise SystemExit("this submission benchmark requires the ROCm torch.cuda device API")
    if not torch.cuda.is_available():
        raise SystemExit("torch.cuda.is_available() is false")

    checkpoint_sha = file_sha256(args.checkpoint)
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        raise SystemExit(
            "checkpoint identity mismatch: "
            f"expected {EXPECTED_CHECKPOINT_SHA256}, got {checkpoint_sha}"
        )

    torch.manual_seed(BENCHMARK_SEED)
    model, loader_sha, checkpoint_meta = load_spatial_checkpoint(
        args.checkpoint,
        device=args.device,
    )
    if loader_sha != checkpoint_sha:
        raise SystemExit("checkpoint loader returned a different hash")
    if checkpoint_meta.get("runtime_backend") != "deeplabv3_resnet50":
        raise SystemExit(
            "unexpected runtime backend: "
            f"{checkpoint_meta.get('runtime_backend')}"
        )
    model.eval()
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    trainable_parameter_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    state_dict_tensor_elements = sum(
        value.numel() for value in model.state_dict().values() if hasattr(value, "numel")
    )

    properties = torch.cuda.get_device_properties(args.device)
    benchmark_results = [
        benchmark_batch(
            torch=torch,
            model=model,
            batch_size=batch_size,
            device=args.device,
            warmup=args.warmup,
            iterations=args.iterations,
        )
        for batch_size in args.batch_sizes
    ]

    report = {
        "schema_version": "look-twice.v8-frozen-inference-benchmark/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "claim_scope": {
            "workload": "synthetic preloaded-tensor model-forward benchmark",
            "includes": [
                "frozen vision model forward pass",
                "Python dispatch and synchronized ROCm execution",
            ],
            "excludes": [
                "RGB-D preprocessing",
                "Genesis simulation",
                "Go evidence fusion",
                "network or storage I/O",
                "closed-loop robot actuation",
            ],
            "not_an_accuracy_evaluation": True,
            "locked_test_opened": False,
            "model_weights_modified": False,
        },
        "checkpoint": {
            "sha256": checkpoint_sha,
            "expected_sha256": EXPECTED_CHECKPOINT_SHA256,
            "hash_verified": True,
            "size_bytes": args.checkpoint.stat().st_size,
            "model_id": checkpoint_meta.get("model_id_ckpt"),
            "preprocessing_version": checkpoint_meta.get(
                "preprocessing_version_ckpt"
            ),
            "epoch": checkpoint_meta.get("epoch"),
            "runtime_backend": checkpoint_meta.get("runtime_backend"),
            "parameter_count": parameter_count,
            "trainable_parameter_count": trainable_parameter_count,
            "state_dict_tensor_elements_including_buffers": state_dict_tensor_elements,
        },
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torch_git_version": getattr(torch.version, "git_version", None),
            "hip": getattr(torch.version, "hip", None),
            "device_api": args.device,
            "device_name": torch.cuda.get_device_name(args.device),
            "device_total_memory_bytes": int(properties.total_memory),
            "gcn_arch_name": getattr(properties, "gcnArchName", None),
            "visible_devices": os.environ.get("HIP_VISIBLE_DEVICES"),
        },
        "source_identity": {
            name: {
                "sha256": file_sha256(args.source_dir / name),
                "size_bytes": (args.source_dir / name).stat().st_size,
            }
            for name in (
                "v8_spatial_model.py",
                "v8_seg_v3_model.py",
                "v8_spatial_runtime.py",
            )
        },
        "benchmark_script": {
            "sha256": file_sha256(Path(__file__).resolve()),
            "size_bytes": Path(__file__).resolve().stat().st_size,
        },
        "method": {
            "seed": BENCHMARK_SEED,
            "precision": "float32",
            "input_resolution": [256, 256],
            "synchronization": "torch.cuda.synchronize after every measured forward",
            "batch_sizes": args.batch_sizes,
            "warmup_iterations_per_batch": args.warmup,
            "measured_iterations_per_batch": args.iterations,
        },
        "results": benchmark_results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
