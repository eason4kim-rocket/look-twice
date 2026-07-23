"use client";

import { useEffect, useRef } from "react";
import type {
  EpisodeBundle,
  MotionPoint,
} from "../lib/types";
import type { ReplayChapterKind } from "../lib/replayDirector";

type Props = {
  bundle: EpisodeBundle;
  chapterKind: ReplayChapterKind;
  chapterStep: number;
  animate: boolean;
  durationMs: number;
  label: string;
};

type Pose = MotionPoint & { agent_id: string };
type Projected = { x: number; y: number };

const FLOOR_X = [-2.7, 3.2] as const;
const FLOOR_Y = [-1.75, 1.75] as const;

function agentPoints(bundle: EpisodeBundle, agentId: string) {
  return bundle.motion_segments
    .filter((motion) => motion.agent_id === agentId)
    .flatMap((motion) => motion.trajectory_sample)
    .sort((a, b) => a.step - b.step);
}

function poseAt(points: MotionPoint[], step: number): MotionPoint | undefined {
  if (!points.length) return undefined;
  if (step <= points[0].step) return points[0];
  if (step >= points.at(-1)!.step) return points.at(-1);
  let before = points[0];
  let after = points.at(-1)!;
  for (let index = 1; index < points.length; index += 1) {
    if (points[index].step >= step) {
      after = points[index];
      before = points[index - 1];
      break;
    }
  }
  const span = Math.max(1, after.step - before.step);
  const mix = Math.max(0, Math.min(1, (step - before.step) / span));
  return {
    step,
    x: before.x + (after.x - before.x) * mix,
    y: before.y + (after.y - before.y) * mix,
    yaw: before.yaw + (after.yaw - before.yaw) * mix,
  };
}

function chapterRange(
  bundle: EpisodeBundle,
  chapterKind: ReplayChapterKind,
  chapterStep: number,
) {
  if (chapterKind === "move") {
    const motions = bundle.motion_segments.filter(
      (motion) =>
        motion.agent_id === "scout" && motion.purpose === "scout_repair",
    );
    return {
      start: Math.min(...motions.map((motion) => motion.start_step)),
      end: Math.max(...motions.map((motion) => motion.end_step)),
    };
  }
  if (chapterKind === "act") {
    const deniedStep =
      bundle.gate_receipts.find((gate) => !gate.effective_admit)?.evaluated_step ||
      chapterStep;
    const admittedStep = bundle.gate_receipts.find(
      (gate) => gate.effective_admit,
    )?.evaluated_step;
    const carrier = bundle.motion_segments.filter(
      (motion) => motion.agent_id === "carrier",
    );
    return {
      start: admittedStep || deniedStep,
      end: Math.max(...carrier.map((motion) => motion.end_step)),
    };
  }
  return { start: chapterStep, end: chapterStep };
}

function project(
  width: number,
  height: number,
  x: number,
  y: number,
  z = 0,
): Projected {
  const scale = Math.min(width / 8.1, height / 4.9);
  return {
    x: width * 0.47 + (x - y) * scale,
    y: height * 0.52 + (x + y) * scale * 0.38 - z * scale,
  };
}

