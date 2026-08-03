#!/usr/bin/env python3
"""Independently verify and recompute the preregistered V8 challenge.

The verifier is deliberately read-only.  It never launches an episode, loads
the checkpoint, retries a failure, or edits a challenge artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREGISTRATION = (
    ROOT
    / "release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json"
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PREREG_SCHEMA = "look-twice.v8-frozen-challenge-preregistration/v1"
RUN_MANIFEST_SCHEMA = "look-twice.v8-frozen-challenge-run-manifest/v1"
TELEMETRY_SCHEMA = "look-twice.v8-frozen-challenge-rocm-telemetry/v1"
REPORT_SCHEMA = "look-twice.v8-frozen-challenge-report/v1"
EPISODE_SCHEMA = "look-twice.episode/v7"

ACTIVE = "purify-active-vision"
PASSIVE = "purify-passive"
POLICIES = (ACTIVE, PASSIVE)
POLICY_LABEL = {ACTIVE: "active", PASSIVE: "passive"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def runtime_source_tree_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = "".join(
        f"{row['sha256']}  {row['path']}\n"
        for row in sorted(rows, key=lambda item: str(item["path"]))
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def expected_runtime_source_closure_record(
    preregistration: Mapping[str, Any]
) -> dict[str, Any]:
    declared = preregistration["identities"]["runtime_source_closure"]
    manifest_path = ROOT / declared["manifest_path"]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    observations = [
        {
            "path": row["path"],
            "size_bytes": (ROOT / row["path"]).stat().st_size,
            "expected_sha256": row["sha256"],
            "observed_sha256": row["sha256"],
            "matched": True,
        }
        for row in payload["files"]
    ]
    return {
        "manifest_path": declared["manifest_path"],
        "manifest_resolved_path": str(manifest_path.resolve()),
        "manifest_sha256_declared": declared["manifest_sha256"],
        "manifest_sha256_observed": declared["manifest_sha256"],
        "manifest_sha256_verified": True,
        "tree_fingerprint_sha256_declared": declared["tree_fingerprint_sha256"],
        "tree_fingerprint_sha256_observed": declared["tree_fingerprint_sha256"],
        "tree_fingerprint_verified": True,
        "file_count_declared": declared["file_count"],
        "file_count_observed": declared["file_count"],
        "python_file_count_declared": declared["python_file_count"],
        "python_file_count_observed": declared["python_file_count"],
        "static_asset_file_count_declared": declared["static_asset_file_count"],
        "static_asset_file_count_observed": declared["static_asset_file_count"],
        "root_entrypoint": declared["root_entrypoint"],
        "exact_python_file_set_required": True,
        "exact_set_verified": True,
        "source_origin_git_commit": declared["source_origin_git_commit"],
        "schema_version": payload["schema_version"],
        "files": observations,
        "import_canary": {
            "expected_module_count": 29,
            "resolved_module_count": 29,
            "all_within_runtime_source_root": True,
            "exact_paths_verified": True,
            "passed": True,
        },
    }


def _validate_runtime_source_closure_record(
    observed: Any,
    preregistration: Mapping[str, Any],
    errors: list[str],
    context: str,
) -> None:
    if not isinstance(observed, dict):
        errors.append(f"{context}_runtime_source_closure_not_object")
        return
    declared = preregistration["identities"]["runtime_source_closure"]
    expected_fields = {
        "manifest_path": declared["manifest_path"],
        "manifest_sha256_declared": declared["manifest_sha256"],
        "manifest_sha256_observed": declared["manifest_sha256"],
        "manifest_sha256_verified": True,
        "tree_fingerprint_sha256_declared": declared["tree_fingerprint_sha256"],
        "tree_fingerprint_sha256_observed": declared["tree_fingerprint_sha256"],
        "tree_fingerprint_verified": True,
        "file_count_declared": declared["file_count"],
        "file_count_observed": declared["file_count"],
        "python_file_count_declared": declared["python_file_count"],
        "python_file_count_observed": declared["python_file_count"],
        "static_asset_file_count_declared": declared["static_asset_file_count"],
        "static_asset_file_count_observed": declared["static_asset_file_count"],
        "root_entrypoint": declared["root_entrypoint"],
        "exact_python_file_set_required": True,
        "exact_set_verified": True,
        "source_origin_git_commit": declared["source_origin_git_commit"],
        "schema_version": "look-twice.v8-challenge-runtime-dependency-manifest/v1",
    }
    for key, value in expected_fields.items():
        if observed.get(key) != value:
            errors.append(f"{context}_runtime_source_closure_{key}_mismatch")
    rows = observed.get("files")
    if not isinstance(rows, list) or len(rows) != 30:
        errors.append(f"{context}_runtime_source_closure_files_invalid")
    else:
        observed_pairs = {
            row.get("path"): row.get("observed_sha256")
            for row in rows
            if isinstance(row, dict)
        }
        manifest_payload = json.loads(
            (ROOT / declared["manifest_path"]).read_text(encoding="utf-8")
        )
        expected_pairs = {
            row["path"]: row["sha256"] for row in manifest_payload["files"]
        }
        if observed_pairs != expected_pairs or any(
            not isinstance(row, dict)
            or row.get("expected_sha256") != row.get("observed_sha256")
            or row.get("matched") is not True
            for row in rows
        ):
            errors.append(f"{context}_runtime_source_closure_file_rows_mismatch")
    canary = observed.get("import_canary")
    if not isinstance(canary, dict) or any(
        canary.get(key) != value
        for key, value in {
            "expected_module_count": 29,
            "resolved_module_count": 29,
            "all_within_runtime_source_root": True,
            "exact_paths_verified": True,
            "passed": True,
        }.items()
    ):
        errors.append(f"{context}_runtime_source_import_canary_mismatch")


def _load_object(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label}_missing:{path.name}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}_invalid_json:{exc.__class__.__name__}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}_not_object")
        return None
    return value


def _safe_relative(path: str) -> bool:
    if not path or "\\" in path:
        return False
    value = PurePosixPath(path)
    return not value.is_absolute() and ".." not in value.parts


def expected_seeds(preregistration: Mapping[str, Any]) -> list[int]:
    design = preregistration["design"]
    return list(range(int(design["seed_start"]), int(design["seed_end"]) + 1))


def expected_execution_order(preregistration: Mapping[str, Any]) -> list[dict[str, Any]]:
    order: list[dict[str, Any]] = []
    for seed in expected_seeds(preregistration):
        policies = (PASSIVE, ACTIVE) if seed % 2 == 0 else (ACTIVE, PASSIVE)
        order.extend({"seed": seed, "policy": policy} for policy in policies)
    return order


def episode_relative_path(seed: int, policy: str) -> str:
    prefix = "active" if policy == ACTIVE else "passive"
    return f"episodes/{prefix}__independent-noise__{seed}.json"


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total)
        / denominator
    )
    return {"lower": max(0.0, center - half), "upper": min(1.0, center + half)}


def exact_mcnemar_two_sided(active_only: int, passive_only: int) -> float:
    discordant = active_only + passive_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, k) for k in range(min(active_only, passive_only) + 1)
    ) / (2.0**discordant)
    return min(1.0, 2.0 * tail)


def _rate(values: Sequence[bool]) -> dict[str, Any]:
    count = sum(bool(value) for value in values)
    total = len(values)
    if total == 0:
        return {"count": 0, "total": 0, "rate": None, "wilson_95": None}
    return {
        "count": count,
        "total": total,
        "rate": count / total,
        "wilson_95": wilson_interval(count, total),
    }


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def nearest_rank(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("nearest-rank percentile requires observations")
    ordered = sorted(float(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def _wall_distribution(values: Sequence[float]) -> dict[str, Any]:
    summary = _distribution(values)
    summary["p95"] = nearest_rank(values, 0.95)
    return summary


def _telemetry_metric_summary(
    values: Sequence[float], *, include_minimum: bool
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": nearest_rank(values, 0.95),
        "maximum": max(values),
    }
    if include_minimum:
        summary["minimum"] = min(values)
    return summary


def build_full_wall_rocm_telemetry(
    manifest: Mapping[str, Any], telemetry: Mapping[str, Any]
) -> dict[str, Any]:
    """Recompute publication telemetry and episode-wall summaries from raw rows."""

    samples = telemetry["samples"]
    timestamps = [int(sample["monotonic_ns"]) for sample in samples]
    gpu_use = [float(sample["gpu_use_percent"]) for sample in samples]
    vram = [float(sample["vram_allocated_percent"]) for sample in samples]
    power = [float(sample["graphics_package_power_w"]) for sample in samples]
    threshold = 1.0
    busy = [value >= threshold for value in gpu_use]

    attempts = manifest["execution"]["attempts"]
    by_policy = {
        ACTIVE: [float(row["wall_seconds"]) for row in attempts if row["policy"] == ACTIVE],
        PASSIVE: [float(row["wall_seconds"]) for row in attempts if row["policy"] == PASSIVE],
    }
    all_walls = [float(row["wall_seconds"]) for row in attempts]
    return {
        "scope": "entire challenge subprocess wall; zero-percent idle samples included",
        "sample_count": len(samples),
        "sample_interval_seconds": float(telemetry["sample_interval_seconds"]),
        "measured_wall_seconds": (
            int(telemetry["challenge_subprocess_ended_monotonic_ns"])
            - int(telemetry["challenge_subprocess_started_monotonic_ns"])
        )
        / 1_000_000_000.0,
        "subprocess_monotonic_range_ns": [
            int(telemetry["challenge_subprocess_started_monotonic_ns"]),
            int(telemetry["challenge_subprocess_ended_monotonic_ns"]),
        ],
        "sample_monotonic_range_ns": [timestamps[0], timestamps[-1]],
        "sample_range_seconds": (timestamps[-1] - timestamps[0])
        / 1_000_000_000.0,
        "gpu_use_percent": _telemetry_metric_summary(
            gpu_use, include_minimum=True
        ),
        "vram_allocated_percent": _telemetry_metric_summary(
            vram, include_minimum=False
        ),
        "graphics_package_power_w": _telemetry_metric_summary(
            power, include_minimum=True
        ),
        "gpu_busy_sample_rate": {
            "threshold_percent": threshold,
            "busy_samples": sum(busy),
            "total_samples": len(busy),
            "rate": sum(busy) / len(busy),
        },
        "episode_subprocess_wall_seconds": {
            "scope": "complete Python + Genesis + checkpoint + episode subprocess wall; not control-loop latency",
            "active": _wall_distribution(by_policy[ACTIVE]),
            "passive": _wall_distribution(by_policy[PASSIVE]),
            "all": _wall_distribution(all_walls),
        },
    }


def _bool_field(
    mapping: Mapping[str, Any], key: str, errors: list[str], context: str
) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        errors.append(f"{context}_{key}_not_bool")
        return False
    return value


def _number_field(
    mapping: Mapping[str, Any], key: str, errors: list[str], context: str
) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{context}_{key}_not_number")
        return 0.0
    number = float(value)
    if not math.isfinite(number):
        errors.append(f"{context}_{key}_not_finite")
        return 0.0
    return number


def _nonnegative_integer_field(
    mapping: Mapping[str, Any], key: str, errors: list[str], context: str
) -> int:
    number = _number_field(mapping, key, errors, context)
    if number < 0.0 or not number.is_integer():
        errors.append(f"{context}_{key}_not_nonnegative_integer")
        return 0
    return int(number)


def _motion_lengths(
    payload: Mapping[str, Any], errors: list[str], context: str
) -> tuple[float, float, int]:
    segments = payload.get("motion_segments")
    if not isinstance(segments, list):
        errors.append(f"{context}_motion_segments_not_list")
        return 0.0, 0.0, 0
    totals = {"carrier": 0.0, "scout": 0.0}
    collision_total = 0
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            errors.append(f"{context}_motion_segment_{index}_not_object")
            continue
        agent = segment.get("agent_id")
        if agent not in totals:
            errors.append(f"{context}_motion_segment_{index}_unexpected_agent")
            continue
        length = _number_field(
            segment, "path_length", errors, f"{context}_motion_segment_{index}"
        )
        if length < 0.0:
            errors.append(f"{context}_motion_segment_{index}_negative_path_length")
            continue
        totals[str(agent)] += length
        collisions = _number_field(
            segment,
            "collision_count",
            errors,
            f"{context}_motion_segment_{index}",
        )
        if collisions < 0.0 or not collisions.is_integer():
            errors.append(f"{context}_motion_segment_{index}_invalid_collision_count")
        else:
            collision_total += int(collisions)
    return totals["carrier"], totals["scout"], collision_total


def extract_episode_record(
    payload: Mapping[str, Any],
    *,
    seed: int,
    policy: str,
    relative_path: str,
    sha256: str,
    preregistration: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    """Validate one raw episode and return only preregistered measurements."""

    context = f"episode_{seed}_{POLICY_LABEL[policy]}"
    if payload.get("schema_version") != EPISODE_SCHEMA:
        errors.append(f"{context}_schema_mismatch")

    scenario = payload.get("scenario")
    configuration = payload.get("configuration")
    metrics = payload.get("metrics")
    outcome = payload.get("outcome")
    environment = payload.get("environment")
    for name, value in (
        ("scenario", scenario),
        ("configuration", configuration),
        ("metrics", metrics),
        ("outcome", outcome),
        ("environment", environment),
    ):
        if not isinstance(value, dict):
            errors.append(f"{context}_{name}_not_object")
    scenario = scenario if isinstance(scenario, dict) else {}
    configuration = configuration if isinstance(configuration, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    outcome = outcome if isinstance(outcome, dict) else {}
    environment = environment if isinstance(environment, dict) else {}

    oracle = scenario.get("oracle_context")
    oracle = oracle if isinstance(oracle, dict) else {}
    expected_scenario_id = f"v6:independent-noise:{seed}"
    identity_checks = {
        "scenario_seed": scenario.get("seed") == seed,
        "oracle_seed": oracle.get("seed") == seed,
        "scenario_profile": scenario.get("profile") == "independent-noise",
        "oracle_profile": oracle.get("profile") == "independent-noise",
        "scenario_id": scenario.get("scenario_id") == expected_scenario_id,
        "configuration_policy": configuration.get("policy") == policy,
        "metrics_policy": metrics.get("policy") == policy,
    }
    errors.extend(
        f"{context}_{name}_mismatch" for name, passed in identity_checks.items() if not passed
    )

    frozen = preregistration["identities"]
    checkpoint = frozen["checkpoint_sha256"]
    vision_conformal = frozen["vision_conformal_artifact_sha256"]
    go_conformal = frozen["go_conformal_artifact_sha256"]
    binary = frozen["purify_binary_sha256"]
    exact_episode_identities = {
        "metrics_checkpoint": metrics.get("checkpoint_sha256") == checkpoint,
        "metrics_vision_checkpoint": metrics.get("vision_checkpoint_sha256")
        == checkpoint,
        "metrics_conformal": metrics.get("conformal_artifact_sha256")
        == vision_conformal,
        "metrics_vision_conformal": metrics.get(
            "vision_conformal_artifact_sha256"
        )
        == vision_conformal,
        "metrics_purify_binary": metrics.get("purify_binary_sha256") == binary,
        "environment_purify_binary": environment.get("purify_binary_sha256")
        == binary,
    }
    errors.extend(
        f"{context}_{name}_mismatch"
        for name, passed in exact_episode_identities.items()
        if not passed
    )

    required_environment = preregistration["episode_contract"][
        "required_environment"
    ]
    environment_contract_valid = True
    for key, expected in required_environment.items():
        if environment.get(key) != expected:
            errors.append(f"{context}_environment_{key}_mismatch")
            environment_contract_valid = False

    vision_audits = payload.get("vision_audits")
    if not isinstance(vision_audits, list):
        errors.append(f"{context}_vision_audits_not_list")
        vision_audits = []
    audit_fallbacks: list[bool] = []
    audit_checkpoint_loaded: list[bool] = []
    for index, audit in enumerate(vision_audits):
        if not isinstance(audit, dict):
            errors.append(f"{context}_vision_audit_{index}_not_object")
            continue
        if audit.get("checkpoint_sha256") != checkpoint:
            errors.append(f"{context}_vision_audit_{index}_checkpoint_mismatch")
        if audit.get("conformal_artifact_sha256") != vision_conformal:
            errors.append(f"{context}_vision_audit_{index}_conformal_mismatch")
        audit_fallbacks.append(
            _bool_field(
                audit, "fallback_used", errors, f"{context}_vision_audit_{index}"
            )
        )
        audit_checkpoint_loaded.append(
            _bool_field(
                audit,
                "checkpoint_loaded",
                errors,
                f"{context}_vision_audit_{index}",
            )
        )
    vision_proposal_count = _nonnegative_integer_field(
        metrics, "vision_proposal_count", errors, context
    )
    if vision_proposal_count != len(vision_audits):
        errors.append(f"{context}_vision_proposal_count_mismatch")

    rgbd_audits = payload.get("rgbd_observation_audits")
    if not isinstance(rgbd_audits, list):
        errors.append(f"{context}_rgbd_observation_audits_not_list")
        rgbd_audits = []
    rgbd_observation_count = _nonnegative_integer_field(
        environment, "rgbd_observation_count", errors, context
    )
    if rgbd_observation_count != len(rgbd_audits):
        errors.append(f"{context}_rgbd_observation_count_mismatch")

    gate_receipts = payload.get("gate_receipts")
    if not isinstance(gate_receipts, list):
        errors.append(f"{context}_gate_receipts_not_list")
        gate_receipts = []
    agreement_flags: list[bool] = []
    full_admit_flags: list[bool] = []
    selected_corridor_full_admit_flags: list[bool] = []
    selected_corridor = metrics.get("selected_corridor")
    for index, receipt in enumerate(gate_receipts):
        if not isinstance(receipt, dict):
            errors.append(f"{context}_gate_receipt_{index}_not_object")
            continue
        py = receipt.get("python_admitted")
        go = receipt.get("purify_go_admitted")
        effective = receipt.get("effective_admit")
        comparison_fields_present = any(
            key in receipt
            for key in ("python_admitted", "purify_go_admitted", "effective_admit")
        )
        if not comparison_fields_present:
            continue
        if not all(isinstance(value, bool) for value in (py, go, effective)):
            errors.append(f"{context}_gate_receipt_{index}_admission_not_bool")
        else:
            action = receipt.get("action")
            corridor_id = receipt.get("corridor_id")
            if not isinstance(action, str) or not action:
                errors.append(f"{context}_gate_receipt_{index}_action_not_string")
            if not isinstance(corridor_id, str) or not corridor_id:
                errors.append(f"{context}_gate_receipt_{index}_corridor_id_not_string")
            agreement_flags.append(py == go == effective)
            full_admit = py is True and go is True and effective is True
            full_admit_flags.append(full_admit)
            selected_corridor_full_admit_flags.append(
                full_admit
                and action == "cross_corridor"
                and isinstance(selected_corridor, str)
                and bool(selected_corridor)
                and corridor_id == selected_corridor
            )

    go_receipts = payload.get("purify_go_receipts")
    if not isinstance(go_receipts, list):
        errors.append(f"{context}_purify_go_receipts_not_list")
        go_receipts = []
    short_go_id = f"v8-spatial-conformal:{go_conformal[:16]}"
    for index, receipt in enumerate(go_receipts):
        if not isinstance(receipt, dict):
            errors.append(f"{context}_purify_go_receipt_{index}_not_object")
            continue
        if receipt.get("_go_calibration_artifact_id") != short_go_id:
            errors.append(f"{context}_purify_go_receipt_{index}_go_identity_mismatch")
        if receipt.get("_purify_binary_sha256") != binary:
            errors.append(f"{context}_purify_go_receipt_{index}_binary_mismatch")
        if receipt.get("_purify_invoked") is not True:
            errors.append(f"{context}_purify_go_receipt_{index}_invocation_mismatch")

    route_mode = metrics.get("route_mode")
    used_detour = _bool_field(metrics, "used_detour", errors, context)
    if not isinstance(route_mode, str):
        errors.append(f"{context}_route_mode_not_string")
    route_only_direct = route_mode == "direct" and used_detour is False
    if route_only_direct and (
        not isinstance(selected_corridor, str) or not selected_corridor
    ):
        errors.append(f"{context}_selected_corridor_not_string_for_direct_route")
    mission_fields = [
        _bool_field(metrics, key, errors, context)
        for key in (
            "mission_success",
            "carrier_reached_goal",
            "payload_delivered",
            "within_deadline",
        )
    ]
    mission = all(mission_fields)
    outcome_mission = _bool_field(outcome, "mission_success", errors, context)
    if mission != outcome_mission:
        errors.append(f"{context}_mission_fields_disagree")
    full_chain_direct = (
        mission
        and outcome_mission
        and route_only_direct
        and isinstance(selected_corridor, str)
        and bool(selected_corridor)
        and any(selected_corridor_full_admit_flags)
    )

    unsafe_crossing = _bool_field(metrics, "unsafe_crossing", errors, context)
    collision_count = _number_field(metrics, "collision_count", errors, context)
    admit_then_contact = _bool_field(metrics, "admit_then_contact", errors, context)
    clear_collision = _bool_field(
        metrics, "clear_admitted_collision", errors, context
    )
    unsafe = (
        unsafe_crossing
        or collision_count > 0.0
        or admit_then_contact
        or clear_collision
    )

    fallback_keys = ("fallback_used", "vision_fallback_used")
    fallback_values = [
        _bool_field(metrics, key, errors, context) for key in fallback_keys
    ]
    safe_fallback = _bool_field(outcome, "safe_fallback", errors, context)
    fallback = any(fallback_values) or any(audit_fallbacks) or safe_fallback

    checkpoint_loaded = _bool_field(
        metrics, "vision_checkpoint_loaded", errors, context
    ) and _bool_field(metrics, "checkpoint_loaded", errors, context)
    checkpoint_loaded = checkpoint_loaded and bool(audit_checkpoint_loaded) and all(
        audit_checkpoint_loaded
    )
    purify_invoked = _bool_field(metrics, "purify_invoked", errors, context)
    environment_purify_invoked = _bool_field(
        environment, "purify_invoked", errors, context
    )
    if purify_invoked != environment_purify_invoked:
        errors.append(f"{context}_purify_invocation_fields_disagree")
    purify_invoked_count = _nonnegative_integer_field(
        metrics, "purify_invoked_count", errors, context
    )
    environment_purify_count = _nonnegative_integer_field(
        environment, "purify_invoked_count", errors, context
    )
    if purify_invoked_count != environment_purify_count:
        errors.append(f"{context}_purify_invocation_count_fields_disagree")
    go_receipt_count_metric = _nonnegative_integer_field(
        metrics, "purify_go_receipt_count", errors, context
    )
    if go_receipt_count_metric != len(go_receipts):
        errors.append(f"{context}_purify_go_receipt_count_mismatch")
    python_go_agreement = bool(agreement_flags) and all(agreement_flags)
    _bool_field(metrics, "purify_go_receipts_ok", errors, context)

    genesis_live = _bool_field(environment, "genesis_live_rgbd", errors, context)
    metrics_genesis_live = _bool_field(
        metrics, "genesis_live_rgbd", errors, context
    )
    if genesis_live != metrics_genesis_live:
        errors.append(f"{context}_genesis_live_rgbd_fields_disagree")
    world_alignment_passed = _bool_field(
        metrics, "world_alignment_passed", errors, context
    )
    world_alignment = payload.get("world_alignment")
    environment_alignment = environment.get("world_alignment")
    if not isinstance(world_alignment, dict):
        errors.append(f"{context}_world_alignment_not_object")
        world_alignment = {}
    if not isinstance(environment_alignment, dict):
        errors.append(f"{context}_environment_world_alignment_not_object")
        environment_alignment = {}
    for label, alignment in (
        ("top", world_alignment),
        ("environment", environment_alignment),
    ):
        passed = _bool_field(
            alignment, "world_alignment_passed", errors, f"{context}_{label}_alignment"
        )
        if passed != world_alignment_passed:
            errors.append(f"{context}_{label}_world_alignment_fields_disagree")
        for unsafe_key in ("admit_then_contact",):
            aligned_unsafe = _bool_field(
                alignment, unsafe_key, errors, f"{context}_{label}_alignment"
            )
            if unsafe_key == "admit_then_contact" and aligned_unsafe != admit_then_contact:
                errors.append(f"{context}_{label}_{unsafe_key}_fields_disagree")
    carrier_path, scout_path, motion_collision_count = _motion_lengths(
        payload, errors, context
    )
    if collision_count != motion_collision_count:
        errors.append(f"{context}_collision_count_fields_disagree")

    return {
        "seed": seed,
        "policy": policy,
        "relative_path": relative_path,
        "sha256": sha256,
        "full_chain_direct": full_chain_direct,
        "route_only_direct": route_only_direct,
        "selected_corridor": selected_corridor,
        "mission_success": mission and outcome_mission,
        "unsafe": unsafe,
        "fallback_used": fallback,
        "python_go_gate_agreement": python_go_agreement,
        "gate_receipt_count": len(gate_receipts),
        "python_go_comparable_receipt_count": len(agreement_flags),
        "python_go_agree_receipt_count": sum(agreement_flags),
        "full_admit_receipt_count": sum(full_admit_flags),
        "selected_corridor_full_admit_receipt_count": sum(
            selected_corridor_full_admit_flags
        ),
        "initial_gate_denied": _bool_field(
            metrics, "initial_gate_denied", errors, context
        ),
        "repair_attempted": _bool_field(
            metrics, "repair_attempted", errors, context
        ),
        "purify_invoked": purify_invoked and environment_purify_invoked,
        "purify_invoked_count": purify_invoked_count,
        "purify_go_receipt_count": len(go_receipts),
        "rgbd_observation_count": rgbd_observation_count,
        "vision_proposal_count": vision_proposal_count,
        "environment_contract_valid": environment_contract_valid,
        "genesis_live_rgbd": genesis_live,
        "frozen_checkpoint_loaded": checkpoint_loaded,
        "world_alignment_passed": world_alignment_passed,
        "carrier_path_length": carrier_path,
        "scout_path_length": scout_path,
        "team_path_length": carrier_path + scout_path,
    }


def load_episode_records(
    results_dir: Path,
    preregistration: Mapping[str, Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    expected_paths = {
        episode_relative_path(seed, policy)
        for seed in expected_seeds(preregistration)
        for policy in POLICIES
    }
    episodes_dir = results_dir / "episodes"
    actual_paths = (
        {
            path.relative_to(results_dir).as_posix()
            for path in episodes_dir.rglob("*.json")
            if path.is_file()
        }
        if episodes_dir.is_dir()
        else set()
    )
    for relative in sorted(expected_paths - actual_paths):
        errors.append(f"raw_episode_missing:{relative}")
    for relative in sorted(actual_paths - expected_paths):
        errors.append(f"unexpected_raw_episode:{relative}")

    records: list[dict[str, Any]] = []
    for seed in expected_seeds(preregistration):
        for policy in POLICIES:
            relative = episode_relative_path(seed, policy)
            path = results_dir / relative
            payload = _load_object(path, errors, f"raw_episode_{seed}_{POLICY_LABEL[policy]}")
            if payload is None:
                continue
            records.append(
                extract_episode_record(
                    payload,
                    seed=seed,
                    policy=policy,
                    relative_path=relative,
                    sha256=file_sha256(path),
                    preregistration=preregistration,
                    errors=errors,
                )
            )
    return records


def build_analysis(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the complete preregistered analysis from validated raw records."""

    by_key = {(int(row["seed"]), str(row["policy"])): row for row in records}
    seeds = sorted({int(row["seed"]) for row in records})
    if len(records) != 60 or len(seeds) != 30:
        raise ValueError("complete analysis requires exactly 30 pairs / 60 episodes")
    paired = [(by_key[(seed, ACTIVE)], by_key[(seed, PASSIVE)]) for seed in seeds]
    active = [row[0] for row in paired]
    passive = [row[1] for row in paired]

    active_direct = [bool(row["full_chain_direct"]) for row in active]
    passive_direct = [bool(row["full_chain_direct"]) for row in passive]
    both = sum(a and p for a, p in zip(active_direct, passive_direct))
    active_only = sum(a and not p for a, p in zip(active_direct, passive_direct))
    passive_only = sum(not a and p for a, p in zip(active_direct, passive_direct))
    neither = len(seeds) - both - active_only - passive_only

    secondary_names = (
        "mission_success",
        "unsafe",
        "fallback_used",
        "python_go_gate_agreement",
        "initial_gate_denied",
        "repair_attempted",
        "purify_invoked",
        "environment_contract_valid",
        "route_only_direct",
    )
    secondary: dict[str, Any] = {}
    for name in secondary_names:
        secondary[name] = {
            "active": _rate([bool(row[name]) for row in active]),
            "passive": _rate([bool(row[name]) for row in passive]),
            "all_episodes": _rate([bool(row[name]) for row in (*active, *passive)]),
        }
    receipt_agreements = [
        True
        for row in (*active, *passive)
        for _ in range(int(row["python_go_agree_receipt_count"]))
    ] + [
        False
        for row in (*active, *passive)
        for _ in range(
            int(row["python_go_comparable_receipt_count"])
            - int(row["python_go_agree_receipt_count"])
        )
    ]
    secondary["python_go_gate_agreement"]["comparable_receipts"] = _rate(
        receipt_agreements
    )

    active_carrier = [float(row["carrier_path_length"]) for row in active]
    passive_carrier = [float(row["carrier_path_length"]) for row in passive]
    active_scout = [float(row["scout_path_length"]) for row in active]
    active_team = [float(row["team_path_length"]) for row in active]
    passive_team = [float(row["team_path_length"]) for row in passive]
    carrier_deltas = [a - p for a, p in zip(active_carrier, passive_carrier)]
    team_deltas = [a - p for a, p in zip(active_team, passive_team)]

    all_rows = [*active, *passive]
    full_pipeline = {
        "episodes": {"count": len(all_rows), "expected": 60},
        "genesis_live_rgbd": _rate(
            [bool(row["genesis_live_rgbd"]) for row in all_rows]
        ),
        "frozen_checkpoint_loaded": _rate(
            [bool(row["frozen_checkpoint_loaded"]) for row in all_rows]
        ),
        "purify_invoked": _rate(
            [bool(row["purify_invoked"]) for row in all_rows]
        ),
        "purify_invoked_count_total": sum(
            int(row["purify_invoked_count"]) for row in all_rows
        ),
        "episodes_with_purify_go_receipt": _rate(
            [int(row["purify_go_receipt_count"]) > 0 for row in all_rows]
        ),
        "purify_go_receipt_count_sum": sum(
            int(row["purify_go_receipt_count"]) for row in all_rows
        ),
        "world_alignment_passed": _rate(
            [bool(row["world_alignment_passed"]) for row in all_rows]
        ),
        "rgbd_observation_count_total": sum(
            int(row["rgbd_observation_count"]) for row in all_rows
        ),
        "rgbd_observation_count_mean": statistics.fmean(
            int(row["rgbd_observation_count"]) for row in all_rows
        ),
        "vision_proposal_count_total": sum(
            int(row["vision_proposal_count"]) for row in all_rows
        ),
        "vision_proposal_count_mean": statistics.fmean(
            int(row["vision_proposal_count"]) for row in all_rows
        ),
    }

    per_seed: list[dict[str, Any]] = []
    public_fields = (
        "full_chain_direct",
        "route_only_direct",
        "mission_success",
        "unsafe",
        "fallback_used",
        "python_go_gate_agreement",
        "genesis_live_rgbd",
        "frozen_checkpoint_loaded",
        "purify_invoked",
        "purify_go_receipt_count",
        "rgbd_observation_count",
        "vision_proposal_count",
        "python_go_comparable_receipt_count",
        "python_go_agree_receipt_count",
        "full_admit_receipt_count",
        "selected_corridor_full_admit_receipt_count",
        "selected_corridor",
        "world_alignment_passed",
        "carrier_path_length",
        "scout_path_length",
        "team_path_length",
        "sha256",
    )
    for seed, (active_row, passive_row) in zip(seeds, paired):
        per_seed.append(
            {
                "seed": seed,
                "execution_order": [PASSIVE, ACTIVE]
                if seed % 2 == 0
                else [ACTIVE, PASSIVE],
                "active": {key: active_row[key] for key in public_fields},
                "passive": {key: passive_row[key] for key in public_fields},
                "paired_deltas_active_minus_passive": {
                    "carrier_path_length": float(active_row["carrier_path_length"])
                    - float(passive_row["carrier_path_length"]),
                    "team_path_length": float(active_row["team_path_length"])
                    - float(passive_row["team_path_length"]),
                },
            }
        )

    return {
        "evidence_scope": {
            "worlds": 30,
            "paired_episodes": 60,
            "seed_range": [min(seeds), max(seeds)],
            "generator_family": "same_generator_reserved_challenge_subset",
            "motion_backend": "kinematic",
            "not_ood": True,
            "not_physical_robot": True,
            "agent_realization": "single_shared_genesis_chassis_with_separate_logical_role_poses",
            "not_simultaneous_dual_body_dynamics": True,
            "distinct_capture_roots_and_viewpoints_do_not_imply_two_physical_devices": True,
        },
        "primary_endpoint": {
            "name": "full_chain_direct_rate_difference",
            "event_definition": "mission success and route-only direct and non-empty metrics.selected_corridor and at least one same-corridor cross_corridor gate receipt with python_admitted == purify_go_admitted == effective_admit == true",
            "active": _rate(active_direct),
            "passive": _rate(passive_direct),
            "active_minus_passive": {
                "rate_difference": sum(active_direct) / len(active_direct)
                - sum(passive_direct) / len(passive_direct),
                "percentage_points": 100.0
                * (
                    sum(active_direct) / len(active_direct)
                    - sum(passive_direct) / len(passive_direct)
                ),
            },
            "paired_table": {
                "both_direct": both,
                "active_only_direct": active_only,
                "passive_only_direct": passive_only,
                "neither_direct": neither,
            },
            "exact_mcnemar_two_sided_p": exact_mcnemar_two_sided(
                active_only, passive_only
            ),
            "success_threshold": None,
        },
        "secondary_endpoints": secondary,
        "full_pipeline_denominator": full_pipeline,
        "logical_role_kinematic_operational_burden": {
            "unit": "episode-reported path_length",
            "scope": "same-generator logical-role kinematic burden on one shared Genesis chassis; not energy, throughput, latency, physical duty cycle, two physical devices, or simultaneous dual-body dynamics",
            "loaded_carrier": {
                "active": _distribution(active_carrier),
                "passive": _distribution(passive_carrier),
                "paired_delta_active_minus_passive": _distribution(carrier_deltas),
            },
            "active_scout": _distribution(active_scout),
            "total_team": {
                "active": _distribution(active_team),
                "passive": _distribution(passive_team),
                "paired_delta_active_minus_passive": _distribution(team_deltas),
            },
        },
        "interpretation_guardrails": [
            "Carrier and scout are logical roles with separate poses, viewpoints, and capture roots on one shared Genesis chassis.",
            "The run is not simultaneous dual-body dynamics and does not demonstrate two physical devices.",
            "Path length is logical-role kinematic burden, not energy, throughput, control-loop latency, or physical duty cycle.",
        ],
        "per_seed": per_seed,
    }


