#!/usr/bin/env python3
"""Measure sustained ROCm telemetry for the exact frozen V8 vision model.

This benchmark uses deterministic, preloaded synthetic tensors.  It never
reads an evaluation split, changes the checkpoint, or measures the complete
robot loop.  ``rocm-smi`` samples are collected only while synchronized model
forwards are running.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_CHECKPOINT_SHA256 = (
    "7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783"
)
BENCHMARK_SEED = 20260803
TELEMETRY_FIELDS = {
    "GPU use (%)": "gpu_use_percent",
    "GPU Memory Allocated (VRAM%)": "vram_allocated_percent",
    "GPU Memory Read/Write Activity (%)": "memory_activity_percent",
    "Average Graphics Package Power (W)": "graphics_package_power_w",
    "Temperature (Sensor edge) (C)": "temperature_edge_c",
    "Temperature (Sensor junction) (C)": "temperature_junction_c",
    "Temperature (Sensor memory) (C)": "temperature_memory_c",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src",
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=1.0)
    parser.add_argument("--rocm-smi", default="rocm-smi")
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


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or value.strip().upper() in {"N/A", "NA", ""}:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def parse_rocm_smi_json(text: str) -> dict[str, float | str | None]:
    """Return an allow-listed, privacy-safe telemetry row."""

    payload = json.loads(text)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("rocm-smi JSON contains no devices")
    card_name = sorted(payload)[0]
    raw = payload[card_name]
    if not isinstance(raw, dict):
        raise ValueError("rocm-smi device payload is not an object")
    row: dict[str, float | str | None] = {"device": card_name}
    for source_name, public_name in TELEMETRY_FIELDS.items():
        row[public_name] = _numeric(raw.get(source_name))
    return row


def confirms_no_kfd_processes(text: str) -> bool:
    """Recognize ROCm SMI's explicit clean-process preflight result."""

    return "No KFD PIDs currently running" in text


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"sample_count": len(samples)}
    for public_name in TELEMETRY_FIELDS.values():
        values = [
            float(sample[public_name])
            for sample in samples
            if sample.get(public_name) is not None
        ]
        if values:
            summary[public_name] = {
                "mean": statistics.fmean(values),
                "minimum": min(values),
                "maximum": max(values),
                "p50": statistics.median(values),
                "p95": percentile(values, 0.95),
                "samples": len(values),
            }
        else:
            summary[public_name] = None
    return summary


