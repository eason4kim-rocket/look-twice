"""把一次 v3 观察的 raw/corrupted RGB-D-segmentation 拼成审计图。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--observation-index", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.result.read_text(encoding="utf-8"))
    evidence = data["evidence"][args.observation_index]
    raw = evidence["metadata"]["raw_artifacts"]
    corrupted = evidence["metadata"]["perception"]["artifact_paths"]
    keys = ("rgb", "depth", "segmentation")
    images = [Image.open(raw[key]).convert("RGB") for key in keys]
    images += [Image.open(corrupted[key]).convert("RGB") for key in keys]
    width = max(image.width for image in images)
    height = max(image.height for image in images)
    header = 42
    panel = Image.new("RGB", (3 * width, 2 * (height + header)), "white")
    draw = ImageDraw.Draw(panel)
    for index, image in enumerate(images):
        row, column = divmod(index, 3)
        x, y = column * width, row * (height + header)
        panel.paste(image, (x, y + header))
        prefix = "RAW" if row == 0 else "CORRUPTED"
        draw.text((x + 10, y + 12), f"{prefix} {keys[column].upper()}", fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.save(args.output)
    print("saved:", args.output)


if __name__ == "__main__":
    main()
