#!/usr/bin/env python3
"""Fail-closed verifier for checkpointed decision/dynamics recovery V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v8_additive_decision_dynamics_bridge import (  # noqa: E402
    EXPECTED_CHALLENGE_REPORT_SHA256,
    FORMAL_SEEDS,
    assess_trial,
    engineering_smoke_cases,
    load_formal_cases,
    sha256_file,
    summarize_trials,
)
from scripts.run_v8_additive_decision_dynamics_recovery_v2 import (  # noqa: E402
    BINDING_SCHEMA_VERSION,
    ENGINEERING_SEEDS,
    REPORT_SCHEMA_VERSION,
    checkpoint_errors,
    source_binding_sha256,
)


def _get(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _safe_child(root: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _attempt_errors(output_root: Path, expected_seeds: list[int]) -> list[str]:
    errors: list[str] = []
    attempts_path = output_root / "ATTEMPTS.jsonl"
    if not attempts_path.is_file():
        return ["ATTEMPTS.jsonl missing"]
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        attempts_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"ATTEMPTS.jsonl line {line_number}: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"ATTEMPTS.jsonl line {line_number}: expected object")
            continue
        events.append(event)
    sealed = [event for event in events if event.get("checkpoint_sealed") is True]
    sealed_seeds = [event.get("seed") for event in sealed]
    if sealed_seeds != expected_seeds:
        errors.append(
            "attempt log sealed seed order/count mismatch: "
            f"expected {expected_seeds}, observed {sealed_seeds}"
        )
    if len(set(sealed_seeds)) != len(sealed_seeds):
        errors.append("attempt log contains a repeated sealed seed")
    for event in events:
        seed = event.get("seed")
        if seed not in expected_seeds:
            errors.append(f"attempt log contains non-fixed seed: {seed!r}")
        if event.get("checkpoint_sealed") is True:
            checkpoint_path = _safe_child(output_root, event.get("checkpoint_path"))
            if checkpoint_path is None or not checkpoint_path.is_file():
                errors.append(f"sealed attempt checkpoint path invalid for seed {seed}")
            elif event.get("checkpoint_sha256") != sha256_file(checkpoint_path):
                errors.append(
                    f"sealed attempt checkpoint hash mismatch for seed {seed}"
                )
    return errors


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path | None = None,
    expected_run_class: str = "formal",
    verify_local_source: bool = True,
    verify_checkpoints: bool = True,
) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, observed {actual!r}")

    if expected_run_class not in ("formal", "engineering_smoke"):
        return [f"unsupported expected run class: {expected_run_class}"]
    expected_seeds = (
        list(FORMAL_SEEDS)
        if expected_run_class == "formal"
        else list(ENGINEERING_SEEDS)
    )
    cases = (
        load_formal_cases(
            ROOT
            / "release"
            / "v8-frozen"
            / "results"
            / "challenge_102500_102529"
            / "CHALLENGE_REPORT.json"
        )
        if expected_run_class == "formal"
        else engineering_smoke_cases()
    )

    require("schema_version", report.get("schema_version"), REPORT_SCHEMA_VERSION)
    require("run_class", report.get("run_class"), expected_run_class)
    for field, expected in (
        ("additive_non_locked", True),
        ("formal_result_eligible", False),
        ("changes_frozen_v8_endpoint", False),
        (
            "uses_archived_decisions_without_rerunning_policy",
            expected_run_class == "formal",
        ),
        ("oracle_used_by_controller", False),
        ("not_simultaneous_90_body_scene", True),
    ):
        require(f"boundary.{field}", _get(report, "boundary", field), expected)
    require(
        "decision_input.sha256",
        _get(report, "decision_input", "sha256"),
        EXPECTED_CHALLENGE_REPORT_SHA256,
    )
    require(
        "decision_input.fixed_seeds",
        _get(report, "decision_input", "fixed_seeds"),
        expected_seeds,
    )
    require(
        "decision_input.consumed_in_this_run",
        _get(report, "decision_input", "consumed_in_this_run"),
        expected_run_class == "formal",
    )
    execution_expected = {
        "layout": "one_fixed_seed_per_fresh_genesis_subprocess",
        "fixed_order_no_parallel_reordering": True,
        "atomic_checkpoint_per_completed_seed": True,
        "resume_accepts_only_unchanged_binding_and_sealed_prefix": True,
        "completed_checkpoint_reruns": 0,
        "seed_replacements": 0,
        "genesis_scene_count": len(expected_seeds),
        "non_fixed_robot_entities_per_scene": 3,
        "distinct_non_fixed_robot_entities_across_run": 3 * len(expected_seeds),
        "cross_seed_entities_share_scene": False,
        "active_and_passive_replicas_share_scene": True,
    }
    for field, expected in execution_expected.items():
        require(f"execution.{field}", _get(report, "execution", field), expected)
    require(
        "environment.all_worker_environments_identical",
        _get(report, "environment", "all_worker_environments_identical"),
        True,
    )
    require(
        "environment.backend_requested",
        _get(report, "environment", "worker_environment", "backend_requested"),
        "amdgpu",
    )
    if expected_run_class == "formal":
        if not _get(report, "environment", "worker_environment", "torch_hip"):
            errors.append("environment.worker_environment.torch_hip missing")
        if not _get(report, "environment", "worker_environment", "gpu"):
            errors.append("environment.worker_environment.gpu missing")
    require(
        "protocol.post_build_actuation_api",
        _get(report, "protocol", "post_build_actuation_api"),
        "control_dofs_velocity only",
    )
    require(
        "protocol.post_build_entity_pose_writes",
        _get(report, "protocol", "post_build_entity_pose_writes"),
        0,
    )
    require(
        "protocol.seed_order",
        _get(report, "protocol", "seed_order"),
        expected_seeds,
    )

    trials = report.get("trials")
    if not isinstance(trials, list):
        errors.append("trials: expected list")
        trials = []
    require(
        "trial seed order",
        [trial.get("seed") for trial in trials if isinstance(trial, dict)],
        expected_seeds,
    )
    for index, (case, trial) in enumerate(zip(cases, trials)):
        if not isinstance(trial, dict):
            errors.append(f"trials[{index}]: expected object")
            continue
        expected_decision = {
            "selected_corridor": case.selected_corridor,
            "full_chain_direct": case.full_chain_direct,
            "corridor_a_blocked": case.corridor_a_blocked,
            "corridor_b_blocked": case.corridor_b_blocked,
            "selected_corridor_clear": case.selected_corridor_clear,
            "both_corridors_blocked": case.both_corridors_blocked,
            "archived_episode_sha256": case.archived_episode_sha256,
            "input_class": case.input_class,
        }
        require(f"trials[{index}].decision", trial.get("decision"), expected_decision)
        require(
            f"trials[{index}].script_entity_pose_writes_after_build",
            trial.get("script_entity_pose_writes_after_build"),
            0,
        )
        try:
            assessment = assess_trial(trial)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"trials[{index}] cannot be assessed: {exc}")
        else:
            require(
                f"trials[{index}].assessment",
                trial.get("assessment"),
                assessment,
            )
            require(f"trials[{index}].assessment.passed", assessment["passed"], True)

    if trials:
        try:
            expected_summary = summarize_trials(trials, expected_run_class)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            errors.append(f"summary cannot be recomputed: {exc}")
        else:
            require("summary", report.get("summary"), expected_summary)
            require("summary.all_passed", expected_summary.get("all_passed"), True)
            require(
                "summary.distinct_non_fixed_robot_entities",
                expected_summary.get("distinct_non_fixed_robot_entities"),
                3 * len(expected_seeds),
            )
            require(
                "summary.total_blocker_contact_rows",
                expected_summary.get("total_blocker_contact_rows"),
                0,
            )
            require(
                "summary.total_active_pair_contact_rows",
                expected_summary.get("total_active_pair_contact_rows"),
                0,
            )

    binding: dict[str, Any] | None = None
    binding_sha = _get(report, "source", "source_binding_sha256")
    output_root = report_path.resolve().parent if report_path is not None else None
    if verify_local_source or verify_checkpoints:
        if output_root is None:
            errors.append("report_path required for source/checkpoint verification")
        else:
            binding_path = _safe_child(
                output_root, _get(report, "source", "source_binding_path")
            )
            if binding_path is None or not binding_path.is_file():
                errors.append("source binding path missing or escapes output root")
            else:
                try:
                    binding = _read_json_object(binding_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"source binding unreadable: {exc}")
                else:
                    require(
                        "source binding schema",
                        binding.get("schema_version"),
                        BINDING_SCHEMA_VERSION,
                    )
                    require(
                        "source binding run_class",
                        binding.get("run_class"),
                        expected_run_class,
                    )
                    require(
                        "source binding sha256",
                        source_binding_sha256(binding),
                        binding_sha,
                    )
                    require(
                        "source binding report copy",
                        _get(report, "source", "source_files"),
                        binding.get("source_files"),
                    )
                    if expected_run_class == "formal":
                        require(
                            "source binding initial git status",
                            binding.get("git_status_porcelain_at_initial_start"),
                            "",
                        )
                    if verify_local_source:
                        files = binding.get("source_files")
                        if not isinstance(files, dict):
                            errors.append("source binding file map missing")
                        else:
                            for name, row in files.items():
                                if not isinstance(row, dict):
                                    errors.append(f"source file row invalid: {name}")
                                    continue
                                path = _safe_child(ROOT, row.get("path"))
                                if path is None or not path.is_file():
                                    errors.append(
                                        f"source file missing or escapes root: {name}"
                                    )
                                elif sha256_file(path) != row.get("sha256"):
                                    errors.append(
                                        f"source file identity mismatch: {name}"
                                    )

    checkpoint_index = report.get("checkpoint_index")
    if not isinstance(checkpoint_index, list):
        errors.append("checkpoint_index: expected list")
        checkpoint_index = []
    require(
        "checkpoint index seeds",
        [row.get("seed") for row in checkpoint_index if isinstance(row, dict)],
        expected_seeds,
    )
    if verify_checkpoints and output_root is not None and binding is not None:
        for index, (case, row) in enumerate(zip(cases, checkpoint_index)):
            if not isinstance(row, dict):
                errors.append(f"checkpoint_index[{index}]: expected object")
                continue
            checkpoint_path = _safe_child(output_root, row.get("path"))
            if checkpoint_path is None or not checkpoint_path.is_file():
                errors.append(f"checkpoint {case.seed}: missing or escapes output root")
                continue
            if sha256_file(checkpoint_path) != row.get("sha256"):
                errors.append(f"checkpoint {case.seed}: hash mismatch")
                continue
            try:
                checkpoint = _read_json_object(checkpoint_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"checkpoint {case.seed}: unreadable: {exc}")
                continue
            errors.extend(
                f"checkpoint {case.seed}: {error}"
                for error in checkpoint_errors(
                    checkpoint,
                    case=case,
                    index=index,
                    run_class=expected_run_class,
                    binding_sha256=str(binding_sha),
                )
            )
            if index < len(trials):
                require(
                    f"checkpoint {case.seed} report trial copy",
                    checkpoint.get("trial"),
                    trials[index],
                )
        errors.extend(_attempt_errors(output_root, expected_seeds))
        progress_path = output_root / "PROGRESS.json"
        if not progress_path.is_file():
            errors.append("PROGRESS.json missing")
        else:
            try:
                progress = _read_json_object(progress_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"PROGRESS.json unreadable: {exc}")
            else:
                require(
                    "progress sealed prefix",
                    progress.get("sealed_prefix_seeds"),
                    expected_seeds,
                )
                require(
                    "progress sealed count",
                    progress.get("sealed_prefix_count"),
                    len(expected_seeds),
                )
                require("progress next seed", progress.get("next_seed"), None)
                require(
                    "progress outcomes hidden",
                    progress.get("outcomes_exposed_in_progress_file"),
                    False,
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--engineering-smoke", action="store_true")
    parser.add_argument("--skip-local-source", action="store_true")
    parser.add_argument("--skip-checkpoints", action="store_true")
    args = parser.parse_args()
    report_path = args.report.resolve()
    report = _read_json_object(report_path)
    run_class = "engineering_smoke" if args.engineering_smoke else "formal"
    errors = validate_report(
        report,
        report_path=report_path,
        expected_run_class=run_class,
        verify_local_source=not args.skip_local_source,
        verify_checkpoints=not args.skip_checkpoints,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"PASS: additive decision-to-dynamics recovery V2 "
        f"{report['summary']['passed']}/{report['summary']['trials']} "
        f"report_sha256={sha256_file(report_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
