#!/usr/bin/env python3
"""Build the deterministic 30-second judge reel from captured Cinematic frames."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


DURATIONS = (3, 4, 4, 6, 5, 8)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("showcase/public/data/replays/v8-active-repair-direct.json"),
    )
    args = parser.parse_args()

    frames = [args.frames_dir / f"frame-{index:02d}.png" for index in range(1, 7)]
    missing = [str(path) for path in frames if not path.is_file()]
    if missing:
        raise SystemExit(f"missing captured Cinematic frames: {missing}")
    if sum(DURATIONS) != 30:
        raise SystemExit("chapter durations must total exactly 30 seconds")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    video = args.out_dir / "look-twice-replay-30s.mp4"
    poster = args.out_dir / "look-twice-replay-30s.poster.webp"
    manifest = args.out_dir / "look-twice-replay-30s.manifest.json"
    video_filter = (
        "scale=1920:1080:force_original_aspect_ratio=decrease:"
        "in_range=pc:out_range=tv,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x05090b,"
        "fps=30,format=yuv420p"
    )

    with tempfile.TemporaryDirectory(prefix="look-twice-video-") as temp_dir:
        concat = Path(temp_dir) / "frames.txt"
        lines: list[str] = []
        for frame, duration in zip(frames, DURATIONS, strict=True):
            escaped = str(frame.resolve()).replace("'", r"'\''")
            lines.extend((f"file '{escaped}'", f"duration {duration}"))
        escaped_last = str(frames[-1].resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped_last}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-vf",
                video_filter,
                "-t",
                "30",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "21",
                "-pix_fmt",
                "yuv420p",
                "-color_range",
                "tv",
                "-movflags",
                "+faststart",
                str(video),
            ]
        )

    run(
        [
            "cwebp",
            "-quiet",
            "-q",
            "82",
            "-resize",
            "1920",
            "1080",
            str(frames[4]),
            "-o",
            str(poster),
        ]
    )

    probe = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video),
            ],
            text=True,
        )
    )
    video_streams = [
        stream for stream in probe["streams"] if stream.get("codec_type") == "video"
    ]
    audio_streams = [
        stream for stream in probe["streams"] if stream.get("codec_type") == "audio"
    ]
    if len(video_streams) != 1 or audio_streams:
        raise SystemExit("expected exactly one video stream and no audio streams")
    stream = video_streams[0]
    if (
        int(stream["width"]) != 1920
        or int(stream["height"]) != 1080
        or stream["pix_fmt"] != "yuv420p"
        or stream["r_frame_rate"] != "30/1"
    ):
        raise SystemExit(f"unexpected output stream: {stream}")
    if video.stat().st_size >= 50 * 1024 * 1024:
        raise SystemExit("video exceeds the 50 MiB publication ceiling")

    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    payload = {
        "schema_version": "look-twice.replay-media-manifest/v1",
        "candidate_id": bundle["candidate_id"],
        "replay_id": bundle["episode_meta"]["replay_id"],
        "bundle_sha256": sha256(args.bundle),
        "recorded_at_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "recording_method": "cinematic_replay_frame_capture",
        "chapter_durations_seconds": list(DURATIONS),
        "video": {
            "path": video.name,
            "sha256": sha256(video),
            "bytes": video.stat().st_size,
            "codec": "h264",
            "pixel_format": "yuv420p",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "duration_seconds": 30,
            "audio": False,
        },
        "poster": {
            "path": poster.name,
            "sha256": sha256(poster),
            "bytes": poster.stat().st_size,
        },
        "boundary": {
            "recorded_amd_gpu_evidence": True,
            "simulation_only": True,
            "live_gpu_dependency": False,
        },
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
