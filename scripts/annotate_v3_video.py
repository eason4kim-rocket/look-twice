"""给 v3 Genesis 顶视视频叠加概率 belief、NBV 与 Action Gate。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def latest(events: list[dict], step: int) -> dict | None:
    candidates = [event for event in events if int(event["step"]) <= step]
    return candidates[-1] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-stride", type=int, default=5)
    args = parser.parse_args()
    data = json.loads(args.result.read_text(encoding="utf-8"))
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Unable to open video: {args.video}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise SystemExit(f"Unable to create video: {args.output}")

    frame_index = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        step = frame_index * args.video_stride
        belief = latest(data["belief_trace"], step)
        action = latest(data["action_decisions"], step)
        viewpoint = latest(data["viewpoint_evaluations"], step)
        event = latest(data["dynamic_events"], step)
        evidence_count = sum(int(item["step"]) <= step for item in data["evidence"])

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 174), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.70, frame, 0.30, 0)
        config = data["configuration"]
        p_blocked = float(belief["p_blocked"]) if belief else 0.5
        entropy = float(belief["entropy"]) if belief else 1.0
        status = belief["status"] if belief else "unknown"
        action_text = "none"
        if action:
            action_text = f"{action['action']} ({'ALLOW' if action['allowed'] else 'DENY'})"
        viewpoint_text = viewpoint["selected"] if viewpoint else "pending"
        event_text = event["event"] if event else "none"
        lines = (
            f"Look Twice v3 | {config['policy']} | {config['profile']}",
            f"step={step}  evidence={evidence_count}  viewpoint={viewpoint_text}",
            f"belief={status}  p(blocked)={p_blocked:.3f}  entropy={entropy:.3f}",
            f"Action Gate: {action_text}",
            f"dynamic event={event_text}",
        )
        for index, line in enumerate(lines):
            cv2.putText(
                frame,
                line,
                (16, 26 + 30 * index),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.56,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        writer.write(frame)
        frame_index += 1
    capture.release()
    writer.release()
    if not frame_index:
        raise SystemExit("Input video contains no frames")
    print(f"saved: {args.output} ({frame_index} frames)")


if __name__ == "__main__":
    main()
