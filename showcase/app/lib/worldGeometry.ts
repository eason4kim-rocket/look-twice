import type { EpisodeBundle, MotionPoint } from "./types";
import type { ReplayChapterKind } from "./replayDirector";

export type Projected = { x: number; y: number };
export type Bounds = { minX: number; maxX: number; minY: number; maxY: number };
export type Box = { x: number; y: number; width: number; height: number };
export type Projection = {
  project: (x: number, y: number, z?: number) => Projected;
  scale: number;
};

const ISO_DEPTH = 0.58;
const ISO_HEIGHT = 1.28;

export function trajectoryPoints(bundle: EpisodeBundle, agentId: string) {
  return bundle.motion_segments
    .filter((motion) => motion.agent_id === agentId)
    .flatMap((motion) => motion.trajectory_sample)
    .sort((a, b) => a.step - b.step);
}

export function interpolatePose(
  points: MotionPoint[],
  step: number,
): MotionPoint | undefined {
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
  const ratio = Math.max(0, Math.min(1, (step - before.step) / span));
  return {
    step,
    x: before.x + (after.x - before.x) * ratio,
    y: before.y + (after.y - before.y) * ratio,
    yaw: before.yaw + (after.yaw - before.yaw) * ratio,
  };
}

export function sceneBounds(bundle: EpisodeBundle): Bounds {
  const xs: number[] = [];
  const ys: number[] = [];
  bundle.motion_segments.forEach((motion) => {
    motion.trajectory_sample.forEach((point) => {
      xs.push(point.x);
      ys.push(point.y);
    });
  });
  bundle.episode_meta.corridors.forEach((corridor) => {
    const [x0, x1, y0, y1] = corridor.region;
    xs.push(x0, x1);
    ys.push(y0, y1);
  });
  return {
    minX: Math.min(...xs) - 0.7,
    maxX: Math.max(...xs) + 0.7,
    minY: Math.min(...ys) - 0.65,
    maxY: Math.max(...ys) + 0.65,
  };
}

function isoCoordinates(x: number, y: number, z = 0) {
  return {
    u: x - y,
    v: (x + y) * ISO_DEPTH - z * ISO_HEIGHT,
  };
}

export function createProjection(
  width: number,
  height: number,
  bounds: Bounds,
): Projection {
  const corners = [
    isoCoordinates(bounds.minX, bounds.minY),
    isoCoordinates(bounds.minX, bounds.maxY),
    isoCoordinates(bounds.maxX, bounds.minY),
    isoCoordinates(bounds.maxX, bounds.maxY),
  ];
  const minU = Math.min(...corners.map((point) => point.u));
  const maxU = Math.max(...corners.map((point) => point.u));
  const minV = Math.min(...corners.map((point) => point.v));
  const maxV = Math.max(...corners.map((point) => point.v));
  const horizontalPadding = Math.max(34, width * 0.055);
  const topPadding = Math.max(105, height * 0.22);
  const bottomPadding = Math.max(74, height * 0.15);
  const scale = Math.min(
    (width - horizontalPadding * 2) / Math.max(0.01, maxU - minU),
    (height - topPadding - bottomPadding) / Math.max(0.01, maxV - minV),
  );
  const availableWidth = width - horizontalPadding * 2;
  const availableHeight = height - topPadding - bottomPadding;
  const renderedWidth = (maxU - minU) * scale;
  const renderedHeight = (maxV - minV) * scale;
  const offsetX =
    horizontalPadding + Math.max(0, (availableWidth - renderedWidth) / 2);
  const offsetY =
    topPadding + Math.max(0, (availableHeight - renderedHeight) / 2);
  return {
    scale,
    project(x: number, y: number, z = 0) {
      const point = isoCoordinates(x, y, z);
      return {
        x: offsetX + (point.u - minU) * scale,
        y: offsetY + (point.v - minV) * scale,
      };
    },
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
    if (motions.length) {
      const admittedStep = bundle.gate_receipts.find(
        (gate) =>
          gate.corridor_id === bundle.outcome.selected_corridor &&
          gate.effective_admit,
      )?.evaluated_step;
      return {
        start: Math.min(...motions.map((motion) => motion.start_step)),
        // MOVE owns every recorded physical pose up to the repaired Gate.
        // Ending at the scout segment used to skip the carrier's recorded
        // approach and made the blue body jump at MOVE → REPAIR.
        end:
          admittedStep !== undefined
            ? Math.max(
                Math.min(...motions.map((motion) => motion.start_step)),
                admittedStep - 1,
              )
            : Math.max(...motions.map((motion) => motion.end_step)),
      };
    }
  }
  if (chapterKind === "act") {
    const carrier = bundle.motion_segments.filter(
      (motion) => motion.agent_id === "carrier",
    );
    if (carrier.length) {
      const deniedStep =
        bundle.gate_receipts.find((gate) => !gate.effective_admit)
          ?.evaluated_step || chapterStep;
      const admittedStep = bundle.gate_receipts.find(
        (gate) => gate.effective_admit,
      )?.evaluated_step;
      return {
        start: admittedStep || deniedStep,
        end: Math.max(...carrier.map((motion) => motion.end_step)),
      };
    }
  }
  return { start: chapterStep, end: chapterStep };
}

export function chapterStepAtProgress(
  bundle: EpisodeBundle,
  chapterKind: ReplayChapterKind,
  chapterStep: number,
  progress: number,
) {
  const range = chapterRange(bundle, chapterKind, chapterStep);
  const ratio = Math.max(0, Math.min(1, progress));
  return range.start + Math.round((range.end - range.start) * ratio);
}

function boxForPoints(points: Projected[]): Box {
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

export function projectedRobotBox(
  projection: Projection,
  pose: MotionPoint,
  collisionWidth: number,
) {
  const half = (collisionWidth * 0.68) / 2;
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
  return boxForPoints([
    ...corners.map((point) => projection.project(point.x, point.y, 0.025)),
    ...corners.map((point) => projection.project(point.x, point.y, height)),
  ]);
}

export function boxOverlapRatio(a: Box, b: Box) {
  const width = Math.max(
    0,
    Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x),
  );
  const height = Math.max(
    0,
    Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y),
  );
  const intersection = width * height;
  return intersection / Math.max(1, Math.min(a.width * a.height, b.width * b.height));
}
