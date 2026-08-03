#!/usr/bin/env python3
"""Run the preregistered, additive V8 frozen full-pipeline challenge once.

This is an evidence collector, not a tuning or promotion script.  Its design is
intentionally closed in code: thirty same-generator, non-locked worlds
(``102500..102529``), one active and one passive episode per world, no retries,
no replacement seeds, and no early stopping.  Every episode is a fresh
``src/look_twice_v7.py`` subprocess using live Genesis RGB-D on AMD ROCm, the
kinematic motion backend, the exact frozen V8 spatial checkpoint and conformal
artifacts, the real Purify Go gate, and the repair-required contract.

The output directory is creation-only.  An existing path is rejected even when
empty, so this runner cannot resume, overwrite, or silently resample a partial
collection.  Adverse outcomes and command failures are retained and the fixed
schedule continues.  ``--dry-run`` validates the immutable design without
opening an output directory, loading a model, or touching ROCm.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import signal
import stat
import statistics
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


SEED_START = 102500
SEED_END = 102529
SEEDS = tuple(range(SEED_START, SEED_END + 1))
PROFILE = "independent-noise"
ACTIVE_POLICY = "purify-active-vision"
PASSIVE_POLICY = "purify-passive"
POLICIES = (ACTIVE_POLICY, PASSIVE_POLICY)
EPISODE_COUNT = len(SEEDS) * len(POLICIES)

EXPECTED_CHECKPOINT_SHA256 = (
    "7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783"
)
EXPECTED_VISION_ARTIFACT_FILE_SHA256 = (
    "8ccce120c2321582d4c9ad6ead90bcd55c562f9808db105f79ae7a76b46aa213"
)
EXPECTED_VISION_ARTIFACT_IDENTITY_SHA256 = (
    "ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f"
)
EXPECTED_GO_ARTIFACT_FILE_SHA256 = (
    "128d2c1a7c814b2f82f1bb660289026ae27f876434ae0c2add4a223242f59eac"
)
EXPECTED_GO_ARTIFACT_IDENTITY_SHA256 = (
    "d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97"
)
EXPECTED_PURIFY_BINARY_SHA256 = (
    "31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00"
)
EXPECTED_IDENTITY_MANIFEST_FILE_SHA256 = (
    "a7ecc586043f26f06daec73464b11146a6bba2832aa67c53c50ce67d2d315c7d"
)
EXPECTED_SOURCE_TREE_FINGERPRINT_SHA256 = (
    "983d7d373a3eedc6f6204e91d2d63b95a7e563506add24d37ee5a30c95aa71a9"
)
RUNTIME_SOURCE_MANIFEST_RELATIVE_PATH = (
    "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
)
EXPECTED_RUNTIME_SOURCE_MANIFEST_FILE_SHA256 = (
    "018f064f0361e59371e6694d7909da8639960f41f2ef158687c8e65e24d45c2f"
)
EXPECTED_RUNTIME_SOURCE_TREE_FINGERPRINT_SHA256 = (
    "abc1b6810aed6dc19a127069b9b5d5f044def24f35c9a13602f7f5096742b1be"
)
EXPECTED_RUNTIME_SOURCE_FILE_COUNT = 30
EXPECTED_RUNTIME_SOURCE_PYTHON_FILE_COUNT = 29
EXPECTED_RUNTIME_STATIC_ASSET_FILE_COUNT = 1
RUNTIME_SOURCE_MANIFEST_SCHEMA = (
    "look-twice.v8-challenge-runtime-dependency-manifest/v1"
)
RUNTIME_SOURCE_ROOT_ENTRYPOINT = "src/look_twice_v7.py"
RUNTIME_REQUIRED_STATIC_ASSET = "assets/robots/look_twice_skid_steer.urdf"
EXPECTED_RUNTIME_SOURCE_ORIGIN_GIT_COMMIT = (
    "aadd429d2da9de690a361218c40c9dfb22b04eb2"
)
RUNTIME_SOURCE_TREE_FINGERPRINT_ALGORITHM = (
    "sha256 of lexicographically path-sorted lines formatted as "
    "'<file_sha256>  <relative_path>\\n'"
)
EXPECTED_CRITICAL_SOURCE_SHA256: dict[str, str] = {
    "src/v6_episode.py": "3259bff66582cb34d98a70307b79084f0af89b48a64320fdd0bad71d16c2120f",
    "src/v7_episode.py": "9a83b0b15e1625159189b82f48f38b0f087957c2bc9f4f70a9376f2ef6b0ae3e",
    "src/v7_vision_claims.py": "929034e3dabdb820523a0719729dc77e85ec89934c68712f574232385c23cfe8",
    "src/v8_go_fusion_claims.py": "ffecd808b2b1feec30f94d5d9085c0b9dc173d535d0efa724ea1b5bc23bfd18e",
    "src/v8_runtime_calibration.py": "300286d56c24f7377a87add86a6ecdd64c3f02025f80acbb2ff819bc46648d14",
    "src/v8_seg_v3_model.py": "30892e644dcdffafc3bd0e928653b74d29a7724d0844ce0284b1448b9cbda649",
    "src/v8_spatial_runtime.py": "095956aa68ccbf8d2c62c47c216be113c89366dfdd86099031a506b66b0d71b2",
    "src/look_twice_v7.py": "09013bcea0c200c87c6bf8c40d1d78a300cafbbdc26807ba8fb9137c6ebb8754",
    "src/purify_bridge.py": "2224f75ed49346741ddbebcac64187a7dd72710e9b73468de78938bce3752700",
    "scripts/v8_go_fusion_v2_pipeline.py": "4e25d7aa7e6e8d96b341308f414129aa90b12283319977e7cd5dbd18b1f896b6",
    "scripts/v8_go_fusion_v3_pipeline.py": "d360a3f29393350607e616ebc73077ecdc38872aedaf2ba3a92c54f4cb1f4524",
    "scripts/v8_go_fusion_v3_rerun_smokes.py": "076b59941ffb028a4bed303a1b090a4a1f5ad744848f99e0e6b9d5dba17f0a3a",
    "scripts/v8_go_fusion_v3_preflight.py": "b5562cd24f9f41688eb71f3ac8aedf3b7644971bebde4d7952cfbfcf3e82a55d",
}

TELEMETRY_SCOPE = "entire_challenge_subprocess_wall"
TELEMETRY_INTERVAL_SECONDS = 2.0
TELEMETRY_MAX_GAP_MULTIPLIER = 2.5
TELEMETRY_MAX_GAP_SLACK_SECONDS = 0.5
TELEMETRY_MAX_GAP_SECONDS = (
    TELEMETRY_INTERVAL_SECONDS * TELEMETRY_MAX_GAP_MULTIPLIER
    + TELEMETRY_MAX_GAP_SLACK_SECONDS
)
EPISODE_TIMEOUT_SECONDS = 300.0
EPISODE_TERMINATION_GRACE_SECONDS = 10.0
ROCM_SMI_METRICS_COMMAND = (
    "--showuse",
    "--showmemuse",
    "--showpower",
    "--showtemp",
    "--json",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# Reuse the already-tested privacy-safe ROCm parser and summarizer when the
# companion benchmark is available.  The fallbacks make this file portable
# when it alone is copied into a frozen remote ``scripts/`` directory.
try:  # normal direct execution: scripts/ is sys.path[0]
    from benchmark_v8_frozen_telemetry import (  # type: ignore
        confirms_no_kfd_processes,
        parse_rocm_smi_json,
        summarize_samples,
    )
except ModuleNotFoundError:  # imported as scripts.run_v8_frozen_challenge
    try:
        from scripts.benchmark_v8_frozen_telemetry import (
            confirms_no_kfd_processes,
            parse_rocm_smi_json,
            summarize_samples,
        )
    except ModuleNotFoundError:
        _FALLBACK_TELEMETRY_FIELDS = {
            "GPU use (%)": "gpu_use_percent",
            "GPU Memory Allocated (VRAM%)": "vram_allocated_percent",
            "GPU Memory Read/Write Activity (%)": "memory_activity_percent",
            "Average Graphics Package Power (W)": "graphics_package_power_w",
            "Temperature (Sensor edge) (C)": "temperature_edge_c",
            "Temperature (Sensor junction) (C)": "temperature_junction_c",
            "Temperature (Sensor memory) (C)": "temperature_memory_c",
        }

        def _numeric(value: Any) -> float | None:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            if not isinstance(value, str) or value.strip().upper() in {
                "N/A",
                "NA",
                "",
            }:
                return None
            try:
                return float(value.strip())
            except ValueError:
                return None

        def parse_rocm_smi_json(text: str) -> dict[str, float | str | None]:
            payload = json.loads(text)
            if not isinstance(payload, dict) or not payload:
                raise ValueError("rocm-smi JSON contains no devices")
            card_name = sorted(payload)[0]
            raw = payload[card_name]
            if not isinstance(raw, dict):
                raise ValueError("rocm-smi device payload is not an object")
            row: dict[str, float | str | None] = {"device": card_name}
            for source_name, public_name in _FALLBACK_TELEMETRY_FIELDS.items():
                row[public_name] = _numeric(raw.get(source_name))
            return row

        def confirms_no_kfd_processes(text: str) -> bool:
            return "No KFD PIDs currently running" in text

        def _percentile(values: list[float], probability: float) -> float:
            ordered = sorted(values)
            index = max(
                0,
                min(
                    len(ordered) - 1,
                    math.ceil(probability * len(ordered)) - 1,
                ),
            )
            return ordered[index]

        def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
            summary: dict[str, Any] = {"sample_count": len(samples)}
            for public_name in _FALLBACK_TELEMETRY_FIELDS.values():
                values = [
                    float(sample[public_name])
                    for sample in samples
                    if sample.get(public_name) is not None
                ]
                summary[public_name] = (
                    {
                        "mean": statistics.fmean(values),
                        "minimum": min(values),
                        "maximum": max(values),
                        "p50": statistics.median(values),
                        "p95": _percentile(values, 0.95),
                        "samples": len(values),
                    }
                    if values
                    else None
                )
            return summary


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def exclusive_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def exclusive_write_json(path: Path, payload: Any) -> None:
    exclusive_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
    )


def append_json_line(handle: Any, payload: Any) -> None:
    handle.write(
        json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    handle.flush()
    os.fsync(handle.fileno())


def episode_label(policy: str) -> str:
    if policy == ACTIVE_POLICY:
        return "active"
    if policy == PASSIVE_POLICY:
        return "passive"
    raise ValueError(f"unexpected policy: {policy}")


def build_schedule() -> list[dict[str, Any]]:
    """Return the immutable parity-balanced, seed-ascending schedule.

    This exactly matches the public preregistration: even seeds run passive
    then active; odd seeds run active then passive.
    """

    rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        within_seed = (
            (PASSIVE_POLICY, ACTIVE_POLICY)
            if seed % 2 == 0
            else (ACTIVE_POLICY, PASSIVE_POLICY)
        )
        for policy in within_seed:
            label = episode_label(policy)
            rows.append(
                {
                    "schedule_index": len(rows),
                    "seed": seed,
                    "policy": policy,
                    "profile": PROFILE,
                    "episode_path": (
                        f"episodes/{label}__{PROFILE}__{seed}.json"
                    ),
                    "stdout_path": f"logs/{label}__{PROFILE}__{seed}.stdout.txt",
                    "stderr_path": f"logs/{label}__{PROFILE}__{seed}.stderr.txt",
                    "error_path": f"errors/{label}__{PROFILE}__{seed}.json",
                }
            )
    if len(rows) != EPISODE_COUNT:
        raise AssertionError("internal schedule size mismatch")
    return rows


def verify_file_identity(
    path: Path, expected_sha256: str, *, executable: bool = False
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required frozen file not found: {path}")
    observed = file_sha256(path)
    if observed != expected_sha256:
        raise ValueError(
            f"identity mismatch for {path}: expected {expected_sha256}, got {observed}"
        )
    if executable and not os.access(path, os.X_OK):
        raise ValueError(f"required binary is not executable: {path}")
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "file_sha256": observed,
        "file_sha256_verified": True,
        "executable": bool(os.access(path, os.X_OK)) if executable else None,
    }


def verify_json_artifact(
    path: Path,
    *,
    expected_file_sha256: str,
    expected_artifact_sha256: str,
    expected_checkpoint_sha256: str,
) -> dict[str, Any]:
    result = verify_file_identity(path, expected_file_sha256)
    payload = read_json_object(path)
    observed_artifact = str(payload.get("artifact_sha256") or "")
    observed_checkpoint = str(payload.get("checkpoint_sha256") or "")
    if observed_artifact != expected_artifact_sha256:
        raise ValueError(
            f"artifact identity mismatch for {path}: expected "
            f"{expected_artifact_sha256}, got {observed_artifact}"
        )
    if observed_checkpoint != expected_checkpoint_sha256:
        raise ValueError(
            f"artifact checkpoint binding mismatch for {path}: expected "
            f"{expected_checkpoint_sha256}, got {observed_checkpoint}"
        )
    result.update(
        {
            "artifact_sha256": observed_artifact,
            "artifact_sha256_verified": True,
            "checkpoint_sha256": observed_checkpoint,
            "checkpoint_binding_verified": True,
            "schema_version": payload.get("schema_version"),
        }
    )
    return result


def verify_frozen_assets(paths: Mapping[str, Path]) -> dict[str, Any]:
    checkpoint = verify_file_identity(
        paths["checkpoint"], EXPECTED_CHECKPOINT_SHA256
    )
    vision = verify_json_artifact(
        paths["vision_artifact"],
        expected_file_sha256=EXPECTED_VISION_ARTIFACT_FILE_SHA256,
        expected_artifact_sha256=EXPECTED_VISION_ARTIFACT_IDENTITY_SHA256,
        expected_checkpoint_sha256=EXPECTED_CHECKPOINT_SHA256,
    )
    go = verify_json_artifact(
        paths["go_artifact"],
        expected_file_sha256=EXPECTED_GO_ARTIFACT_FILE_SHA256,
        expected_artifact_sha256=EXPECTED_GO_ARTIFACT_IDENTITY_SHA256,
        expected_checkpoint_sha256=EXPECTED_CHECKPOINT_SHA256,
    )
    purify = verify_file_identity(
        paths["purify_binary"], EXPECTED_PURIFY_BINARY_SHA256, executable=True
    )
    return {
        "all_verified": True,
        "checkpoint": checkpoint,
        "vision_conformal_artifact": vision,
        "go_conformal_artifact": go,
        "purify_binary": purify,
    }


def verify_identity_manifest(
    path: Path,
    repo_root: Path,
    *,
    expected_manifest_file_sha256: str = EXPECTED_IDENTITY_MANIFEST_FILE_SHA256,
    expected_fingerprint: str = EXPECTED_SOURCE_TREE_FINGERPRINT_SHA256,
    expected_files: Mapping[str, str] = EXPECTED_CRITICAL_SOURCE_SHA256,
) -> dict[str, Any]:
    manifest_identity = verify_file_identity(path, expected_manifest_file_sha256)
    payload = read_json_object(path)
    fingerprint = str(payload.get("source_tree_fingerprint_sha256") or "")
    if fingerprint != expected_fingerprint:
        raise ValueError(
            "identity manifest source-tree fingerprint mismatch: "
            f"expected {expected_fingerprint}, got {fingerprint}"
        )
    declared_rows = payload.get("critical_source_files")
    if not isinstance(declared_rows, list):
        raise ValueError("identity manifest critical_source_files is not a list")
    declared = {
        str(row.get("path")): str(row.get("sha256"))
        for row in declared_rows
        if isinstance(row, dict)
    }
    if declared != dict(expected_files):
        missing = sorted(set(expected_files) - set(declared))
        extra = sorted(set(declared) - set(expected_files))
        mismatched = sorted(
            key
            for key in set(expected_files) & set(declared)
            if expected_files[key] != declared[key]
        )
        raise ValueError(
            "identity manifest critical-source declaration mismatch: "
            f"missing={missing} extra={extra} mismatched={mismatched}"
        )

    observations: list[dict[str, Any]] = []
    for relative_path, expected_sha in expected_files.items():
        source_path = repo_root / relative_path
        if not source_path.is_file():
            raise ValueError(f"critical frozen source file missing: {source_path}")
        observed_sha = file_sha256(source_path)
        row = {
            "path": relative_path,
            "size_bytes": source_path.stat().st_size,
            "expected_sha256": expected_sha,
            "observed_sha256": observed_sha,
            "matched": observed_sha == expected_sha,
        }
        observations.append(row)
        if not row["matched"]:
            raise ValueError(
                f"critical frozen source mismatch: {relative_path}: "
                f"expected {expected_sha}, got {observed_sha}"
            )

    return {
        "all_verified": True,
        "identity_manifest": manifest_identity,
        "source_tree_fingerprint_sha256": fingerprint,
        "source_tree_fingerprint_verified": True,
        "critical_source_file_count": len(observations),
        "critical_source_files": observations,
    }


def runtime_source_tree_fingerprint(files: Mapping[str, str]) -> str:
    material = "".join(
        f"{files[path]}  {path}\n" for path in sorted(files)
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _validated_runtime_source_relative_path(raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("runtime source manifest path must be a non-empty string")
    pure = PurePosixPath(raw_path)
    if (
        pure.is_absolute()
        or raw_path != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or not pure.parts
        or not (
            (pure.parts[0] == "src" and pure.suffix == ".py")
            or pure.as_posix() == RUNTIME_REQUIRED_STATIC_ASSET
        )
    ):
        raise ValueError(f"unsafe runtime source manifest path: {raw_path!r}")
    return pure.as_posix()


def verify_runtime_source_manifest(
    path: Path,
    repo_root: Path,
    *,
    expected_manifest_file_sha256: str = EXPECTED_RUNTIME_SOURCE_MANIFEST_FILE_SHA256,
    expected_tree_fingerprint: str = EXPECTED_RUNTIME_SOURCE_TREE_FINGERPRINT_SHA256,
    expected_file_count: int = EXPECTED_RUNTIME_SOURCE_FILE_COUNT,
    expected_python_file_count: int = EXPECTED_RUNTIME_SOURCE_PYTHON_FILE_COUNT,
    expected_static_asset_file_count: int = EXPECTED_RUNTIME_STATIC_ASSET_FILE_COUNT,
    expected_schema: str = RUNTIME_SOURCE_MANIFEST_SCHEMA,
    expected_root_entrypoint: str = RUNTIME_SOURCE_ROOT_ENTRYPOINT,
) -> dict[str, Any]:
    """Verify the exact executable Python closure, including its closed file set."""

    manifest_identity = verify_file_identity(path, expected_manifest_file_sha256)
    payload = read_json_object(path)
    if payload.get("schema_version") != expected_schema:
        raise ValueError(
            "runtime source manifest schema mismatch: "
            f"expected {expected_schema!r}, got {payload.get('schema_version')!r}"
        )
    if payload.get("root_entrypoint") != expected_root_entrypoint:
        raise ValueError(
            "runtime source root entrypoint mismatch: "
            f"expected {expected_root_entrypoint!r}, "
            f"got {payload.get('root_entrypoint')!r}"
        )
    if payload.get("file_count") != expected_file_count:
        raise ValueError(
            "runtime source manifest file_count mismatch: "
            f"expected {expected_file_count}, got {payload.get('file_count')!r}"
        )
    if payload.get("python_file_count") != expected_python_file_count:
        raise ValueError(
            "runtime dependency manifest python_file_count mismatch: "
            f"expected {expected_python_file_count}, "
            f"got {payload.get('python_file_count')!r}"
        )
    if (
        payload.get("static_asset_file_count")
        != expected_static_asset_file_count
    ):
        raise ValueError(
            "runtime dependency manifest static_asset_file_count mismatch: "
            f"expected {expected_static_asset_file_count}, "
            f"got {payload.get('static_asset_file_count')!r}"
        )
    if (
        payload.get("tree_fingerprint_algorithm")
        != RUNTIME_SOURCE_TREE_FINGERPRINT_ALGORITHM
    ):
        raise ValueError("runtime source tree fingerprint algorithm mismatch")
    declared_tree = payload.get("tree_fingerprint_sha256")
    if declared_tree != expected_tree_fingerprint:
        raise ValueError(
            "runtime source tree fingerprint declaration mismatch: "
            f"expected {expected_tree_fingerprint}, got {declared_tree!r}"
        )

    declared_rows = payload.get("files")
    if not isinstance(declared_rows, list) or len(declared_rows) != expected_file_count:
        raise ValueError(
            "runtime source manifest files must contain exactly "
            f"{expected_file_count} rows"
        )
    declared: dict[str, str] = {}
    for index, row in enumerate(declared_rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"runtime source manifest files[{index}] is not an object")
        relative = _validated_runtime_source_relative_path(row.get("path"))
        digest = row.get("sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError(
                f"runtime source manifest files[{index}].sha256 is invalid"
            )
        if relative in declared:
            raise ValueError(f"duplicate runtime source manifest path: {relative}")
        declared[relative] = digest

    repo_root = repo_root.resolve()
    source_root = repo_root / "src"
    if not source_root.is_dir() or source_root.is_symlink():
        raise ValueError(f"runtime source root is not an ordinary directory: {source_root}")
    actual: set[str] = set()
    for candidate in source_root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(f"runtime source tree contains a symlink: {candidate}")
        if candidate.suffix == ".py":
            try:
                mode = candidate.lstat().st_mode
            except FileNotFoundError as exc:
                raise ValueError(
                    f"runtime source file disappeared during preflight: {candidate}"
                ) from exc
            if not stat.S_ISREG(mode):
                raise ValueError(
                    f"runtime source .py path is not a regular file: {candidate}"
                )
            actual.add(candidate.relative_to(repo_root).as_posix())
    declared_python = {
        relative for relative in declared if relative.startswith("src/")
    }
    if actual != declared_python:
        raise ValueError(
            "runtime source Python file set mismatch: "
            f"missing={sorted(declared_python - actual)} "
            f"extra={sorted(actual - declared_python)}"
        )

    observations: list[dict[str, Any]] = []
    observed_files: dict[str, str] = {}
    for relative in sorted(declared):
        relative_parts = PurePosixPath(relative).parts
        candidate = repo_root.joinpath(*relative_parts)
        current = repo_root
        for part in relative_parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"runtime dependency path traverses a symlink: {current}"
                )
        if not candidate.exists():
            raise ValueError(f"runtime dependency file is missing: {candidate}")
        if not stat.S_ISREG(candidate.lstat().st_mode):
            raise ValueError(
                f"runtime dependency is not a regular file: {candidate}"
            )
        observed_sha = file_sha256(candidate)
        expected_sha = declared[relative]
        matched = observed_sha == expected_sha
        observations.append(
            {
                "path": relative,
                "size_bytes": candidate.stat().st_size,
                "expected_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "matched": matched,
            }
        )
        if not matched:
            raise ValueError(
                f"runtime source mismatch: {relative}: "
                f"expected {expected_sha}, got {observed_sha}"
            )
        observed_files[relative] = observed_sha
    observed_tree = runtime_source_tree_fingerprint(observed_files)
    if observed_tree != expected_tree_fingerprint:
        raise ValueError(
            "runtime source tree fingerprint mismatch: "
            f"expected {expected_tree_fingerprint}, got {observed_tree}"
        )

    return {
        "manifest_path": RUNTIME_SOURCE_MANIFEST_RELATIVE_PATH,
        "manifest_resolved_path": str(path.resolve()),
        "manifest_sha256_declared": expected_manifest_file_sha256,
        "manifest_sha256_observed": manifest_identity["file_sha256"],
        "manifest_sha256_verified": True,
        "tree_fingerprint_sha256_declared": expected_tree_fingerprint,
        "tree_fingerprint_sha256_observed": observed_tree,
        "tree_fingerprint_verified": True,
        "file_count_declared": expected_file_count,
        "file_count_observed": len(observations),
        "python_file_count_declared": expected_python_file_count,
        "python_file_count_observed": len(declared_python),
        "static_asset_file_count_declared": expected_static_asset_file_count,
        "static_asset_file_count_observed": len(observations)
        - len(declared_python),
        "root_entrypoint": payload["root_entrypoint"],
        "exact_python_file_set_required": True,
        "exact_set_verified": True,
        "source_origin_git_commit": payload.get("source_origin_git_commit"),
        "schema_version": payload["schema_version"],
        "files": observations,
    }


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def validate_preregistration(
    path: Path,
    runner_path: Path,
    *,
    require_runner_binding: bool,
    validator_path: Path | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required public preregistration not found: {path}")
    payload = read_json_object(path)
    runner_sha = file_sha256(runner_path)
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, got {actual!r}")

    require(
        "schema_version",
        payload.get("schema_version"),
        "look-twice.v8-frozen-challenge-preregistration/v1",
    )
    require(
        "status",
        payload.get("status"),
        "PREREGISTERED_BEFORE_ANY_CHALLENGE_EPISODE",
    )
    require("design.seed_start", _nested(payload, "design", "seed_start"), SEED_START)
    require("design.seed_end", _nested(payload, "design", "seed_end"), SEED_END)
    require("design.n_worlds", _nested(payload, "design", "n_worlds"), len(SEEDS))
    require("design.n_episodes", _nested(payload, "design", "n_episodes"), EPISODE_COUNT)
    require("design.profile", _nested(payload, "design", "profile"), PROFILE)
    require(
        "design.seed_order",
        _nested(payload, "design", "seed_order"),
        "strictly_ascending",
    )
    require("design.paired_by_seed", _nested(payload, "design", "paired_by_seed"), True)
    require(
        "design.policies",
        _nested(payload, "design", "policies"),
        [ACTIVE_POLICY, PASSIVE_POLICY],
    )
    require(
        "design.even order",
        _nested(payload, "design", "within_seed_order_rule", "even_seed"),
        [PASSIVE_POLICY, ACTIVE_POLICY],
    )
    require(
        "design.odd order",
        _nested(payload, "design", "within_seed_order_rule", "odd_seed"),
        [ACTIVE_POLICY, PASSIVE_POLICY],
    )
    for key, expected in (
        ("attempts_per_seed_policy", 1),
        ("retry_count_allowed", 0),
        ("early_stopping_allowed", False),
        ("continue_after_bad_outcome", True),
        ("publish_every_attempt", True),
        ("retuning_allowed", False),
        ("threshold_changes_allowed", False),
        ("checkpoint_changes_allowed", False),
        ("seed_substitution_allowed", False),
    ):
        require(f"design.{key}", _nested(payload, "design", key), expected)

    require(
        "population.generator_family",
        _nested(payload, "population_boundary", "generator_family"),
        "same_generator_as_v8_spatial_dataset_v1",
    )
    require(
        "population.challenge_subset",
        _nested(payload, "population_boundary", "challenge_subset"),
        [SEED_START, SEED_END],
    )
    require(
        "identities.checkpoint",
        _nested(payload, "identities", "checkpoint_sha256"),
        EXPECTED_CHECKPOINT_SHA256,
    )
    require(
        "identities.vision",
        _nested(payload, "identities", "vision_conformal_artifact_sha256"),
        EXPECTED_VISION_ARTIFACT_IDENTITY_SHA256,
    )
    require(
        "identities.go",
        _nested(payload, "identities", "go_conformal_artifact_sha256"),
        EXPECTED_GO_ARTIFACT_IDENTITY_SHA256,
    )
    require(
        "identities.purify",
        _nested(payload, "identities", "purify_binary_sha256"),
        EXPECTED_PURIFY_BINARY_SHA256,
    )
    require(
        "identities.source_tree_fingerprint",
        _nested(payload, "identities", "source_tree_fingerprint_sha256"),
        EXPECTED_SOURCE_TREE_FINGERPRINT_SHA256,
    )
    declared_critical = _nested(payload, "identities", "critical_source_files")
    if not isinstance(declared_critical, list):
        errors.append("identities.critical_source_files: expected list")
    else:
        declared_map = {
            str(row.get("path")): str(row.get("sha256"))
            for row in declared_critical
            if isinstance(row, dict)
        }
        require(
            "identities.critical_source_files",
            declared_map,
            EXPECTED_CRITICAL_SOURCE_SHA256,
        )

    runtime_source_closure_payload = _nested(
        payload, "identities", "runtime_source_closure"
    )
    if not isinstance(runtime_source_closure_payload, Mapping):
        errors.append("identities.runtime_source_closure: expected object")
        runtime_source_closure_payload = {}
    for key, expected in (
        ("manifest_path", RUNTIME_SOURCE_MANIFEST_RELATIVE_PATH),
        ("manifest_sha256", EXPECTED_RUNTIME_SOURCE_MANIFEST_FILE_SHA256),
        (
            "tree_fingerprint_sha256",
            EXPECTED_RUNTIME_SOURCE_TREE_FINGERPRINT_SHA256,
        ),
        ("file_count", EXPECTED_RUNTIME_SOURCE_FILE_COUNT),
        ("python_file_count", EXPECTED_RUNTIME_SOURCE_PYTHON_FILE_COUNT),
        ("static_asset_file_count", EXPECTED_RUNTIME_STATIC_ASSET_FILE_COUNT),
        ("root_entrypoint", RUNTIME_SOURCE_ROOT_ENTRYPOINT),
        ("exact_python_file_set_required", True),
        ("source_origin_git_commit", EXPECTED_RUNTIME_SOURCE_ORIGIN_GIT_COMMIT),
    ):
        require(
            f"identities.runtime_source_closure.{key}",
            runtime_source_closure_payload.get(key),
            expected,
        )

    require(
        "episode active filename",
        _nested(
            payload,
            "episode_contract",
            "filename_templates",
            ACTIVE_POLICY,
        ),
        "episodes/active__independent-noise__{seed}.json",
    )
    require(
        "episode passive filename",
        _nested(
            payload,
            "episode_contract",
            "filename_templates",
            PASSIVE_POLICY,
        ),
        "episodes/passive__independent-noise__{seed}.json",
    )
    require(
        "telemetry.scope",
        _nested(payload, "telemetry_contract", "scope"),
        TELEMETRY_SCOPE,
    )
    max_interval = _nested(
        payload, "telemetry_contract", "sample_interval_seconds_max"
    )
    if not isinstance(max_interval, (int, float)) or max_interval < TELEMETRY_INTERVAL_SECONDS:
        errors.append(
            "telemetry.sample_interval_seconds_max does not permit the fixed 2 s interval"
        )
    require(
        "telemetry.sampler_errors_allowed",
        _nested(payload, "telemetry_contract", "sampler_errors_allowed"),
        0,
    )
    require(
        "reporting.raw_episode_files",
        _nested(payload, "reporting_contract", "raw_episode_files"),
        EPISODE_COUNT,
    )
    require(
        "reporting.no rerun",
        _nested(
            payload,
            "reporting_contract",
            "no_result_may_be_deleted_replaced_or_rerun",
        ),
        True,
    )

    declared_runner_sha = str(_nested(payload, "identities", "runner_sha256") or "")
    placeholder = declared_runner_sha == "TO_BE_BOUND_AFTER_RUNNER_FINALIZATION"
    runner_binding_verified = declared_runner_sha == runner_sha
    if require_runner_binding and not runner_binding_verified:
        errors.append(
            "identities.runner_sha256 is not bound to this runner: "
            f"declared={declared_runner_sha!r} observed={runner_sha}"
        )
    elif not require_runner_binding and not (runner_binding_verified or placeholder):
        errors.append(
            "identities.runner_sha256 is neither the dry-run placeholder nor this runner"
        )

    declared_validator_sha = str(
        _nested(payload, "identities", "validator_sha256") or ""
    )
    validator_placeholder = (
        declared_validator_sha == "TO_BE_BOUND_AFTER_VALIDATOR_FINALIZATION"
    )
    observed_validator_sha = (
        file_sha256(validator_path)
        if validator_path is not None and validator_path.is_file()
        else None
    )
    validator_binding_verified = bool(
        observed_validator_sha is not None
        and declared_validator_sha == observed_validator_sha
    )
    if require_runner_binding and not validator_binding_verified:
        errors.append(
            "identities.validator_sha256 is not bound to the exact validator: "
            f"declared={declared_validator_sha!r} observed={observed_validator_sha!r}"
        )
    elif not require_runner_binding and not (
        validator_binding_verified or validator_placeholder
    ):
        errors.append(
            "identities.validator_sha256 is neither the dry-run placeholder nor the exact validator"
        )

    public_commit = str(
        _nested(payload, "public_binding", "runner_protocol_commit") or ""
    )
    public_placeholder = public_commit == "TO_BE_BOUND_BEFORE_RUN"
    public_binding_verified = bool(re.fullmatch(r"[0-9a-f]{40}", public_commit))
    if require_runner_binding and not public_binding_verified:
        errors.append(
            "public_binding.runner_protocol_commit must be a lowercase 40-hex public commit before execution"
        )
    elif not require_runner_binding and not (
        public_binding_verified or public_placeholder
    ):
        errors.append(
            "public_binding.runner_protocol_commit is neither the dry-run placeholder nor a 40-hex commit"
        )

    if errors:
        raise ValueError("invalid preregistration:\n- " + "\n- ".join(errors))
    return {
        "path": str(path.resolve()),
        "file_sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "created_utc": payload.get("created_utc"),
        "tag": payload.get("tag"),
        "runner_sha256_declared": declared_runner_sha,
        "runner_sha256_observed": runner_sha,
        "runner_binding_verified": runner_binding_verified,
        "dry_run_placeholder_accepted": bool(placeholder and not require_runner_binding),
        "public_binding_commit": public_commit,
        "runner_protocol_commit": public_commit,
        "public_binding_verified": public_binding_verified,
        "public_binding_placeholder_accepted": bool(
            public_placeholder and not require_runner_binding
        ),
        "validator_sha256_declared": declared_validator_sha,
        "validator_sha256_observed": observed_validator_sha,
        "validator_binding_verified": validator_binding_verified,
        "validator_dry_run_placeholder_accepted": bool(
            validator_placeholder and not require_runner_binding
        ),
        "runtime_source_closure": dict(runtime_source_closure_payload),
        "contract_verified": True,
    }


def _first_existing(repo_root: Path, candidates: Sequence[str]) -> Path:
    for candidate in candidates:
        path = repo_root / candidate
        if path.exists():
            return path
    return repo_root / candidates[0]


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    repo_root = args.repo_root.resolve()
    return {
        "repo_root": repo_root,
        "entrypoint": repo_root / "src" / "look_twice_v7.py",
        "checkpoint": (
            args.checkpoint.resolve()
            if args.checkpoint
            else _first_existing(
                repo_root,
                (
                    "results/v8-seg-v3-full-paired-v2-fast-promote/frozen_checkpoint/"
                    "v8_seg_v3_selected_ep22_7b158726f9c0.pt",
                    "release/v8-frozen/results/frozen_checkpoint/"
                    "v8_seg_v3_selected_ep22_7b158726f9c0.pt",
                ),
            )
        ),
        "vision_artifact": (
            args.vision_conformal_artifact.resolve()
            if args.vision_conformal_artifact
            else _first_existing(
                repo_root,
                (
                    "results/v8-seg-v3-full-paired-v2-fast-promote/"
                    "calibration_vision/conformal_artifact.json",
                    "release/v8-frozen/results/calibration_vision/"
                    "conformal_artifact.json",
                ),
            )
        ),
        "go_artifact": (
            args.go_conformal_artifact.resolve()
            if args.go_conformal_artifact
            else _first_existing(
                repo_root,
                (
                    "results/v8-seg-v3-full-paired-v2-fast-promote/"
                    "calibration_go_fusion_v3/conformal_artifact.json",
                    "release/v8-frozen/results/calibration_go_fusion_v3/"
                    "conformal_artifact.json",
                ),
            )
        ),
        "purify_binary": (
            args.purify_binary.resolve()
            if args.purify_binary
            else _first_existing(
                repo_root,
                (
                    "purify_robotics/bin/purify-robotics-core-linux",
                    "release/v8-frozen/artifacts/purify-robotics-core-linux",
                ),
            )
        ),
        "identity_manifest": (
            args.identity_manifest.resolve()
            if args.identity_manifest
            else _first_existing(
                repo_root,
                (
                    "results/v8-seg-v3-full-paired-v2-fast-promote/"
                    "V8_IDENTITY_FREEZE_MANIFEST.json",
                    "release/v8-frozen/results/V8_IDENTITY_FREEZE_MANIFEST.json",
                ),
            )
        ),
        "runtime_source_manifest": (
            args.runtime_source_manifest.resolve()
            if args.runtime_source_manifest
            else repo_root / RUNTIME_SOURCE_MANIFEST_RELATIVE_PATH
        ),
        "preregistration": args.preregistration.resolve(),
        "validator": (
            args.validator.resolve()
            if args.validator
            else repo_root / "scripts" / "verify_v8_frozen_challenge.py"
        ),
        "output_dir": args.output_dir.resolve(),
    }


def build_episode_command(
    *,
    python: str,
    paths: Mapping[str, Path],
    spec: Mapping[str, Any],
) -> list[str]:
    return [
        python,
        str(paths["entrypoint"]),
        "--runtime",
        "genesis",
        "--motion-backend",
        "kinematic",
        "--policy",
        str(spec["policy"]),
        "--profile",
        PROFILE,
        "--seed",
        str(spec["seed"]),
        "--device",
        "cuda:0",
        "--vision-backend",
        "torch_spatial_rgbd",
        "--vision-checkpoint",
        str(paths["checkpoint"]),
        "--vision-conformal-artifact",
        str(paths["vision_artifact"]),
        "--go-conformal-artifact",
        str(paths["go_artifact"]),
        "--use-purify-go-gate",
        "--purify-binary",
        str(paths["purify_binary"]),
        "--repair-required",
        "--json-output",
        str(paths["output_dir"] / str(spec["episode_path"])),
    ]


def _capture_command(
    argv: Sequence[str],
    *,
    timeout: float = 10.0,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    started_utc = utc_now()
    started_ns = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
        )
        return {
            "argv": list(argv),
            "started_at_utc": started_utc,
            "ended_at_utc": utc_now(),
            "started_monotonic_ns": started_ns,
            "ended_monotonic_ns": time.perf_counter_ns(),
            "command_exit_code": completed.returncode,
            "raw_stdout": completed.stdout,
            "raw_stderr": completed.stderr,
            "exception": None,
        }
    except Exception as exc:
        return {
            "argv": list(argv),
            "started_at_utc": started_utc,
            "ended_at_utc": utc_now(),
            "started_monotonic_ns": started_ns,
            "ended_monotonic_ns": time.perf_counter_ns(),
            "command_exit_code": None,
            "raw_stdout": "",
            "raw_stderr": "",
            "exception": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        }


_IMPORT_CANARY_SCRIPT = r"""
import importlib
import json
import pathlib
import sys
import traceback

