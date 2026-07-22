"""Version-neutral competition replay adapter for Look Twice candidates.

The public showcase consumes only the stable ReleaseProfile/EpisodeBundle
contracts produced here. Candidate-specific episode JSON never leaks into the
web UI, and oracle/private machine paths are excluded by construction.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

RELEASE_PROFILE_SCHEMA = "look-twice.release-profile/v1"
EPISODE_BUNDLE_SCHEMA = "look-twice.episode-bundle/v1"
BUILDER_VERSION = "look-twice.competition-replay-builder/1"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _public_claim(claim: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "claim_id",
        "fact_id",
        "predicate",
        "value",
        "confidence",
        "observed_step",
        "valid_until_step",
        "modality",
        "device_root_id",
        "capture_root_id",
        "calibration_id",
        "model_id",
        "artifact_sha256",
        "observer_agent_id",
        "intended_actor_id",
        "received_step",
        "parent_claim_ids",
        "quality",
        "visibility",
        "temporal_skew",
        "scope",
    )
    return {key: claim.get(key) for key in allowed if key in claim}


def _public_go_receipt(receipt: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not receipt:
        return None
    allowed = (
        "receipt_id",
        "action",
        "fact_id",
        "predicate",
        "scope",
        "evaluated_step",
        "valid_until_step",
        "admitted",
        "decision",
        "p_blocked",
        "prediction_set",
        "calibration_artifact_id",
        "calibration_applicable",
        "clauses",
        "used_claim_ids",
        "discounted_claims",
        "measurement_root_ids",
        "device_root_ids",
        "unresolved_conflicts",
        "belief_gaps",
        "assumptions",
        "receipt_sha256",
    )
    return {key: receipt.get(key) for key in allowed if key in receipt}


def _public_gate_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    go_receipt = _public_go_receipt(receipt.get("purify_go_receipt"))
    result = {
        "receipt_sha256": receipt.get("receipt_sha256"),
        "corridor_id": receipt.get("corridor_id"),
        "action": receipt.get("action"),
        "evaluated_step": int(receipt.get("evaluated_step") or 0),
        "valid_until_step": receipt.get("valid_until_step"),
        "decision": receipt.get("decision"),
        "admitted": bool(receipt.get("admitted")),
        "python_admitted": bool(receipt.get("python_admitted")),
        "purify_go_admitted": bool(receipt.get("purify_go_admitted")),
        "effective_admit": bool(receipt.get("effective_admit")),
        "p_blocked": receipt.get("p_blocked"),
        "reasons": list(receipt.get("reasons") or []),
        "belief_gaps": list(receipt.get("belief_gaps") or []),
        "measurement_root_ids": list(receipt.get("measurement_root_ids") or []),
        "claim_count": int(receipt.get("claim_count") or 0),
        "go_receipt": go_receipt,
    }
    return result


def _observation_step_lookup(episode: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    lookup: dict[tuple[str, str], int] = {}
    for audit in episode.get("rgbd_observation_audits") or []:
        corridor = str(audit.get("corridor_id") or "")
        viewpoint = str(audit.get("viewpoint") or "")
        if corridor and viewpoint:
            lookup.setdefault((corridor, viewpoint), int(audit.get("observed_step") or 0))
    return lookup


def _sensor_frames(
    episode: Mapping[str, Any],
    replay_id: str,
    media_root: Path | None = None,
    media_manifest_path: Path | None = None,
) -> list[dict[str, Any]]:
    step_lookup = _observation_step_lookup(episode)
    media_manifest: dict[str, Any] = {}
    if media_manifest_path is not None and media_manifest_path.is_file():
        raw_manifest = json.loads(media_manifest_path.read_text())
        media_manifest = {
            item["frame_id"]: item for item in raw_manifest.get("frames") or []
        }
    frames: list[dict[str, Any]] = []
    for index, audit in enumerate(episode.get("vision_audits") or []):
        corridor = str(audit.get("corridor_id") or "")
        viewpoint = str(audit.get("viewpoint") or "")
        input_sha = str(audit.get("input_sha256") or "")
        frame_id = f"frame-{index + 1}"
        media_names = {
            "rgb": f"frame-{index + 1}-rgb.webp",
            "depth": f"frame-{index + 1}-depth.webp",
            "corridor_mask": f"frame-{index + 1}-mask.webp",
        }
        available = bool(media_root) and all(
            (media_root / name).is_file() for name in media_names.values()
        )
        frames.append(
            {
                "frame_id": frame_id,
                "step": step_lookup.get((corridor, viewpoint), index),
                "corridor_id": corridor,
                "viewpoint": viewpoint,
                "observer_agent_id": audit.get("observer_agent_id"),
                "value": audit.get("value"),
                "p_blocked": audit.get("p_blocked"),
                "prediction_set": list(audit.get("prediction_set") or []),
                "quality": audit.get("quality"),
                "visibility": audit.get("visibility"),
                "tensor_device": audit.get("tensor_device"),
                "input_sha256": input_sha,
                "checkpoint_sha256": audit.get("checkpoint_sha256"),
                "conformal_artifact_sha256": audit.get(
                    "conformal_artifact_sha256"
                ),
                "media": {
                    **{
                        key: f"/data/media/{replay_id}/{name}"
                        for key, name in media_names.items()
                    },
                    "available": available,
                    "sha256": (media_manifest.get(frame_id) or {}).get(
                        "media_sha256", {}
                    ),
                },
            }
        )
    return frames


def _measurement_roots(claims: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    metadata: dict[str, dict[str, Any]] = {}
    for claim in claims:
        # Modalities derived from the same physical capture collapse to one
        # public measurement root even if runtime adapters used distinct wire IDs.
        step = claim.get("observed_step")
        observer = str(claim.get("observer_agent_id") or "unknown")
        root = f"measurement:{step}:{observer}"
        grouped[root].append(str(claim.get("claim_id") or ""))
        item = metadata.setdefault(root, {"measurement_root_id": root, "observer_agent_id": claim.get("observer_agent_id"), "observed_step": step, "source_capture_root_ids": set(), "device_root_ids": set()})
        item["source_capture_root_ids"].add(str(claim.get("capture_root_id") or "unknown"))
        item["device_root_ids"].add(str(claim.get("device_root_id") or "unknown"))
    return [
        {
            **metadata[root],
            "source_capture_root_ids": sorted(metadata[root]["source_capture_root_ids"]),
            "device_root_ids": sorted(metadata[root]["device_root_ids"]),
            "claim_ids": sorted(grouped[root]),
        }
        for root in sorted(grouped)
    ]


def _repair_requests(episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, receipt in enumerate(episode.get("evidence_request_receipts") or []):
        results.append(
            {
                "request_id": receipt.get("receipt_id") or f"request-{index + 1}",
                "authorized": bool(receipt.get("authorized")),
                "selected_observer": receipt.get("selected_observer"),
                "target_viewpoint": receipt.get("target_viewpoint"),
                "target_fact_id": receipt.get("target_fact_id"),
                "target_scope": receipt.get("target_scope"),
                "expected_gap_repairs": list(
                    receipt.get("expected_gap_repairs") or []
                ),
                "candidate_ranking_sha256": receipt.get(
                    "candidate_ranking_sha256"
                ),
                "physical_risk": receipt.get("physical_risk"),
                "valid_until_step": receipt.get("valid_until_step"),
                "receipt_sha256": receipt.get("receipt_sha256"),
            }
        )
    return results


def _nbv_candidates(episode: Mapping[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, decision in enumerate(episode.get("repair_decisions") or []):
        ranking = []
        for candidate in decision.get("ranking_head") or []:
            ranking.append(dict(candidate))
        results.append(
            {
                "decision_id": f"nbv-{index + 1}",
                "authorized": bool(decision.get("authorized")),
                "selected": dict(decision.get("selected") or {}),
                "ranking": ranking,
                "alignment_score": decision.get("nbv_alignment_score"),
                "contamination_risk": decision.get("nbv_contamination_risk"),
                "selection_reason": decision.get("nbv_selection_reason"),
                "same_side": decision.get("nbv_same_side"),
            }
        )
    return results


def _events(
    sensor_frames: list[Mapping[str, Any]],
    gates: list[Mapping[str, Any]],
    requests: list[Mapping[str, Any]],
    outcome: Mapping[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in sensor_frames:
        events.append(
            {
                "event_id": f"observe-{frame['frame_id']}",
                "step": int(frame.get("step") or 0),
                "type": "observation",
                "status": frame.get("value") or "inconclusive",
                "title_key": "event.observation",
                "ref_id": frame["frame_id"],
            }
        )
    for index, gate in enumerate(gates):
        events.append(
            {
                "event_id": f"gate-{index + 1}",
                "step": int(gate.get("evaluated_step") or 0),
                "type": "gate_decision",
                "status": "admitted" if gate.get("effective_admit") else "denied",
                "title_key": "event.gate",
                "ref_id": gate.get("receipt_sha256"),
            }
        )
    deny_steps: list[int] = [
        int(gate.get("evaluated_step") or 0)
        for gate in gates
        if not gate.get("effective_admit")
    ]
    for index, request in enumerate(requests):
        inferred = deny_steps[min(index, max(0, len(deny_steps) - 1))] if deny_steps else 0
        events.append(
            {
                "event_id": f"repair-{index + 1}",
                "step": inferred,
                "type": "evidence_request",
                "status": "authorized" if request.get("authorized") else "denied",
                "title_key": "event.repair",
                "ref_id": request.get("request_id"),
            }
        )
    final_step = max([int(e.get("step") or 0) for e in events] or [0]) + 1
    events.append(
        {
            "event_id": "outcome",
            "step": final_step,
            "type": "outcome",
            "status": outcome.get("route_mode") or "denied",
            "title_key": "event.outcome",
            "ref_id": "outcome",
        }
    )
    priority = {"observation": 0, "gate_decision": 1, "evidence_request": 2, "outcome": 3}
    events.sort(key=lambda item: (item["step"], priority.get(item["type"], 9), item["event_id"]))
    return events


def adapt_v8_episode(
    episode_path: str | Path,
    *,
    replay_id: str,
    frozen_identity: Mapping[str, str],
    media_root: str | Path | None = None,
    media_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(episode_path)
    episode = json.loads(path.read_text(encoding="utf-8"))
    scenario = episode.get("scenario") or {}
    public_context = scenario.get("public_context") or {}
    configuration = episode.get("configuration") or {}
    environment = episode.get("environment") or {}
    metrics = episode.get("metrics") or {}
    claims = [_public_claim(item) for item in episode.get("claims") or []]
    gates = [_public_gate_receipt(item) for item in episode.get("gate_receipts") or []]
    requests = _repair_requests(episode)
    media_path = Path(media_root) if media_root is not None else None
    media_manifest = (
        Path(media_manifest_path) if media_manifest_path is not None else None
    )
    sensor_frames = _sensor_frames(
        episode, replay_id, media_path, media_manifest
    )
    outcome = {
        "mission_success": bool(metrics.get("mission_success")),
        "unsafe_crossing": bool(metrics.get("unsafe_crossing")),
        "route_mode": metrics.get("route_mode"),
        "repair_attempted": bool(metrics.get("repair_attempted")),
        "repair_success": bool(metrics.get("repair_success")),
        "initial_gate_denied": bool(metrics.get("initial_gate_denied")),
        "new_capture_root_added": bool(metrics.get("new_capture_root_added")),
        "selected_corridor": metrics.get("selected_corridor"),
        "observation_count": int(metrics.get("observation_count") or 0),
        "replan_count": int(metrics.get("replan_count") or 0),
    }
    bundle: dict[str, Any] = {
        "schema_version": EPISODE_BUNDLE_SCHEMA,
        "candidate_id": "v8-frozen",
        "episode_meta": {
            "replay_id": replay_id,
            "scenario_id": scenario.get("scenario_id"),
            "profile": scenario.get("profile"),
            "seed": scenario.get("seed"),
            "policy": configuration.get("policy") or metrics.get("policy"),
            "runtime": environment.get("runtime"),
            "device": environment.get("device") or metrics.get("device"),
            "gpu": environment.get("gpu"),
            "claims_mode": environment.get("claims_mode"),
            "corridors": public_context.get("corridors") or [],
            "source_partition": "confirmatory-non-locked",
            "recorded_gpu_evidence": True,
            "simulation_only": True,
            "frozen_candidate_artifact": True,
            "live_gpu_dependency": False,
        },
        "sensor_frames": sensor_frames,
        "claims": claims,
        "measurement_roots": _measurement_roots(claims),
        "gate_receipts": gates,
        "repair_requests": requests,
        "nbv_candidates": _nbv_candidates(episode),
        "motion_segments": list(episode.get("motion_segments") or []),
        "events": [],
        "outcome": outcome,
        "integrity": {
            "builder_version": BUILDER_VERSION,
            "source_episode_sha256": file_sha256(path),
            "frozen_identity": dict(frozen_identity),
            "recorded_media_manifest_sha256": (
                file_sha256(media_manifest)
                if media_manifest is not None and media_manifest.is_file()
                else None
            ),
        },
    }
    bundle["events"] = _events(sensor_frames, gates, requests, outcome)
    bundle["integrity"]["bundle_sha256"] = canonical_sha256(bundle)
    return bundle


def build_v8_release_profile(
    *,
    replay_ids: list[str],
    locked_report: Mapping[str, Any],
    frozen_identity: Mapping[str, str],
) -> dict[str, Any]:
    live = locked_report["live_fullchain"]
    gates = live["gates"]
    profile: dict[str, Any] = {
        "schema_version": RELEASE_PROFILE_SCHEMA,
        "candidate_id": "v8-frozen",
        "display_name": "Look Twice",
        "tagline": {
            "en": "Active evidence assurance for Physical AI",
            "zh": "Physical AI 主动证据保障层",
        },
        "capabilities": [
            "spatially_grounded_rgbd",
            "lineage_aware_claims",
            "conformal_prediction_sets",
            "purify_action_authorization",
            "active_evidence_repair",
            "fail_closed_detour",
        ],
        "headline_metrics": [
            {
                "metric_id": "locked_active_full_chain",
                "value": int(gates["active_full_chain_direct"]),
                "denominator": int(gates["n_active"]),
                "label": {
                    "en": "Locked active repair chains",
                    "zh": "Locked 主动修证据闭环",
                },
                "source": "locked_test_v8_once/LOCKED_TEST_REPORT.json",
            },
            {
                "metric_id": "locked_unsafe",
                "value": int(gates["unsafe_total"]),
                "denominator": int(gates["n_active"] + gates["n_passive"]),
                "label": {"en": "Unsafe crossings", "zh": "不安全穿越"},
                "source": "locked_test_v8_once/LOCKED_TEST_REPORT.json",
            },
        ],
        "artifact_identities": [
            {"artifact": key, "sha256": value}
            for key, value in sorted(frozen_identity.items())
        ],
        "limitations": [
            {
                "en": "Simulation only; no real-robot or certified-safety claim.",
                "zh": "仅为仿真验证，不声称真实机器人或安全认证。",
            },
            {
                "en": "The public Purify Robotics Core is a contest reference implementation.",
                "zh": "公开的 Purify Robotics Core 是比赛参考实现。",
            },
        ],
        "experiment_links": [
            {
                "label": "V8 locked test",
                "href": "/data/source/LOCKED_TEST_REPORT.json",
            }
        ],
        "default_replays": replay_ids,
    }
    profile["profile_sha256"] = canonical_sha256(profile)
    return profile


def assert_public_bundle(bundle: Mapping[str, Any]) -> None:
    encoded = json.dumps(bundle, sort_keys=True)
    forbidden = ("/workspace/", "/Users/", "root@", "oracle_context", '"oracle"')
    for token in forbidden:
        if token in encoded:
            raise ValueError(f"public replay contains forbidden token: {token}")
    claim_ids = {str(item.get("claim_id")) for item in bundle.get("claims") or []}
    for root in bundle.get("measurement_roots") or []:
        unknown = set(root.get("claim_ids") or []) - claim_ids
        if unknown:
            raise ValueError(f"measurement root references unknown claims: {unknown}")
    steps = [int(item.get("step") or 0) for item in bundle.get("events") or []]
    if steps != sorted(steps):
        raise ValueError("events are not monotonic")


__all__ = (
    "BUILDER_VERSION",
    "EPISODE_BUNDLE_SCHEMA",
    "RELEASE_PROFILE_SCHEMA",
    "adapt_v8_episode",
    "assert_public_bundle",
    "build_v8_release_profile",
    "canonical_sha256",
    "file_sha256",
)
