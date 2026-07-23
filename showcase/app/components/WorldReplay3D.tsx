"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { EpisodeBundle, MotionPoint } from "../lib/types";
import type { ReplayChapterKind } from "../lib/replayDirector";
import {
  chapterStepAtProgress,
  createProjection,
  interpolatePose,
  sceneBounds,
  trajectoryPoints,
  type Bounds,
  type Box,
  type Projected,
  type Projection,
} from "../lib/worldGeometry";

type Props = {
  bundle: EpisodeBundle;
  chapterKind: ReplayChapterKind;
  chapterStep: number;
  progress: number;
  activeFrameStep: number;
  rootProgress: number;
  label: string;
  language: "en" | "zh";
};

type Pose = MotionPoint & { agent_id: "carrier" | "scout" };

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

function drawFloor(
  context: CanvasRenderingContext2D,
  projection: Projection,
  bounds: Bounds,
) {
  const step = 0.5;
  for (let x = Math.floor(bounds.minX / step) * step; x < bounds.maxX; x += step) {
    for (let y = Math.floor(bounds.minY / step) * step; y < bounds.maxY; y += step) {
      const parity = Math.round((x + y) / step) % 2;
      polygon(
        context,
        [
          projection.project(x, y),
          projection.project(x + step, y),
          projection.project(x + step, y + step),
          projection.project(x, y + step),
        ],
        parity ? "#152126" : "#111b1f",
        "rgba(121,151,157,.07)",
      );
    }
  }
}

function drawCorridor(
  context: CanvasRenderingContext2D,
  projection: Projection,
  region: number[],
  color: string,
) {
  const [x0, x1, y0, y1] = region;
  polygon(
    context,
    [
      projection.project(x0, y0, 0.015),
      projection.project(x1, y0, 0.015),
      projection.project(x1, y1, 0.015),
      projection.project(x0, y1, 0.015),
    ],
    color,
    "rgba(219,234,232,.2)",
  );
}

function drawPath(
  context: CanvasRenderingContext2D,
  projection: Projection,
  points: MotionPoint[],
  untilStep: number,
  color: string,
) {
  const visible = points.filter((point) => point.step <= untilStep);
  if (visible.length < 2) return;
  context.strokeStyle = color;
  context.lineWidth = 2.4;
  context.setLineDash([8, 7]);
  context.beginPath();
  visible.forEach((point, index) => {
    const screen = projection.project(point.x, point.y, 0.035);
    if (index === 0) context.moveTo(screen.x, screen.y);
    else context.lineTo(screen.x, screen.y);
  });
  context.stroke();
  context.setLineDash([]);
}

function drawGate(
  context: CanvasRenderingContext2D,
  projection: Projection,
  bundle: EpisodeBundle,
  admitted: boolean,
) {
  const x = Math.min(
    ...bundle.episode_meta.corridors.map((corridor) => corridor.region[0]),
  ) - 0.08;
  const y0 =
    Math.min(
      ...bundle.episode_meta.corridors.map((corridor) => corridor.region[2]),
    ) - 0.12;
  const y1 =
    Math.max(
      ...bundle.episode_meta.corridors.map((corridor) => corridor.region[3]),
    ) + 0.12;
  const start = projection.project(x, y0, 0.025);
  const end = projection.project(x, y1, 0.025);
  context.strokeStyle = admitted ? "#8adf72" : "#ff6f61";
  context.lineWidth = 4;
  context.setLineDash([6, 5]);
  context.beginPath();
  context.moveTo(start.x, start.y);
  context.lineTo(end.x, end.y);
  context.stroke();
  context.setLineDash([]);
}

function drawCollisionEnvelope(
  context: CanvasRenderingContext2D,
  projection: Projection,
  pose: Pose,
  collisionWidth: number,
  color: string,
) {
  const center = projection.project(pose.x, pose.y, 0.01);
  const xEdge = projection.project(
    pose.x + collisionWidth / 2,
    pose.y,
    0.01,
  );
  const yEdge = projection.project(
    pose.x,
    pose.y + collisionWidth / 2,
    0.01,
  );
  const radiusX = Math.max(6, Math.abs(xEdge.x - center.x));
  const radiusY = Math.max(4, Math.abs(yEdge.y - center.y));
  context.fillStyle = color;
  context.strokeStyle = color.replace(".14", ".52");
  context.lineWidth = 1.5;
  context.beginPath();
  context.ellipse(center.x, center.y, radiusX, radiusY, 0, 0, Math.PI * 2);
  context.fill();
  context.stroke();
}

