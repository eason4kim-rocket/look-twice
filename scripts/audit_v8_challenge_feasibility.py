#!/usr/bin/env python3
"""Post-hoc offline feasibility audit for the archived V8 challenge.

This script is deliberately read-only.  It streams active episode JSON records
from the raw ``tar.gz`` archive, reads archived oracle state only for offline
classification, and never runs or modifies the policy, runner, or validator.

The resulting 30/30 feasibility-consistency statistic is a descriptive,
post-hoc secondary audit.  It does not replace or relabel the preregistered
primary active direct-route result, which remains 29/30 (96.7%).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "look-twice.v8-frozen-challenge-feasibility-audit/v1"
EPISODE_SCHEMA_VERSION = "look-twice.episode/v7"
ACTIVE_POLICY = "purify-active-vision"
PROFILE = "independent-noise"
SEED_START = 102500
SEED_END = 102529
EXPECTED_SEEDS = tuple(range(SEED_START, SEED_END + 1))
CORRIDORS = ("corridor_a", "corridor_b")
ACTIVE_EPISODE_RE = re.compile(
    r"(?:^|/)episodes/active__independent-noise__(\d+)\.json$"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object")
    return value


def _boolean(value: Any, context: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{context} must be a boolean")
    return value


def _nonnegative_integer(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value


def classify_episode(episode: Mapping[str, Any], *, member_seed: int | None = None) -> dict[str, Any]:
    """Classify one archived active episode against its oracle feasibility.

    ``oracle_context`` is consulted only by this offline function.  The function
    does not execute the runtime policy or infer a counterfactual route.
    """

    if episode.get("schema_version") != EPISODE_SCHEMA_VERSION:
        raise ValueError("episode schema_version mismatch")

    scenario = _mapping(episode.get("scenario"), "scenario")
    seed = scenario.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("scenario.seed must be an integer")
    if member_seed is not None and seed != member_seed:
        raise ValueError(
            f"archive member seed {member_seed} disagrees with scenario.seed {seed}"
        )
    if scenario.get("profile") != PROFILE:
        raise ValueError(f"seed {seed}: scenario profile mismatch")

    configuration = _mapping(episode.get("configuration"), "configuration")
    if configuration.get("policy") != ACTIVE_POLICY:
        raise ValueError(f"seed {seed}: configuration is not the active policy")

    metrics = _mapping(episode.get("metrics"), "metrics")
    if metrics.get("policy") != ACTIVE_POLICY:
        raise ValueError(f"seed {seed}: metrics policy mismatch")

    oracle = _mapping(scenario.get("oracle_context"), "scenario.oracle_context")
    external_event_present = oracle.get("external_event") is not None
    blocked = {
        corridor: _boolean(
            oracle.get(f"{corridor}_blocked_initial"),
            f"seed {seed}: oracle {corridor} blocked flag",
        )
        for corridor in CORRIDORS
    }
    clear_corridors = [corridor for corridor in CORRIDORS if not blocked[corridor]]
    blocked_corridors = [corridor for corridor in CORRIDORS if blocked[corridor]]

    route_mode = metrics.get("route_mode")
    if route_mode not in {"direct", "detour"}:
        raise ValueError(f"seed {seed}: unsupported route_mode {route_mode!r}")
    used_detour = _boolean(metrics.get("used_detour"), f"seed {seed}: used_detour")
    selected_corridor = metrics.get("selected_corridor")
    if selected_corridor is not None and selected_corridor not in CORRIDORS:
        raise ValueError(f"seed {seed}: invalid selected_corridor {selected_corridor!r}")

    mission_success = _boolean(
        metrics.get("mission_success"), f"seed {seed}: mission_success"
    )
    unsafe_crossing = _boolean(
        metrics.get("unsafe_crossing"), f"seed {seed}: unsafe_crossing"
    )
    collision_count = _nonnegative_integer(
        metrics.get("collision_count"), f"seed {seed}: collision_count"
    )
    fallback_used = _boolean(
        metrics.get("fallback_used"), f"seed {seed}: fallback_used"
    )
    selected_corridor_oracle_blocked = metrics.get(
        "selected_corridor_oracle_blocked"
    )
    if selected_corridor is None:
        if selected_corridor_oracle_blocked is not None:
            raise ValueError(
                f"seed {seed}: a null selected_corridor must have a null "
                "selected_corridor_oracle_blocked"
            )
    elif type(selected_corridor_oracle_blocked) is not bool:
        raise ValueError(
            f"seed {seed}: selected_corridor_oracle_blocked must be a boolean"
        )

    direct_route = route_mode == "direct"
    route_encoding_consistent = (direct_route and not used_detour) or (
        route_mode == "detour" and used_detour
    )
    safe_mission_outcome = (
        mission_success
        and not unsafe_crossing
        and collision_count == 0
        and not fallback_used
    )

    oracle_clear_world = bool(clear_corridors)
    both_blocked_world = not oracle_clear_world
    oracle_clear_direct_and_selected_clear = (
        oracle_clear_world
        and direct_route
        and route_encoding_consistent
        and selected_corridor in clear_corridors
        and selected_corridor_oracle_blocked is False
    )
    both_blocked_safe_detour = (
        both_blocked_world
        and route_mode == "detour"
        and route_encoding_consistent
        and selected_corridor is None
        and safe_mission_outcome
    )
    route_choice_feasibility_consistent = (
        oracle_clear_direct_and_selected_clear or both_blocked_safe_detour
    )
    offline_feasibility_consistent_route_outcome = (
        route_choice_feasibility_consistent and safe_mission_outcome
    )

    if offline_feasibility_consistent_route_outcome:
        classification = (
            "oracle_clear_direct_selected_clear"
            if oracle_clear_world
            else "both_blocked_safe_detour"
        )
    else:
        classification = "feasibility_inconsistent"

    return {
        "seed": seed,
        "oracle_clear_corridors": clear_corridors,
        "oracle_blocked_corridors": blocked_corridors,
        "oracle_clear_world": oracle_clear_world,
        "both_blocked_world": both_blocked_world,
        "external_event_present": external_event_present,
        "selected_corridor": selected_corridor,
        "selected_corridor_oracle_blocked": selected_corridor_oracle_blocked,
        "route_mode": route_mode,
        "used_detour": used_detour,
        "mission_success": mission_success,
        "unsafe_crossing": unsafe_crossing,
        "collision_count": collision_count,
        "fallback_used": fallback_used,
        "direct_route_primary_observation": direct_route,
        "route_encoding_consistent": route_encoding_consistent,
        "safe_mission_outcome": safe_mission_outcome,
        "oracle_clear_direct_and_selected_clear": (
            oracle_clear_direct_and_selected_clear
        ),
        "both_blocked_safe_detour": both_blocked_safe_detour,
        "route_choice_feasibility_consistent": (
            route_choice_feasibility_consistent
        ),
        "offline_feasibility_consistent_route_outcome": (
            offline_feasibility_consistent_route_outcome
        ),
        "classification": classification,
    }


def stream_active_episodes(archive_path: Path) -> list[dict[str, Any]]:
    """Read exactly the archived active seed suite without extracting files."""

    if not archive_path.is_file():
        raise ValueError(f"archive not found: {archive_path}")

    episodes: dict[int, dict[str, Any]] = {}
    try:
        with tarfile.open(archive_path, mode="r|gz") as archive:
            for member in archive:
                match = ACTIVE_EPISODE_RE.search(member.name)
                if match is None:
                    continue
                if not member.isfile():
                    raise ValueError(f"active episode member is not a file: {member.name}")
                member_seed = int(match.group(1))
                if member_seed in episodes:
                    raise ValueError(f"duplicate active episode seed: {member_seed}")
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError(f"unable to read active episode: {member.name}")
                try:
                    payload = json.load(handle)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid active episode JSON for seed {member_seed}: "
                        f"{exc.__class__.__name__}"
                    ) from exc
                episodes[member_seed] = classify_episode(
                    _mapping(payload, f"seed {member_seed} episode"),
                    member_seed=member_seed,
                )
    except (tarfile.TarError, OSError) as exc:
        raise ValueError(f"unable to stream archive: {exc}") from exc

    observed = set(episodes)
    expected = set(EXPECTED_SEEDS)
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise ValueError(
            "active episode seed set mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return [episodes[seed] for seed in EXPECTED_SEEDS]


def _count(rows: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(row.get(key) is True for row in rows)


def _fraction(count: int, denominator: int) -> dict[str, Any]:
    return {
        "count": count,
        "denominator": denominator,
        "percent": 100.0 * count / denominator,
    }


def build_audit(archive_path: Path) -> dict[str, Any]:
    rows = stream_active_episodes(archive_path)
    total = len(rows)
    direct_count = _count(rows, "direct_route_primary_observation")
    oracle_clear_count = _count(rows, "oracle_clear_world")
    both_blocked_count = _count(rows, "both_blocked_world")
    clear_consistent_count = _count(
        rows, "oracle_clear_direct_and_selected_clear"
    )
    blocked_detour_count = _count(rows, "both_blocked_safe_detour")
    feasibility_consistent_count = _count(
        rows, "offline_feasibility_consistent_route_outcome"
    )
    unsafe_count = _count(rows, "unsafe_crossing")
    fallback_count = _count(rows, "fallback_used")
    external_event_count = _count(rows, "external_event_present")
    collision_episode_count = sum(int(row["collision_count"]) > 0 for row in rows)
    collision_event_count = sum(int(row["collision_count"]) for row in rows)
    mission_success_count = _count(rows, "mission_success")

    checks = {
        "exact_active_seed_set_102500_through_102529": [
            row["seed"] for row in rows
        ]
        == list(EXPECTED_SEEDS),
        "active_episode_count_is_30": total == 30,
        "preregistered_primary_direct_route_remains_29_of_30": (
            direct_count == 29
        ),
        "oracle_clear_world_count_is_29": oracle_clear_count == 29,
        "all_oracle_clear_worlds_are_direct_and_select_oracle_clear": (
            clear_consistent_count == oracle_clear_count == 29
        ),
        "both_blocked_world_count_is_1": both_blocked_count == 1,
        "both_blocked_world_is_seed_102515": [
            row["seed"] for row in rows if row["both_blocked_world"]
        ]
        == [102515],
        "both_blocked_world_uses_safe_detour": (
            blocked_detour_count == both_blocked_count == 1
        ),
        "all_30_route_outcomes_are_offline_feasibility_consistent": (
            feasibility_consistent_count == total == 30
        ),
        "zero_unsafe_crossings": unsafe_count == 0,
        "zero_fallbacks": fallback_count == 0,
        "no_external_events_in_this_fixed_archive": external_event_count == 0,
        "zero_collision_episodes_and_events": (
            collision_episode_count == collision_event_count == 0
        ),
        "all_30_missions_succeeded": mission_success_count == total == 30,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if all(checks.values()) else "failed",
        "evidence_boundary": {
            "analysis_type": "post-hoc descriptive offline feasibility audit",
            "post_hoc": True,
            "descriptive_only": True,
            "secondary_not_preregistered_endpoint": True,
            "oracle_use": (
                "Archived oracle_context is read only after runtime completion "
                "for this offline classification; this audit does not execute "
                "or alter the runtime policy."
            ),
            "oracle_used_by_this_artifact_only_for_offline_classification": True,
            "does_not_replace_preregistered_primary_endpoint": True,
            "does_not_relabel_detour_as_direct": True,
            "preregistered_primary_result_must_remain": "29/30 direct (96.7%)",
            "prohibited_interpretation": (
                "30/30 feasibility-consistent is not a 30/30 direct-route score, "
                "not a preregistered endpoint, and not evidence of real-world or "
                "out-of-distribution generalization."
            ),
        },
        "source": {
            "archive_input_basename": archive_path.name,
            "archive_sha256": file_sha256(archive_path),
            "archive_bytes": archive_path.stat().st_size,
            "archive_read_mode": "streaming tar r|gz",
            "archive_extracted": False,
            "active_episode_records_read": total,
            "model_inference_run": False,
            "episode_rerun": False,
            "runner_or_validator_modified": False,
        },
        "scope": {
            "policy": ACTIVE_POLICY,
            "profile": PROFILE,
            "seed_start": SEED_START,
            "seed_end": SEED_END,
            "expected_seed_count": len(EXPECTED_SEEDS),
            "observed_seeds": [row["seed"] for row in rows],
        },
        "definitions": {
            "oracle_clear_direct_and_selected_oracle_clear": (
                "At least one corridor is oracle-clear; archived route_mode is "
                "direct, used_detour is false, and selected_corridor is one of "
                "the oracle-clear corridors, with the archived selected-corridor "
                "oracle flag also false."
            ),
            "both_blocked_safe_detour": (
                "Both corridors are oracle-blocked; archived route_mode is "
                "detour, used_detour is true, no corridor is selected for "
                "crossing, the mission succeeds, and unsafe/collision/fallback "
                "counts are zero."
            ),
            "offline_feasibility_consistent_route_outcome": (
                "The archived route choice matches one of the two definitions "
                "above and completes the mission with zero unsafe crossings "
                "and zero collisions or fallbacks."
            ),
        },
        "summary": {
            "preregistered_primary_active_direct_route": {
                **_fraction(direct_count, total),
                "unchanged": True,
            },
            "oracle_clear_worlds": _fraction(oracle_clear_count, total),
            "oracle_clear_direct_and_selected_oracle_clear": _fraction(
                clear_consistent_count, oracle_clear_count
            ),
            "both_blocked_worlds": _fraction(both_blocked_count, total),
            "both_blocked_safe_detour": _fraction(
                blocked_detour_count, both_blocked_count
            ),
            "offline_feasibility_consistent_route_outcomes": _fraction(
                feasibility_consistent_count, total
            ),
            "mission_success": _fraction(mission_success_count, total),
            "unsafe_crossing": _fraction(unsafe_count, total),
            "fallback_used": _fraction(fallback_count, total),
            "external_event_present": _fraction(external_event_count, total),
            "collision_episodes": _fraction(collision_episode_count, total),
            "collision_events": collision_event_count,
        },
        "checks": checks,
        "episodes": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="raw V8 challenge tar.gz archive")
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json"
        ),
        help="derived JSON report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_audit(args.archive)
    except ValueError as exc:
        raise SystemExit(f"feasibility audit failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"status={report['status']}")
    print(f"output={args.output}")
    print(f"output_sha256={file_sha256(args.output)}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
