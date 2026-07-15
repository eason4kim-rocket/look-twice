#!/usr/bin/env python3
"""Collect the paired Look Twice v4 split-conformal calibration dataset."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from purify_bridge import PurifyBridge
from v4_claims import canonical_json
from v4_episode import (
    cross_region_contract,
    select_initial_viewpoint,
    smoke_calibration_artifact,
)
from v4_evidence import SENSOR_VERSION, process_evidence_frame
from v4_runtime import SyntheticEpisodeRuntime
from v4_scenario import PROFILES, sample_v4_scenario


ROW_SCHEMA = "look-twice.calibration-row/v4"
ERROR_SCHEMA = "look-twice.calibration-error/v4"
ID_PROFILES = tuple(profile for profile in PROFILES if profile != "ood-severity")
SMOKE_SEEDS = tuple(range(30000, 30002))
FORMAL_SEEDS = tuple(range(30000, 30050))
REQUIRED_SAMPLE_FIELDS = (
    "seed",
    "profile",
    "noise_intensity",
    "sensor_version",
    "true_label",
    "p_clear",
)


@dataclass(frozen=True, slots=True)
class CalibrationSpec:
    profile: str
    seed: int

    def __post_init__(self) -> None:
        if self.profile == "ood-severity":
            raise ValueError("ood-severity is forbidden in calibration collection")
        if self.profile not in ID_PROFILES:
            raise ValueError(f"unsupported calibration profile: {self.profile}")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")

    @property
    def stem(self) -> str:
        return f"{self.profile}__seed-{self.seed}"


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    mode: str
    runtime: str
    motion_backend: str
    device: str
    output_dir: Path
    output_jsonl: Path
    python: str
    script: Path
    purify_bin: Path | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"smoke", "formal"}:
            raise ValueError("mode must be smoke or formal")
        if self.runtime not in {"synthetic", "genesis"}:
            raise ValueError("runtime must be synthetic or genesis")
        if self.motion_backend not in {"kinematic", "skid-steer"}:
            raise ValueError("motion_backend must be kinematic or skid-steer")
        if self.mode == "formal":
            if self.runtime != "genesis":
                raise ValueError("formal calibration requires --runtime genesis")
            if not self.device.startswith("cuda"):
                raise ValueError("formal calibration requires a ROCm cuda:* device")
        if self.runtime == "synthetic":
            if self.mode != "smoke":
                raise ValueError("synthetic calibration is smoke/dev only")
            if self.device != "cpu":
                raise ValueError("synthetic calibration requires --device cpu")
            if self.motion_backend != "kinematic":
                raise ValueError("synthetic calibration uses kinematic motion")
        if not self.script.is_file():
            raise ValueError(f"collector script does not exist: {self.script}")
        if self.purify_bin is not None and not self.purify_bin.is_file():
            raise ValueError(f"Purify core does not exist: {self.purify_bin}")


def calibration_matrix(mode: str) -> tuple[CalibrationSpec, ...]:
    if mode == "smoke":
        seeds = SMOKE_SEEDS
    elif mode == "formal":
        seeds = FORMAL_SEEDS
    else:
        raise ValueError("mode must be smoke or formal")
    return tuple(
        CalibrationSpec(profile, seed)
        for profile in ID_PROFILES
        for seed in seeds
    )


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text(path, canonical_json(payload) + "\n")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _row_matches(
    row: dict[str, Any], config: CollectorConfig, spec: CalibrationSpec
) -> bool:
    if row.get("schema_version") != ROW_SCHEMA:
        return False
    if any(field not in row for field in REQUIRED_SAMPLE_FIELDS):
        return False
    if row.get("profile") != spec.profile or row.get("seed") != spec.seed:
        return False
    configuration = row.get("collector_configuration")
    if not isinstance(configuration, dict):
        return False
    return configuration == {
        "mode": config.mode,
        "runtime": config.runtime,
        "motion_backend": config.motion_backend,
        "device": config.device,
    }


def collect_one(
    config: CollectorConfig,
    spec: CalibrationSpec,
) -> dict[str, Any]:
    """Collect one row in-process; Genesis callers isolate this in a subprocess."""
    scenario = sample_v4_scenario(spec.profile, spec.seed)
    if config.runtime == "genesis":
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        from v4_genesis_runtime import GenesisEpisodeRuntime

        runtime = GenesisEpisodeRuntime(
            scenario,
            motion_backend=config.motion_backend,
        )
    else:
        runtime = SyntheticEpisodeRuntime(scenario)

    command = (config.purify_bin,) if config.purify_bin is not None else None
    bridge = PurifyBridge(command=command)
    try:
        bridge.start()
        start_xy = (runtime.current_pose.x, runtime.current_pose.y)
        # Prefer the planner's initial viewpoint, then fall back through every
        # publicly reachable candidate so kinematic contact on one side view
        # does not discard the entire calibration seed.
        ordered: list[dict[str, Any]] = []
        preferred = select_initial_viewpoint(scenario.public_context, start_xy)
        if preferred is not None:
            ordered.append(dict(preferred))
        for item in scenario.public_context["candidate_viewpoints"]:
            if not item.get("reachable"):
                continue
            if preferred is not None and item.get("name") == preferred.get("name"):
                continue
            ordered.append(dict(item))
        if not ordered:
            raise RuntimeError("no reachable initial calibration viewpoint")

        candidate: dict[str, Any] | None = None
        viewpoint_xy: tuple[float, float] | None = None
        attempt_errors: list[str] = []
        for option in ordered:
            target = (float(option["xy"][0]), float(option["xy"][1]))
            movement = runtime.move_to(target)
            if movement.reached:
                candidate = option
                viewpoint_xy = target
                break
            attempt_errors.append(
                f"{option.get('name')}:{movement.reason}"
            )
        if candidate is None or viewpoint_xy is None:
            raise RuntimeError(
                "failed to reach any calibration viewpoint: "
                + "; ".join(attempt_errors)
            )
        runtime.wait_steps(10)
        raw = runtime.capture_raw(
            viewpoint=str(candidate["name"]),
            viewpoint_xy=viewpoint_xy,
            predicted_coverage=float(candidate["predicted_coverage"]),
        )
        capture = process_evidence_frame(
            raw,
            scenario,
            observation_index=0,
            repair_action_kind="initial",
            device=config.device,
            ttl_steps=60,
            evidence_dir=None,
        )
        discarded_nonapplicable_capture: dict[str, Any] | None = None
        if capture.corruption.sensor_version != SENSOR_VERSION:
            # A calibration row may only describe the sensor version named in
            # the resulting artifact.  The pose-drift profile deliberately
            # makes the first capture non-applicable, so audit it and collect a
            # repaired base-version capture instead of silently relabelling a
            # mismatched score as SENSOR_VERSION.
            discarded_nonapplicable_capture = {
                "capture_root_id": capture.capture_root_id,
                "capture_step": capture.observed_step,
                "observed_sensor_version": capture.corruption.sensor_version,
                "raw_artifact_sha256": dict(capture.raw_artifact_sha256),
                "corrupted_artifact_sha256": dict(
                    capture.corrupted_artifact_sha256
                ),
                "reason": "sensor_version_not_applicable_to_calibration_artifact",
            }
            runtime.wait_steps(10)
            repaired_raw = runtime.capture_raw(
                viewpoint=str(candidate["name"]),
                viewpoint_xy=viewpoint_xy,
                predicted_coverage=float(candidate["predicted_coverage"]),
            )
            capture = process_evidence_frame(
                repaired_raw,
                scenario,
                observation_index=1,
                repair_action_kind="same_view",
                device=config.device,
                ttl_steps=60,
                evidence_dir=None,
            )
            if capture.corruption.sensor_version != SENSOR_VERSION:
                raise RuntimeError(
                    "sensor version repair did not return to the calibrated base version"
                )
        # The placeholder artifact is only a valid wire object for the Go core.
        # p_blocked is fused before applicability/conformal admission, so the
        # returned probability is the required uncalibrated model score even
        # when calibration_applicable is false.
        receipt = bridge.evaluate_action(
            claims=capture.claims,
            contract=cross_region_contract(),
            calibration=smoke_calibration_artifact(),
            current_step=capture.observed_step,
            profile=spec.profile,
            noise_intensity=capture.corruption.declared_noise_intensity,
            sensor_version=capture.corruption.sensor_version,
        )
        p_clear = 1.0 - float(receipt["p_blocked"])
        if not 0.0 <= p_clear <= 1.0:
            raise RuntimeError("Go core returned an invalid uncalibrated probability")
        true_label = (
            "blocked"
            if scenario.truth_blocked_at(capture.observed_step)
            else "clear"
        )
        return {
            "schema_version": ROW_SCHEMA,
            "seed": spec.seed,
            "profile": spec.profile,
            "noise_intensity": capture.corruption.declared_noise_intensity,
            # Calibration uses one supported base sensor version.  The observed
            # version is retained separately to audit injected pose drift.
            "sensor_version": SENSOR_VERSION,
            "observed_sensor_version": capture.corruption.sensor_version,
            "true_label": true_label,
            "p_clear": p_clear,
            "capture_step": capture.observed_step,
            "viewpoint": capture.viewpoint,
            "viewpoint_xy": list(capture.viewpoint_xy),
            "paired_world_id": scenario.paired_world_id,
            "scenario_id": scenario.scenario_id,
            "capture_root_id": capture.capture_root_id,
            "receipt_id": receipt.get("receipt_id"),
            "receipt_sha256": receipt.get("receipt_sha256"),
            "calibration_applicable_during_collection": receipt.get(
                "calibration_applicable"
            ),
            "raw_artifact_sha256": dict(capture.raw_artifact_sha256),
            "corrupted_artifact_sha256": dict(
                capture.corrupted_artifact_sha256
            ),
            "gpu_environment": runtime.environment,
            "collector_configuration": {
                "mode": config.mode,
                "runtime": config.runtime,
                "motion_backend": config.motion_backend,
                "device": config.device,
            },
            "discarded_nonapplicable_capture": discarded_nonapplicable_capture,
        }
    finally:
        bridge.close()
        runtime.close()


def _worker_command(
    config: CollectorConfig, spec: CalibrationSpec, row_path: Path
) -> list[str]:
    command = [
        config.python,
        str(config.script),
        "--worker",
        "--mode",
        config.mode,
        "--runtime",
        config.runtime,
        "--motion",
        config.motion_backend,
        "--device",
        config.device,
        "--output-dir",
        str(config.output_dir),
        "--output-jsonl",
        str(config.output_jsonl),
        "--worker-profile",
        spec.profile,
        "--worker-seed",
        str(spec.seed),
        "--worker-output",
        str(row_path),
    ]
    if config.purify_bin is not None:
        command.extend(["--purify-bin", str(config.purify_bin)])
    return command


def _write_error(
    config: CollectorConfig,
    spec: CalibrationSpec,
    *,
    reason: str,
    command: list[str] | None = None,
    returncode: int | None = None,
    stderr: str = "",
) -> Path:
    path = config.output_dir / "errors" / f"{spec.stem}.error.json"
    _atomic_json(
        path,
        {
            "schema_version": ERROR_SCHEMA,
            "profile": spec.profile,
            "seed": spec.seed,
            "reason": reason,
            "command": command,
            "returncode": returncode,
            "stderr_tail": stderr[-8000:],
            "recorded_unix_time": time.time(),
        },
    )
    return path


def collect_spec(config: CollectorConfig, spec: CalibrationSpec) -> str:
    row_path = config.output_dir / "rows" / f"{spec.stem}.json"
    existing = _read_json(row_path)
    if existing is not None and _row_matches(existing, config, spec):
        return "skipped"
    try:
        if config.runtime == "genesis":
            command = _worker_command(config, spec, row_path)
            completed = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if completed.returncode != 0:
                _write_error(
                    config,
                    spec,
                    reason="genesis_worker_failed",
                    command=command,
                    returncode=completed.returncode,
                    stderr=completed.stderr,
                )
                return "error"
            row = _read_json(row_path)
            if row is None or not _row_matches(row, config, spec):
                _write_error(
                    config,
                    spec,
                    reason="genesis_worker_produced_invalid_row",
                    command=command,
                    returncode=completed.returncode,
                    stderr=completed.stderr,
                )
                return "error"
        else:
            row = collect_one(config, spec)
            _atomic_json(row_path, row)
        return "completed"
    except Exception as exc:
        _write_error(config, spec, reason=f"{type(exc).__name__}: {exc}")
        return "error"


def build_deterministic_jsonl(
    config: CollectorConfig, specs: Iterable[CalibrationSpec]
) -> int:
    rows: list[dict[str, Any]] = []
    for spec in sorted(specs, key=lambda item: (item.profile, item.seed)):
        path = config.output_dir / "rows" / f"{spec.stem}.json"
        row = _read_json(path)
        if row is None or not _row_matches(row, config, spec):
            raise ValueError(f"missing complete calibration row: {spec.stem}")
        rows.append(row)
    _atomic_text(
        config.output_jsonl,
        "".join(canonical_json(row) + "\n" for row in rows),
    )
    return len(rows)


def collect_specs(
    config: CollectorConfig, specs: Iterable[CalibrationSpec]
) -> dict[str, int]:
    materialised = tuple(specs)
    counts = {"completed": 0, "skipped": 0, "error": 0}
    for index, spec in enumerate(materialised, start=1):
        status = collect_spec(config, spec)
        counts[status] += 1
        print(
            f"[{index}/{len(materialised)}] {status}: {spec.profile} seed={spec.seed}",
            flush=True,
        )
    if counts["error"] == 0:
        build_deterministic_jsonl(config, materialised)
    return counts


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "formal"), default="smoke")
    parser.add_argument(
        "--runtime", choices=("synthetic", "genesis"), default="synthetic"
    )
    parser.add_argument(
        "--motion", choices=("kinematic", "skid-steer"), default="kinematic"
    )
    parser.add_argument("--device")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--purify-bin", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-profile", choices=ID_PROFILES, help=argparse.SUPPRESS)
    parser.add_argument("--worker-seed", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.device is None:
        args.device = "cpu" if args.runtime == "synthetic" else "cuda:0"
    if args.output_jsonl is None:
        args.output_jsonl = args.output_dir / "calibration.jsonl"
    return args


def config_from_args(args: argparse.Namespace) -> CollectorConfig:
    return CollectorConfig(
        mode=args.mode,
        runtime=args.runtime,
        motion_backend=args.motion,
        device=args.device,
        output_dir=args.output_dir,
        output_jsonl=args.output_jsonl,
        python=args.python,
        script=Path(__file__).resolve(),
        purify_bin=args.purify_bin,
    )


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = config_from_args(args)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    if args.worker:
        if args.worker_profile is None or args.worker_seed is None or args.worker_output is None:
            print("worker requires profile, seed, and output", file=sys.stderr)
            return 2
        spec = CalibrationSpec(args.worker_profile, args.worker_seed)
        try:
            _atomic_json(args.worker_output, collect_one(config, spec))
        except Exception as exc:
            print(f"worker failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0

    specs = calibration_matrix(config.mode)
    counts = collect_specs(config, specs)
    print(
        "finished:",
        f"completed={counts['completed']}",
        f"skipped={counts['skipped']}",
        f"error={counts['error']}",
        f"jsonl={config.output_jsonl}",
    )
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
