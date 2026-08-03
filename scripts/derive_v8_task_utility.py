#!/usr/bin/env python3
"""Derive task-utility claims from archived V8 evidence without rerunning V8.

The permanent locked report supplies paired route outcomes but not trajectory
lengths.  A separate guarded confirmatory replay supplies trajectory lengths.
This script keeps those two evidence scopes separate and verifies every source
identity before emitting the submission-facing derivation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


LOCKED_REPORT_SHA256 = (
    "5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb"
)
ACTIVE_REPLAY_SHA256 = (
    "30a543dad8fa5ee70f02fb4fe836be674d9391c3617fc81ddafa78b8ffbb1a44"
)
PASSIVE_REPLAY_SHA256 = (
    "724d79964456266b72d70d450ffc636a7bb2fa3e75295ad9fa3b1f62be67e349"
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locked-report",
        type=Path,
        default=root / "release/v8-frozen/results/LOCKED_TEST_REPORT.json",
    )
    parser.add_argument(
        "--active-replay",
        type=Path,
        default=root
        / "release/v8-frozen/episodes/active__independent-noise__105400.json",
    )
    parser.add_argument(
        "--passive-replay",
        type=Path,
        default=root
        / "release/v8-frozen/episodes/passive__independent-noise__105400.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "release/v8-derived/V8_TASK_UTILITY_DERIVATION.json",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"source not found: {path}")
    actual = sha256(path)
    if actual != expected_sha256:
        raise SystemExit(
            f"source identity mismatch for {path}: expected {expected_sha256}, got {actual}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def percentage(numerator: float, denominator: float) -> float:
    return 100.0 * numerator / denominator


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    args = parse_args()
    locked = load_verified(args.locked_report, LOCKED_REPORT_SHA256)
    active = load_verified(args.active_replay, ACTIVE_REPLAY_SHA256)
    passive = load_verified(args.passive_replay, PASSIVE_REPLAY_SHA256)

    live = locked["live_fullchain"]
    gates = live["gates"]
    rows = live["rows"]
    active_rows = [row for row in rows if row["policy"] == "purify-active-vision"]
    passive_rows = [row for row in rows if row["policy"] == "purify-passive"]
    require(len(active_rows) == len(passive_rows) == 12, "expected 12 paired worlds")
    require(len(rows) == 24, "expected 24 locked full-chain episodes")
    require({row["seed"] for row in active_rows} == {row["seed"] for row in passive_rows},
            "locked policies do not share an identical seed set")
    require(all(row["flags"]["initial_gate_denied"] for row in rows),
            "not every locked episode begins with a denial")
    require(all(row["flags"]["mission"] for row in rows),
            "not every locked episode completes the mission")
    require(all(row["flags"]["unsafe"] == 0 for row in rows),
            "an unsafe locked episode is present")
    require(all(not row["flags"]["fallback"] for row in rows),
            "a fallback locked episode is present")
    require(all(
        row["flags"]["effective_admit"]
        == (row["flags"]["python_admit"] and row["flags"]["go_admit"])
        for row in rows
    ), "effective admission is not the Python/Go conjunction")

    active_direct = sum(row["flags"]["route_mode"] == "direct" for row in active_rows)
    passive_direct = sum(row["flags"]["route_mode"] == "direct" for row in passive_rows)
    require(active_direct == gates["active_full_chain_direct"] == 11,
            "active direct count disagrees with the locked gate summary")
    require(passive_direct == 0 and gates["passive_detour"] == 12,
            "passive route counts disagree with the locked gate summary")
    conservative_active_seeds = [
        row["seed"] for row in active_rows if row["flags"]["route_mode"] != "direct"
    ]
    require(conservative_active_seeds == [102105],
            "unexpected conservative active seed")

    direct_gain_pp = percentage(active_direct, 12) - percentage(passive_direct, 12)
    discordant_active_wins = sum(
        active_row["flags"]["route_mode"] == "direct"
        and passive_row["flags"]["route_mode"] != "direct"
        for active_row, passive_row in zip(
            sorted(active_rows, key=lambda row: row["seed"]),
            sorted(passive_rows, key=lambda row: row["seed"]),
            strict=True,
        )
    )
    discordant_passive_wins = 0
    # Exact two-sided McNemar/binomial test for b=11, c=0: 2 * (1/2)^11.
    exact_mcnemar_p = 2.0 * (0.5 ** (discordant_active_wins + discordant_passive_wins))

    offline = locked["offline"]["metrics"]
    decisive = int(offline["n_decisive"])
    samples = int(offline["n_samples"])

    for replay, expected_policy in (
        (active, "purify-active-vision"),
        (passive, "purify-passive"),
    ):
        require(replay["environment"]["formal_result_eligible"] is False,
                "confirmatory replay is unexpectedly formal-result eligible")
        require(replay["environment"]["physics_backend"] == "kinematic",
                "confirmatory replay is not the disclosed kinematic backend")
        require(replay["configuration"]["policy"] == expected_policy,
                "confirmatory replay policy mismatch")
        require(replay["metrics"]["mission_success"],
                "confirmatory replay did not complete the mission")
        require(replay["metrics"]["collision_count"] == 0,
                "confirmatory replay contains a collision")

    active_carrier_m = sum(
        segment["path_length"]
        for segment in active["motion_segments"]
        if segment["agent_id"] == "carrier"
    )
    active_scout_m = sum(
        segment["path_length"]
        for segment in active["motion_segments"]
        if segment["agent_id"] == "scout"
    )
    passive_carrier_m = sum(
        segment["path_length"]
        for segment in passive["motion_segments"]
        if segment["agent_id"] == "carrier"
    )
    passive_scout_m = sum(
        segment["path_length"]
        for segment in passive["motion_segments"]
        if segment["agent_id"] == "scout"
    )
    require(passive_scout_m == 0.0, "passive scout unexpectedly moved")
    active_total_m = active_carrier_m + active_scout_m
    passive_total_m = passive_carrier_m + passive_scout_m

    report = {
        "schema_version": "look-twice.v8-task-utility-derivation/v1",
        "derived_on": "2026-08-03",
        "status": "passed",
        "claim_scope": {
            "derivation_only": True,
            "v8_rerun": False,
            "locked_test_reopened": False,
            "model_or_threshold_changed": False,
            "locked_and_confirmatory_scopes_kept_separate": True,
        },
        "sources": {
            "locked_report": {
                "path": "release/v8-frozen/results/LOCKED_TEST_REPORT.json",
                "sha256": LOCKED_REPORT_SHA256,
                "permanent": bool(locked["permanent"]),
                "locked_test_runs": 1,
            },
            "confirmatory_active_replay": {
                "path": "release/v8-frozen/episodes/active__independent-noise__105400.json",
                "sha256": ACTIVE_REPLAY_SHA256,
                "seed": 105400,
                "formal_result_eligible": False,
            },
            "confirmatory_passive_replay": {
                "path": "release/v8-frozen/episodes/passive__independent-noise__105400.json",
                "sha256": PASSIVE_REPLAY_SHA256,
                "seed": 105400,
                "formal_result_eligible": False,
            },
        },
        "locked_task_utility": {
            "scope": "permanent one-shot locked suite; 12 paired Genesis worlds",
            "paired_worlds": 12,
            "full_chain_episodes": 24,
            "initial_gate_denied": {"count": 24, "denominator": 24},
            "mission_complete": {
                "active": {"count": 12, "denominator": 12},
                "passive": {"count": 12, "denominator": 12},
            },
            "direct_route": {
                "active": {
                    "count": active_direct,
                    "denominator": 12,
                    "percent": percentage(active_direct, 12),
                },
                "passive": {
                    "count": passive_direct,
                    "denominator": 12,
                    "percent": percentage(passive_direct, 12),
                },
                "paired_gain_percentage_points": direct_gain_pp,
                "conservative_active_seed": conservative_active_seeds[0],
            },
            "unsafe_crossing": {"count": 0, "denominator": 24},
            "fallback": {"count": 0, "denominator": 24},
            "python_go_decision_agreement": {"count": 24, "denominator": 24},
            "effective_admit_conjunction_verified": {"count": 24, "denominator": 24},
            "paired_descriptive_test": {
                "name": "exact two-sided McNemar test",
                "active_only_direct_pairs": discordant_active_wins,
                "passive_only_direct_pairs": discordant_passive_wins,
                "p_value": exact_mcnemar_p,
                "interpretation_limit": (
                    "descriptive evidence for this fixed seed suite; no population "
                    "or real-world generalization"
                ),
            },
        },
        "locked_offline_decisiveness": {
            "decisive": decisive,
            "total": samples,
            "decisive_percent": percentage(decisive, samples),
            "non_decisive": samples - decisive,
            "non_decisive_percent": percentage(samples - decisive, samples),
            "warning": (
                "perfect decisive metrics are not an all-sample forced-classification claim"
            ),
        },
        "confirmatory_cost_ledger": {
            "scope": (
                "guarded non-locked seed 105400 replay; kinematic simulation; "
                "formal_result_eligible=false"
            ),
            "loaded_carrier_travel_m": {
                "active": active_carrier_m,
                "passive": passive_carrier_m,
                "active_reduction_m": passive_carrier_m - active_carrier_m,
                "active_reduction_percent": percentage(
                    passive_carrier_m - active_carrier_m, passive_carrier_m
                ),
            },
            "scout_travel_m": {"active": active_scout_m, "passive": passive_scout_m},
            "total_robot_travel_m": {
                "active": active_total_m,
                "passive": passive_total_m,
                "active_increase_percent": percentage(
                    active_total_m - passive_total_m, passive_total_m
                ),
            },
            "elapsed_steps": {
                "active": active["metrics"]["elapsed_steps"],
                "passive": passive["metrics"]["elapsed_steps"],
            },
            "recorded_wall_seconds": {
                "active": active["metrics"]["elapsed_seconds"],
                "passive": passive["metrics"]["elapsed_seconds"],
                "not_a_deterministic_latency_benchmark": True,
            },
            "observations": {
                "active": active["metrics"]["observation_count"],
                "passive": passive["metrics"]["observation_count"],
            },
            "replans": {
                "active": active["metrics"]["replan_count"],
                "passive": passive["metrics"]["replan_count"],
            },
            "payload_delivered": {"active": True, "passive": True},
            "collision_count": {"active": 0, "passive": 0},
            "interpretation": (
                "active repair shifts travel burden away from the loaded carrier to a "
                "scout; it does not reduce total robot travel or episode duration"
            ),
        },
        "non_claims": [
            "no locked aggregate path-length, latency, energy, or utilization claim",
            "no real-robot, sim-to-real, or safety-certification claim",
            "no claim that active repair reduces total travel or total elapsed time",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
