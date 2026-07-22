#!/usr/bin/env python3
"""Create the immutable import boundary for the frozen V8 release candidate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import canonical_sha256, file_sha256  # noqa: E402

GUARDED = (
    "src/look_twice_v7.py",
    "src/purify_bridge.py",
    "src/v6_episode.py",
    "src/v7_episode.py",
    "src/v7_vision_claims.py",
    "src/v8_claims.py",
    "src/v8_corridor_projection.py",
    "src/v8_go_fusion_claims.py",
    "src/v8_runtime_calibration.py",
    "src/v8_seg_v3_model.py",
    "src/v8_spatial_model.py",
    "src/v8_spatial_runtime.py",
    "release/v8-frozen/artifacts/purify-robotics-core-linux",
    "release/v8-frozen/results/V8_IDENTITY_FREEZE_MANIFEST.json",
    "release/v8-frozen/results/V8_RUNTIME_FROZEN.json",
    "release/v8-frozen/results/calibration_vision/conformal_artifact.json",
    "release/v8-frozen/results/calibration_go_fusion_v3/conformal_artifact.json",
    "release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_REPORT.json",
    "release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_OPENED.json",
    "release/v8-frozen/episodes/active__independent-noise__105400.json",
    "release/v8-frozen/episodes/passive__independent-noise__105400.json",
)


def main() -> int:
    rows = []
    for relative in GUARDED:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    identity = json.loads(
        (ROOT / "release/v8-frozen/results/V8_IDENTITY_FREEZE_MANIFEST.json").read_text()
    )["V8_RUNTIME_FROZEN"]
    manifest = {
        "schema_version": "look-twice.v8-frozen-import/v1",
        "candidate_id": "v8-frozen",
        "policy": "V9 may add an adapter; it may not alter these files.",
        "frozen_identity": identity,
        "guarded_files": rows,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    output = ROOT / "release/V8_FROZEN_IMPORT_MANIFEST.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"guarded_files": len(rows), "manifest_sha256": manifest["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
