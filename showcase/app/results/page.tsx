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

type LockedReport = {
  passed: boolean;
  permanent: boolean;
  no_retune: boolean;
  no_refit: boolean;
  no_vision_retrain: boolean;
  offline: {
    split: string;
    seed_range: [number, number];
    metrics: {
      n_samples: number;
      n_blocked: number;
      n_clear: number;
      roi_iou: number;
      balanced_accuracy_decisive: number;
      blocked_recall_decisive: number;
      false_clear_singleton_rate: number;
      coverage: number;
      n_decisive: number;
    };
  };
};

type BenchmarkReport = {
  status: string;
  checkpoint: {
    hash_verified: boolean;
    parameter_count: number;
  };
  runtime: {
    torch: string;
    hip: string;
    device_name: string;
    gcn_arch_name: string;
  };
  method: {
    precision: string;
    warmup_iterations_per_batch: number;
    measured_iterations_per_batch: number;
  };
  results: Array<{
    batch_size: number;
    latency_ms: { median_p50: number; p95: number };
    throughput_images_per_second: number;
    memory_mib: { peak_allocated: number };
  }>;
};

const percent = (value: number) => `${(value * 100).toFixed(2)}%`;

export default function ResultsPage() {
  return <SiteShell><Results /></SiteShell>;
}

