"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { buildReplayChapters, resolveChapterState } from "../lib/replayDirector";
import {
  advanceTimeline,
  timelineDurations,
} from "../lib/replayTimeline";
import type { EpisodeBundle, ReleaseProfile } from "../lib/types";
import { ReplayMap } from "./ReplayMap";
import { useLanguage } from "./SiteShell";
import "./console.css";
import "./judge-console.css";
import "./recorded.css";

type Manifest = {
  default_candidate_id: string;
  profiles: Array<{ candidate_id: string; href: string }>;
  replays: Array<{
    replay_id: string;
    candidate_id: string;
    policy: string;
    route_mode: string;
    repair_success: boolean;
    href: string;
  }>;
};

export function EvidenceConsole() {
  const { language, setLanguage } = useLanguage();
  const zh = language === "zh";
  const tx = (en: string, cn: string) => (zh ? cn : en);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [profile, setProfile] = useState<ReleaseProfile | null>(null);
  const [bundle, setBundle] = useState<EpisodeBundle | null>(null);
  const [replayId, setReplayId] = useState("");
  const [chapterIndex, setChapterIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sensorMode, setSensorMode] = useState<"rgb" | "depth" | "mask">("rgb");
  const [cinematic, setCinematic] = useState(false);
  const requestedReplay = useRef("");
  const requestedAutoplay = useRef(false);
  const autoplayStarted = useRef(false);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    requestedReplay.current = query.get("replay") || "";
    requestedAutoplay.current = query.get("autoplay") === "1";
    const isCinematic = query.get("cinematic") === "1";
    setCinematic(isCinematic);
    if (query.get("locale") === "zh") setLanguage("zh");
    if (query.get("locale") === "en") setLanguage("en");
    document.documentElement.classList.toggle("cinematic-page", isCinematic);
    return () => document.documentElement.classList.remove("cinematic-page");
  }, [setLanguage]);

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((response) => {
        if (!response.ok) throw new Error("manifest unavailable");
        return response.json();
      })
      .then((next: Manifest) => {
        setManifest(next);
        setCandidateId(next.default_candidate_id);
      });
  }, []);

  useEffect(() => {
    if (!manifest || !candidateId) return;
    const href = manifest.profiles.find(
      (item) => item.candidate_id === candidateId,
    )?.href;
    if (!href) return;
    fetch(href)
      .then((response) => response.json())
      .then((next: ReleaseProfile) => {
        setProfile(next);
        const requested = manifest.replays.find(
          (item) =>
            item.candidate_id === candidateId &&
            item.replay_id === requestedReplay.current,
        );
        setReplayId(requested?.replay_id || next.default_replays[0] || "");
      });
  }, [manifest, candidateId]);

  useEffect(() => {
    const row = manifest?.replays.find((item) => item.replay_id === replayId);
    if (!row) return;
    fetch(row.href)
      .then((response) => response.json())
      .then((next: EpisodeBundle) => {
        setBundle(next);
        setChapterIndex(0);
        setPlaying(false);
        autoplayStarted.current = false;
      });
  }, [manifest, replayId]);

  const chapters = useMemo(
    () => (bundle ? buildReplayChapters(bundle, zh) : []),
    [bundle, zh],
  );
  const chapter = chapters[chapterIndex];
  const state = useMemo(
    () => (bundle && chapter ? resolveChapterState(bundle, chapter) : undefined),
    [bundle, chapter],
  );

  useEffect(() => {
    if (
      !bundle ||
      !chapters.length ||
      !requestedAutoplay.current ||
      autoplayStarted.current
    ) {
      return;
    }
    autoplayStarted.current = true;
    setPlaying(true);
  }, [bundle, chapters.length]);

  useEffect(() => {
    if (!playing || !chapters.length) return;
    const durations = timelineDurations(Boolean(bundle?.outcome.repair_attempted));
    const timer = window.setTimeout(() => {
      setChapterIndex((current) => {
        const next = advanceTimeline(current, chapters.length);
        setPlaying(next.playing);
        return next.chapterIndex;
      });
    }, durations[chapterIndex] || 4000);
    return () => window.clearTimeout(timer);
  }, [playing, chapterIndex, chapters.length, bundle]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!chapters.length) return;
      if (event.key === "ArrowRight") {
        setChapterIndex((value) => Math.min(chapters.length - 1, value + 1));
        setPlaying(false);
      }
      if (event.key === "ArrowLeft") {
        setChapterIndex((value) => Math.max(0, value - 1));
        setPlaying(false);
      }
      if (event.key === " ") {
        event.preventDefault();
        setPlaying((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chapters.length]);

  if (!manifest || !profile || !bundle || !chapter || !state) {
    return <div className="loading">LOADING VERIFIED EVIDENCE PACK…</div>;
  }

  const frames = state.frameIds
    .map((frameId) =>
      bundle.sensor_frames.find((frame) => frame.frame_id === frameId),
    )
    .filter((frame): frame is EpisodeBundle["sensor_frames"][number] =>
      Boolean(frame),
    );
  const frame = frames.at(-1) || bundle.sensor_frames[0];
  const request = chapter.requestId
    ? bundle.repair_requests.find(
        (candidate) => candidate.request_id === chapter.requestId,
      )
    : undefined;
  const denied = state.gate && !state.gate.effective_admit;
  const admitted = Boolean(state.gate?.effective_admit);
  const qualifyingRootCount = admitted ? 2 : 1;
  const showMap = chapter.kind === "move" || chapter.kind === "act";
  const nextView = String(request?.target_viewpoint || "diagnostic side view")
    .replaceAll("_", " ")
    .toUpperCase();

  const restartOrToggle = () => {
    if (chapterIndex === chapters.length - 1) {
      setChapterIndex(0);
      setPlaying(true);
      return;
    }
    setPlaying((value) => !value);
  };

  return (
    <main className={"console-wrap " + (cinematic ? "cinematic" : "")}>
      {!cinematic && (
        <div className="console-toolbar">
          <label>
            <span>{tx("ACTIVE CANDIDATE", "当前候选")}</span>
            <select
              aria-label="Candidate"
              value={candidateId}
              onChange={(event) => setCandidateId(event.target.value)}
            >
              {manifest.profiles.map((item) => (
                <option key={item.candidate_id} value={item.candidate_id}>
                  {item.candidate_id.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{tx("REPLAY", "证据回放")}</span>
            <select
              aria-label="Replay"
              value={replayId}
              onChange={(event) => setReplayId(event.target.value)}
            >
              {manifest.replays
                .filter((item) => item.candidate_id === candidateId)
                .map((item) => (
                  <option key={item.replay_id} value={item.replay_id}>
                    {item.policy.includes("active")
                      ? tx("ACTIVE · REPAIR → DIRECT", "主动 · 修证 → 直行")
                      : tx("PASSIVE · DENY → DETOUR", "被动 · 拒绝 → 绕行")}
                  </option>
                ))}
            </select>
          </label>
          <div className="evidence-labels">
            <span>RECORDED AMD GPU EVIDENCE</span>
            <span>SIMULATION ONLY</span>
            <span>FROZEN ARTIFACT</span>
          </div>
        </div>
      )}

      <section className={"judge-stage story-" + chapter.kind}>
        <div className="judge-copy">
          <span>
            {tx("THE QUESTION", "核心问题")} · {chapter.label} ·{" "}
            {String(chapterIndex + 1).padStart(2, "0")}/
            {String(chapters.length).padStart(2, "0")}
          </span>
          <h1>{chapter.title}</h1>
          <p>{chapter.body}</p>
          <div className="judge-actions">
            <button className="big-play" onClick={restartOrToggle}>
              <i>{playing ? "Ⅱ" : "▶"}</i>
              <span>
                <b>
                  {playing
                    ? tx("PAUSE THE LOOP", "暂停闭环")
                    : chapterIndex === chapters.length - 1
                      ? tx("REPLAY 30 SECONDS", "重播 30 秒")
                      : tx("PLAY THE 30-SECOND LOOP", "播放 30 秒闭环")}
                </b>
                <small>
                  {tx(
                    "Claim → Purify → repair → action",
                    "Claim → Purify → 修证 → 行动",
                  )}
                </small>
              </span>
            </button>
            <div className="why-card">
              <span>{tx("WHY DID IT STOP?", "为什么停下？")}</span>
              <b>
                {admitted
                  ? tx("THE EVIDENCE CONTRACT IS REPAIRED", "证据合同已修复")
                  : denied
                    ? humanReason(state.gate?.reasons[0], zh)
                    : tx("EVIDENCE IS BEING QUALIFIED", "正在审查证据资格")}
              </b>
            </div>
          </div>
        </div>
        <div className="chapter-rail">
          {chapters.map((item, index) => (
            <button
              key={item.id}
              className={
                (index < chapterIndex ? "done " : "") +
                (index === chapterIndex ? "current" : "")
              }
              onClick={() => {
                setChapterIndex(index);
                setPlaying(false);
              }}
            >
              <i>{index < chapterIndex ? "✓" : index + 1}</i>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        <div className="headline-facts">
          <Fact
            label={tx("QUALIFYING ROOTS", "合格证据根")}
            value={String(qualifyingRootCount)}
          />
          <Fact
            label={tx("AUTHORIZATION", "动作授权")}
            value={admitted ? "ADMIT" : denied ? "DENY" : "PENDING"}
            tone={admitted ? "pass" : denied ? "fail" : "pending"}
          />
          <Fact
            label={tx("FINAL ROUTE", "最终路线")}
            value={state.routeMode.toUpperCase()}
            tone={state.revealOutcome ? "pass" : "pending"}
          />
        </div>
      </section>

      <section className="visual-stage">
        <div className="visual-primary">
          {showMap ? (
            <ReplayMap
              bundle={bundle}
              motion={state.motion}
              animate={playing || chapter.kind === "move" || chapter.kind === "act"}
              label={
                chapter.kind === "move"
                  ? tx("SCOUT MOVES TO THE DIAGNOSTIC VIEW", "SCOUT 移动到诊断视角")
                  : state.routeMode === "direct"
                    ? tx("AUTHORIZED DIRECT CROSSING", "已授权的直接通行")
                    : tx("SAFE DETOUR", "安全绕行")
              }
            />
          ) : chapter.kind === "repair" && frames.length > 1 ? (
            <div className="frame-compare">
              <FrameView
                frame={frames[0]}
                mode={sensorMode}
                label={tx("BEFORE · ROOT 01", "之前 · ROOT 01")}
              />
              <div className="compare-arrow">→</div>
              <FrameView
                frame={frames.at(-1)!}
                mode={sensorMode}
                label={tx("AFTER · ROOT 02", "之后 · ROOT 02")}
              />
            </div>
          ) : (
            <FrameView
              frame={frame}
              mode={sensorMode}
              label={
                chapter.kind === "observe"
                  ? tx("INITIAL FRONT VIEW · ROOT 01", "初始正面视角 · ROOT 01")
                  : tx("THE CLAIM IS CLEAR; THE CONTRACT IS NOT", "CLAIM 为 CLEAR；合同仍不满足")
              }
            />
          )}
        </div>
        <aside className="decision-summary">
          <span>{tx("CURRENT DECISION", "当前决策")}</span>
          <strong className={admitted ? "pass" : denied ? "fail" : "pending"}>
            {admitted ? "ADMITTED" : denied ? "DENIED" : "EVALUATING"}
          </strong>
          <p>
            {admitted
              ? tx(
                  "A new independent root changed the action qualification.",
                  "新的独立证据根改变了动作资格。",
                )
              : denied
                ? tx("Direct action is not qualified yet.", "直行动作尚未获得资格。")
                : tx("Sensor claims are being checked.", "正在检查传感器 Claim。")}
          </p>
          <div className="decision-next">
            <span>
              {admitted
                ? tx("WHAT CHANGED", "发生了什么变化")
                : tx("NEXT BEST VIEW", "下一最佳视角")}
            </span>
            <b>{admitted ? "PYTHON ∧ PURIFY ADMIT" : nextView}</b>
            <small>
              {admitted
                ? tx("NEW ROOT · CALIBRATED · TRACEABLE", "新根 · 已校准 · 可追溯")
                : tx("TARGETED EVIDENCE REPAIR", "定向证据修复")}
            </small>
          </div>
          <div className="contract-mini-live">
            <ContractLine
              label={tx("Fresh calibrated evidence", "证据新鲜且校准适用")}
              pass={!state.gate?.reasons?.includes("stale")}
            />
            <ContractLine
              label={tx("Independent side-view root", "独立侧视采集根")}
              pass={
                state.gate
                  ? !state.gate.reasons.includes("missing_side_view_vision_root")
                  : undefined
              }
            />
            <ContractLine
              label="Python ∧ Purify"
              pass={state.gate?.effective_admit}
            />
          </div>
        </aside>
      </section>

      <section className="evidence-strip">
        <div className="sensor-switch">
          {(["rgb", "depth", "mask"] as const).map((mode) => (
            <button
              key={mode}
              className={sensorMode === mode ? "active" : ""}
              onClick={() => setSensorMode(mode)}
            >
              {mode === "mask" ? "CORRIDOR MASK" : mode.toUpperCase()}
            </button>
          ))}
        </div>
        <Metric label="P(BLOCKED)" value={formatP(frame?.p_blocked)} />
        <Metric
          label={tx("PREDICTION SET", "预测集")}
          value={"{" + (frame?.prediction_set?.join(", ") || "—") + "}"}
        />
        <Metric label="CLAIM" value={(frame?.value || "—").toUpperCase()} accent />
        <Metric
          label="PYTHON GATE"
          value={state.gate?.python_admitted ? "ADMIT" : state.gate ? "DENY" : "—"}
        />
        <Metric
          label="PURIFY GO"
          value={state.gate?.purify_go_admitted ? "ADMIT" : state.gate ? "DENY" : "—"}
        />
      </section>

      {state.revealOutcome && (
        <section className="comparison-card">
          <div>
            <span>ACTIVE</span>
            <b>REPAIR EVIDENCE → DIRECT</b>
            <small>Independent root · Python ∧ Purify admit</small>
          </div>
          <div>
            <span>PASSIVE</span>
            <b>NO REPAIR → SAFE DETOUR</b>
            <small>Safe, but pays for unresolved uncertainty</small>
          </div>
          <div className="safe-result">
            <span>UNSAFE CROSSINGS</span>
            <b>0</b>
            <small>Recorded Genesis + AMD GPU evidence</small>
          </div>
        </section>
      )}

      {!cinematic && (
        <>
          <section className="timeline-panel">
            <div className="playback">
              <button
                aria-label={tx("Previous chapter", "上一章")}
                onClick={() => {
                  setChapterIndex(Math.max(0, chapterIndex - 1));
                  setPlaying(false);
                }}
              >
                ‹
              </button>
              <button className="play" onClick={restartOrToggle}>
                {playing ? "Ⅱ" : "▶"}
              </button>
              <button
                aria-label={tx("Next chapter", "下一章")}
                onClick={() => {
                  setChapterIndex(
                    Math.min(chapters.length - 1, chapterIndex + 1),
                  );
                  setPlaying(false);
                }}
              >
                ›
              </button>
              <span>
                {tx("GUIDED LOOP", "引导回放")} ·{" "}
                {String(chapterIndex + 1).padStart(2, "0")} /{" "}
                {String(chapters.length).padStart(2, "0")}
              </span>
            </div>
            <div className="timeline">
              {chapters.map((item, index) => (
                <button
                  key={item.id}
                  title={item.label}
                  className={
                    (index <= chapterIndex ? "seen " : "") +
                    (index === chapterIndex ? "current" : "")
                  }
                  onClick={() => {
                    setChapterIndex(index);
                    setPlaying(false);
                  }}
                >
                  <i />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
            <a
              className="raw-link"
              href={"/data/replays/" + replayId + ".json"}
              target="_blank"
            >
              RAW JSON ↗
            </a>
          </section>
          <details className="technical-details">
            <summary>{tx("Technical trace and integrity", "技术追溯与完整性")}</summary>
            <div>
              <span>
                SOURCE <b>{bundle.integrity.source_episode_sha256.slice(0, 16)}…</b>
              </span>
              <span>
                BUNDLE <b>{bundle.integrity.bundle_sha256.slice(0, 16)}…</b>
              </span>
              <span>
                GATE <b>{state.gate?.gate_id || "—"}</b>
              </span>
              <span>
                LIVE GPU DEPENDENCY <b>NONE</b>
              </span>
            </div>
          </details>
        </>
      )}
      {cinematic && (
        <div className="cinematic-footer">
          <b>LOOK TWICE</b>
          <span>AMD GPU · GENESIS · PURIFY · SIMULATION ONLY</span>
        </div>
      )}
    </main>
  );
}

function FrameView({
  frame,
  mode,
  label,
}: {
  frame: EpisodeBundle["sensor_frames"][number];
  mode: "rgb" | "depth" | "mask";
  label: string;
}) {
  const source = frame.media[mode === "mask" ? "corridor_mask" : mode];
  return (
    <div className="judge-frame">
      <Image
        fill
        unoptimized
        className="recorded-frame"
        src={source}
        alt={mode + " evidence at " + frame.viewpoint}
      />
      <div className="frame-top">
        <b>{label}</b>
        <span>{frame.tensor_device}</span>
      </div>
      <div className="frame-bottom">
        <span>{frame.corridor_id} · {frame.viewpoint}</span>
        <b>CLAIM: {frame.value.toUpperCase()}</b>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div>
      <span>{label}</span>
      <b className={tone}>{value}</b>
    </div>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div>
      <span>{label}</span>
      <b className={accent ? "accent" : ""}>{value}</b>
    </div>
  );
}

function ContractLine({
  label,
  pass,
}: {
  label: string;
  pass?: boolean;
}) {
  return (
    <div>
      <i className={pass === undefined ? "pending" : pass ? "pass" : "fail"}>
        {pass === undefined ? "·" : pass ? "✓" : "×"}
      </i>
      <span>{label}</span>
      <b>{pass === undefined ? "WAIT" : pass ? "PASS" : "OPEN"}</b>
    </div>
  );
}

function formatP(value?: number) {
  if (value === undefined) return "—";
  if (value < 0.001) return value.toExponential(1);
  return value.toFixed(3);
}

function humanReason(reason: string | undefined, zh: boolean) {
  const reasons: Record<string, [string, string]> = {
    missing_side_view_vision_root: [
      "MISSING INDEPENDENT SIDE-VIEW EVIDENCE",
      "缺少独立侧视证据",
    ],
    insufficient_roots: [
      "NOT ENOUGH INDEPENDENT MEASUREMENT ROOTS",
      "独立测量根不足",
    ],
    purify_go_denied: [
      "PURIFY GO DID NOT AUTHORIZE THE ACTION",
      "PURIFY GO 未授权该动作",
    ],
  };
  return (
    reasons[reason || ""] || [
      "EVIDENCE DOES NOT SATISFY THE ACTION CONTRACT",
      "证据尚未满足动作合同",
    ]
  )[zh ? 1 : 0];
}
