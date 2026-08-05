#!/usr/bin/env python3
"""Creation-only runner for the preregistered V8 contract-progress challenge.

Formal mode requires separate frozen-baseline and opt-in-candidate source roots,
fully bound public preregistration hashes, a clean two-commit Git binding, exact
frozen V8 artifacts, and a clean AMD GPU.  The forty fixed cells are attempted
once in their preregistered order.  Failures are retained and never retried.

``--dry-run`` performs design and identity checks only.  It does not create the
output root, query ROCm, initialize Genesis, load the checkpoint, or execute a
challenge seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import shutil
import stat
import statistics
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

try:
    from verify_v8_contract_progress_challenge import (
        EPISODE_COUNT,
        EPISODE_TIMEOUT_SECONDS,
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
        MANIFEST_SCHEMA,
        POSTRUN_SCHEMA,
        PRESTART_SCHEMA,
        PROFILE,
        SEED_END,
        SEED_START,
        VerificationError,
        build_schedule,
        canonical_json_sha256,
        derive_episode_row,
        file_sha256,
        read_json_object,
        schedule_sha256,
        validate_preregistration,
    )
except ModuleNotFoundError:  # imported as scripts.run_...
    from scripts.verify_v8_contract_progress_challenge import (
        EPISODE_COUNT,
        EPISODE_TIMEOUT_SECONDS,
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
        MANIFEST_SCHEMA,
        POSTRUN_SCHEMA,
        PRESTART_SCHEMA,
        PROFILE,
        SEED_END,
        SEED_START,
        VerificationError,
        build_schedule,
        canonical_json_sha256,
        derive_episode_row,
        file_sha256,
        read_json_object,
        schedule_sha256,
        validate_preregistration,
    )


TELEMETRY_SCHEMA = "look-twice.v8-contract-progress-challenge-rocm-telemetry/v1"
TELEMETRY_INTERVAL_SECONDS = 2.0
TELEMETRY_MAX_GAP_SECONDS = 5.5
PREFLIGHT_MAX_GPU_USE_PERCENT = 5.0
PREFLIGHT_MAX_VRAM_ALLOCATED_PERCENT = 2.0
TERMINATION_GRACE_SECONDS = 10.0
RUNTIME_MANIFEST_RELATIVE = (
    "release/v8-frozen/results/V8_CHALLENGE_RUNTIME_SOURCE_MANIFEST.json"
)
RUNTIME_MANIFEST_SCHEMA = "look-twice.v8-challenge-runtime-dependency-manifest/v1"
RUNTIME_ROOT_ENTRYPOINT = "src/look_twice_v7.py"
RUNTIME_STATIC_ASSET = "assets/robots/look_twice_skid_steer.urdf"
RUNTIME_SOURCE_ORIGIN_COMMIT = "aadd429d2da9de690a361218c40c9dfb22b04eb2"
RUNTIME_TREE_ALGORITHM = (
    "sha256 of lexicographically path-sorted lines formatted as "
    "'<file_sha256>  <relative_path>\\n'"
)
PREREG_RELATIVE = (
    "release/v8-derived/contract_progress_challenge_102530_102549/PREREGISTRATION.json"
)
DEFAULT_OUTPUT_BASENAME = "look-twice-contract-progress-102530-102549-formal-run"
ROCM_COMMAND = (
    "rocm-smi",
    "--showuse",
    "--showmemuse",
    "--showpower",
    "--showtemp",
    "--json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def exclusive_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    exclusive_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
    )


def append_jsonl(handle: Any, payload: Mapping[str, Any]) -> None:
    handle.write(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    handle.flush()
    os.fsync(handle.fileno())


def _fsync_file_and_parent(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path.parent, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def durably_persist_attempt_files(paths: Sequence[Path]) -> None:
    """Persist child-written episode output before its ATTEMPTS row is fsynced."""

    existing = [path for path in paths if path.is_file()]
    for path in existing:
        _fsync_file_and_parent(path)


def _first_existing(root: Path, relatives: Sequence[str]) -> Path:
    for relative in relatives:
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return root / relatives[0]


def _resolve_python(value: str) -> Path:
    discovered = shutil.which(value) if "/" not in value else value
    if not discovered:
        raise VerificationError(f"Python executable not found: {value}")
    # Preserve the venv launcher path.  Resolving /opt/venv/bin/python to its
    # system target changes sys.prefix and silently drops the venv packages.
    path = Path(os.path.abspath(discovered))
    target = path.resolve()
    if not target.is_file() or not os.access(path, os.X_OK):
        raise VerificationError(f"Python executable target is unavailable: {path}")
    return path


def verify_python_identity(path: Path) -> dict[str, Any]:
    invocation = Path(os.path.abspath(path))
    target = invocation.resolve()
    if not target.is_file() or not os.access(invocation, os.X_OK):
        raise VerificationError(
            f"Python executable target is unavailable: {invocation}"
        )
    completed = subprocess.run(
        [str(invocation), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"Python identity query failed for {invocation}: {completed.stderr.strip()}"
        )
    return {
        "invocation_path": str(invocation),
        "resolved_target_path": str(target),
        "resolved_target_sha256": file_sha256(target),
        "version": (completed.stdout or completed.stderr).strip(),
        "venv_launcher_path_preserved": True,
    }


def resolve_paths(args: argparse.Namespace) -> dict[str, Path]:
    candidate_root = args.candidate_root.resolve()
    baseline_root = args.baseline_root.resolve()
    asset_root = (args.asset_root or baseline_root).resolve()
    checkpoint = (
        args.checkpoint.resolve()
        if args.checkpoint
        else _first_existing(
            asset_root,
            (
                "results/v8-seg-v3-full-paired-v2-fast-promote/frozen_checkpoint/"
                "v8_seg_v3_selected_ep22_7b158726f9c0.pt",
                "release/v8-frozen/results/frozen_checkpoint/"
                "v8_seg_v3_selected_ep22_7b158726f9c0.pt",
            ),
        )
    )
    vision = (
        args.vision_conformal_artifact.resolve()
        if args.vision_conformal_artifact
        else _first_existing(
            asset_root,
            (
                "results/v8-seg-v3-full-paired-v2-fast-promote/"
                "calibration_vision/conformal_artifact.json",
                "release/v8-frozen/results/calibration_vision/conformal_artifact.json",
            ),
        )
    )
    go = (
        args.go_conformal_artifact.resolve()
        if args.go_conformal_artifact
        else _first_existing(
            asset_root,
            (
                "results/v8-seg-v3-full-paired-v2-fast-promote/"
                "calibration_go_fusion_v3/conformal_artifact.json",
                "release/v8-frozen/results/calibration_go_fusion_v3/"
                "conformal_artifact.json",
            ),
        )
    )
    purify = (
        args.purify_binary.resolve()
        if args.purify_binary
        else _first_existing(
            asset_root,
            (
                "purify_robotics/bin/purify-robotics-core-linux",
                "release/v8-frozen/artifacts/purify-robotics-core-linux",
            ),
        )
    )
    identity_manifest = (
        args.identity_manifest.resolve()
        if args.identity_manifest
        else _first_existing(
            asset_root,
            (
                "results/v8-seg-v3-full-paired-v2-fast-promote/"
                "V8_IDENTITY_FREEZE_MANIFEST.json",
                "release/v8-frozen/results/V8_IDENTITY_FREEZE_MANIFEST.json",
            ),
        )
    )
    return {
        "baseline_root": baseline_root,
        "candidate_root": candidate_root,
        "baseline_entrypoint": baseline_root / "src" / "look_twice_v7.py",
        "candidate_entrypoint": candidate_root / "src" / "look_twice_v7.py",
        "checkpoint": checkpoint,
        "vision_artifact": vision,
        "go_artifact": go,
        "purify_binary": purify,
        "identity_manifest": identity_manifest,
        "runtime_manifest": baseline_root / RUNTIME_MANIFEST_RELATIVE,
        "preregistration": args.preregistration.resolve(),
        "runner": Path(__file__).resolve(),
        "verifier": Path(__file__)
        .resolve()
        .with_name("verify_v8_contract_progress_challenge.py"),
        "python_executable": _resolve_python(str(args.python)),
        "output_root": args.output_root.resolve(),
    }


def _verify_file(
    path: Path, expected_sha: str, *, executable: bool = False
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"required file is missing: {path}")
    actual = file_sha256(path)
    if actual != expected_sha:
        raise VerificationError(
            f"file identity mismatch {path}: expected {expected_sha}, got {actual}"
        )
    if executable and not os.access(path, os.X_OK):
        raise VerificationError(f"required binary is not executable: {path}")
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": actual,
        "executable": os.access(path, os.X_OK) if executable else None,
    }


def _verify_json_artifact(
    path: Path,
    *,
    expected_file_sha: str,
    expected_artifact_sha: str,
) -> dict[str, Any]:
    result = _verify_file(path, expected_file_sha)
    payload = read_json_object(path)
    if payload.get("artifact_sha256") != expected_artifact_sha:
        raise VerificationError(f"artifact identity mismatch: {path}")
    if payload.get("checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA256:
        raise VerificationError(f"artifact checkpoint binding mismatch: {path}")
    result["artifact_sha256"] = expected_artifact_sha
    result["checkpoint_sha256"] = EXPECTED_CHECKPOINT_SHA256
    return result


def verify_baseline_runtime_closure(root: Path, manifest_path: Path) -> dict[str, Any]:
    identity = _verify_file(manifest_path, EXPECTED_RUNTIME_MANIFEST_SHA256)
    payload = read_json_object(manifest_path)
    if payload.get("schema_version") != RUNTIME_MANIFEST_SCHEMA:
        raise VerificationError("baseline runtime manifest schema changed")
    if payload.get("root_entrypoint") != RUNTIME_ROOT_ENTRYPOINT:
        raise VerificationError("baseline runtime root entrypoint changed")
    if payload.get("source_origin_git_commit") != RUNTIME_SOURCE_ORIGIN_COMMIT:
        raise VerificationError("baseline runtime source-origin commit changed")
    if payload.get("file_count") != 30 or payload.get("python_file_count") != 29:
        raise VerificationError("baseline runtime manifest counts changed")
    if payload.get("static_asset_file_count") != 1:
        raise VerificationError("baseline runtime static-asset count changed")
    if payload.get("tree_fingerprint_algorithm") != RUNTIME_TREE_ALGORITHM:
        raise VerificationError("baseline runtime fingerprint algorithm changed")
    if payload.get("tree_fingerprint_sha256") != EXPECTED_RUNTIME_TREE_SHA256:
        raise VerificationError("baseline runtime manifest tree identity changed")
    files = payload.get("files")
    if not isinstance(files, list) or len(files) != 30:
        raise VerificationError("baseline runtime manifest must declare 30 files")
    observations: list[dict[str, Any]] = []
    observed_files: dict[str, str] = {}
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, Mapping):
            raise VerificationError("invalid runtime manifest file row")
        relative = str(row.get("path") or "")
        pure = PurePosixPath(relative)
        declared = str(row.get("sha256") or row.get("file_sha256") or "")
        if (
            not relative
            or pure.is_absolute()
            or relative != pure.as_posix()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or not (
                (pure.parts[0] == "src" and pure.suffix == ".py")
                or relative == RUNTIME_STATIC_ASSET
            )
            or relative in seen
            or not re.fullmatch(r"[0-9a-f]{64}", declared)
        ):
            raise VerificationError(
                f"invalid runtime manifest declaration: {relative!r}"
            )
        seen.add(relative)
        path = root / relative
        current = root
        for part in pure.parts:
            current = current / part
            if current.is_symlink():
                raise VerificationError(
                    f"baseline runtime path traverses a symlink: {current}"
                )
        if not path.exists() or not stat.S_ISREG(path.lstat().st_mode):
            raise VerificationError(f"baseline runtime path is not regular: {path}")
        observed = _verify_file(path, declared)
        observations.append({"path": relative, "sha256": observed["sha256"]})
        observed_files[relative] = observed["sha256"]
    declared_python = {relative for relative in seen if relative.startswith("src/")}
    source_root = root / "src"
    if not source_root.is_dir() or source_root.is_symlink():
        raise VerificationError("baseline src root is not an ordinary directory")
    actual_source_files: set[str] = set()
    for candidate in source_root.rglob("*"):
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise VerificationError(
                f"baseline runtime source tree contains a symlink: {candidate}"
            )
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise VerificationError(
                f"baseline runtime source path is not regular: {candidate}"
            )
        actual_source_files.add(candidate.relative_to(root).as_posix())
    if actual_source_files != declared_python:
        raise VerificationError(
            "baseline runtime exact src file set mismatch: "
            f"missing={sorted(declared_python - actual_source_files)} "
            f"extra={sorted(actual_source_files - declared_python)}"
        )

    fingerprint_material = "".join(
        f"{observed_files[path]}  {path}\n" for path in sorted(observed_files)
    )
    fingerprint = hashlib.sha256(fingerprint_material.encode("utf-8")).hexdigest()
    if fingerprint != EXPECTED_RUNTIME_TREE_SHA256:
        raise VerificationError("observed baseline runtime tree fingerprint mismatch")
    return {
        "manifest": identity,
        "tree_fingerprint_sha256": fingerprint,
        "file_count": len(observations),
        "python_file_count": len(declared_python),
        "exact_python_file_set_verified": True,
        "exact_src_file_set_verified": True,
        "source_origin_git_commit": RUNTIME_SOURCE_ORIGIN_COMMIT,
        "files": observations,
    }


def _local_git_environment() -> dict[str, str]:
    """Return a Git environment with repository/config redirection scrubbed."""

    allowed_exact = {
        "PATH",
        "LANG",
        "LANGUAGE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in allowed_exact or key.startswith("LC_")
    }
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
        }
    )
    return environment


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=_local_git_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"git {' '.join(args)} failed in {root}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _anonymous_github_https_url(remote_url: str) -> tuple[str, str]:
    value = remote_url.strip()
    path: str | None = None
    if value.startswith("git@github.com:"):
        path = value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        path = value.removeprefix("ssh://git@github.com/")
    elif value.startswith("https://github.com/"):
        path = value.removeprefix("https://github.com/")
    if path is None:
        raise VerificationError(
            "public preregistration remote must resolve to github.com"
        )
    path = path.removesuffix(".git").strip("/")
    fields = path.split("/")
    if len(fields) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", field) for field in fields
    ):
        raise VerificationError("public GitHub owner/repository path is malformed")
    slug = "/".join(fields)
    return f"https://github.com/{slug}.git", slug


def _anonymous_git_environment() -> dict[str, str]:
    """Build a minimal Git environment with no inherited credential hooks."""

    environment = _local_git_environment()
    environment.update(
        {
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
        }
    )
    return environment


def verify_two_commit_binding(
    candidate_root: Path, prereg: Mapping[str, Any]
) -> dict[str, Any]:
    binding = prereg["public_binding"]
    commit_a = str(binding["commit_a"])
    remote_name = str(binding["remote_name"])
    head = _git(candidate_root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise VerificationError("candidate HEAD is not a full Git commit")
    status = _git(
        candidate_root,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise VerificationError("candidate root is not clean at formal prestart")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_a, head],
        cwd=candidate_root,
        env=_local_git_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if ancestor.returncode != 0 or commit_a == head:
        raise VerificationError("Commit A is not a strict ancestor of current Commit B")
    parent = _git(candidate_root, "rev-parse", f"{head}^")
    commit_count = _git(candidate_root, "rev-list", "--count", f"{commit_a}..{head}")
    if parent != commit_a or commit_count != "1":
        raise VerificationError("Commit B must be the single direct child of Commit A")
    changed = _git(
        candidate_root, "diff", "--name-only", f"{commit_a}..{head}"
    ).splitlines()
    allowed = str(binding["commit_b_diff_from_a_may_only_change"])
    if changed != [allowed]:
        raise VerificationError(
            f"Commit A to B diff must contain only {allowed}; observed {changed}"
        )
    configured_remote_url = _git(candidate_root, "remote", "get-url", remote_name)
    public_url, public_slug = _anonymous_github_https_url(configured_remote_url)
    anonymous_environment = _anonymous_git_environment()
    remote = subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "ls-remote",
            "--heads",
            public_url,
        ],
        cwd=candidate_root.parent,
        env=anonymous_environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if remote.returncode != 0:
        raise VerificationError(
            f"live public remote check failed for {remote_name}: "
            f"{remote.stderr.strip()}"
        )
    public_refs: list[str] = []
    for line in remote.stdout.splitlines():
        fields = line.split()
        if (
            len(fields) == 2
            and fields[0] == head
            and fields[1].startswith("refs/heads/")
        ):
            public_refs.append(fields[1])
    public_refs = sorted(set(public_refs))
    if not public_refs:
        raise VerificationError(
            "current clean Commit B is not an exact branch head returned by "
            f"an anonymous live git ls-remote --heads {public_slug}"
        )
    return {
        "commit_a": commit_a,
        "commit_b_observed_clean_head": head,
        "commit_a_strict_ancestor": True,
        "commit_b_direct_parent_is_commit_a": True,
        "commit_count_a_to_b": 1,
        "commit_a_to_b_changed_paths": changed,
        "candidate_checkout_clean": True,
        "public_remote_name": remote_name,
        "public_github_repository": public_slug,
        "public_remote_access": "anonymous_https_no_credential_helper",
        "public_remote_head_refs": public_refs,
        "commit_b_public_remote_head_verified": True,
        "public_remote_checked_at_utc": utc_now(),
    }


def verify_design(paths: Mapping[str, Path], *, formal: bool) -> dict[str, Any]:
    if not paths["baseline_root"].is_dir() or not paths["candidate_root"].is_dir():
        raise VerificationError("baseline and candidate roots must exist")
    if formal and paths["baseline_root"] == paths["candidate_root"]:
        raise VerificationError("formal baseline and candidate roots must be different")
    if formal and any(
        paths["output_root"] == root or root in paths["output_root"].parents
        for root in (paths["baseline_root"], paths["candidate_root"])
    ):
        raise VerificationError(
            "formal output root must be outside both source roots so postrun Git "
            "cleanliness remains independently checkable"
        )
    for key in ("baseline_entrypoint", "candidate_entrypoint", "verifier"):
        if not paths[key].is_file():
            raise VerificationError(f"required executable source missing: {paths[key]}")

    prereg = read_json_object(paths["preregistration"])
    prereg_obs = validate_preregistration(
        prereg,
        runner_sha256=file_sha256(paths["runner"]),
        verifier_sha256=file_sha256(paths["verifier"]),
        candidate_root=paths["candidate_root"],
        formal=formal,
    )
    if formal and not isinstance(prereg_obs.get("candidate_source_closure"), Mapping):
        raise VerificationError("formal candidate exact tracked src closure is missing")
    checkpoint = _verify_file(paths["checkpoint"], EXPECTED_CHECKPOINT_SHA256)
    vision = _verify_json_artifact(
        paths["vision_artifact"],
        expected_file_sha=EXPECTED_VISION_FILE_SHA256,
        expected_artifact_sha=EXPECTED_VISION_ARTIFACT_SHA256,
    )
    go = _verify_json_artifact(
        paths["go_artifact"],
        expected_file_sha=EXPECTED_GO_FILE_SHA256,
        expected_artifact_sha=EXPECTED_GO_ARTIFACT_SHA256,
    )
    purify = _verify_file(
        paths["purify_binary"], EXPECTED_PURIFY_SHA256, executable=True
    )
    identity = _verify_file(
        paths["identity_manifest"], EXPECTED_IDENTITY_MANIFEST_SHA256
    )
    identity_payload = read_json_object(paths["identity_manifest"])
    if (
        identity_payload.get("source_tree_fingerprint_sha256")
        != EXPECTED_SOURCE_TREE_SHA256
    ):
        raise VerificationError("V8 identity manifest source fingerprint changed")
    baseline_closure = verify_baseline_runtime_closure(
        paths["baseline_root"], paths["runtime_manifest"]
    )
    python_identity = verify_python_identity(paths["python_executable"])
    git_binding = (
        verify_two_commit_binding(paths["candidate_root"], prereg) if formal else None
    )
    return {
        "preregistration": prereg_obs,
        "checkpoint": checkpoint,
        "vision_artifact": vision,
        "go_artifact": go,
        "purify_binary": purify,
        "identity_manifest": identity,
        "baseline_runtime_closure": baseline_closure,
        "candidate_source_closure": prereg_obs.get("candidate_source_closure"),
        "python_identity": python_identity,
        "git_binding": git_binding,
        "schedule": build_schedule(),
        "schedule_sha256": schedule_sha256(),
    }


def immutable_binding_snapshot(
    paths: Mapping[str, Path], design: Mapping[str, Any]
) -> dict[str, Any]:
    git_binding = design.get("git_binding")
    if not isinstance(git_binding, Mapping):
        raise VerificationError("formal immutable binding lacks Git proof")
    return {
        "paths": {
            key: str(paths[key])
            for key in (
                "baseline_root",
                "candidate_root",
                "baseline_entrypoint",
                "candidate_entrypoint",
                "checkpoint",
                "vision_artifact",
                "go_artifact",
                "purify_binary",
                "identity_manifest",
                "runtime_manifest",
                "preregistration",
                "runner",
                "verifier",
                "python_executable",
            )
        },
        "files": {
            "preregistration_sha256": file_sha256(paths["preregistration"]),
            "runner_sha256": file_sha256(paths["runner"]),
            "verifier_sha256": file_sha256(paths["verifier"]),
            "checkpoint": design["checkpoint"],
            "vision_artifact": design["vision_artifact"],
            "go_artifact": design["go_artifact"],
            "purify_binary": design["purify_binary"],
            "identity_manifest": design["identity_manifest"],
        },
        "baseline_runtime_closure": design["baseline_runtime_closure"],
        "candidate_source_files": design["preregistration"]["candidate_source_files"],
        "candidate_source_closure": design["candidate_source_closure"],
        "python_identity": design["python_identity"],
        "git": {
            key: git_binding[key]
            for key in (
                "commit_a",
                "commit_b_observed_clean_head",
                "commit_a_strict_ancestor",
                "commit_b_direct_parent_is_commit_a",
                "commit_count_a_to_b",
                "commit_a_to_b_changed_paths",
                "candidate_checkout_clean",
                "public_remote_name",
                "public_github_repository",
                "public_remote_access",
                "public_remote_head_refs",
                "commit_b_public_remote_head_verified",
            )
        },
        "schedule_sha256": schedule_sha256(),
    }


def write_postrun_binding(
    paths: Mapping[str, Path],
    prestart_snapshot: Mapping[str, Any],
    *,
    attempts_completed: int,
    last_attempt_ended_monotonic_ns: int,
) -> dict[str, Any]:
    path = paths["output_root"] / "raw" / "POSTRUN_BINDING.json"
    checked_at = utc_now()
    checked_ns = time.perf_counter_ns()
    try:
        post_design = verify_design(paths, formal=True)
        post_snapshot = immutable_binding_snapshot(paths, post_design)
        pre_hash = canonical_json_sha256(prestart_snapshot)
        post_hash = canonical_json_sha256(post_snapshot)
        identical = post_snapshot == prestart_snapshot and post_hash == pre_hash
        payload = {
            "schema_version": POSTRUN_SCHEMA,
            "checked_at_utc_after_all_attempts": checked_at,
            "checked_monotonic_ns_after_all_attempts": checked_ns,
            "attempts_completed": attempts_completed,
            "last_attempt_ended_monotonic_ns": last_attempt_ended_monotonic_ns,
            "revalidation_passed": identical,
            "prestart_immutable_binding_sha256": pre_hash,
            "postrun_immutable_binding_sha256": post_hash,
            "prestart_equals_postrun": identical,
            "immutable_binding": post_snapshot,
            "validation_error": (
                None if identical else "postrun immutable binding differs from prestart"
            ),
        }
        exclusive_write_json(path, payload)
        return payload
    except Exception as exc:
        failure_payload = {
            "schema_version": POSTRUN_SCHEMA,
            "checked_at_utc_after_all_attempts": checked_at,
            "checked_monotonic_ns_after_all_attempts": checked_ns,
            "attempts_completed": attempts_completed,
            "last_attempt_ended_monotonic_ns": last_attempt_ended_monotonic_ns,
            "revalidation_passed": False,
            "prestart_immutable_binding_sha256": canonical_json_sha256(
                prestart_snapshot
            ),
            "postrun_immutable_binding_sha256": None,
            "prestart_equals_postrun": False,
            "immutable_binding": None,
            "validation_error": f"{type(exc).__name__}: {exc}",
        }
        if not path.exists():
            exclusive_write_json(path, failure_payload)
        return failure_payload


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if not isinstance(value, str):
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _find_metric(value: Any, names: Sequence[str]) -> float | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in names:
                number = _numeric(child)
                if number is not None:
                    return number
        for child in value.values():
            found = _find_metric(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_metric(child, names)
            if found is not None:
                return found
    return None


def query_rocm() -> dict[str, Any]:
    started = utc_now()
    monotonic_ns = time.perf_counter_ns()
    completed = subprocess.run(
        list(ROCM_COMMAND),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"rocm-smi telemetry failed: {completed.stderr.strip()}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"rocm-smi returned invalid JSON: {exc}") from exc
    return {
        "captured_at_utc": started,
        "captured_monotonic_ns": monotonic_ns,
        "gpu_use_percent": _find_metric(payload, ("GPU use (%)", "GPU use")),
        "vram_allocated_percent": _find_metric(
            payload, ("GPU Memory Allocated (VRAM%)", "GPU Memory Allocated")
        ),
        "memory_activity_percent": _find_metric(
            payload, ("GPU Memory Read/Write Activity (%)",)
        ),
        "graphics_package_power_w": _find_metric(
            payload, ("Average Graphics Package Power (W)",)
        ),
        "temperature_edge_c": _find_metric(payload, ("Temperature (Sensor edge) (C)",)),
        "temperature_junction_c": _find_metric(
            payload, ("Temperature (Sensor junction) (C)",)
        ),
        "temperature_memory_c": _find_metric(
            payload, ("Temperature (Sensor memory) (C)",)
        ),
        "command_exit_code": completed.returncode,
    }


def _parse_kfd_pids(text: str) -> list[int]:
    pids: set[int] = set()
    for line in text.splitlines():
        match = re.match(r"^\s*([1-9][0-9]*)\s+", line)
        if match:
            pids.add(int(match.group(1)))
        for explicit in re.finditer(
            r"(?:\"?PID\"?\s*[:=]\s*)([1-9][0-9]*)",
            line,
            flags=re.IGNORECASE,
        ):
            pids.add(int(explicit.group(1)))
    return sorted(pids)


def _proc_pid_exists(pid: int) -> bool:
    return (Path("/proc") / str(pid)).exists()


def _scan_open_kfd_fds(proc_root: Path = Path("/proc")) -> list[dict[str, Any]]:
    handles: list[dict[str, Any]] = []
    try:
        processes = list(proc_root.iterdir())
    except OSError as exc:
        raise VerificationError(
            f"cannot scan {proc_root} for /dev/kfd FDs: {exc}"
        ) from exc
    for process in processes:
        if not process.name.isdigit():
            continue
        fd_root = process / "fd"
        try:
            fds = list(fd_root.iterdir())
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise VerificationError(
                f"cannot prove global /dev/kfd FD absence at {fd_root}: {exc}"
            ) from exc
        except OSError:
            # A process can disappear between the /proc and fd walks.
            if not process.exists():
                continue
            raise
        for fd in fds:
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                raise VerificationError(
                    f"cannot inspect candidate KFD descriptor {fd}: {exc}"
                ) from exc
            if target == "/dev/kfd":
                handles.append({"pid": int(process.name), "fd": fd.name})
    return sorted(handles, key=lambda item: (int(item["pid"]), str(item["fd"])))


def clean_gpu_preflight() -> dict[str, Any]:
    completed = subprocess.run(
        ["rocm-smi", "--showpids"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise VerificationError(
            "clean GPU preflight failed because rocm-smi --showpids failed: "
            f"{completed.stderr.strip()}"
        )
    reported_pids = _parse_kfd_pids(completed.stdout)
    recognized_empty = "No KFD PIDs currently running" in completed.stdout
    if (
        not reported_pids
        and not recognized_empty
        and not ("KFD" in completed.stdout and "PID" in completed.stdout.upper())
    ):
        raise VerificationError("rocm-smi --showpids output was not recognized")
    live_pids = [pid for pid in reported_pids if _proc_pid_exists(pid)]
    stale_pids = [pid for pid in reported_pids if pid not in live_pids]
    open_kfd_fds = _scan_open_kfd_fds()
    if live_pids or open_kfd_fds:
        raise VerificationError(
            "clean GPU preflight found active KFD use: "
            f"live_reported_pids={live_pids}, open_kfd_fds={open_kfd_fds}"
        )
    first_sample = query_rocm()
    gpu_use = first_sample.get("gpu_use_percent")
    vram_use = first_sample.get("vram_allocated_percent")
    if (
        isinstance(gpu_use, bool)
        or not isinstance(gpu_use, (int, float))
        or not math.isfinite(float(gpu_use))
        or float(gpu_use) > PREFLIGHT_MAX_GPU_USE_PERCENT
        or isinstance(vram_use, bool)
        or not isinstance(vram_use, (int, float))
        or not math.isfinite(float(vram_use))
        or float(vram_use) > PREFLIGHT_MAX_VRAM_ALLOCATED_PERCENT
    ):
        raise VerificationError(
            "clean GPU preflight first telemetry sample is not idle: "
            f"gpu_use_percent={gpu_use!r}, vram_allocated_percent={vram_use!r}"
        )
    return {
        "checked_at_utc": utc_now(),
        "showpids_exit_code": completed.returncode,
        "showpids_stdout": completed.stdout,
        "showpids_stderr": completed.stderr,
        "reported_kfd_pids": reported_pids,
        "live_kfd_pids": live_pids,
        "stale_kfd_pids": stale_pids,
        "no_live_kfd_processes": True,
        "open_kfd_fds": open_kfd_fds,
        "global_dev_kfd_fd_scan_clear": True,
        "idle_thresholds": {
            "gpu_use_percent_max": PREFLIGHT_MAX_GPU_USE_PERCENT,
            "vram_allocated_percent_max": PREFLIGHT_MAX_VRAM_ALLOCATED_PERCENT,
        },
        "first_telemetry_idle": True,
        "first_telemetry_sample": first_sample,
    }


class TelemetrySampler:
    def __init__(self, path: Path, first_sample: Mapping[str, Any]) -> None:
        self.path = path
        self.first_sample = dict(first_sample)
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._handle: Any = None

    def _record(self, sample: Mapping[str, Any]) -> None:
        row = dict(sample)
        self.samples.append(row)
        append_jsonl(self._handle, row)

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("x", encoding="utf-8")
        self._record(self.first_sample)

        def loop() -> None:
            while not self._stop.wait(TELEMETRY_INTERVAL_SECONDS):
                try:
                    self._record(query_rocm())
                except Exception as exc:  # retained; formal gate later fails
                    self.errors.append(f"{type(exc).__name__}: {exc}")

        self._thread = threading.Thread(target=loop, name="rocm-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # Stop and join the background sampler before taking the final sample.
        # This makes raw timestamps strictly ordered while retaining a sample
        # captured after the formal challenge end marker.
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        if self._thread is not None and self._thread.is_alive():
            self.errors.append("telemetry sampler did not stop within 30 seconds")
        else:
            try:
                self._record(query_rocm())
            except Exception as exc:
                self.errors.append(f"{type(exc).__name__}: {exc}")
        if self._handle is not None:
            self._handle.close()

    def report(self, challenge_start_ns: int, challenge_end_ns: int) -> dict[str, Any]:
        times = [int(row["captured_monotonic_ns"]) for row in self.samples]
        gaps = [(b - a) / 1e9 for a, b in zip(times, times[1:])]
        fields = (
            "gpu_use_percent",
            "vram_allocated_percent",
            "memory_activity_percent",
            "graphics_package_power_w",
            "temperature_edge_c",
            "temperature_junction_c",
            "temperature_memory_c",
        )
        summary: dict[str, Any] = {"sample_count": len(self.samples)}
        for field in fields:
            values = [
                float(row[field]) for row in self.samples if row.get(field) is not None
            ]
            summary[field] = (
                {
                    "mean": statistics.fmean(values),
                    "minimum": min(values),
                    "maximum": max(values),
                    "median": statistics.median(values),
                    "samples": len(values),
                }
                if values
                else None
            )
        coverage = bool(
            times
            and times[0] <= challenge_start_ns
            and times[-1] >= challenge_end_ns
            and (not gaps or max(gaps) <= TELEMETRY_MAX_GAP_SECONDS)
            and not self.errors
        )
        return {
            "schema_version": TELEMETRY_SCHEMA,
            "sample_interval_seconds": TELEMETRY_INTERVAL_SECONDS,
            "max_allowed_gap_seconds": TELEMETRY_MAX_GAP_SECONDS,
            "challenge_started_monotonic_ns": challenge_start_ns,
            "challenge_ended_monotonic_ns": challenge_end_ns,
            "sample_count": len(self.samples),
            "max_observed_gap_seconds": max(gaps) if gaps else 0.0,
            "sampler_errors": list(self.errors),
            "coverage_valid": coverage,
            "summary": summary,
        }


def build_episode_command(
    spec: Mapping[str, Any], paths: Mapping[str, Path], python: str
) -> list[str]:
    entrypoint = (
        paths["baseline_entrypoint"]
        if spec["arm"] == "baseline"
        else paths["candidate_entrypoint"]
    )
    return [
        python,
        str(entrypoint),
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
        str(paths["output_root"] / str(spec["episode_path"])),
    ]


def _terminate_group(process: subprocess.Popen[str]) -> list[str]:
    actions: list[str] = []
    try:
        os.killpg(process.pid, signal.SIGTERM)
        actions.append("SIGTERM")
    except ProcessLookupError:
        return actions
    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
        return actions
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            actions.append("SIGKILL")
        except ProcessLookupError:
            pass
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
    return actions


def run_attempt(
    spec: Mapping[str, Any], paths: Mapping[str, Path], python: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    output_root = paths["output_root"]
    episode_path = output_root / str(spec["episode_path"])
    stdout_path = output_root / str(spec["stdout_path"])
    stderr_path = output_root / str(spec["stderr_path"])
    error_path = output_root / str(spec["error_path"])
    for path in (episode_path, stdout_path, stderr_path, error_path):
        if path.exists():
            raise VerificationError(
                f"creation-only attempt path already exists: {path}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)

    command = build_episode_command(spec, paths, python)
    source_root = paths[f"{spec['arm']}_root"]
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(source_root / "src"),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYOPENGL_PLATFORM": "egl",
            "MIOPEN_FIND_MODE": "FAST",
            "PATH": "/opt/venv/bin:" + environment.get("PATH", ""),
        }
    )
    started_utc = utc_now()
    started_ns = time.perf_counter_ns()
    timed_out = False
    termination_actions: list[str] = []
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    launch_error: str | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=source_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=EPISODE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            termination_actions = _terminate_group(process)
            stdout, stderr = process.communicate()
        exit_code = process.returncode
    except Exception as exc:
        launch_error = f"{type(exc).__name__}: {exc}"
        stderr = traceback.format_exc()
        exit_code = 127
    ended_ns = time.perf_counter_ns()
    ended_utc = utc_now()
    exclusive_write_text(stdout_path, stdout)
    exclusive_write_text(stderr_path, stderr)

    episode_exists = episode_path.is_file()
    parse_error: str | None = None
    row_errors: list[str] = []
    if episode_exists:
        try:
            payload = read_json_object(episode_path)
            derived = derive_episode_row(payload, spec)
            row_errors = list(derived["validation_errors"])
        except Exception as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    valid = bool(
        exit_code == 0
        and not timed_out
        and launch_error is None
        and episode_exists
        and parse_error is None
        and not row_errors
    )
    error_exists = not valid
    if error_exists:
        exclusive_write_json(
            error_path,
            {
                "schema_version": "look-twice.v8-contract-progress-challenge-attempt-error/v1",
                "schedule_index": spec["schedule_index"],
                "seed": spec["seed"],
                "arm": spec["arm"],
                "policy": spec["policy"],
                "command_exit_code": exit_code,
                "timed_out": timed_out,
                "termination_actions": termination_actions,
                "launch_error": launch_error,
                "parse_error": parse_error,
                "episode_validation_errors": row_errors,
                "retry_permitted": False,
            },
        )
    durably_persist_attempt_files((episode_path, stdout_path, stderr_path, error_path))
    record = {
        **{
            key: spec[key]
            for key in ("schedule_index", "seed", "arm", "policy", "profile")
        },
        "episode_path": spec["episode_path"],
        "stdout_path": spec["stdout_path"],
        "stderr_path": spec["stderr_path"],
        "error_path": spec["error_path"],
        "command": command,
        "started_at_utc": started_utc,
        "ended_at_utc": ended_utc,
        "started_monotonic_ns": started_ns,
        "ended_monotonic_ns": ended_ns,
        "wall_seconds": (ended_ns - started_ns) / 1e9,
        "command_exit_code": exit_code,
        "timed_out": timed_out,
        "termination_actions": termination_actions,
        "episode_exists": episode_exists,
        "episode_sha256": file_sha256(episode_path) if episode_exists else None,
        "stdout_sha256": file_sha256(stdout_path),
        "stderr_sha256": file_sha256(stderr_path),
        "error_exists": error_exists,
        "error_sha256": file_sha256(error_path) if error_exists else None,
        "attempt_integrity_valid": valid,
        "attempt_artifacts_fsynced": True,
        "retry_count": 0,
    }
    window = {
        **{
            key: spec[key]
            for key in ("schedule_index", "seed", "arm", "policy", "profile")
        },
        "started_monotonic_ns": started_ns,
        "ended_monotonic_ns": ended_ns,
        "command_exit_code": exit_code,
        "timed_out": timed_out,
    }
    return record, window


def _run_verifier(paths: Mapping[str, Path], mode: str, python: str) -> dict[str, Any]:
    command = [
        python,
        str(paths["verifier"]),
        "--output-root",
        str(paths["output_root"]),
        "--preregistration",
        str(paths["preregistration"]),
        "--runner",
        str(paths["runner"]),
        mode,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise VerificationError(f"verifier {mode} failed: {completed.stderr.strip()}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout.strip()}
    return {"command": command, "result": payload}


def write_checksum_index(output_root: Path) -> None:
    index_path = output_root / "SHA256SUMS"
    if index_path.exists():
        raise VerificationError("SHA256SUMS already exists")
    rows: list[str] = []
    for path in sorted(output_root.rglob("*")):
        if path.is_symlink():
            raise VerificationError(f"symlink forbidden in output: {path}")
        if path.is_file() and path.name not in {"SHA256SUMS", "VERIFICATION.json"}:
            relative = path.relative_to(output_root).as_posix()
            rows.append(f"{file_sha256(path)}  {relative}\n")
    exclusive_write_text(index_path, "".join(rows))


def run_formal(
    paths: Mapping[str, Path], design: Mapping[str, Any], python: str
) -> int:
    output_root = paths["output_root"]
    if output_root.exists():
        raise VerificationError(
            f"creation-only output root already exists (even empty): {output_root}"
        )
    preflight = clean_gpu_preflight()
    output_root.mkdir(parents=True, exist_ok=False)
    for arm in ("baseline", "candidate"):
        for kind in ("episodes", "logs", "errors"):
            (output_root / arm / kind).mkdir(parents=True, exist_ok=False)
    (output_root / "raw").mkdir(parents=True, exist_ok=False)

    prereg = read_json_object(paths["preregistration"])
    prestart_snapshot = immutable_binding_snapshot(paths, design)
    prestart = {
        "schema_version": PRESTART_SCHEMA,
        "bound_at_utc_before_first_episode": utc_now(),
        "bound_monotonic_ns_before_first_episode": time.perf_counter_ns(),
        "fresh_seed_opened_before_prestart": False,
        "no_episode_had_started": True,
        "baseline_root": str(paths["baseline_root"]),
        "candidate_root": str(paths["candidate_root"]),
        "checkpoint_path": str(paths["checkpoint"]),
        "vision_artifact_path": str(paths["vision_artifact"]),
        "go_artifact_path": str(paths["go_artifact"]),
        "purify_binary_path": str(paths["purify_binary"]),
        "preregistration_path": str(paths["preregistration"]),
        "preregistration_sha256": file_sha256(paths["preregistration"]),
        "runner_sha256": file_sha256(paths["runner"]),
        "verifier_sha256": file_sha256(paths["verifier"]),
        "python_executable": str(paths["python_executable"]),
        "python_identity": design["python_identity"],
        "commit_a": prereg["public_binding"]["commit_a"],
        "commit_b_observed": design["git_binding"]["commit_b_observed_clean_head"],
        "git_two_commit_proof": {
            "candidate_checkout_clean": design["git_binding"][
                "candidate_checkout_clean"
            ],
            "commit_a_strict_ancestor": design["git_binding"][
                "commit_a_strict_ancestor"
            ],
            "commit_b_direct_parent_is_commit_a": design["git_binding"][
                "commit_b_direct_parent_is_commit_a"
            ],
            "commit_count_a_to_b": design["git_binding"]["commit_count_a_to_b"],
            "changed_paths_a_to_b": design["git_binding"][
                "commit_a_to_b_changed_paths"
            ],
        },
        "public_remote_proof": {
            "remote_name": design["git_binding"]["public_remote_name"],
            "github_repository": design["git_binding"]["public_github_repository"],
            "access": design["git_binding"]["public_remote_access"],
            "remote_head_commit": design["git_binding"]["commit_b_observed_clean_head"],
            "remote_head_refs": design["git_binding"]["public_remote_head_refs"],
            "commit_b_public_remote_head_verified": design["git_binding"][
                "commit_b_public_remote_head_verified"
            ],
            "checked_at_utc": design["git_binding"]["public_remote_checked_at_utc"],
        },
        "frozen_identities": {
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "vision_artifact_sha256": EXPECTED_VISION_ARTIFACT_SHA256,
            "go_artifact_sha256": EXPECTED_GO_ARTIFACT_SHA256,
            "purify_binary_sha256": EXPECTED_PURIFY_SHA256,
            "baseline_runtime_tree_sha256": EXPECTED_RUNTIME_TREE_SHA256,
        },
        "baseline_runtime_closure": design["baseline_runtime_closure"],
        "candidate_source_closure": design["candidate_source_closure"],
        "candidate_source_files": design["preregistration"]["candidate_source_files"],
        "immutable_binding": prestart_snapshot,
        "immutable_binding_sha256": canonical_json_sha256(prestart_snapshot),
        "fixed_schedule": build_schedule(),
        "schedule_sha256": schedule_sha256(),
        "clean_gpu_preflight": preflight,
    }
    exclusive_write_json(output_root / "raw" / "PRESTART_BINDING.json", prestart)

    sampler = TelemetrySampler(
        output_root / "raw" / "ROCM_SAMPLES.jsonl",
        preflight["first_telemetry_sample"],
    )
    attempts: list[dict[str, Any]] = []
    challenge_started_ns = time.perf_counter_ns()
    sampler.start()
    attempts_handle = (output_root / "raw" / "ATTEMPTS.jsonl").open(
        "x", encoding="utf-8"
    )
    windows_handle = (output_root / "raw" / "EPISODE_WINDOWS.jsonl").open(
        "x", encoding="utf-8"
    )
    try:
        for spec in build_schedule():
            try:
                record, window = run_attempt(spec, paths, python)
            except Exception as exc:
                # Internal runner failure still consumes this cell exactly once.
                now_ns = time.perf_counter_ns()
                stdout_path = output_root / str(spec["stdout_path"])
                stderr_path = output_root / str(spec["stderr_path"])
                error_path = output_root / str(spec["error_path"])
                stdout_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_path.parent.mkdir(parents=True, exist_ok=True)
                error_path.parent.mkdir(parents=True, exist_ok=True)
                if not stdout_path.exists():
                    exclusive_write_text(stdout_path, "")
                if not stderr_path.exists():
                    exclusive_write_text(stderr_path, traceback.format_exc())
                if not error_path.exists():
                    exclusive_write_json(
                        error_path,
                        {
                            "schema_version": "look-twice.v8-contract-progress-challenge-attempt-error/v1",
                            "schedule_index": spec["schedule_index"],
                            "seed": spec["seed"],
                            "arm": spec["arm"],
                            "policy": spec["policy"],
                            "internal_runner_error": f"{type(exc).__name__}: {exc}",
                            "retry_permitted": False,
                        },
                    )
                episode_path = output_root / str(spec["episode_path"])
                durably_persist_attempt_files(
                    (episode_path, stdout_path, stderr_path, error_path)
                )
                record = {
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
                    # No argv is claimed when the runner itself failed before it
                    # could establish a normal child-attempt record.
                    "command": [],
                    "started_at_utc": utc_now(),
                    "ended_at_utc": utc_now(),
                    "started_monotonic_ns": now_ns,
                    "ended_monotonic_ns": now_ns,
                    "wall_seconds": 0.0,
                    "command_exit_code": 127,
                    "timed_out": False,
                    "termination_actions": [],
                    "episode_exists": episode_path.is_file(),
                    "episode_sha256": file_sha256(episode_path)
                    if episode_path.is_file()
                    else None,
                    "stdout_sha256": file_sha256(stdout_path),
                    "stderr_sha256": file_sha256(stderr_path),
                    "error_exists": True,
                    "error_sha256": file_sha256(error_path),
                    "attempt_integrity_valid": False,
                    "attempt_artifacts_fsynced": True,
                    "retry_count": 0,
                }
                window = {
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
                    "started_monotonic_ns": now_ns,
                    "ended_monotonic_ns": now_ns,
                    "command_exit_code": 127,
                    "timed_out": False,
                }
            attempts.append(record)
            append_jsonl(attempts_handle, record)
            append_jsonl(windows_handle, window)
            print(
                f"[{record['schedule_index'] + 1:02d}/{EPISODE_COUNT}] "
                f"seed={record['seed']} arm={record['arm']} "
                f"exit={record['command_exit_code']} valid={record['attempt_integrity_valid']}",
                flush=True,
            )
    finally:
        attempts_handle.close()
        windows_handle.close()
        challenge_ended_ns = time.perf_counter_ns()
        sampler.stop()

    telemetry = sampler.report(challenge_started_ns, challenge_ended_ns)
    exclusive_write_json(output_root / "ROCM_TELEMETRY.json", telemetry)
    if not attempts:
        raise VerificationError("formal challenge retained no attempt records")
    postrun = write_postrun_binding(
        paths,
        prestart_snapshot,
        attempts_completed=len(attempts),
        last_attempt_ended_monotonic_ns=int(attempts[-1]["ended_monotonic_ns"]),
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "formal_result_eligible": False,
        "created_at_utc": utc_now(),
        "preregistration_sha256": file_sha256(paths["preregistration"]),
        "runner_sha256": file_sha256(paths["runner"]),
        "verifier_sha256": file_sha256(paths["verifier"]),
        "postrun_binding_sha256": file_sha256(
            output_root / "raw" / "POSTRUN_BINDING.json"
        ),
        "postrun_revalidation_passed": postrun["revalidation_passed"],
        "schedule_sha256": schedule_sha256(),
        "fixed_schedule": build_schedule(),
        "attempts": attempts,
        "attempt_accounting": {
            "expected": EPISODE_COUNT,
            "attempted": len(attempts),
            "valid": sum(bool(row["attempt_integrity_valid"]) for row in attempts),
            "timed_out": sum(bool(row["timed_out"]) for row in attempts),
            "retry_count": 0,
            "seed_substitutions": 0,
            "early_stopped": len(attempts) != EPISODE_COUNT,
        },
        "source_roots": {
            "baseline": str(paths["baseline_root"]),
            "candidate": str(paths["candidate_root"]),
        },
        "fixed_runtime": {
            "runtime": "genesis-amd",
            "motion_backend": "kinematic",
            "device": "cuda:0",
            "profile": PROFILE,
            "seed_range": [SEED_START, SEED_END],
            "episode_timeout_seconds": EPISODE_TIMEOUT_SECONDS,
        },
    }
    exclusive_write_json(output_root / "RUN_MANIFEST.json", manifest)

    _run_verifier(paths, "--write-report", python)
    write_checksum_index(output_root)
    _run_verifier(paths, "--write-verification", python)
    _run_verifier(paths, "--require-final", python)
    final = read_json_object(output_root / "VERIFICATION.json")
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "promotion_pass": final.get("promotion_pass"),
                "attempts": len(attempts),
                "no_retry": True,
            },
            indent=2,
        )
    )
    return 0 if final.get("promotion_pass") is True else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--baseline-root", type=Path, default=default_root)
    parser.add_argument("--candidate-root", type=Path, default=default_root)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--vision-conformal-artifact", type=Path)
    parser.add_argument("--go-conformal-artifact", type=Path)
    parser.add_argument("--purify-binary", type=Path)
    parser.add_argument("--identity-manifest", type=Path)
    parser.add_argument(
        "--preregistration", type=Path, default=default_root / PREREG_RELATIVE
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=default_root.parent / DEFAULT_OUTPUT_BASENAME,
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = resolve_paths(args)
    try:
        design = verify_design(paths, formal=not args.dry_run)
        if args.dry_run:
            if paths["output_root"].exists():
                # Dry run never mutates it, but surfaces creation-only status.
                output_status = "exists_and_would_be_rejected_in_formal_mode"
            else:
                output_status = "absent_and_creation_only_eligible"
            print(
                json.dumps(
                    {
                        "schema_version": "look-twice.v8-contract-progress-challenge-dry-run/v1",
                        "dry_run": True,
                        "no_seed_executed": True,
                        "no_output_created": True,
                        "no_rocm_queried": True,
                        "no_checkpoint_loaded": True,
                        "seed_range_not_opened": [SEED_START, SEED_END],
                        "schedule_sha256": design["schedule_sha256"],
                        "episode_count": EPISODE_COUNT,
                        "output_status": output_status,
                        "design": design,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        return run_formal(paths, design, str(paths["python_executable"]))
    except (OSError, subprocess.SubprocessError, VerificationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