def expected_report(
    records: Sequence[Mapping[str, Any]],
    preregistration_sha256: str,
    manifest: Mapping[str, Any],
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    analysis = build_analysis(records)
    analysis["full_wall_rocm_telemetry"] = build_full_wall_rocm_telemetry(
        manifest, telemetry
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "preregistration_sha256": preregistration_sha256,
        "analysis": analysis,
    }


def _validate_preregistration(
    preregistration: Mapping[str, Any], repo_root: Path, errors: list[str]
) -> None:
    if preregistration.get("schema_version") != PREREG_SCHEMA:
        errors.append("preregistration_schema_mismatch")
    design = preregistration.get("design")
    if not isinstance(design, dict):
        errors.append("preregistration_design_not_object")
        return
    fixed = {
        "seed_start": 102500,
        "seed_end": 102529,
        "n_worlds": 30,
        "n_episodes": 60,
        "profile": "independent-noise",
        "attempts_per_seed_policy": 1,
        "retry_count_allowed": 0,
        "early_stopping_allowed": False,
        "publish_every_attempt": True,
        "retuning_allowed": False,
        "threshold_changes_allowed": False,
        "checkpoint_changes_allowed": False,
        "seed_substitution_allowed": False,
    }
    errors.extend(
        f"preregistration_{key}_mismatch"
        for key, expected in fixed.items()
        if design.get(key) != expected
    )
    order_rule = design.get("within_seed_order_rule")
    if not isinstance(order_rule, dict) or order_rule.get("even_seed") != [PASSIVE, ACTIVE]:
        errors.append("preregistration_even_order_mismatch")
    if not isinstance(order_rule, dict) or order_rule.get("odd_seed") != [ACTIVE, PASSIVE]:
        errors.append("preregistration_odd_order_mismatch")
    endpoints = preregistration.get("endpoints")
    primary = endpoints.get("primary") if isinstance(endpoints, dict) else None
    if not isinstance(primary, dict) or primary.get("name") != (
        "full_chain_direct_rate_difference"
    ):
        errors.append("preregistration_primary_endpoint_mismatch")
    secondary = endpoints.get("secondary") if isinstance(endpoints, dict) else None
    if not isinstance(secondary, list) or "route_only_direct" not in secondary:
        errors.append("preregistration_route_only_secondary_missing")
    episode_contract = preregistration.get("episode_contract")
    agent_scope = (
        episode_contract.get("agent_scope")
        if isinstance(episode_contract, dict)
        else None
    )
    expected_agent_scope = {
        "agent_realization": "single_shared_genesis_chassis_with_separate_logical_role_poses",
        "not_simultaneous_dual_body_dynamics": True,
        "distinct_logical_role_poses_viewpoints_and_capture_roots": True,
        "not_two_physical_devices": True,
    }
    if agent_scope != expected_agent_scope:
        errors.append("preregistration_agent_scope_mismatch")
    telemetry_contract = preregistration.get("telemetry_contract")
    if not isinstance(telemetry_contract, dict):
        errors.append("preregistration_telemetry_contract_not_object")
    else:
        if telemetry_contract.get("gpu_busy_threshold_percent") != 1.0:
            errors.append("preregistration_gpu_busy_threshold_mismatch")
        if telemetry_contract.get("include_zero_percent_idle_samples") is not True:
            errors.append("preregistration_idle_sample_rule_mismatch")
        if telemetry_contract.get("percentile_method") != "nearest_rank_ceil_p_times_n":
            errors.append("preregistration_percentile_method_mismatch")
        if telemetry_contract.get("sample_interval_seconds") != 2.0:
            errors.append("preregistration_sample_interval_mismatch")
        if telemetry_contract.get("max_gap_seconds") != 5.5:
            errors.append("preregistration_max_gap_mismatch")
    subprocess_contract = preregistration.get("subprocess_wall_contract")
    if not isinstance(subprocess_contract, dict):
        errors.append("preregistration_subprocess_contract_not_object")
    else:
        timeout_checks = {
            "episode_timeout_seconds": 300,
            "timeout_process_group": True,
            "timeout_outcome_preserved": True,
            "continue_after_timeout": True,
            "retry_after_timeout": False,
        }
        for key, expected in timeout_checks.items():
            if subprocess_contract.get(key) != expected:
                errors.append(f"preregistration_{key}_mismatch")
        if subprocess_contract.get("timeout_signal_sequence") != [
            {"signal": "SIGTERM", "at_timeout_seconds": 300},
            {"grace_seconds": 10},
            {"signal": "SIGKILL", "if_still_running": True},
        ]:
            errors.append("preregistration_timeout_signal_sequence_mismatch")
        if subprocess_contract.get("fixed_subprocess_environment") != {
            "PATH_prepend": "/opt/venv/bin",
            "MIOPEN_FIND_MODE": "FAST",
        }:
            errors.append("preregistration_fixed_subprocess_environment_mismatch")

    identities = preregistration.get("identities")
    if not isinstance(identities, dict):
        errors.append("preregistration_identities_not_object")
        return
    runner_sha = identities.get("runner_sha256")
    if not isinstance(runner_sha, str) or not SHA256_RE.fullmatch(runner_sha):
        errors.append("preregistration_runner_sha256_not_bound")
    runner_relative = identities.get("runner_path")
    if not isinstance(runner_relative, str) or not _safe_relative(runner_relative):
        errors.append("preregistration_runner_path_unsafe")
    elif isinstance(runner_sha, str) and SHA256_RE.fullmatch(runner_sha):
        runner_path = repo_root / runner_relative
        if not runner_path.is_file():
            errors.append("bound_runner_missing")
        elif file_sha256(runner_path) != runner_sha:
            errors.append("bound_runner_sha256_mismatch")
    validator_sha = identities.get("validator_sha256")
    if not isinstance(validator_sha, str) or not SHA256_RE.fullmatch(validator_sha):
        errors.append("preregistration_validator_sha256_not_bound")
    validator_relative = identities.get("validator_path")
    if not isinstance(validator_relative, str) or not _safe_relative(validator_relative):
        errors.append("preregistration_validator_path_unsafe")
    elif isinstance(validator_sha, str) and SHA256_RE.fullmatch(validator_sha):
        validator_path = repo_root / validator_relative
        if not validator_path.is_file():
            errors.append("bound_validator_missing")
        elif file_sha256(validator_path) != validator_sha:
            errors.append("bound_validator_sha256_mismatch")
    public = preregistration.get("public_binding")
    if not isinstance(public, dict):
        errors.append("public_binding_not_object")
    else:
        commit = public.get("runner_protocol_commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            errors.append("public_binding_runner_protocol_commit_not_bound")

    runtime_closure = identities.get("runtime_source_closure")
    if not isinstance(runtime_closure, dict):
        errors.append("runtime_source_closure_not_object")
        runtime_closure = {}
    expected_runtime_closure = {
        "manifest_path": "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json",
        "manifest_sha256": "018f064f0361e59371e6694d7909da8639960f41f2ef158687c8e65e24d45c2f",
        "tree_fingerprint_sha256": "abc1b6810aed6dc19a127069b9b5d5f044def24f35c9a13602f7f5096742b1be",
        "file_count": 30,
        "python_file_count": 29,
        "static_asset_file_count": 1,
        "root_entrypoint": "src/look_twice_v7.py",
        "exact_python_file_set_required": True,
        "source_origin_git_commit": "aadd429d2da9de690a361218c40c9dfb22b04eb2",
    }
    if runtime_closure != expected_runtime_closure:
        errors.append("runtime_source_closure_declaration_mismatch")
    runtime_manifest_relative = runtime_closure.get("manifest_path")
    runtime_manifest_sha = runtime_closure.get("manifest_sha256")
    runtime_manifest: dict[str, Any] | None = None
    if (
        not isinstance(runtime_manifest_relative, str)
        or not _safe_relative(runtime_manifest_relative)
    ):
        errors.append("runtime_source_manifest_path_unsafe")
    elif not isinstance(runtime_manifest_sha, str) or not SHA256_RE.fullmatch(
        runtime_manifest_sha
    ):
        errors.append("runtime_source_manifest_sha256_invalid")
    else:
        runtime_manifest_path = repo_root / runtime_manifest_relative
        runtime_manifest = _load_object(
            runtime_manifest_path, errors, "runtime_source_manifest"
        )
        if runtime_manifest_path.is_file() and file_sha256(
            runtime_manifest_path
        ) != runtime_manifest_sha:
            errors.append("runtime_source_manifest_file_sha256_mismatch")
        if runtime_manifest is not None:
            if runtime_manifest.get("schema_version") != (
                "look-twice.v8-challenge-runtime-dependency-manifest/v1"
            ):
                errors.append("runtime_source_manifest_schema_mismatch")
            manifest_rows = runtime_manifest.get("files")
            fixed_runtime_fields = {
                "file_count": 30,
                "python_file_count": 29,
                "static_asset_file_count": 1,
                "tree_fingerprint_sha256": runtime_closure.get(
                    "tree_fingerprint_sha256"
                ),
                "root_entrypoint": runtime_closure.get("root_entrypoint"),
                "source_origin_git_commit": runtime_closure.get(
                    "source_origin_git_commit"
                ),
            }
            for key, expected in fixed_runtime_fields.items():
                if runtime_manifest.get(key) != expected:
                    errors.append(f"runtime_source_manifest_{key}_mismatch")
    declared_runtime_rows = (
        runtime_manifest.get("files") if isinstance(runtime_manifest, dict) else None
    )
    if not isinstance(declared_runtime_rows, list) or len(declared_runtime_rows) != 30:
        errors.append("runtime_source_exact_file_count_mismatch")
    else:
        paths = [row.get("path") for row in declared_runtime_rows if isinstance(row, dict)]
        rows_well_formed = all(
            isinstance(row, dict)
            and isinstance(row.get("path"), str)
            and isinstance(row.get("sha256"), str)
            and bool(SHA256_RE.fullmatch(str(row.get("sha256"))))
            for row in declared_runtime_rows
        )
        if len(paths) != 30 or len(set(paths)) != 30 or not rows_well_formed:
            errors.append("runtime_source_exact_paths_invalid")
        if rows_well_formed and runtime_source_tree_fingerprint(
            declared_runtime_rows
        ) != runtime_closure.get("tree_fingerprint_sha256"):
            errors.append("runtime_source_declared_tree_fingerprint_mismatch")
        for row in declared_runtime_rows:
            if not isinstance(row, dict):
                continue
            relative = row.get("path")
            expected_sha = row.get("sha256")
            if not isinstance(relative, str) or not _safe_relative(relative):
                errors.append("runtime_source_file_path_unsafe")
                continue
            path = repo_root / relative
            if not path.is_file():
                errors.append(f"runtime_source_file_missing:{relative}")
            elif file_sha256(path) != expected_sha:
                errors.append(f"runtime_source_file_sha256_mismatch:{relative}")
    critical = identities.get("critical_source_files")
    if not isinstance(critical, list) or len(critical) != 13:
        errors.append("preregistration_critical_source_file_count_mismatch")
    elif len({row.get("path") for row in critical if isinstance(row, dict)}) != 13:
        errors.append("preregistration_critical_source_paths_not_unique")


def _validate_run_manifest(
    manifest: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    preregistration_sha256: str,
    errors: list[str],
) -> None:
    if manifest.get("schema_version") != RUN_MANIFEST_SCHEMA:
        errors.append("run_manifest_schema_mismatch")
    if manifest.get("preregistration_sha256") != preregistration_sha256:
        errors.append("run_manifest_preregistration_sha256_mismatch")
    identities = preregistration["identities"]
    if manifest.get("runner_sha256") != identities.get("runner_sha256"):
        errors.append("run_manifest_runner_sha256_mismatch")
    if manifest.get("validator_sha256") != identities.get("validator_sha256"):
        errors.append("run_manifest_validator_sha256_mismatch")
    _validate_runtime_source_closure_record(
        manifest.get("runtime_source_closure"),
        preregistration,
        errors,
        "run_manifest",
    )
    runtime = manifest.get("runtime")
    overrides = runtime.get("environment_overrides") if isinstance(runtime, dict) else None
    if not isinstance(overrides, dict) or overrides.get("MIOPEN_FIND_MODE") != "FAST":
        errors.append("run_manifest_miopen_find_mode_mismatch")
    path_value = overrides.get("PATH") if isinstance(overrides, dict) else None
    if not isinstance(path_value, str) or path_value.split(":", 1)[0] != "/opt/venv/bin":
        errors.append("run_manifest_path_prepend_mismatch")
    if not isinstance(overrides, dict) or overrides.get("PATH_prepend") != "/opt/venv/bin":
        errors.append("run_manifest_path_prepend_declaration_mismatch")
    runner_protocol_commit = manifest.get("runner_protocol_commit")
    if runner_protocol_commit != preregistration.get(
        "public_binding", {}
    ).get("runner_protocol_commit"):
        errors.append("run_manifest_runner_protocol_commit_mismatch")
    preregistration_public_commit = manifest.get("preregistration_public_commit")
    if not isinstance(preregistration_public_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", preregistration_public_commit
    ):
        errors.append("run_manifest_preregistration_public_commit_invalid")
    if preregistration_public_commit == runner_protocol_commit:
        errors.append("run_manifest_public_commits_not_distinct")
    observed_identities = manifest.get("frozen_identities")
    if not isinstance(observed_identities, dict):
        errors.append("run_manifest_frozen_identities_not_object")
    else:
        for key in (
            "checkpoint_sha256",
            "vision_conformal_artifact_sha256",
            "go_conformal_artifact_sha256",
            "purify_binary_sha256",
            "source_tree_fingerprint_sha256",
        ):
            if observed_identities.get(key) != identities.get(key):
                errors.append(f"run_manifest_{key}_mismatch")

    execution = manifest.get("execution")
    if not isinstance(execution, dict):
        errors.append("run_manifest_execution_not_object")
    else:
        checks = {
            "order": execution.get("order") == expected_execution_order(preregistration),
            "attempted_episode_count": execution.get("attempted_episode_count") == 60,
            "completed_episode_count": execution.get("completed_episode_count") == 60,
            "retry_count": execution.get("retry_count") == 0,
            "early_stopped": execution.get("early_stopped") is False,
            "all_outcomes_preserved": execution.get("all_outcomes_preserved") is True,
            "subprocess_exit_code": execution.get("subprocess_exit_code") == 0,
        }
        errors.extend(
            f"run_manifest_execution_{name}_mismatch"
            for name, passed in checks.items()
            if not passed
        )
        attempts = execution.get("attempts")
        expected_order = expected_execution_order(preregistration)
        if not isinstance(attempts, list) or len(attempts) != 60:
            errors.append("run_manifest_execution_attempt_count_mismatch")
        else:
            previous_end: int | None = None
            for index, (attempt, expected) in enumerate(zip(attempts, expected_order)):
                context = f"run_manifest_attempt_{index}"
                if not isinstance(attempt, dict):
                    errors.append(f"{context}_not_object")
                    continue
                if attempt.get("seed") != expected["seed"]:
                    errors.append(f"{context}_seed_mismatch")
                if attempt.get("policy") != expected["policy"]:
                    errors.append(f"{context}_policy_mismatch")
                started = attempt.get("started_monotonic_ns")
                ended = attempt.get("ended_monotonic_ns")
                wall = attempt.get("wall_seconds")
                if (
                    isinstance(started, bool)
                    or not isinstance(started, int)
                    or isinstance(ended, bool)
                    or not isinstance(ended, int)
                    or ended <= started
                ):
                    errors.append(f"{context}_monotonic_bounds_invalid")
                    continue
                if previous_end is not None and started < previous_end:
                    errors.append(f"{context}_overlaps_previous_attempt")
                previous_end = ended
                measured_wall = (ended - started) / 1_000_000_000.0
                if (
                    isinstance(wall, bool)
                    or not isinstance(wall, (int, float))
                    or float(wall) <= 0.0
                    or not math.isclose(
                        float(wall), measured_wall, rel_tol=1e-9, abs_tol=1e-6
                    )
                ):
                    errors.append(f"{context}_wall_seconds_invalid")
                if attempt.get("exit_code") != 0:
                    errors.append(f"{context}_exit_code_not_zero")
                if attempt.get("timeout_seconds") != 300.0:
                    errors.append(f"{context}_timeout_seconds_mismatch")
                if attempt.get("timed_out") is not False:
                    errors.append(f"{context}_timed_out")
                if attempt.get("start_new_session") is not True:
                    errors.append(f"{context}_process_group_not_isolated")
                if attempt.get("termination_grace_seconds") != 10.0:
                    errors.append(f"{context}_termination_grace_mismatch")
                if attempt.get("termination_actions") != []:
                    errors.append(f"{context}_unexpected_termination_actions")

    fixed_episode_contract = manifest.get("fixed_episode_contract")
    if not isinstance(fixed_episode_contract, dict):
        errors.append("run_manifest_fixed_episode_contract_not_object")
    else:
        if fixed_episode_contract.get("episode_timeout_seconds") != 300.0:
            errors.append("run_manifest_episode_timeout_seconds_mismatch")
        if fixed_episode_contract.get("timeout_process_group_termination") != {
            "start_new_session": True,
            "first_signal": "SIGTERM",
            "grace_seconds": 10.0,
            "final_signal": "SIGKILL",
            "retry_after_timeout": False,
        }:
            errors.append("run_manifest_timeout_process_group_contract_mismatch")

    preflight = manifest.get("source_preflight")
    expected_files = {
        row["path"]: row["sha256"] for row in identities["critical_source_files"]
    }
    if not isinstance(preflight, dict):
        errors.append("run_manifest_source_preflight_not_object")
        return
    if preflight.get("source_tree_fingerprint_sha256") != identities.get(
        "source_tree_fingerprint_sha256"
    ):
        errors.append("source_preflight_fingerprint_mismatch")
    if preflight.get("critical_source_file_count") != 13:
        errors.append("source_preflight_file_count_mismatch")
    if preflight.get("mismatch_count") != 0:
        errors.append("source_preflight_mismatch_count_not_zero")
    rows = preflight.get("files")
    if not isinstance(rows, list):
        errors.append("source_preflight_files_not_list")
        return
    observed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append("source_preflight_file_row_invalid")
            continue
        if row["path"] in observed:
            errors.append(f"source_preflight_duplicate:{row['path']}")
        observed[row["path"]] = row
    if set(observed) != set(expected_files):
        errors.append("source_preflight_path_set_mismatch")
    for path, expected_sha in expected_files.items():
        row = observed.get(path, {})
        if row.get("expected_sha256") != expected_sha:
            errors.append(f"source_preflight_expected_sha_mismatch:{path}")
        if row.get("observed_sha256") != expected_sha:
            errors.append(f"source_preflight_observed_sha_mismatch:{path}")
        if row.get("matched") is not True:
            errors.append(f"source_preflight_matched_false:{path}")


def _validate_prestart_binding(
    binding: Mapping[str, Any],
    manifest: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    preregistration_sha256: str,
    errors: list[str],
) -> None:
    if binding.get("schema_version") != (
        "look-twice.v8-frozen-challenge-prestart-binding/v1"
    ):
        errors.append("prestart_binding_schema_mismatch")
    identities = preregistration["identities"]
    expected = {
        "preregistration_sha256": preregistration_sha256,
        "runner_sha256": identities["runner_sha256"],
        "validator_sha256": identities["validator_sha256"],
        "runner_protocol_commit": preregistration["public_binding"][
            "runner_protocol_commit"
        ],
        "preregistration_public_commit": manifest.get(
            "preregistration_public_commit"
        ),
        "no_episode_had_started": True,
    }
    for key, value in expected.items():
        if binding.get(key) != value:
            errors.append(f"prestart_binding_{key}_mismatch")
    _validate_runtime_source_closure_record(
        binding.get("runtime_source_closure"),
        preregistration,
        errors,
        "prestart_binding",
    )
    planned = binding.get("planned_schedule")
    planned_projection = (
        [
            {"seed": row.get("seed"), "policy": row.get("policy")}
            for row in planned
            if isinstance(row, dict)
        ]
        if isinstance(planned, list)
        else []
    )
    if planned_projection != expected_execution_order(preregistration):
        errors.append("prestart_binding_planned_schedule_mismatch")
    environment = binding.get("fixed_subprocess_environment")
    if not isinstance(environment, dict) or environment.get("MIOPEN_FIND_MODE") != "FAST":
        errors.append("prestart_binding_miopen_find_mode_mismatch")
    path_value = environment.get("PATH") if isinstance(environment, dict) else None
    if not isinstance(path_value, str) or path_value.split(":", 1)[0] != "/opt/venv/bin":
        errors.append("prestart_binding_path_prepend_mismatch")
    if not isinstance(environment, dict) or environment.get("PATH_prepend") != "/opt/venv/bin":
        errors.append("prestart_binding_path_prepend_declaration_mismatch")


def _validate_telemetry(
    telemetry: Mapping[str, Any], preregistration: Mapping[str, Any], errors: list[str]
) -> None:
    if telemetry.get("schema_version") != TELEMETRY_SCHEMA:
        errors.append("telemetry_schema_mismatch")
    if telemetry.get("scope") != "entire_challenge_subprocess_wall":
        errors.append("telemetry_scope_mismatch")
    numeric_names = (
        "sampler_started_monotonic_ns",
        "challenge_subprocess_started_monotonic_ns",
        "challenge_subprocess_ended_monotonic_ns",
        "sampler_ended_monotonic_ns",
    )
    bounds: dict[str, int] = {}
    for name in numeric_names:
        value = telemetry.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"telemetry_{name}_not_integer")
            bounds[name] = 0
        else:
            bounds[name] = value
    if not (
        bounds[numeric_names[0]]
        <= bounds[numeric_names[1]]
        < bounds[numeric_names[2]]
        <= bounds[numeric_names[3]]
    ):
        errors.append("telemetry_wall_bounds_invalid")
    contract = preregistration["telemetry_contract"]
    interval = telemetry.get("sample_interval_seconds")
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or float(interval) != float(contract["sample_interval_seconds"])
    ):
        errors.append("telemetry_sample_interval_invalid")
        interval = 1.0
    interval = float(interval)
    if telemetry.get("sampler_errors") != []:
        errors.append("telemetry_sampler_errors_not_empty")
    if telemetry.get("command_exit_code") != 0:
        errors.append("telemetry_command_exit_code_not_zero")
    preflight = telemetry.get("preflight")
    if not isinstance(preflight, dict):
        errors.append("telemetry_preflight_not_object")
    else:
        if preflight.get("no_other_kfd_processes") is not True:
            errors.append("telemetry_preflight_other_kfd_process")
        for name, maximum in (("gpu_use_percent", 5.0), ("vram_allocated_percent", 1.0)):
            value = preflight.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"telemetry_preflight_{name}_not_number")
            elif float(value) > maximum:
                errors.append(f"telemetry_preflight_{name}_too_high")

    samples = telemetry.get("samples")
    if not isinstance(samples, list) or len(samples) < 2:
        errors.append("telemetry_samples_insufficient")
        return
    timestamps: list[int] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"telemetry_sample_{index}_not_object")
            continue
        timestamp = sample.get("monotonic_ns")
        if isinstance(timestamp, bool) or not isinstance(timestamp, int):
            errors.append(f"telemetry_sample_{index}_timestamp_not_integer")
            continue
        timestamps.append(timestamp)
        if not isinstance(sample.get("device"), str):
            errors.append(f"telemetry_sample_{index}_device_not_string")
        for metric in (
            "gpu_use_percent",
            "vram_allocated_percent",
            "graphics_package_power_w",
        ):
            value = sample.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"telemetry_sample_{index}_{metric}_not_number")
            elif not math.isfinite(float(value)):
                errors.append(f"telemetry_sample_{index}_{metric}_not_finite")
    if len(timestamps) != len(samples):
        return
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        errors.append("telemetry_timestamps_not_strictly_increasing")
    if timestamps[0] > bounds["challenge_subprocess_started_monotonic_ns"]:
        errors.append("telemetry_does_not_cover_subprocess_start")
    if timestamps[-1] < bounds["challenge_subprocess_ended_monotonic_ns"]:
        errors.append("telemetry_does_not_cover_subprocess_end")
    if timestamps[0] < bounds["sampler_started_monotonic_ns"]:
        errors.append("telemetry_sample_before_sampler_start")
    if timestamps[-1] > bounds["sampler_ended_monotonic_ns"]:
        errors.append("telemetry_sample_after_sampler_end")
    max_gap_ns = int(float(contract["max_gap_seconds"]) * 1_000_000_000)
    if any(right - left > max_gap_ns for left, right in zip(timestamps, timestamps[1:])):
        errors.append("telemetry_sampling_gap_too_large")


