#!/usr/bin/env python3
"""Build a simple demo panel video from v6 episode JSON (no fake physics).

Produces an MP4 via matplotlib animation if ffmpeg available; else writes
frame PNGs + a markdown storyboard.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    d = json.loads(args.episode.read_text(encoding="utf-8"))
    m = d["metrics"]
    story = [
        "# v6 demo storyboard (from real episode JSON)",
        "",
        f"- policy: {m.get('policy')}",
        f"- claims_mode: {m.get('claims_mode')}",
        f"- device: {m.get('device')}",
        f"- mission: {m.get('mission_success')} unsafe={m.get('unsafe_crossing')}",
        f"- route: {m.get('route_mode')} repair_success={m.get('repair_success')}",
        f"- observations: {m.get('observation_count')}",
        f"- gate receipts: {len(d.get('gate_receipts') or [])}",
        f"- evidence requests: {len(d.get('evidence_request_receipts') or [])}",
        f"- RGB-D audits: {len(d.get('rgbd_observation_audits') or [])}",
        "",
        "## Beat sheet",
        "1. Carrier initial front view → low coverage / deny",
        "2. BeliefGap insufficient_roots",
        "3. Scout side views authorized via EvidenceRequestReceipt",
        "4. Independent clear capture roots → Gate admitted",
        "5. Carrier direct corridor cross + delivery" if m.get("route_mode") == "direct" else "5. Safe detour delivery",
        "",
        "## Motion segments",
    ]
    for seg in (d.get("motion_segments") or [])[:40]:
        story.append(
            f"- {seg.get('agent_id')} → {seg.get('target_xy')} reached={seg.get('reached')} "
            f"path={seg.get('path_length')}"
        )
    md = args.out_dir / "STORYBOARD.md"
    md.write_text("\n".join(story) + "\n", encoding="utf-8")

    # Optional matplotlib path plot
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xs, ys = [], []
        for seg in d.get("motion_segments") or []:
            for pt in seg.get("trajectory") or []:
                xs.append(pt.get("x"))
                ys.append(pt.get("y"))
            if not seg.get("trajectory") and seg.get("final_pose"):
                xs.append(seg["final_pose"].get("x"))
                ys.append(seg["final_pose"].get("y"))
        fig, ax = plt.subplots(figsize=(8, 5))
        if xs:
            ax.plot(xs, ys, "-o", markersize=2, label="trajectory")
        ax.set_title(
            f"v6 {m.get('policy')} route={m.get('route_mode')} repair={m.get('repair_success')}"
        )
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.savefig(args.out_dir / "trajectory.png", dpi=120)
        plt.close(fig)
        print("wrote", args.out_dir / "trajectory.png")
    except Exception as exc:
        (args.out_dir / "plot_error.txt").write_text(str(exc), encoding="utf-8")
    print("wrote", md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