root = pathlib.Path(sys.argv[1]).resolve()
pairs = json.loads(sys.argv[2])
rows = []
for module_name, relative_path in pairs:
    expected = (root / relative_path).resolve()
    try:
        module = importlib.import_module(module_name)
        raw_file = getattr(module, "__file__", None)
        observed = pathlib.Path(raw_file).resolve() if raw_file else None
        rows.append({
            "module": module_name,
            "relative_path": relative_path,
            "expected_resolved_path": str(expected),
            "observed_resolved_path": str(observed) if observed else None,
            "exact_path_match": observed == expected,
            "error": None,
        })
    except BaseException as exc:
        rows.append({
            "module": module_name,
            "relative_path": relative_path,
            "expected_resolved_path": str(expected),
            "observed_resolved_path": None,
            "exact_path_match": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        })
passed = len(rows) == len(pairs) and all(row["exact_path_match"] for row in rows)
print("__LOOK_TWICE_IMPORT_CANARY_JSON__" + json.dumps({
    "passed": passed,
    "rows": rows,
}, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if passed else 3)
"""


def run_runtime_source_import_canary(
    *,
    python: str,
    repo_root: Path,
    runtime_source_closure: Mapping[str, Any],
) -> dict[str, Any]:
    python_rows = [
        row
        for row in runtime_source_closure.get("files", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("path"), str)
        and str(row["path"]).startswith("src/")
        and str(row["path"]).endswith(".py")
    ]
    module_pairs: list[list[str]] = []
    for row in python_rows:
        relative = str(row["path"])
        module_relative = PurePosixPath(relative).relative_to("src")
        if module_relative.name == "__init__.py":
            module_parts = module_relative.parts[:-1]
        else:
            module_parts = (*module_relative.parts[:-1], module_relative.stem)
        if not module_parts:
            raise ValueError(f"cannot derive import name for runtime source: {relative}")
        module_pairs.append([".".join(module_parts), relative])
    if len(module_pairs) != EXPECTED_RUNTIME_SOURCE_PYTHON_FILE_COUNT:
        raise ValueError(
            "runtime import canary module count mismatch: "
            f"expected {EXPECTED_RUNTIME_SOURCE_PYTHON_FILE_COUNT}, "
            f"got {len(module_pairs)}"
        )

    command = [
        python,
        "-c",
        _IMPORT_CANARY_SCRIPT,
        str(repo_root.resolve()),
        json.dumps(module_pairs, separators=(",", ":")),
    ]
    canary_env = os.environ.copy()
    canary_env["PYTHONPATH"] = str(repo_root.resolve() / "src")
    canary_env["PYOPENGL_PLATFORM"] = "egl"
    canary_env["MIOPEN_FIND_MODE"] = "FAST"
    canary_env["PYTHONNOUSERSITE"] = "1"
    captured = _capture_command(
        command,
        timeout=120.0,
        cwd=repo_root.resolve(),
        env=canary_env,
    )
    marker = "__LOOK_TWICE_IMPORT_CANARY_JSON__"
    payload: dict[str, Any] | None = None
    for line in str(captured.get("raw_stdout") or "").splitlines():
        if line.startswith(marker):
            try:
                candidate = json.loads(line[len(marker) :])
                if isinstance(candidate, dict):
                    payload = candidate
            except json.JSONDecodeError:
                payload = None
    resolved = payload.get("rows") if isinstance(payload, Mapping) else None
    resolved = resolved if isinstance(resolved, list) else []
    passed = bool(
        captured.get("command_exit_code") == 0
        and isinstance(payload, Mapping)
        and payload.get("passed") is True
        and len(resolved) == len(module_pairs)
        and all(
            isinstance(row, Mapping) and row.get("exact_path_match") is True
            for row in resolved
        )
    )
    return {
        "command": command,
        "command_exit_code": captured.get("command_exit_code"),
        "started_at_utc": captured.get("started_at_utc"),
        "ended_at_utc": captured.get("ended_at_utc"),
        "started_monotonic_ns": captured.get("started_monotonic_ns"),
        "ended_monotonic_ns": captured.get("ended_monotonic_ns"),
        "expected_module_count": len(module_pairs),
        "resolved_module_count": len(resolved),
        "resolved_modules": resolved,
        "all_within_runtime_source_root": bool(
            resolved
            and all(
                isinstance(row, Mapping) and row.get("exact_path_match") is True
                for row in resolved
            )
        ),
        "exact_paths_verified": passed,
        "passed": passed,
        "exception": captured.get("exception"),
        "raw_stdout": captured.get("raw_stdout"),
        "raw_stderr": captured.get("raw_stderr"),
    }


def bind_runtime_source_import_canary(
    runtime_source_closure: Mapping[str, Any],
    canary: Mapping[str, Any],
) -> dict[str, Any]:
    raw_stdout = str(canary.get("raw_stdout") or "")
    raw_stderr = str(canary.get("raw_stderr") or "")
    compact = {
        key: value
        for key, value in canary.items()
        if key not in {"raw_stdout", "raw_stderr"}
    }
    compact.update(
        {
            "raw_stdout_path": "raw/runtime_source_import_canary.stdout.txt",
            "raw_stdout_sha256": hashlib.sha256(
                raw_stdout.encode("utf-8")
            ).hexdigest(),
            "raw_stderr_path": "raw/runtime_source_import_canary.stderr.txt",
            "raw_stderr_sha256": hashlib.sha256(
                raw_stderr.encode("utf-8")
            ).hexdigest(),
            "command_metadata_path": "raw/runtime_source_import_canary.command.json",
        }
    )
    return {**dict(runtime_source_closure), "import_canary": compact}


def persist_runtime_source_import_canary_raw(
    output_dir: Path, canary: Mapping[str, Any]
) -> None:
    exclusive_write_text(
        output_dir / "raw/runtime_source_import_canary.stdout.txt",
        str(canary.get("raw_stdout") or ""),
    )
    exclusive_write_text(
        output_dir / "raw/runtime_source_import_canary.stderr.txt",
        str(canary.get("raw_stderr") or ""),
    )
    exclusive_write_json(
        output_dir / "raw/runtime_source_import_canary.command.json",
        {
            key: value
            for key, value in canary.items()
            if key not in {"raw_stdout", "raw_stderr", "resolved_modules"}
        },
    )


def run_clean_gpu_preflight(rocm_smi: str) -> dict[str, Any]:
    telemetry_raw = _capture_command(
        [rocm_smi, *ROCM_SMI_METRICS_COMMAND], timeout=10.0
    )
    processes_raw = _capture_command([rocm_smi, "--showpids"], timeout=10.0)
    errors: list[str] = []
    parsed: dict[str, Any] | None = None
    if telemetry_raw["command_exit_code"] != 0:
        errors.append("rocm-smi telemetry preflight command failed")
    else:
        try:
            parsed = parse_rocm_smi_json(telemetry_raw["raw_stdout"])
        except Exception as exc:
            errors.append(f"rocm-smi telemetry preflight parse failed: {exc}")
    if processes_raw["command_exit_code"] != 0:
        errors.append("rocm-smi process preflight command failed")
    no_kfd = bool(
        processes_raw["command_exit_code"] == 0
        and confirms_no_kfd_processes(processes_raw["raw_stdout"])
    )
    if not no_kfd:
        errors.append("GPU preflight did not confirm an empty KFD process list")
    if parsed is not None:
        for name in ("gpu_use_percent", "vram_allocated_percent"):
            value = parsed.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"GPU preflight metric is unavailable: {name}")
        if isinstance(parsed.get("gpu_use_percent"), (int, float)) and float(
            parsed["gpu_use_percent"]
        ) > 5.0:
            errors.append("GPU preflight utilization is above 5 percent")
        if isinstance(parsed.get("vram_allocated_percent"), (int, float)) and float(
            parsed["vram_allocated_percent"]
        ) > 1.0:
            errors.append("GPU preflight VRAM allocation is above 1 percent")
    return {
        "passed": not errors,
        "no_kfd_processes": no_kfd,
        "no_other_kfd_processes": no_kfd,
        "telemetry_before_first_episode": parsed,
        "thresholds": {
            "gpu_use_percent_max": 5.0,
            "vram_allocated_percent_max": 1.0,
            "requires_explicit_no_kfd_message": True,
        },
        "errors": errors,
        "raw": {"telemetry": telemetry_raw, "processes": processes_raw},
    }


class FullChainTelemetrySampler:
    """Continuously sample ROCm while every challenge subprocess runs."""

    def __init__(
        self,
        command: str,
        interval_seconds: float = TELEMETRY_INTERVAL_SECONDS,
    ) -> None:
        self.command = command
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.started_monotonic_ns: int | None = None
        self.ended_monotonic_ns: int | None = None
        self._stop = threading.Event()
        self._condition = threading.Condition()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("telemetry sampler can only be started once")
        self.started_monotonic_ns = time.perf_counter_ns()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(10.0, self.interval_seconds + 7.0))
            if self._thread.is_alive():
                self.errors.append(
                    {
                        "type": "SamplerThreadTimeout",
                        "message": "telemetry sampler thread did not stop in time",
                        "at_utc": utc_now(),
                    }
                )
        self.ended_monotonic_ns = time.perf_counter_ns()

    def wait_for_first_sample(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self.samples:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def wait_for_sample_at_or_after(
        self, monotonic_ns: int, timeout: float = 15.0
    ) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self.samples or int(self.samples[-1]["monotonic_ns"]) < monotonic_ns:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    def _run(self) -> None:
        argv = [self.command, *ROCM_SMI_METRICS_COMMAND]
        next_due_ns = time.perf_counter_ns()
        while not self._stop.is_set():
            started_ns = time.perf_counter_ns()
            sample: dict[str, Any] = {
                "sample_index": len(self.samples),
                "command_started_monotonic_ns": started_ns,
                "started_at_utc": utc_now(),
                "argv": list(argv),
            }
            try:
                completed = subprocess.run(
                    argv,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                completed_ns = time.perf_counter_ns()
                sample.update(
                    {
                        "monotonic_ns": completed_ns,
                        "ended_at_utc": utc_now(),
                        "command_exit_code": completed.returncode,
                        "raw_stdout": completed.stdout,
                        "raw_stderr": completed.stderr,
                    }
                )
                if completed.returncode == 0:
                    parsed = parse_rocm_smi_json(completed.stdout)
                    sample.update(parsed)
                    for required_metric in (
                        "gpu_use_percent",
                        "vram_allocated_percent",
                        "graphics_package_power_w",
                    ):
                        value = sample.get(required_metric)
                        if isinstance(value, bool) or not isinstance(
                            value, (int, float)
                        ):
                            raise ValueError(
                                f"required telemetry metric unavailable: {required_metric}"
                            )
                else:
                    raise RuntimeError(
                        f"rocm-smi telemetry exited {completed.returncode}"
                    )
            except Exception as exc:
                sample.setdefault("monotonic_ns", time.perf_counter_ns())
                sample.setdefault("ended_at_utc", utc_now())
                sample.setdefault("command_exit_code", None)
                sample.setdefault("raw_stdout", "")
                sample.setdefault("raw_stderr", "")
                error = {
                    "sample_index": sample["sample_index"],
                    "monotonic_ns": sample["monotonic_ns"],
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
                sample["sampler_error"] = error
                self.errors.append(error)
            with self._condition:
                self.samples.append(sample)
                self._condition.notify_all()

            next_due_ns += int(self.interval_seconds * 1_000_000_000)
            delay_seconds = max(
                0.0, (next_due_ns - time.perf_counter_ns()) / 1_000_000_000.0
            )
            self._stop.wait(delay_seconds)


def telemetry_coverage_checks(
    *,
    sampler_started_monotonic_ns: int | None,
    sampler_ended_monotonic_ns: int | None,
    challenge_started_monotonic_ns: int | None,
    challenge_ended_monotonic_ns: int | None,
    samples: Sequence[Mapping[str, Any]],
    sampler_errors: Sequence[Any],
    max_gap_seconds: float = TELEMETRY_MAX_GAP_SECONDS,
) -> dict[str, Any]:
    sample_times = [
        int(row["monotonic_ns"])
        for row in samples
        if isinstance(row.get("monotonic_ns"), int)
    ]
    gaps = [
        (later - earlier) / 1_000_000_000.0
        for earlier, later in zip(sample_times, sample_times[1:])
    ]
    max_observed_gap = max(gaps) if gaps else None
    ordering_valid = bool(
        sampler_started_monotonic_ns is not None
        and sampler_ended_monotonic_ns is not None
        and challenge_started_monotonic_ns is not None
        and challenge_ended_monotonic_ns is not None
        and sampler_started_monotonic_ns
        <= challenge_started_monotonic_ns
        < challenge_ended_monotonic_ns
        <= sampler_ended_monotonic_ns
    )
    starts_covered = bool(
        sample_times
        and challenge_started_monotonic_ns is not None
        and sample_times[0] <= challenge_started_monotonic_ns
    )
    ends_covered = bool(
        sample_times
        and challenge_ended_monotonic_ns is not None
        and sample_times[-1] >= challenge_ended_monotonic_ns
    )
    command_exit_codes_zero = bool(
        samples and all(row.get("command_exit_code") == 0 for row in samples)
    )
    gaps_valid = bool(
        len(sample_times) >= 2
        and max_observed_gap is not None
        and max_observed_gap <= max_gap_seconds
    )
    checks = {
        "ordering_valid": ordering_valid,
        "sample_before_or_at_challenge_start": starts_covered,
        "sample_after_or_at_challenge_end": ends_covered,
        "all_sample_command_exit_codes_zero": command_exit_codes_zero,
        "sampler_errors_empty": len(sampler_errors) == 0,
        "continuous_sampling_gap_valid": gaps_valid,
        "sample_count": len(samples),
        "max_observed_gap_seconds": max_observed_gap,
        "max_allowed_gap_seconds": max_gap_seconds,
    }
    checks["all_valid"] = all(
        bool(checks[name])
        for name in (
            "ordering_valid",
            "sample_before_or_at_challenge_start",
            "sample_after_or_at_challenge_end",
            "all_sample_command_exit_codes_zero",
            "sampler_errors_empty",
            "continuous_sampling_gap_valid",
        )
    )
    return checks


def build_telemetry_report(
    *,
    sampler: FullChainTelemetrySampler,
    challenge_started_monotonic_ns: int | None,
    challenge_ended_monotonic_ns: int | None,
    episode_records: Sequence[Mapping[str, Any]],
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = telemetry_coverage_checks(
        sampler_started_monotonic_ns=sampler.started_monotonic_ns,
        sampler_ended_monotonic_ns=sampler.ended_monotonic_ns,
        challenge_started_monotonic_ns=challenge_started_monotonic_ns,
        challenge_ended_monotonic_ns=challenge_ended_monotonic_ns,
        samples=sampler.samples,
        sampler_errors=sampler.errors,
    )
    exit_codes = [record.get("command_exit_code") for record in episode_records]
    all_episode_commands_zero = bool(
        len(exit_codes) == EPISODE_COUNT and all(code == 0 for code in exit_codes)
    )
    preflight_metrics = preflight.get("telemetry_before_first_episode")
    preflight_metrics = (
        preflight_metrics if isinstance(preflight_metrics, Mapping) else {}
    )
    return {
        "schema_version": "look-twice.v8-frozen-challenge-rocm-telemetry/v1",
        "generated_at_utc": utc_now(),
        "scope": TELEMETRY_SCOPE,
        "scope_includes": [
            "all sixty look_twice_v7 subprocess walls",
            "Genesis initialization, simulation, and live RGB-D rendering",
            "RGB-D preprocessing and exact frozen V8 model inference",
            "Python evidence processing and Purify Go gate invocations",
            "planning, kinematic robot motion, process startup, and episode JSON I/O",
            "the deterministic gaps between consecutive episode subprocesses",
        ],
        "scope_excludes": [
            "artifact hashing and source identity checks before collection",
            "the clean-GPU preflight commands",
            "post-collection report derivation",
        ],
        "sample_interval_seconds": TELEMETRY_INTERVAL_SECONDS,
        "telemetry_command": [sampler.command, *ROCM_SMI_METRICS_COMMAND],
        "fixed_subprocess_environment": {
            "PYOPENGL_PLATFORM": "egl",
            "MIOPEN_FIND_MODE": "FAST",
        },
        "sampler_started_monotonic_ns": sampler.started_monotonic_ns,
        "challenge_subprocess_started_monotonic_ns": challenge_started_monotonic_ns,
        "challenge_subprocess_ended_monotonic_ns": challenge_ended_monotonic_ns,
        "sampler_ended_monotonic_ns": sampler.ended_monotonic_ns,
        "command_exit_code": 0 if all_episode_commands_zero else 1,
        "challenge_subprocess_exit_code": 0 if all_episode_commands_zero else 1,
        "episode_subprocess_exit_codes": exit_codes,
        "clean_gpu_preflight": {
            key: value for key, value in preflight.items() if key != "raw"
        },
        "preflight": {
            "no_other_kfd_processes": bool(
                preflight.get("no_other_kfd_processes")
            ),
            "gpu_use_percent": preflight_metrics.get("gpu_use_percent"),
            "vram_allocated_percent": preflight_metrics.get(
                "vram_allocated_percent"
            ),
        },
        "coverage_checks": coverage,
        "sampler_errors": list(sampler.errors),
        "telemetry_summary": summarize_samples(list(sampler.samples)),
        "samples": list(sampler.samples),
    }


def validate_episode_payload(
    payload: Mapping[str, Any], spec: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []

    def require(name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            errors.append(f"{name}: expected {expected!r}, got {actual!r}")

    require("schema_version", payload.get("schema_version"), "look-twice.episode/v7")
    require("scenario.seed", _nested(payload, "scenario", "seed"), spec["seed"])
    require("scenario.profile", _nested(payload, "scenario", "profile"), PROFILE)
    require(
        "configuration.policy",
        _nested(payload, "configuration", "policy"),
        spec["policy"],
    )
    for key, expected in (
        ("device", "cuda:0"),
        ("vision_backend", "torch_spatial_rgbd"),
        ("repair_required", True),
        ("use_purify_go_gate", True),
    ):
        require(
            f"configuration.{key}",
            _nested(payload, "configuration", key),
            expected,
        )
    required_environment = {
        "runtime": "genesis-amd",
        "formal_result_eligible": False,
        "physics_backend": "kinematic",
        "genesis": "1.1.2",
        "genesis_backend": "gs.amdgpu",
        "torch": "2.9.1+gitff65f5b",
        "rocm": "7.2.53211-e1a6bc5663",
        "gpu": "AMD Radeon Graphics",
        "v6": True,
        "v6_motion_backend": "kinematic",
        "device": "cuda:0",
        "claims_mode": "genesis_rgbd_multi_agent_v6",
        "dual_agent": True,
        "artifact_inputs_eligible": True,
        "genesis_live_rgbd": True,
    }
    for key, expected in required_environment.items():
        require(
            f"environment.{key}",
            _nested(payload, "environment", key),
            expected,
        )
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        errors.append("metrics: expected object")
        return errors
    for key, expected in (
        ("vision_backend", "torch_spatial_rgbd"),
        ("checkpoint_sha256", EXPECTED_CHECKPOINT_SHA256),
        (
            "conformal_artifact_sha256",
            EXPECTED_VISION_ARTIFACT_IDENTITY_SHA256,
        ),
        ("purify_binary_sha256", EXPECTED_PURIFY_BINARY_SHA256),
        ("repair_required", True),
        ("tensor_device", "cuda:0"),
    ):
        require(f"metrics.{key}", metrics.get(key), expected)
    receipts = payload.get("purify_go_receipts")
    if not isinstance(receipts, list) or not receipts:
        errors.append("purify_go_receipts: expected at least one raw Go receipt")
    else:
        go_id = f"v8-spatial-conformal:{EXPECTED_GO_ARTIFACT_IDENTITY_SHA256[:16]}"
        for index, receipt in enumerate(receipts):
            if not isinstance(receipt, Mapping):
                errors.append(f"purify_go_receipts[{index}]: expected object")
                continue
            require(
                f"purify_go_receipts[{index}]._go_calibration_artifact_id",
                receipt.get("_go_calibration_artifact_id"),
                go_id,
            )
            require(
                f"purify_go_receipts[{index}]._purify_binary_sha256",
                receipt.get("_purify_binary_sha256"),
                EXPECTED_PURIFY_BINARY_SHA256,
            )
    return errors


def python_go_agreement(payload: Mapping[str, Any]) -> dict[str, Any]:
    python_receipts = payload.get("gate_receipts")
    go_receipts = payload.get("purify_go_receipts")
    if not isinstance(python_receipts, list) or not isinstance(go_receipts, list):
        return {"pair_count": 0, "agree_count": 0, "all_agree": False}
    pairs = list(zip(python_receipts[: len(go_receipts)], go_receipts))
    agreement_rows = [
        bool(
            isinstance(py, Mapping)
            and isinstance(go, Mapping)
            and py.get("evaluated_step") == go.get("evaluated_step")
            and bool(py.get("admitted")) == bool(go.get("admitted"))
        )
        for py, go in pairs
    ]
    return {
        "pair_count": len(pairs),
        "agree_count": sum(agreement_rows),
        "all_agree": bool(
            len(go_receipts) > 0
            and len(pairs) == len(go_receipts)
            and all(agreement_rows)
        ),
    }


def motion_burden_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Sum raw motion-segment path lengths by agent, without energy claims."""

    by_agent = {"carrier": 0.0, "scout": 0.0}
    invalid_segments: list[int] = []
    segments = payload.get("motion_segments")
    if not isinstance(segments, list):
        return {
            "valid": False,
            "carrier_path_length": None,
            "scout_path_length": None,
            "total_team_path_length": None,
            "segment_count": 0,
            "invalid_segment_indices": [],
        }
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            invalid_segments.append(index)
            continue
        agent = str(segment.get("agent_id") or "")
        value = segment.get("path_length")
        if (
            agent not in by_agent
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            invalid_segments.append(index)
            continue
        by_agent[agent] += float(value)
    valid = bool(segments) and not invalid_segments
    return {
        "valid": valid,
        "carrier_path_length": by_agent["carrier"] if valid else None,
        "scout_path_length": by_agent["scout"] if valid else None,
        "total_team_path_length": sum(by_agent.values()) if valid else None,
        "segment_count": len(segments),
        "invalid_segment_indices": invalid_segments,
    }


def workload_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    environment = payload.get("environment")
    metrics = payload.get("metrics")
    environment = environment if isinstance(environment, Mapping) else {}
    metrics = metrics if isinstance(metrics, Mapping) else {}
    return {
        "rgbd_observation_count": environment.get("rgbd_observation_count"),
        "observation_count": metrics.get("observation_count"),
        "vision_proposal_count": metrics.get("vision_proposal_count"),
        "purify_invoked_count": metrics.get("purify_invoked_count"),
        "checkpoint_loaded": bool(metrics.get("checkpoint_loaded")),
        "fallback_used": bool(
            metrics.get("fallback_used") or metrics.get("vision_fallback_used")
        ),
        "genesis_live_rgbd": bool(
            environment.get("genesis_live_rgbd") or metrics.get("genesis_live_rgbd")
        ),
        "world_alignment_passed": bool(metrics.get("world_alignment_passed")),
        "purify_invoked": bool(metrics.get("purify_invoked")),
    }


def compact_episode_result(
    payload: Mapping[str, Any], spec: Mapping[str, Any]
) -> dict[str, Any]:
    metrics = payload.get("metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    agreement = python_go_agreement(payload)
    direct = bool(metrics.get("route_mode") == "direct" and not metrics.get("used_detour"))
    mission = all(
        metrics.get(key) is True
        for key in (
            "mission_success",
            "carrier_reached_goal",
            "payload_delivered",
            "within_deadline",
        )
    )
    gate_receipts = payload.get("gate_receipts")
    selected_corridor = metrics.get("selected_corridor")
    behavior_linked_full_admit_receipts = [
        receipt
        for receipt in gate_receipts
        if isinstance(receipt, Mapping)
        and isinstance(selected_corridor, str)
        and bool(selected_corridor)
        and receipt.get("action") == "cross_corridor"
        and receipt.get("corridor_id") == selected_corridor
        and receipt.get("python_admitted") is True
        and receipt.get("purify_go_admitted") is True
        and receipt.get("effective_admit") is True
    ] if isinstance(gate_receipts, list) else []
    effective_python_go_admit = bool(behavior_linked_full_admit_receipts)
    full_chain_direct = bool(direct and mission and effective_python_go_admit)
    return {
        "seed": spec["seed"],
        "policy": spec["policy"],
        "direct_route": direct,
        "full_chain_direct": full_chain_direct,
        "effective_python_go_admit_observed": effective_python_go_admit,
        "behavior_linked_full_admit_receipt_count": len(
            behavior_linked_full_admit_receipts
        ),
        "selected_corridor": selected_corridor,
        "mission_success": mission,
        "unsafe_episode": bool(metrics.get("unsafe_crossing")),
        "route_mode": metrics.get("route_mode"),
        "initial_gate_denied": bool(metrics.get("initial_gate_denied")),
        "repair_attempted": bool(metrics.get("repair_attempted")),
        "repair_success": bool(metrics.get("repair_success")),
        "repair_chain_complete": bool(metrics.get("repair_chain_complete")),
        "python_go_gate_agreement": agreement,
        "motion_burden": motion_burden_from_payload(payload),
        "full_pipeline_workload": workload_from_payload(payload),
    }


def _terminate_episode_process_group(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float | None = None,
) -> tuple[int | None, list[dict[str, Any]]]:
    if grace_seconds is None:
        grace_seconds = EPISODE_TERMINATION_GRACE_SECONDS
    actions: list[dict[str, Any]] = []
    try:
        os.killpg(process.pid, signal.SIGTERM)
        actions.append(
            {
                "signal": "SIGTERM",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": True,
            }
        )
    except ProcessLookupError:
        actions.append(
            {
                "signal": "SIGTERM",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": False,
                "reason": "process_group_already_absent",
            }
        )
    except Exception as exc:
        actions.append(
            {
                "signal": "SIGTERM",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
    try:
        return process.wait(timeout=grace_seconds), actions
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
        actions.append(
            {
                "signal": "SIGKILL",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": True,
            }
        )
    except ProcessLookupError:
        actions.append(
            {
                "signal": "SIGKILL",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": False,
                "reason": "process_group_already_absent",
            }
        )
    except Exception as exc:
        actions.append(
            {
                "signal": "SIGKILL",
                "sent_at_utc": utc_now(),
                "process_group_id": process.pid,
                "sent": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
    try:
        return process.wait(timeout=grace_seconds), actions
    except subprocess.TimeoutExpired:
        actions.append(
            {
                "signal": "SIGKILL",
                "sent": False,
                "reason": "process_group_did_not_exit_after_sigkill",
            }
        )
        return process.poll(), actions


def _run_one_episode(
    *,
    python: str,
    paths: Mapping[str, Path],
    spec: Mapping[str, Any],
    env: Mapping[str, str],
) -> dict[str, Any]:
    output_dir = paths["output_dir"]
    episode_path = output_dir / str(spec["episode_path"])
    stdout_path = output_dir / str(spec["stdout_path"])
    stderr_path = output_dir / str(spec["stderr_path"])
    error_path = output_dir / str(spec["error_path"])
    for path in (episode_path, stdout_path, stderr_path, error_path):
        if path.exists():
            raise RuntimeError(f"refusing to overwrite pre-existing attempt artifact: {path}")

    command = build_episode_command(python=python, paths=paths, spec=spec)
    started_utc = utc_now()
    started_ns = time.perf_counter_ns()
    return_code: int | None = None
    exception_payload: dict[str, Any] | None = None
    timed_out = False
    termination_actions: list[dict[str, Any]] = []
    process: subprocess.Popen[Any] | None = None
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=str(paths["repo_root"]),
                env=dict(env),
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
            try:
                return_code = process.wait(timeout=EPISODE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                exception_payload = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
                return_code, termination_actions = _terminate_episode_process_group(
                    process
                )
    except Exception as exc:  # preserve an OS launch failure as this one attempt
        exception_payload = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    except BaseException:
        if process is not None and process.poll() is None:
            _terminate_episode_process_group(process)
        raise
    ended_ns = time.perf_counter_ns()
    ended_utc = utc_now()

    parse_error: str | None = None
    validation_errors: list[str] = []
    compact: dict[str, Any] | None = None
    episode_sha: str | None = None
    episode_size: int | None = None
    if episode_path.is_file():
        episode_sha = file_sha256(episode_path)
        episode_size = episode_path.stat().st_size
        try:
            payload = read_json_object(episode_path)
            validation_errors = validate_episode_payload(payload, spec)
            compact = compact_episode_result(payload, spec)
        except Exception as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    else:
        parse_error = "episode JSON was not produced"

    attempt_valid = bool(
        return_code == 0
        and exception_payload is None
        and parse_error is None
        and not validation_errors
        and compact is not None
    )
    record: dict[str, Any] = {
        "schedule_index": spec["schedule_index"],
        "seed": spec["seed"],
        "policy": spec["policy"],
        "profile": PROFILE,
        "command": command,
        "subprocess_started_at_utc": started_utc,
        "subprocess_ended_at_utc": ended_utc,
        "subprocess_started_monotonic_ns": started_ns,
        "subprocess_ended_monotonic_ns": ended_ns,
        "wall_seconds": (ended_ns - started_ns) / 1_000_000_000.0,
        "command_exit_code": return_code,
        "timeout_seconds": EPISODE_TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "start_new_session": True,
        "termination_grace_seconds": EPISODE_TERMINATION_GRACE_SECONDS,
        "termination_actions": termination_actions,
        "episode_path": spec["episode_path"],
        "episode_size_bytes": episode_size,
        "episode_sha256": episode_sha,
        "stdout_path": spec["stdout_path"],
        "stdout_sha256": file_sha256(stdout_path) if stdout_path.is_file() else None,
        "stderr_path": spec["stderr_path"],
        "stderr_sha256": file_sha256(stderr_path) if stderr_path.is_file() else None,
        "exception": exception_payload,
        "parse_error": parse_error,
        "contract_validation_errors": validation_errors,
        "attempt_integrity_valid": attempt_valid,
        "result": compact,
    }
    if not attempt_valid:
        exclusive_write_json(
            error_path,
            {
                "schema_version": "look-twice.v8-frozen-challenge-episode-error/v1",
                "preserved_at_utc": utc_now(),
                "no_retry_permitted": True,
                **record,
            },
        )
        record["error_path"] = spec["error_path"]
    else:
        record["error_path"] = None
    return record


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def exact_mcnemar_two_sided(active_only: int, passive_only: int) -> float:
    discordant = active_only + passive_only
    if discordant == 0:
        return 1.0
    tail_to = min(active_only, passive_only)
    tail = sum(math.comb(discordant, k) for k in range(tail_to + 1)) / (2**discordant)
    return min(1.0, 2.0 * tail)


def numeric_summary(values: Iterable[float]) -> dict[str, Any]:
    numbers = [float(value) for value in values]
    if not numbers:
        return {"n": 0, "sum": None, "mean": None, "median": None, "minimum": None, "maximum": None}
    return {
        "n": len(numbers),
        "sum": sum(numbers),
        "mean": statistics.fmean(numbers),
        "median": statistics.median(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
    }


def _valid_result_rows(
    episode_records: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return [
        record
        for record in episode_records
        if record.get("attempt_integrity_valid")
        and isinstance(record.get("result"), Mapping)
    ]


def aggregate_primary_endpoint(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid = _valid_result_rows(episode_records)
    by_key = {
        (int(record["seed"]), str(record["policy"])): record["result"]
        for record in valid
    }
    by_policy: dict[str, Any] = {}
    for policy in POLICIES:
        values = [
            bool(result.get("full_chain_direct"))
            for (seed, observed_policy), result in by_key.items()
            if observed_policy == policy
        ]
        successes = sum(values)
        by_policy[policy] = {
            "n": len(values),
            "full_chain_direct_count": successes,
            "full_chain_direct_rate": successes / len(values) if values else None,
            "wilson_95_interval": wilson_interval(successes, len(values)),
        }
    paired_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        active = by_key.get((seed, ACTIVE_POLICY))
        passive = by_key.get((seed, PASSIVE_POLICY))
        if not isinstance(active, Mapping) or not isinstance(passive, Mapping):
            continue
        active_event = bool(active.get("full_chain_direct"))
        passive_event = bool(passive.get("full_chain_direct"))
        paired_rows.append(
            {
                "seed": seed,
                "active_full_chain_direct": active_event,
                "passive_full_chain_direct": passive_event,
                "paired_difference": int(active_event) - int(passive_event),
            }
        )
    active_only = sum(
        row["active_full_chain_direct"]
        and not row["passive_full_chain_direct"]
        for row in paired_rows
    )
    passive_only = sum(
        row["passive_full_chain_direct"]
        and not row["active_full_chain_direct"]
        for row in paired_rows
    )
    active_rate = by_policy[ACTIVE_POLICY]["full_chain_direct_rate"]
    passive_rate = by_policy[PASSIVE_POLICY]["full_chain_direct_rate"]
    return {
        "name": "full_chain_direct_rate_difference",
        "descriptive_only_until_collection_complete": len(paired_rows) != len(SEEDS),
        "by_policy": by_policy,
        "active_rate_minus_passive_rate": (
            active_rate - passive_rate
            if active_rate is not None and passive_rate is not None
            else None
        ),
        "paired_seed_count": len(paired_rows),
        "mcnemar_discordance": {
            "active_only": active_only,
            "passive_only": passive_only,
        },
        "exact_mcnemar_two_sided_p": exact_mcnemar_two_sided(
            active_only, passive_only
        ),
        "paired_rows": paired_rows,
        "success_threshold": None,
        "promotion_decision": None,
    }


def aggregate_motion_burden(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid = _valid_result_rows(episode_records)
    by_key: dict[tuple[int, str], Mapping[str, Any]] = {}
    for record in valid:
        result = record["result"]
        motion = result.get("motion_burden") if isinstance(result, Mapping) else None
        if isinstance(motion, Mapping) and motion.get("valid"):
            by_key[(int(record["seed"]), str(record["policy"]))] = motion

    by_policy: dict[str, Any] = {}
    for policy in POLICIES:
        rows = [
            motion
            for (seed, observed_policy), motion in by_key.items()
            if observed_policy == policy
        ]
        by_policy[policy] = {
            "episode_count": len(rows),
            "loaded_carrier_path_length": numeric_summary(
                float(row["carrier_path_length"]) for row in rows
            ),
            "scout_path_length": numeric_summary(
                float(row["scout_path_length"]) for row in rows
            ),
            "total_team_path_length": numeric_summary(
                float(row["total_team_path_length"]) for row in rows
            ),
        }
    pairs: list[dict[str, Any]] = []
    for seed in SEEDS:
        active = by_key.get((seed, ACTIVE_POLICY))
        passive = by_key.get((seed, PASSIVE_POLICY))
        if active is None or passive is None:
            continue
        carrier_delta = float(active["carrier_path_length"]) - float(
            passive["carrier_path_length"]
        )
        total_delta = float(active["total_team_path_length"]) - float(
            passive["total_team_path_length"]
        )
        pairs.append(
            {
                "seed": seed,
                "active_loaded_carrier_path_length": active["carrier_path_length"],
                "passive_loaded_carrier_path_length": passive["carrier_path_length"],
                "active_minus_passive_loaded_carrier_path_length": carrier_delta,
                "active_scout_path_length": active["scout_path_length"],
                "active_total_team_path_length": active["total_team_path_length"],
                "passive_total_team_path_length": passive["total_team_path_length"],
                "active_minus_passive_total_team_path_length": total_delta,
            }
        )
    return {
        "endpoint_type": "logical_role_kinematic_burden_from_raw_motion_segments",
        "unit": "declared Genesis scene path-length unit by logical role",
        "derivation": "sum motion_segments[].path_length grouped by agent_id per episode",
        "loaded_carrier_definition": "agent_id == 'carrier'; scenario payload_id == 'payload_loaded'",
        "agent_realization": (
            "single_shared_genesis_chassis_with_separate_logical_role_poses"
        ),
        "not_simultaneous_dual_body_dynamics": True,
        "claim_guardrail": (
            "Path length is logical-role simulated kinematic burden on a shared "
            "Genesis chassis only; it is not energy, throughput, latency, a "
            "physical-robot measurement, or simultaneous dual-body dynamics."
        ),
        "by_policy": by_policy,
        "paired_seed_count": len(pairs),
        "paired_active_minus_passive_loaded_carrier_path_length": numeric_summary(
            row["active_minus_passive_loaded_carrier_path_length"] for row in pairs
        ),
        "paired_active_minus_passive_total_team_path_length": numeric_summary(
            row["active_minus_passive_total_team_path_length"] for row in pairs
        ),
        "pairs": pairs,
    }


def _as_nonnegative_number(value: Any) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        return None
    return float(value)


def aggregate_workload(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid = _valid_result_rows(episode_records)
    by_policy: dict[str, Any] = {}
    for policy in POLICIES:
        workloads = [
            record["result"].get("full_pipeline_workload")
            for record in valid
            if record.get("policy") == policy
            and isinstance(record.get("result"), Mapping)
            and isinstance(record["result"].get("full_pipeline_workload"), Mapping)
        ]
        counts: dict[str, Any] = {}
        for key in (
            "rgbd_observation_count",
            "observation_count",
            "vision_proposal_count",
            "purify_invoked_count",
        ):
            values = [
                number
                for workload in workloads
                if (number := _as_nonnegative_number(workload.get(key))) is not None
            ]
            counts[key] = numeric_summary(values)
        flags = {
            key: sum(bool(workload.get(key)) for workload in workloads)
            for key in (
                "checkpoint_loaded",
                "fallback_used",
                "genesis_live_rgbd",
                "world_alignment_passed",
                "purify_invoked",
            )
        }
        by_policy[policy] = {
            "episode_count": len(workloads),
            "counts_per_episode": counts,
            "flag_true_episode_counts": flags,
        }

    all_workloads = [
        record["result"].get("full_pipeline_workload")
        for record in valid
        if isinstance(record.get("result"), Mapping)
        and isinstance(record["result"].get("full_pipeline_workload"), Mapping)
    ]
    overall_counts = {}
    for key in (
        "rgbd_observation_count",
        "observation_count",
        "vision_proposal_count",
        "purify_invoked_count",
    ):
        values = [
            number
            for workload in all_workloads
            if (number := _as_nonnegative_number(workload.get(key))) is not None
        ]
        overall_counts[key] = numeric_summary(values)
    return {
        "scope": "denominators for the full-chain Radeon telemetry window",
        "episode_denominator": len(all_workloads),
        "by_policy": by_policy,
        "overall_counts_per_episode": overall_counts,
        "guardrail": (
            "Counts describe captured RGB-D observations, model proposals, and Go "
            "gate calls; they are workload quantities, not throughput or latency."
        ),
    }


def aggregate_secondary_endpoints(
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    valid = _valid_result_rows(episode_records)
    by_policy: dict[str, Any] = {}
    for policy in POLICIES:
        rows = [
            record["result"]
            for record in valid
            if record.get("policy") == policy
        ]
        by_policy[policy] = {
            "n": len(rows),
            "mission_success": sum(bool(row.get("mission_success")) for row in rows),
            "unsafe_episode": sum(bool(row.get("unsafe_episode")) for row in rows),
            "initial_gate_denied": sum(
                bool(row.get("initial_gate_denied")) for row in rows
            ),
            "repair_attempted": sum(bool(row.get("repair_attempted")) for row in rows),
            "repair_success": sum(bool(row.get("repair_success")) for row in rows),
            "repair_chain_complete": sum(
                bool(row.get("repair_chain_complete")) for row in rows
            ),
            "python_go_gate_agreement": sum(
                bool(_nested(row, "python_go_gate_agreement", "all_agree"))
                for row in rows
            ),
        }
    return {
        "multiplicity": (
            "descriptive secondary endpoints; no multiplicity-adjusted confirmatory claim"
        ),
        "by_policy": by_policy,
        "motion_burden": aggregate_motion_burden(episode_records),
        "full_pipeline_workload": aggregate_workload(episode_records),
    }


def build_challenge_report(
    *,
    episode_records: Sequence[Mapping[str, Any]],
    telemetry: Mapping[str, Any],
    manifest_path: Path,
    telemetry_path: Path,
    preregistration: Mapping[str, Any],
    fatal_error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    valid_attempts = sum(
        bool(record.get("attempt_integrity_valid")) for record in episode_records
    )
    collection_complete = len(episode_records) == EPISODE_COUNT
    integrity_valid = bool(
        collection_complete
        and valid_attempts == EPISODE_COUNT
        and _nested(telemetry, "coverage_checks", "all_valid") is True
        and telemetry.get("challenge_subprocess_exit_code") == 0
        and fatal_error is None
    )
    return {
        "schema_version": "look-twice.v8-frozen-challenge-report/v1",
        "generated_at_utc": utc_now(),
        "collection_status": "complete" if collection_complete else "incomplete",
        "integrity_status": "valid" if integrity_valid else "invalid",
        "claim_scope": {
            "role": "additive same-generator non-locked supplement",
            "worlds": len(SEEDS),
            "seed_range": [SEED_START, SEED_END],
            "episodes": EPISODE_COUNT,
            "same_generator": True,
            "locked_test": False,
            "not_ood": True,
            "not_population_generalization": True,
            "no_retuning_or_threshold_change": True,
            "simulation": "Genesis 1.1.2 on AMD ROCm",
            "motion_backend": "kinematic",
            "agent_realization": (
                "single_shared_genesis_chassis_with_separate_logical_role_poses"
            ),
            "not_simultaneous_dual_body_dynamics": True,
            "not_physical_robot_test": True,
        },
        "preregistration": dict(preregistration),
        "evidence_files": {
            "run_manifest": {
                "path": "RUN_MANIFEST.json",
                "sha256": file_sha256(manifest_path),
            },
            "rocm_telemetry": {
                "path": "ROCM_TELEMETRY.json",
                "sha256": file_sha256(telemetry_path),
            },
        },
        "attempt_integrity": {
            "scheduled": EPISODE_COUNT,
            "attempted": len(episode_records),
            "valid": valid_attempts,
            "invalid": len(episode_records) - valid_attempts,
            "retry_count_allowed": 0,
            "retry_count_observed": 0,
            "every_attempt_preserved": True,
        },
        "primary_endpoint": aggregate_primary_endpoint(episode_records),
        "secondary_endpoints": aggregate_secondary_endpoints(episode_records),
        "telemetry": {
            "scope": telemetry.get("scope"),
            "coverage_checks": telemetry.get("coverage_checks"),
            "summary": telemetry.get("telemetry_summary"),
            "sample_count": len(telemetry.get("samples") or []),
        },
        "episodes": list(episode_records),
        "fatal_error": fatal_error,
        "interpretation_guardrails": [
            "Adverse outcomes are retained and do not trigger replacement or rerun.",
            "No success threshold or promotion decision is attached to this supplement.",
            "ROCm telemetry covers this sequential full-pipeline challenge workload only.",
            "Carrier/scout motion is logical-role kinematic burden on one shared Genesis chassis, not simultaneous dual-body dynamics.",
            "Motion path length is not an energy, throughput, latency, or physical-robot result.",
        ],
    }


def write_sha256sums(output_dir: Path) -> Path:
    target = output_dir / "SHA256SUMS"
    if target.exists():
        raise RuntimeError(f"refusing to overwrite: {target}")
    files = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path != target
    )
    lines = [
        f"{file_sha256(path)}  {path.relative_to(output_dir).as_posix()}"
        for path in files
    ]
    exclusive_write_text(target, "\n".join(lines) + "\n")
    return target


def prepare_output_directory(output_dir: Path) -> None:
    if output_dir.exists():
        raise ValueError(
            f"refusing existing output directory (no resume/overwrite/resample): {output_dir}"
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    for relative in ("episodes", "logs", "errors", "raw"):
        (output_dir / relative).mkdir(exist_ok=False)


def persist_preflight_raw(output_dir: Path, preflight: Mapping[str, Any]) -> None:
    raw = preflight.get("raw")
    if not isinstance(raw, Mapping):
        return
    for label in ("telemetry", "processes"):
        row = raw.get(label)
        if not isinstance(row, Mapping):
            continue
        exclusive_write_text(
            output_dir / "raw" / f"preflight_{label}.stdout.txt",
            str(row.get("raw_stdout") or ""),
        )
        exclusive_write_text(
            output_dir / "raw" / f"preflight_{label}.stderr.txt",
            str(row.get("raw_stderr") or ""),
        )
        exclusive_write_json(
            output_dir / "raw" / f"preflight_{label}.command.json",
            {key: value for key, value in row.items() if not key.startswith("raw_")},
        )


def build_run_manifest(
    *,
    args: argparse.Namespace,
    paths: Mapping[str, Path],
    preregistration: Mapping[str, Any],
    assets: Mapping[str, Any],
    source_identity: Mapping[str, Any],
    runtime_source_closure: Mapping[str, Any],
    preflight: Mapping[str, Any],
    schedule: Sequence[Mapping[str, Any]],
    episode_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    runner_path = Path(__file__).resolve()
    runner_protocol_commit = str(preregistration["runner_protocol_commit"])
    preregistration_public_commit = str(args.preregistration_public_commit or "")
    execution_order = [
        {"seed": int(row["seed"]), "policy": str(row["policy"])}
        for row in schedule
    ]
    source_rows = [
        {
            "path": row["path"],
            "expected_sha256": row["expected_sha256"],
            "observed_sha256": row["observed_sha256"],
            "matched": bool(row["matched"]),
        }
        for row in source_identity["critical_source_files"]
    ]
    attempts = [
        {
            "seed": int(record["seed"]),
            "policy": str(record["policy"]),
            "started_monotonic_ns": int(
                record["subprocess_started_monotonic_ns"]
            ),
            "ended_monotonic_ns": int(record["subprocess_ended_monotonic_ns"]),
            "wall_seconds": float(record["wall_seconds"]),
            "exit_code": record.get("command_exit_code"),
            "timeout_seconds": record.get("timeout_seconds"),
            "timed_out": bool(record.get("timed_out")),
            "start_new_session": bool(record.get("start_new_session")),
            "termination_grace_seconds": record.get(
                "termination_grace_seconds"
            ),
            "termination_actions": list(record.get("termination_actions") or []),
            "raw_episode_relative_path": str(record["episode_path"]),
            "log_relative_path": str(record["stdout_path"]),
            "stderr_relative_path": str(record["stderr_path"]),
        }
        for record in episode_records
    ]
    all_attempts_valid = bool(
        len(episode_records) == EPISODE_COUNT
        and all(record.get("attempt_integrity_valid") for record in episode_records)
        and all(record.get("command_exit_code") == 0 for record in episode_records)
    )
    return {
        "schema_version": "look-twice.v8-frozen-challenge-run-manifest/v1",
        "preregistration_sha256": preregistration["file_sha256"],
        "runner_sha256": preregistration["runner_sha256_observed"],
        "validator_sha256": preregistration["validator_sha256_observed"],
        "runner_protocol_commit": runner_protocol_commit,
        "preregistration_public_commit": preregistration_public_commit,
        "frozen_identities": {
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "vision_conformal_artifact_sha256": EXPECTED_VISION_ARTIFACT_IDENTITY_SHA256,
            "go_conformal_artifact_sha256": EXPECTED_GO_ARTIFACT_IDENTITY_SHA256,
            "purify_binary_sha256": EXPECTED_PURIFY_BINARY_SHA256,
            "source_tree_fingerprint_sha256": EXPECTED_SOURCE_TREE_FINGERPRINT_SHA256,
        },
        "execution": {
            "order": execution_order,
            "attempted_episode_count": len(episode_records),
            "completed_episode_count": sum(
                bool(record.get("attempt_integrity_valid"))
                for record in episode_records
            ),
            "retry_count": 0,
            "early_stopped": len(episode_records) != EPISODE_COUNT,
            "all_outcomes_preserved": True,
            "subprocess_exit_code": 0 if all_attempts_valid else 1,
            "attempts": attempts,
        },
        "source_preflight": {
            "source_tree_fingerprint_sha256": source_identity[
                "source_tree_fingerprint_sha256"
            ],
            "critical_source_file_count": len(source_rows),
            "mismatch_count": sum(not row["matched"] for row in source_rows),
            "files": source_rows,
            "runtime_source_closure": dict(runtime_source_closure),
        },
        "generated_at_utc_after_collection": utc_now(),
        "status": "COLLECTION_RECORDED",
        "one_shot_contract": {
            "attempts_per_seed_policy": 1,
            "retry_count_allowed": 0,
            "resume_allowed": False,
            "overwrite_allowed": False,
            "replacement_seed_allowed": False,
            "early_stopping_allowed": False,
            "continue_after_bad_outcome": True,
            "all_raw_outcomes_and_errors_preserved": True,
        },
        "claim_scope": {
            "label": "same-generator non-locked supplement",
            "not_locked": True,
            "not_ood": True,
            "not_population_generalization": True,
            "no_retuning_or_threshold_change": True,
            "motion_backend": "kinematic",
            "agent_realization": (
                "single_shared_genesis_chassis_with_separate_logical_role_poses"
            ),
            "not_simultaneous_dual_body_dynamics": True,
            "not_physical_robot_test": True,
        },
        "public_preregistration": {
            **dict(preregistration),
            "runner_protocol_commit": runner_protocol_commit,
            "preregistration_public_commit": preregistration_public_commit,
            "public_commits_distinct": (
                runner_protocol_commit != preregistration_public_commit
            ),
        },
        "runner": {
            "path": "scripts/run_v8_frozen_challenge.py",
            "sha256": file_sha256(runner_path),
            "size_bytes": runner_path.stat().st_size,
        },
        "frozen_assets": dict(assets),
        "frozen_source_identity": dict(source_identity),
        "runtime_source_closure": dict(runtime_source_closure),
        "clean_gpu_preflight": {
            key: value for key, value in preflight.items() if key != "raw"
        },
        "runtime": {
            "platform": platform.platform(),
            "python_executable": args.python,
            "python_version": platform.python_version(),
            "repo_root": str(paths["repo_root"]),
            "entrypoint": str(paths["entrypoint"]),
            "environment_overrides": {
                "PYTHONPATH": str(paths["repo_root"] / "src"),
                "PYOPENGL_PLATFORM": "egl",
                "MIOPEN_FIND_MODE": "FAST",
                "PATH": "/opt/venv/bin:" + os.environ.get("PATH", ""),
                "PATH_prepend": "/opt/venv/bin",
            },
        },
        "fixed_episode_contract": {
            "runtime": "genesis",
            "declared_environment_runtime": "genesis-amd",
            "motion_backend": "kinematic",
            "device": "cuda:0",
            "vision_backend": "torch_spatial_rgbd",
            "purify_go_gate": True,
            "repair_required": True,
            "profile": PROFILE,
            "seed_range": [SEED_START, SEED_END],
            "world_count": len(SEEDS),
            "episode_count": EPISODE_COUNT,
            "episode_timeout_seconds": EPISODE_TIMEOUT_SECONDS,
            "timeout_process_group_termination": {
                "start_new_session": True,
                "first_signal": "SIGTERM",
                "grace_seconds": EPISODE_TERMINATION_GRACE_SECONDS,
                "final_signal": "SIGKILL",
                "retry_after_timeout": False,
            },
        },
        "telemetry_contract": {
            "scope": TELEMETRY_SCOPE,
            "sample_interval_seconds": TELEMETRY_INTERVAL_SECONDS,
            "requires_sample_before_or_at_first_subprocess_start": True,
            "requires_sample_after_or_at_last_subprocess_end": True,
            "max_gap_seconds": TELEMETRY_MAX_GAP_SECONDS,
            "sampler_errors_allowed": 0,
        },
        "schedule_definition_sha256": canonical_json_sha256(list(schedule)),
        "schedule": list(schedule),
        "output_contract": {
            "required_top_level_files": [
                "RUN_MANIFEST.json",
                "ROCM_TELEMETRY.json",
                "CHALLENGE_REPORT.json",
                "SHA256SUMS",
            ],
            "raw_episode_files_expected": EPISODE_COUNT,
            "episode_windows_log": "raw/episode_windows.jsonl",
            "stdout_and_stderr_preserved_separately": True,
        },
    }


def empty_telemetry_report(
    preflight: Mapping[str, Any], fatal_error: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "look-twice.v8-frozen-challenge-rocm-telemetry/v1",
        "generated_at_utc": utc_now(),
        "scope": TELEMETRY_SCOPE,
        "sample_interval_seconds": TELEMETRY_INTERVAL_SECONDS,
        "sampler_started_monotonic_ns": None,
        "challenge_subprocess_started_monotonic_ns": None,
        "challenge_subprocess_ended_monotonic_ns": None,
        "sampler_ended_monotonic_ns": None,
        "command_exit_code": 1,
        "challenge_subprocess_exit_code": 1,
        "clean_gpu_preflight": {
            key: value for key, value in preflight.items() if key != "raw"
        },
        "coverage_checks": {
            "all_valid": False,
            "reason": "collection did not start",
        },
        "preflight": {
            "no_other_kfd_processes": bool(
                preflight.get("no_other_kfd_processes")
            ),
            "gpu_use_percent": _nested(
                preflight, "telemetry_before_first_episode", "gpu_use_percent"
            ),
            "vram_allocated_percent": _nested(
                preflight,
                "telemetry_before_first_episode",
                "vram_allocated_percent",
            ),
        },
        "sampler_errors": [dict(fatal_error)],
        "telemetry_summary": {"sample_count": 0},
        "samples": [],
    }


def load_bound_validator(path: Path) -> Any:
    """Import the exact validator whose SHA is bound in the preregistration."""

    spec = importlib.util.spec_from_file_location(
        "look_twice_bound_v8_challenge_validator", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import bound validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_report_with_bound_validator(
    *,
    paths: Mapping[str, Path],
    preregistration: Mapping[str, Any],
    manifest: Mapping[str, Any],
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    observed_validator_sha = file_sha256(paths["validator"])
    expected_validator_sha = str(preregistration["validator_sha256_declared"])
    if observed_validator_sha != expected_validator_sha:
        raise RuntimeError(
            "bound validator changed after preflight: "
            f"expected {expected_validator_sha}, got {observed_validator_sha}"
        )
    validator = load_bound_validator(paths["validator"])
    preregistration_payload = read_json_object(paths["preregistration"])
    validation_errors: list[str] = []
    records = validator.load_episode_records(
        paths["output_dir"], preregistration_payload, validation_errors
    )
    if validation_errors:
        raise RuntimeError(
            "bound validator rejected raw episodes before report derivation: "
            + "; ".join(validation_errors)
        )
    if len(records) != EPISODE_COUNT:
        raise RuntimeError(
            f"bound validator read {len(records)} episodes, expected {EPISODE_COUNT}"
        )
    report = validator.expected_report(
        records,
        str(preregistration["file_sha256"]),
        manifest,
        telemetry,
    )
    if not isinstance(report, dict):
        raise RuntimeError("bound validator expected_report did not return an object")
    return report


def execute_collection(
    *,
    args: argparse.Namespace,
    paths: Mapping[str, Path],
    preregistration: Mapping[str, Any],
    preflight: Mapping[str, Any],
    schedule: Sequence[Mapping[str, Any]],
    assets: Mapping[str, Any],
    source_identity: Mapping[str, Any],
    runtime_source_closure: Mapping[str, Any],
) -> int:
    output_dir = paths["output_dir"]
    manifest_path = output_dir / "RUN_MANIFEST.json"
    telemetry_path = output_dir / "ROCM_TELEMETRY.json"
    report_path = output_dir / "CHALLENGE_REPORT.json"
    episode_records: list[dict[str, Any]] = []
    fatal_error: dict[str, Any] | None = None
    challenge_started_ns: int | None = None
    challenge_ended_ns: int | None = None
    sampler = FullChainTelemetrySampler(args.rocm_smi, TELEMETRY_INTERVAL_SECONDS)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(paths["repo_root"] / "src")
    env["PYOPENGL_PLATFORM"] = "egl"
    env["MIOPEN_FIND_MODE"] = "FAST"
    env["PATH"] = "/opt/venv/bin:" + env.get("PATH", "")

    windows_path = output_dir / "raw" / "episode_windows.jsonl"
    try:
        with windows_path.open("x", encoding="utf-8") as windows_handle:
            sampler.start()
            if not sampler.wait_for_first_sample(timeout=15.0):
                raise RuntimeError("telemetry sampler produced no pre-challenge sample")
            first = sampler.samples[0]
            if first.get("command_exit_code") != 0 or first.get("sampler_error"):
                raise RuntimeError("first telemetry sample failed; challenge not started")

            for index, spec in enumerate(schedule):
                print(
                    f"[{index + 1:02d}/{EPISODE_COUNT}] seed={spec['seed']} "
                    f"policy={spec['policy']}",
                    flush=True,
                )
                record = _run_one_episode(
                    python=args.python,
                    paths=paths,
                    spec=spec,
                    env=env,
                )
                if challenge_started_ns is None:
                    challenge_started_ns = int(
                        record["subprocess_started_monotonic_ns"]
                    )
                challenge_ended_ns = int(record["subprocess_ended_monotonic_ns"])
                episode_records.append(record)
                append_json_line(windows_handle, record)
                print(
                    f"  rc={record['command_exit_code']} "
                    f"valid={record['attempt_integrity_valid']} "
                    f"wall={record['wall_seconds']:.3f}s "
                    f"output={record['episode_path']}",
                    flush=True,
                )
    except BaseException as exc:
        fatal_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
            "at_utc": utc_now(),
        }
        try:
            exclusive_write_json(output_dir / "errors" / "runner_fatal.json", fatal_error)
        except FileExistsError:
            pass
    finally:
        if challenge_ended_ns is not None:
            covered = sampler.wait_for_sample_at_or_after(
                challenge_ended_ns, timeout=15.0
            )
            if not covered and fatal_error is None:
                fatal_error = {
                    "type": "TelemetryPostCoverageTimeout",
                    "message": "no telemetry sample covered the last subprocess end",
                    "traceback": None,
                    "at_utc": utc_now(),
                }
        if sampler.started_monotonic_ns is not None:
            sampler.stop()

    manifest = build_run_manifest(
        args=args,
        paths=paths,
        preregistration=preregistration,
        assets=assets,
        source_identity=source_identity,
        runtime_source_closure=runtime_source_closure,
        preflight=preflight,
        schedule=schedule,
        episode_records=episode_records,
    )
    exclusive_write_json(manifest_path, manifest)
    telemetry = build_telemetry_report(
        sampler=sampler,
        challenge_started_monotonic_ns=challenge_started_ns,
        challenge_ended_monotonic_ns=challenge_ended_ns,
        episode_records=episode_records,
        preflight=preflight,
    )
    if fatal_error is None and (
        _nested(telemetry, "coverage_checks", "all_valid") is not True
        or _nested(manifest, "execution", "subprocess_exit_code") != 0
    ):
        fatal_error = {
            "type": "CollectionIntegrityFailure",
            "message": (
                "one or more episode attempts or full-wall telemetry checks were invalid; "
                "the one-shot evidence is preserved and will not be rerun"
            ),
            "traceback": None,
            "at_utc": utc_now(),
        }
    exclusive_write_json(telemetry_path, telemetry)
    try:
        report = build_report_with_bound_validator(
            paths=paths,
            preregistration=preregistration,
            manifest=manifest,
            telemetry=telemetry,
        )
    except Exception as exc:
        if fatal_error is None:
            fatal_error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "at_utc": utc_now(),
            }
        report = build_challenge_report(
            episode_records=episode_records,
            telemetry=telemetry,
            manifest_path=manifest_path,
            telemetry_path=telemetry_path,
            preregistration=preregistration,
            fatal_error=fatal_error,
        )
    exclusive_write_json(report_path, report)
    sums_path = write_sha256sums(output_dir)
    print(
        json.dumps(
            {
                "collection_status": (
                    "complete" if len(episode_records) == EPISODE_COUNT else "incomplete"
                ),
                "integrity_status": (
                    "valid" if fatal_error is None else "invalid"
                ),
                "attempted": len(episode_records),
                "valid": sum(
                    bool(record.get("attempt_integrity_valid"))
                    for record in episode_records
                ),
                "report": str(report_path),
                "sha256sums": str(sums_path),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if fatal_error is None else 2


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    default_python = "/opt/venv/bin/python" if Path("/opt/venv/bin/python").is_file() else sys.executable
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--preregistration",
        type=Path,
        required=True,
        help="Public preregistration JSON; exact runner SHA binding is required to execute.",
    )
    parser.add_argument(
        "--preregistration-public-commit",
        default=None,
        help=(
            "Formal-run Commit B: 40-hex public commit containing the bound "
            "preregistration; required unless --dry-run."
        ),
    )
    parser.add_argument("--identity-manifest", type=Path, default=None)
    parser.add_argument(
        "--runtime-source-manifest",
        type=Path,
        default=None,
        help=(
            "Exact 30-file runtime dependency manifest; defaults to the bound "
            "release manifest under --repo-root."
        ),
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=None,
        help="Bound independent validator used to derive the exact public report.",
    )
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--vision-conformal-artifact", type=Path, default=None)
    parser.add_argument("--go-conformal-artifact", type=Path, default=None)
    parser.add_argument("--purify-binary", type=Path, default=None)
    parser.add_argument("--python", default=default_python)
    parser.add_argument("--rocm-smi", default="rocm-smi")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect the fixed design only; do not hash assets, touch ROCm, or create output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = resolve_paths(args)
    schedule = build_schedule()
    preregistration = validate_preregistration(
        paths["preregistration"],
        Path(__file__).resolve(),
        require_runner_binding=not args.dry_run,
        validator_path=paths["validator"],
    )
    if args.preregistration_public_commit is not None and not re.fullmatch(
        r"[0-9a-f]{40}", args.preregistration_public_commit
    ):
        raise SystemExit("--preregistration-public-commit must be a lowercase 40-hex SHA")
    if not args.dry_run and args.preregistration_public_commit is None:
        raise SystemExit(
            "formal execution requires --preregistration-public-commit (Commit B)"
        )
    if (
        not args.dry_run
        and args.preregistration_public_commit
        == preregistration["runner_protocol_commit"]
    ):
        raise SystemExit(
            "Commit B (--preregistration-public-commit) must differ from runner/protocol Commit A"
        )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "schema_version": "look-twice.v8-frozen-challenge-dry-run/v1",
                    "status": "dry-run",
                    "created_output": False,
                    "touched_rocm": False,
                    "loaded_checkpoint": False,
                    "preregistration": preregistration,
                    "claim_scope": "same-generator non-locked supplement",
                    "fixed_seed_range": [SEED_START, SEED_END],
                    "fixed_episode_count": EPISODE_COUNT,
                    "fixed_schedule": schedule,
                    "resolved_paths_not_opened": {
                        key: str(value) for key, value in paths.items()
                    },
                },
                indent=2,
            )
        )
        return 0

    if paths["output_dir"].exists():
        raise SystemExit(
            "refusing existing output directory (no resume/overwrite/resample): "
            f"{paths['output_dir']}"
        )
    if not paths["repo_root"].is_dir():
        raise SystemExit(f"repo root not found: {paths['repo_root']}")
    if not paths["entrypoint"].is_file():
        raise SystemExit(f"frozen entrypoint not found: {paths['entrypoint']}")

    try:
        assets = verify_frozen_assets(paths)
        source_identity = verify_identity_manifest(
            paths["identity_manifest"], paths["repo_root"]
        )
        runtime_source_closure = verify_runtime_source_manifest(
            paths["runtime_source_manifest"], paths["repo_root"]
        )
        runtime_import_canary = run_runtime_source_import_canary(
            python=args.python,
            repo_root=paths["repo_root"],
            runtime_source_closure=runtime_source_closure,
        )
        runtime_source_closure = bind_runtime_source_import_canary(
            runtime_source_closure, runtime_import_canary
        )
        if not runtime_import_canary["passed"]:
            raise ValueError(
                "runtime source import canary failed before collection: "
                f"exit={runtime_import_canary.get('command_exit_code')} "
                f"stderr={str(runtime_import_canary.get('raw_stderr') or '')[-4000:]}"
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    preflight = run_clean_gpu_preflight(args.rocm_smi)
    prepare_output_directory(paths["output_dir"])
    persist_preflight_raw(paths["output_dir"], preflight)
    persist_runtime_source_import_canary_raw(
        paths["output_dir"], runtime_import_canary
    )
    exclusive_write_json(
        paths["output_dir"] / "raw" / "PRESTART_BINDING.json",
        {
            "schema_version": "look-twice.v8-frozen-challenge-prestart-binding/v1",
            "bound_at_utc_before_first_episode": utc_now(),
            "preregistration_sha256": preregistration["file_sha256"],
            "runner_sha256": preregistration["runner_sha256_observed"],
            "validator_sha256": preregistration["validator_sha256_observed"],
            "runner_protocol_commit": preregistration["runner_protocol_commit"],
            "preregistration_public_commit": args.preregistration_public_commit,
            "frozen_assets": assets,
            "source_preflight": source_identity,
            "runtime_source_closure": runtime_source_closure,
            "clean_gpu_preflight": {
                key: value for key, value in preflight.items() if key != "raw"
            },
            "fixed_subprocess_environment": {
                "PYTHONPATH": str(paths["repo_root"] / "src"),
                "PYOPENGL_PLATFORM": "egl",
                "MIOPEN_FIND_MODE": "FAST",
                "PATH": "/opt/venv/bin:" + os.environ.get("PATH", ""),
                "PATH_prepend": "/opt/venv/bin",
            },
            "planned_schedule": list(schedule),
            "no_episode_had_started": True,
        },
    )
    manifest_path = paths["output_dir"] / "RUN_MANIFEST.json"

    if not preflight["passed"]:
        fatal = {
            "type": "CleanGpuPreflightFailed",
            "message": "; ".join(preflight["errors"]),
            "traceback": None,
            "at_utc": utc_now(),
        }
        exclusive_write_json(paths["output_dir"] / "errors" / "preflight.json", fatal)
        manifest = build_run_manifest(
            args=args,
            paths=paths,
            preregistration=preregistration,
            assets=assets,
            source_identity=source_identity,
            runtime_source_closure=runtime_source_closure,
            preflight=preflight,
            schedule=schedule,
            episode_records=[],
        )
        exclusive_write_json(manifest_path, manifest)
        telemetry = empty_telemetry_report(preflight, fatal)
        telemetry_path = paths["output_dir"] / "ROCM_TELEMETRY.json"
        exclusive_write_json(telemetry_path, telemetry)
        report = build_challenge_report(
            episode_records=[],
            telemetry=telemetry,
            manifest_path=manifest_path,
            telemetry_path=telemetry_path,
            preregistration=preregistration,
            fatal_error=fatal,
        )
        exclusive_write_json(paths["output_dir"] / "CHALLENGE_REPORT.json", report)
        write_sha256sums(paths["output_dir"])
        return 2

    return execute_collection(
        args=args,
        paths=paths,
        preregistration=preregistration,
        preflight=preflight,
        schedule=schedule,
        assets=assets,
        source_identity=source_identity,
        runtime_source_closure=runtime_source_closure,
    )


if __name__ == "__main__":
    raise SystemExit(main())
