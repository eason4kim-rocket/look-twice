#!/usr/bin/env python3
"""Issue the two-day competition-foundation acceptance stamp."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import file_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-url", default="http://localhost:3000")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    errors: list[str] = []

    source_report = json.loads((ROOT / "release/FOUNDATION_SOURCE_READY.json").read_text())
    checks["frozen_sha_guard"] = bool(source_report.get("passed"))
    manifest = json.loads((ROOT / "showcase/public/data/manifest.json").read_text())
    checks["two_replays"] = len(manifest.get("replays") or []) == 2
    checks["candidate_driven_manifest"] = bool(manifest.get("default_candidate_id")) and all(
        row.get("candidate_id") for row in manifest.get("replays") or []
    )

    media_ok = True
    behavior_ok = True
    for replay in manifest.get("replays") or []:
        bundle = json.loads(
            (ROOT / f"showcase/public/data/replays/{replay['replay_id']}.json").read_text()
        )
        for frame in bundle.get("sensor_frames") or []:
            if not frame.get("media", {}).get("available"):
                media_ok = False
            for kind in ("rgb", "depth", "corridor_mask"):
                relative = str(frame["media"][kind]).lstrip("/")
                path = ROOT / "showcase/public" / relative
                expected = frame["media"].get("sha256", {}).get(kind)
                if not path.is_file() or not expected or file_sha256(path) != expected:
                    media_ok = False
        media_manifest = json.loads(
            (ROOT / f"showcase/public/data/media/{replay['replay_id']}/MEDIA_MANIFEST.json").read_text()
        )
        behavior_ok &= media_manifest.get("reference_behavior_match") is True
        behavior_ok &= media_manifest.get("runtime_inputs_unchanged") is True
    checks["recorded_rgb_depth_mask"] = media_ok
    checks["recording_preserved_behavior"] = behavior_ok

    public_text = "\n".join(
        path.read_text(errors="ignore")
        for path in (ROOT / "showcase/public/data").rglob("*.json")
    )
    forbidden = ("/workspace/", "/Users/", "root@", "36.150.116.", '"oracle"')
    checks["public_data_scrubbed"] = not any(token in public_text for token in forbidden)
    checks["bilingual_keys_present"] = all(
        token in (ROOT / "showcase/app/components/EvidenceConsole.tsx").read_text()
        for token in ("当前候选", "传感器证据", "动作资格审查", "机器人决策")
    )
    checks["neutral_schemas_present"] = all(
        (ROOT / path).is_file()
        for path in (
            "schemas/release_profile_v1.schema.json",
            "schemas/episode_bundle_v1.schema.json",
        )
    )
    checks["four_routes_built"] = all(
        (ROOT / path).is_file()
        for path in (
            "showcase/app/page.tsx",
            "showcase/app/console/page.tsx",
            "showcase/app/results/page.tsx",
            "showcase/app/reproduce/page.tsx",
        )
    )
    checks["docker_files_present"] = all(
        (ROOT / name).is_file() for name in ("Dockerfile", "docker-compose.yml")
    )

    runtime_ok = True
    for route in ("/", "/console", "/results", "/reproduce", "/data/manifest.json"):
        route_ok = False
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                with urllib.request.urlopen(args.runtime_url + route, timeout=5) as response:
                    route_ok = response.status == 200
                if route_ok:
                    break
            except Exception as exc:  # pragma: no cover - environment failure path
                last_error = exc
            time.sleep(0.5 * (attempt + 1))
        runtime_ok &= route_ok
        if not route_ok:
            errors.append(f"runtime:{route}:{type(last_error).__name__ if last_error else 'status'}")
    checks["cpu_replay_runtime"] = runtime_ok
    try:
        running = subprocess.run(
            ["docker", "compose", "ps", "--services", "--status", "running"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        checks["docker_running"] = "evidence-console" in running
    except (OSError, subprocess.CalledProcessError):
        checks["docker_running"] = False

    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    report = {
        "schema_version": "look-twice.competition-foundation-ready/v1",
        "status": "COMPETITION_FOUNDATION_READY" if not errors else "NOT_READY",
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "default_candidate_id": manifest.get("default_candidate_id"),
        "replay_manifest_sha256": manifest.get("manifest_sha256"),
        "frozen_import_manifest_sha256": json.loads(
            (ROOT / "release/V8_FROZEN_IMPORT_MANIFEST.json").read_text()
        )["manifest_sha256"],
        "v9_integration_boundary": "add ReleaseProfile + EpisodeBundle adapter only",
    }
    output = ROOT / "release/COMPETITION_FOUNDATION_READY.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
