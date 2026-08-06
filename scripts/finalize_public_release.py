#!/usr/bin/env python3
"""Validate the publishable replay surface and write release readiness stamps."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import assert_public_bundle  # noqa: E402


PUBLIC_ROUTES = (
    "/",
    "/console",
    "/results",
    "/reproduce",
    "/media/look-twice-replay-30s.mp4",
    "/media/look-twice-repair-to-action-10s.mp4",
    "/media/look-twice-repair-to-action-10s.webp",
    "/media/look-twice-repair-to-action-10s.manifest.json",
)
PUBLIC_ROUTE_MIME_TYPES = {
    "/media/look-twice-replay-30s.mp4": "video/mp4",
    "/media/look-twice-repair-to-action-10s.mp4": "video/mp4",
    "/media/look-twice-repair-to-action-10s.webp": "image/webp",
    "/media/look-twice-repair-to-action-10s.manifest.json": "application/json",
}
JUDGE_MOTION_HOOK_MANIFEST_NAME = (
    "look-twice-repair-to-action-10s.manifest.json"
)
JUDGE_MOTION_HOOK_MANIFEST_SHA256 = (
    "98ea58ffa994768990ec0021e87c52f0c0157047a4ac646008d192e632a7e038"
)
FORBIDDEN = (
    b"/workspace/",
    b"/Users/",
    b"ssh root@",
    b"oracle",
    b"private purify",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-url")
    parser.add_argument("--docker-verified", action="store_true")
    parser.add_argument("--browser-verified", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    data_root = ROOT / "showcase" / "public" / "data"
    media_root = ROOT / "showcase" / "public" / "media"
    manifest_path = data_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundles: list[dict[str, object]] = []
    for replay in manifest["replays"]:
        path = ROOT / "showcase" / "public" / replay["href"].lstrip("/")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        try:
            assert_public_bundle(bundle)
        except AssertionError as exc:
            errors.append(f"{replay['replay_id']}: {exc}")
        bundles.append(bundle)

    media_manifest_path = media_root / "look-twice-replay-30s.manifest.json"
    media_manifest = json.loads(media_manifest_path.read_text(encoding="utf-8"))
    active_path = data_root / "replays" / "v8-active-repair-direct.json"
    if media_manifest["bundle_sha256"] != sha256(active_path):
        errors.append("media bundle_sha256 mismatch")
    for key in ("video", "poster"):
        item = media_manifest[key]
        target = media_root / item["path"]
        if not target.is_file() or sha256(target) != item["sha256"]:
            errors.append(f"{key} SHA mismatch")
    if media_manifest["video"]["bytes"] >= 50 * 1024 * 1024:
        errors.append("video exceeds 50 MiB")
    if sum(media_manifest["chapter_durations_seconds"]) != 30:
        errors.append("video chapters do not total 30 seconds")

    hook_manifest_path = media_root / JUDGE_MOTION_HOOK_MANIFEST_NAME
    hook_manifest = json.loads(hook_manifest_path.read_text(encoding="utf-8"))
    if sha256(hook_manifest_path) != JUDGE_MOTION_HOOK_MANIFEST_SHA256:
        errors.append("judge-motion hook manifest SHA mismatch")
    if (
        hook_manifest.get("schema_version")
        != "look-twice.judge-motion-hook/v1"
        or hook_manifest.get("candidate_id") != manifest["default_candidate_id"]
        or hook_manifest.get("hook_id") != "repair-to-action-10s"
    ):
        errors.append("judge-motion hook manifest identity mismatch")

    hook_source = hook_manifest["derived_from"]
    for label, relative_path, expected_sha256 in (
        (
            "source video",
            hook_source["path"],
            hook_source["sha256"],
        ),
        (
            "source manifest",
            hook_source["manifest_path"],
            hook_source["manifest_sha256"],
        ),
    ):
        target = ROOT / relative_path
        if not target.is_file() or sha256(target) != expected_sha256:
            errors.append(f"judge-motion hook {label} SHA mismatch")

    for key in ("video", "readme_preview"):
        item = hook_manifest[key]
        target = media_root / item["path"]
        if (
            not target.is_file()
            or sha256(target) != item["sha256"]
            or target.stat().st_size != item["bytes"]
        ):
            errors.append(f"judge-motion hook {key} SHA/size mismatch")

    hook_boundary = hook_manifest["boundary"]
    hook_video = hook_manifest["video"]
    hook_preview = hook_manifest["readme_preview"]
    hook_spec_valid = (
        hook_source["source_start_seconds"] == 16.8
        and hook_source["source_end_seconds"] == 26.8
        and hook_video["duration_seconds"] == 10.0
        and hook_video["width"] == 1280
        and hook_video["height"] == 720
        and hook_video["fps"] == 30.0
        and hook_video["audio"] is False
        and hook_preview["duration_seconds"] == 10.0
        and hook_preview["width"] == 960
        and hook_preview["height"] == 540
        and hook_preview["loop"] is True
        and hook_boundary
        == {
            "recorded_replay_excerpt": True,
            "new_experiment_or_result": False,
            "simulation_only": True,
            "real_robot_footage": False,
            "audio": False,
        }
    )
    if not hook_spec_valid:
        errors.append("judge-motion hook media specification or boundary mismatch")

    for path in (data_root, media_root):
        for candidate in path.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() in {
                ".mp4",
                ".webp",
                ".png",
                ".jpg",
                ".jpeg",
            }:
                continue
            payload = candidate.read_bytes().lower()
            for marker in FORBIDDEN:
                if marker.lower() in payload:
                    errors.append(f"forbidden public marker in {candidate.relative_to(ROOT)}")

    frozen = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_frozen_foundation.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if frozen.returncode:
        errors.append("frozen foundation verification failed")

    anonymous_results: list[dict[str, object]] = []
    if args.public_url:
        base = args.public_url.rstrip("/")
        public_route_sha256s = {
            "/media/look-twice-replay-30s.mp4": media_manifest["video"]["sha256"],
            "/media/look-twice-repair-to-action-10s.mp4": hook_video["sha256"],
            "/media/look-twice-repair-to-action-10s.webp": hook_preview["sha256"],
            "/media/look-twice-repair-to-action-10s.manifest.json": sha256(
                hook_manifest_path
            ),
        }
        for route in PUBLIC_ROUTES:
            url = base + route
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "LookTwiceReleaseVerifier/1.0"}
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    body = response.read()
                    content_type = response.headers.get("content-type")
                    result = {
                        "route": route,
                        "status": response.status,
                        "content_type": content_type,
                    }
                    if response.status != 200:
                        errors.append(f"anonymous route failed: {route}")
                    if route in PUBLIC_ROUTE_MIME_TYPES:
                        normalized_content_type = (content_type or "").split(";", 1)[
                            0
                        ].strip().lower()
                        expected_content_type = PUBLIC_ROUTE_MIME_TYPES[route]
                        observed_sha256 = hashlib.sha256(body).hexdigest()
                        expected_sha256 = public_route_sha256s[route]
                        result.update(
                            {
                                "sha256": observed_sha256,
                                "expected_sha256": expected_sha256,
                                "expected_content_type": expected_content_type,
                            }
                        )
                        if normalized_content_type != expected_content_type:
                            errors.append(
                                f"anonymous MIME mismatch {route}: expected "
                                f"{expected_content_type}, observed {content_type}"
                            )
                        if observed_sha256 != expected_sha256:
                            errors.append(f"anonymous SHA mismatch: {route}")
                    else:
                        lowered = body.lower()
                        if b"chatgpt login" in lowered or b"log in to chatgpt" in lowered:
                            errors.append(f"login gate detected: {route}")
                    anonymous_results.append(result)
            except Exception as exc:  # pragma: no cover - network handoff
                errors.append(f"anonymous route error {route}: {exc}")

    checks = {
        "episode_bundle_v1_1": all(
            bundle["schema_version"] == "look-twice.episode-bundle/v1.1"
            for bundle in bundles
        ),
        "active_and_passive_replays": len(bundles) == 2,
        "frozen_v8_guard": frozen.returncode == 0,
        "media_sha_recomputed": not any("SHA mismatch" in error for error in errors),
        "judge_motion_hook_sha_recomputed": not any(
            "judge-motion hook" in error and "SHA" in error for error in errors
        ),
        "judge_motion_hook_spec": hook_spec_valid,
        "video_spec": (
            media_manifest["video"]["width"] == 1920
            and media_manifest["video"]["height"] == 1080
            and media_manifest["video"]["fps"] == 30
            and media_manifest["video"]["duration_seconds"] == 30
            and media_manifest["video"]["audio"] is False
        ),
        "docker_fresh_build": args.docker_verified,
        "browser_state_and_responsive": args.browser_verified,
        "anonymous_public_routes": bool(args.public_url) and not anonymous_results == [],
    }
    core_passed = not errors and all(
        checks[key]
        for key in (
            "episode_bundle_v1_1",
            "active_and_passive_replays",
            "frozen_v8_guard",
            "media_sha_recomputed",
            "judge_motion_hook_sha_recomputed",
            "judge_motion_hook_spec",
            "video_spec",
            "docker_fresh_build",
            "browser_state_and_responsive",
        )
    )
    public_passed = core_passed and bool(args.public_url) and all(
        result["status"] == 200 for result in anonymous_results
    )
    payload = {
        "schema_version": "look-twice.replay-presentation-ready/v1",
        "status": (
            "REPLAY_PRESENTATION_READY"
            if public_passed
            else "BUILD_VERIFIED_AWAITING_CLOUDFLARE_CREDENTIALS"
        ),
        "passed": public_passed,
        "build_verified": core_passed,
        "commit_sha": git_commit(),
        "candidate_id": manifest["default_candidate_id"],
        "manifest_sha256": sha256(manifest_path),
        "active_bundle_sha256": sha256(active_path),
        "video_sha256": media_manifest["video"]["sha256"],
        "poster_sha256": media_manifest["poster"]["sha256"],
        "judge_motion_hook_manifest_sha256": sha256(hook_manifest_path),
        "judge_motion_hook_video_sha256": hook_video["sha256"],
        "judge_motion_hook_preview_sha256": hook_preview["sha256"],
        "public_url": args.public_url,
        "checked_at_utc": utc_now(),
        "checks": checks,
        "anonymous_results": anonymous_results,
        "errors": errors,
    }
    output = (
        ROOT / "release" / "REPLAY_PRESENTATION_READY.json"
        if public_passed
        else ROOT / "release" / "PUBLIC_RELEASE_BUILD_VERIFIED.json"
    )
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if public_passed:
        public_release = {
            "schema_version": "look-twice.public-release/v1",
            "status": "PUBLIC_RELEASE_VERIFIED",
            "passed": True,
            "url": args.public_url,
            "commit_sha": payload["commit_sha"],
            "candidate_id": payload["candidate_id"],
            "manifest_sha256": payload["manifest_sha256"],
            "active_bundle_sha256": payload["active_bundle_sha256"],
            "video_sha256": payload["video_sha256"],
            "poster_sha256": payload["poster_sha256"],
            "judge_motion_hook_manifest_sha256": payload[
                "judge_motion_hook_manifest_sha256"
            ],
            "judge_motion_hook_video_sha256": payload[
                "judge_motion_hook_video_sha256"
            ],
            "judge_motion_hook_preview_sha256": payload[
                "judge_motion_hook_preview_sha256"
            ],
            "deployed_and_checked_at_utc": payload["checked_at_utc"],
            "anonymous_results": anonymous_results,
        }
        (ROOT / "release" / "PUBLIC_RELEASE.json").write_text(
            json.dumps(public_release, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, indent=2))
    return 0 if core_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
