#!/usr/bin/env python3
"""Verify the archived V8 locked-input pack without running model inference.

This verifier reads archive metadata and JSON records only. It never extracts
the archive, loads the V8 checkpoint, imports PyTorch, or executes an episode.
The resulting manifest is an additive publication record; it does not replace
or modify the permanent one-shot locked report.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import hashlib


ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_NAME = "v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz"
ARCHIVE_SHA256 = "0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba"
ARCHIVE_BYTES = 1_019_307_579
SIDECAR_NAME = (
    "v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.sidecar.json"
)
SIDECAR_SHA256 = "eaecfd450b807183aa0b26fad1cb6fc792202eda54d3abbcd8332f6373a84766"
SIDECAR_BYTES = 678
ARCHIVE_CREATED_UTC = "20260720T120737Z"

LOCKED_OPEN_RELATIVE = (
    "release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_OPENED.json"
)
LOCKED_OPEN_SHA256 = "7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14"
LOCKED_REPORT_RELATIVE = (
    "release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_REPORT.json"
)
LOCKED_REPORT_SHA256 = (
    "5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb"
)

REQUIRED_ARRAY_KEYS = (
    "rgb",
    "depth_noisy",
    "depth_clean",
    "seg_entity",
    "obstacle_mask",
    "corridor_mask",
)
FORBIDDEN_LOCATION_TOKENS = (
    "/workspace/",
    "/Users/",
    "file://",
    "root@",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class PackExpectations:
    archive_name: str
    archive_sha256: str
    archive_bytes: int
    sidecar_name: str
    sidecar_sha256: str
    sidecar_bytes: int
    created_utc: str
    split: str
    profile: str
    seed_lo: int
    seed_hi: int
    samples_per_seed: int
    label_counts: Mapping[str, int]

    @property
    def n_seeds(self) -> int:
        return self.seed_hi - self.seed_lo + 1

    @property
    def n_samples(self) -> int:
        return self.n_seeds * self.samples_per_seed


PRODUCTION_EXPECTATIONS = PackExpectations(
    archive_name=ARCHIVE_NAME,
    archive_sha256=ARCHIVE_SHA256,
    archive_bytes=ARCHIVE_BYTES,
    sidecar_name=SIDECAR_NAME,
    sidecar_sha256=SIDECAR_SHA256,
    sidecar_bytes=SIDECAR_BYTES,
    created_utc=ARCHIVE_CREATED_UTC,
    split="locked_test",
    profile="independent-noise",
    seed_lo=102100,
    seed_hi=102499,
    samples_per_seed=8,
    label_counts={"blocked": 1560, "clear": 1640},
)


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


def _safe_relative(value: str) -> bool:
    if not value or "\\" in value or WINDOWS_ABSOLUTE_RE.match(value):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def _walk_strings(value: Any, pointer: str = "$") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_walk_strings(item, f"{pointer}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_strings(item, f"{pointer}[{index}]"))
    elif isinstance(value, str):
        rows.append((pointer, value))
    return rows


def _json_from_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo, errors: list[str]
) -> dict[str, Any] | None:
    handle = archive.extractfile(member)
    if handle is None:
        errors.append(f"unreadable_json_member:{member.name}")
        return None
    try:
        text = handle.read().decode("utf-8")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid_json:{member.name}:{exc.__class__.__name__}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"json_not_object:{member.name}")
        return None
    for pointer, value in _walk_strings(payload):
        if any(token in value for token in FORBIDDEN_LOCATION_TOKENS):
            errors.append(f"forbidden_location:{member.name}:{pointer}")
        if value.startswith("/") or WINDOWS_ABSOLUTE_RE.match(value):
            errors.append(f"absolute_json_path:{member.name}:{pointer}")
    return payload


def _validate_sidecar(
    sidecar_path: Path,
    archive_path: Path,
    expected: PackExpectations,
    errors: list[str],
) -> dict[str, Any]:
    if sidecar_path.name != expected.sidecar_name:
        errors.append("sidecar_filename_mismatch")
    if sidecar_path.stat().st_size != expected.sidecar_bytes:
        errors.append("sidecar_size_mismatch")
    if file_sha256(sidecar_path) != expected.sidecar_sha256:
        errors.append("sidecar_sha256_mismatch")
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"sidecar_invalid_json:{exc.__class__.__name__}")
        return {}
    if not isinstance(sidecar, dict):
        errors.append("sidecar_not_object")
        return {}

    checks = {
        "sidecar_schema": sidecar.get("schema_version")
        == "look-twice.v8-eval-evidence-pack/v1",
        "sidecar_split": sidecar.get("split") == expected.split,
        "sidecar_n_seeds": sidecar.get("n_seeds") == expected.n_seeds,
        "sidecar_archive": sidecar.get("archive") == expected.archive_name,
        "sidecar_archive_bytes": sidecar.get("archive_bytes") == expected.archive_bytes,
        "sidecar_archive_sha256": sidecar.get("archive_sha256")
        == expected.archive_sha256,
        "sidecar_created_utc": sidecar.get("created_utc") == expected.created_utc,
        "sidecar_locked_opened_false": sidecar.get("locked_opened") is False,
        "sidecar_locked_analyzed_false": sidecar.get("locked_analyzed") is False,
        "sidecar_source_relative": isinstance(sidecar.get("source_path"), str)
        and _safe_relative(str(sidecar.get("source_path"))),
        "archive_basename": archive_path.name == expected.archive_name,
        "archive_bytes": archive_path.stat().st_size == expected.archive_bytes,
        "archive_sha256": file_sha256(archive_path) == expected.archive_sha256,
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    return sidecar


def verify_input_pack(
    archive_path: Path,
    sidecar_path: Path,
    expected: PackExpectations = PRODUCTION_EXPECTATIONS,
) -> dict[str, Any]:
    """Return a path-neutral verification manifest for one input archive."""
    errors: list[str] = []
    if not archive_path.is_file():
        return {"passed": False, "errors": ["archive_missing"]}
    if not sidecar_path.is_file():
        return {"passed": False, "errors": ["sidecar_missing"]}

    sidecar = _validate_sidecar(sidecar_path, archive_path, expected, errors)
    member_names: set[str] = set()
    member_counts: Counter[str] = Counter()
    meta_by_path: dict[str, dict[str, Any]] = {}
    complete_by_seed: dict[int, dict[str, Any]] = {}
    samples_by_seed: dict[int, int] = defaultdict(int)
    labels: Counter[str] = Counter()
    commits: Counter[str] = Counter()
    required_paths: set[str] = set()
    json_count = 0

    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        errors.append(f"archive_open_failed:{exc.__class__.__name__}")
        archive = None

    if archive is not None:
        with archive:
            for member in archive:
                name = member.name
                if not _safe_relative(name):
                    errors.append(f"unsafe_member_path:{name}")
                if name in member_names:
                    errors.append(f"duplicate_member:{name}")
                member_names.add(name)
                if member.issym() or member.islnk():
                    errors.append(f"link_member_forbidden:{name}")
                    continue
                if not (member.isfile() or member.isdir()):
                    errors.append(f"special_member_forbidden:{name}")
                    continue
                if member.isdir():
                    member_counts["directories"] += 1
                    continue
                member_counts["files"] += 1
                if not name.startswith(f"{expected.split}/"):
                    errors.append(f"member_outside_split:{name}")

                complete_match = re.fullmatch(
                    rf"{re.escape(expected.split)}/_COMPLETE__(\d+)\.json", name
                )
                meta_match = re.fullmatch(
                    rf"{re.escape(expected.split)}/seed_(\d+)/.+__meta\.json", name
                )
                array_match = re.fullmatch(
                    rf"{re.escape(expected.split)}/seed_(\d+)/.+__(rgb|depth_noisy|"
                    r"depth_clean|seg_entity|obstacle_mask|corridor_mask)\.npy",
                    name,
                )

                if complete_match:
                    member_counts["complete_markers"] += 1
                    json_count += 1
                    payload = _json_from_member(archive, member, errors)
                    if payload is not None:
                        seed = int(complete_match.group(1))
                        if seed in complete_by_seed:
                            errors.append(f"duplicate_complete_seed:{seed}")
                        complete_by_seed[seed] = payload
                    continue
                if meta_match:
                    member_counts["metadata_records"] += 1
                    json_count += 1
                    payload = _json_from_member(archive, member, errors)
                    if payload is not None:
                        seed = int(meta_match.group(1))
                        meta_by_path[name] = payload
                        samples_by_seed[seed] += 1
                        label = str(payload.get("offline_label") or "")
                        labels[label] += 1
                        commits[str(payload.get("git_commit") or "missing")] += 1
                        if (
                            payload.get("schema_version")
                            != "look-twice.v8-spatial-rgbd/v1"
                        ):
                            errors.append(f"meta_schema:{name}")
                        if payload.get("split") != expected.split:
                            errors.append(f"meta_split:{name}")
                        if payload.get("profile") != expected.profile:
                            errors.append(f"meta_profile:{name}")
                        if payload.get("seed") != seed:
                            errors.append(f"meta_seed:{name}")
                        if label not in {"clear", "blocked"}:
                            errors.append(f"meta_label:{name}")
                        offline_blocked = payload.get("offline_blocked")
                        if (
                            not isinstance(offline_blocked, bool)
                            or (label == "blocked") != offline_blocked
                        ):
                            errors.append(f"meta_label_consistency:{name}")
                        if payload.get("world_alignment_passed") is not True:
                            errors.append(f"meta_world_alignment:{name}")
                        if payload.get("train_eligible") is not True:
                            errors.append(f"meta_train_eligible:{name}")
                        generation = payload.get("generation_config") or {}
                        if not isinstance(generation, dict):
                            errors.append(f"meta_generation_config:{name}")
                            generation = {}
                        if generation.get("split") != expected.split:
                            errors.append(f"generation_split:{name}")
                        if generation.get("seed") != seed:
                            errors.append(f"generation_seed:{name}")
                        if generation.get("profile") != expected.profile:
                            errors.append(f"generation_profile:{name}")
                        paths = payload.get("paths") or {}
                        if not isinstance(paths, dict):
                            errors.append(f"meta_paths:{name}")
                            paths = {}
                        for key in REQUIRED_ARRAY_KEYS:
                            relative = paths.get(key)
                            stored_sha = paths.get(f"{key}_sha256")
                            if not isinstance(relative, str) or not _safe_relative(
                                relative
                            ):
                                errors.append(f"meta_path_{key}:{name}")
                            else:
                                required_paths.add(relative)
                                expected_prefix = f"{expected.split}/seed_{seed}/"
                                if not relative.startswith(expected_prefix):
                                    errors.append(f"meta_path_seed_scope_{key}:{name}")
                            if not isinstance(
                                stored_sha, str
                            ) or not SHA256_RE.fullmatch(stored_sha):
                                errors.append(f"meta_sha_{key}:{name}")
                    continue
                if array_match:
                    member_counts[f"array_{array_match.group(2)}"] += 1
                    continue
                errors.append(f"unexpected_file:{name}")

    expected_seeds = set(range(expected.seed_lo, expected.seed_hi + 1))
    if set(samples_by_seed) != expected_seeds:
        errors.append("metadata_seed_set_mismatch")
    if set(complete_by_seed) != expected_seeds:
        errors.append("complete_seed_set_mismatch")
    for seed in sorted(expected_seeds):
        if samples_by_seed.get(seed, 0) != expected.samples_per_seed:
            errors.append(f"samples_per_seed:{seed}")
        complete = complete_by_seed.get(seed)
        if complete is None:
            continue
        if complete.get("seed") != seed:
            errors.append(f"complete_seed:{seed}")
        if complete.get("split") != expected.split:
            errors.append(f"complete_split:{seed}")
        if complete.get("profile") != expected.profile:
            errors.append(f"complete_profile:{seed}")
        if complete.get("n_samples") != expected.samples_per_seed:
            errors.append(f"complete_n_samples:{seed}")
        rows = complete.get("samples")
        if not isinstance(rows, list) or len(rows) != expected.samples_per_seed:
            errors.append(f"complete_samples:{seed}")
            continue
        referenced = [row.get("meta") for row in rows if isinstance(row, dict)]
        if len(referenced) != len(set(referenced)):
            errors.append(f"complete_duplicate_meta:{seed}")
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"complete_sample_not_object:{seed}")
                continue
            meta_name = row.get("meta")
            if not isinstance(meta_name, str) or meta_name not in meta_by_path:
                errors.append(f"complete_meta_missing:{seed}")
                continue
            meta = meta_by_path[meta_name]
            for field in ("offline_label", "corridor_id", "viewpoint"):
                if row.get(field) != meta.get(field):
                    errors.append(f"complete_meta_{field}:{seed}:{meta_name}")

    for path in sorted(required_paths - member_names):
        errors.append(f"required_array_missing:{path}")

    expected_counts = {
        "directories": expected.n_seeds + 1,
        "files": expected.n_samples * len(REQUIRED_ARRAY_KEYS)
        + expected.n_samples
        + expected.n_seeds,
        "complete_markers": expected.n_seeds,
        "metadata_records": expected.n_samples,
        **{f"array_{key}": expected.n_samples for key in REQUIRED_ARRAY_KEYS},
    }
    for key, value in expected_counts.items():
        if member_counts.get(key, 0) != value:
            errors.append(f"member_count_{key}:{member_counts.get(key, 0)}!={value}")
    if dict(labels) != dict(expected.label_counts):
        errors.append("label_counts_mismatch")
    if json_count != expected.n_samples + expected.n_seeds:
        errors.append("json_count_mismatch")

    errors = sorted(set(errors))
    result: dict[str, Any] = {
        "schema_version": "look-twice.v8-locked-input-pack-manifest/v1",
        "status": "passed" if not errors else "failed",
        "passed": not errors,
        "evidence_class": "pre-open locked inputs and labels only",
        "source_pack": {
            "archive": expected.archive_name,
            "archive_bytes": expected.archive_bytes,
            "archive_sha256": expected.archive_sha256,
            "sidecar": expected.sidecar_name,
            "sidecar_bytes": expected.sidecar_bytes,
            "sidecar_sha256": expected.sidecar_sha256,
            "declared_created_utc": expected.created_utc,
            "declared_source_path": sidecar.get("source_path"),
            "declared_locked_opened": sidecar.get("locked_opened"),
            "declared_locked_analyzed": sidecar.get("locked_analyzed"),
        },
        "contents": {
            "split": expected.split,
            "profile": expected.profile,
            "seed_range": [expected.seed_lo, expected.seed_hi],
            "seeds": expected.n_seeds,
            "samples_per_seed": expected.samples_per_seed,
            "metadata_records": len(meta_by_path),
            "label_counts": dict(sorted(labels.items())),
            "json_files_checked": json_count,
            "member_counts": dict(sorted(member_counts.items())),
            "generation_git_commits": dict(sorted(commits.items())),
        },
        "path_hygiene": {
            "archive_extracted": False,
            "all_member_paths_relative": not any(
                error.startswith("unsafe_member_path:") for error in errors
            ),
            "absolute_machine_locations_found": sum(
                error.startswith(("forbidden_location:", "absolute_json_path:"))
                for error in errors
            ),
            "links_or_special_members_found": sum(
                error.startswith(
                    ("link_member_forbidden:", "special_member_forbidden:")
                )
                for error in errors
            ),
        },
        "evidence_boundary": {
            "contains_runtime_legal_inputs": True,
            "contains_offline_labels_and_train_only_label_artifacts": True,
            "contains_original_one_shot_per_sample_predictions": False,
            "contains_24_locked_live_raw_episodes": False,
            "recomputes_locked_aggregate": False,
            "runs_model_inference": False,
            "runs_genesis_or_robot_episode": False,
            "opens_or_reruns_locked_test": False,
            "changes_model_calibration_or_thresholds": False,
            "changes_permanent_locked_report": False,
        },
        "errors": errors,
    }
    result["manifest_sha256"] = canonical_sha256(result)
    return result


def _parse_archive_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def add_formal_result_binding(manifest: dict[str, Any]) -> None:
    errors = list(manifest.get("errors") or [])
    open_path = ROOT / LOCKED_OPEN_RELATIVE
    report_path = ROOT / LOCKED_REPORT_RELATIVE
    if not open_path.is_file():
        errors.append("locked_open_seal_missing")
        opened_at = None
    elif file_sha256(open_path) != LOCKED_OPEN_SHA256:
        errors.append("locked_open_seal_sha256_mismatch")
        opened_at = None
    else:
        opened = json.loads(open_path.read_text(encoding="utf-8"))
        opened_at = opened.get("opened_at_utc")
    if not report_path.is_file():
        errors.append("locked_report_missing")
    elif file_sha256(report_path) != LOCKED_REPORT_SHA256:
        errors.append("locked_report_sha256_mismatch")

    created = _parse_archive_time(PRODUCTION_EXPECTATIONS.created_utc)
    delta_seconds: int | None = None
    if isinstance(opened_at, str):
        try:
            opened_dt = datetime.fromisoformat(opened_at)
            delta_seconds = int((opened_dt - created).total_seconds())
            if delta_seconds <= 0:
                errors.append("archive_not_declared_before_locked_open")
        except ValueError:
            errors.append("locked_open_time_invalid")
    else:
        errors.append("locked_open_time_missing")

    manifest["formal_result_binding"] = {
        "locked_open_seal": {
            "path": LOCKED_OPEN_RELATIVE,
            "sha256": LOCKED_OPEN_SHA256,
            "opened_at_utc": opened_at,
        },
        "permanent_locked_report": {
            "path": LOCKED_REPORT_RELATIVE,
            "sha256": LOCKED_REPORT_SHA256,
            "modified_by_this_verification": False,
        },
        "declared_archive_created_before_open": bool(
            delta_seconds is not None and delta_seconds > 0
        ),
        "declared_lead_time_seconds": delta_seconds,
        "chronology_limit": (
            "The sidecar timestamp is first-party provenance, not an external "
            "timestamp authority; the archive is being publicly bound after the run."
        ),
    }
    manifest["errors"] = sorted(set(errors))
    manifest["passed"] = not manifest["errors"]
    manifest["status"] = "passed" if manifest["passed"] else "failed"
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = canonical_sha256(manifest)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify and print the manifest without writing --output.",
    )
    args = parser.parse_args()
    sidecar = args.sidecar or args.archive.with_name(SIDECAR_NAME)
    manifest = verify_input_pack(args.archive, sidecar)
    add_formal_result_binding(manifest)
    if manifest["passed"] and not args.check_only:
        _atomic_write_json(args.output, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if manifest["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