function polygon(
  context: CanvasRenderingContext2D,
  points: Projected[],
  fill: string,
  stroke?: string,
) {
  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  if (stroke) {
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function slab(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  region: number[],
  color: string,
  label: string,
) {
  const [x0, x1, y0, y1] = region;
  const top = [
    project(width, height, x0, y0, 0.025),
    project(width, height, x1, y0, 0.025),
    project(width, height, x1, y1, 0.025),
    project(width, height, x0, y1, 0.025),
  ];
  polygon(context, top, color, "rgba(255,255,255,.18)");
  const center = project(width, height, (x0 + x1) / 2, (y0 + y1) / 2, 0.04);
  context.fillStyle = "rgba(222,241,242,.8)";
  context.font = "600 10px ui-monospace, SFMono-Regular, Menlo, monospace";
  context.textAlign = "center";
  context.fillText(label.toUpperCase(), center.x, center.y);
}

function cuboid(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  pose: Pose,
  color: string,
  label: string,
) {
  const length = pose.agent_id === "carrier" ? 0.34 : 0.25;
  const breadth = pose.agent_id === "carrier" ? 0.22 : 0.18;
  const tall = pose.agent_id === "carrier" ? 0.22 : 0.17;
  const cosine = Math.cos(pose.yaw);
  const sine = Math.sin(pose.yaw);
  const corners = [
    [-length, -breadth],
    [length, -breadth],
    [length, breadth],
    [-length, breadth],
  ].map(([x, y]) => ({
    x: pose.x + x * cosine - y * sine,
    y: pose.y + x * sine + y * cosine,
  }));
  const bottom = corners.map((point) =>
    project(width, height, point.x, point.y, 0.02),
  );
  const top = corners.map((point) =>
    project(width, height, point.x, point.y, tall),
  );
  const carrier = pose.agent_id === "carrier";
  const gate = pose.agent_id === "gate";
  polygon(
    context,
    [bottom[1], bottom[2], top[2], top[1]],
    gate ? "#343f44" : carrier ? "#0b7779" : "#9a6721",
  );
  polygon(
    context,
    [bottom[2], bottom[3], top[3], top[2]],
    gate ? "#465158" : carrier ? "#0e9c9d" : "#c1842b",
  );
  polygon(context, top, color, "rgba(255,255,255,.45)");
  const center = project(width, height, pose.x, pose.y, tall + 0.03);
  if (!gate) {
    const nose = project(
      width,
      height,
      pose.x + Math.cos(pose.yaw) * length * 1.25,
      pose.y + Math.sin(pose.yaw) * length * 1.25,
      tall + 0.03,
    );
    context.strokeStyle = "#061012";
    context.lineWidth = 3;
    context.beginPath();
    context.moveTo(center.x, center.y);
    context.lineTo(nose.x, nose.y);
    context.stroke();
  }
  if (label) {
    context.fillStyle = "#e7f0f1";
    context.font = "700 10px ui-monospace, SFMono-Regular, Menlo, monospace";
    context.textAlign = "center";
    context.fillText(label, center.x, center.y - 18);
  }
}

function drawPath(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  points: MotionPoint[],
  untilStep: number,
  color: string,
) {
  const visible = points.filter((point) => point.step <= untilStep);
  if (visible.length < 2) return;
  context.strokeStyle = color;
  context.lineWidth = 3;
  context.setLineDash([7, 6]);
  context.beginPath();
  visible.forEach((point, index) => {
    const projected = project(width, height, point.x, point.y, 0.035);
    if (index === 0) context.moveTo(projected.x, projected.y);
    else context.lineTo(projected.x, projected.y);
  });
  context.stroke();
  context.setLineDash([]);
}

function drawCaptureRoot(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  pose: MotionPoint,
  label: string,
  color: string,
  pulse: number,
) {
  const point = project(width, height, pose.x, pose.y, 0.03);
  context.strokeStyle = color;
  context.lineWidth = 2;
  context.globalAlpha = 0.6 + pulse * 0.35;
  context.beginPath();
  context.ellipse(point.x, point.y, 15 + pulse * 5, 8 + pulse * 3, 0, 0, Math.PI * 2);
  context.stroke();
  context.globalAlpha = 1;
  context.fillStyle = color;
  context.font = "700 9px ui-monospace, SFMono-Regular, Menlo, monospace";
  context.textAlign = "left";
  context.fillText(label, point.x + 18, point.y - 8);
}

export function WorldReplay3D({
  bundle,
  chapterKind,
  chapterStep,
  animate,
  durationMs,
  label,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let animationFrame = 0;
    let cancelled = false;
    const carrierPoints = agentPoints(bundle, "carrier");
    const scoutPoints = agentPoints(bundle, "scout");
    const range = chapterRange(bundle, chapterKind, chapterStep);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const movingChapter = chapterKind === "move" || chapterKind === "act";
    const shouldAnimate = animate && movingChapter && !reduced;
    const started = performance.now();

    const render = (timestamp: number) => {
      if (cancelled) return;
      const ratio = shouldAnimate
        ? Math.min(1, Math.max(0, (timestamp - started) / durationMs))
        : movingChapter
          ? 1
          : 0;
      const currentStep =
        range.start + Math.round((range.end - range.start) * ratio);
      const deviceScale = Math.min(2, window.devicePixelRatio || 1);
      const bounds = canvas.getBoundingClientRect();
      const width = Math.max(1, Math.round(bounds.width));
      const height = Math.max(1, Math.round(bounds.height));
      const pixelWidth = Math.round(width * deviceScale);
      const pixelHeight = Math.round(height * deviceScale);
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
      context.clearRect(0, 0, width, height);

      const gradient = context.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, "#081217");
      gradient.addColorStop(1, "#101a1e");
      context.fillStyle = gradient;
      context.fillRect(0, 0, width, height);

      for (let x = FLOOR_X[0]; x < FLOOR_X[1]; x += 0.5) {
        for (let y = FLOOR_Y[0]; y < FLOOR_Y[1]; y += 0.5) {
          const parity = Math.round((x + y) * 2) % 2;
          polygon(
            context,
            [
              project(width, height, x, y),
              project(width, height, x + 0.5, y),
              project(width, height, x + 0.5, y + 0.5),
              project(width, height, x, y + 0.5),
            ],
            parity ? "#172329" : "#121d22",
            "rgba(95,126,136,.09)",
          );
        }
      }

      bundle.episode_meta.corridors.forEach((corridor, index) => {
        slab(
          context,
          width,
          height,
          corridor.region,
          index === 0 ? "rgba(21,213,208,.2)" : "rgba(131,229,110,.16)",
          corridor.id,
        );
      });

      const gateX = Math.min(
        ...bundle.episode_meta.corridors.map((corridor) => corridor.region[0]),
      );
      const gateLeft: Pose = {
        agent_id: "gate",
        step: currentStep,
        x: gateX - 0.12,
        y: -0.94,
        yaw: 0,
      };
      const gateRight: Pose = { ...gateLeft, y: 0.94 };
      cuboid(context, width, height, gateLeft, "#59646a", "");
      cuboid(context, width, height, gateRight, "#59646a", "");
      const gateLabel = project(width, height, gateX - 0.12, 0, 0.5);
      context.fillStyle = "rgba(211,224,226,.72)";
      context.font = "600 9px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.textAlign = "center";
      context.fillText("EVIDENCE GATE", gateLabel.x, gateLabel.y);

      drawPath(context, width, height, carrierPoints, currentStep, "#15d5d0");
      drawPath(context, width, height, scoutPoints, currentStep, "#f0b44d");

      const carrierPose = poseAt(carrierPoints, currentStep);
      const scoutPose = poseAt(scoutPoints, currentStep);
      if (carrierPose) {
        cuboid(
          context,
          width,
          height,
          { ...carrierPose, agent_id: "carrier" },
          "#15d5d0",
          "CARRIER",
        );
      }
      if (scoutPose) {
        cuboid(
          context,
          width,
          height,
          { ...scoutPose, agent_id: "scout" },
          "#f0b44d",
          "SCOUT",
        );
      }

      const pulse = (Math.sin(timestamp / 350) + 1) / 2;
      const selectedRootSteps = new Set(
        bundle.sensor_frames
          .filter(
            (frame) =>
              frame.corridor_id === bundle.outcome.selected_corridor,
          )
          .map((frame) => frame.step),
      );
      [...bundle.measurement_roots]
        .sort((a, b) => a.observed_step - b.observed_step)
        .filter(
          (root) =>
            root.observed_step <= currentStep &&
            selectedRootSteps.has(root.observed_step),
        )
        .forEach((root, index) => {
          const points =
            root.observer_agent_id === "scout" ? scoutPoints : carrierPoints;
          const rootPose = poseAt(points, root.observed_step);
          if (rootPose) {
            drawCaptureRoot(
              context,
              width,
              height,
              rootPose,
              `ROOT ${String(index + 1).padStart(2, "0")}`,
              root.observer_agent_id === "scout" ? "#f0b44d" : "#15d5d0",
              pulse,
            );
          }
        });

      context.fillStyle = "rgba(5,9,11,.88)";
      context.fillRect(16, 16, 310, 66);
      context.strokeStyle = "rgba(72,99,108,.65)";
      context.strokeRect(16, 16, 310, 66);
      context.textAlign = "left";
      context.fillStyle = "#dce7e9";
      context.font = "700 11px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText(label, 32, 42);
      context.fillStyle = movingChapter ? "#83e56e" : "#87969b";
      context.font = "600 9px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText(
        movingChapter
          ? `${chapterKind.toUpperCase()} · STEP ${currentStep}`
          : `HELD STATE · STEP ${currentStep}`,
        32,
        64,
      );

      if (shouldAnimate && ratio < 1) {
        animationFrame = requestAnimationFrame(render);
      }
    };

    animationFrame = requestAnimationFrame(render);
    return () => {
      cancelled = true;
      cancelAnimationFrame(animationFrame);
    };
  }, [
    animate,
    bundle,
    chapterKind,
    chapterStep,
    durationMs,
    label,
  ]);

  return (
    <div className="world-replay-3d">
      <canvas ref={canvasRef} aria-label={label} />
      <div className="world-replay-badge">
        <i />
        RECORDED TRAJECTORY REPLAY · SIMULATION ONLY
      </div>
      <div className="world-replay-legend">
        <span><i className="carrier" /> CARRIER</span>
        <span><i className="scout" /> SCOUT</span>
        <span>AMD GPU EVIDENCE</span>
      </div>
    </div>
  );
}