class TelemetrySampler:
    def __init__(self, command: str, interval_s: float) -> None:
        self.command = command
        self.interval_s = interval_s
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_ns = 0

    def start(self) -> None:
        self._started_ns = time.perf_counter_ns()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self.interval_s + 2.0))

    def _run(self) -> None:
        argv = [
            self.command,
            "--showuse",
            "--showmemuse",
            "--showpower",
            "--showtemp",
            "--json",
        ]
        while not self._stop.is_set():
            sample_started = time.perf_counter()
            try:
                completed = subprocess.run(
                    argv,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                row = parse_rocm_smi_json(completed.stdout)
                row["offset_seconds"] = (
                    time.perf_counter_ns() - self._started_ns
                ) / 1_000_000_000.0
                self.samples.append(row)
            except Exception as exc:  # telemetry failure invalidates publication
                self.errors.append(f"{type(exc).__name__}: {exc}")
            elapsed = time.perf_counter() - sample_started
            self._stop.wait(max(0.0, self.interval_s - elapsed))


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("batch size must be positive")
    if args.warmup < 1:
        raise SystemExit("warmup must be >= 1")
    if args.duration_seconds < 10.0:
        raise SystemExit("duration must be >= 10 seconds")
    if args.sample_interval_seconds < 0.2:
        raise SystemExit("sample interval must be >= 0.2 seconds")
    if not args.checkpoint.is_file():
        raise SystemExit(f"checkpoint not found: {args.checkpoint}")
    if not args.source_dir.is_dir():
        raise SystemExit(f"source directory not found: {args.source_dir}")

    source_dir = str(args.source_dir.resolve())
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)

    preflight_telemetry_completed = subprocess.run(
        [
            args.rocm_smi,
            "--showuse",
            "--showmemuse",
            "--showpower",
            "--showtemp",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    preflight_telemetry = parse_rocm_smi_json(
        preflight_telemetry_completed.stdout
    )
    preflight_processes_completed = subprocess.run(
        [args.rocm_smi, "--showpids"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    no_other_gpu_processes = confirms_no_kfd_processes(
        preflight_processes_completed.stdout
    )
    if not no_other_gpu_processes:
        raise SystemExit("GPU preflight failed: another KFD process is active")
    if (preflight_telemetry.get("gpu_use_percent") or 0.0) > 5.0:
        raise SystemExit("GPU preflight failed: utilization is above 5 percent")
    if (preflight_telemetry.get("vram_allocated_percent") or 0.0) > 1.0:
        raise SystemExit("GPU preflight failed: VRAM allocation is above 1 percent")

    import torch

    from v8_spatial_runtime import load_spatial_checkpoint

    if not args.device.startswith("cuda") or not torch.cuda.is_available():
        raise SystemExit("a PyTorch ROCm torch.cuda device is required")
    checkpoint_sha = file_sha256(args.checkpoint)
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA256:
        raise SystemExit(
            f"checkpoint identity mismatch: expected {EXPECTED_CHECKPOINT_SHA256}, "
            f"got {checkpoint_sha}"
        )

    torch.manual_seed(BENCHMARK_SEED)
    model, loader_sha, checkpoint_meta = load_spatial_checkpoint(
        args.checkpoint, device=args.device
    )
    if loader_sha != checkpoint_sha:
        raise SystemExit("checkpoint loader returned a different hash")
    if checkpoint_meta.get("runtime_backend") != "deeplabv3_resnet50":
        raise SystemExit("unexpected runtime backend")
    model.eval()

    generator = torch.Generator(device="cpu")
    generator.manual_seed(BENCHMARK_SEED + args.batch_size)
    x5 = torch.rand(
        (args.batch_size, 5, 256, 256), generator=generator, dtype=torch.float32
    )
    x5[:, 4, :, :] = 0.0
    x5[:, 4, 48:224, 72:184] = 1.0
    geom = torch.zeros((args.batch_size, 12), dtype=torch.float32)
    geom[:, 2] = 0.5
    geom[:, 4:7] = 1.0
    x5 = x5.to(args.device)
    geom = geom.to(args.device)

    with torch.inference_mode():
        for _ in range(args.warmup):
            model(x5, geom)
        torch.cuda.synchronize(args.device)

        sampler = TelemetrySampler(args.rocm_smi, args.sample_interval_seconds)
        durations_ms: list[float] = []
        benchmark_started = time.perf_counter()
        sampler.start()
        while time.perf_counter() - benchmark_started < args.duration_seconds:
            started_ns = time.perf_counter_ns()
            model(x5, geom)
            torch.cuda.synchronize(args.device)
            durations_ms.append((time.perf_counter_ns() - started_ns) / 1_000_000.0)
        measured_duration_s = time.perf_counter() - benchmark_started
        sampler.stop()

    if sampler.errors:
        raise SystemExit(f"telemetry sampling failed: {sampler.errors}")
    if len(sampler.samples) < 5:
        raise SystemExit(f"too few telemetry samples: {len(sampler.samples)}")

    properties = torch.cuda.get_device_properties(args.device)
    mean_ms = statistics.fmean(durations_ms)
    report = {
        "schema_version": "look-twice.v8-frozen-rocm-telemetry/v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "claim_scope": {
            "workload": "sustained synthetic preloaded-tensor model-forward benchmark",
            "includes": [
                "exact frozen V8 vision model forward pass",
                "Python dispatch and synchronized ROCm execution",
                "rocm-smi samples collected during measured forwards",
            ],
            "excludes": [
                "RGB-D preprocessing",
                "Genesis simulation and rendering",
                "Go evidence fusion",
                "I/O and robot actuation",
            ],
            "not_end_to_end_latency": True,
            "not_an_accuracy_evaluation": True,
            "locked_test_opened": False,
            "model_weights_modified": False,
        },
        "checkpoint": {
            "sha256": checkpoint_sha,
            "hash_verified": True,
            "size_bytes": args.checkpoint.stat().st_size,
            "model_id": checkpoint_meta.get("model_id_ckpt"),
            "epoch": checkpoint_meta.get("epoch"),
            "runtime_backend": checkpoint_meta.get("runtime_backend"),
            "parameter_count": sum(p.numel() for p in model.parameters()),
        },
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "hip": getattr(torch.version, "hip", None),
            "device_api": args.device,
            "device_name": torch.cuda.get_device_name(args.device),
            "device_total_memory_bytes": int(properties.total_memory),
            "gcn_arch_name": getattr(properties, "gcnArchName", None),
            "visible_devices": os.environ.get("HIP_VISIBLE_DEVICES"),
        },
        "clean_gpu_preflight": {
            "passed": True,
            "no_kfd_processes_before_model_load": no_other_gpu_processes,
            "telemetry_before_model_load": preflight_telemetry,
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
            "batch_size": args.batch_size,
            "warmup_iterations": args.warmup,
            "requested_duration_seconds": args.duration_seconds,
            "measured_duration_seconds": measured_duration_s,
            "sample_interval_seconds": args.sample_interval_seconds,
            "synchronization": "torch.cuda.synchronize after every forward",
            "telemetry_command": "rocm-smi --showuse --showmemuse --showpower --showtemp --json",
            "privacy": "device serial, unique ID, hostname, and local paths are not collected",
        },
        "forward_results": {
            "measured_iterations": len(durations_ms),
            "measured_images": len(durations_ms) * args.batch_size,
            "latency_ms": {
                "mean": mean_ms,
                "median_p50": statistics.median(durations_ms),
                "p95": percentile(durations_ms, 0.95),
                "minimum": min(durations_ms),
                "maximum": max(durations_ms),
            },
            "throughput_images_per_second": (
                len(durations_ms) * args.batch_size / measured_duration_s
            ),
        },
        "telemetry_summary": summarize_samples(sampler.samples),
        "telemetry_samples": sampler.samples,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
