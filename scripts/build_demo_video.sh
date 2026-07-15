#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-"$repo_dir/assets/demo/look-twice-demo.mp4"}
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

python3 - "$work_dir" <<'PY'
import sys
from pathlib import Path

import matplotlib.pyplot as plt

work_dir = Path(sys.argv[1])
cards = {
    "title.png": (
        "LOOK TWICE",
        "Evidence-gated active perception for safe navigation",
    ),
    "closing.png": (
        "AMD Radeon PRO W7900D",
        "ROCm + PyTorch + Genesis gs.amdgpu",
    ),
}
for filename, (title, subtitle) in cards.items():
    figure = plt.figure(figsize=(6.4, 4.8), dpi=100, facecolor="#101820")
    figure.text(0.5, 0.60, title, color="white", fontsize=30, ha="center")
    figure.text(0.5, 0.45, subtitle, color="white", fontsize=14, ha="center")
    plt.axis("off")
    figure.savefig(work_dir / filename, facecolor=figure.get_facecolor())
    plt.close(figure)
PY

ffmpeg -y -loop 1 -i "$work_dir/title.png" -t 7.5 -vf "fps=30" \
  -an -c:v libx264 -pix_fmt yuv420p "$work_dir/01-title.mp4" >/dev/null 2>&1

for spec in "clear:02" "blocked:03" "conflict:04"; do
  name=${spec%%:*}
  order=${spec##*:}
  ffmpeg -y -i "$repo_dir/assets/demo/$name.mp4" \
    -vf "setpts=4.0*PTS,fps=30,scale=640:480" \
    -an -c:v libx264 -pix_fmt yuv420p "$work_dir/$order-$name.mp4" \
    >/dev/null 2>&1
done

ffmpeg -y -loop 1 \
  -i "$repo_dir/results/2026-07-15_formal-experiment/policy-comparison.png" \
  -t 10 -vf "scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2:white,fps=30" \
  -an -c:v libx264 -pix_fmt yuv420p "$work_dir/05-results.mp4" \
  >/dev/null 2>&1

ffmpeg -y -loop 1 -i "$work_dir/closing.png" -t 7.5 -vf "fps=30" \
  -an -c:v libx264 -pix_fmt yuv420p "$work_dir/06-amd.mp4" >/dev/null 2>&1

for clip in "$work_dir"/*.mp4; do
  printf "file '%s'\n" "$clip"
done > "$work_dir/concat.txt"

mkdir -p "$(dirname "$output")"
ffmpeg -y -f concat -safe 0 -i "$work_dir/concat.txt" \
  -c copy -movflags +faststart "$output" >/dev/null 2>&1

echo "saved: $output"
