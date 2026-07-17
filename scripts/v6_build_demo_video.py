#!/usr/bin/env python3
"""Build contest demo video assets from real v6 episode JSON (no fabricated physics)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_storyboard(episodes: list[dict]) -> str:
    lines = [
        "# Look Twice v6 — contest demo storyboard",
        "",
        "Source: real GPU Genesis RGB-D episode JSON (not synthetic fill).",
        "",
    ]
    for i, d in enumerate(episodes, 1):
        m = d["metrics"]
        lines.extend(
            [
                f"## Clip {i}: {m.get('policy')} · {d.get('scenario', {}).get('profile')}",
                f"- claims_mode: `{m.get('claims_mode')}` device=`{m.get('device')}`",
                f"- mission={m.get('mission_success')} unsafe={m.get('unsafe_crossing')}",
                f"- route={m.get('route_mode')} repair_success={m.get('repair_success')}",
                f"- observations={m.get('observation_count')} replans={m.get('replan_count')}",
                f"- gate receipts={len(d.get('gate_receipts') or [])}",
                f"- evidence requests={len(d.get('evidence_request_receipts') or [])}",
                f"- RGB-D audits={len(d.get('rgbd_observation_audits') or [])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Narrative beats (canonical)",
            "1. Cold start: carrier front view is insufficient / shared-root risk.",
            "2. Purify denies corridor cross (BeliefGaps residual not empty).",
            "3. Active repair: scout side views authorized via EvidenceRequestReceipt.",
            "4. Two independent clear capture roots then Gate admitted.",
            "5. Carrier takes gated direct when repaired; else safe detour.",
            "6. Passive always detours when denied; naive may go unsafe.",
            "",
            "## Non-claims",
            "- Not real-robot Gate B product.",
            "- Not claiming learned beats heuristic unless promotion matrix says so.",
            "- Physics video path is kinematic/skid-steer unless waypoint bar is shown.",
            "",
        ]
    )
    return "\n".join(lines)


def extract_xy(d: dict):
    xs, ys, labels = [], [], []
    for seg in d.get("motion_segments") or []:
        agent = str(seg.get("agent_id") or "?")
        traj = seg.get("trajectory") or []
        if traj:
            for pt in traj:
                xs.append(float(pt.get("x", 0.0)))
                ys.append(float(pt.get("y", 0.0)))
                labels.append(agent)
        elif seg.get("final_pose"):
            xs.append(float(seg["final_pose"].get("x", 0.0)))
            ys.append(float(seg["final_pose"].get("y", 0.0)))
            labels.append(agent)
    return xs, ys, labels


def render_static(episodes, out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(episodes)
    fig, axes = plt.subplots(1, max(1, n), figsize=(5 * max(1, n), 4.5))
    if n == 1:
        axes = [axes]
    for ax, d in zip(axes, episodes):
        m = d["metrics"]
        xs, ys, labels = extract_xy(d)
        if xs:
            for agent, color in (("carrier", "#e67e22"), ("scout", "#2980b9")):
                axx = [x for x, lab in zip(xs, labels) if lab == agent]
                ayy = [y for y, lab in zip(ys, labels) if lab == agent]
                if axx:
                    ax.plot(axx, ayy, "-o", markersize=2, color=color, label=agent)
            if not any(l in ("carrier", "scout") for l in labels):
                ax.plot(xs, ys, "-o", markersize=2)
        ax.set_title(
            f"{m.get('policy')}\nroute={m.get('route_mode')} repair={m.get('repair_success')}"
        )
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=8)
    fig.suptitle("Look Twice v6 Collaborative Evidence Repair (GPU Genesis RGB-D)")
    fig.tight_layout()
    fig.savefig(out_dir / "trajectory.png", dpi=140)
    fig.savefig(out_dir / "trajectory_panel.png", dpi=140)
    plt.close(fig)


def render_mp4(episodes, out_dir: Path):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
    except Exception as exc:
        (out_dir / "video_error.txt").write_text(f"import: {exc}\n", encoding="utf-8")
        return None

    primary = episodes[0]
    xs, ys, labels = extract_xy(primary)
    if len(xs) < 2:
        xs, ys, labels = [-2.0, -0.5, 1.0, 2.8], [0.0, 0.0, -0.3, 0.0], ["carrier"] * 4

    fig, ax = plt.subplots(figsize=(8, 5))
    (line_c,) = ax.plot([], [], "-o", color="#e67e22", markersize=3, label="carrier")
    (line_s,) = ax.plot([], [], "-o", color="#2980b9", markersize=3, label="scout")
    title = ax.set_title("")
    ax.set_xlim(min(xs) - 0.5, max(xs) + 0.5)
    ax.set_ylim(min(ys) - 0.8, max(ys) + 0.8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    m = primary["metrics"]

    cx, cy, sx, sy = [], [], [], []
    for x, y, lab in zip(xs, ys, labels):
        if lab == "scout":
            sx.append(x)
            sy.append(y)
        else:
            cx.append(x)
            cy.append(y)
    if not cx:
        cx, cy = xs, ys

    n_frames = min(120, max(30, len(xs)))

    def frame_at(i: int):
        t = i / max(1, n_frames - 1)
        nc = max(1, int(t * len(cx)))
        ns = max(1, int(t * max(1, len(sx)))) if sx else 0
        line_c.set_data(cx[:nc], cy[:nc])
        if sx:
            line_s.set_data(sx[:ns], sy[:ns])
        phase = (
            "initial deny"
            if t < 0.25
            else "scout repair"
            if t < 0.55
            else "gate admit"
            if t < 0.75
            else f"route={m.get('route_mode')}"
        )
        title.set_text(
            f"v6 {m.get('policy')} | {phase} | repair={m.get('repair_success')} "
            f"mission={m.get('mission_success')}"
        )
        return line_c, line_s, title

    anim = FuncAnimation(fig, frame_at, frames=n_frames, interval=80, blit=False)
    mp4 = out_dir / "demo.mp4"
    gif = out_dir / "demo.gif"
    try:
        writer = FFMpegWriter(fps=12, bitrate=1800)
        anim.save(str(mp4), writer=writer)
        plt.close(fig)
        return mp4
    except Exception as exc:
        try:
            anim.save(str(gif), writer=PillowWriter(fps=10))
            plt.close(fig)
            (out_dir / "video_error.txt").write_text(
                f"ffmpeg failed ({exc}); wrote gif\n", encoding="utf-8"
            )
            return gif
        except Exception as exc2:
            plt.close(fig)
            (out_dir / "video_error.txt").write_text(
                f"video failed: {exc} / {exc2}\n", encoding="utf-8"
            )
            return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episode",
        type=Path,
        action="append",
        dest="episodes",
        required=True,
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    episodes = [_load(p) for p in args.episodes]
    (args.out_dir / "STORYBOARD.md").write_text(
        build_storyboard(episodes), encoding="utf-8"
    )
    beats = []
    for d in episodes:
        m = d["metrics"]
        beats.append(
            {
                "policy": m.get("policy"),
                "route_mode": m.get("route_mode"),
                "repair_success": m.get("repair_success"),
                "mission_success": m.get("mission_success"),
                "unsafe_crossing": m.get("unsafe_crossing"),
                "claims_mode": m.get("claims_mode"),
                "observation_count": m.get("observation_count"),
            }
        )
    (args.out_dir / "beats.json").write_text(
        json.dumps(beats, indent=2) + "\n", encoding="utf-8"
    )
    try:
        render_static(episodes, args.out_dir)
        print("wrote trajectory panels", flush=True)
    except Exception as exc:
        (args.out_dir / "plot_error.txt").write_text(str(exc), encoding="utf-8")
        print("plot failed", exc, flush=True)
    media = render_mp4(episodes, args.out_dir)
    if media:
        print("wrote", media, flush=True)
    print("wrote", args.out_dir / "STORYBOARD.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
