#!/usr/bin/env python3
"""Benchmark the real v4 evidence pipeline on CPU and AMD ROCm.

The timed region calls ``v4_evidence.process_evidence_frame``.  Imports,
device discovery, scenario construction, frame construction, and warmup are
explicitly excluded.  The current public pipeline processes one frame per call,
so a batch is reported honestly as a sequential microbatch rather than a fused
batch kernel.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


DEFAULT_BATCH_SIZES = (1, 8, 32, 128)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _device_environment() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {
            "torch": None,
            "rocm": None,
            "cuda_available": False,
            "gpu": None,
        }
    available = bool(torch.cuda.is_available())
    return {
        "torch": torch.__version__,
        "rocm": torch.version.hip,
        "cuda_available": available,
        "gpu": torch.cuda.get_device_name(0) if available else None,
    }


def _resolve_device(label: str) -> str:
    if label == "cpu":
        return "cpu"
    if label != "rocm":
        raise ValueError(f"unsupported benchmark device: {label}")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is not installed") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("ROCm/CUDA-compatible device is unavailable")
    if torch.version.hip is None:
        raise RuntimeError("PyTorch device is not a ROCm build")
    return "cuda:0"


def benchmark_device(
    *,
    label: str,
    batch_size: int,
    warmup: int,
    repeat: int,
) -> dict[str, Any]:
    """Time one device/batch after all setup and warmup."""
    if batch_size < 1 or warmup < 0 or repeat < 1:
        raise ValueError("batch/repeat must be positive and warmup non-negative")
    device = _resolve_device(label)
    from v4_evidence import SyntheticEvidenceSource, process_evidence_frame
    from v4_scenario import sample_v4_scenario

    scenario = sample_v4_scenario("independent-noise", 50000)
    source = SyntheticEvidenceSource()
    public = scenario.public_context
    candidate = next(
        item for item in public["candidate_viewpoints"] if item["reachable"]
    )
    frame = source.raw_frame(
        scenario=scenario,
        viewpoint=str(candidate["name"]),
        viewpoint_xy=(float(candidate["xy"][0]), float(candidate["xy"][1])),
        predicted_coverage=float(candidate["predicted_coverage"]),
        capture_step=100,
    )

    def run_microbatch() -> tuple[float, float]:
        started = time.perf_counter()
        processing_ms = 0.0
        for observation_index in range(batch_size):
            capture = process_evidence_frame(
                frame,
                scenario,
                observation_index=observation_index,
                repair_action_kind="initial",
                device=device,
                ttl_steps=60,
                evidence_dir=None,
            )
            processing_ms += float(capture.corruption.processing_time_ms)
        wall_ms = (time.perf_counter() - started) * 1000.0
        return processing_ms, wall_ms

    # Device/runtime initialization is complete before this loop.  Warmup is
    # intentionally executed but never added to any reported sample.
    for _ in range(warmup):
        run_microbatch()

    processing_samples: list[float] = []
    residual_samples: list[float] = []
    end_to_end_samples: list[float] = []
    for _ in range(repeat):
        processing_ms, wall_ms = run_microbatch()
        processing_samples.append(processing_ms)
        end_to_end_samples.append(wall_ms)
        residual_samples.append(max(0.0, wall_ms - processing_ms))

    end_median = statistics.median(end_to_end_samples)
    processing_label = "rocm_tensor_region" if label == "rocm" else "cpu_array_region"
    return {
        "status": "completed",
        "device_class": label,
        "tensor_device": device,
        "batch_size": batch_size,
        "execution_mode": "sequential_calls_to_process_evidence_frame",
        "warmup_iterations_excluded": warmup,
        "timed_iterations": repeat,
        "timing_scope": {
            "processing": processing_label,
            "transfer": (
                "residual wall time: transfers plus Python, perception, lineage, "
                "hashing, and host post-processing; not a pure transfer metric"
            ),
            "end_to_end": "complete process_evidence_frame microbatch wall time",
            "initialization_included": False,
        },
        "tensor_or_array_processing_median_ms": statistics.median(
            processing_samples
        ),
        "tensor_or_array_processing_p95_ms": percentile(processing_samples, 0.95),
        "transfer_plus_host_postprocess_median_ms": statistics.median(
            residual_samples
        ),
        "transfer_plus_host_postprocess_p95_ms": percentile(
            residual_samples, 0.95
        ),
        "end_to_end_median_ms": end_median,
        "end_to_end_p95_ms": percentile(end_to_end_samples, 0.95),
        "observations_per_second": 1000.0 * batch_size / end_median,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument(
        "--batch-sizes", type=int, nargs="+", default=list(DEFAULT_BATCH_SIZES)
    )
    parser.add_argument(
        "--devices", nargs="+", choices=("cpu", "rocm"), default=["cpu", "rocm"]
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use warmup=1, repeat=2, batches=1/8 for a non-reportable smoke check",
    )
    args = parser.parse_args(argv)
    if args.quick:
        args.warmup = 1
        args.repeat = 2
        args.batch_sizes = [1, 8]
    if args.warmup < 0 or args.repeat < 1 or any(size < 1 for size in args.batch_sizes):
        parser.error("warmup must be non-negative; repeat and batches must be positive")
    return args


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    rows: list[dict[str, Any]] = []
    for label in args.devices:
        for batch_size in args.batch_sizes:
            try:
                row = benchmark_device(
                    label=label,
                    batch_size=batch_size,
                    warmup=args.warmup,
                    repeat=args.repeat,
                )
            except RuntimeError as exc:
                row = {
                    "status": "unavailable",
                    "device_class": label,
                    "tensor_device": None,
                    "batch_size": batch_size,
                    "reason": str(exc),
                }
            rows.append(row)
            print(
                f"{label} batch={batch_size}: {row['status']}",
                flush=True,
            )
    payload = {
        "schema_version": "look-twice.evidence-benchmark/v4",
        "reportable": not args.quick,
        "environment": _device_environment(),
        "configuration": {
            "warmup": args.warmup,
            "repeat": args.repeat,
            "batch_sizes": args.batch_sizes,
            "devices": args.devices,
            "initialization_included": False,
            "public_pipeline": "v4_evidence.process_evidence_frame",
        },
        "results": rows,
    }
    _atomic_json(args.output, payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

