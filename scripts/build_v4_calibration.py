#!/usr/bin/env python3
"""从严格隔离的 v4 JSONL calibration split 构建 Conformal Artifact。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from v4_claims import canonical_json
from v4_conformal import CalibrationSample, fit_class_conditional_calibration
from v4_scenario import PROFILES


STANDARD_SEEDS = frozenset(range(30000, 30050))
STANDARD_PROFILES = tuple(profile for profile in PROFILES if profile != "ood-severity")
REQUIRED_FIELDS = (
    "seed",
    "profile",
    "noise_intensity",
    "sensor_version",
    "true_label",
    "p_clear",
)


def read_samples(path: Path) -> list[CalibrationSample]:
    samples: list[CalibrationSample] = []
    seen_pairs: set[tuple[str, int]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: each line must be a JSON object")
            missing = [field for field in REQUIRED_FIELDS if field not in payload]
            if missing:
                raise ValueError(f"{path}:{line_number}: missing fields {missing}")
            if isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int):
                raise ValueError(f"{path}:{line_number}: seed must be an integer")
            pair = (str(payload["profile"]), payload["seed"])
            if pair in seen_pairs:
                raise ValueError(
                    f"{path}:{line_number}: duplicate profile/seed pair {pair}"
                )
            seen_pairs.add(pair)
            try:
                samples.append(
                    CalibrationSample(
                        seed=payload["seed"],
                        profile=str(payload["profile"]),
                        noise_intensity=float(payload["noise_intensity"]),
                        sensor_version=str(payload["sensor_version"]),
                        true_label=str(payload["true_label"]),
                        p_clear=float(payload["p_clear"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not samples:
        raise ValueError(f"{path}: no calibration samples found")
    return samples


def validate_standard_split(samples: list[CalibrationSample]) -> None:
    actual_profiles = {sample.profile for sample in samples}
    actual_seeds = {sample.seed for sample in samples}
    if "ood-severity" in actual_profiles:
        raise ValueError("ood-severity is reserved for locked OOD evaluation")
    if actual_profiles != set(STANDARD_PROFILES):
        missing = sorted(set(STANDARD_PROFILES) - actual_profiles)
        extra = sorted(actual_profiles - set(STANDARD_PROFILES))
        raise ValueError(f"nonstandard calibration profiles: missing={missing}, extra={extra}")
    if actual_seeds != STANDARD_SEEDS:
        missing = sorted(STANDARD_SEEDS - actual_seeds)
        extra = sorted(actual_seeds - STANDARD_SEEDS)
        raise ValueError(f"nonstandard calibration seeds: missing={missing}, extra={extra}")
    actual_pairs = {(sample.profile, sample.seed) for sample in samples}
    expected_pairs = {
        (profile, seed) for profile in STANDARD_PROFILES for seed in STANDARD_SEEDS
    }
    if actual_pairs != expected_pairs or len(samples) != len(expected_pairs):
        missing = sorted(expected_pairs - actual_pairs)
        extra = sorted(actual_pairs - expected_pairs)
        raise ValueError(
            "calibration split must contain exactly one record per profile/seed: "
            f"missing={missing[:5]}, extra={extra[:5]}, rows={len(samples)}"
        )


def current_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Calibration JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--git-commit", default=None)
    parser.add_argument(
        "--allow-nonstandard-split",
        action="store_true",
        help="Testing only: bypass the official 7 profiles × seeds 30000–30049 check",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        samples = read_samples(args.input)
        if not args.allow_nonstandard_split:
            validate_standard_split(samples)
        else:
            print("WARNING: building a nonstandard testing artifact", file=sys.stderr)
        artifact = fit_class_conditional_calibration(
            samples,
            alpha=args.alpha,
            git_commit=args.git_commit or current_git_commit(),
        )
        atomic_write(args.output, artifact.to_wire())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"calibration build failed: {exc}") from exc
    print(f"calibration rows: {len(samples)}")
    print(f"artifact: {args.output}")
    print(f"artifact id: {artifact.artifact_id}")
    print(f"artifact sha256: {artifact.sha256}")


if __name__ == "__main__":
    main()
