"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { buildReplayChapters, resolveChapterState } from "../lib/replayDirector";
import {
  chapterProgress,
  createPlaybackState,
  seekPlayback,
  tickPlayback,
  timelineDurations,
  togglePlayback,
} from "../lib/replayTimeline";
import type { EpisodeBundle, ReleaseProfile } from "../lib/types";
import { useLanguage } from "./SiteShell";
import { WorldReplay3D } from "./WorldReplay3D";
import "./industrial-console.css";

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
  const { language } = useLanguage();
  const zh = language === "zh";
  const tx = (en: string, cn: string) => (zh ? cn : en);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [profile, setProfile] = useState<ReleaseProfile | null>(null);
  const [bundle, setBundle] = useState<EpisodeBundle | null>(null);
  const [replayId, setReplayId] = useState("");
  const [playback, setPlayback] = useState(() => createPlaybackState(false));
  const chapterIndex = playback.chapterIndex;
  const playing = playback.playing;
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
    const stateTimer = window.setTimeout(() => setCinematic(isCinematic), 0);
    document.documentElement.classList.toggle("cinematic-page", isCinematic);
    return () => {
      window.clearTimeout(stateTimer);
      document.documentElement.classList.remove("cinematic-page");
    };
  }, []);

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
        setPlayback(createPlaybackState(false));
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
    setPlayback(createPlaybackState(true));
  }, [bundle, chapters.length]);

  useEffect(() => {
    if (!playback.playing || !chapters.length || !bundle) return;
    const durations = timelineDurations(Boolean(bundle?.outcome.repair_attempted));
    let animationFrame = 0;
    let previous = performance.now();
    const update = (now: number) => {
      const delta = Math.max(0, now - previous);
      previous = now;
      setPlayback((current) => tickPlayback(current, delta, durations));
      animationFrame = requestAnimationFrame(update);
    };
    animationFrame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(animationFrame);
  }, [playback.playing, chapters.length, bundle]);

  useEffect(() => {
    const durations = timelineDurations(
      Boolean(bundle?.outcome.repair_attempted),
    );
    const onKey = (event: KeyboardEvent) => {
      if (!chapters.length) return;
      if (event.key === "ArrowRight") {
        setPlayback((current) =>
          seekPlayback(current.chapterIndex + 1, durations),
        );
      }
      if (event.key === "ArrowLeft") {
        setPlayback((current) =>
          seekPlayback(current.chapterIndex - 1, durations),
        );
      }
      if (event.key === " ") {
        event.preventDefault();
        setPlayback((current) => togglePlayback(current));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chapters.length, bundle]);

  if (!manifest || !profile || !bundle || !chapter || !state) {
    return <div className="loading">{tx("LOADING VERIFIED EVIDENCE PACK…", "正在加载已验证证据包…")}</div>;
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
  const qualifyingRootCount =
    bundle.outcome.repair_attempted &&
    (chapter.kind === "repair" || chapter.kind === "act") &&
    admitted
      ? 2
      : 1;
  const playbackProgress = chapterProgress(
    playback,
    timelineDurations(Boolean(bundle.outcome.repair_attempted)),
  );
  const nextView = viewpointLabel(
    String(request?.target_viewpoint || "diagnostic_side_view"),
    zh,
  );

  const restartOrToggle = () => {
    setPlayback((current) => togglePlayback(current));
  };

  return (
    <main className={"console-wrap " + (cinematic ? "cinematic" : "")}>
      {!cinematic && (
        <div className="console-toolbar">
          <label>
            <span>{tx("ACTIVE CANDIDATE", "当前候选")}</span>
            <select
              aria-label={tx("Candidate", "候选版本")}
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
              aria-label={tx("Replay", "证据回放")}
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
            <span>{tx("RECORDED AMD GPU EVIDENCE", "录制的 AMD GPU 证据")}</span>
            <span>{tx("SIMULATION ONLY", "仅限仿真")}</span>
            <span>{tx("FROZEN ARTIFACT", "冻结产物")}</span>
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
            <div className="chapter-controls">
              <button
                aria-label={tx("Previous chapter", "上一阶段")}
                onClick={() =>
                  setPlayback(
                    seekPlayback(
                      chapterIndex - 1,
                      timelineDurations(Boolean(bundle.outcome.repair_attempted)),
                    ),
                  )
                }
              >
                ‹
              </button>
              <span>
                {String(chapterIndex + 1).padStart(2, "0")} /{" "}
                {String(chapters.length).padStart(2, "0")}
              </span>
              <button
                aria-label={tx("Next chapter", "下一阶段")}
                onClick={() =>
                  setPlayback(
                    seekPlayback(
                      chapterIndex + 1,
                      timelineDurations(Boolean(bundle.outcome.repair_attempted)),
                    ),
                  )
                }
              >
                ›
              </button>
            </div>
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
                setPlayback(
                  seekPlayback(
                    index,
                    timelineDurations(Boolean(bundle.outcome.repair_attempted)),
                  ),
                );
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
            value={admitted ? tx("ADMIT", "准入") : denied ? tx("DENY", "拒绝") : tx("PENDING", "待定")}
            tone={admitted ? "pass" : denied ? "fail" : "pending"}
          />
          <Fact
            label={tx("FINAL ROUTE", "最终路线")}
            value={
              state.revealOutcome
                ? state.routeMode === "direct"
                  ? tx("DIRECT", "直行")
                  : tx("DETOUR", "绕行")
                : tx("PENDING", "待定")
            }
            tone={state.revealOutcome ? "pass" : "pending"}
          />
        </div>
      </section>

      <section className="visual-stage">
        <div className="visual-primary">
          <div className="world-evidence-layout">
            <WorldReplay3D
              bundle={bundle}
              chapterKind={chapter.kind}
              chapterStep={state.event?.step || frame.step}
              progress={playbackProgress}
              activeFrameStep={frame.step}
              rootProgress={qualifyingRootCount}
              language={language}
              label={
                chapter.kind === "observe"
                  ? tx("GENESIS WORLD · ROBOT HELD", "GENESIS 世界 · 机器人停止")
                  : chapter.kind === "deny"
                    ? tx("PURIFY HOLD · ACTION DENIED", "PURIFY 保持停止 · 动作拒绝")
                    : chapter.kind === "plan"
                      ? tx("INDEPENDENT REVIEW VIEW LOCKED", "独立复核视角已锁定")
                      : chapter.kind === "move"
                        ? tx("SCOUT MOVES TO THE REVIEW VIEW", "侦察车移动到独立复核视角")
                        : chapter.kind === "repair"
                          ? tx("NEW ROOT · GATE RE-EVALUATION", "新证据根 · GATE 重新评估")
                          : state.routeMode === "direct"
                            ? tx("AUTHORIZED DIRECT CROSSING", "已授权的直接通行")
                            : tx("SAFE DETOUR", "安全绕行")
              }
            />
            <div className="world-evidence-dock">
              <div className="evidence-dock-title">
                <span>{tx("ROBOT-CAPTURED EVIDENCE SNAPSHOT", "机器人采集的证据快照")}</span>
                <b>{tx("STATIC SNAPSHOT · NOT VIDEO", "静态快照 · 非连续视频")}</b>
              </div>
              {chapter.kind === "repair" && frames.length > 1 ? (
                <div className="evidence-pair">
                  <FrameView
                    frame={frames[0]}
                    mode={sensorMode}
                    rootOrdinal={1}
                    rootTotal={2}
                    label={tx("BEFORE · ROOT 01", "之前 · ROOT 01")}
                    status={tx(
                      "CARRIER SNAPSHOT · INDEPENDENT ROOT 1/2",
                      "主车快照 · 独立根 1/2",
                    )}
                    zh={zh}
                  />
                  <FrameView
                    frame={frames.at(-1)!}
                    mode={sensorMode}
                    rootOrdinal={2}
                    rootTotal={2}
                    label={tx("AFTER · ROOT 02", "之后 · ROOT 02")}
                    status={tx(
                      "SCOUT SNAPSHOT · INDEPENDENT ROOT 2/2",
                      "侦察车快照 · 独立根 2/2",
                    )}
                    zh={zh}
                  />
                </div>
              ) : (
                <FrameView
                  frame={frame}
                  mode={sensorMode}
                  rootOrdinal={
                    frame.observer_agent_id === "scout" ? 2 : 1
                  }
                  rootTotal={2}
                  status={
                    chapter.kind === "observe"
                      ? tx(
                          "CARRIER SNAPSHOT · INDEPENDENT ROOT 1/2",
                          "主车快照 · 独立根 1/2",
                        )
                      : chapter.kind === "deny"
                        ? tx(
                            "PURIFY REVIEWS ROOT 01 · ROBOT HELD",
                            "Purify 审查 ROOT 01 · 机器人保持停止",
                          )
                        : chapter.kind === "move"
                          ? tx(
                              "SCOUT IS MOVING · ROOT 01 REMAINS ON SCREEN",
                              "侦察车移动中 · 当前仍显示 ROOT 01",
                            )
                        : chapter.kind === "act"
                            ? tx("QUALIFIED SNAPSHOT RETAINED", "保留已授权证据快照")
                            : tx(
                                "ROOT 01 RETAINED · PLANNING INDEPENDENT REVIEW",
                                "保留 ROOT 01 · 正在规划独立复核",
                              )
                  }
                  zh={zh}
                  label={
                    frame.observer_agent_id === "scout"
                      ? tx("ROOT 02 · STATIC SNAPSHOT", "ROOT 02 · 静态快照")
                      : tx("ROOT 01 · STATIC SNAPSHOT", "ROOT 01 · 静态快照")
                  }
                />
              )}
            </div>
          </div>
        </div>
        <aside className="decision-summary">
          <span>{tx("CURRENT DECISION", "当前决策")}</span>
          <strong className={admitted ? "pass" : denied ? "fail" : "pending"}>
            {admitted ? tx("ADMITTED", "已准入") : denied ? tx("DENIED", "已拒绝") : tx("EVALUATING", "评估中")}
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
            <b>{admitted ? tx("PYTHON ∧ PURIFY ADMIT", "PYTHON ∧ PURIFY 双重准入") : nextView}</b>
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
              zh={zh}
            />
            <ContractLine
              label={tx("Independent side-view root", "独立侧视采集根")}
              pass={
                state.gate
                  ? !state.gate.reasons.includes("missing_side_view_vision_root")
                  : undefined
              }
              zh={zh}
            />
            <ContractLine
              label="Python ∧ Purify"
              pass={state.gate?.effective_admit}
              zh={zh}
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
              {sensorModeLabel(mode, zh)}
            </button>
          ))}
        </div>
        <Metric label={tx("P(BLOCKED)", "P（受阻）")} value={formatP(frame?.p_blocked)} />
        <Metric
          label={tx("PREDICTION SET", "预测集")}
          value={predictionSetValue(frame?.prediction_set, zh)}
        />
        <Metric label={tx("CLAIM", "证据声明")} value={claimValue(frame?.value, zh)} accent />
        <Metric
          label={tx("PYTHON GATE", "PYTHON 门控")}
          value={state.gate?.python_admitted ? tx("ADMIT", "准入") : state.gate ? tx("DENY", "拒绝") : "—"}
        />
        <Metric
          label={tx("PURIFY GO", "PURIFY GO 门控")}
          value={state.gate?.purify_go_admitted ? tx("ADMIT", "准入") : state.gate ? tx("DENY", "拒绝") : "—"}
        />
      </section>

      {state.revealOutcome &&
        (!cinematic || playbackProgress >= 0.625 || playback.completed) && (
        <section className="comparison-card">
          <div>
            <span>{tx("ACTIVE", "主动策略")}</span>
            <b>{tx("REPAIR EVIDENCE → DIRECT", "修复证据 → 直行")}</b>
            <small>{tx("Independent root · Python ∧ Purify admit", "独立证据根 · Python ∧ Purify 双重准入")}</small>
          </div>
          <div>
            <span>{tx("PASSIVE", "被动策略")}</span>
            <b>{tx("NO REPAIR → SAFE DETOUR", "不修证据 → 安全绕行")}</b>
            <small>{tx("Safe, but pays for unresolved uncertainty", "保持安全，但为未消除的不确定性付出绕行成本")}</small>
          </div>
          <div className="safe-result">
            <span>{tx("UNSAFE CROSSINGS", "不安全穿越")}</span>
            <b>0</b>
            <small>{tx("Recorded Genesis + AMD GPU evidence", "录制的 Genesis + AMD GPU 证据")}</small>
          </div>
        </section>
      )}

      {!cinematic && (
        <>
          <details className="technical-details">
            <summary>{tx("Open evidence audit", "展开证据审计")}</summary>
            <div className="audit-grid">
              <section>
                <span>{tx("CURRENT EVIDENCE", "当前证据")}</span>
                <p>{tx("CLAIM", "证据声明")} <b>{claimValue(frame.value, zh)}</b></p>
                <p>{tx("P(BLOCKED)", "P（受阻）")} <b>{formatP(frame.p_blocked)}</b></p>
                <p>{tx("PREDICTION SET", "预测集")} <b>{predictionSetValue(frame.prediction_set, zh)}</b></p>
                <p>{tx("CAPTURE ROOTS", "采集根")} <b>{state.gate?.measurement_root_ids.length || 1}</b></p>
              </section>
              <section>
                <span>{tx("ACTION RECEIPT", "动作回执")}</span>
                <p>PYTHON <b>{state.gate?.python_admitted ? tx("ADMIT", "准入") : state.gate ? tx("DENY", "拒绝") : "—"}</b></p>
                <p>PURIFY GO <b>{state.gate?.purify_go_admitted ? tx("ADMIT", "准入") : state.gate ? tx("DENY", "拒绝") : "—"}</b></p>
                <p>{tx("EFFECTIVE", "最终结果")} <b>{state.gate?.effective_admit ? tx("ADMIT", "准入") : state.gate ? tx("DENY", "拒绝") : "—"}</b></p>
                <p>{tx("GATE ID", "门控 ID")} <b>{state.gate?.gate_id || "—"}</b></p>
              </section>
              <section>
                <span>{tx("INTEGRITY", "完整性")}</span>
                <p>{tx("SOURCE", "源回合")} <b>{bundle.integrity.source_episode_sha256.slice(0, 16)}…</b></p>
                <p>BUNDLE <b>{bundle.integrity.bundle_sha256.slice(0, 16)}…</b></p>
                <p>{tx("CLAIMS", "证据声明")} <b>{bundle.claims.length}</b></p>
                <p>{tx("LIVE GPU", "在线 GPU")} <b>{tx("NOT REQUIRED", "无需")}</b></p>
              </section>
            </div>
            <a
              className="raw-link"
              href={"/data/replays/" + replayId + ".json"}
              target="_blank"
            >
              {tx("OPEN SOURCE EPISODE JSON ↗", "打开原始回合 JSON ↗")}
            </a>
          </details>
        </>
      )}
      {cinematic && (
        <div className="cinematic-footer">
          <b>LOOK TWICE</b>
          <span>{tx("AMD GPU · GENESIS · PURIFY · SIMULATION ONLY", "AMD GPU · GENESIS · PURIFY · 仅限仿真")}</span>
        </div>
      )}
    </main>
  );
}

function FrameView({
  frame,
  mode,
  label,
  status,
  rootOrdinal,
  rootTotal,
  zh,
}: {
  frame: EpisodeBundle["sensor_frames"][number];
  mode: "rgb" | "depth" | "mask";
  label: string;
  status: string;
  rootOrdinal: number;
  rootTotal: number;
  zh: boolean;
}) {
  const source = frame.media[mode === "mask" ? "corridor_mask" : mode];
  const actor = observerLabel(frame.observer_agent_id, zh);
  return (
    <article className="judge-frame">
      <div className="frame-top">
        <b>{label}</b>
        <span>{frame.tensor_device}</span>
      </div>
      <div className="snapshot-media">
        <Image
          fill
          unoptimized
          className="recorded-frame"
          src={source}
          alt={zh
            ? `${actor}在 Step ${frame.step} 采集的${sensorModeLabel(mode, true)}静态证据快照`
            : `${sensorModeLabel(mode, false)} static evidence snapshot captured by ${actor} at step ${frame.step}`}
        />
      </div>
      <div className="snapshot-details">
        <div>
          <span>{zh ? "拍摄者" : "CAPTURED BY"}</span>
          <b>{actor}</b>
        </div>
        <div>
          <span>{zh ? "时刻 / 位置" : "STEP / VIEWPOINT"}</span>
          <b>STEP {frame.step} · {viewpointLabel(frame.viewpoint, zh)}</b>
        </div>
        <div>
          <span>{zh ? "目标 / 结论" : "TARGET / CLAIM"}</span>
          <b>{corridorLabel(frame.corridor_id, zh)} · {claimValue(frame.value, zh)}</b>
        </div>
        <div>
          <span>{zh ? "独立根进度" : "INDEPENDENT ROOTS"}</span>
          <b>{rootOrdinal}/{rootTotal}</b>
        </div>
      </div>
      <div className="recorded-status">
        <i />
        <span>{status}</span>
      </div>
    </article>
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
  zh,
}: {
  label: string;
  pass?: boolean;
  zh: boolean;
}) {
  return (
    <div>
      <i className={pass === undefined ? "pending" : pass ? "pass" : "fail"}>
        {pass === undefined ? "·" : pass ? "✓" : "×"}
      </i>
      <span>{label}</span>
      <b>{pass === undefined ? (zh ? "等待" : "WAIT") : pass ? (zh ? "通过" : "PASS") : (zh ? "缺失" : "OPEN")}</b>
    </div>
  );
}

function sensorModeLabel(mode: "rgb" | "depth" | "mask", zh: boolean) {
  if (mode === "rgb") return zh ? "彩色图像" : "RGB";
  if (mode === "depth") return zh ? "深度图" : "DEPTH";
  return zh ? "走廊掩码" : "CORRIDOR MASK";
}

function observerLabel(observer: string, zh: boolean) {
  if (observer === "scout") return zh ? "侦察车侧视相机" : "Scout side-view camera";
  return zh ? "主车前视相机" : "Carrier front camera";
}

function claimValue(value: string | undefined, zh: boolean) {
  if (!value) return "—";
  if (!zh) return value.toUpperCase();
  if (value === "clear") return "畅通";
  if (value === "blocked") return "受阻";
  if (value === "inconclusive") return "不确定";
  return value;
}

function predictionSetValue(values: string[] | undefined, zh: boolean) {
  if (!values?.length) return "—";
  return `{${values.map((value) => claimValue(value, zh)).join(", ")}}`;
}

function corridorLabel(value: string, zh: boolean) {
  if (!zh) return value.replaceAll("_", " ").toUpperCase();
  return value.replace(/^corridor_/i, "走廊 ").replaceAll("_", " ").toUpperCase();
}

function viewpointLabel(value: string, zh: boolean) {
  const [corridor, point] = value.split("/");
  if (!zh) {
    if (value === "diagnostic_side_view") return "INDEPENDENT REVIEW VIEW";
    if (value === "carrier_initial_front") return "CARRIER FRONT CAMERA";
    return point
      ? `${corridor.replaceAll("_", " ").toUpperCase()} · ${point.replaceAll("_", " ").toUpperCase()}`
      : value.replaceAll("_", " ").toUpperCase();
  }
  const labels: Record<string, string> = {
    diagnostic_side_view: "独立复核视角",
    carrier_initial_front: "主车前视相机位",
    left_near: "左侧近点",
    left_far: "左侧远点",
    right_near: "右侧近点",
    right_far: "右侧远点",
  };
  if (point) {
    return `${corridorLabel(corridor, true)} · ${labels[point] || point.replaceAll("_", " ")}`;
  }
  return labels[value] || value.replaceAll("_", " ");
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
