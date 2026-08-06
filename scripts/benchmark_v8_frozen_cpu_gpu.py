#!/usr/bin/env python3
"""Compare the exact frozen V8 vision model on the host CPU and Radeon GPU.

This additive benchmark measures only synchronized FP32 model forwards on
preloaded synthetic tensors. It never opens the locked dataset, changes model
weights, runs Genesis, invokes Purify, or measures end-to-end robot latency.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_CHECKPOINT_SHA256 = (
    "7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783"
)
BENCHMARK_SEED = 20260803
FORMAL_BATCH_SIZES = (1, 4, 8)
FORMAL_WARMUP = 20
FORMAL_ITERATIONS = 100
FORMAL_CPU_THREADS = 64
DEVICE_ORDER = ("cpu", "cuda:0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src",
        help="Directory containing the frozen V8 runtime sources",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cpu-threads", type=int, default=FORMAL_CPU_THREADS)
    parser.add_argument(
        "--expected-source-commit",
        help="Required for a formal run; must equal the repository HEAD",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use one batch, one warm-up, and two measurements",
    )
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


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def cpu_model_name() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.is_file():
        return platform.processor() or None
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or None


def make_inputs(torch: Any, batch_size: int) -> tuple[Any, Any]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(BENCHMARK_SEED + batch_size)
    x5 = torch.rand(
        (batch_size, 5, 256, 256),
        generator=generator,
        dtype=torch.float32,
    )
    x5[:, 4, :, :] = 0.0
    x5[:, 4, 48:224, 72:184] = 1.0
    geom = torch.zeros((batch_size, 12), dtype=torch.float32)
    geom[:, 2] = 0.5
    geom[:, 4] = 1.0
    geom[:, 5] = 1.0
    geom[:, 6] = 1.0
    return x5, geom


def synchronize(torch: Any, device: str) -> None:
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)


def tensor_snapshot(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        raise RuntimeError(f"expected dictionary model output, got {type(output)!r}")
    snapshot: dict[str, Any] = {}
    for key, value in output.items():
        if hasattr(value, "detach"):
            snapshot[key] = value.detach().to("cpu").clone()
    if not snapshot:
        raise RuntimeError("model output contained no tensors")
    return snapshot


def benchmark_device(
    *,
    torch: Any,
    load_spatial_checkpoint: Any,
    checkpoint: Path,
    expected_checkpoint_sha: str,
    device: str,
    batch_sizes: tuple[int, ...],
    warmup: int,
    iterations: int,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]], dict[str, Any]]:
    model, loader_sha, checkpoint_meta = load_spatial_checkpoint(
        checkpoint,
        device=device,
    )
    if loader_sha != expected_checkpoint_sha:
        raise RuntimeError("checkpoint loader returned a different hash")
    if checkpoint_meta.get("runtime_backend") != "deeplabv3_resnet50":
        raise RuntimeError(
            f"unexpected runtime backend: {checkpoint_meta.get('runtime_backend')}"
        )
    model.eval()

    parameter_identity = {
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "trainable_parameter_count": sum(
            parameter.numel()
            for parameter in model.parameters()
            if parameter.requires_grad
        ),
        "state_dict_tensor_elements_including_buffers": sum(
            value.numel()
            for value in model.state_dict().values()
            if hasattr(value, "numel")
        ),
        "model_id": checkpoint_meta.get("model_id_ckpt"),
        "preprocessing_version": checkpoint_meta.get("preprocessing_version_ckpt"),
        "epoch": checkpoint_meta.get("epoch"),
        "runtime_backend": checkpoint_meta.get("runtime_backend"),
    }

    device_identity: dict[str, Any]
    if device.startswith("cuda"):
        properties = torch.cuda.get_device_properties(device)
        device_identity = {
            "device": device,
            "device_name": torch.cuda.get_device_name(device),
            "device_total_memory_bytes": int(properties.total_memory),
            "gcn_arch_name": getattr(properties, "gcnArchName", None),
            "visible_devices": os.environ.get("HIP_VISIBLE_DEVICES"),
        }
    else:
        device_identity = {
            "device": device,
            "cpu_model": cpu_model_name(),
            "logical_cpu_count": os.cpu_count(),
            "affinity_cpu_count": (
                len(os.sched_getaffinity(0))
                if hasattr(os, "sched_getaffinity")
                else None
            ),
            "torch_intraop_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
        }

    rows: list[dict[str, Any]] = []
    snapshots: dict[int, dict[str, Any]] = {}
    with torch.inference_mode():
        for batch_size in batch_sizes:
            x5_cpu, geom_cpu = make_inputs(torch, batch_size)
            x5 = x5_cpu.to(device)
            geom = geom_cpu.to(device)

            if device.startswith("cuda"):
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats(device)
                baseline_allocated = int(torch.cuda.memory_allocated(device))
            else:
                baseline_allocated = None

            last_warmup_output = None
            for _ in range(warmup):
                last_warmup_output = model(x5, geom)
            synchronize(torch, device)
            if last_warmup_output is None:
                raise RuntimeError("warm-up produced no model output")
            snapshots[batch_size] = tensor_snapshot(last_warmup_output)

            durations_ms: list[float] = []
            for _ in range(iterations):
                started = time.perf_counter_ns()
                model(x5, geom)
                synchronize(torch, device)
                durations_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)

            if not all(math.isfinite(value) and value > 0 for value in durations_ms):
                raise RuntimeError(f"non-finite or non-positive duration on {device}")
            mean_ms = statistics.fmean(durations_ms)
            memory_mib: dict[str, float] | None = None
            if device.startswith("cuda"):
                peak_allocated = int(torch.cuda.max_memory_allocated(device))
                peak_reserved = int(torch.cuda.max_memory_reserved(device))
                memory_mib = {
                    "baseline_allocated": baseline_allocated / (1024.0 * 1024.0),
                    "peak_allocated": peak_allocated / (1024.0 * 1024.0),
                    "peak_reserved": peak_reserved / (1024.0 * 1024.0),
                    "incremental_peak_allocated": max(
                        0, peak_allocated - baseline_allocated
                    )
                    / (1024.0 * 1024.0),
                }
            rows.append(
                {
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
                    "memory_mib": memory_mib,
                }
            )
            del x5_cpu, geom_cpu, x5, geom
            if device.startswith("cuda"):
                torch.cuda.empty_cache()

    del model
    gc.collect()
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return (
        {
            "identity": device_identity,
            "results": rows,
        },
        snapshots,
        parameter_identity,
    )


def compare_outputs(
    *,
    torch: Any,
    cpu_outputs: dict[int, dict[str, Any]],
    gpu_outputs: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for batch_size in sorted(cpu_outputs):
        cpu_batch = cpu_outputs[batch_size]
        gpu_batch = gpu_outputs[batch_size]
        if set(cpu_batch) != set(gpu_batch):
            raise RuntimeError(f"output keys differ at batch {batch_size}")
        per_tensor: dict[str, Any] = {}
        for key in sorted(cpu_batch):
            cpu_value = cpu_batch[key]
            gpu_value = gpu_batch[key]
            if tuple(cpu_value.shape) != tuple(gpu_value.shape):
                raise RuntimeError(
                    f"output shape differs for {key} at batch {batch_size}"
                )
            difference = (cpu_value - gpu_value).abs()
            if not bool(torch.isfinite(cpu_value).all()) or not bool(
                torch.isfinite(gpu_value).all()
            ):
                raise RuntimeError(f"non-finite output for {key} at batch {batch_size}")
            per_tensor[key] = {
                "shape": list(cpu_value.shape),
                "maximum_absolute_difference": float(difference.max().item()),
                "mean_absolute_difference": float(difference.mean().item()),
                "allclose_rtol_1e-3_atol_1e-4": bool(
                    torch.allclose(cpu_value, gpu_value, rtol=1e-3, atol=1e-4)
                ),
            }
        comparisons.append(
            {
                "batch_size": batch_size,
                "all_tensors_close_at_declared_tolerance": all(
                    row["allclose_rtol_1e-3_atol_1e-4"] for row in per_tensor.values()
                ),
                "tensors": per_tensor,
            }
        )
    return comparisons


def main() -> int:
    args = parse_args()
    if not args.checkpoint.is_file():
        raise SystemExit(f"checkpoint not found: {args.checkpoint}")
    if not args.source_dir.is_dir():
        raise SystemExit(f"source directory not found: {args.source_dir}")
    if args.cpu_threads < 1:
        raise SystemExit("--cpu-threads must be positive")
    if not args.smoke and args.cpu_threads != FORMAL_CPU_THREADS:
        raise SystemExit(
            f"formal CPU thread count is fixed at {FORMAL_CPU_THREADS}, got {args.cpu_threads}"
        )
    if not args.smoke and not args.expected_source_commit:
        raise SystemExit("formal runs require --expected-source-commit")

    repo_root = Path(__file__).resolve().parents[1]
    source_commit = git_output(repo_root, "rev-parse", "HEAD")
    tracked_status = git_output(
        repo_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    )
    if tracked_status:
        raise SystemExit("tracked source worktree is not clean")
    if args.expected_source_commit and source_commit != args.expected_source_commit:
        raise SystemExit(
            f"source commit mismatch: expected {args.expected_source_commit}, got {source_commit}"
        )

    source_dir = str(args.source_dir.resolve())
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)

    import torch

    from v8_spatial_runtime import load_spatial_checkpoint

    if not torch.cuda.is_available():
        raise SystemExit(
            "torch.cuda.is_available() is false; Radeon comparison unavailable"
        )
    checkpoint_sha = file_sha256(args.checkpoint)
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        raise SystemExit(
            "checkpoint identity mismatch: "
            f"expected {EXPECTED_CHECKPOINT_SHA256}, got {checkpoint_sha}"
        )

    torch.manual_seed(BENCHMARK_SEED)
    torch.set_num_threads(args.cpu_threads)
    if args.smoke:
        batch_sizes = (1,)
        warmup = 1
        iterations = 2
        run_class = "engineering_smoke"
    else:
        batch_sizes = FORMAL_BATCH_SIZES
        warmup = FORMAL_WARMUP
        iterations = FORMAL_ITERATIONS
        run_class = "formal_additive"

    device_reports: dict[str, Any] = {}
    reference_outputs: dict[str, dict[int, dict[str, Any]]] = {}
    parameter_identities: dict[str, dict[str, Any]] = {}
    for device in DEVICE_ORDER:
        report, snapshots, parameter_identity = benchmark_device(
            torch=torch,
            load_spatial_checkpoint=load_spatial_checkpoint,
            checkpoint=args.checkpoint,
            expected_checkpoint_sha=checkpoint_sha,
            device=device,
            batch_sizes=batch_sizes,
            warmup=warmup,
            iterations=iterations,
        )
        device_reports[device] = report
        reference_outputs[device] = snapshots
        parameter_identities[device] = parameter_identity
    if parameter_identities["cpu"] != parameter_identities["cuda:0"]:
        raise RuntimeError("CPU and GPU model identities differ")

    parity = compare_outputs(
        torch=torch,
        cpu_outputs=reference_outputs["cpu"],
        gpu_outputs=reference_outputs["cuda:0"],
    )
    cpu_by_batch = {row["batch_size"]: row for row in device_reports["cpu"]["results"]}
    gpu_by_batch = {
        row["batch_size"]: row for row in device_reports["cuda:0"]["results"]
    }
    comparisons = []
    for batch_size in batch_sizes:
        cpu_row = cpu_by_batch[batch_size]
        gpu_row = gpu_by_batch[batch_size]
        comparisons.append(
            {
                "batch_size": batch_size,
                "gpu_over_cpu_speedup_by_mean_latency": (
                    cpu_row["latency_ms"]["mean"] / gpu_row["latency_ms"]["mean"]
                ),
                "gpu_over_cpu_speedup_by_p50_latency": (
                    cpu_row["latency_ms"]["median_p50"]
                    / gpu_row["latency_ms"]["median_p50"]
                ),
                "gpu_over_cpu_throughput_ratio": (
                    gpu_row["throughput_images_per_second"]
                    / cpu_row["throughput_images_per_second"]
                ),
            }
        )

    report = {
        "schema_version": "look-twice.v8-frozen-cpu-gpu-comparison/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "run_class": run_class,
        "claim_scope": {
            "workload": "same-host FP32 frozen-model forwards on preloaded synthetic tensors",
            "includes": [
                "frozen vision model forward pass",
                "Python dispatch",
                "synchronous CPU execution",
                "synchronized ROCm execution",
            ],
            "excludes": [
                "RGB-D preprocessing",
                "Genesis simulation and rendering",
                "Purify Go",
                "network and storage I/O",
                "closed-loop robot actuation",
            ],
            "not_end_to_end_robot_latency": True,
            "not_an_accuracy_evaluation": True,
            "locked_test_opened": False,
            "model_weights_modified": False,
            "no_minimum_speedup_acceptance_bar": True,
        },
        "method": {
            "device_order": list(DEVICE_ORDER),
            "seed": BENCHMARK_SEED,
            "precision": "float32",
            "input_resolution": [256, 256],
            "batch_sizes": list(batch_sizes),
            "warmup_iterations_per_device_and_batch": warmup,
            "measured_iterations_per_device_and_batch": iterations,
            "cpu_intraop_threads": args.cpu_threads,
            "inputs_preloaded_before_timing": True,
            "gpu_synchronized_after_every_measured_forward": True,
            "cpu_operations_are_synchronous": True,
        },
        "checkpoint": {
            "path_at_execution": str(args.checkpoint),
            "sha256": checkpoint_sha,
            "expected_sha256": EXPECTED_CHECKPOINT_SHA256,
            "size_bytes": args.checkpoint.stat().st_size,
            **parameter_identities["cpu"],
        },
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torch_git_version": getattr(torch.version, "git_version", None),
            "hip": getattr(torch.version, "hip", None),
        },
        "source_identity": {
            "repository_head": source_commit,
            "tracked_worktree_clean": True,
            "files": {
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
        },
        "devices": device_reports,
        "output_parity": {
            "informational_not_a_speed_acceptance_gate": True,
            "rtol": 1e-3,
            "atol": 1e-4,
            "batches": parity,
        },
        "comparison": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "run_class": run_class,
                "source_commit": source_commit,
                "output": str(args.output),
                "comparison": comparisons,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