function drawRobot(
  context: CanvasRenderingContext2D,
  projection: Projection,
  pose: Pose,
  collisionWidth: number,
  color: string,
): Box {
  const bodySize = collisionWidth * 0.68;
  const half = bodySize / 2;
  const height = Math.max(0.1, collisionWidth * 0.34);
  const cosine = Math.cos(pose.yaw);
  const sine = Math.sin(pose.yaw);
  const corners = [
    [-half, -half],
    [half, -half],
    [half, half],
    [-half, half],
  ].map(([x, y]) => ({
    x: pose.x + x * cosine - y * sine,
    y: pose.y + x * sine + y * cosine,
  }));
  const bottom = corners.map((point) =>
    projection.project(point.x, point.y, 0.025),
  );
  const top = corners.map((point) =>
    projection.project(point.x, point.y, height),
  );
  polygon(
    context,
    [bottom[1], bottom[2], top[2], top[1]],
    pose.agent_id === "carrier" ? "#08797a" : "#94661f",
  );
  polygon(
    context,
    [bottom[2], bottom[3], top[3], top[2]],
    pose.agent_id === "carrier" ? "#0d9898" : "#be842d",
  );
  polygon(context, top, color, "rgba(255,255,255,.48)");
  const center = projection.project(pose.x, pose.y, height + 0.02);
  const nose = projection.project(
    pose.x + Math.cos(pose.yaw) * half * 1.15,
    pose.y + Math.sin(pose.yaw) * half * 1.15,
    height + 0.02,
  );
  context.strokeStyle = "#071012";
  context.lineWidth = 2.5;
  context.beginPath();
  context.moveTo(center.x, center.y);
  context.lineTo(nose.x, nose.y);
  context.stroke();
  const all = [...bottom, ...top];
  return boxForPoints(all);
}

function boxesOverlap(a: Box, b: Box, padding = 0) {
  return !(
    a.x + a.width + padding <= b.x ||
    b.x + b.width + padding <= a.x ||
    a.y + a.height + padding <= b.y ||
    b.y + b.height + padding <= a.y
  );
}

