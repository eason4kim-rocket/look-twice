#!/usr/bin/env python3
"""Run the paired Look Twice v4 experiment matrices with atomic resume."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


EPISODE_SCHEMA = "look-twice.episode/v4"
ERROR_SCHEMA = "look-twice.experiment-error/v4"
RUNNER_SCHEMA = "look-twice.experiment-runner/v4"
POLICIES = (
    "naive-majority",
    "v3-logodds",
    "conformal-only",
    "lineage-only",
    "purify-passive",
    "purify-active",
)
PROFILES = (
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "pose-calibration-drift",
    "structured-depth-dropout",
    "dynamic-change",
    "ood-severity",
)
SMOKE_SEEDS = tuple(range(50000, 50002))
FORMAL_SEEDS = tuple(range(50000, 50020))
PHYSICAL_POLICIES = ("naive-majority", "purify-passive", "purify-active")
PHYSICAL_PROFILES = (
    "shared-occlusion",
    "evidence-echo",
    "dynamic-change",
    "ood-severity",
)
PHYSICAL_SEEDS = tuple(range(50000, 50005))


@dataclass(frozen=True, slots=True)
class EpisodeSpec:
    policy: str
    profile: str
    seed: int

    @property
    def stem(self) -> str:
        return f"{self.policy}__{self.profile}__seed-{self.seed}"


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    mode: str
    runtime: str
    motion_backend: str
    calibration: Path | None
    device: str | None
    output_dir: Path
    python: str
    entrypoint: Path

    def __post_init__(self) -> None:
        if self.mode not in {"smoke", "formal"}:
            raise ValueError("mode must be smoke or formal")
        if self.runtime not in {"synthetic", "genesis"}:
            raise ValueError("runtime must be synthetic or genesis")
        if self.motion_backend not in {"kinematic", "skid-steer"}:
            raise ValueError("motion_backend must be kinematic or skid-steer")
        if self.mode == "formal":
            if self.runtime != "genesis":
                raise ValueError("formal mode requires --runtime genesis")
            if self.calibration is None:
                raise ValueError("formal mode requires --calibration")
        if self.runtime == "synthetic" and self.mode != "smoke":
            raise ValueError("synthetic runtime is restricted to smoke/dev runs")
        if self.runtime == "synthetic" and self.motion_backend != "kinematic":
            raise ValueError("synthetic runtime uses the kinematic CI backend")
        if self.calibration is not None and not self.calibration.is_file():
            raise ValueError(f"calibration file does not exist: {self.calibration}")
        if not self.python:
            raise ValueError("python executable cannot be empty")
        if not self.entrypoint.is_file():
            raise ValueError(f"v4 entrypoint does not exist: {self.entrypoint}")


@dataclass(frozen=True, slots=True)
class JobResult:
    spec: EpisodeSpec
    status: str
    output_path: Path
    error_path: Path | None = None
    message: str = ""


def experiment_matrix(mode: str) -> tuple[EpisodeSpec, ...]:
    if mode == "smoke":
        seeds = SMOKE_SEEDS
    elif mode == "formal":
        seeds = FORMAL_SEEDS
    else:
        raise ValueError("mode must be smoke or formal")
    return tuple(
        EpisodeSpec(policy, profile, seed)
        for policy in POLICIES
        for profile in PROFILES
        for seed in seeds
    )


def physical_validation_matrix() -> tuple[EpisodeSpec, ...]:
    """Return the frozen 3 × 4 × 5 skid-steer validation matrix."""
    return tuple(
        EpisodeSpec(policy, profile, seed)
        for policy in PHYSICAL_POLICIES
        for profile in PHYSICAL_PROFILES
        for seed in PHYSICAL_SEEDS
    )


def _file_sha256(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runner_signature(config: RunnerConfig, spec: EpisodeSpec) -> dict[str, Any]:
    return {
        "schema_version": RUNNER_SCHEMA,
        "mode": config.mode,
        "runtime": config.runtime,
        "motion_backend": config.motion_backend,
        "device": config.device,
        "calibration_path": (
            str(config.calibration.resolve()) if config.calibration else None
        ),
        "calibration_sha256": _file_sha256(config.calibration),
        "python": config.python,
        "entrypoint": str(config.entrypoint.resolve()),
        "policy": spec.policy,
        "profile": spec.profile,
        "seed": spec.seed,
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _episode_matches(
    payload: dict[str, Any], signature: dict[str, Any], spec: EpisodeSpec
) -> bool:
    if payload.get("schema_version") != EPISODE_SCHEMA:
        return False
    if payload.get("experiment_runner") != signature:
        return False
    configuration = payload.get("configuration")
    scenario = payload.get("scenario")
    if not isinstance(configuration, dict) or not isinstance(scenario, dict):
        return False
    oracle_context = scenario.get("oracle_context")
    if not isinstance(oracle_context, dict):
        return False
    if configuration.get("policy") != spec.policy:
        return False
    if oracle_context.get("profile") != spec.profile or oracle_context.get("seed") != spec.seed:
        return False
    if not isinstance(payload.get("metrics"), dict):
        return False
    if not isinstance(payload.get("outcome"), dict):
        return False
    return True


def is_complete(path: Path, config: RunnerConfig, spec: EpisodeSpec) -> bool:
    payload = _read_json(path)
    return payload is not None and _episode_matches(
        payload, runner_signature(config, spec), spec
    )


def _validate_child_result(
    payload: dict[str, Any], config: RunnerConfig, spec: EpisodeSpec
) -> str | None:
    if payload.get("schema_version") != EPISODE_SCHEMA:
        return f"episode schema must be {EPISODE_SCHEMA}"
    configuration = payload.get("configuration")
    scenario = payload.get("scenario")
    if not isinstance(configuration, dict):
        return "episode configuration is missing"
    if not isinstance(scenario, dict) or not isinstance(
        scenario.get("oracle_context"), dict
    ):
        return "episode scenario oracle record is missing"
    oracle_context = scenario["oracle_context"]
    if configuration.get("policy") != spec.policy:
        return "episode policy does not match the requested job"
    if oracle_context.get("profile") != spec.profile:
        return "episode profile does not match the requested job"
    if oracle_context.get("seed") != spec.seed:
        return "episode seed does not match the requested job"
    if configuration.get("runtime") != config.runtime:
        return "episode runtime does not match the requested job"
    expected_motion = (
        "kinematic-ci" if config.runtime == "synthetic" else config.motion_backend
    )
    if configuration.get("motion_backend") != expected_motion:
        return "episode motion backend does not match the requested job"
    if not isinstance(payload.get("metrics"), dict):
        return "episode metrics are missing"
    if not isinstance(payload.get("outcome"), dict):
        return "episode outcome is missing"
    return None


def _command(
    config: RunnerConfig, spec: EpisodeSpec, temporary_output: Path
) -> list[str]:
    command = [
        config.python,
        str(config.entrypoint),
        "--policy",
        spec.policy,
        "--profile",
        spec.profile,
        "--seed",
        str(spec.seed),
        "--runtime",
        config.runtime,
        "--json-output",
        str(temporary_output),
    ]
    if config.runtime == "genesis":
        command.extend(["--motion-backend", config.motion_backend])
    if config.calibration is not None:
        command.extend(["--calibration", str(config.calibration)])
    elif config.runtime == "genesis":
        command.append("--allow-smoke-calibration")
    if config.device:
        command.extend(["--device", config.device])
    return command


def _error_payload(
    *,
    config: RunnerConfig,
    spec: EpisodeSpec,
    command: list[str],
    returncode: int | None,
    reason: str,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": ERROR_SCHEMA,
        "runner": runner_signature(config, spec),
        "reason": reason,
        "returncode": returncode,
        "command": command,
        "stdout_tail": stdout[-8000:],
        "stderr_tail": stderr[-8000:],
        "recorded_unix_time": time.time(),
    }


def run_job(config: RunnerConfig, spec: EpisodeSpec) -> JobResult:
    """Run one isolated episode; never replace a success with an error."""
    raw_dir = config.output_dir / "raw"
    error_dir = config.output_dir / "errors"
    output_path = raw_dir / f"{spec.stem}.json"
    error_path = error_dir / f"{spec.stem}.error.json"
    signature = runner_signature(config, spec)
    if is_complete(output_path, config, spec):
        return JobResult(spec, "skipped", output_path, message="complete matching result")

    raw_dir.mkdir(parents=True, exist_ok=True)
    temporary_output = raw_dir / f".{spec.stem}.child-{os.getpid()}.json"
    try:
        temporary_output.unlink(missing_ok=True)
        command = _command(config, spec, temporary_output)
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            _atomic_json(
                error_path,
                _error_payload(
                    config=config,
                    spec=spec,
                    command=command,
                    returncode=completed.returncode,
                    reason="episode_subprocess_failed",
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                ),
            )
            return JobResult(
                spec,
                "error",
                output_path,
                error_path,
                f"subprocess exited {completed.returncode}",
            )
        payload = _read_json(temporary_output)
        reason = (
            "child did not produce valid JSON"
            if payload is None
            else _validate_child_result(payload, config, spec)
        )
        if reason is not None:
            _atomic_json(
                error_path,
                _error_payload(
                    config=config,
                    spec=spec,
                    command=command,
                    returncode=completed.returncode,
                    reason=reason,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                ),
            )
            return JobResult(spec, "error", output_path, error_path, reason)

        assert payload is not None
        payload["experiment_runner"] = signature
        _atomic_json(temporary_output, payload)
        # The final replacement happens only after schema/config validation.
        os.replace(temporary_output, output_path)
        return JobResult(spec, "completed", output_path)
    finally:
        temporary_output.unlink(missing_ok=True)


def append_progress(path: Path, result: JobResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "unix_time": time.time(),
        "status": result.status,
        "policy": result.spec.policy,
        "profile": result.spec.profile,
        "seed": result.spec.seed,
        "output": str(result.output_path),
        "error": str(result.error_path) if result.error_path else None,
        "message": result.message,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--runtime", choices=("synthetic", "genesis"), default="synthetic")
    parser.add_argument(
        "--motion",
        "--motion-backend",
        dest="motion_backend",
        choices=("kinematic", "skid-steer"),
        default="kinematic",
    )
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--device")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--entrypoint",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "look_twice_v4.py",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RunnerConfig:
    return RunnerConfig(
        mode=args.mode,
        runtime=args.runtime,
        motion_backend=args.motion_backend,
        calibration=args.calibration,
        device=args.device,
        output_dir=args.output_dir,
        python=args.python,
        entrypoint=args.entrypoint,
    )


def run_matrix(config: RunnerConfig, specs: Iterable[EpisodeSpec]) -> dict[str, int]:
    counts = {"completed": 0, "skipped": 0, "error": 0}
    progress_path = config.output_dir / "progress.log"
    for index, spec in enumerate(specs, start=1):
        result = run_job(config, spec)
        counts[result.status] += 1
        append_progress(progress_path, result)
        print(
            f"[{index}] {result.status}: {spec.policy} {spec.profile} seed={spec.seed}",
            flush=True,
        )
    _atomic_json(
        config.output_dir / "run_summary.json",
        {
            "schema_version": "look-twice.experiment-summary/v4",
            "runner_configuration": {
                **asdict(config),
                "calibration": str(config.calibration) if config.calibration else None,
                "output_dir": str(config.output_dir),
                "entrypoint": str(config.entrypoint),
            },
            "counts": counts,
        },
    )
    return counts


def main(argv: Iterable[str] | None = None) -> int:
    try:
        config = config_from_args(parse_args(argv))
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    matrix = experiment_matrix(config.mode)
    counts = run_matrix(config, matrix)
    print(
        "finished:",
        f"completed={counts['completed']}",
        f"skipped={counts['skipped']}",
        f"error={counts['error']}",
    )
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
