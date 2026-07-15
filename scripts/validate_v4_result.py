#!/usr/bin/env python3
"""Strict, standard-library audit of Look Twice v4 episode JSON.

The validator deliberately treats experimental conclusions as data, not truth:
it verifies provenance, receipt integrity, online/oracle separation, action-gate
semantics, and motion/result consistency.  It supports one or more files and
directories and exits non-zero if any episode is invalid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EPISODE_SCHEMA = "look-twice.episode/v4"
CLAIM_SCHEMA = "look-twice.robot-claim/v1"
GATE_SCHEMA = "purify.robotics.gate-receipt/v1"
INVALIDATION_SCHEMA = "purify.robotics.plan-invalidation-receipt/v1"
CONTRACT_SCHEMA = "purify.robotics.action-contract/v1"
CALIBRATION_SCHEMA = "purify.robotics.calibration.v1"
PROFILES = {
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "pose-calibration-drift",
    "structured-depth-dropout",
    "dynamic-change",
    "ood-severity",
}
UNKNOWN_ROOTS = {"", "unknown", "unavailable", "none"}
ONLINE_FORBIDDEN_KEYS = {
    "oracle",
    "oracle_context",
    "ground_truth",
    "true_label",
    "world_truth",
    "fault_realization",
    "future_observation",
    "future_observations",
}
CLAIM_FIELDS = {
    "schema_version",
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
    "pose_version",
    "model_id",
    "artifact_sha256",
    "parent_claim_ids",
    "quality",
    "visibility",
    "temporal_skew",
    "scope",
}
CONTRACT_FIELDS = {
    "schema_version",
    "contract_id",
    "action",
    "fact_id",
    "predicate",
    "scope",
    "required_prediction_set",
    "max_evidence_age",
    "min_distinct_measurement_roots",
    "max_modality_skew",
    "max_unresolved_conflicts",
    "require_calibration_applicable",
}
GATE_FIELDS = {
    "schema_version",
    "receipt_id",
    "contract_id",
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
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "git_commit",
    "configuration",
    "scenario",
    "environment",
    "action_contracts",
    "calibration_artifact",
    "gate_calibration_artifact",
    "claims",
    "gate_submitted_claims",
    "evidence",
    "gate_receipts",
    "repair_decisions",
    "plan_invalidation_receipts",
    "policy_decisions",
    "motion_segments",
    "oracle",
    "metrics",
    "outcome",
    # Optional provenance stamped by scripts/run_v4_experiments.py.
    "experiment_runner",
}


class DuplicateKeyError(ValueError):
    pass


def _pairs_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=reject_constant,
        )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    payload = dict(receipt)
    payload["receipt_sha256"] = ""
    return canonical_sha256(payload)


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _known_root(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() not in UNKNOWN_ROOTS


def _scope_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"robot_id", "payload_id", "region_id"}
        and all(isinstance(item, str) and item for item in value.values())
    )


class Audit:
    def __init__(self, source: str) -> None:
        self.source = source
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{self.source}:{path}: {message}")

    def exact_fields(self, value: Any, expected: set[str], path: str) -> bool:
        if not isinstance(value, dict):
            self.error(path, "must be an object")
            return False
        missing, extra = expected - set(value), set(value) - expected
        if missing:
            self.error(path, f"missing fields {sorted(missing)}")
        if extra:
            self.error(path, f"unknown fields {sorted(extra)}")
        return not missing and not extra


def _walk_forbidden(audit: Audit, value: Any, path: str) -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).lower()
            if key in ONLINE_FORBIDDEN_KEYS or key.startswith("oracle_"):
                audit.error(f"{path}.{raw_key}", "oracle/evaluator data leaked into an online section")
            _walk_forbidden(audit, child, f"{path}.{raw_key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(audit, child, f"{path}[{index}]")


def _validate_claims(
    audit: Audit, values: Any, path: str
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    if not isinstance(values, list):
        audit.error(path, "must be an array")
        return {}, {}
    claims: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    for index, claim in enumerate(values):
        item_path = f"{path}[{index}]"
        if not audit.exact_fields(claim, CLAIM_FIELDS, item_path):
            continue
        _walk_forbidden(audit, claim, item_path)
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            audit.error(f"{item_path}.claim_id", "must be a non-empty string")
            continue
        if claim_id in claims:
            audit.error(f"{item_path}.claim_id", f"duplicate claim_id {claim_id}")
        claims[claim_id] = claim
        if claim.get("schema_version") != CLAIM_SCHEMA:
            audit.error(f"{item_path}.schema_version", f"must be {CLAIM_SCHEMA}")
        for key in ("fact_id", "predicate", "modality", "calibration_id", "pose_version", "model_id"):
            if not isinstance(claim.get(key), str) or not claim[key]:
                audit.error(f"{item_path}.{key}", "must be a non-empty string")
        if claim.get("value") not in {"clear", "blocked", "inconclusive"}:
            audit.error(f"{item_path}.value", "must be clear, blocked, or inconclusive")
        for key in ("confidence", "quality", "visibility"):
            value = claim.get(key)
            if not _is_number(value) or not 0 <= float(value) <= 1:
                audit.error(f"{item_path}.{key}", "must be finite and in [0,1]")
        observed, valid_until, skew = (
            claim.get("observed_step"),
            claim.get("valid_until_step"),
            claim.get("temporal_skew"),
        )
        if not _is_int(observed) or observed < 0:
            audit.error(f"{item_path}.observed_step", "must be a non-negative integer")
        if not _is_int(valid_until) or not _is_int(observed) or valid_until < observed:
            audit.error(f"{item_path}.valid_until_step", "must be an integer no earlier than observed_step")
        if not _is_int(skew) or skew < 0:
            audit.error(f"{item_path}.temporal_skew", "must be a non-negative integer")
        if not _is_sha256(claim.get("artifact_sha256")):
            audit.error(f"{item_path}.artifact_sha256", "must be lowercase SHA-256")
        if not _scope_valid(claim.get("scope")):
            audit.error(f"{item_path}.scope", "must contain exact non-empty robot/payload/region IDs")
        parents = claim.get("parent_claim_ids")
        if not isinstance(parents, list) or any(not isinstance(item, str) or not item for item in parents):
            audit.error(f"{item_path}.parent_claim_ids", "must be an array of non-empty strings")
        elif len(parents) != len(set(parents)):
            audit.error(f"{item_path}.parent_claim_ids", "must not contain duplicates")
        else:
            for parent in parents:
                children[parent].append(claim_id)

    for claim_id, claim in claims.items():
        for parent in claim.get("parent_claim_ids", []):
            if parent not in claims:
                audit.error(f"{path}.{claim_id}.parent_claim_ids", f"missing parent Claim {parent}")
            if parent == claim_id:
                audit.error(f"{path}.{claim_id}.parent_claim_ids", "a Claim cannot parent itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(claim_id: str) -> None:
        if claim_id in visiting:
            audit.error(path, f"Claim DAG contains a cycle at {claim_id}")
            return
        if claim_id in visited:
            return
        visiting.add(claim_id)
        for child in children.get(claim_id, []):
            if child in claims:
                visit(child)
        visiting.remove(claim_id)
        visited.add(claim_id)

    for claim_id in sorted(claims):
        visit(claim_id)
    return claims, children


def _validate_contracts(audit: Audit, values: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list) or not values:
        audit.error("$.action_contracts", "must be a non-empty array")
        return {}
    contracts: dict[str, dict[str, Any]] = {}
    for index, contract in enumerate(values):
        path = f"$.action_contracts[{index}]"
        if not audit.exact_fields(contract, CONTRACT_FIELDS, path):
            continue
        contract_id = contract.get("contract_id")
        if not isinstance(contract_id, str) or not contract_id:
            audit.error(f"{path}.contract_id", "must be non-empty")
            continue
        if contract_id in contracts:
            audit.error(f"{path}.contract_id", "duplicate contract_id")
        contracts[contract_id] = contract
        if contract.get("schema_version") != CONTRACT_SCHEMA:
            audit.error(f"{path}.schema_version", f"must be {CONTRACT_SCHEMA}")
        if not _scope_valid(contract.get("scope")):
            audit.error(f"{path}.scope", "invalid action scope")
        prediction = contract.get("required_prediction_set")
        if not isinstance(prediction, list) or not prediction or len(prediction) != len(set(prediction)) or not set(prediction) <= {"clear", "blocked"}:
            audit.error(f"{path}.required_prediction_set", "must be a unique non-empty clear/blocked set")
        for key, minimum in (
            ("max_evidence_age", 0),
            ("min_distinct_measurement_roots", 1),
            ("max_modality_skew", 0),
            ("max_unresolved_conflicts", 0),
        ):
            if not _is_int(contract.get(key)) or contract[key] < minimum:
                audit.error(f"{path}.{key}", f"must be an integer >= {minimum}")
        if type(contract.get("require_calibration_applicable")) is not bool:
            audit.error(f"{path}.require_calibration_applicable", "must be boolean")
    actions = {item.get("action") for item in contracts.values()}
    if not {"cross_region", "take_detour"} <= actions:
        audit.error("$.action_contracts", "must contain cross_region and take_detour contracts")
    return contracts


def _validate_calibration(audit: Audit, artifact: Any, path: str) -> None:
    required = {
        "schema_version", "artifact_id", "alpha", "class_quantiles",
        "applicable_profiles", "min_noise_intensity", "max_noise_intensity",
        "sensor_versions", "git_commit", "dataset_sha256", "seed_ranges",
    }
    if not audit.exact_fields(artifact, required, path):
        return
    if artifact.get("schema_version") != CALIBRATION_SCHEMA:
        audit.error(f"{path}.schema_version", f"must be {CALIBRATION_SCHEMA}")
    if not isinstance(artifact.get("artifact_id"), str) or not artifact["artifact_id"]:
        audit.error(f"{path}.artifact_id", "must be non-empty")
    if not _is_number(artifact.get("alpha")) or not 0 < float(artifact["alpha"]) < 1:
        audit.error(f"{path}.alpha", "must be in (0,1)")
    quantiles = artifact.get("class_quantiles")
    if not isinstance(quantiles, dict) or set(quantiles) != {"clear", "blocked"} or any(not _is_number(value) or not 0 <= float(value) <= 1 for value in getattr(quantiles, "values", lambda: [])()):
        audit.error(f"{path}.class_quantiles", "must contain finite clear/blocked quantiles in [0,1]")
    profiles = artifact.get("applicable_profiles")
    if not isinstance(profiles, list) or not profiles or not set(profiles) <= PROFILES - {"ood-severity"}:
        audit.error(f"{path}.applicable_profiles", "must be non-empty ID profiles only")
    if not _is_sha256(artifact.get("dataset_sha256")):
        audit.error(f"{path}.dataset_sha256", "must be lowercase SHA-256")
    if not isinstance(artifact.get("sensor_versions"), list) or not artifact["sensor_versions"]:
        audit.error(f"{path}.sensor_versions", "must be non-empty")
    if not isinstance(artifact.get("seed_ranges"), list) or not artifact["seed_ranges"]:
        audit.error(f"{path}.seed_ranges", "must be non-empty")
    else:
        for index, seed_range in enumerate(artifact["seed_ranges"]):
            if not isinstance(seed_range, dict) or set(seed_range) != {"start", "end"} or not _is_int(seed_range.get("start")) or not _is_int(seed_range.get("end")) or seed_range["start"] < 0 or seed_range["end"] < seed_range["start"]:
                audit.error(f"{path}.seed_ranges[{index}]", "must be an inclusive non-negative {start,end} range")


def _lineage_roots(claims: Sequence[dict[str, Any]]) -> tuple[set[str], set[str]]:
    physical = [claim for claim in claims if claim.get("modality") != "static_map"]
    if not physical:
        return set(), set()
    parent = list(range(len(physical)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    by_capture: dict[str, int] = {}
    by_artifact: dict[str, int] = {}
    by_id = {claim["claim_id"]: index for index, claim in enumerate(physical)}
    for index, claim in enumerate(physical):
        capture = claim.get("capture_root_id")
        if _known_root(capture):
            if capture in by_capture:
                union(index, by_capture[capture])
            else:
                by_capture[capture] = index
        artifact = claim.get("artifact_sha256")
        if _is_sha256(artifact):
            if artifact in by_artifact:
                union(index, by_artifact[artifact])
            else:
                by_artifact[artifact] = index
    for index, claim in enumerate(physical):
        for parent_id in claim.get("parent_claim_ids", []):
            if parent_id in by_id:
                union(index, by_id[parent_id])

    components: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, claim in enumerate(physical):
        components[find(index)].append(claim)
    roots, devices = set(), set()
    for component in components.values():
        captures = sorted({claim["capture_root_id"] for claim in component if _known_root(claim.get("capture_root_id"))})
        component_devices = sorted({claim["device_root_id"] for claim in component if _known_root(claim.get("device_root_id"))})
        if not captures or not component_devices:
            continue
        if len(captures) == 1:
            roots.add(captures[0])
        else:
            roots.add("lineage:" + canonical_sha256(captures)[:16])
        devices.update(component_devices)
    return roots, devices


def _expected_prediction_set(p_blocked: float, applicable: bool, calibration: Mapping[str, Any]) -> list[str]:
    if not applicable:
        return ["clear", "blocked"]
    quantiles = calibration.get("class_quantiles", {})
    selected: list[str] = []
    if p_blocked <= float(quantiles.get("clear", -1)):
        selected.append("clear")
    if 1 - p_blocked <= float(quantiles.get("blocked", -1)):
        selected.append("blocked")
    return selected or ["clear", "blocked"]


def _validate_gate_receipts(
    audit: Audit,
    values: Any,
    claims: Mapping[str, dict[str, Any]],
    contracts: Mapping[str, dict[str, Any]],
    calibration: Mapping[str, Any],
    profile: str | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        audit.error("$.gate_receipts", "must be an array")
        return {}
    receipts: dict[str, dict[str, Any]] = {}
    for index, receipt in enumerate(values):
        path = f"$.gate_receipts[{index}]"
        if not audit.exact_fields(receipt, GATE_FIELDS, path):
            continue
        _walk_forbidden(audit, receipt, path)
        receipt_hash = receipt.get("receipt_sha256")
        if not _is_sha256(receipt_hash) or receipt_sha256(receipt) != receipt_hash:
            audit.error(f"{path}.receipt_sha256", "does not match Go-compatible canonical receipt hash")
        if receipt.get("schema_version") != GATE_SCHEMA:
            audit.error(f"{path}.schema_version", f"must be {GATE_SCHEMA}")
        receipt_id = receipt.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id.startswith("gate:"):
            audit.error(f"{path}.receipt_id", "must be a gate receipt ID")
        if isinstance(receipt_hash, str):
            if receipt_hash in receipts:
                audit.error(f"{path}.receipt_sha256", "duplicate GateReceipt hash")
            receipts[receipt_hash] = receipt

        contract = contracts.get(receipt.get("contract_id"))
        if contract is None:
            audit.error(f"{path}.contract_id", "does not reference a published ActionContract")
            continue
        for key in ("action", "fact_id", "predicate", "scope"):
            if receipt.get(key) != contract.get(key):
                audit.error(f"{path}.{key}", "does not match the referenced ActionContract")
        if receipt.get("calibration_artifact_id") != calibration.get("artifact_id"):
            audit.error(f"{path}.calibration_artifact_id", "does not match gate_calibration_artifact")
        p_blocked = receipt.get("p_blocked")
        if not _is_number(p_blocked) or not 0 <= float(p_blocked) <= 1:
            audit.error(f"{path}.p_blocked", "must be finite and in [0,1]")
        prediction = receipt.get("prediction_set")
        if not isinstance(prediction, list) or not prediction or len(prediction) != len(set(prediction)) or not set(prediction) <= {"clear", "blocked"}:
            audit.error(f"{path}.prediction_set", "must be a unique non-empty clear/blocked set")
        elif _is_number(p_blocked):
            expected = _expected_prediction_set(float(p_blocked), receipt.get("calibration_applicable") is True, calibration)
            if prediction != expected:
                audit.error(f"{path}.prediction_set", f"expected conformal set {expected}, got {prediction}")
        if profile == "ood-severity" and receipt.get("calibration_applicable") is not False:
            audit.error(f"{path}.calibration_applicable", "OOD profile must be calibration_not_applicable")

        used = receipt.get("used_claim_ids")
        discounted = receipt.get("discounted_claims")
        if not isinstance(used, list) or len(used) != len(set(used)):
            audit.error(f"{path}.used_claim_ids", "must be a unique array")
            used = []
        if not isinstance(discounted, list):
            audit.error(f"{path}.discounted_claims", "must be an array")
            discounted = []
        used_set = set(used)
        used_claims: list[dict[str, Any]] = []
        for claim_id in used:
            claim = claims.get(claim_id)
            if claim is None:
                audit.error(f"{path}.used_claim_ids", f"unknown Claim {claim_id}")
                continue
            used_claims.append(claim)
            if claim.get("fact_id") != receipt.get("fact_id") or claim.get("predicate") != receipt.get("predicate") or claim.get("scope") != receipt.get("scope"):
                audit.error(f"{path}.used_claim_ids", f"Claim {claim_id} has incompatible fact/scope")
            step = receipt.get("evaluated_step")
            if _is_int(step) and not claim["observed_step"] <= step <= claim["valid_until_step"]:
                audit.error(f"{path}.used_claim_ids", f"Claim {claim_id} was not fresh at evaluation")
        discounted_ids: set[str] = set()
        for item_index, item in enumerate(discounted):
            item_path = f"{path}.discounted_claims[{item_index}]"
            if not isinstance(item, dict) or set(item) != {"claim_id", "reason"}:
                audit.error(item_path, "must contain exactly claim_id and reason")
                continue
            claim_id, reason = item.get("claim_id"), item.get("reason")
            if claim_id not in claims:
                audit.error(f"{item_path}.claim_id", f"unknown Claim {claim_id}")
            if claim_id in discounted_ids:
                audit.error(f"{item_path}.claim_id", "duplicate discounted Claim")
            discounted_ids.add(claim_id)
            if claim_id in used_set:
                audit.error(item_path, "a Claim cannot be both used and discounted")
            if isinstance(reason, str) and reason.startswith("artifact_duplicate_of:"):
                original_id = reason.split(":", 1)[1]
                original, duplicate = claims.get(original_id), claims.get(claim_id)
                if original is None or duplicate is None or original.get("artifact_sha256") != duplicate.get("artifact_sha256"):
                    audit.error(item_path, "artifact echo reason does not reference an exact matching artifact")

        artifacts: dict[str, str] = {}
        for claim in used_claims:
            artifact = claim.get("artifact_sha256")
            if artifact in artifacts:
                audit.error(f"{path}.used_claim_ids", f"artifact echo counted twice: {artifacts[artifact]} and {claim['claim_id']}")
            artifacts[artifact] = claim["claim_id"]
        expected_roots, expected_devices = _lineage_roots(used_claims)
        root_ids, device_ids = receipt.get("measurement_root_ids"), receipt.get("device_root_ids")
        if not isinstance(root_ids, list) or len(root_ids) != len(set(root_ids)):
            audit.error(f"{path}.measurement_root_ids", "must be a unique array")
            root_ids = []
        if not isinstance(device_ids, list) or len(device_ids) != len(set(device_ids)):
            audit.error(f"{path}.device_root_ids", "must be a unique array")
            device_ids = []
        if set(root_ids) != expected_roots:
            audit.error(f"{path}.measurement_root_ids", f"expected root-aware set {sorted(expected_roots)}, got {sorted(root_ids)}")
        if set(device_ids) != expected_devices:
            audit.error(f"{path}.device_root_ids", f"expected device roots {sorted(expected_devices)}, got {sorted(device_ids)}")

        clauses = receipt.get("clauses")
        clause_map: dict[str, dict[str, Any]] = {}
        if not isinstance(clauses, list):
            audit.error(f"{path}.clauses", "must be an array")
            clauses = []
        for clause_index, clause in enumerate(clauses):
            if not isinstance(clause, dict) or set(clause) != {"clause", "required", "actual", "passed"}:
                audit.error(f"{path}.clauses[{clause_index}]", "invalid clause shape")
                continue
            name = clause.get("clause")
            if name in clause_map:
                audit.error(f"{path}.clauses[{clause_index}]", f"duplicate clause {name}")
            clause_map[name] = clause
        required_names = {
            "prediction_set", "evidence_age", "distinct_measurement_roots",
            "modality_skew", "unresolved_conflicts",
            "calibration_applicable", "scope_match",
        }
        if set(clause_map) != required_names:
            audit.error(f"{path}.clauses", f"must contain exactly {sorted(required_names)}")

        physical = [claim for claim in used_claims if claim.get("modality") != "static_map"]
        evaluated_step = receipt.get("evaluated_step")
        evidence_age = max((evaluated_step - claim["observed_step"] for claim in physical), default=None) if _is_int(evaluated_step) else None
        max_skew = max((claim["temporal_skew"] for claim in physical), default=0)
        expected_clause_values = {
            "prediction_set": (sorted(contract["required_prediction_set"]), prediction, sorted(prediction) == sorted(contract["required_prediction_set"])),
            "evidence_age": (contract["max_evidence_age"], evidence_age, evidence_age is not None and evidence_age <= contract["max_evidence_age"]),
            "distinct_measurement_roots": (contract["min_distinct_measurement_roots"], len(root_ids), len(root_ids) >= contract["min_distinct_measurement_roots"]),
            "modality_skew": (contract["max_modality_skew"], max_skew, max_skew <= contract["max_modality_skew"]),
            "unresolved_conflicts": (contract["max_unresolved_conflicts"], receipt.get("unresolved_conflicts"), _is_int(receipt.get("unresolved_conflicts")) and receipt["unresolved_conflicts"] <= contract["max_unresolved_conflicts"]),
            "calibration_applicable": (contract["require_calibration_applicable"], receipt.get("calibration_applicable"), not contract["require_calibration_applicable"] or receipt.get("calibration_applicable") is True),
            "scope_match": (True, bool(physical), bool(physical)),
        }
        for name, (required, actual, passed) in expected_clause_values.items():
            clause = clause_map.get(name)
            if clause is None:
                continue
            if clause.get("required") != required or clause.get("actual") != actual or clause.get("passed") is not passed:
                audit.error(f"{path}.clauses.{name}", f"expected required={required!r}, actual={actual!r}, passed={passed}")
        all_passed = len(clause_map) == len(required_names) and all(clause.get("passed") is True for clause in clause_map.values())
        if receipt.get("admitted") is not all_passed:
            audit.error(f"{path}.admitted", "must equal the conjunction of all ActionContract clauses")
        expected_decision = "admitted" if all_passed else "denied"
        if receipt.get("decision") != expected_decision:
            audit.error(f"{path}.decision", f"must be {expected_decision}")
        if not _is_int(evaluated_step) or not _is_int(receipt.get("valid_until_step")):
            audit.error(path, "evaluated_step and valid_until_step must be integers")
        elif all_passed and receipt["valid_until_step"] < evaluated_step:
            audit.error(f"{path}.valid_until_step", "admitted receipt cannot already be stale")
        elif not all_passed and receipt["valid_until_step"] != evaluated_step:
            audit.error(f"{path}.valid_until_step", "denied receipt must expire at evaluated_step")

        gaps = receipt.get("belief_gaps")
        if not isinstance(gaps, list):
            audit.error(f"{path}.belief_gaps", "must be an array")
        else:
            for gap_index, gap in enumerate(gaps):
                if not isinstance(gap, dict):
                    audit.error(f"{path}.belief_gaps[{gap_index}]", "must be an object")
                    continue
                references = gap.get("claim_ids")
                if references is not None:
                    if not isinstance(references, list) or any(item not in claims for item in references):
                        audit.error(f"{path}.belief_gaps[{gap_index}].claim_ids", "contains an unknown Claim")
    return receipts


def _validate_invalidation_receipts(
    audit: Audit,
    values: Any,
    gate_receipts: Mapping[str, dict[str, Any]],
    claims: Mapping[str, dict[str, Any]],
    ablation: str,
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        audit.error("$.plan_invalidation_receipts", "must be an array")
        return []
    result: list[dict[str, Any]] = []
    for index, receipt in enumerate(values):
        path = f"$.plan_invalidation_receipts[{index}]"
        if ablation == "no-plan-invalidation" and isinstance(receipt, dict) and receipt.get("reasons") == ["ablation_disabled"]:
            if set(receipt) != {"invalidated", "reasons", "previous_receipt_sha256"} or receipt.get("invalidated") is not False:
                audit.error(path, "invalid no-plan-invalidation ablation marker")
            if receipt.get("previous_receipt_sha256") not in gate_receipts:
                audit.error(f"{path}.previous_receipt_sha256", "does not reference a GateReceipt")
            result.append(receipt)
            continue
        expected_fields = {
            "schema_version", "receipt_id", "previous_receipt_sha256", "current_step",
            "invalidated", "reasons", "triggering_claim_ids", "receipt_sha256",
        }
        if not audit.exact_fields(receipt, expected_fields, path):
            continue
        _walk_forbidden(audit, receipt, path)
        if receipt.get("schema_version") != INVALIDATION_SCHEMA:
            audit.error(f"{path}.schema_version", f"must be {INVALIDATION_SCHEMA}")
        if not _is_sha256(receipt.get("receipt_sha256")) or receipt_sha256(receipt) != receipt.get("receipt_sha256"):
            audit.error(f"{path}.receipt_sha256", "does not match canonical invalidation receipt hash")
        previous_hash = receipt.get("previous_receipt_sha256")
        previous = gate_receipts.get(previous_hash)
        if previous is None:
            audit.error(f"{path}.previous_receipt_sha256", "does not reference a GateReceipt in this episode")
        trigger_ids = receipt.get("triggering_claim_ids")
        if not isinstance(trigger_ids, list) or len(trigger_ids) != len(set(trigger_ids)) or any(item not in claims for item in trigger_ids):
            audit.error(f"{path}.triggering_claim_ids", "must uniquely reference submitted Claims")
        reasons = receipt.get("reasons")
        if not isinstance(reasons, list) or len(reasons) != len(set(reasons)):
            audit.error(f"{path}.reasons", "must be a unique array")
            reasons = []
        if receipt.get("invalidated") is True and not set(reasons) & {"expired", "new_contradicting_claim"}:
            audit.error(f"{path}.invalidated", "true invalidation requires expiry or a new contradicting Claim")
        if previous is not None and "expired" in reasons:
            if not _is_int(receipt.get("current_step")) or receipt["current_step"] <= previous["valid_until_step"]:
                audit.error(f"{path}.reasons", "expired reason is inconsistent with previous receipt validity")
        result.append(receipt)
    return result


def _validate_motion(audit: Audit, segments: Any) -> list[dict[str, Any]]:
    if not isinstance(segments, list):
        audit.error("$.motion_segments", "must be an array")
        return []
    required = {
        "reached", "target_xy", "final_pose", "path_length", "collision_count",
        "elapsed_steps", "reason", "trajectory", "controls", "label",
        "start_step", "end_step",
    }
    last_start = -1
    for index, segment in enumerate(segments):
        path = f"$.motion_segments[{index}]"
        if not audit.exact_fields(segment, required, path):
            continue
        start, end, elapsed = segment.get("start_step"), segment.get("end_step"), segment.get("elapsed_steps")
        if not all(_is_int(value) and value >= 0 for value in (start, end, elapsed)):
            audit.error(path, "motion steps must be non-negative integers")
        elif end != start + elapsed:
            audit.error(f"{path}.end_step", "must equal start_step + elapsed_steps")
        if _is_int(start) and start < last_start:
            audit.error(f"{path}.start_step", "motion segments must be chronological")
        if _is_int(start):
            last_start = start
        if not _is_number(segment.get("path_length")) or segment["path_length"] < 0:
            audit.error(f"{path}.path_length", "must be a non-negative finite number")
        if not _is_int(segment.get("collision_count")) or segment["collision_count"] < 0:
            audit.error(f"{path}.collision_count", "must be a non-negative contact count")
        if not isinstance(segment.get("target_xy"), list) or len(segment["target_xy"]) != 2 or not all(_is_number(value) for value in segment["target_xy"]):
            audit.error(f"{path}.target_xy", "must contain two finite coordinates")
        pose = segment.get("final_pose")
        if not isinstance(pose, dict) or set(pose) != {"x", "y", "yaw"} or not all(_is_number(value) for value in getattr(pose, "values", lambda: [])()):
            audit.error(f"{path}.final_pose", "must contain finite x/y/yaw")
        for series_name, fields in (
            ("trajectory", {"step", "x", "y", "yaw", "global_step"}),
            ("controls", {"step", "linear_velocity", "angular_velocity", "left_wheel_velocity", "right_wheel_velocity", "global_step"}),
        ):
            series = segment.get(series_name)
            if not isinstance(series, list) or not series:
                audit.error(f"{path}.{series_name}", "must be a non-empty array")
                continue
            previous_step = -1
            for point_index, point in enumerate(series):
                point_path = f"{path}.{series_name}[{point_index}]"
                if not isinstance(point, dict) or set(point) != fields:
                    audit.error(point_path, f"must contain exactly {sorted(fields)}")
                    continue
                step, global_step = point.get("step"), point.get("global_step")
                if not _is_int(step) or step < previous_step or not _is_int(global_step) or (_is_int(start) and global_step != start + step):
                    audit.error(point_path, "step/global_step must be monotonic and globally aligned")
                else:
                    previous_step = step
                for key, value in point.items():
                    if key not in {"step", "global_step"} and not _is_number(value):
                        audit.error(f"{point_path}.{key}", "must be finite")
    return segments


def _validate_online_and_outcome(
    audit: Audit,
    document: Mapping[str, Any],
    profile: str | None,
    receipts: Mapping[str, dict[str, Any]],
    invalidations: Sequence[dict[str, Any]],
    segments: Sequence[dict[str, Any]],
) -> None:
    for key in ("repair_decisions",):
        _walk_forbidden(audit, document.get(key), f"$.{key}")
    policy_decisions = document.get("policy_decisions")
    if not isinstance(policy_decisions, list):
        audit.error("$.policy_decisions", "must be an array")
    else:
        for index, decision in enumerate(policy_decisions):
            if not isinstance(decision, dict):
                audit.error(f"$.policy_decisions[{index}]", "must be an object")
                continue
            diagnostics = decision.get("diagnostics", {})
            if isinstance(diagnostics, dict) and diagnostics.get("oracle_inputs_used") not in (None, False):
                audit.error(f"$.policy_decisions[{index}].diagnostics.oracle_inputs_used", "must be false")

    outcome, metrics, configuration = document.get("outcome"), document.get("metrics"), document.get("configuration")
    if not isinstance(outcome, dict) or not isinstance(metrics, dict) or not isinstance(configuration, dict):
        return
    crossing_segments = [segment for segment in segments if segment.get("label") == "cross_region"]
    decision = outcome.get("decision", {})
    resolved = decision.get("resolved_value") if isinstance(decision, dict) else None
    safe_fallback = outcome.get("safe_fallback") is True
    if safe_fallback:
        if resolved != "unresolved" or decision.get("action") != "safe_fallback" or set(decision.get("prediction_set", [])) != {"clear", "blocked"}:
            audit.error("$.outcome.safe_fallback", "must remain unresolved with {clear,blocked}; it cannot impersonate blocked")
        if crossing_segments:
            audit.error("$.motion_segments", "safe_fallback must never enter the risk crossing")
    if resolved == "unresolved" and crossing_segments:
        audit.error("$.motion_segments", "unresolved evidence must never enter the risk crossing")
    if profile == "ood-severity" and crossing_segments:
        audit.error("$.motion_segments", "OOD calibration scope must fail closed before risk crossing")
    if resolved == "blocked" and decision.get("action") == "safe_fallback":
        if safe_fallback:
            audit.error("$.outcome", "qualified blocked detour cannot be labelled unresolved safe_fallback")
        qualified = any(
            receipt.get("admitted") is True
            and receipt.get("action") == "take_detour"
            and receipt.get("prediction_set") == ["blocked"]
            for receipt in receipts.values()
        )
        if str(configuration.get("policy", "")).startswith("purify") and not qualified:
            audit.error("$.outcome.decision", "blocked detour lacks an admitted take_detour GateReceipt")

    invalidation_events = [item for item in invalidations if item.get("invalidated") is True]
    if str(configuration.get("policy", "")).startswith("purify"):
        for segment in crossing_segments:
            start = segment.get("start_step")
            candidates = [
                receipt
                for receipt in receipts.values()
                if receipt.get("action") == "cross_region"
                and receipt.get("admitted") is True
                and receipt.get("prediction_set") == ["clear"]
                and receipt.get("calibration_applicable") is True
                and receipt.get("unresolved_conflicts") == 0
                and _is_int(start)
                and receipt.get("evaluated_step") <= start <= receipt.get("valid_until_step")
                and not any(
                    event.get("previous_receipt_sha256") == receipt.get("receipt_sha256")
                    and _is_int(event.get("current_step"))
                    and event["current_step"] <= start
                    for event in invalidation_events
                )
            ]
            if not candidates:
                audit.error("$.motion_segments", f"risk crossing at step {start} has no fresh, unrevoked singleton-clear GateReceipt")

    if metrics.get("observation_count") != len(document.get("evidence", [])):
        audit.error("$.metrics.observation_count", "must equal evidence capture count")
    path_length = sum(float(segment.get("path_length", 0)) for segment in segments if _is_number(segment.get("path_length")))
    if not _is_number(metrics.get("path_length")) or not math.isclose(float(metrics["path_length"]), path_length, rel_tol=1e-9, abs_tol=1e-9):
        audit.error("$.metrics.path_length", "must equal the sum of motion segment lengths")
    collisions = sum(int(segment.get("collision_count", 0)) for segment in segments if _is_int(segment.get("collision_count")))
    if metrics.get("collision_count") != collisions:
        audit.error("$.metrics.collision_count", "must equal summed motion contact counts")
    max_end = max((segment.get("end_step", 0) for segment in segments if _is_int(segment.get("end_step"))), default=0)
    if not _is_int(metrics.get("simulation_steps")) or metrics["simulation_steps"] < max_end:
        audit.error("$.metrics.simulation_steps", "must cover every motion segment")
    route = outcome.get("route")
    if not isinstance(route, list) or any(segment.get("label") not in route for segment in segments):
        audit.error("$.outcome.route", "must contain every recorded motion label")


def validate_episode(document: Any, source: str = "<memory>") -> list[str]:
    audit = Audit(source)
    if not audit.exact_fields(document, TOP_LEVEL_FIELDS, "$"):
        return audit.errors
    if document.get("schema_version") != EPISODE_SCHEMA:
        audit.error("$.schema_version", f"must be {EPISODE_SCHEMA}")
    commit = document.get("git_commit")
    if not isinstance(commit, str) or len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        audit.error("$.git_commit", "must be the full lowercase 40-hex Git commit")

    configuration = document.get("configuration")
    required_config = {
        "policy", "device", "max_observations", "max_replans", "ttl_steps",
        "evidence_dir", "ablation", "alpha", "calibration_artifact_id",
        "runtime", "motion_backend", "calibration_path", "smoke_calibration",
        "video_output",
    }
    if isinstance(configuration, dict):
        missing = required_config - set(configuration)
        if missing:
            audit.error("$.configuration", f"missing fields {sorted(missing)}")
        for key in ("max_observations", "max_replans", "ttl_steps"):
            if not _is_int(configuration.get(key)) or configuration[key] < (0 if key == "max_replans" else 1):
                audit.error(f"$.configuration.{key}", "invalid episode limit")
    else:
        audit.error("$.configuration", "must be an object")
        configuration = {}

    scenario = document.get("scenario")
    profile: str | None = None
    if not isinstance(scenario, dict) or set(scenario) != {"public_context", "oracle_context"}:
        audit.error("$.scenario", "must contain exactly public_context and evaluator-only oracle_context")
    else:
        public, oracle_context = scenario.get("public_context"), scenario.get("oracle_context")
        _walk_forbidden(audit, public, "$.scenario.public_context")
        if not isinstance(oracle_context, dict):
            audit.error("$.scenario.oracle_context", "must be an object")
        else:
            profile = oracle_context.get("profile")
            if profile not in PROFILES:
                audit.error("$.scenario.oracle_context.profile", f"must be one of {sorted(PROFILES)}")
            if not _is_int(oracle_context.get("seed")) or oracle_context["seed"] < 0:
                audit.error("$.scenario.oracle_context.seed", "must be a non-negative integer")
            if isinstance(public, dict) and public.get("paired_world_id") != oracle_context.get("paired_world_id"):
                audit.error("$.scenario", "public and oracle contexts must share paired_world_id")

    oracle = document.get("oracle")
    if not isinstance(oracle, dict) or set(oracle) != {"scenario", "observations"}:
        audit.error("$.oracle", "must be the separate evaluator-only {scenario,observations} object")
    elif isinstance(scenario, dict) and oracle.get("scenario") != scenario.get("oracle_context"):
        audit.error("$.oracle.scenario", "must exactly mirror scenario.oracle_context")

    environment = document.get("environment")
    environment_required = {"runtime", "physics_backend", "gpu", "rocm", "formal_result_eligible"}
    if not isinstance(environment, dict) or not environment_required <= set(environment):
        audit.error("$.environment", f"must contain {sorted(environment_required)}")
    elif type(environment.get("formal_result_eligible")) is not bool:
        audit.error("$.environment.formal_result_eligible", "must be boolean")
    elif environment["formal_result_eligible"] and (not environment.get("gpu") or not environment.get("rocm") or environment.get("runtime") != "genesis-amd"):
        audit.error("$.environment", "formal result requires Genesis AMD, a GPU name, and ROCm version")

    contracts = _validate_contracts(audit, document.get("action_contracts"))
    _validate_calibration(audit, document.get("calibration_artifact"), "$.calibration_artifact")
    _validate_calibration(audit, document.get("gate_calibration_artifact"), "$.gate_calibration_artifact")
    calibration = document.get("calibration_artifact", {})
    gate_calibration = document.get("gate_calibration_artifact", {})
    if configuration.get("calibration_artifact_id") != calibration.get("artifact_id"):
        audit.error("$.configuration.calibration_artifact_id", "must reference calibration_artifact")
    if configuration.get("alpha") != calibration.get("alpha"):
        audit.error("$.configuration.alpha", "must match calibration_artifact.alpha")
    if configuration.get("ablation") != "no-conformal-calibration" and gate_calibration != calibration:
        audit.error("$.gate_calibration_artifact", "must equal calibration_artifact outside the declared conformal ablation")

    claims, _ = _validate_claims(audit, document.get("claims"), "$.claims")
    gate_claims, _ = _validate_claims(audit, document.get("gate_submitted_claims"), "$.gate_submitted_claims")
    ablation = str(configuration.get("ablation", "none"))
    if not str(configuration.get("policy", "")).startswith("purify") and gate_claims:
        audit.error("$.gate_submitted_claims", "non-Purify baseline must not submit Claims to the Go gate")
    if ablation != "no-lineage-collapse" and gate_claims != claims and str(configuration.get("policy", "")).startswith("purify"):
        audit.error("$.gate_submitted_claims", "must exactly match episode Claims outside the lineage ablation")
    if ablation == "no-lineage-collapse":
        for claim in gate_claims.values():
            if claim.get("modality") == "static_map":
                continue
            capture = str(claim.get("capture_root_id", ""))
            original_id = capture.removeprefix("lineage-ablation:")
            expected_artifact = canonical_sha256({"ablation": "no-lineage-collapse", "claim_id": original_id})
            if not capture.startswith("lineage-ablation:") or original_id not in claims or not str(claim.get("model_id", "")).endswith("+no-lineage") or claim.get("artifact_sha256") != expected_artifact:
                audit.error("$.gate_submitted_claims", f"Claim {claim.get('claim_id')} is not an auditable lineage-ablation transform")

    evidence = document.get("evidence")
    if not isinstance(evidence, list):
        audit.error("$.evidence", "must be an array")
    else:
        for index, capture in enumerate(evidence):
            path = f"$.evidence[{index}]"
            if not isinstance(capture, dict):
                audit.error(path, "must be an object")
                continue
            _walk_forbidden(audit, capture, path)
            embedded = capture.get("claims")
            if not isinstance(embedded, list):
                audit.error(f"{path}.claims", "must be an array")
                continue
            for item in embedded:
                claim_id = item.get("claim_id") if isinstance(item, dict) else None
                if claim_id not in claims or claims[claim_id] != item:
                    audit.error(f"{path}.claims", f"embedded Claim {claim_id} does not exactly match top-level Claims")
                elif item.get("capture_root_id") != capture.get("capture_root_id"):
                    audit.error(f"{path}.capture_root_id", "does not match embedded Claim root")

    receipts = _validate_gate_receipts(
        audit, document.get("gate_receipts"), gate_claims, contracts,
        gate_calibration if isinstance(gate_calibration, dict) else {}, profile,
    )
    invalidations = _validate_invalidation_receipts(
        audit, document.get("plan_invalidation_receipts"), receipts, gate_claims, ablation,
    )
    segments = _validate_motion(audit, document.get("motion_segments"))
    _validate_online_and_outcome(audit, document, profile, receipts, invalidations, segments)
    return audit.errors


def discover_json_files(paths: Iterable[Path]) -> list[Path]:
    result: set[Path] = set()
    for path in paths:
        if path.is_dir():
            result.update(item for item in path.rglob("*.json") if item.is_file())
        elif path.is_file():
            result.add(path)
        else:
            raise FileNotFoundError(path)
    return sorted(result)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="episode JSON file or directory")
    parser.add_argument("--quiet", action="store_true", help="print errors only")
    args = parser.parse_args(argv)
    try:
        files = discover_json_files(args.paths)
    except FileNotFoundError as exc:
        print(f"ERROR: path does not exist: {exc}", file=sys.stderr)
        return 2
    if not files:
        print("ERROR: no JSON files found", file=sys.stderr)
        return 2
    failed = 0
    for path in files:
        try:
            document = load_json_strict(path)
            errors = validate_episode(document, str(path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors = [f"{path}:$: cannot read strict JSON: {exc}"]
        if errors:
            failed += 1
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
        elif not args.quiet:
            print(f"OK {path}")
    if not args.quiet:
        print(f"validated={len(files)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
