#!/usr/bin/env python3
"""确定性汇总 v4 episode JSON/JSONL，并原子写出三张正式 CSV。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from v4_claims import canonical_json
from v4_metrics import EpisodeOutcome, aggregate_episode_outcomes


RUN_FIELDS = (
    "run_id",
    "source_file",
    "record_index",
    "schema_version",
    "policy",
    "profile",
    "seed",
    "status",
    "failure_type",
    "failure_message",
    "unsafe_crossing",
    "safe_success",
    "wrong_detour",
    "contract_repair_attempted",
    "contract_repair_success",
    "plan_invalidation_expected",
    "plan_invalidation_correct",
    "echo_present",
    "echo_rejection_success",
    "p_clear",
    "true_label",
    "prediction_set",
    "observation_count",
    "replan_count",
    "path_length",
    "record_sha256",
)

EPISODE_SCHEMA = "look-twice.episode/v4"
ERROR_SCHEMA = "look-twice.experiment-error/v4"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _metric_number(value: Any) -> float | None:
    boolean = _bool(value)
    if boolean is not None:
        return float(boolean)
    return _number(value)


def _last_receipt(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    candidates = payload.get("gate_receipts")
    if isinstance(candidates, list) and candidates:
        return _mapping(candidates[-1])
    candidate = payload.get("gate_receipt")
    if isinstance(candidate, Mapping):
        return candidate
    decisions = payload.get("action_decisions")
    if isinstance(decisions, list):
        for decision in reversed(decisions):
            receipt = _mapping(decision).get("gate_receipt")
            if isinstance(receipt, Mapping):
                return receipt
    return {}


def _echo_was_rejected(payload: Mapping[str, Any], metrics: Mapping[str, Any]) -> bool | None:
    direct = _bool(
        _first(
            metrics.get("echo_rejection_success"),
            metrics.get("echo_rejected"),
            metrics.get("redundant_evidence_rejected"),
        )
    )
    if direct is not None:
        return direct
    receipts = payload.get("gate_receipts")
    if not isinstance(receipts, list):
        receipts = [payload.get("gate_receipt")] if payload.get("gate_receipt") else []
    for receipt in receipts:
        for discounted in _mapping(receipt).get("discounted_claims", []):
            reason = str(_mapping(discounted).get("reason", ""))
            if reason.startswith("artifact_duplicate_of:"):
                return True
    return None


def normalize_episode(
    payload: Mapping[str, Any], *, source_file: str, record_index: int
) -> dict[str, Any]:
    configuration = _mapping(_first(payload.get("configuration"), payload.get("config")))
    experiment_runner = _mapping(payload.get("experiment_runner"))
    scenario = _mapping(payload.get("scenario"))
    oracle_context = _mapping(scenario.get("oracle_context"))
    error_runner = _mapping(payload.get("runner"))
    metrics = _mapping(payload.get("metrics"))
    outcome = _mapping(payload.get("outcome"))
    belief = _mapping(outcome.get("belief"))
    oracle = _mapping(payload.get("oracle"))
    receipt = _last_receipt(payload)

    policy = str(
        _first(
            configuration.get("policy"),
            experiment_runner.get("policy"),
            error_runner.get("policy"),
            payload.get("policy"),
            "unknown",
        )
    )
    profile = str(
        _first(
            configuration.get("profile"),
            experiment_runner.get("profile"),
            oracle_context.get("profile"),
            error_runner.get("profile"),
            payload.get("profile"),
            "unknown",
        )
    )
    seed = _integer(
        _first(
            configuration.get("seed"),
            experiment_runner.get("seed"),
            oracle_context.get("seed"),
            error_runner.get("seed"),
            payload.get("seed"),
        )
    )
    supplied_status = str(payload.get("status", "")).lower()
    is_runner_error = payload.get("schema_version") == ERROR_SCHEMA
    failed = (
        is_runner_error
        or supplied_status in ("failed", "error", "exception")
        or payload.get("error") is not None
    )
    missing_identity = policy == "unknown" or profile == "unknown" or seed is None
    if missing_identity:
        failed = True
    status = "failed" if failed else "completed"
    failure_type = str(
        _first(
            payload.get("failure_type"),
            payload.get("reason") if is_runner_error else None,
            "schema_error" if missing_identity else None,
            "episode_error" if failed else "",
        )
    )
    failure_message = str(
        _first(
            payload.get("failure_message"),
            payload.get("error"),
            payload.get("stderr_tail") if is_runner_error else None,
            "missing policy/profile/seed" if missing_identity else "",
        )
    )

    repair_attempt_count = _integer(
        _first(metrics.get("contract_repair_attempts"), metrics.get("repair_attempts"))
    )
    repair_attempted = _bool(metrics.get("contract_repair_attempted"))
    if repair_attempted is None:
        repair_attempted = bool(repair_attempt_count and repair_attempt_count > 0)
    repair_success = _bool(
        _first(metrics.get("contract_repair_success"), metrics.get("repair_success"))
    )
    if repair_success is None:
        successes = _integer(metrics.get("contract_repair_successes"))
        repair_success = successes > 0 if successes is not None and repair_attempted else None
    if repair_success is True:
        repair_attempted = True

    invalidation_expected = _bool(metrics.get("plan_invalidation_expected"))
    if invalidation_expected is None:
        expected_count = _integer(metrics.get("plan_invalidations_expected"))
        invalidation_expected = bool(expected_count and expected_count > 0)
    invalidation_correct = _bool(
        _first(metrics.get("plan_invalidation_correct"), metrics.get("invalidation_correct"))
    )
    if invalidation_correct is True:
        invalidation_expected = True

    echo_present = _bool(metrics.get("echo_present"))
    if echo_present is None:
        echo_present = profile == "evidence-echo"
    echo_rejection = _echo_was_rejected(payload, metrics) if echo_present else None

    p_clear = _number(metrics.get("p_clear"))
    if p_clear is None:
        p_blocked = _number(
            _first(metrics.get("p_blocked"), belief.get("p_blocked"), receipt.get("p_blocked"))
        )
        p_clear = 1.0 - p_blocked if p_blocked is not None else None
    true_label = _first(metrics.get("true_label"), oracle.get("true_label"))
    if true_label is None:
        truth_blocked = _bool(outcome.get("final_truth_blocked"))
        true_label = (
            "blocked" if truth_blocked else "clear" if truth_blocked is not None else None
        )
    if true_label not in ("clear", "blocked"):
        true_label = None
    prediction_set = _first(metrics.get("prediction_set"), receipt.get("prediction_set"), [])
    if not isinstance(prediction_set, list) or any(
        value not in ("clear", "blocked") for value in prediction_set
    ):
        prediction_set = []

    run_id = str(
        _first(
            payload.get("run_id"),
            payload.get("episode_id"),
            f"{policy}__{profile}__seed-{seed}" if seed is not None else None,
            f"{source_file}#{record_index}",
        )
    )
    return {
        "run_id": run_id,
        "source_file": source_file,
        "record_index": record_index,
        "schema_version": payload.get("schema_version", ""),
        "policy": policy,
        "profile": profile,
        "seed": seed if seed is not None else "",
        "status": status,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "unsafe_crossing": _bool(metrics.get("unsafe_crossing")),
        "safe_success": _bool(metrics.get("safe_success")),
        "wrong_detour": _bool(metrics.get("wrong_detour")),
        "contract_repair_attempted": repair_attempted,
        "contract_repair_success": repair_success,
        "plan_invalidation_expected": invalidation_expected,
        "plan_invalidation_correct": invalidation_correct,
        "echo_present": echo_present,
        "echo_rejection_success": echo_rejection,
        "p_clear": p_clear,
        "true_label": true_label or "",
        "prediction_set": canonical_json(prediction_set),
        "observation_count": _integer(metrics.get("observation_count")),
        "replan_count": _integer(metrics.get("replan_count")),
        "path_length": _number(metrics.get("path_length")),
        "record_sha256": hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest(),
    }


def load_error_row(source_file: str, record_index: int, message: str, raw: str) -> dict[str, Any]:
    payload = {
        "load_error": message,
        "raw_input": raw,
    }
    row = normalize_episode(payload, source_file=source_file, record_index=record_index)
    row["failure_type"] = "load_error"
    row["failure_message"] = message
    row["status"] = "failed"
    return row


def safe_normalize_episode(
    payload: Mapping[str, Any], *, source_file: str, record_index: int, raw: str
) -> dict[str, Any]:
    try:
        return normalize_episode(
            payload, source_file=source_file, record_index=record_index
        )
    except (TypeError, ValueError, OverflowError) as exc:
        return load_error_row(
            source_file,
            record_index,
            f"episode normalization failed: {exc}",
            raw,
        )


def load_file(path: Path) -> list[dict[str, Any]]:
    source = str(path.resolve())
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [load_error_row(source, 1, str(exc), "")]
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append(load_error_row(source, line_number, f"invalid JSON: {exc.msg}", line))
                continue
            if not isinstance(payload, Mapping):
                rows.append(load_error_row(source, line_number, "record must be an object", line))
            else:
                rows.append(
                    safe_normalize_episode(
                        payload,
                        source_file=source,
                        record_index=line_number,
                        raw=line,
                    )
                )
        return rows
    if path.suffix.lower() != ".json":
        return [load_error_row(source, 1, "unsupported file extension", text)]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return [load_error_row(source, 1, f"invalid JSON: {exc.msg}", text)]
    # An experiment root also contains runner summaries, benchmarks and
    # generated summaries.  Those are metadata, not failed episodes.  Explicit
    # runner error records remain first-class failed rows.
    if isinstance(payload, Mapping):
        schema = payload.get("schema_version")
        episode_like = (
            schema in (EPISODE_SCHEMA, ERROR_SCHEMA)
            or "episodes" in payload
            or ("configuration" in payload and "metrics" in payload)
        )
        if not episode_like:
            return []
    episodes: Any = payload.get("episodes") if isinstance(payload, Mapping) and "episodes" in payload else payload
    if isinstance(episodes, Mapping):
        episodes = [episodes]
    if not isinstance(episodes, list):
        return [load_error_row(source, 1, "JSON must contain an object, array, or episodes array", text)]
    rows = []
    for index, episode in enumerate(episodes, start=1):
        if isinstance(episode, Mapping):
            rows.append(
                safe_normalize_episode(
                    episode,
                    source_file=source,
                    record_index=index,
                    raw=text,
                )
            )
        else:
            rows.append(load_error_row(source, index, "episode must be an object", canonical_json(episode)))
    return rows


def discover_files(inputs: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for item in inputs:
        if item.is_dir():
            files.update(path.resolve() for path in item.rglob("*.json") if path.is_file())
            files.update(path.resolve() for path in item.rglob("*.jsonl") if path.is_file())
        else:
            files.add(item.resolve())
    return sorted(files, key=lambda path: str(path))


def row_to_outcome(row: Mapping[str, Any]) -> EpisodeOutcome:
    prediction_set = json.loads(row["prediction_set"]) if row.get("prediction_set") else []
    return EpisodeOutcome(
        unsafe_crossing=_bool(row.get("unsafe_crossing")),
        safe_success=_bool(row.get("safe_success")),
        wrong_detour=_bool(row.get("wrong_detour")),
        contract_repair_attempted=bool(_bool(row.get("contract_repair_attempted"))),
        contract_repair_success=_bool(row.get("contract_repair_success")),
        plan_invalidation_expected=bool(_bool(row.get("plan_invalidation_expected"))),
        plan_invalidation_correct=_bool(row.get("plan_invalidation_correct")),
        echo_present=bool(_bool(row.get("echo_present"))),
        echo_rejection_success=_bool(row.get("echo_rejection_success")),
        p_clear=_number(row.get("p_clear")),
        true_label=row.get("true_label") or None,
        prediction_set=tuple(prediction_set),
        failed=row.get("status") != "completed",
    )


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["policy"]), str(row["profile"]))].append(row)
    aggregates = []
    for (policy, profile), group in sorted(groups.items()):
        aggregate = {
            "policy": policy,
            "profile": profile,
            **aggregate_episode_outcomes(row_to_outcome(row) for row in group),
        }
        for output_name, input_name in (
            ("avg_observation_count", "observation_count"),
            ("avg_replan_count", "replan_count"),
            ("avg_path_length", "path_length"),
        ):
            values = [_number(row.get(input_name)) for row in group]
            available = [value for value in values if value is not None]
            aggregate[output_name] = sum(available) / len(available) if available else ""
        aggregates.append(aggregate)
    return aggregates


PAIR_METRICS = {
    "unsafe_crossing": False,
    "safe_success": True,
    "wrong_detour": False,
    "contract_repair_success": True,
    "plan_invalidation_correct": True,
    "echo_rejection_success": True,
    "observation_count": False,
    "path_length": False,
}


def paired_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        seed = _integer(row.get("seed"))
        if row.get("status") == "completed" and seed is not None:
            by_key[(str(row["policy"]), str(row["profile"]), seed)].append(row)
    profiles = sorted({key[1] for key in by_key})
    output = []
    for profile in profiles:
        policies = sorted({key[0] for key in by_key if key[1] == profile})
        for policy_a, policy_b in itertools.combinations(policies, 2):
            seeds_a = {key[2] for key, value in by_key.items() if key[:2] == (policy_a, profile) and len(value) == 1}
            seeds_b = {key[2] for key, value in by_key.items() if key[:2] == (policy_b, profile) and len(value) == 1}
            shared_seeds = sorted(seeds_a & seeds_b)
            for metric, higher_is_better in PAIR_METRICS.items():
                pairs = []
                for seed in shared_seeds:
                    left = by_key[(policy_a, profile, seed)][0]
                    right = by_key[(policy_b, profile, seed)][0]
                    left_value = _metric_number(left.get(metric))
                    right_value = _metric_number(right.get(metric))
                    if left_value is not None and right_value is not None:
                        pairs.append((left_value, right_value))
                if not pairs:
                    continue
                differences = [right - left for left, right in pairs]
                b_better = sum(
                    right > left if higher_is_better else right < left
                    for left, right in pairs
                )
                a_better = sum(
                    left > right if higher_is_better else left < right
                    for left, right in pairs
                )
                output.append(
                    {
                        "profile": profile,
                        "policy_a": policy_a,
                        "policy_b": policy_b,
                        "metric": metric,
                        "higher_is_better": higher_is_better,
                        "shared_seed_count": len(shared_seeds),
                        "eligible_pairs": len(pairs),
                        "mean_a": sum(left for left, _ in pairs) / len(pairs),
                        "mean_b": sum(right for _, right in pairs) / len(pairs),
                        "mean_difference_b_minus_a": sum(differences) / len(differences),
                        "a_better": a_better,
                        "ties": len(pairs) - a_better - b_better,
                        "b_better": b_better,
                    }
                )
    return output


def atomic_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = tuple(fieldnames)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
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
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = discover_files(args.input)
    if not files:
        raise SystemExit("No episode JSON or JSONL files found")
    rows = []
    for path in files:
        rows.extend(load_file(path))
    rows.sort(key=lambda row: (str(row["policy"]), str(row["profile"]), str(row["seed"]), str(row["source_file"]), int(row["record_index"])))
    aggregates = aggregate_rows(rows)
    comparisons = paired_rows(rows)

    aggregate_fields = tuple(aggregates[0]) if aggregates else ("policy", "profile")
    comparison_fields = tuple(comparisons[0]) if comparisons else (
        "profile", "policy_a", "policy_b", "metric", "higher_is_better",
        "shared_seed_count", "eligible_pairs", "mean_a", "mean_b",
        "mean_difference_b_minus_a", "a_better", "ties", "b_better",
    )
    atomic_csv(args.output_dir / "runs.csv", rows, RUN_FIELDS)
    atomic_csv(args.output_dir / "aggregate.csv", aggregates, aggregate_fields)
    atomic_csv(args.output_dir / "paired_comparisons.csv", comparisons, comparison_fields)
    print(
        f"summarized files={len(files)} episodes={len(rows)} "
        f"failures={sum(row['status'] != 'completed' for row in rows)}"
    )
    print(f"output: {args.output_dir}")


if __name__ == "__main__":
    main()
