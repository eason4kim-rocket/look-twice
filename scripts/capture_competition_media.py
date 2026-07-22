#!/usr/bin/env python3
"""Record public RGB/depth/mask sidecars without changing episode inputs.

This is a transparent wrapper around ``V6GenesisRuntime.capture_raw``. The
runtime receives exactly the same arrays it would without recording; the hook
only serializes display copies after capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgb_u8(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 3 and array.shape[-1] > 3:
        array = array[..., :3]
    if np.issubdtype(array.dtype, np.floating):
        scale = 255.0 if float(np.nanmax(array)) <= 1.5 else 1.0
        array = array * scale
    return np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))


def depth_u8(value: Any) -> np.ndarray:
    depth = np.asarray(value, dtype=np.float32)
    valid = np.isfinite(depth) & (depth > 0)
    normalized = np.zeros_like(depth, dtype=np.float32)
    if np.any(valid):
        lo, hi = np.percentile(depth[valid], [3, 97])
        if hi <= lo:
            hi = lo + 1.0
        normalized[valid] = np.clip((depth[valid] - lo) / (hi - lo), 0, 1)
    # Compact perceptual blue→cyan→amber ramp, implemented without matplotlib.
    r = np.clip(2.0 * normalized - 0.45, 0, 1)
    g = np.clip(1.7 * normalized, 0, 1)
    b = np.clip(1.4 - 1.2 * normalized, 0, 1)
    return np.ascontiguousarray(np.stack((r, g, b), axis=-1) * 255, dtype=np.uint8)


def behavior_signature(episode: dict[str, Any]) -> dict[str, Any]:
    metrics = episode.get("metrics") or {}
    vision = episode.get("vision_audits") or []
    return {
        "route_mode": metrics.get("route_mode"),
        "repair_success": bool(metrics.get("repair_success")),
        "unsafe_crossing": bool(metrics.get("unsafe_crossing")),
        "selected_corridor": metrics.get("selected_corridor"),
        "vision_values": [item.get("value") for item in vision],
        "vision_viewpoints": [item.get("viewpoint") for item in vision],
        "effective_admit_count": sum(
            bool(item.get("effective_admit"))
            for item in (episode.get("gate_receipts") or [])
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-output", type=Path, required=True)
    parser.add_argument("--episode-output", type=Path, required=True)
    parser.add_argument("--reference-episode", type=Path)
    args, episode_args = parser.parse_known_args()
    args.media_output.mkdir(parents=True, exist_ok=True)

    from v6_genesis_runtime import V6GenesisRuntime
    from v8_corridor_projection import corridor_mask_from_geometry

    original = V6GenesisRuntime.capture_raw
    records: list[dict[str, Any]] = []

    def recording_capture(self: Any, **kwargs: Any) -> Any:
        frame = original(self, **kwargs)
        index = len(records) + 1
        rgb = rgb_u8(frame.rgb)
        depth = np.asarray(frame.depth)
        viewpoint = str(kwargs.get("viewpoint") or "")
        corridor_id = viewpoint.split("/", 1)[0] if viewpoint.startswith("corridor_") else "corridor_a"
        mask = corridor_mask_from_geometry(
            rgb.shape[0], rgb.shape[1], corridor_id=corridor_id,
            public=self.scenario.public_context,
        )
        mask_image = np.zeros_like(rgb)
        mask_image[..., 0] = np.where(mask > 0, 21, 5)
        mask_image[..., 1] = np.where(mask > 0, 213, 12)
        mask_image[..., 2] = np.where(mask > 0, 208, 15)
        outputs = {
            "rgb": args.media_output / f"frame-{index}-rgb.webp",
            "depth": args.media_output / f"frame-{index}-depth.webp",
            "corridor_mask": args.media_output / f"frame-{index}-mask.webp",
        }
        Image.fromarray(rgb).save(outputs["rgb"], "WEBP", quality=88, method=6)
        Image.fromarray(depth_u8(depth)).save(outputs["depth"], "WEBP", quality=88, method=6)
        Image.fromarray(mask_image).save(outputs["corridor_mask"], "WEBP", lossless=True, method=6)
        records.append({
            "frame_id": f"frame-{index}", "viewpoint": viewpoint,
            "corridor_id": corridor_id, "capture_step": int(frame.capture_step),
            "rgb_array_sha256": hashlib.sha256(np.ascontiguousarray(frame.rgb).tobytes()).hexdigest(),
            "depth_array_sha256": hashlib.sha256(np.ascontiguousarray(frame.depth).tobytes()).hexdigest(),
            "media_sha256": {key: sha256(path) for key, path in outputs.items()},
        })
        return frame

    V6GenesisRuntime.capture_raw = recording_capture
    from look_twice_v7 import main as episode_main
    code = episode_main([*episode_args, "--json-output", str(args.episode_output)])
    episode = json.loads(args.episode_output.read_text())
    signature = behavior_signature(episode)
    reference_match = None
    if args.reference_episode:
        reference_match = signature == behavior_signature(json.loads(args.reference_episode.read_text()))
    report = {
        "schema_version": "look-twice.recorded-media/v1",
        "episode_output": str(args.episode_output),
        "frame_count": len(records),
        "frames": records,
        "behavior_signature": signature,
        "reference_behavior_match": reference_match,
        "runtime_inputs_unchanged": True,
    }
    (args.media_output / "MEDIA_MANIFEST.json").write_text(json.dumps(report, indent=2) + "\n")
    if args.reference_episode and not reference_match:
        raise SystemExit("recorded episode behavior differs from frozen reference")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