def _validate_attempts_within_telemetry_wall(
    manifest: Mapping[str, Any], telemetry: Mapping[str, Any], errors: list[str]
) -> None:
    execution = manifest.get("execution")
    attempts = execution.get("attempts") if isinstance(execution, dict) else None
    if not isinstance(attempts, list) or len(attempts) != 60:
        return
    challenge_start = telemetry.get("challenge_subprocess_started_monotonic_ns")
    challenge_end = telemetry.get("challenge_subprocess_ended_monotonic_ns")
    if not isinstance(challenge_start, int) or not isinstance(challenge_end, int):
        return
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            continue
        started = attempt.get("started_monotonic_ns")
        ended = attempt.get("ended_monotonic_ns")
        if not isinstance(started, int) or not isinstance(ended, int):
            continue
        if started < challenge_start or ended > challenge_end:
            errors.append(f"run_manifest_attempt_{index}_outside_telemetry_wall")


def _parse_sha256sums(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.is_file():
        errors.append("sha256sums_missing")
        return {}
    entries: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if match is None:
            errors.append(f"sha256sums_invalid_line:{line_number}")
            continue
        digest, relative = match.groups()
        if not _safe_relative(relative):
            errors.append(f"sha256sums_unsafe_path:{line_number}")
            continue
        if relative in entries:
            errors.append(f"sha256sums_duplicate:{relative}")
        entries[relative] = digest
    return entries


def _validate_checksums(
    results_dir: Path, preregistration: Mapping[str, Any], errors: list[str]
) -> None:
    entries = _parse_sha256sums(results_dir / "SHA256SUMS", errors)
    required = {
        episode_relative_path(seed, policy)
        for seed in expected_seeds(preregistration)
        for policy in POLICIES
    } | {
        "RUN_MANIFEST.json",
        "ROCM_TELEMETRY.json",
        "CHALLENGE_REPORT.json",
        "raw/PRESTART_BINDING.json",
    }
    actual = {
        path.relative_to(results_dir).as_posix()
        for path in results_dir.rglob("*")
        if path.is_file() and path != results_dir / "SHA256SUMS"
    }
    for relative in sorted(required - actual):
        errors.append(f"required_result_file_missing:{relative}")
    if set(entries) != actual:
        for relative in sorted(actual - set(entries)):
            errors.append(f"sha256sums_entry_missing:{relative}")
        for relative in sorted(set(entries) - actual):
            errors.append(f"sha256sums_entry_unexpected:{relative}")
    for relative in sorted(actual & set(entries)):
        path = results_dir / relative
        if not path.is_file():
            errors.append(f"checksummed_file_missing:{relative}")
        elif file_sha256(path) != entries[relative]:
            errors.append(f"checksummed_file_digest_mismatch:{relative}")


def verify_challenge(
    results_dir: Path,
    preregistration_path: Path = DEFAULT_PREREGISTRATION,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    errors: list[str] = []
    preregistration = _load_object(
        preregistration_path, errors, "preregistration"
    )
    if preregistration is None:
        return {"passed": False, "errors": errors}
    preregistration_sha = file_sha256(preregistration_path)
    _validate_preregistration(preregistration, repo_root, errors)

    manifest = _load_object(results_dir / "RUN_MANIFEST.json", errors, "run_manifest")
    telemetry = _load_object(
        results_dir / "ROCM_TELEMETRY.json", errors, "telemetry"
    )
    report = _load_object(
        results_dir / "CHALLENGE_REPORT.json", errors, "challenge_report"
    )
    prestart_binding = _load_object(
        results_dir / "raw/PRESTART_BINDING.json", errors, "prestart_binding"
    )
    if manifest is not None:
        _validate_run_manifest(
            manifest, preregistration, preregistration_sha, errors
        )
    if manifest is not None and prestart_binding is not None:
        _validate_prestart_binding(
            prestart_binding,
            manifest,
            preregistration,
            preregistration_sha,
            errors,
        )
    if telemetry is not None:
        _validate_telemetry(telemetry, preregistration, errors)
    if manifest is not None and telemetry is not None:
        _validate_attempts_within_telemetry_wall(manifest, telemetry, errors)

    records = load_episode_records(results_dir, preregistration, errors)
    recomputed: dict[str, Any] | None = None
    if len(records) == 60 and manifest is not None and telemetry is not None:
        try:
            recomputed = expected_report(
                records, preregistration_sha, manifest, telemetry
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"analysis_recompute_failed:{exc.__class__.__name__}")
    if report is not None and recomputed is not None and report != recomputed:
        errors.append("challenge_report_does_not_match_raw_recomputation")

    _validate_checksums(results_dir, preregistration, errors)
    errors = sorted(set(errors))
    result: dict[str, Any] = {
        "schema_version": "look-twice.v8-frozen-challenge-verification/v1",
        "passed": not errors,
        "errors": errors,
        "preregistration_sha256": preregistration_sha,
        "raw_episode_records_read": len(records),
        "expected_raw_episode_records": 60,
        "evidence_boundary": {
            "runs_episode": False,
            "loads_checkpoint": False,
            "retries_failure": False,
            "modifies_artifacts": False,
            "motion_backend": "kinematic",
            "generator_family": "same_generator_reserved_challenge_subset",
        },
        "recomputed_report": recomputed,
    }
    result["verification_sha256"] = canonical_sha256(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument(
        "--preregistration", type=Path, default=DEFAULT_PREREGISTRATION
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for a copy of the verification result; inputs stay read-only",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output is not None:
        results_resolved = args.results_dir.resolve()
        output_resolved = args.output.resolve()
        if output_resolved == results_resolved or results_resolved in output_resolved.parents:
            raise SystemExit(
                "--output must be outside --results-dir; validation may not add a file to the checksummed result set"
            )
    result = verify_challenge(
        args.results_dir, args.preregistration, args.repo_root
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
