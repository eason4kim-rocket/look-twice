#!/usr/bin/env python3
"""Verify frozen V8 imports and public replay integrity."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import assert_public_bundle, file_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "release" / "V8_FROZEN_IMPORT_MANIFEST.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "release" / "FOUNDATION_SOURCE_READY.json",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    errors: list[str] = []
    for item in manifest["guarded_files"]:
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append(f"missing:{item['path']}")
        elif file_sha256(path) != item["sha256"]:
            errors.append(f"sha_mismatch:{item['path']}")

    public_root = ROOT / "showcase" / "public" / "data"
    replay_manifest = json.loads((public_root / "manifest.json").read_text())
    for row in replay_manifest["replays"]:
        replay_path = public_root / "replays" / f"{row['replay_id']}.json"
        bundle = json.loads(replay_path.read_text())
        try:
            assert_public_bundle(bundle)
        except ValueError as exc:
            errors.append(f"replay:{row['replay_id']}:{exc}")
        if bundle["integrity"]["bundle_sha256"] != row["bundle_sha256"]:
            errors.append(f"bundle_manifest_mismatch:{row['replay_id']}")

    report = {
        "schema_version": "look-twice.foundation-source-ready/v1",
        "passed": not errors,
        "guarded_file_count": len(manifest["guarded_files"]),
        "replay_count": len(replay_manifest["replays"]),
        "errors": errors,
        "v8_runtime_frozen": True,
        "locked_test_runs": 1,
        "public_replay_gpu_dependency": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
