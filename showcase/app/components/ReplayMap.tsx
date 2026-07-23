"use client";

import { useEffect, useRef } from "react";
import type { EpisodeBundle, MotionSegment } from "../lib/types";

type Props = {
  bundle: EpisodeBundle;
  motion?: MotionSegment;
  animate: boolean;
  label: string;
};

export function ReplayMap({ bundle, motion, animate, label }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let frame = 0;
    let cancelled = false;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reduced || !animate ? 1 : 2200;
    const started = performance.now();
    const points = motion?.trajectory_sample || [];
    const corridors = bundle.episode_meta.corridors || [];
    const allX = [
      ...corridors.flatMap((item) => [item.region[0], item.region[1]]),
      ...points.map((point) => point.x),
    ];
    const allY = [
      ...corridors.flatMap((item) => [item.region[2], item.region[3]]),
      ...points.map((point) => point.y),
    ];
    const minX = Math.min(-2.2, ...allX) - 0.3;
    const maxX = Math.max(3.0, ...allX) + 0.3;
    const minY = Math.min(-1.6, ...allY) - 0.2;
    const maxY = Math.max(1.6, ...allY) + 0.2;
    const scale = (x: number, y: number) => ({
      x: 24 + ((x - minX) / (maxX - minX)) * (canvas.width - 48),
      y: canvas.height - 24 - ((y - minY) / (maxY - minY)) * (canvas.height - 48),
    });
    const draw = (progress: number) => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = "#0b1115";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.strokeStyle = "rgba(122,145,154,.12)";
      context.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 32) {
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x, canvas.height);
        context.stroke();
      }
      for (let y = 0; y < canvas.height; y += 32) {
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(canvas.width, y);
        context.stroke();
      }
      corridors.forEach((corridor, index) => {
        const start = scale(corridor.region[0], corridor.region[2]);
        const end = scale(corridor.region[1], corridor.region[3]);
        context.fillStyle =
          index === 0 ? "rgba(21,213,208,.10)" : "rgba(240,180,77,.08)";
        context.strokeStyle =
          index === 0 ? "rgba(21,213,208,.55)" : "rgba(240,180,77,.45)";
        context.lineWidth = 2;
        context.fillRect(start.x, end.y, end.x - start.x, start.y - end.y);
        context.strokeRect(start.x, end.y, end.x - start.x, start.y - end.y);
        context.fillStyle = "#9aabb1";
        context.font = "11px ui-monospace, monospace";
        context.fillText(corridor.id.toUpperCase(), start.x + 7, end.y + 16);
      });
      if (!points.length) return;
      const last = Math.max(0, Math.floor((points.length - 1) * progress));
      context.strokeStyle =
        motion?.agent_id === "scout" ? "#f0b44d" : "#15d5d0";
      context.lineWidth = 4;
      context.beginPath();
      points.slice(0, last + 1).forEach((point, index) => {
        const next = scale(point.x, point.y);
        if (index === 0) context.moveTo(next.x, next.y);
        else context.lineTo(next.x, next.y);
      });
      context.stroke();
      const point = points[last];
      const marker = scale(point.x, point.y);
      context.fillStyle =
        motion?.agent_id === "scout" ? "#f0b44d" : "#15d5d0";
      context.fillRect(marker.x - 8, marker.y - 8, 16, 16);
      context.strokeStyle = "#071012";
      context.lineWidth = 2;
      context.strokeRect(marker.x - 8, marker.y - 8, 16, 16);
      context.fillStyle = "#dce7e9";
      context.font = "10px ui-monospace, monospace";
      context.fillText(
        motion?.agent_id?.toUpperCase() || "ROBOT",
        marker.x + 13,
        marker.y + 4,
      );
    };
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      draw(progress);
      if (progress < 1 && !cancelled) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [animate, bundle, motion]);

  return (
    <div className="replay-map">
      <div className="map-label">
        <span>RECORDED TRAJECTORY</span>
        <b>{label}</b>
      </div>
      <canvas ref={canvasRef} width={900} height={440} aria-label={label} />
      <div className="map-legend">
        <span><i className="carrier" /> CARRIER</span>
        <span><i className="scout" /> SCOUT</span>
        <span>SIMULATION ONLY</span>
      </div>
    </div>
  );
}
