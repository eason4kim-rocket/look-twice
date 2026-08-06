"""Pure-Python tests for the contract-progress formal evidence surface."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from tests.test_v8_contract_progress_nbv import (
        _FakePurifyBridge,
        _RGBDKinematicRuntime,
        _fake_process_genesis,
        _proposal,
    )
except ModuleNotFoundError:
    from test_v8_contract_progress_nbv import (
        _FakePurifyBridge,
        _RGBDKinematicRuntime,
        _fake_process_genesis,
        _proposal,
    )
from v6_episode import V6EpisodeConfig, run_v6_episode
from v6_scenario import sample_v6_scenario

from scripts.run_v8_contract_progress_challenge import (
    _anonymous_git_environment,
    _resolve_python,
    build_episode_command,
    clean_gpu_preflight,
    durably_persist_attempt_files,
    verify_two_commit_binding,
    write_postrun_binding,
    write_checksum_index,
)
from scripts.verify_v8_contract_progress_challenge import (
    CANDIDATE_POLICY,
    CANDIDATE_SOURCE_TREE_ALGORITHM,
    EXPECTED_CHECKPOINT_SHA256,
    EXPECTED_GO_ARTIFACT_SHA256,
    EXPECTED_GO_FILE_SHA256,
    EXPECTED_IDENTITY_MANIFEST_SHA256,
    EXPECTED_PURIFY_SHA256,
    EXPECTED_RUNTIME_MANIFEST_SHA256,
    EXPECTED_RUNTIME_TREE_SHA256,
    EXPECTED_SOURCE_TREE_SHA256,
    EXPECTED_VISION_ARTIFACT_SHA256,
    EXPECTED_VISION_FILE_SHA256,
    GO_CALIBRATION_ID,
    MANIFEST_SCHEMA,
    POLICY_ARTIFACT_ID,
    PRESTART_SCHEMA,
    POSTRUN_SCHEMA,
    PROFILE,
    PREREG_SCHEMA,
    VerificationError,
    authenticate_output_go_receipts,
    build_schedule,
    derive_episode_row,
    derive_report,
    file_sha256,
    read_json_object,
    schedule_sha256,
    validate_preregistration,
    validate_postrun_binding,
    verify_candidate_source_closure,
    verify_output,
)


VISION_CALIBRATION_ID = f"look-twice-v8-spatial:{EXPECTED_VISION_ARTIFACT_SHA256[:16]}"


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_v8_contract_progress_challenge.py"
VERIFIER = ROOT / "scripts" / "verify_v8_contract_progress_challenge.py"
RUNNER_MODULE = clean_gpu_preflight.__module__
RUNNER_VERIFICATION_ERROR = clean_gpu_preflight.__globals__["VerificationError"]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _bind_candidate_evidence_requests(
    payload: dict, *, steps: list[int] | None = None
) -> None:
    receipts = []
    for index, decision in enumerate(payload.get("repair_decisions", [])):
        selected = decision.get("selected")
        authorized = decision.get("authorized") is True
        decision["execution_status"] = (
            "authorized_for_execution" if authorized else "authorization_denied_noop"
        )
        reasons = [] if authorized else ["max_replans_reached"]
        ranking_sha = hashlib.sha256(f"ranking:{index}".encode()).hexdigest()
        step = steps[index] if steps is not None else index + 1
        if selected is None:
            body = {
                "authorized": False,
                "step": step,
                "reasons": reasons,
                "ranking": ranking_sha,
            }
            observer = viewpoint = fact = scope = None
            risk = 0.0
        else:
            name = str(selected.get("name") or "")
            observer = str(selected.get("observer") or "") or None
            viewpoint = str(selected.get("viewpoint") or name) or None
            corridor = str(selected.get("corridor_id") or "")
            fact = f"region:{corridor}" if corridor else None
            scope = (
                {
                    "robot_id": "carrier",
                    "payload_id": "payload_loaded",
                    "region_id": corridor,
                }
                if corridor
                else None
            )
            risk = float(selected.get("physical_risk") or 0.0)
            body = {
                "authorized": authorized,
                "name": name,
                "observer": observer or "",
                "viewpoint": viewpoint or "",
                "step": step,
                "reasons": reasons,
                "ranking": ranking_sha,
                "policy": POLICY_ARTIFACT_ID,
            }
        receipt_sha = hashlib.sha256(
            json.dumps(
                body,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        decision["evidence_request_receipt_sha256"] = receipt_sha
        receipts.append(
            {
                "schema_version": "look-twice.evidence-request-receipt/v1",
                "receipt_id": f"evr_{receipt_sha[:20]}",
                "authorized": authorized,
                "selected_observer": observer,
                "target_viewpoint": viewpoint,
                "target_fact_id": fact,
                "target_scope": scope,
                "expected_gap_repairs": ["insufficient_roots"],
                "policy_artifact_id": POLICY_ARTIFACT_ID,
                "candidate_ranking_sha256": ranking_sha,
                "physical_risk": risk,
                "valid_until_step": step + 40,
                "receipt_sha256": receipt_sha,
                "reasons": reasons,
            }
        )
    payload["evidence_request_receipts"] = receipts


def _bound_prereg() -> dict:
    source_paths = [
        "src/v8_contract_progress_nbv.py",
        "src/v8_spatial_runtime.py",
        "src/v8_seg_v3_model.py",
        "src/v7_vision_claims.py",
        "src/v6_episode.py",
        "src/v7_episode.py",
        "src/look_twice_v7.py",
    ]
    candidate_tree_sha = hashlib.sha256(
        "".join(f"{'0' * 64}  {path}\n" for path in sorted(source_paths)).encode()
    ).hexdigest()
    return {
        "schema_version": PREREG_SCHEMA,
        "status": "PREREGISTERED_BEFORE_ANY_CHALLENGE_EPISODE",
        "created_utc": "2026-08-05T00:00:00Z",
        "protocol_path": "docs/V8_CONTRACT_PROGRESS_CHALLENGE_PROTOCOL.md",
        "public_binding": {
            "method": "two_commit_public_preregistration",
            "remote_name": "origin",
            "commit_a": "a" * 40,
            "commit_b": "SELF_NOT_EMBEDDED_CURRENT_CLEAN_HEAD_RECORDED_AT_PRESTART",
            "commit_b_diff_from_a_may_only_change": (
                "release/v8-derived/contract_progress_challenge_102530_102549/"
                "PREREGISTRATION.json"
            ),
            "fresh_seed_opened_before_commit_b": False,
        },
        "design": {
            "seed_start": 102530,
            "seed_end": 102549,
            "seeds": list(range(102530, 102550)),
            "n_worlds": 20,
            "n_episodes": 40,
            "profile": PROFILE,
            "baseline_policy": "purify-active-vision",
            "candidate_policy": CANDIDATE_POLICY,
            "candidate_policy_artifact_id": POLICY_ARTIFACT_ID,
            "seed_order": "strictly_ascending",
            "paired_by_seed": True,
            "within_seed_order_rule": {
                "even_seed": ["purify-active-vision", CANDIDATE_POLICY],
                "odd_seed": [CANDIDATE_POLICY, "purify-active-vision"],
            },
            "attempts_per_seed_policy": 1,
            "retry_count_allowed": 0,
            "seed_substitution_allowed": False,
            "early_stopping_allowed": False,
            "resume_allowed": False,
            "continue_after_bad_outcome": True,
            "persist_every_attempt_locally": True,
            "retuning_allowed": False,
            "checkpoint_changes_allowed": False,
            "calibration_changes_allowed": False,
            "gate_changes_allowed": False,
            "threshold_changes_allowed": False,
            "episode_timeout_seconds": 300,
        },
        "candidate_algorithm_contract": {
            "intervention_type": "compound_v8_system_intervention",
            "intervention_pipeline": [
                "one_initial_physical_rgbd_capture",
                "one_shared_frozen_seg_v3_backbone_forward",
                "two_corridor_scoped_roi_proposals",
                "geometry_vision_physical_capture_root_unification",
                "contract_debt_then_online_go_p_blocked_then_travel_nbv",
            ],
            "frozen_components": [
                "seg_v3_checkpoint",
                "vision_conformal_thresholds",
                "go_conformal_thresholds",
                "purify_gate_rules",
                "world_generator",
                "kinematic_motion_backend",
            ],
            "attribution": (
                "overall_v8_plus_compound_intervention_not_planner_only_"
                "or_shared_capture_only"
            ),
            "contract_debt_source": (
                "latest_applicable_online_purify_go_receipt_"
                "distinct_measurement_roots_clause"
            ),
            "corridor_order": [
                "lower_repair_step_debt",
                "lower_online_go_p_blocked",
                "lower_public_geometry_scout_travel_distance",
                "stable_deterministic_ties",
            ],
            "allowed_inputs": [
                "current_corridor_scoped_purify_go_receipts",
                "effective_python_go_decisions",
                "public_map_geometry",
                "current_robot_poses",
                "public_candidate_actions",
                "visit_history",
                "online_claim_derived_confirmed_blocked_set",
                "observations_taken",
                "max_observations",
                "side_observations_per_corridor",
                "max_side_observation_budget_per_corridor",
            ],
            "forbidden_inputs": [
                "scenario_seed",
                "oracle_state",
                "future_image",
                "clean_segmentation",
                "noise_realization",
                "retry_outcome",
            ],
            "go_p_blocked_semantics": (
                "online_receipt_value_not_oracle_occupancy_or_new_calibration"
            ),
            "go_measurement_root_debt_definition": (
                "max(required_roots_minus_actual_roots,0)"
            ),
            "repair_step_debt_rule": (
                "measurement_root_debt_if_positive_else_one_for_"
                "otherwise_repairable_denied_gate"
            ),
            "chosen_ranking_debt_fields_required": True,
            "malformed_missing_inapplicable_or_hard_deny_receipt": "fail_closed",
            "fail_closed_delegation": (
                "audited_frozen_v8_public_probe_or_safe_detour_only_"
                "never_direct_admission"
            ),
            "chosen_ranking_go_p_blocked_required": True,
            "chosen_ranking_go_receipt_sha256_required": True,
            "evidence_request_receipt_rehash_and_decision_binding": True,
            "go_receipt_time_binding": (
                "evaluated_step_equals_strictly_increasing_"
                "evidence_request_current_step"
            ),
            "authorized_execution_closure_required": True,
            "terminal_budget_denied_side_view": (
                "proposal_only_noop_after_exactly_three_authorized_side_views"
            ),
            "safe_fallback_semantics": (
                "final_route_control_noop_with_raw_safe_detour_proof"
            ),
        },
        "population_boundary": {
            "generator_family": "same_generator_as_v8_spatial_dataset_v1",
            "challenge_subset": [102530, 102549],
            "same_generator": True,
            "non_locked": True,
            "not_ood": True,
            "not_physical_robot": True,
            "formal_result_eligible": False,
        },
        "runtime_contract": {
            "runtime": "genesis-amd",
            "motion_backend": "kinematic",
            "device": "cuda:0",
            "vision_backend": "torch_spatial_rgbd",
            "repair_required": True,
            "purify_go_gate": True,
            "heuristic_fallback_allowed": False,
            "audited_fail_closed_frozen_v8_probe_delegation_allowed": True,
            "baseline_and_candidate_source_roots_must_differ": True,
            "baseline_exact_python_file_set_required": True,
            "baseline_exact_src_file_set_required": True,
            "candidate_exact_git_tracked_src_closure_required": True,
            "python_user_site_allowed": False,
            "python_bytecode_writes_allowed": False,
            "anonymous_public_remote_head_required": True,
            "postrun_local_and_live_remote_revalidation_required": True,
            "formal_output_outside_both_source_roots": True,
            "frozen_go_binary_receipt_authentication_required": True,
            "python_launcher_and_resolved_target_identity_required": True,
            "attempt_fixed_argv_exact_reconstruction_required": True,
            "clean_gpu_kfd_and_idle_preflight_required": True,
            "attempt_artifacts_fsynced_before_attempt_record": True,
            "go_authentication_adverse_result_report_required": True,
            "malformed_episode_adverse_result_report_required": True,
            "runner_attempt_integrity_is_provisional_until_frozen_go_auth": True,
            "git_replace_objects_disabled": True,
            "git_status_fsmonitor_and_untracked_cache_disabled": True,
            "output_creation_only": True,
            "raw_failures_retained": True,
            "process_group_timeout_kill": True,
        },
        "identities": {
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "vision_conformal_file_sha256": EXPECTED_VISION_FILE_SHA256,
            "vision_conformal_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
            "go_conformal_file_sha256": EXPECTED_GO_FILE_SHA256,
            "go_conformal_artifact_sha256": EXPECTED_GO_ARTIFACT_SHA256,
            "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
            "identity_manifest_file_sha256": EXPECTED_IDENTITY_MANIFEST_SHA256,
            "source_tree_fingerprint_sha256": EXPECTED_SOURCE_TREE_SHA256,
            "baseline_runtime_source_manifest_file_sha256": EXPECTED_RUNTIME_MANIFEST_SHA256,
            "baseline_runtime_source_tree_fingerprint_sha256": EXPECTED_RUNTIME_TREE_SHA256,
            "candidate_tracked_src_tree_fingerprint_algorithm": (
                CANDIDATE_SOURCE_TREE_ALGORITHM
            ),
            "candidate_tracked_src_file_count": len(source_paths),
            "candidate_tracked_src_tree_fingerprint_sha256": candidate_tree_sha,
            "baseline_runtime_source_manifest_path": (
                "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
            ),
            "runner_path": "scripts/run_v8_contract_progress_challenge.py",
            "runner_sha256": file_sha256(RUNNER),
            "verifier_path": "scripts/verify_v8_contract_progress_challenge.py",
            "verifier_sha256": file_sha256(VERIFIER),
            "candidate_source_files": [
                {"path": path, "sha256": "0" * 64} for path in source_paths
            ],
        },
        "mandatory_gates": {
            "valid_attempts_required": 40,
            "mission_success_required": 40,
            "unsafe_allowed": 0,
            "false_clear_allowed": 0,
            "fallback_allowed": 0,
            "collision_allowed": 0,
            "exact_v8_identity_every_episode": True,
            "purify_invoked_every_episode": True,
            "candidate_policy_artifact_id_every_candidate_episode": True,
            "repair_decision_selected_chosen_alignment_every_episode": True,
            "candidate_selector_invoked_every_candidate_episode": True,
            "candidate_selected_equals_chosen_action_every_decision": True,
            "candidate_evidence_request_receipt_rehashed_every_decision": True,
            "candidate_decision_steps_strictly_increasing": True,
            "candidate_go_receipt_exactly_then_current_every_decision": True,
            "candidate_authorized_execution_closure_every_episode": True,
            "native_chosen_required_for_each_repairable_selector_decision": True,
            "zero_native_allowed_only_for_strict_raw_no_repairable_delegation": True,
            "delegated_policy_provenance_every_delegated_item": True,
            "terminal_noop_only_under_exact_budget_and_route_proof": True,
            "compound_intervention_raw_execution_every_candidate_episode": True,
            "compound_initial_capture_raw_binding_every_candidate_episode": True,
            "candidate_helper_absent_from_every_baseline_episode": True,
            "every_chosen_side_view_has_same_corridor_go_p_blocked": True,
            "every_chosen_side_view_has_same_corridor_go_receipt_binding": True,
            "candidate_direct_count_not_below_baseline": True,
            "paired_baseline_direct_to_candidate_nondirect_allowed": 0,
        },
        "capability_gates": {
            "scout_path_relative_reduction_min": 0.25,
            "team_path_relative_reduction_min": 0.1,
            "physical_capture_relative_reduction_min": 0.2,
            "physical_capture_definition": (
                "metrics.observation_count_equal_to_len_metrics.viewpoints_sequence"
            ),
            "vision_proposals_are_not_physical_captures": True,
            "denominator": "all_20_paired_worlds",
        },
        "reporting_contract": {
            "raw_episode_files_expected": 40,
            "per_seed_rows_required": 20,
            "paired_deltas_required": True,
            "mean_median_min_max_required": True,
            "deterministic_paired_bootstrap_95_required": True,
            "wilson_95_for_direct_rates_required": True,
            "carrier_scout_team_path_required": True,
            "physical_capture_and_vision_proposal_counts_separate": True,
            "exact_path_set_required": True,
            "sha256_index_required": True,
            "postrun_immutable_binding_required": True,
            "adverse_no_receipt_run_must_still_report": True,
            "malformed_episode_must_still_report": True,
            "runner_true_to_verifier_false_downgrade_must_still_report": True,
            "no_result_may_be_deleted_replaced_or_rerun": True,
            "sealed_pdf_or_submission_package_may_be_modified": False,
        },
    }


def _episode(spec: dict) -> dict:
    candidate = spec["arm"] == "candidate"
    scout = 2.8 if candidate else 4.0
    captures = 2 if candidate else 5
    viewpoints = (
        ["carrier_initial_front", "corridor_b/left_far"]
        if candidate
        else [f"capture-{index}" for index in range(captures)]
    )
    go_receipt = {
        "schema_version": "purify.robotics.gate-receipt/v1",
        "receipt_id": "gate-test-corridor-b",
        "contract_id": "cross-corridor_b",
        "action": "cross_corridor",
        "fact_id": "region:corridor_b",
        "predicate": "carrier_traversable",
        "receipt_sha256": "d" * 64,
        "scope": {
            "robot_id": "carrier",
            "payload_id": "payload_loaded",
            "region_id": "corridor_b",
        },
        "evaluated_step": 1,
        "valid_until_step": 2001,
        "admitted": False,
        "decision": "denied",
        "p_blocked": 0.02,
        "prediction_set": ["clear"],
        "calibration_artifact_id": GO_CALIBRATION_ID,
        "calibration_applicable": True,
        "clauses": [
            {
                "clause": "prediction_set",
                "actual": ["clear"],
                "required": ["clear"],
                "passed": True,
            },
            {
                "clause": "evidence_age",
                "actual": 0,
                "required": 80,
                "passed": True,
            },
            {
                "clause": "distinct_measurement_roots",
                "actual": 1,
                "required": 2,
                "passed": False,
            },
            {
                "clause": "modality_skew",
                "actual": 0,
                "required": 40,
                "passed": True,
            },
            {
                "clause": "unresolved_conflicts",
                "actual": 0,
                "required": 0,
                "passed": True,
            },
            {
                "clause": "calibration_applicable",
                "actual": True,
                "required": True,
                "passed": True,
            },
            {
                "clause": "scope_match",
                "actual": True,
                "required": True,
                "passed": True,
            },
        ],
        "used_claim_ids": [],
        "discounted_claims": [],
        "measurement_root_ids": ["capture-root-0"],
        "device_root_ids": ["device-root-0"],
        "unresolved_conflicts": [],
        "belief_gaps": [{"reason": "insufficient_roots"}],
        "assumptions": [],
        "_purify_invoked": True,
        "_purify_binary_sha256": EXPECTED_PURIFY_SHA256,
        "_go_calibration_artifact_id": GO_CALIBRATION_ID,
        "_runtime_calibration_id": VISION_CALIBRATION_ID,
        "_n_claims_sent": 1,
    }
    claims = []
    audits = []

    def add_capture(
        index: int,
        geometry_corridor: str,
        proposal_corridors: list[str],
        *,
        shared: bool = False,
    ) -> None:
        capture_root = f"capture-root-{index}"
        device_root = f"device-root-{index}"
        claims.append(
            {
                "claim_id": f"geometry-{index}",
                "modality": "depth_geometry",
                "scope": {"region_id": geometry_corridor},
                "capture_root_id": capture_root,
                "device_root_id": device_root,
                "value": "inconclusive",
                "quality": 0.8,
                "visibility": 0.8,
                "observed_step": index,
                "received_step": index,
            }
        )
        for proposal_index, corridor in enumerate(proposal_corridors):
            model_id = f"model-{index}-{corridor}"
            input_sha = hashlib.sha256(
                f"{index}:{corridor}:{proposal_index}".encode()
            ).hexdigest()
            claim = {
                "claim_id": f"vision-{index}-{corridor}",
                "modality": "vision_semantic_v7",
                "scope": {"region_id": corridor},
                "capture_root_id": capture_root,
                "device_root_id": device_root,
                "model_id": model_id,
                "artifact_sha256": input_sha,
                "value": "clear",
                "quality": 0.9,
                "visibility": 0.9,
                "observed_step": index,
                "received_step": index,
            }
            claims.append(claim)
            audit = {
                "kind": "vision_proposal_v7",
                "vision_source": "genesis_rgb",
                "corridor_id": corridor,
                "observer_agent_id": "carrier" if index == 0 else "scout",
                "viewpoint": viewpoints[index],
                "physical_capture_root_bound": True,
                "physical_capture_root_id": capture_root,
                "physical_device_root_id": device_root,
                "model_id": model_id,
                "input_sha256": input_sha,
            }
            if shared:
                audit.update(
                    {
                        "shared_initial_ab_capture": True,
                        "shared_rgbd_backbone": True,
                        "features": {"shared_rgbd_backbone": 1.0},
                        "shared_physical_capture_root_id": capture_root,
                        "shared_device_root_id": device_root,
                        "shared_initial_a_mask_source": ("raw_frame.corridor_mask"),
                        "shared_initial_b_mask_source": ("public_geometry_projection"),
                        "shared_geometry_pose_semantics": ("legacy_default_empty"),
                    }
                )
            audits.append(audit)

    if candidate:
        add_capture(0, "corridor_a", ["corridor_a", "corridor_b"], shared=True)
        add_capture(1, "corridor_b", ["corridor_b"])
    else:
        for index in range(captures):
            corridor = "corridor_a" if index % 2 == 0 else "corridor_b"
            add_capture(index, corridor, [corridor])

    decisions = []
    if candidate:
        decisions = [
            {
                "selected": {
                    "kind": "side_view",
                    "name": "scout_b_left_far",
                    "observer": "scout",
                    "corridor_id": "corridor_b",
                    "viewpoint": "corridor_b/left_far",
                    "physical_risk": 0.0,
                    "target_xy": [0.5, 1.0],
                    "predicted_coverage": 0.8,
                    "predicted_degradation": 0.1,
                    "reachable": True,
                    "travel_cost": 0.5,
                    "wait_steps": 0,
                },
                "authorized": True,
                "policy_artifact_id": POLICY_ARTIFACT_ID,
                "contract_progress_nbv_enabled": True,
                "contract_progress_selector_invoked": True,
                "contract_progress_no_repairable_contract": False,
                "contract_progress_selector_selection_reason": (
                    "chosen_min_contract_debt_then_go_p_then_travel"
                ),
                "contract_progress_selector_corridor_audit": {
                    "corridor_a": {
                        "go_receipt_sha256": None,
                        "go_p_blocked": None,
                        "roots_actual": None,
                        "roots_required": None,
                        "go_measurement_root_debt": None,
                        "repair_step_debt": None,
                        "fail_closed_reasons": ["missing_go_receipt"],
                    },
                    "corridor_b": {
                        "go_receipt_sha256": "d" * 64,
                        "go_p_blocked": 0.02,
                        "roots_actual": 1,
                        "roots_required": 2,
                        "go_measurement_root_debt": 1,
                        "repair_step_debt": 1,
                        "fail_closed_reasons": [],
                    },
                },
                "delegated_baseline_fail_closed": False,
                "ranking_head": [
                    {
                        "action": {
                            "kind": "side_view",
                            "name": "scout_b_left_far",
                            "corridor_id": "corridor_b",
                            "observer": "scout",
                            "viewpoint": "corridor_b/left_far",
                            "target_xy": [0.5, 1.0],
                            "predicted_coverage": 0.8,
                            "predicted_degradation": 0.1,
                            "physical_risk": 0.0,
                            "reachable": True,
                            "travel_cost": 0.5,
                            "wait_steps": 0,
                        },
                        "chosen": True,
                        "policy_artifact_id": POLICY_ARTIFACT_ID,
                        "go_p_blocked": 0.02,
                        "go_receipt_sha256": "d" * 64,
                        "go_measurement_root_debt": 1,
                        "repair_step_debt": 1,
                    }
                ],
            }
        ]
    payload = {
        "schema_version": "look-twice.episode/v7",
        "scenario": {"seed": spec["seed"], "profile": PROFILE},
        "configuration": {
            "policy": spec["policy"],
            "ttl_steps": 2000,
            "max_observations": 6,
            "max_replans": 3,
            "device": "cuda:0",
            "prefer_rgbd_claims": True,
            "learned_checkpoint": None,
            "vision_enabled": True,
            "vision_backend": "torch_spatial_rgbd",
            "require_vision_clear_root": True,
            "require_side_view_vision_root": True,
            "enforce_modality_conflict": True,
            "use_v7_contract": True,
            "use_purify_go_gate": True,
            "repair_required": True,
            "sensor_version": "look-twice-rgbd-multi-agent-v6/1",
        },
        "environment": {
            "formal_result_eligible": False,
            "runtime": "genesis-amd",
            "physics_backend": "kinematic",
            "device": "cuda:0",
            "artifact_inputs_eligible": True,
        },
        "metrics": {
            "mission_success": True,
            "route_mode": "direct",
            "selected_corridor": "corridor_b",
            "unsafe_crossing": False,
            "clear_admitted_collision": False,
            "admit_then_contact": False,
            "selected_corridor_oracle_blocked": False,
            "collision_count": 0,
            "observation_count": captures,
            "viewpoints_sequence": viewpoints,
            "replan_count": 1 if candidate else 0,
            "used_detour": False,
            "repair_success": True,
            # Candidate deliberately has more proposals than captures: dual-ROI
            # inference must not be counted as extra physical acquisition.
            "vision_proposal_count": captures + (1 if candidate else 0),
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "conformal_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
            "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
            "checkpoint_loaded": True,
            "fallback_used": False,
            "vision_fallback_used": False,
            "genesis_live_rgbd": True,
            "world_alignment_passed": True,
            "purify_invoked": True,
            "purify_invoked_count": 1,
            "vision_sources": ["genesis_rgb"],
            **(
                {
                    "contract_progress_nbv_enabled": True,
                    "contract_progress_nbv_policy_artifact_id": POLICY_ARTIFACT_ID,
                    "contract_progress_shared_initial_ab_capture": True,
                    "contract_progress_shared_initial_ab_proposal_count": 2,
                    "contract_progress_shared_initial_ab_corridors": [
                        "corridor_a",
                        "corridor_b",
                    ],
                    "contract_progress_shared_initial_capture_root_ids": [
                        "capture-root-0"
                    ],
                    "contract_progress_shared_initial_device_root_ids": [
                        "device-root-0"
                    ],
                    "contract_progress_rgbd_vision_proposal_count": captures + 1,
                    "contract_progress_physical_root_bound_vision_count": captures + 1,
                    "contract_progress_all_rgbd_geometry_vision_roots_bound": True,
                }
                if candidate
                else {}
            ),
        },
        "motion_segments": (
            [
                {
                    "agent_id": "scout",
                    "path_length": scout,
                    "target_xy": [0.5, 1.0],
                },
                {"agent_id": "carrier", "path_length": 5.0},
            ]
            if candidate
            else [
                {"agent_id": "scout", "path_length": scout},
                {"agent_id": "carrier", "path_length": 5.0},
            ]
        ),
        "purify_go_receipts": [go_receipt],
        "claims": claims,
        "rgbd_observation_audits": audits,
        "gate_receipts": [
            {
                "corridor_id": "corridor_b",
                "reasons": [],
                "python_admitted": True,
                "purify_go_admitted": True,
                "effective_admit": True,
                "purify_go_receipt": {
                    "receipt_sha256": "d" * 64,
                },
            }
        ],
        "repair_decisions": decisions,
    }
    if candidate:
        _bind_candidate_evidence_requests(payload)
    return payload


class ContractProgressEvidenceTests(unittest.TestCase):
    def test_fixed_schedule_is_seed_ascending_and_parity_counterbalanced(self) -> None:
        schedule = build_schedule()
        self.assertEqual(len(schedule), 40)
        self.assertEqual(
            [row["arm"] for row in schedule[:4]],
            ["baseline", "candidate", "candidate", "baseline"],
        )
        self.assertEqual(schedule[0]["seed"], 102530)
        self.assertEqual(schedule[-1]["seed"], 102549)
        self.assertEqual(len(schedule_sha256()), 64)

    def test_publicly_bound_prereg_is_valid_in_formal_mode(self) -> None:
        preregistration = json.loads(
            (
                ROOT
                / "release/v8-derived/contract_progress_challenge_102530_102549/PREREGISTRATION.json"
            ).read_text(encoding="utf-8")
        )
        validate_preregistration(preregistration, formal=False)
        receipt = validate_preregistration(preregistration, formal=True)
        self.assertTrue(receipt["contract_valid"])

    def test_capture_endpoint_uses_observation_count_not_proposals(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        row = derive_episode_row(_episode(spec), spec)
        self.assertTrue(row["structural_valid"], row["validation_errors"])
        self.assertEqual(row["physical_capture_count"], 2)
        self.assertEqual(row["vision_proposal_count"], 3)

    def test_candidate_chosen_ranking_requires_online_go_probability(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        del episode["repair_decisions"][0]["ranking_head"][0]["go_p_blocked"]
        row = derive_episode_row(episode, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_policy_receipt_valid"])

    def test_native_selector_cannot_ignore_effective_hard_reason(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        gate = episode["gate_receipts"][0]
        gate.update(
            {
                "reasons": ["modality_conflict"],
                "python_admitted": False,
                "purify_go_admitted": False,
                "effective_admit": False,
            }
        )
        self.assertEqual(
            episode["repair_decisions"][0]["contract_progress_selector_corridor_audit"][
                "corridor_b"
            ]["fail_closed_reasons"],
            [],
        )
        row = derive_episode_row(episode, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])
        self.assertEqual(row["nondelegated_candidate_chosen_count"], 0)

    def test_each_decision_uses_its_bound_then_current_go_receipt(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        old_receipt = episode["purify_go_receipts"][0]
        old_receipt["prediction_set"] = ["blocked"]
        old_prediction_clause = next(
            clause
            for clause in old_receipt["clauses"]
            if clause["clause"] == "prediction_set"
        )
        old_prediction_clause["actual"] = ["blocked"]
        old_prediction_clause["passed"] = False

        later_receipt = copy.deepcopy(old_receipt)
        later_receipt.update(
            {
                "receipt_id": "gate-test-corridor-b-later",
                "receipt_sha256": "e" * 64,
                "evaluated_step": 2,
                "prediction_set": ["clear"],
            }
        )
        later_prediction_clause = next(
            clause
            for clause in later_receipt["clauses"]
            if clause["clause"] == "prediction_set"
        )
        later_prediction_clause["actual"] = ["clear"]
        later_prediction_clause["passed"] = True
        episode["purify_go_receipts"] = [old_receipt, later_receipt]

        later_decision = episode["repair_decisions"][0]
        later_decision["contract_progress_selector_corridor_audit"]["corridor_b"][
            "go_receipt_sha256"
        ] = "e" * 64
        later_decision["ranking_head"][0]["go_receipt_sha256"] = "e" * 64

        earlier_decision = copy.deepcopy(later_decision)
        earlier_action = dict(earlier_decision["selected"])
        earlier_action.update(
            {
                "name": "scout_b_left_near",
                "viewpoint": "corridor_b/left_near",
                "target_xy": [0.3, 0.8],
                "travel_cost": 0.3,
            }
        )
        earlier_decision.update(
            {
                "selected": earlier_action,
                "delegated_baseline_fail_closed": True,
                "contract_progress_no_repairable_contract": True,
                "contract_progress_selector_selection_reason": (
                    "fail_closed_no_repairable_go_contract"
                ),
            }
        )
        earlier_decision["contract_progress_selector_corridor_audit"]["corridor_b"][
            "go_receipt_sha256"
        ] = "d" * 64
        earlier_decision["contract_progress_selector_corridor_audit"]["corridor_b"][
            "fail_closed_reasons"
        ] = ["go_prediction_blocked"]
        earlier_item = earlier_decision["ranking_head"][0]
        earlier_item.update(
            {
                "action": copy.deepcopy(earlier_action),
                "delegated_baseline_fail_closed": True,
                "policy_artifact_id": "heuristic-v6/1",
                "delegating_policy_artifact_id": POLICY_ARTIFACT_ID,
                "go_receipt_sha256": "d" * 64,
            }
        )
        episode["repair_decisions"] = [earlier_decision, later_decision]

        current_side_audit = next(
            audit
            for audit in episode["rgbd_observation_audits"]
            if audit.get("shared_initial_ab_capture") is not True
        )
        earlier_audit = copy.deepcopy(current_side_audit)
        earlier_audit.update(
            {
                "viewpoint": "corridor_b/left_near",
                "physical_capture_root_id": "capture-root-earlier",
                "physical_device_root_id": "device-root-earlier",
                "model_id": "model-earlier-corridor-b",
                "input_sha256": "9" * 64,
            }
        )
        episode["rgbd_observation_audits"].insert(2, earlier_audit)
        earlier_claims = []
        for claim in episode["claims"]:
            if claim.get("capture_root_id") != "capture-root-1":
                continue
            cloned = copy.deepcopy(claim)
            cloned["claim_id"] = f"earlier-{claim['claim_id']}"
            cloned["capture_root_id"] = "capture-root-earlier"
            cloned["device_root_id"] = "device-root-earlier"
            if cloned.get("modality") == "vision_semantic_v7":
                cloned["model_id"] = "model-earlier-corridor-b"
                cloned["artifact_sha256"] = "9" * 64
            earlier_claims.append(cloned)
        episode["claims"].extend(earlier_claims)
        for claim in episode["claims"]:
            if claim.get("capture_root_id") == "capture-root-1":
                claim["observed_step"] = 2
                claim["received_step"] = 2
        episode["motion_segments"].insert(
            0,
            {
                "agent_id": "scout",
                "path_length": 0.5,
                "target_xy": [0.3, 0.8],
            },
        )
        episode["metrics"].update(
            {
                "observation_count": 3,
                "viewpoints_sequence": [
                    "carrier_initial_front",
                    "corridor_b/left_near",
                    "corridor_b/left_far",
                ],
                "vision_proposal_count": 4,
                "replan_count": 2,
                "contract_progress_rgbd_vision_proposal_count": 4,
                "contract_progress_physical_root_bound_vision_count": 4,
                "purify_invoked_count": 2,
            }
        )
        episode["gate_receipts"][0]["purify_go_receipt"]["receipt_sha256"] = "e" * 64
        _bind_candidate_evidence_requests(episode)

        row = derive_episode_row(episode, spec)
        self.assertTrue(row["structural_valid"], row["validation_errors"])
        self.assertEqual(row["delegated_chosen_count"], 1)
        self.assertEqual(row["nondelegated_candidate_chosen_count"], 1)
        self.assertEqual(row["native_selector_decision_count"], 1)

        future_bound = copy.deepcopy(episode)
        future_bound["purify_go_receipts"][1]["evaluated_step"] = 3
        row = derive_episode_row(future_bound, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])

        duplicate_step = copy.deepcopy(episode)
        duplicate_step["purify_go_receipts"][1]["evaluated_step"] = 1
        _bind_candidate_evidence_requests(duplicate_step, steps=[1, 1])
        row = derive_episode_row(duplicate_step, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_selector_invoked_valid"])

    def test_all_delegated_candidate_cannot_satisfy_invocation_gate(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        item = episode["repair_decisions"][0]["ranking_head"][0]
        item.update(
            {
                "delegated_baseline_fail_closed": True,
                "policy_artifact_id": "heuristic-v6/1",
                "delegating_policy_artifact_id": POLICY_ARTIFACT_ID,
            }
        )
        row = derive_episode_row(episode, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])
        self.assertTrue(row["delegated_policy_provenance_valid"])

    def test_selected_and_unique_chosen_action_must_match(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        episode["repair_decisions"][0]["selected"]["name"] = "scout_a_right_far"
        row = derive_episode_row(episode, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["repair_decision_alignment_valid"])

        same_name_split_action = _episode(spec)
        same_name_split_action["repair_decisions"][0]["ranking_head"][0]["action"][
            "target_xy"
        ] = [99.0, 99.0]
        row = derive_episode_row(same_name_split_action, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["repair_decision_alignment_valid"])

    def test_delegated_item_cannot_spoof_candidate_policy_id(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        item = episode["repair_decisions"][0]["ranking_head"][0]
        item.update(
            {
                "delegated_baseline_fail_closed": True,
                "delegating_policy_artifact_id": POLICY_ARTIFACT_ID,
            }
        )
        row = derive_episode_row(episode, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["delegated_policy_provenance_valid"])

    def test_all_hard_deny_delegation_is_valid_without_native_choice(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")
        episode = _episode(spec)
        receipt = episode["purify_go_receipts"][0]
        receipt["prediction_set"] = ["blocked"]
        prediction_clause = next(
            clause
            for clause in receipt["clauses"]
            if clause["clause"] == "prediction_set"
        )
        prediction_clause["actual"] = ["blocked"]
        prediction_clause["passed"] = False
        decision = episode["repair_decisions"][0]
        decision.update(
            {
                "delegated_baseline_fail_closed": True,
                "contract_progress_no_repairable_contract": True,
                "contract_progress_selector_selection_reason": (
                    "fail_closed_no_repairable_go_contract"
                ),
            }
        )
        decision["contract_progress_selector_corridor_audit"]["corridor_b"][
            "fail_closed_reasons"
        ] = ["go_prediction_blocked"]
        item = decision["ranking_head"][0]
        item.update(
            {
                "delegated_baseline_fail_closed": True,
                "policy_artifact_id": "heuristic-v6/1",
                "delegating_policy_artifact_id": POLICY_ARTIFACT_ID,
            }
        )
        row = derive_episode_row(episode, spec)
        self.assertTrue(row["structural_valid"], row["validation_errors"])
        self.assertTrue(row["candidate_conditional_native_invocation_valid"])
        self.assertEqual(row["nondelegated_candidate_chosen_count"], 0)
        self.assertEqual(row["delegated_decision_count"], 1)

    def test_chosen_side_view_must_be_authorized_to_count_as_executed(self) -> None:
        spec = next(row for row in build_schedule() if row["arm"] == "candidate")

        native = _episode(spec)
        native["repair_decisions"][0]["authorized"] = False
        row = derive_episode_row(native, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])
        self.assertEqual(row["nondelegated_candidate_chosen_count"], 0)

        delegated = _episode(spec)
        receipt = delegated["purify_go_receipts"][0]
        receipt["prediction_set"] = ["blocked"]
        prediction_clause = next(
            clause
            for clause in receipt["clauses"]
            if clause["clause"] == "prediction_set"
        )
        prediction_clause["actual"] = ["blocked"]
        prediction_clause["passed"] = False
        decision = delegated["repair_decisions"][0]
        decision.update(
            {
                "authorized": False,
                "delegated_baseline_fail_closed": True,
                "contract_progress_no_repairable_contract": True,
                "contract_progress_selector_selection_reason": (
                    "fail_closed_no_repairable_go_contract"
                ),
            }
        )
        decision["contract_progress_selector_corridor_audit"]["corridor_b"][
            "fail_closed_reasons"
        ] = ["go_prediction_blocked"]
        item = decision["ranking_head"][0]
        item.update(
            {
                "delegated_baseline_fail_closed": True,
                "policy_artifact_id": "heuristic-v6/1",
                "delegating_policy_artifact_id": POLICY_ARTIFACT_ID,
            }
        )
        row = derive_episode_row(delegated, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])
        self.assertFalse(row["delegated_policy_provenance_valid"])

        fallback = copy.deepcopy(delegated)
        fallback_decision = fallback["repair_decisions"][0]
        fallback_decision["authorized"] = True
        fallback_decision["selected"] = {
            "kind": "safe_fallback",
            "name": "safe_detour",
        }
        fallback_item = fallback_decision["ranking_head"][0]
        fallback_item["action"] = {
            "kind": "safe_fallback",
            "name": "safe_detour",
        }
        for key in (
            "go_p_blocked",
            "go_receipt_sha256",
            "go_measurement_root_debt",
            "repair_step_debt",
        ):
            fallback_item[key] = None
        fallback["claims"] = [
            claim
            for claim in fallback["claims"]
            if claim.get("capture_root_id") == "capture-root-0"
        ]
        fallback["rgbd_observation_audits"] = [
            audit
            for audit in fallback["rgbd_observation_audits"]
            if audit.get("physical_capture_root_id") == "capture-root-0"
        ]
        fallback["motion_segments"] = [
            segment
            for segment in fallback["motion_segments"]
            if segment.get("agent_id") != "scout"
        ]
        fallback_metrics = fallback["metrics"]
        fallback_metrics.update(
            {
                "observation_count": 1,
                "viewpoints_sequence": ["carrier_initial_front"],
                "vision_proposal_count": 2,
                "replan_count": 0,
                "route_mode": "detour",
                "used_detour": True,
                "selected_corridor": None,
                "repair_success": False,
                "contract_progress_rgbd_vision_proposal_count": 2,
                "contract_progress_physical_root_bound_vision_count": 2,
            }
        )
        _bind_candidate_evidence_requests(fallback)
        row = derive_episode_row(fallback, spec)
        self.assertTrue(row["structural_valid"], row["validation_errors"])
        self.assertTrue(row["candidate_conditional_native_invocation_valid"])
        self.assertTrue(row["delegated_policy_provenance_valid"])
        self.assertEqual(row["terminal_delegated_route_noop_count"], 1)

        mid_list_fallback = copy.deepcopy(fallback)
        mid_list_fallback["repair_decisions"].append(
            copy.deepcopy(mid_list_fallback["repair_decisions"][0])
        )
        _bind_candidate_evidence_requests(mid_list_fallback)
        row = derive_episode_row(mid_list_fallback, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_conditional_native_invocation_valid"])

    def test_actual_producer_payload_flows_into_compound_and_execution_audits(
        self,
    ) -> None:
        scenario = sample_v6_scenario("shared-occlusion", 90000)
        runtime = _RGBDKinematicRuntime(scenario)

        def process_with_runtime_step(*args, **kwargs):
            claims, audit = _fake_process_genesis(*args, **kwargs)
            for claim in claims:
                claim.observed_step = runtime.current_step
            return claims, audit

        with tempfile.NamedTemporaryFile() as fake_binary:
            fake_binary.write(b"fake-purify-binary")
            fake_binary.flush()
            with (
                mock.patch("purify_bridge.PurifyBridge", _FakePurifyBridge),
                mock.patch(
                    "v5_rgbd_claims.process_genesis_observation",
                    side_effect=process_with_runtime_step,
                ),
                mock.patch(
                    "v7_vision_claims.propose_vision_spatial_rgbd_ab_shared",
                    return_value=(
                        _proposal("corridor_a", shared=True),
                        _proposal("corridor_b", shared=True),
                    ),
                ),
                mock.patch(
                    "v7_vision_claims.propose_vision",
                    return_value=_proposal("corridor_a", shared=False, value="blocked"),
                ),
            ):
                payload = run_v6_episode(
                    scenario=scenario,
                    runtime=runtime,
                    config=V6EpisodeConfig(
                        policy=CANDIDATE_POLICY,
                        vision_enabled=True,
                        vision_backend="torch_spatial_rgbd",
                        require_vision_clear_root=True,
                        require_side_view_vision_root=True,
                        use_v7_contract=True,
                        use_purify_go_gate=True,
                        purify_binary=fake_binary.name,
                    ),
                )
        spec = dict(next(row for row in build_schedule() if row["arm"] == "candidate"))
        spec["seed"] = scenario.seed
        row = derive_episode_row(payload, spec)
        self.assertTrue(row["compound_intervention_valid"], row["validation_errors"])
        self.assertTrue(row["candidate_execution_closure_valid"])
        self.assertTrue(
            all(
                decision["evidence_request_receipt_sha256"] == receipt["receipt_sha256"]
                and decision["execution_status"]
                == (
                    "authorized_for_execution"
                    if decision["authorized"]
                    else "authorization_denied_noop"
                )
                for decision, receipt in zip(
                    payload["repair_decisions"],
                    payload["evidence_request_receipts"],
                )
            )
        )

    def test_retained_gpu_terminal_noop_rejects_phantom_motion(self) -> None:
        fixture = Path(
            "/tmp/look-twice-contract-progress-smoke.3gURJC/candidate-102515.json"
        )
        if not fixture.is_file():
            self.skipTest("retained read-only GPU smoke payload is unavailable")
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        for decision, request in zip(
            payload["repair_decisions"], payload["evidence_request_receipts"]
        ):
            decision["evidence_request_receipt_sha256"] = request["receipt_sha256"]
            decision["execution_status"] = (
                "authorized_for_execution"
                if decision["authorized"]
                else "authorization_denied_noop"
            )
        spec = dict(next(row for row in build_schedule() if row["arm"] == "candidate"))
        spec["seed"] = 102515
        row = derive_episode_row(payload, spec)
        self.assertTrue(row["structural_valid"], row["validation_errors"])
        self.assertEqual(row["terminal_delegated_noop_count"], 1)

        tampered = copy.deepcopy(payload)
        terminal_target = tampered["repair_decisions"][-1]["selected"]["target_xy"]
        tampered["motion_segments"].append(
            {
                "agent_id": "scout",
                "target_xy": terminal_target,
                "path_length": 0.0,
            }
        )
        row = derive_episode_row(tampered, spec)
        self.assertFalse(row["structural_valid"])
        self.assertFalse(row["candidate_execution_closure_valid"])

    def test_go_authentication_retains_no_receipt_and_rejected_receipt_runs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            self.assertEqual(
                authenticate_output_go_receipts(
                    output,
                    {"purify_binary_path": "/missing-but-unused-with-no-receipts"},
                ),
                set(),
            )

            spec = next(row for row in build_schedule() if row["arm"] == "candidate")
            _write_json(output / spec["episode_path"], _episode(spec))
            binary = output / "purify"
            binary.write_bytes(b"frozen-binary-placeholder")
            rejected = SimpleNamespace(
                returncode=0,
                stdout=(
                    json.dumps(
                        {
                            "schema_version": "purify.robotics.response.v1",
                            "request_id": "verify-00000000",
                            "ok": False,
                            "error": "receipt hash mismatch",
                        }
                    )
                    + "\n"
                ),
                stderr="",
            )
            with (
                mock.patch(
                    "scripts.verify_v8_contract_progress_challenge.file_sha256",
                    return_value=EXPECTED_PURIFY_SHA256,
                ),
                mock.patch(
                    "scripts.verify_v8_contract_progress_challenge.subprocess.run",
                    return_value=rejected,
                ),
            ):
                authenticated = authenticate_output_go_receipts(
                    output,
                    {"purify_binary_path": str(binary)},
                )
            self.assertEqual(authenticated, set())
            row = derive_episode_row(
                _episode(spec),
                spec,
                authenticated_go_receipt_hashes=authenticated,
            )
            self.assertFalse(row["structural_valid"])
            self.assertTrue(
                any("not authenticated" in error for error in row["validation_errors"])
            )

    def test_go_authentication_skips_malformed_retained_episode_files(self) -> None:
        malformed_payloads = (
            b'{"schema_version":',
            b"[]\n",
            b"\xff\xfe\x00",
        )
        for malformed in malformed_payloads:
            with (
                self.subTest(malformed=malformed),
                tempfile.TemporaryDirectory() as temporary,
            ):
                output = Path(temporary)
                spec = build_schedule()[0]
                episode_path = output / spec["episode_path"]
                episode_path.parent.mkdir(parents=True, exist_ok=True)
                episode_path.write_bytes(malformed)
                with mock.patch(
                    "scripts.verify_v8_contract_progress_challenge.subprocess.run"
                ) as run:
                    authenticated = authenticate_output_go_receipts(
                        output,
                        {"purify_binary_path": "/unused-for-malformed-episode"},
                    )
                self.assertEqual(authenticated, set())
                run.assert_not_called()

    def test_compound_gate_rejects_metric_raw_claim_and_baseline_tampering(
        self,
    ) -> None:
        candidate_spec = next(
            row for row in build_schedule() if row["arm"] == "candidate"
        )
        mutations = []

        wrong_claim_root = _episode(candidate_spec)
        wrong_claim_root["claims"][1]["capture_root_id"] = "forged-root"
        mutations.append(wrong_claim_root)

        wrong_mask = _episode(candidate_spec)
        wrong_mask["rgbd_observation_audits"][0]["shared_initial_b_mask_source"] = (
            "forged-mask"
        )
        mutations.append(wrong_mask)

        forged_initial = _episode(candidate_spec)
        forged_initial["metrics"]["viewpoints_sequence"][0] = "forged_initial"
        for audit in forged_initial["rgbd_observation_audits"][:2]:
            audit["viewpoint"] = "forged_initial"
        mutations.append(forged_initial)

        forged_observer = _episode(candidate_spec)
        forged_observer["rgbd_observation_audits"][0]["observer_agent_id"] = "scout"
        mutations.append(forged_observer)

        synthetic_side = _episode(candidate_spec)
        synthetic_side["rgbd_observation_audits"][-1]["vision_source"] = (
            "synthetic_rgb_proxy"
        )
        mutations.append(synthetic_side)

        metric_lie = _episode(candidate_spec)
        metric_lie["metrics"][
            "contract_progress_all_rgbd_geometry_vision_roots_bound"
        ] = True
        metric_lie["rgbd_observation_audits"][-1]["physical_capture_root_bound"] = False
        mutations.append(metric_lie)

        for episode in mutations:
            with self.subTest(mutation=mutations.index(episode)):
                row = derive_episode_row(episode, candidate_spec)
                self.assertFalse(row["compound_intervention_valid"])
                self.assertFalse(row["structural_valid"])

        baseline_spec = next(
            row for row in build_schedule() if row["arm"] == "baseline"
        )
        baseline = _episode(baseline_spec)
        baseline["metrics"]["contract_progress_nbv_enabled"] = True
        baseline["rgbd_observation_audits"][0]["shared_rgbd_backbone"] = True
        row = derive_episode_row(baseline, baseline_spec)
        self.assertFalse(row["compound_intervention_valid"])

    def test_candidate_src_closure_rejects_ignored_import_hook_and_scrubs_git_env(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "src").mkdir()
            (root / "src/main.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                "src/sitecustomize.py\nsrc/__pycache__/\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "add", ".gitignore", "src/main.py"], cwd=root, check=True
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GIT_DIR": "/tmp/forged-git-dir",
                    "GIT_INDEX_FILE": "/tmp/forged-index",
                    "GIT_WORK_TREE": "/tmp/forged-worktree",
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.fsmonitor",
                    "GIT_CONFIG_VALUE_0": "true",
                },
            ):
                closure = verify_candidate_source_closure(root)
            self.assertEqual(closure["tracked_file_count"], 1)
            (root / "src/sitecustomize.py").write_text(
                "raise RuntimeError('ignored import hook')\n", encoding="utf-8"
            )
            with self.assertRaises(VerificationError):
                verify_candidate_source_closure(root)

    def test_anonymous_git_environment_drops_credentials_and_redirection(self) -> None:
        injected = {
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "credential.helper",
            "GIT_CONFIG_VALUE_0": "evil",
            "GIT_SSH_COMMAND": "evil",
            "GIT_DIR": "/tmp/evil",
            "GIT_WORK_TREE": "/tmp/evil-tree",
            "GITHUB_TOKEN": "secret",
            "GH_TOKEN": "secret",
            "SSH_AUTH_SOCK": "/tmp/agent",
        }
        with mock.patch.dict(os.environ, injected, clear=False):
            environment = _anonymous_git_environment()
        for key in injected:
            self.assertNotIn(key, environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(environment["GIT_CONFIG_SYSTEM"], "/dev/null")
        self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(environment["GIT_ASKPASS"], "/bin/false")

    def test_gpu_preflight_allows_stale_pids_but_rejects_live_pid(self) -> None:
        showpids = SimpleNamespace(
            returncode=0,
            stdout="KFD Processes\nPID PROCESS\n2268904 stale\n4014921 stale\n",
            stderr="",
        )
        idle = {
            "gpu_use_percent": 0.0,
            "vram_allocated_percent": 0.0,
        }
        with (
            mock.patch(
                f"{RUNNER_MODULE}.subprocess.run",
                return_value=showpids,
            ),
            mock.patch(
                f"{RUNNER_MODULE}._proc_pid_exists",
                return_value=False,
            ),
            mock.patch(
                f"{RUNNER_MODULE}._scan_open_kfd_fds",
                return_value=[],
            ),
            mock.patch(
                f"{RUNNER_MODULE}.query_rocm",
                return_value=idle,
            ),
        ):
            proof = clean_gpu_preflight()
        self.assertEqual(proof["stale_kfd_pids"], [2268904, 4014921])
        self.assertTrue(proof["no_live_kfd_processes"])

        with (
            mock.patch(
                f"{RUNNER_MODULE}.subprocess.run",
                return_value=showpids,
            ),
            mock.patch(
                f"{RUNNER_MODULE}._proc_pid_exists",
                side_effect=lambda pid: pid == 2268904,
            ),
            mock.patch(
                f"{RUNNER_MODULE}._scan_open_kfd_fds",
                return_value=[],
            ),
            self.assertRaises(RUNNER_VERIFICATION_ERROR),
        ):
            clean_gpu_preflight()

    def test_python_launcher_preserves_venv_symlink_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            launcher = Path(temporary) / "venv-python"
            launcher.symlink_to(Path(sys.executable))
            resolved = _resolve_python(str(launcher))
            self.assertEqual(resolved, launcher)
            self.assertNotEqual(str(resolved), str(launcher.resolve()))

    def test_postrun_failure_is_retained_instead_of_raising_before_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "raw").mkdir()
            paths = {"output_root": output}
            with mock.patch(
                f"{RUNNER_MODULE}.verify_design",
                side_effect=VerificationError("remote head changed"),
            ):
                payload = write_postrun_binding(
                    paths,
                    {"bound": "before"},
                    attempts_completed=40,
                    last_attempt_ended_monotonic_ns=99,
                )
            self.assertFalse(payload["revalidation_passed"])
            self.assertIn("remote head changed", payload["validation_error"])
            self.assertTrue((output / "raw/POSTRUN_BINDING.json").is_file())

    def test_postrun_manifest_hash_tamper_is_rejected_before_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            postrun_path = output / "raw/POSTRUN_BINDING.json"
            _write_json(
                postrun_path,
                {
                    "schema_version": POSTRUN_SCHEMA,
                    "revalidation_passed": True,
                },
            )
            with self.assertRaisesRegex(
                VerificationError, "postrun binding fields differ"
            ):
                validate_postrun_binding(
                    output,
                    {},
                    {},
                    {
                        "postrun_binding_sha256": "0" * 64,
                        "postrun_revalidation_passed": True,
                    },
                    [{}],
                )

    def test_durable_attempt_helper_fsyncs_child_output_before_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            episode = Path(temporary) / "episode.json"
            episode.write_text("{}\n", encoding="utf-8")
            missing = Path(temporary) / "missing.json"
            with mock.patch(
                f"{RUNNER_MODULE}._fsync_file_and_parent"
            ) as fsync:
                durably_persist_attempt_files([episode, missing])
            fsync.assert_called_once_with(episode)

    def test_report_passes_preregistered_effect_and_safety_gates(self) -> None:
        rows = [derive_episode_row(_episode(spec), spec) for spec in build_schedule()]
        report = derive_report(
            rows,
            preregistration_sha256="1" * 64,
            run_manifest_sha256="2" * 64,
        )
        self.assertTrue(report["mandatory_gates"]["all_pass"])
        self.assertTrue(report["capability_gates"]["all_pass"])
        self.assertTrue(
            report["capability_gates"]["team_path_relative_reduction_min_0_10"]
        )
        self.assertAlmostEqual(
            report["operational_burden"]["scout_path_length"]["relative_reduction"],
            0.30,
        )
        self.assertEqual(
            report["operational_burden"]["physical_capture_count"]["candidate"]["mean"],
            2.0,
        )

    def test_paired_direct_regression_fails_mandatory_gate(self) -> None:
        rows = [derive_episode_row(_episode(spec), spec) for spec in build_schedule()]
        victim = next(
            row for row in rows if row["seed"] == 102530 and row["arm"] == "candidate"
        )
        victim["full_chain_direct"] = False
        report = derive_report(
            rows, preregistration_sha256="1" * 64, run_manifest_sha256="2" * 64
        )
        self.assertFalse(report["mandatory_gates"]["no_paired_direct_regression"])
        self.assertFalse(report["mandatory_gates"]["all_pass"])

    def test_team_path_gate_is_independent_of_scout_and_capture_gates(self) -> None:
        rows = [derive_episode_row(_episode(spec), spec) for spec in build_schedule()]
        for row in rows:
            if row["arm"] == "candidate":
                row["carrier_path_length"] = 5.5
                row["team_path_length"] = row["scout_path_length"] + 5.5
        report = derive_report(
            rows,
            preregistration_sha256="1" * 64,
            run_manifest_sha256="2" * 64,
        )
        gates = report["capability_gates"]
        self.assertTrue(gates["scout_path_relative_reduction_min_0_25"])
        self.assertTrue(gates["physical_capture_relative_reduction_min_0_20"])
        self.assertFalse(gates["team_path_relative_reduction_min_0_10"])
        self.assertFalse(gates["all_pass"])

    def test_runner_commands_use_separate_entrypoints(self) -> None:
        schedule = build_schedule()
        fake = {
            "baseline_entrypoint": Path("/baseline/src/look_twice_v7.py"),
            "candidate_entrypoint": Path("/candidate/src/look_twice_v7.py"),
            "checkpoint": Path("/assets/model.pt"),
            "vision_artifact": Path("/assets/vision.json"),
            "go_artifact": Path("/assets/go.json"),
            "purify_binary": Path("/assets/purify"),
            "output_root": Path("/output"),
        }
        baseline = build_episode_command(schedule[0], fake, "/python")
        candidate = build_episode_command(schedule[1], fake, "/python")
        self.assertIn("/baseline/src/look_twice_v7.py", baseline)
        self.assertIn("/candidate/src/look_twice_v7.py", candidate)
        self.assertIn("purify-active-contract-progress", candidate)

    def test_formal_git_binding_requires_exact_live_remote_head(self) -> None:
        head = "b" * 40
        allowed = (
            "release/v8-derived/contract_progress_challenge_102530_102549/"
            "PREREGISTRATION.json"
        )
        prereg = {
            "public_binding": {
                "commit_a": "a" * 40,
                "remote_name": "origin",
                "commit_b_diff_from_a_may_only_change": allowed,
            }
        }
        merge_base_ok = SimpleNamespace(returncode=0, stdout="", stderr="")
        live_exact = SimpleNamespace(
            returncode=0,
            stdout=f"{head}\trefs/heads/contract-progress\n",
            stderr="",
        )
        with (
            mock.patch(
                f"{RUNNER_MODULE}._git",
                side_effect=[
                    head,
                    "",
                    "a" * 40,
                    "1",
                    allowed,
                    "git@github.com:liulin/look-twice.git",
                ],
            ),
            mock.patch(
                f"{RUNNER_MODULE}.subprocess.run",
                side_effect=[merge_base_ok, live_exact],
            ),
        ):
            observation = verify_two_commit_binding(Path("/candidate"), prereg)
        self.assertTrue(observation["commit_b_public_remote_head_verified"])
        self.assertEqual(observation["public_github_repository"], "liulin/look-twice")
        self.assertEqual(
            observation["public_remote_head_refs"],
            ["refs/heads/contract-progress"],
        )

        stale_remote = SimpleNamespace(
            returncode=0,
            stdout=f"{'c' * 40}\trefs/heads/contract-progress\n",
            stderr="",
        )
        with (
            mock.patch(
                f"{RUNNER_MODULE}._git",
                side_effect=[
                    head,
                    "",
                    "a" * 40,
                    "1",
                    allowed,
                    "git@github.com:liulin/look-twice.git",
                ],
            ),
            mock.patch(
                f"{RUNNER_MODULE}.subprocess.run",
                side_effect=[merge_base_ok, stale_remote],
            ),
            self.assertRaises(RUNNER_VERIFICATION_ERROR),
        ):
            verify_two_commit_binding(Path("/candidate"), prereg)

    @mock.patch(
        "scripts.verify_v8_contract_progress_challenge.validate_postrun_binding",
        return_value=True,
    )
    @mock.patch(
        "scripts.verify_v8_contract_progress_challenge.authenticate_output_go_receipts",
        return_value={"d" * 64},
    )
    def test_full_raw_fixture_verifies_and_extra_file_is_rejected(
        self, _authenticate, _postrun
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "formal"
            out.mkdir()
            prereg_path = root / "PREREGISTRATION.json"
            _write_json(prereg_path, _bound_prereg())
            attempts = []
            windows = []
            for spec in build_schedule():
                started_ns = 1_000_000_000 + spec["schedule_index"] * 100_000_000
                ended_ns = started_ns + 50_000_000
                episode_path = out / spec["episode_path"]
                stdout_path = out / spec["stdout_path"]
                stderr_path = out / spec["stderr_path"]
                _write_json(episode_path, _episode(spec))
                stdout_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_path.parent.mkdir(parents=True, exist_ok=True)
                stdout_path.write_text("ok\n", encoding="utf-8")
                stderr_path.write_text("", encoding="utf-8")
                attempt = {
                    **{
                        key: spec[key]
                        for key in (
                            "schedule_index",
                            "seed",
                            "arm",
                            "policy",
                            "profile",
                        )
                    },
                    "episode_path": spec["episode_path"],
                    "stdout_path": spec["stdout_path"],
                    "stderr_path": spec["stderr_path"],
                    "error_path": spec["error_path"],
                    "command": build_episode_command(
                        spec,
                        {
                            "baseline_entrypoint": Path(
                                "/baseline/src/look_twice_v7.py"
                            ),
                            "candidate_entrypoint": Path(
                                "/candidate/src/look_twice_v7.py"
                            ),
                            "checkpoint": Path("/assets/checkpoint.pt"),
                            "vision_artifact": Path("/assets/vision.json"),
                            "go_artifact": Path("/assets/go.json"),
                            "purify_binary": Path("/assets/purify"),
                            "output_root": out,
                        },
                        "/python",
                    ),
                    "started_at_utc": "2026-08-05T00:02:01Z",
                    "ended_at_utc": "2026-08-05T00:02:02Z",
                    "command_exit_code": 0,
                    "timed_out": False,
                    "started_monotonic_ns": started_ns,
                    "ended_monotonic_ns": ended_ns,
                    "wall_seconds": (ended_ns - started_ns) / 1e9,
                    "episode_exists": True,
                    "episode_sha256": file_sha256(episode_path),
                    "stdout_sha256": file_sha256(stdout_path),
                    "stderr_sha256": file_sha256(stderr_path),
                    "error_exists": False,
                    "error_sha256": None,
                    "attempt_integrity_valid": True,
                    "attempt_artifacts_fsynced": True,
                    "retry_count": 0,
                }
                attempts.append(attempt)
                windows.append(
                    {
                        **{
                            key: spec[key]
                            for key in (
                                "schedule_index",
                                "seed",
                                "arm",
                                "policy",
                                "profile",
                            )
                        },
                        "started_monotonic_ns": started_ns,
                        "ended_monotonic_ns": ended_ns,
                        "command_exit_code": 0,
                        "timed_out": False,
                    }
                )
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", attempts)
            _write_jsonl(out / "raw/EPISODE_WINDOWS.jsonl", windows)
            telemetry_fields = {
                "gpu_use_percent": 0.0,
                "vram_allocated_percent": 0.0,
                "memory_activity_percent": None,
                "graphics_package_power_w": None,
                "temperature_edge_c": None,
                "temperature_junction_c": None,
                "temperature_memory_c": None,
            }
            samples = [
                {
                    "captured_monotonic_ns": captured_ns,
                    "command_exit_code": 0,
                    **telemetry_fields,
                }
                for captured_ns in (
                    800_000_000,
                    2_800_000_000,
                    4_800_000_000,
                    5_100_000_000,
                )
            ]
            _write_jsonl(out / "raw/ROCM_SAMPLES.jsonl", samples)
            prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
            source_observations = [
                {
                    "path": row["path"],
                    "sha256_declared": row["sha256"],
                    "sha256_observed": row["sha256"],
                }
                for row in prereg["identities"]["candidate_source_files"]
            ]
            candidate_closure_rows = [
                {"path": row["path"], "sha256": row["sha256"]}
                for row in prereg["identities"]["candidate_source_files"]
            ]
            candidate_closure = {
                "tree_fingerprint_algorithm": CANDIDATE_SOURCE_TREE_ALGORITHM,
                "tree_fingerprint_sha256": prereg["identities"][
                    "candidate_tracked_src_tree_fingerprint_sha256"
                ],
                "tracked_file_count": len(candidate_closure_rows),
                "exact_git_tracked_file_set_verified": True,
                "untracked_and_ignored_files_absent": True,
                "symlinks_and_nonregular_paths_absent": True,
                "files": candidate_closure_rows,
            }
            runtime_manifest = json.loads(
                (
                    ROOT / "release/v8-frozen/results/"
                    "V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
                ).read_text(encoding="utf-8")
            )
            baseline_closure = {
                "manifest": {"sha256": EXPECTED_RUNTIME_MANIFEST_SHA256},
                "tree_fingerprint_sha256": EXPECTED_RUNTIME_TREE_SHA256,
                "file_count": 30,
                "python_file_count": 29,
                "exact_python_file_set_verified": True,
                "exact_src_file_set_verified": True,
                "source_origin_git_commit": (
                    "aadd429d2da9de690a361218c40c9dfb22b04eb2"
                ),
                "files": [
                    {"path": row["path"], "sha256": row["sha256"]}
                    for row in runtime_manifest["files"]
                ],
            }
            _write_json(
                out / "raw/PRESTART_BINDING.json",
                {
                    "schema_version": PRESTART_SCHEMA,
                    "bound_at_utc_before_first_episode": "2026-08-05T00:02:00Z",
                    "bound_monotonic_ns_before_first_episode": 900_000_000,
                    "no_episode_had_started": True,
                    "fixed_schedule": build_schedule(),
                    "schedule_sha256": schedule_sha256(),
                    "preregistration_sha256": file_sha256(prereg_path),
                    "runner_sha256": file_sha256(RUNNER),
                    "verifier_sha256": file_sha256(VERIFIER),
                    "baseline_root": "/baseline",
                    "candidate_root": "/candidate",
                    "python_executable": "/python",
                    "checkpoint_path": "/assets/checkpoint.pt",
                    "vision_artifact_path": "/assets/vision.json",
                    "go_artifact_path": "/assets/go.json",
                    "purify_binary_path": "/assets/purify",
                    "fresh_seed_opened_before_prestart": False,
                    "commit_a": "a" * 40,
                    "commit_b_observed": "b" * 40,
                    "git_two_commit_proof": {
                        "candidate_checkout_clean": True,
                        "commit_a_strict_ancestor": True,
                        "commit_b_direct_parent_is_commit_a": True,
                        "commit_count_a_to_b": 1,
                        "changed_paths_a_to_b": [
                            "release/v8-derived/"
                            "contract_progress_challenge_102530_102549/"
                            "PREREGISTRATION.json"
                        ],
                    },
                    "public_remote_proof": {
                        "remote_name": "origin",
                        "github_repository": "liulin/look-twice",
                        "access": "anonymous_https_no_credential_helper",
                        "remote_head_commit": "b" * 40,
                        "remote_head_refs": ["refs/heads/contract-progress"],
                        "commit_b_public_remote_head_verified": True,
                        "checked_at_utc": "2026-08-05T00:01:00Z",
                    },
                    "frozen_identities": {
                        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
                        "vision_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
                        "go_artifact_sha256": EXPECTED_GO_ARTIFACT_SHA256,
                        "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
                        "baseline_runtime_tree_sha256": EXPECTED_RUNTIME_TREE_SHA256,
                    },
                    "baseline_runtime_closure": baseline_closure,
                    "candidate_source_closure": candidate_closure,
                    "candidate_source_files": source_observations,
                    "clean_gpu_preflight": {
                        "showpids_exit_code": 0,
                        "showpids_stdout": "No KFD PIDs currently running\n",
                        "showpids_stderr": "",
                        "reported_kfd_pids": [],
                        "live_kfd_pids": [],
                        "stale_kfd_pids": [],
                        "no_live_kfd_processes": True,
                        "open_kfd_fds": [],
                        "global_dev_kfd_fd_scan_clear": True,
                        "idle_thresholds": {
                            "gpu_use_percent_max": 5.0,
                            "vram_allocated_percent_max": 2.0,
                        },
                        "first_telemetry_idle": True,
                        "first_telemetry_sample": samples[0],
                    },
                },
            )
            _write_json(
                out / "ROCM_TELEMETRY.json",
                {
                    "schema_version": "look-twice.v8-contract-progress-challenge-rocm-telemetry/v1",
                    "sample_interval_seconds": 2.0,
                    "max_allowed_gap_seconds": 5.5,
                    "challenge_started_monotonic_ns": 950_000_000,
                    "challenge_ended_monotonic_ns": 5_000_000_000,
                    "sample_count": len(samples),
                    "max_observed_gap_seconds": 2.0,
                    "sampler_errors": [],
                    "coverage_valid": True,
                    "summary": {
                        "sample_count": len(samples),
                        "gpu_use_percent": {
                            "mean": 0.0,
                            "minimum": 0.0,
                            "maximum": 0.0,
                            "median": 0.0,
                            "samples": len(samples),
                        },
                        "vram_allocated_percent": {
                            "mean": 0.0,
                            "minimum": 0.0,
                            "maximum": 0.0,
                            "median": 0.0,
                            "samples": len(samples),
                        },
                        **{
                            key: None
                            for key in telemetry_fields
                            if key not in {"gpu_use_percent", "vram_allocated_percent"}
                        },
                    },
                },
            )
            _write_json(
                out / "raw/POSTRUN_BINDING.json",
                {
                    "schema_version": POSTRUN_SCHEMA,
                    "revalidation_passed": True,
                },
            )
            _write_json(
                out / "RUN_MANIFEST.json",
                {
                    "schema_version": MANIFEST_SCHEMA,
                    "formal_result_eligible": False,
                    "preregistration_sha256": file_sha256(prereg_path),
                    "runner_sha256": file_sha256(RUNNER),
                    "verifier_sha256": file_sha256(VERIFIER),
                    "postrun_binding_sha256": file_sha256(
                        out / "raw/POSTRUN_BINDING.json"
                    ),
                    "postrun_revalidation_passed": True,
                    "fixed_schedule": build_schedule(),
                    "schedule_sha256": schedule_sha256(),
                    "attempts": attempts,
                    "attempt_accounting": {
                        "expected": 40,
                        "attempted": 40,
                        "valid": 40,
                        "timed_out": 0,
                        "retry_count": 0,
                        "seed_substitutions": 0,
                        "early_stopped": False,
                    },
                    "source_roots": {
                        "baseline": "/baseline",
                        "candidate": "/candidate",
                    },
                    "fixed_runtime": {
                        "runtime": "genesis-amd",
                        "motion_backend": "kinematic",
                        "device": "cuda:0",
                        "profile": PROFILE,
                        "seed_range": [102530, 102549],
                        "episode_timeout_seconds": 300,
                    },
                },
            )
            report, verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="base",
            )
            self.assertTrue(report["promotion_pass"])
            self.assertTrue(verification["telemetry_valid"])

            # A present, hash-bound but truncated child episode remains exactly
            # one failed cell.  Its runner parse-error artifact is authenticated,
            # and the complete report/checksum/final-verification sequence still
            # succeeds as an adverse (non-promotable) package.
            first_spec = build_schedule()[0]
            first_episode_path = out / first_spec["episode_path"]
            first_error_path = out / first_spec["error_path"]
            original_episode_bytes = first_episode_path.read_bytes()
            clean_manifest = json.loads(
                (out / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            first_episode_path.write_bytes(b'{"schema_version":')
            with self.assertRaises(VerificationError) as parse_failure:
                read_json_object(first_episode_path)
            recorded_parse_error = (
                f"{type(parse_failure.exception).__name__}: {parse_failure.exception}"
            )
            _write_json(
                first_error_path,
                {
                    "schema_version": (
                        "look-twice.v8-contract-progress-challenge-attempt-error/v1"
                    ),
                    "schedule_index": first_spec["schedule_index"],
                    "seed": first_spec["seed"],
                    "arm": first_spec["arm"],
                    "policy": first_spec["policy"],
                    "command_exit_code": 0,
                    "timed_out": False,
                    "termination_actions": [],
                    "launch_error": None,
                    "parse_error": recorded_parse_error,
                    "episode_validation_errors": [],
                    "retry_permitted": False,
                },
            )
            malformed_attempts = copy.deepcopy(attempts)
            malformed_attempts[0].update(
                {
                    "episode_sha256": file_sha256(first_episode_path),
                    "error_exists": True,
                    "error_sha256": file_sha256(first_error_path),
                    "attempt_integrity_valid": False,
                }
            )
            malformed_manifest = copy.deepcopy(clean_manifest)
            malformed_manifest["attempts"] = malformed_attempts
            malformed_manifest["attempt_accounting"]["valid"] = 39
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", malformed_attempts)
            _write_json(out / "RUN_MANIFEST.json", malformed_manifest)

            adverse_report, adverse_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="base",
            )
            self.assertEqual(
                adverse_report["attempt_accounting"]["structurally_valid"],
                39,
            )
            self.assertFalse(adverse_report["promotion_pass"])
            self.assertTrue(adverse_verification["structural_verification_pass"])
            _write_json(out / "REPORT.json", adverse_report)
            write_checksum_index(out)
            _, adverse_checksum_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="checksum",
            )
            adverse_checksum_verification["stage"] = "final"
            _write_json(out / "VERIFICATION.json", adverse_checksum_verification)
            final_adverse_report, final_adverse_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="final",
            )
            self.assertEqual(final_adverse_report, adverse_report)
            self.assertTrue(final_adverse_verification["checksum_valid"])

            for artifact in (
                out / "VERIFICATION.json",
                out / "SHA256SUMS",
                out / "REPORT.json",
            ):
                artifact.unlink()
            first_episode_path.write_bytes(original_episode_bytes)
            first_error_path.unlink()
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", attempts)
            _write_json(out / "RUN_MANIFEST.json", clean_manifest)

            # The runner flag is provisional because only the independent
            # verifier asks the frozen Go binary to authenticate raw receipts.
            # A well-formed Go rejection may downgrade true -> false, but still
            # yields a complete failed report instead of an exception.
            _authenticate.return_value = set()
            rejected_report, rejected_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="base",
            )
            self.assertFalse(rejected_report["promotion_pass"])
            self.assertEqual(
                rejected_report["attempt_accounting"][
                    "runner_provisional_integrity_downgraded_by_verifier"
                ],
                40,
            )
            self.assertTrue(rejected_verification["structural_verification_pass"])
            _write_json(out / "REPORT.json", rejected_report)
            verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="report",
            )
            (out / "REPORT.json").unlink()
            _authenticate.return_value = {"d" * 64}

            forged_downgrade_attempts = copy.deepcopy(attempts)
            forged_downgrade_attempts[0]["attempt_integrity_valid"] = False
            forged_downgrade_manifest = copy.deepcopy(clean_manifest)
            forged_downgrade_manifest["attempts"] = forged_downgrade_attempts
            forged_downgrade_manifest["attempt_accounting"]["valid"] = 39
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", forged_downgrade_attempts)
            _write_json(out / "RUN_MANIFEST.json", forged_downgrade_manifest)
            with self.assertRaisesRegex(VerificationError, "runner-provisional result"):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="base",
                )
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", attempts)
            _write_json(out / "RUN_MANIFEST.json", clean_manifest)

            # A stale runner summary cannot conceal a raw sampling hole.
            bad_samples = [dict(row) for row in samples]
            bad_samples[2]["captured_monotonic_ns"] = 8_400_000_000
            bad_samples[3]["captured_monotonic_ns"] = 8_500_000_000
            _write_jsonl(out / "raw/ROCM_SAMPLES.jsonl", bad_samples)
            with self.assertRaises(VerificationError):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="base",
                )
            _write_jsonl(out / "raw/ROCM_SAMPLES.jsonl", samples)

            # Matching tampered ATTEMPTS/manifest/window records still fail when
            # their chronological windows overlap the fixed prior cell.
            bad_attempts = [dict(row) for row in attempts]
            bad_windows = [dict(row) for row in windows]
            overlap_start = bad_attempts[0]["ended_monotonic_ns"] - 1
            bad_attempts[1]["started_monotonic_ns"] = overlap_start
            bad_attempts[1]["wall_seconds"] = (
                bad_attempts[1]["ended_monotonic_ns"] - overlap_start
            ) / 1e9
            bad_windows[1]["started_monotonic_ns"] = overlap_start
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", bad_attempts)
            _write_jsonl(out / "raw/EPISODE_WINDOWS.jsonl", bad_windows)
            bad_manifest = json.loads(
                (out / "RUN_MANIFEST.json").read_text(encoding="utf-8")
            )
            bad_manifest["attempts"] = bad_attempts
            _write_json(out / "RUN_MANIFEST.json", bad_manifest)
            with self.assertRaises(VerificationError):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="base",
                )
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", attempts)
            _write_jsonl(out / "raw/EPISODE_WINDOWS.jsonl", windows)
            restored_manifest = dict(bad_manifest)
            restored_manifest["attempts"] = attempts
            _write_json(out / "RUN_MANIFEST.json", restored_manifest)

            # Matching ATTEMPTS/manifest tampering still cannot alter the fixed
            # child argv after prestart.
            argv_tampered_attempts = copy.deepcopy(attempts)
            argv_tampered_attempts[0]["command"].extend(["--seed", "999999"])
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", argv_tampered_attempts)
            argv_tampered_manifest = dict(restored_manifest)
            argv_tampered_manifest["attempts"] = argv_tampered_attempts
            _write_json(out / "RUN_MANIFEST.json", argv_tampered_manifest)
            with self.assertRaisesRegex(
                VerificationError, "command differs from fixed argv"
            ):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="base",
                )
            _write_jsonl(out / "raw/ATTEMPTS.jsonl", attempts)
            _write_json(out / "RUN_MANIFEST.json", restored_manifest)

            # A missing postrun proof invalidates even an otherwise complete raw
            # package; the retained attempts remain untouched.
            postrun_path = out / "raw/POSTRUN_BINDING.json"
            postrun_payload = json.loads(postrun_path.read_text(encoding="utf-8"))
            postrun_path.unlink()
            with self.assertRaises(VerificationError):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="base",
                )
            _write_json(postrun_path, postrun_payload)

            # Exercise the exact creation sequence used by the formal runner:
            # independently derive the report, bind every prior artifact in the
            # checksum index, write the final verification, and recompute it.
            _write_json(out / "REPORT.json", report)
            write_checksum_index(out)
            _, checksum_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="checksum",
            )
            checksum_verification["stage"] = "final"
            _write_json(out / "VERIFICATION.json", checksum_verification)
            final_report, final_verification = verify_output(
                out,
                prereg_path,
                runner_path=RUNNER,
                verifier_path=VERIFIER,
                stage="final",
            )
            self.assertEqual(final_report, report)
            self.assertTrue(final_verification["structural_verification_pass"])
            self.assertTrue(final_verification["checksum_valid"])

            (out / "UNDECLARED.txt").write_text("bad", encoding="utf-8")
            with self.assertRaises(VerificationError):
                verify_output(
                    out,
                    prereg_path,
                    runner_path=RUNNER,
                    verifier_path=VERIFIER,
                    stage="final",
                )


if __name__ == "__main__":
    unittest.main()
