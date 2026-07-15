"""将状态、belief 和 Action Gate 决策叠加到 Genesis 原始视频。"""

import argparse
import json
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-stride", type=int, default=5)
    return parser.parse_args()


def latest_at_step(events: list[dict], step: int) -> dict | None:
    latest = None
    for event in events:
        if event["step"] > step:
            break
        latest = event
    return latest


def main() -> None:
    args = parse_args()
    data = json.loads(args.result.read_text(encoding="utf-8"))
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Unable to open video: {args.video}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(args.output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit(f"Unable to create video: {args.output}")

    frame_index = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        step = frame_index * args.video_stride
        state_event = latest_at_step(data["state_transitions"], step)
        belief_event = latest_at_step(data["belief_lifecycle"], step)
        decisions = [
            item for item in data["action_decisions"] if item["step"] <= step
        ]
        evidence_count = sum(
            item["step"] <= step for item in data["evidence"]
        )

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, 132), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.68, frame, 0.32, 0)
        config = data["configuration"]
        state_name = state_event["to"] if state_event else "UNKNOWN"
        belief_name = belief_event["status"] if belief_event else "unknown"
        last_action = "none"
        if decisions:
            decision = decisions[-1]
            verdict = "ALLOW" if decision["allowed"] else "DENY"
            last_action = f"{verdict} {decision['action']}"

        lines = (
            f"Look Twice | {config['policy']} | scenario={config['scenario']}",
            f"step={step}  state={state_name}",
            f"belief={belief_name}  evidence={evidence_count}",
            f"action gate: {last_action}",
        )
        for line_index, line in enumerate(lines):
            cv2.putText(
                frame,
                line,
                (16, 25 + line_index * 29),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        writer.write(frame)
        frame_index += 1

    capture.release()
    writer.release()
    if frame_index == 0:
        raise SystemExit("Input video contained no frames")
    print(f"saved: {args.output} ({frame_index} frames)")


if __name__ == "__main__":
    main()