function Results() {
  const { language } = useLanguage();
  const zh = language === "zh";
  const [profile, setProfile] = useState<ReleaseProfile | null>(null);
  const [locked, setLocked] = useState<LockedReport | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  useEffect(() => {
    fetch("/data/manifest.json").then((response) => response.json()).then((manifest) => {
      const selected = manifest.profiles.find(
        (item: { candidate_id: string }) => item.candidate_id === manifest.default_candidate_id,
      );
      if (selected) fetch(selected.href).then((response) => response.json()).then(setProfile);
    });
    fetch("/data/source/LOCKED_TEST_REPORT.json")
      .then((response) => response.json())
      .then(setLocked);
    fetch("/data/source/V8_FROZEN_INFERENCE_BENCHMARK.json")
      .then((response) => {
        if (!response.ok) throw new Error("benchmark report unavailable");
        return response.json();
      })
      .then(setBenchmark)
      .catch(() => setBenchmark(null));
  }, []);
  if (!profile) return <div className="loading">{zh ? "正在加载冻结候选…" : "LOADING FROZEN PROFILE…"}</div>;
  const batchOne = benchmark?.results.find((item) => item.batch_size === 1);
  const batchEight = benchmark?.results.find((item) => item.batch_size === 8);
  return <main>
    <header className="page-header"><div><span className="eyebrow">{zh ? "冻结证据 / 仅评测一次" : "FROZEN EVIDENCE / LOCKED ONCE"}</span><h1>{zh ? "结果，不靠口号。" : "Results, with receipts."}</h1></div><p>{zh ? "所有数字均从机器可读发布产物加载，并链接到锁定报告或哈希固定的 ROCm 基准。" : "Every number is loaded from a machine-readable release artifact and links to either the locked report or the hash-pinned ROCm benchmark."}</p></header>
    <section className="results-metrics">{profile.headline_metrics.map((metric) => <article key={metric.metric_id}><span>{zh ? metric.label.zh : metric.label.en}</span><strong>{metric.value}<small>/{metric.denominator}</small></strong><a href="/data/source/LOCKED_TEST_REPORT.json" target="_blank">{zh ? "查看源 JSON ↗" : "SOURCE JSON ↗"}</a></article>)}</section>
    {locked && <section className="result-section offline-evidence">
      <div className="result-title"><span>{zh ? "锁定离线总体" : "LOCKED OFFLINE POPULATION"}</span><h2>{zh ? "完整分母，而不是精选演示。" : "The full denominator, not a cherry-picked replay."}</h2><p>{zh ? `种子 ${locked.offline.seed_range[0]}–${locked.offline.seed_range[1]}，${locked.offline.metrics.n_blocked.toLocaleString()} blocked / ${locked.offline.metrics.n_clear.toLocaleString()} clear。` : `Seeds ${locked.offline.seed_range[0]}–${locked.offline.seed_range[1]}; ${locked.offline.metrics.n_blocked.toLocaleString()} blocked and ${locked.offline.metrics.n_clear.toLocaleString()} clear samples.`}</p></div>
      <div className="audit-grid">
        <article><span>{zh ? "样本" : "SAMPLES"}</span><strong>{locked.offline.metrics.n_samples.toLocaleString()}</strong><small>{locked.offline.split.replaceAll("_", " ")}</small></article>
        <article><span>{zh ? "走廊 ROI IoU" : "CORRIDOR ROI IOU"}</span><strong>{percent(locked.offline.metrics.roi_iou)}</strong><small>{zh ? "目标走廊范围" : "action-scoped region"}</small></article>
        <article><span>{zh ? "决断样本平衡准确率" : "DECISIVE BALANCED ACCURACY"}</span><strong>{percent(locked.offline.metrics.balanced_accuracy_decisive)}</strong><small>{locked.offline.metrics.n_decisive.toLocaleString()} / {locked.offline.metrics.n_samples.toLocaleString()} decisive</small></article>
        <article><span>{zh ? "False-clear 单例率" : "FALSE-CLEAR SINGLETON RATE"}</span><strong>{percent(locked.offline.metrics.false_clear_singleton_rate)}</strong><small>{zh ? "决断预测" : "decisive predictions"}</small></article>
        <article><span>{zh ? "Conformal 覆盖率" : "CONFORMAL COVERAGE"}</span><strong>{percent(locked.offline.metrics.coverage)}</strong><small>{zh ? "声明总体" : "declared population"}</small></article>
        <article className="seal-card"><span>{zh ? "冻结纪律" : "FREEZE DISCIPLINE"}</span><strong>{locked.passed && locked.permanent ? "PASS" : "CHECK"}</strong><small>{zh ? "无重调参 · 无重拟合 · 无视觉重训" : "no retune · no refit · no vision retrain"}</small></article>
      </div>
    </section>}
    {benchmark && batchOne && batchEight && <section className="result-section rocm-evidence">
      <div className="result-title"><span>{zh ? "AMD / ROCm 执行" : "AMD / ROCm EXECUTION"}</span><h2>{zh ? "同一冻结权重，单独测量模型前向。" : "The same frozen weights, measured as model forward only."}</h2><p>{benchmark.runtime.device_name} · {benchmark.runtime.gcn_arch_name} · HIP {benchmark.runtime.hip}</p></div>
      <div className="benchmark-panel">
        <div className="benchmark-tags"><span>{benchmark.method.precision.toUpperCase()}</span><span>{benchmark.method.warmup_iterations_per_batch} WARM-UP</span><span>{benchmark.method.measured_iterations_per_batch} MEASURED</span><span>{benchmark.checkpoint.hash_verified ? "SHA VERIFIED" : "SHA CHECK"}</span></div>
        <div className="benchmark-grid">
          <article><span>B1 P50</span><strong>{batchOne.latency_ms.median_p50.toFixed(2)}<small> ms</small></strong></article>
          <article><span>B1 P95</span><strong>{batchOne.latency_ms.p95.toFixed(2)}<small> ms</small></strong></article>
          <article><span>B8 THROUGHPUT</span><strong>{batchEight.throughput_images_per_second.toFixed(2)}<small> img/s</small></strong></article>
          <article><span>B8 PEAK ALLOCATED</span><strong>{batchEight.memory_mib.peak_allocated.toFixed(2)}<small> MiB</small></strong></article>
        </div>
        <p>{zh ? "预加载合成张量；包含 Python 调度与同步 ROCm 前向。排除预处理、Genesis、Go、I/O 与机器人执行；不是端到端延迟。" : "Preloaded synthetic tensors; includes Python dispatch and synchronized ROCm forward. Excludes preprocessing, Genesis, Go, I/O and robot actuation; not end-to-end latency."}</p>
        <a href="/data/source/V8_FROZEN_INFERENCE_BENCHMARK.json" target="_blank">{zh ? "查看基准 JSON ↗" : "BENCHMARK JSON ↗"}</a>
      </div>
    </section>}
    <section className="result-section"><div className="result-title"><span>{zh ? "能力边界" : "CAPABILITY ENVELOPE"}</span><h2>{zh ? "通过的不是单一模型，而是端到端动作保障链。" : "The evaluated unit is the end-to-end action assurance chain."}</h2></div><div className="capability-list">{profile.capabilities.map((capability, index) => <div key={capability}><b>{String(index + 1).padStart(2, "0")}</b><span>{capabilityLabels[capability]?.[zh ? "zh" : "en"] || capability.replaceAll("_", " ")}</span><i>{zh ? "已验证" : "VERIFIED"}</i></div>)}</div></section>
    <section className="result-section identities"><div className="result-title"><span>{zh ? "冻结身份" : "FROZEN IDENTITIES"}</span><h2>{zh ? "模型、校准与授权内核均可追溯。" : "Model, calibration and authorization identities are traceable."}</h2></div><div>{profile.artifact_identities.map((artifact) => <p key={artifact.artifact}><span>{artifactLabels[artifact.artifact]?.[zh ? "zh" : "en"] || artifact.artifact.replaceAll("_", " ")}</span><code>{artifact.sha256}</code></p>)}</div></section>
    <section className="result-section limits"><div className="result-title"><span>{zh ? "诚实边界" : "HONEST BOUNDARY"}</span><h2>{zh ? "我们明确系统做到了什么，也明确没有声称什么。" : "The boundary is part of the result."}</h2></div><div>{profile.limitations.map((limitation, index) => <article key={limitation.en}><b>0{index + 1}</b><p>{zh ? limitation.zh : limitation.en}</p></article>)}</div></section>
    <section className="result-section report-download"><div className="result-title"><span>{zh ? "提交资料" : "SUBMISSION MATERIALS"}</span><h2>{zh ? "英文报告、原始数据与复现说明已归档。" : "English report, raw evidence and reproduction notes are packaged."}</h2></div><div><a className="report-primary" href="/docs/Look-Twice-V8-Technical-Report.pdf" target="_blank">{zh ? "下载技术报告 PDF ↗" : "DOWNLOAD TECHNICAL REPORT PDF ↗"}</a><a href="https://github.com/eason4kim-rocket/look-twice" target="_blank">{zh ? "打开源代码仓库 ↗" : "OPEN SOURCE REPOSITORY ↗"}</a><a href="/reproduce?locale=en">{zh ? "打开复现路径 →" : "OPEN REPRODUCTION PATH →"}</a><a href="/media/look-twice-replay-30s.mp4">{zh ? "下载 30 秒证据短片 ↓" : "DOWNLOAD 30-SECOND EVIDENCE REEL ↓"}</a></div></section>
  </main>;
}
