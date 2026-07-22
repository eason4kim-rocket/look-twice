#!/usr/bin/env python3
"""Build public, version-neutral replay packs from frozen V8 episodes."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import (  # noqa: E402
    adapt_v8_episode,
    assert_public_bundle,
    build_v8_release_profile,
    canonical_sha256,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sanitize_public_source(value: object) -> object:
    """Remove machine-only location fields while preserving evidence values."""
    if isinstance(value, dict):
        return {
            key: sanitize_public_source(item)
            for key, item in value.items()
            if key not in {"path", "opened_seal", "live_rows_path"}
        }
    if isinstance(value, list):
        return [sanitize_public_source(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-root", type=Path, default=ROOT / "release" / "v8-frozen"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "showcase" / "public" / "data"
    )
    args = parser.parse_args()

    identity_manifest = json.loads(
        (args.frozen_root / "results" / "V8_IDENTITY_FREEZE_MANIFEST.json").read_text()
    )
    frozen = identity_manifest["V8_RUNTIME_FROZEN"]
    purify = identity_manifest["frozen_assets"]["purify_binary"]
    identity = {
        "vision_checkpoint": frozen["checkpoint_sha256"],
        "vision_conformal": frozen["vision_conformal_sha256"],
        "go_conformal": frozen["go_fusion_v3_sha256"],
        "purify_binary": purify["file_sha256"],
    }
    locked_report_path = (
        args.frozen_root
        / "results"
        / "locked_test_v8_once"
        / "LOCKED_TEST_REPORT.json"
    )
    locked_report = json.loads(locked_report_path.read_text())

    specs = [
        (
            "v8-active-repair-direct",
            args.frozen_root
            / "episodes"
            / "active__independent-noise__105400.json",
        ),
        (
            "v8-passive-safe-detour",
            args.frozen_root
            / "episodes"
            / "passive__independent-noise__105400.json",
        ),
    ]
    replay_dir = args.output / "replays"
    replay_ids: list[str] = []
    replay_manifest: list[dict[str, object]] = []
    for replay_id, episode_path in specs:
        recorded_manifest_path = (
            args.frozen_root / "media" / replay_id / "MEDIA_MANIFEST.json"
        )
        bundle = adapt_v8_episode(
            episode_path,
            replay_id=replay_id,
            frozen_identity=identity,
            media_root=args.output / "media" / replay_id,
            media_manifest_path=recorded_manifest_path,
        )
        assert_public_bundle(bundle)
        output_path = replay_dir / f"{replay_id}.json"
        write_json(output_path, bundle)
        replay_ids.append(replay_id)
        replay_manifest.append(
            {
                "replay_id": replay_id,
                "candidate_id": bundle["candidate_id"],
                "policy": bundle["episode_meta"]["policy"],
                "route_mode": bundle["outcome"]["route_mode"],
                "repair_success": bundle["outcome"]["repair_success"],
                "href": f"/data/replays/{replay_id}.json",
                "bundle_sha256": bundle["integrity"]["bundle_sha256"],
            }
        )
        if recorded_manifest_path.is_file():
            recorded = json.loads(recorded_manifest_path.read_text())
            write_json(
                args.output / "media" / replay_id / "MEDIA_MANIFEST.json",
                {
                    "schema_version": recorded.get("schema_version"),
                    "frame_count": recorded.get("frame_count"),
                    "frames": recorded.get("frames") or [],
                    "behavior_signature": recorded.get("behavior_signature"),
                    "reference_behavior_match": recorded.get(
                        "reference_behavior_match"
                    ),
                    "runtime_inputs_unchanged": recorded.get(
                        "runtime_inputs_unchanged"
                    ),
                },
            )

    profile = build_v8_release_profile(
        replay_ids=replay_ids,
        locked_report=locked_report,
        frozen_identity=identity,
    )
    write_json(args.output / "profiles" / "v8-frozen.json", profile)
    manifest = {
        "schema_version": "look-twice.replay-manifest/v1",
        "default_candidate_id": "v8-frozen",
        "profiles": [
            {
                "candidate_id": "v8-frozen",
                "href": "/data/profiles/v8-frozen.json",
                "profile_sha256": profile["profile_sha256"],
            }
        ],
        "replays": replay_manifest,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    write_json(args.output / "manifest.json", manifest)

    source_dir = args.output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        source_dir / "LOCKED_TEST_REPORT.json",
        sanitize_public_source(locked_report),
    )
    print(
        json.dumps(
            {
                "replays": len(replay_manifest),
                "candidate": "v8-frozen",
                "manifest_sha256": manifest["manifest_sha256"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
