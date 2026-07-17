#!/usr/bin/env python3
"""Evaluate frozen learned RGB-D promotion gates without tuning the model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MIN_BALANCED_ACCURACY = 0.85
MAX_TEST_BRIER = 0.15
MIN_CONFORMAL_COVERAGE = 0.92  # 1 - alpha - 0.03
MIN_SINGLETON_RATE = 0.50
MIN_SINGLETON_ACCURACY = 0.85


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def evaluate(training: dict[str, Any], conformal: dict[str, Any]) -> dict[str, Any]:
    validation = training["validation"]
    test = training["test"]
    locked = conformal["locked_test"]
    checks = {
        "validation_balanced_accuracy": {
            "required": MIN_BALANCED_ACCURACY,
            "actual": float(validation["balanced_accuracy"]),
            "passed": float(validation["balanced_accuracy"])
            >= MIN_BALANCED_ACCURACY,
        },
        "locked_test_balanced_accuracy": {
            "required": MIN_BALANCED_ACCURACY,
            "actual": float(test["balanced_accuracy"]),
            "passed": float(test["balanced_accuracy"])
            >= MIN_BALANCED_ACCURACY,
        },
        "locked_test_brier": {
            "required_max": MAX_TEST_BRIER,
            "actual": float(test["brier"]),
            "passed": float(test["brier"]) <= MAX_TEST_BRIER,
        },
        "locked_test_coverage": {
            "required": MIN_CONFORMAL_COVERAGE,
            "actual": float(locked["coverage"]),
            "passed": float(locked["coverage"]) >= MIN_CONFORMAL_COVERAGE,
        },
        "locked_test_clear_coverage": {
            "required": MIN_CONFORMAL_COVERAGE,
            "actual": float(locked["clear_coverage"]),
            "passed": float(locked["clear_coverage"])
            >= MIN_CONFORMAL_COVERAGE,
        },
        "locked_test_blocked_coverage": {
            "required": MIN_CONFORMAL_COVERAGE,
            "actual": float(locked["blocked_coverage"]),
            "passed": float(locked["blocked_coverage"])
            >= MIN_CONFORMAL_COVERAGE,
        },
        "locked_test_singleton_rate": {
            "required": MIN_SINGLETON_RATE,
            "actual": float(locked["singleton_rate"]),
            "passed": float(locked["singleton_rate"])
            >= MIN_SINGLETON_RATE,
        },
        "locked_test_singleton_accuracy": {
            "required": MIN_SINGLETON_ACCURACY,
            "actual": float(locked["singleton_accuracy"]),
            "passed": float(locked["singleton_accuracy"])
            >= MIN_SINGLETON_ACCURACY,
        },
        "rocm_training": {
            "required": "cuda device with non-empty ROCm version",
            "actual": {
                "device": training.get("device"),
                "rocm": training.get("rocm"),
                "gpu": training.get("gpu"),
            },
            "passed": str(training.get("device", "")).startswith("cuda")
            and bool(training.get("rocm")),
        },
    }
    candidate = all(bool(item["passed"]) for item in checks.values())
    return {
        "schema_version": "look-twice.learned-rgbd-promotion-gate/v1",
        "model_candidate_eligible": candidate,
        "online_promotion_eligible": False,
        "online_promotion_status": (
            "pending_closed_loop_safety_evaluation"
            if candidate
            else "model_quality_gate_failed"
        ),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-metrics", type=Path, required=True)
    parser.add_argument("--conformal-evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        _load(args.training_metrics), _load(args.conformal_evaluation)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["model_candidate_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
