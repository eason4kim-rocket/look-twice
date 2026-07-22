"use client";

import { useEffect, useState } from "react";
import { SiteShell, useLanguage } from "../components/SiteShell";
import type { ReleaseProfile } from "../lib/types";
import "./results.css";

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
  if (!profile) return <div className="loading">LOADING FROZEN PROFILE…</div>;
  return <main>
    <header className="page-header"><div><span className="eyebrow">FROZEN EVIDENCE / LOCKED ONCE</span><h1>{zh ? "结果，不靠口号。" : "Results, with receipts."}</h1></div><p>{zh ? "所有首页数字由 ReleaseProfile 注入，并链接到一次性 locked 报告。" : "Every public metric is injected by ReleaseProfile and links back to the single-use locked report."}</p></header>
    <section className="results-metrics">{profile.headline_metrics.map((metric) => <article key={metric.metric_id}><span>{zh ? metric.label.zh : metric.label.en}</span><strong>{metric.value}<small>/{metric.denominator}</small></strong><a href="/data/source/LOCKED_TEST_REPORT.json" target="_blank">SOURCE JSON ↗</a></article>)}</section>
    <section className="result-section"><div className="result-title"><span>CAPABILITY ENVELOPE</span><h2>{zh ? "通过的不是单一模型，而是端到端动作保障链。" : "The evaluated unit is the end-to-end action assurance chain."}</h2></div><div className="capability-list">{profile.capabilities.map((capability, index) => <div key={capability}><b>{String(index + 1).padStart(2, "0")}</b><span>{capability.replaceAll("_", " ")}</span><i>VERIFIED</i></div>)}</div></section>
    <section className="result-section identities"><div className="result-title"><span>FROZEN IDENTITIES</span><h2>{zh ? "模型、校准与授权内核均可追溯。" : "Model, calibration and authorization identities are traceable."}</h2></div><div>{profile.artifact_identities.map((artifact) => <p key={artifact.artifact}><span>{artifact.artifact.replaceAll("_", " ")}</span><code>{artifact.sha256}</code></p>)}</div></section>
    <section className="result-section limits"><div className="result-title"><span>HONEST BOUNDARY</span><h2>{zh ? "我们明确系统做到了什么，也明确没有声称什么。" : "The boundary is part of the result."}</h2></div><div>{profile.limitations.map((limitation, index) => <article key={limitation.en}><b>0{index + 1}</b><p>{zh ? limitation.zh : limitation.en}</p></article>)}</div></section>
  </main>;
}
