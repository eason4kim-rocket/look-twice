#!/usr/bin/env python3
"""Build the formal learned RGB-D Gate calibration artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v4_conformal import CalibrationSample, fit_class_conditional_calibration
from v5_rgbd_claims import LEARNED_RGBD_SENSOR_VERSION


PROFILES = {
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "dynamic-change",
    "repair-required",
}
SEEDS = set(range(30000, 30050))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pairs = {(str(row["source_profile"]), int(row["seed"])) for row in rows}
    expected = {(profile, seed) for profile in PROFILES for seed in SEEDS}
    if len(rows) != len(expected) or pairs != expected:
        raise SystemExit(
            f"expected exactly {len(expected)} profile/seed rows; got {len(rows)}"
        )
    if {row["sensor_version"] for row in rows} != {
        LEARNED_RGBD_SENSOR_VERSION
    }:
        raise SystemExit("learned Gate sensor version mismatch")
    samples = [
        CalibrationSample(
            seed=int(row["seed"]),
            profile=str(row["profile"]),
            noise_intensity=float(row["noise_intensity"]),
            sensor_version=str(row["sensor_version"]),
            true_label=str(row["true_label"]),
            p_clear=float(row["p_clear"]),
        )
        for row in rows
    ]
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    artifact = fit_class_conditional_calibration(
        samples, git_commit=commit, alpha=args.alpha
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifact.save(args.output)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "class_quantiles": artifact.class_quantiles,
                "sensor_versions": list(artifact.sensor_versions),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