function boxForPoints(points: Projected[]): Box {
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function drawLabel(
  context: CanvasRenderingContext2D,
  anchor: Projected,
  text: string,
  color: string,
  occupied: Box[],
  width: number,
  height: number,
) {
  context.font = "700 11px Inter, system-ui, sans-serif";
  const labelWidth = context.measureText(text).width + 18;
  const labelHeight = 25;
  const candidates: Box[] = [
    { x: anchor.x - labelWidth / 2, y: anchor.y - 47, width: labelWidth, height: labelHeight },
    { x: anchor.x + 18, y: anchor.y - 14, width: labelWidth, height: labelHeight },
    { x: anchor.x - labelWidth - 18, y: anchor.y - 14, width: labelWidth, height: labelHeight },
  ];
  const selected =
    candidates.find(
      (candidate) =>
        candidate.x >= 8 &&
        candidate.y >= 96 &&
        candidate.x + candidate.width <= width - 8 &&
        candidate.y + candidate.height <= height - 58 &&
        !occupied.some((box) => boxesOverlap(candidate, box, 5)),
    ) || candidates[0];
  context.fillStyle = "rgba(7,12,14,.9)";
  context.beginPath();
  context.roundRect(
    selected.x,
    selected.y,
    selected.width,
    selected.height,
    6,
  );
  context.fill();
  context.strokeStyle = color;
  context.lineWidth = 1;
  context.stroke();
  context.fillStyle = "#e7eeec";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(
    text,
    selected.x + selected.width / 2,
    selected.y + selected.height / 2,
  );
  occupied.push(selected);
}

function drawCaptureRoot(
  context: CanvasRenderingContext2D,
  projection: Projection,
  pose: MotionPoint,
  label: string,
  color: string,
  active: boolean,
) {
  const point = projection.project(pose.x, pose.y, 0.025);
  const direction = projection.project(
    pose.x + Math.cos(pose.yaw) * 0.65,
    pose.y + Math.sin(pose.yaw) * 0.65,
    0.03,
  );
  context.strokeStyle = color;
  context.lineWidth = active ? 2.4 : 1.2;
  context.setLineDash([4, 4]);
  context.beginPath();
  context.moveTo(point.x, point.y);
  context.lineTo(direction.x, direction.y);
  context.stroke();
  context.setLineDash([]);
  const directionAngle = Math.atan2(
    direction.y - point.y,
    direction.x - point.x,
  );
  context.fillStyle = color;
  context.beginPath();
  context.moveTo(direction.x, direction.y);
  context.lineTo(
    direction.x - Math.cos(directionAngle - 0.55) * 7,
    direction.y - Math.sin(directionAngle - 0.55) * 7,
  );
  context.lineTo(
    direction.x - Math.cos(directionAngle + 0.55) * 7,
    direction.y - Math.sin(directionAngle + 0.55) * 7,
  );
  context.closePath();
  context.fill();
  context.strokeStyle = color;
  context.lineWidth = active ? 2.8 : 1.5;
  if (active) {
    context.fillStyle = color.replace("#", "#") + "22";
    context.beginPath();
    context.ellipse(point.x, point.y, 22, 13, 0, 0, Math.PI * 2);
    context.fill();
  }
  context.beginPath();
  context.ellipse(point.x, point.y, 15, 8, 0, 0, Math.PI * 2);
  context.stroke();
  context.fillStyle = color;
  context.font = `${active ? "700" : "600"} 8px IBM Plex Mono, monospace`;
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  context.fillText(label, point.x + 18, point.y - 7);
}

function drawScale(
  context: CanvasRenderingContext2D,
  projection: Projection,
  width: number,
  height: number,
  language: "en" | "zh",
) {
  const x = 24;
  const y = height - 76;
  const length = projection.scale;
  context.strokeStyle = "#91a2a5";
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(x, y);
  context.lineTo(x + length, y);
  context.moveTo(x, y - 4);
  context.lineTo(x, y + 4);
  context.moveTo(x + length, y - 4);
  context.lineTo(x + length, y + 4);
  context.stroke();
  context.fillStyle = "#91a2a5";
  context.font = "600 9px IBM Plex Mono, monospace";
  context.textAlign = "left";
  context.fillText("1 m", x, y - 9);
  context.fillText(
    language === "zh" ? "录制的世界坐标" : "RECORDED WORLD COORDINATES",
    Math.min(width - 185, x + length + 18),
    y + 3,
  );
}

export function WorldReplay3D({
  bundle,
  chapterKind,
  chapterStep,
  progress,
  activeFrameStep,
  rootProgress,
  label,
  language,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 1, height: 1 });
  const bounds = useMemo(() => sceneBounds(bundle), [bundle]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      setSize({
        width: Math.max(1, Math.round(entry.contentRect.width)),
        height: Math.max(1, Math.round(entry.contentRect.height)),
      });
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const moving = chapterKind === "move" || chapterKind === "act";
    const effectiveProgress = reduced && moving ? 1 : progress;
    const currentStep = chapterStepAtProgress(
      bundle,
      chapterKind,
      chapterStep,
      effectiveProgress,
    );
    const deviceScale = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(size.width * deviceScale);
    canvas.height = Math.round(size.height * deviceScale);
    context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
    context.clearRect(0, 0, size.width, size.height);

    const gradient = context.createLinearGradient(0, 0, 0, size.height);
    gradient.addColorStop(0, "#091216");
    gradient.addColorStop(1, "#121c20");
    context.fillStyle = gradient;
    context.fillRect(0, 0, size.width, size.height);

    const projection = createProjection(size.width, size.height, bounds);
    drawFloor(context, projection, bounds);
    bundle.episode_meta.corridors.forEach((corridor, index) =>
      drawCorridor(
        context,
        projection,
        corridor.region,
        index === 0 ? "rgba(34,194,190,.16)" : "rgba(139,217,113,.13)",
      ),
    );

    const gate = bundle.gate_receipts
      .filter((receipt) => receipt.evaluated_step <= currentStep)
      .at(-1);
    drawGate(context, projection, bundle, Boolean(gate?.effective_admit));

    const carrierPoints = trajectoryPoints(bundle, "carrier");
    const scoutPoints = trajectoryPoints(bundle, "scout");
    drawPath(context, projection, carrierPoints, currentStep, "#26c7c3");
    drawPath(context, projection, scoutPoints, currentStep, "#efb34f");

    const selectedRootSteps = new Set(
      bundle.sensor_frames
        .filter(
          (frame) => frame.corridor_id === bundle.outcome.selected_corridor,
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
        const rootPose = interpolatePose(points, root.observed_step);
        if (rootPose) {
          drawCaptureRoot(
            context,
            projection,
            rootPose,
            `ROOT ${String(index + 1).padStart(2, "0")} · ${
              root.observer_agent_id === "scout"
                ? language === "zh"
                  ? "侦察车"
                  : "SCOUT"
                : language === "zh"
                  ? "主车"
                  : "CARRIER"
            }`,
            root.observer_agent_id === "scout" ? "#efb34f" : "#26c7c3",
            root.observed_step === activeFrameStep,
          );
        }
      });

    const geometry = bundle.episode_meta.agent_geometry;
    const robots: Array<{
      pose: Pose;
      width: number;
      color: string;
      envelope: string;
      label: string;
    }> = [];
    const carrier = interpolatePose(carrierPoints, currentStep);
    const scout = interpolatePose(scoutPoints, currentStep);
    if (carrier) {
      robots.push({
        pose: { ...carrier, agent_id: "carrier" },
        width: geometry?.carrier.collision_width_m || 0.55,
        color: "#20d0cb",
        envelope: "rgba(32,208,203,.14)",
        label: language === "zh" ? "载具" : "CARRIER",
      });
    }
    if (scout) {
      robots.push({
        pose: { ...scout, agent_id: "scout" },
        width: geometry?.scout.collision_width_m || 0.32,
        color: "#f0b64f",
        envelope: "rgba(240,182,79,.14)",
        label: language === "zh" ? "侦察车" : "SCOUT",
      });
    }
    robots.forEach((robot) =>
      drawCollisionEnvelope(
        context,
        projection,
        robot.pose,
        robot.width,
        robot.envelope,
      ),
    );
    robots.sort(
      (a, b) =>
        projection.project(a.pose.x, a.pose.y).y -
        projection.project(b.pose.x, b.pose.y).y,
    );
    const bodyBoxes: Box[] = [];
    const labelAnchors: Array<{
      anchor: Projected;
      text: string;
      color: string;
    }> = [];
    robots.forEach((robot) => {
      const box = drawRobot(
        context,
        projection,
        robot.pose,
        robot.width,
        robot.color,
      );
      bodyBoxes.push(box);
      labelAnchors.push({
        anchor: {
          x: box.x + box.width / 2,
          y: box.y,
        },
        text: robot.label,
        color: robot.color,
      });
    });
    const occupied = [...bodyBoxes];
    labelAnchors.forEach((item) =>
      drawLabel(
        context,
        item.anchor,
        item.text,
        item.color,
        occupied,
        size.width,
        size.height,
      ),
    );

    drawScale(context, projection, size.width, size.height, language);
  }, [
    bounds,
    bundle,
    chapterKind,
    chapterStep,
    progress,
    activeFrameStep,
    language,
    size.height,
    size.width,
  ]);

  return (
    <div className="world-replay-3d">
      <canvas ref={canvasRef} aria-label={label} />
      <div className="world-stage-heading">
        <span>{label}</span>
        <b>
          {chapterKind === "act"
            ? language === "zh" ? "动作已获准" : "ACTION QUALIFIED"
            : chapterKind === "move"
              ? language === "zh" ? "正在移动修复证据" : "EVIDENCE REPAIR IN MOTION"
              : language === "zh" ? "机器人保持停止" : "ROBOT HELD"}
        </b>
      </div>
      <div className="world-replay-badge">
        <i />
        {language === "zh"
          ? "录制轨迹回放 · 仅限仿真"
          : "RECORDED TRAJECTORY REPLAY · SIMULATION ONLY"}
      </div>
      <div className="root-progress-badge">
        <span>{language === "zh" ? "独立证据根" : "INDEPENDENT ROOTS"}</span>
        <b>{rootProgress}/2</b>
      </div>
      <div className="world-replay-legend">
        <span><i className="carrier" /> {language === "zh" ? "载具" : "CARRIER"}</span>
        <span><i className="scout" /> {language === "zh" ? "侦察车" : "SCOUT"}</span>
        <span>{language === "zh"
          ? "示意车体与观察方向 · 录制位姿、朝向与碰撞宽度"
          : "SCHEMATIC BODIES + VIEW DIRECTION · RECORDED POSE, YAW + COLLISION WIDTH"}</span>
      </div>
    </div>
  );
}
