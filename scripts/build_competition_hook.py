#!/usr/bin/env python3
"""Build the short judge-facing motion hook from the sealed 30-second replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = ROOT / "showcase" / "public" / "media"
SOURCE_VIDEO = MEDIA_ROOT / "look-twice-replay-30s.mp4"
SOURCE_MANIFEST = MEDIA_ROOT / "look-twice-replay-30s.manifest.json"
VIDEO_NAME = "look-twice-repair-to-action-10s.mp4"
PREVIEW_NAME = "look-twice-repair-to-action-10s.webp"
MANIFEST_NAME = "look-twice-repair-to-action-10s.manifest.json"
SOURCE_START_SECONDS = 16.8
DURATION_SECONDS = 10.0
EXPECTED_SOURCE_SHA256 = (
    "46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"required program is unavailable: {name}")


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def probe_video(path: Path) -> dict[str, Any]:
    payload = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,pix_fmt,width,height,r_frame_rate:format=duration",
                "-of",
                "json",
                str(path),
            ],
            cwd=ROOT,
            text=True,
        )
    )
    stream = payload["streams"][0]
    numerator, denominator = stream["r_frame_rate"].split("/", 1)
    return {
        "codec": stream["codec_name"],
        "pixel_format": stream["pix_fmt"],
        "width": stream["width"],
        "height": stream["height"],
        "fps": int(numerator) / int(denominator),
        "duration_seconds": float(payload["format"]["duration"]),
    }


def is_faststart(path: Path) -> bool:
    payload = path.read_bytes()
    moov = payload.find(b"moov")
    mdat = payload.find(b"mdat")
    return moov >= 0 and mdat >= 0 and moov < mdat


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(payload: dict[str, Any], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)


def build(output_dir: Path) -> dict[str, Any]:
    for program in ("ffmpeg", "ffprobe", "img2webp"):
        require_program(program)

    source_sha256 = sha256(SOURCE_VIDEO)
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            "sealed replay identity mismatch: "
            f"expected {EXPECTED_SOURCE_SHA256}, observed {source_sha256}"
        )
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    if source_manifest["video"]["sha256"] != source_sha256:
        raise SystemExit("sealed replay manifest does not bind the source video")

    with tempfile.TemporaryDirectory(prefix="look-twice-hook-") as directory:
        temporary_root = Path(directory)
        frames_root = temporary_root / "frames"
        frames_root.mkdir()
        video = temporary_root / VIDEO_NAME
        preview = temporary_root / PREVIEW_NAME

        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(SOURCE_START_SECONDS),
                "-t",
                str(DURATION_SECONDS),
                "-i",
                str(SOURCE_VIDEO),
                "-an",
                "-vf",
                "scale=1280:-2:flags=lanczos",
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "25",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "60",
                "-movflags",
                "+faststart",
                str(video),
            ]
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(SOURCE_START_SECONDS),
                "-t",
                str(DURATION_SECONDS),
                "-i",
                str(SOURCE_VIDEO),
                "-an",
                "-vf",
                "fps=10,scale=960:-2:flags=lanczos",
                str(frames_root / "frame-%03d.png"),
            ]
        )
        frames = sorted(frames_root.glob("frame-*.png"))
        if len(frames) != 100:
            raise SystemExit(f"expected 100 preview frames, observed {len(frames)}")
        run(
            [
                "img2webp",
                "-lossy",
                "-q",
                "65",
                "-m",
                "6",
                "-d",
                "100",
                "-loop",
                "0",
                *[str(frame) for frame in frames],
                "-o",
                str(preview),
            ]
        )

        video_probe = probe_video(video)
        if abs(video_probe["duration_seconds"] - DURATION_SECONDS) > 0.01:
            raise SystemExit(f"unexpected hook duration: {video_probe['duration_seconds']}")
        if not is_faststart(video):
            raise SystemExit("hook MP4 is not faststart")

        output_video = output_dir / VIDEO_NAME
        output_preview = output_dir / PREVIEW_NAME
        atomic_copy(video, output_video)
        atomic_copy(preview, output_preview)

    manifest = {
        "schema_version": "look-twice.judge-motion-hook/v1",
        "candidate_id": "v8-frozen",
        "hook_id": "repair-to-action-10s",
        "description": (
            "A silent excerpt of the recorded replay: an independent root repairs "
            "the Action Contract, Python and Purify Go admit, and the carrier moves."
        ),
        "builder": "scripts/build_competition_hook.py",
        "derived_from": {
            "path": SOURCE_VIDEO.relative_to(ROOT).as_posix(),
            "sha256": source_sha256,
            "manifest_path": SOURCE_MANIFEST.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha256(SOURCE_MANIFEST),
            "recorded_at_utc": source_manifest["recorded_at_utc"],
            "source_start_seconds": SOURCE_START_SECONDS,
            "source_end_seconds": SOURCE_START_SECONDS + DURATION_SECONDS,
        },
        "video": {
            "path": VIDEO_NAME,
            "sha256": sha256(output_video),
            "bytes": output_video.stat().st_size,
            **video_probe,
            "audio": False,
            "faststart": True,
        },
        "readme_preview": {
            "path": PREVIEW_NAME,
            "sha256": sha256(output_preview),
            "bytes": output_preview.stat().st_size,
            "format": "animated_webp",
            "width": 960,
            "height": 540,
            "fps": 10,
            "duration_seconds": DURATION_SECONDS,
            "loop": True,
        },
        "boundary": {
            "recorded_replay_excerpt": True,
            "new_experiment_or_result": False,
            "simulation_only": True,
            "real_robot_footage": False,
            "audio": False,
        },
    }
    atomic_json(manifest, output_dir / MANIFEST_NAME)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=MEDIA_ROOT)
    parser.add_argument(
        "--package-dir",
        type=Path,
        help="also copy the exact hook assets into an official submission package",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    manifest = build(output_dir)
    if args.package_dir:
        package_dir = args.package_dir.resolve()
        for name in (VIDEO_NAME, PREVIEW_NAME, MANIFEST_NAME):
            atomic_copy(output_dir / name, package_dir / name)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
