"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { useLanguage } from "./SiteShell";
import type { EpisodeBundle, GateReceipt, ReleaseProfile } from "../lib/types";
import "./console.css";
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

type StoryChapter = {
  eventIndex: number;
  kind: "observe" | "deny" | "move" | "repair" | "act";
  label: string;
  title: string;
  body: string;
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
  const [chapterIndex, setChapterIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sensorMode, setSensorMode] = useState<"rgb" | "depth" | "mask">("rgb");

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((response) => response.json())
      .then((next: Manifest) => {
        setManifest(next);
        setCandidateId(next.default_candidate_id);
      });
  }, []);

  useEffect(() => {
    if (!manifest || !candidateId) return;
    const href = manifest.profiles.find((item) => item.candidate_id === candidateId)?.href;
    if (!href) return;
    fetch(href)
      .then((response) => response.json())
      .then((next: ReleaseProfile) => {
        setProfile(next);
        setReplayId(next.default_replays[0] || "");
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
      });
  }, [manifest, replayId]);

  const chapters = useMemo(() => (bundle ? buildStory(bundle, zh) : []), [bundle, zh]);

  useEffect(() => {
    if (!playing || !chapters.length) return;
    const timer = setInterval(() => {
      setChapterIndex((current) => {
        if (current >= chapters.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 2600);
    return () => clearInterval(timer);
  }, [playing, chapters.length]);

  const chapter = chapters[chapterIndex];
  const cursor = chapter?.eventIndex || 0;
  const event = bundle?.events[cursor];
  const visibleEvents = useMemo(
    () => bundle?.events.slice(0, cursor + 1) || [],
    [bundle, cursor],
  );
  const frame = useMemo(() => {
    if (!bundle) return undefined;
    const seen = visibleEvents.filter((item) => item.type === "observation").at(-1);
    return (
      bundle.sensor_frames.find((item) => item.frame_id === seen?.ref_id) ||
      bundle.sensor_frames[0]
    );
  }, [bundle, visibleEvents]);
  const gate = useMemo(() => {
    if (!bundle) return undefined;
    const receipts = visibleEvents
      .filter((item) => item.type === "gate_decision")
      .map((item) =>
        bundle.gate_receipts.find((receipt) => receipt.receipt_sha256 === item.ref_id),
      )
      .filter((receipt): receipt is GateReceipt => Boolean(receipt));
    return receipts.findLast((receipt) => receipt.effective_admit) || receipts.at(-1);
  }, [bundle, visibleEvents]);

  if (!manifest || !profile || !bundle) {
    return <div className="loading">LOADING EVIDENCE PACK…</div>;
  }

  const observedFrameIndex = Math.max(
    0,
    bundle.sensor_frames.findIndex((item) => item.frame_id === frame?.frame_id),
  );
  const rootCount = bundle.measurement_roots.filter(
    (root) => root.observed_step <= (event?.step || 0),
  ).length;
  const nextView = bundle.repair_requests.length
    ? String(bundle.repair_requests[0].target_viewpoint || "side view")
        .replaceAll("_", " ")
        .toUpperCase()
    : tx("TAKE SAFE DETOUR", "执行安全绕行");

  return (
    <main className="console-wrap">
      <div className="console-toolbar">
        <label>
          <span>{tx("ACTIVE CANDIDATE", "当前候选")}</span>
          <select
            aria-label="Candidate"
            value={candidateId}
            onChange={(change) => setCandidateId(change.target.value)}
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
            onChange={(change) => setReplayId(change.target.value)}
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
          <span>RECORDED AMD GPU EVIDENCE REPLAY</span>
          <span>SIMULATION ONLY</span>
          <span>FROZEN ARTIFACT</span>
        </div>
      </div>

      <section className={"story-director story-" + (chapter?.kind || "observe")}>
        <div className="story-copy">
          <span>
            {tx("WHAT IS HAPPENING", "当前发生了什么")} ·{" "}
            {String(chapterIndex + 1).padStart(2, "0")}/
            {String(chapters.length).padStart(2, "0")}
          </span>
          <h2>{chapter?.title}</h2>
          <p>{chapter?.body}</p>
        </div>
        <div className="story-rail" aria-label={tx("Guided story chapters", "引导式故事章节")}>
          {chapters.map((item, index) => (
            <button
              key={item.kind + "-" + index}
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
        <div className="story-facts">
          <div>
            <span>{tx("EVIDENCE ROOTS", "证据根")}</span>
            <b>{Math.max(1, rootCount)}</b>
          </div>
          <div>
            <span>{tx("AUTHORIZATION", "动作授权")}</span>
            <b className={gate?.effective_admit ? "pass" : "fail"}>
              {gate?.effective_admit
                ? tx("ADMIT", "准入")
                : gate
                  ? tx("DENY", "拒绝")
                  : tx("PENDING", "待审查")}
            </b>
          </div>
          <div>
            <span>{tx("FINAL ROUTE", "最终路线")}</span>
            <b>{bundle.outcome.route_mode.toUpperCase()}</b>
          </div>
        </div>
      </section>

      <div className="console-grid">
        <section className="sensor-panel console-panel">
          <PanelHead
            title={tx("SENSOR EVIDENCE", "传感器证据")}
            value={(frame?.corridor_id || "—") + " / " + (frame?.viewpoint || "—")}
          />
          <div className="sensor-tabs">
            {(["rgb", "depth", "mask"] as const).map((mode) => (
              <button
                className={sensorMode === mode ? "active" : ""}
                key={mode}
                onClick={() => setSensorMode(mode)}
              >
                {mode === "mask" ? "CORRIDOR MASK" : mode.toUpperCase()}
              </button>
            ))}
          </div>
          <div className={"sensor-viewport " + sensorMode}>
            {frame?.media.available ? (
              <Image
                fill
                unoptimized
                className="recorded-frame"
                src={frame.media[sensorMode === "mask" ? "corridor_mask" : sensorMode]}
                alt={sensorMode + " evidence at " + frame.viewpoint}
              />
            ) : (
              <div className="sensor-scene">
                <div className="scene-rack left" />
                <div className="scene-rack right" />
                <div className="scene-path" />
                <div className="scene-obstacle" />
                <div className="scene-mask" />
              </div>
            )}
            <div className="recorded-overlay">
              <span>FRAME {frame?.frame_id?.replace("frame-", "").padStart(2, "0")}</span>
              <span>{frame?.tensor_device}</span>
            </div>
            <div className="view-callout">
              <b>
                {observedFrameIndex === 0
                  ? tx("INITIAL FRONT VIEW", "初始正面视角")
                  : tx("NEW SIDE VIEW", "新侧面视角")}
              </b>
              <span>
                {observedFrameIndex === 0
                  ? tx("ONE CAPTURE ROOT", "仅一个采集根")
                  : tx("INDEPENDENT CAPTURE ROOT ADDED", "已新增独立采集根")}
              </span>
            </div>
            <div className="media-note">
              {frame?.media.available
                ? tx("Recorded AMD GPU frame · SHA archived", "AMD GPU 记录帧 · SHA 已归档")
                : tx(
                    "Raw frame hash archived · evidence geometry view",
                    "原始帧哈希已归档；显示证据示意层",
                  )}
            </div>
          </div>
          <div className="evidence-delta">
            <div className="before">
              <span>{tx("BEFORE", "之前")}</span>
              <b>ROOT 01</b>
              <small>{tx("Clear claim, but not independent", "虽为 clear，但缺少独立性")}</small>
            </div>
            <i>→</i>
            <div className={observedFrameIndex > 0 ? "after active" : "after"}>
              <span>{tx("AFTER LOOKING TWICE", "再次观察后")}</span>
              <b>
                {observedFrameIndex > 0
                  ? "ROOT " + String(observedFrameIndex + 1).padStart(2, "0")
                  : tx("WAITING FOR NEW ROOT", "等待新证据根")}
              </b>
              <small>
                {observedFrameIndex > 0
                  ? tx("New viewpoint, new physical evidence", "新视角带来新的物理证据")
                  : tx("Robot must change viewpoint", "机器人必须移动观察位置")}
              </small>
            </div>
          </div>
          <div className="sensor-stats">
            <Metric label="P(BLOCKED)" value={formatP(frame?.p_blocked)} />
            <Metric
              label={tx("PREDICTION SET", "预测集")}
              value={"{" + (frame?.prediction_set?.join(", ") || "—") + "}"}
            />
            <Metric label="CLAIM" value={(frame?.value || "—").toUpperCase()} accent />
          </div>
        </section>

        <section className="gate-panel console-panel">
          <PanelHead
            title={tx("ACTION QUALIFICATION", "动作资格审查")}
            value={tx("STEP", "步骤") + " " + (event?.step || 0)}
          />
          <div className="gate-stack">
            <GateRow label={tx("PYTHON CONTRACT", "PYTHON 合同")} pass={gate?.python_admitted} />
            <GateRow label="PURIFY GO GATE" pass={gate?.purify_go_admitted} />
            <GateRow
              label={tx("EFFECTIVE ADMIT", "最终准入")}
              pass={gate?.effective_admit}
              major
            />
          </div>
          <div className="contract-list">
            <span>{tx("ACTION CONTRACT", "动作合同")}</span>
            <Clause
              label={tx("Fresh calibrated evidence", "证据新鲜且校准适用")}
              pass={gate ? !gate.belief_gaps?.includes("stale") : undefined}
            />
            <Clause
              label={tx("Independent side-view root", "独立侧视采集根")}
              pass={gate ? !gate.reasons?.includes("missing_side_view_vision_root") : undefined}
            />
            <Clause
              label={tx("No unresolved conflict", "无未解决冲突")}
              pass={gate ? !gate.reasons?.some((reason) => reason.includes("conflict")) : undefined}
            />
            <Clause
              label={tx("Python ∧ Purify authorization", "Python ∧ Purify 双重授权")}
              pass={gate?.effective_admit}
            />
          </div>
          <div className="root-map">
            <span>{tx("PHYSICAL MEASUREMENT ROOTS", "物理测量根")}</span>
            <div>
              {bundle.measurement_roots.map((root, index) => (
                <i
                  key={root.measurement_root_id}
                  className={root.observed_step <= (event?.step || 0) ? "used" : ""}
                  title={root.measurement_root_id}
                >
                  {index + 1}
                </i>
              ))}
            </div>
          </div>
        </section>

        <section className="decision-panel console-panel">
          <PanelHead
            title={tx("ROBOT DECISION", "机器人决策")}
            value={chapter?.label || "—"}
          />
          <div
            className={
              "decision-state " + (gate?.effective_admit ? "admit" : gate ? "deny" : "pending")
            }
          >
            <span>{tx("CURRENT AUTHORIZATION", "当前授权")}</span>
            <strong>
              {gate?.effective_admit
                ? tx("ADMITTED", "准入")
                : gate
                  ? tx("DENIED", "拒绝")
                  : tx("EVALUATING", "正在评估")}
            </strong>
            <p>
              {gate?.effective_admit
                ? tx(
                    "A new independent root repaired the contract. Direct action is now qualified.",
                    "新的独立证据修复了动作合同，可安全直行。",
                  )
                : gate
                  ? tx("Why denied: ", "拒绝原因：") + humanReason(gate.reasons[0], zh) + "."
                  : tx(
                      "Turning sensor observations into lineage-aware claims.",
                      "正在将传感器观察转化为带谱系的 Claim。",
                    )}
            </p>
          </div>
          <div className={"nbv-card " + (gate?.effective_admit ? "repaired" : "")}>
            <span>
              {gate?.effective_admit
                ? tx("WHAT CHANGED", "发生了什么变化")
                : tx("ROBOT'S NEXT MOVE", "机器人下一步")}
            </span>
            <b>
              {gate?.effective_admit
                ? tx("EVIDENCE CONTRACT REPAIRED", "证据合同已修复")
                : nextView}
            </b>
            <small>
              {gate?.effective_admit
                ? tx(
                    "NEW ROOT · PYTHON ADMIT · PURIFY ADMIT",
                    "新根 · PYTHON 准入 · PURIFY 准入",
                  )
                : bundle.repair_requests.length
                  ? tx(
                      "MOVE CAMERA · ACQUIRE INDEPENDENT ROOT",
                      "移动相机 · 获取独立根",
                    )
                  : tx("NO QUALIFIED DIRECT ACTION", "直行动作未获资格")}
            </small>
          </div>
          <div className="outcome-row">
            <span>{tx("FINAL ROUTE", "最终路线")}</span>
            <b className={bundle.outcome.route_mode}>{bundle.outcome.route_mode.toUpperCase()}</b>
            <span>{tx("UNSAFE", "不安全事件")}</span>
            <b className="safe">{bundle.outcome.unsafe_crossing ? tx("YES", "是") : "0"}</b>
          </div>
        </section>
      </div>

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
          <button
            className="play"
            onClick={() => {
              if (chapterIndex === chapters.length - 1) setChapterIndex(0);
              setPlaying(!playing);
            }}
          >
            {playing ? "Ⅱ" : "▶"}
          </button>
          <button
            aria-label={tx("Next chapter", "下一章")}
            onClick={() => {
              setChapterIndex(Math.min(chapters.length - 1, chapterIndex + 1));
              setPlaying(false);
            }}
          >
            ›
          </button>
          <span>
            {tx("GUIDED LOOP", "引导回放")} · {String(chapterIndex + 1).padStart(2, "0")} /{" "}
            {String(chapters.length).padStart(2, "0")}
          </span>
        </div>
        <div className="timeline">
          {bundle.events.map((item, index) => (
            <button
              key={item.event_id}
              title={item.type + " · " + item.status}
              className={
                item.type +
                " " +
                (index <= cursor ? "seen " : "") +
                (index === cursor ? "current" : "")
              }
              onClick={() => {
                const nearest = chapters.reduce(
                  (best, current, chapterPosition) =>
                    Math.abs(current.eventIndex - index) <
                    Math.abs(chapters[best].eventIndex - index)
                      ? chapterPosition
                      : best,
                  0,
                );
                setChapterIndex(nearest);
                setPlaying(false);
              }}
            >
              <i />
              <span>{item.step}</span>
            </button>
          ))}
        </div>
        <a className="raw-link" href={"/data/replays/" + replayId + ".json"} target="_blank">
          RAW JSON ↗
        </a>
      </section>
      <div className="integrity-bar">
        <span>
          SOURCE EPISODE <b>{bundle.integrity.source_episode_sha256.slice(0, 16)}…</b>
        </span>
        <span>
          BUNDLE <b>{bundle.integrity.bundle_sha256.slice(0, 16)}…</b>
        </span>
        <span>
          LIVE GPU DEPENDENCY <b>NONE</b>
        </span>
      </div>
    </main>
  );
}

function PanelHead({ title, value }: { title: string; value: string }) {
  return (
    <div className="panel-head">
      <b>{title}</b>
      <span>{value}</span>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <span>{label}</span>
      <b className={accent ? "accent" : ""}>{value}</b>
    </div>
  );
}

function GateRow({ label, pass, major }: { label: string; pass?: boolean; major?: boolean }) {
  return (
    <div className={major ? "major" : ""}>
      <span>{label}</span>
      <b className={pass === undefined ? "pending" : pass ? "pass" : "fail"}>
        {pass === undefined ? "PENDING" : pass ? "ADMIT" : "DENY"}
      </b>
    </div>
  );
}

function Clause({ label, pass }: { label: string; pass?: boolean }) {
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

function buildStory(bundle: EpisodeBundle, zh: boolean): StoryChapter[] {
  const events = bundle.events;
  const observations = events
    .map((item, index) => (item.type === "observation" ? index : -1))
    .filter((index) => index >= 0);
  const gateFor = (index: number) =>
    bundle.gate_receipts.find((receipt) => receipt.receipt_sha256 === events[index]?.ref_id);
  const firstDeny = events.findIndex(
    (item, index) => item.type === "gate_decision" && gateFor(index) && !gateFor(index)?.effective_admit,
  );
  const request = events.findIndex((item) => item.type === "evidence_request");
  const admit = events.findIndex(
    (item, index) => item.type === "gate_decision" && gateFor(index)?.effective_admit,
  );
  const outcome = events.findIndex((item) => item.type === "outcome");
  const direct = bundle.outcome.route_mode === "direct";
  const repair = bundle.outcome.repair_attempted || request >= 0;
  const story: StoryChapter[] = [
    {
      eventIndex: Math.max(0, observations[0] || 0),
      kind: "observe",
      label: zh ? "观察" : "OBSERVE",
      title: zh ? "机器人看见走廊似乎可通行" : "The corridor looks clear to the robot",
      body: zh
        ? "但这只是单一正面采集产生的 Claim，还不是可供物理动作依赖的事实。"
        : "But it is only a claim from one front capture—not yet a fact reliable enough for physical action.",
    },
  ];
  if (firstDeny >= 0) {
    story.push({
      eventIndex: firstDeny,
      kind: "deny",
      label: zh ? "拒绝" : "DENY",
      title: zh ? "Purify 拒绝直接通行" : "Purify refuses the direct crossing",
      body: zh
        ? "动作合同缺少独立侧视根。复制更多同源 Claim 不会增加可信度。"
        : "The action contract is missing an independent side-view root. More correlated claims would not add assurance.",
    });
  }
  if (repair && request >= 0) {
    story.push({
      eventIndex: request,
      kind: "move",
      label: zh ? "换视角" : "MOVE",
      title: zh ? "机器人为修复证据而移动" : "The robot moves to repair the evidence",
      body: zh
        ? "系统不是盲目重拍：它选择能填补合同缺口的诊断视角，并创建新的物理采集根。"
        : "It does not simply retry. It selects a diagnostic viewpoint that can close the contract gap and create a new physical root.",
    });
  }
  if (admit >= 0) {
    story.push({
      eventIndex: admit,
      kind: "repair",
      label: zh ? "修复" : "REPAIR",
      title: zh ? "新的独立证据修复了动作合同" : "Independent evidence repairs the action contract",
      body: zh
        ? "Python 合同与 Purify Go 同时准入。可追溯证据改变了动作资格。"
        : "Both the Python contract and Purify Go now admit. Traceable evidence changed the action qualification.",
    });
  }
  if (outcome >= 0) {
    story.push({
      eventIndex: outcome,
      kind: "act",
      label: zh ? "行动" : "ACT",
      title: direct
        ? zh
          ? "机器人获得授权并安全直行"
          : "The robot is authorized to cross directly"
        : zh
          ? "证据仍不足，机器人安全绕行"
          : "Evidence remains insufficient, so the robot detours safely",
      body: direct
        ? zh
          ? "最终路线为 direct，unsafe=0。每一步都可追溯到 Claim、采集根和 GateReceipt。"
          : "The final route is direct with unsafe=0. Every decision remains traceable to claims, capture roots and GateReceipts."
        : zh
          ? "被动策略不会伪装成确认堵塞；它明确标记 safe fallback 并绕行。"
          : "The passive policy does not pretend the corridor is blocked. It marks a safe fallback and takes the detour.",
    });
  }
  return story.filter(
    (item, index, all) => index === 0 || item.eventIndex !== all[index - 1].eventIndex,
  );
}

function humanReason(reason: string | undefined, zh: boolean) {
  const key = reason || "evidence_not_qualified";
  const reasons: Record<string, [string, string]> = {
    missing_side_view_vision_root: [
      "missing independent side-view evidence",
      "缺少独立侧视证据",
    ],
    insufficient_roots: [
      "not enough independent measurement roots",
      "独立测量根不足",
    ],
    modality_conflict: ["sensor modalities still conflict", "传感器模态仍有冲突"],
    purify_go_denied: ["Purify Go did not authorize the action", "Purify Go 未授权该动作"],
    evidence_not_qualified: [
      "evidence does not yet satisfy the action contract",
      "证据尚未满足动作合同",
    ],
  };
  return (reasons[key] || [key.replaceAll("_", " "), key.replaceAll("_", " ")])[zh ? 1 : 0];
}
