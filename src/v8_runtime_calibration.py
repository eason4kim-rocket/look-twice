"""V8 runtime calibration identity + Go CalibrationArtifact conversion.

Single source of truth for the runtime calibration ID shared by:
  - V8 Vision Claims
  - Python CorridorContract.calibration_id
  - Go Context.SensorVersion
  - Go CalibrationArtifact.sensor_versions

Format:
  look-twice-v8-spatial:<conformal_artifact_sha256 first 16 hex chars>
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def v8_runtime_calibration_id(conformal_artifact_sha256: str) -> str:
    sha = str(conformal_artifact_sha256 or "").strip().lower()
    if len(sha) < 16 or any(c not in "0123456789abcdef" for c in sha[:16]):
        raise ValueError(f"invalid conformal artifact sha for runtime cal id: {sha!r}")
    return f"look-twice-v8-spatial:{sha[:16]}"


def load_v8_conformal_raw(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"conformal artifact must be object: {p}")
    # Prefer stamped artifact_sha256; fall back to content hash of file bytes.
    art_sha = str(raw.get("artifact_sha256") or "").strip().lower()
    if len(art_sha) != 64:
        art_sha = file_sha256(p)
        raw = dict(raw)
        raw["artifact_sha256"] = art_sha
    return raw


def class_quantiles_from_v8_thresholds(thr: Mapping[str, Any]) -> dict[str, float]:
    """Map V8 spatial thresholds → Go class_quantiles.

    Go conformalPredictionSet:
      clear  if p_blocked <= quantiles[\"clear\"]
      blocked if (1 - p_blocked) <= quantiles[\"blocked\"]
              i.e. p_blocked >= 1 - quantiles[\"blocked\"]

    V8 SpatialConformal:
      clear  if p_blocked <= include_clear_if_p_blocked_le
      blocked if p_blocked >= include_blocked_if_p_blocked_ge
    """
    q_clear = thr.get("include_clear_if_p_blocked_le", thr.get("q_clear"))
    if "include_blocked_if_p_blocked_ge" in thr:
        q_blocked = 1.0 - float(thr["include_blocked_if_p_blocked_ge"])
    else:
        q_blocked = thr.get("q_blocked")
    if q_clear is None or q_blocked is None:
        raise ValueError(f"V8 thresholds missing clear/blocked quantiles: {dict(thr)}")
    qc = float(q_clear)
    qb = float(q_blocked)
    # Numerical clamp to (0,1] for Go validator; keep extremely small values.
    qc = min(1.0, max(qc, 1e-12))
    qb = min(1.0, max(qb, 1e-12))
    return {"clear": qc, "blocked": qb}


def resolve_dataset_sha256(raw: Mapping[str, Any], *, repo_root: Path | None = None) -> str:
    """Prefer explicit fields, else dataset finalize manifest SHA, else artifact sha."""
    for key in (
        "dataset_sha256",
        "manifest_all_sha256",
        "dataset_manifest_sha256",
    ):
        v = raw.get(key)
        if isinstance(v, str) and len(v) == 64:
            return v.lower()
    thr = raw.get("thresholds") if isinstance(raw.get("thresholds"), dict) else {}
    for key in ("dataset_sha256", "manifest_all_sha256"):
        v = thr.get(key) if isinstance(thr, dict) else None
        if isinstance(v, str) and len(v) == 64:
            return v.lower()
    if repo_root is not None:
        cand = repo_root / "results" / "v8-spatial-dataset-v1" / "dataset_sha256.json"
        if cand.is_file():
            try:
                d = json.loads(cand.read_text(encoding="utf-8"))
                m = d.get("manifest_all_sha256")
                if isinstance(m, str) and len(m) == 64:
                    return m.lower()
            except Exception:
                pass
    # Last resort: bind to conformal artifact content identity (not a smoke placeholder).
    return str(raw["artifact_sha256"]).lower()


def seed_ranges_from_v8_artifact(raw: Mapping[str, Any]) -> list[dict[str, int]]:
    sr = raw.get("calibration_seed_range") or raw.get("seed_range")
    if isinstance(sr, (list, tuple)) and len(sr) == 2:
        return [{"start": int(sr[0]), "end": int(sr[1])}]
    if isinstance(raw.get("seed_ranges"), list) and raw["seed_ranges"]:
        out = []
        for item in raw["seed_ranges"]:
            if isinstance(item, dict) and "start" in item and "end" in item:
                out.append({"start": int(item["start"]), "end": int(item["end"])})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out.append({"start": int(item[0]), "end": int(item[1])})
        if out:
            return out
    return [{"start": 0, "end": 0}]


def go_calibration_from_v8_artifact(
    path: str | Path,
    *,
    profile: str | None = None,
    repo_root: Path | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return (runtime_calibration_id, go_calibration_wire, raw_artifact)."""
    raw = load_v8_conformal_raw(path)
    art_sha = str(raw["artifact_sha256"]).lower()
    cal_id = v8_runtime_calibration_id(art_sha)
    thr = raw.get("thresholds") or {}
    if not isinstance(thr, dict):
        thr = {}
    quantiles = class_quantiles_from_v8_thresholds(thr)
    coverage = float(raw.get("coverage_target") or thr.get("coverage_target") or 0.95)
    alpha = max(0.0, min(1.0, 1.0 - coverage))
    profiles = [
        "independent-noise",
        "shared-noise",
        "correlated-noise",
        "default",
    ]
    if profile and str(profile) not in profiles:
        profiles.append(str(profile))
    ckpt = str(raw.get("checkpoint_sha256") or "")
    go_cal = {
        "schema_version": "purify.robotics.calibration.v1",
        "artifact_id": f"v8-spatial-conformal:{art_sha[:16]}",
        "alpha": alpha,
        "class_quantiles": quantiles,
        "applicable_profiles": profiles,
        "min_noise_intensity": 0.0,
        "max_noise_intensity": 1.0,
        "sensor_versions": [cal_id],
        "git_commit": str(raw.get("git_commit") or f"ckpt:{(ckpt[:12] if ckpt else 'unknown')}"),
        "dataset_sha256": resolve_dataset_sha256(raw, repo_root=repo_root),
        "seed_ranges": seed_ranges_from_v8_artifact(raw),
        # Audit-only extras (ignored by Go JSON decode if unknown — kept out of wire
        # to avoid schema issues; attach via sidecar if needed).
    }
    return cal_id, go_cal, raw


def filter_claims_for_corridor_go(
    claim_wires: list[dict[str, Any]],
    *,
    corridor_id: str,
    predicate: str = "carrier_traversable",
) -> list[dict[str, Any]]:
    """Keep claims matching corridor fact_id/predicate/scope.region_id.

    Intra-corridor conflicts (clear vs blocked) are intentionally retained.
    Claims for other corridors are dropped before Go evaluation.
    """
    fact_id = f"region:{corridor_id}"
    out: list[dict[str, Any]] = []
    for w in claim_wires:
        if not isinstance(w, dict):
            continue
        if str(w.get("fact_id") or "") != fact_id:
            continue
        if str(w.get("predicate") or "") != predicate:
            continue
        scope = w.get("scope") or {}
        region = ""
        if isinstance(scope, dict):
            region = str(scope.get("region_id") or "")
        if region and region != corridor_id:
            continue
        out.append(w)
    return out


__all__ = (
    "v8_runtime_calibration_id",
    "load_v8_conformal_raw",
    "class_quantiles_from_v8_thresholds",
    "go_calibration_from_v8_artifact",
    "filter_claims_for_corridor_go",
    "file_sha256",
)
