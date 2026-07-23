"use client";

import { useEffect, useState } from "react";
import { SiteShell, useLanguage } from "../components/SiteShell";
import type { ReleaseProfile } from "../lib/types";
import "./results.css";

const capabilityLabels: Record<string, { en: string; zh: string }> = {
  spatially_grounded_rgbd: {
    en: "Spatially grounded RGB-D",
    zh: "空间对齐的 RGB-D",
  },
  lineage_aware_claims: {
    en: "Lineage-aware claims",
    zh: "可追溯谱系的证据声明",
  },
  conformal_prediction_sets: {
    en: "Conformal prediction sets",
    zh: "Conformal 预测集",
  },
  purify_action_authorization: {
    en: "Purify action authorization",
    zh: "Purify 动作授权",
  },
  active_evidence_repair: {
    en: "Active evidence repair",
    zh: "主动证据修复",
  },
  fail_closed_detour: {
    en: "Fail-closed safe detour",
    zh: "失效关闭式安全绕行",
  },
};

const artifactLabels: Record<string, { en: string; zh: string }> = {
  go_conformal: { en: "Go conformal", zh: "Go Conformal 校准" },
  purify_binary: { en: "Purify binary", zh: "Purify 二进制" },
  vision_checkpoint: { en: "Vision checkpoint", zh: "视觉模型权重" },
  vision_conformal: { en: "Vision conformal", zh: "视觉 Conformal 校准" },
};

export default function ResultsPage() {
  return <SiteShell><Results /></SiteShell>;
}

function Results() {
  const { language } = useLanguage();
  const zh = language === "zh";
  const [profile, setProfile] = useState<ReleaseProfile | null>(null);
  useEffect(() => {
    fetch("/data/manifest.json").then((response) => response.json()).then((manifest) => {
      const selected = manifest.profiles.find(
        (item: { candidate_id: string }) => item.candidate_id === manifest.default_candidate_id,
      );
      if (selected) fetch(selected.href).then((response) => response.json()).then(setProfile);
    });
  }, []);
  if (!profile) return <div className="loading">{zh ? "正在加载冻结候选…" : "LOADING FROZEN PROFILE…"}</div>;
  return <main>
    <header className="page-header"><div><span className="eyebrow">{zh ? "冻结证据 / 仅评测一次" : "FROZEN EVIDENCE / LOCKED ONCE"}</span><h1>{zh ? "结果，不靠口号。" : "Results, with receipts."}</h1></div><p>{zh ? "所有公开数字由发布配置（ReleaseProfile）注入，并链接到唯一一次锁定评测报告。" : "Every public metric is injected by ReleaseProfile and links back to the single-use locked report."}</p></header>
    <section className="results-metrics">{profile.headline_metrics.map((metric) => <article key={metric.metric_id}><span>{zh ? metric.label.zh : metric.label.en}</span><strong>{metric.value}<small>/{metric.denominator}</small></strong><a href="/data/source/LOCKED_TEST_REPORT.json" target="_blank">{zh ? "查看源 JSON ↗" : "SOURCE JSON ↗"}</a></article>)}</section>
    <section className="result-section"><div className="result-title"><span>{zh ? "能力边界" : "CAPABILITY ENVELOPE"}</span><h2>{zh ? "通过的不是单一模型，而是端到端动作保障链。" : "The evaluated unit is the end-to-end action assurance chain."}</h2></div><div className="capability-list">{profile.capabilities.map((capability, index) => <div key={capability}><b>{String(index + 1).padStart(2, "0")}</b><span>{capabilityLabels[capability]?.[zh ? "zh" : "en"] || capability.replaceAll("_", " ")}</span><i>{zh ? "已验证" : "VERIFIED"}</i></div>)}</div></section>
    <section className="result-section identities"><div className="result-title"><span>{zh ? "冻结身份" : "FROZEN IDENTITIES"}</span><h2>{zh ? "模型、校准与授权内核均可追溯。" : "Model, calibration and authorization identities are traceable."}</h2></div><div>{profile.artifact_identities.map((artifact) => <p key={artifact.artifact}><span>{artifactLabels[artifact.artifact]?.[zh ? "zh" : "en"] || artifact.artifact.replaceAll("_", " ")}</span><code>{artifact.sha256}</code></p>)}</div></section>
    <section className="result-section limits"><div className="result-title"><span>{zh ? "诚实边界" : "HONEST BOUNDARY"}</span><h2>{zh ? "我们明确系统做到了什么，也明确没有声称什么。" : "The boundary is part of the result."}</h2></div><div>{profile.limitations.map((limitation, index) => <article key={limitation.en}><b>0{index + 1}</b><p>{zh ? limitation.zh : limitation.en}</p></article>)}</div></section>
  </main>;
}
