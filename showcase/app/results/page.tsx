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

type TaskUtilityReport = {
  status: string;
  locked_task_utility: {
    direct_route: {
      active: { count: number; denominator: number; percent: number };
      passive: { count: number; denominator: number; percent: number };
      paired_gain_percentage_points: number;
    };
    python_go_decision_agreement: { count: number; denominator: number };
  };
  confirmatory_cost_ledger: {
    loaded_carrier_travel_m: {
      active: number;
      passive: number;
      active_reduction_percent: number;
    };
    scout_travel_m: { active: number };
    total_robot_travel_m: { active_increase_percent: number };
  };
};

const percent = (value: number) => `${(value * 100).toFixed(2)}%`;

const lockedInputEvidence = {
  archiveSha256: "0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba",
  archiveUrl:
    "https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz",
  noteUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_LOCKED_INPUT_EVIDENCE.md",
  manifestUrl:
    "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json",
};

const rocmTelemetryUrl =
  "https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json";

export default function ResultsPage() {
  return <SiteShell><Results /></SiteShell>;
}

function Results() {
  const { language } = useLanguage();
  const zh = language === "zh";
  const [profile, setProfile] = useState<ReleaseProfile | null>(null);
  const [locked, setLocked] = useState<LockedReport | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  const [utility, setUtility] = useState<TaskUtilityReport | null>(null);
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
    fetch("/data/source/V8_TASK_UTILITY_DERIVATION.json")
      .then((response) => {
        if (!response.ok) throw new Error("task-utility report unavailable");
        return response.json();
      })
      .then(setUtility)
      .catch(() => setUtility(null));
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
    <section className="result-section locked-input-evidence">
      <div className="result-title">
        <span>{zh ? "锁定输入证据包" : "LOCKED INPUT EVIDENCE PACK"}</span>
        <h2>{zh ? "冻结结果不变；输入与标签总体现在可供审计。" : "The frozen result stays unchanged. Its input and label population is now auditable."}</h2>
        <p>{zh ? "归档包含正式开启前生成的 400 个世界与 3,200 条元数据记录，对应 locked report 的相同种子范围与标签数量。" : "The archive contains 400 worlds and 3,200 metadata records generated before the formal open, matching the locked report's seed range and label counts."}</p>
      </div>
      <div className="benchmark-panel evidence-pack-panel">
        <div className="benchmark-tags"><span>PRE-OPEN SIDECAR</span><span>INPUT + LABEL ONLY</span><span>0 INFERENCE RUNS</span><span>SHA256 VERIFIED</span></div>
        <div className="benchmark-grid evidence-pack-grid">
          <article><span>{zh ? "世界" : "WORLDS"}</span><strong>400</strong></article>
          <article><span>{zh ? "元数据记录" : "METADATA RECORDS"}</span><strong>3,200</strong></article>
          <article><span>{zh ? "BLOCKED / CLEAR" : "BLOCKED / CLEAR"}</span><strong>1,560<small> / 1,640</small></strong></article>
          <article className="archive-identity"><span>{zh ? "归档 SHA256" : "ARCHIVE SHA256"}</span><code title={lockedInputEvidence.archiveSha256}>{lockedInputEvidence.archiveSha256}</code></article>
        </div>
        <div className="evidence-boundary-grid">
          <article>
            <b>{zh ? "它建立了什么" : "WHAT IT ESTABLISHES"}</b>
            <p>{zh ? "一个字节身份明确、路径中立的输入与标签归档；包含运行时合法的 RGB、噪声深度与走廊掩码，以及仅用于评估的标签产物。" : "A byte-identified, path-neutral input-and-label archive with runtime-legal RGB, noisy depth and corridor masks, plus evaluation-only label artifacts."}</p>
          </article>
          <article className="boundary-warning">
            <b>{zh ? "它不能建立什么" : "WHAT IT CANNOT ESTABLISH"}</b>
            <p>{zh ? "它不含原始 one-shot 逐样本预测，也不含 24 个原始 locked live 回合。因此它不能复算 1.000 指标或重建原始 one-shot 执行。" : "It does not contain the original one-shot per-sample predictions or the 24 raw locked live episodes. It cannot recompute the 1.000 metrics or reconstruct the original one-shot execution."}</p>
          </article>
        </div>
        <p className="range-boundary">{zh ? "种子 102500–102699 只是来自相同生成器家族的预留挑战范围，未被评测；本项目不将其表述为 OOD 证据。预开启时间来自第一方 sidecar，并非外部时间戳认证。" : "Seeds 102500–102699 are a reserved challenge range from the same generator family and were not evaluated; they are not presented as OOD evidence. Pre-open chronology comes from a first-party sidecar, not an external timestamp authority."}</p>
        <div className="evidence-links">
          <a href={lockedInputEvidence.archiveUrl} target="_blank" rel="noreferrer">{zh ? "下载 1,019,307,579 字节归档 ↗" : "DOWNLOAD 1,019,307,579-BYTE ARCHIVE ↗"}</a>
          <a href={lockedInputEvidence.noteUrl} target="_blank" rel="noreferrer">{zh ? "阅读证据说明 ↗" : "READ EVIDENCE NOTE ↗"}</a>
          <a href={lockedInputEvidence.manifestUrl} target="_blank" rel="noreferrer">{zh ? "检查路径中立 MANIFEST ↗" : "INSPECT PATH-NEUTRAL MANIFEST ↗"}</a>
        </div>
      </div>
    </section>
    {utility && <section className="result-section utility-evidence">
      <div className="result-title"><span>{zh ? "锁定成对任务效用" : "LOCKED PAIRED TASK UTILITY"}</span><h2>{zh ? "安全拒绝是底线；主动修证让有用行动重新发生。" : "Safe refusal is the baseline. Active repair earns useful action back."}</h2><p>{zh ? "12 个相同世界、两种策略成对比较；24 个回合均从初始拒绝开始。" : "Twelve identical paired worlds, two policies; all 24 episodes began with the same initial denial."}</p></div>
      <div className="benchmark-panel">
        <div className="benchmark-tags"><span>LOCKED ONCE</span><span>12 PAIRED WORLDS</span><span>DERIVATION ONLY</span><span>NO V8 RERUN</span></div>
        <div className="benchmark-grid">
          <article><span>{zh ? "主动直行" : "ACTIVE DIRECT"}</span><strong>{utility.locked_task_utility.direct_route.active.count}<small>/{utility.locked_task_utility.direct_route.active.denominator}</small></strong></article>
          <article><span>{zh ? "被动直行" : "PASSIVE DIRECT"}</span><strong>{utility.locked_task_utility.direct_route.passive.count}<small>/{utility.locked_task_utility.direct_route.passive.denominator}</small></strong></article>
          <article><span>{zh ? "成对直行增益" : "PAIRED DIRECT GAIN"}</span><strong>+{utility.locked_task_utility.direct_route.paired_gain_percentage_points.toFixed(1)}<small> pp</small></strong></article>
          <article><span>{zh ? "PYTHON / GO 一致" : "PYTHON / GO AGREE"}</span><strong>{utility.locked_task_utility.python_go_decision_agreement.count}<small>/{utility.locked_task_utility.python_go_decision_agreement.denominator}</small></strong></article>
        </div>
        <p>{zh ? `独立的非锁定 seed 105400 成本账本：主动修证将载荷车里程从 ${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.passive.toFixed(3)} m 降至 ${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.active.toFixed(3)} m（-${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.active_reduction_percent.toFixed(2)}%），但 scout 行驶 ${utility.confirmatory_cost_ledger.scout_travel_m.active.toFixed(3)} m，总机器人里程增加 ${utility.confirmatory_cost_ledger.total_robot_travel_m.active_increase_percent.toFixed(2)}%。这是运动负担转移，不是总距离或延迟加速。` : `Separate non-locked seed 105400 cost ledger: active repair reduced loaded-carrier travel from ${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.passive.toFixed(3)} m to ${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.active.toFixed(3)} m (-${utility.confirmatory_cost_ledger.loaded_carrier_travel_m.active_reduction_percent.toFixed(2)}%), while the scout traveled ${utility.confirmatory_cost_ledger.scout_travel_m.active.toFixed(3)} m and total robot travel rose ${utility.confirmatory_cost_ledger.total_robot_travel_m.active_increase_percent.toFixed(2)}%. This is burden shifting, not a total-distance or latency speedup.`}</p>
        <a href="/data/source/V8_TASK_UTILITY_DERIVATION.json" target="_blank">{zh ? "查看派生 JSON ↗" : "TASK-UTILITY JSON ↗"}</a>
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
    <section className="result-section rocm-telemetry-evidence">
      <div className="result-title">
        <span>{zh ? "冻结 ROCm 遥测窗口" : "FROZEN ROCm TELEMETRY WINDOW"}</span>
        <h2>{zh ? "持续一分钟的受控前向负载，GPU 全程有据可查。" : "One sustained minute of controlled forwards, with the GPU accounted for."}</h2>
        <p>{zh ? "独立的提交期测量；准确 checkpoint 在加载前通过 SHA 校验，clean preflight 在模型加载前记录到零 KFD 计算进程、0% GPU 使用率和 0% VRAM 分配。" : "A separate submission-time measurement. The exact checkpoint passed SHA verification before load; a clean preflight recorded zero KFD compute processes, 0% GPU use and 0% VRAM allocation before model load."}</p>
      </div>
      <div className="benchmark-panel telemetry-panel">
        <div className="benchmark-tags"><span>CLEAN PREFLIGHT</span><span>BATCH 8</span><span>FP32</span><span>20 WARM-UP</span><span>1 Hz TELEMETRY</span></div>
        <div className="benchmark-grid telemetry-grid">
          <article><span>{zh ? "测量窗口" : "MEASURED WINDOW"}</span><strong>60.182<small> s</small></strong></article>
          <article><span>{zh ? "GPU 使用率采样" : "GPU-USE SAMPLES"}</span><strong>61<small>/61 @ 100%</small></strong></article>
          <article><span>{zh ? "平均封装功率" : "MEAN PACKAGE POWER"}</span><strong>135.33<small> W</small></strong></article>
          <article><span>{zh ? "P95 封装功率" : "P95 PACKAGE POWER"}</span><strong>156<small> W</small></strong></article>
          <article className="telemetry-throughput"><span>{zh ? "BATCH 8 图像 / 窗口" : "BATCH 8 IMAGES / WINDOW"}</span><strong>376<small> / 60.182 s</small></strong></article>
        </div>
        <p>{zh ? "该窗口仅测量持续的合成、预加载张量、FP32 冻结模型前向，包含 Python 调度和同步 ROCm 执行。它排除 RGB-D 预处理、Genesis 仿真与渲染、Go 证据融合、I/O 和动作执行；既不是端到端性能，也不是准确率评测。" : "This window measures only sustained synthetic, preloaded-tensor, FP32 frozen-model forwards, including Python dispatch and synchronized ROCm execution. It excludes RGB-D preprocessing, Genesis simulation and rendering, Go evidence fusion, I/O and actuation; it is neither end-to-end performance nor an accuracy evaluation."}</p>
        <a href={rocmTelemetryUrl} target="_blank" rel="noreferrer">{zh ? "查看 61 条遥测记录与方法 JSON ↗" : "INSPECT 61 TELEMETRY SAMPLES AND METHOD JSON ↗"}</a>
      </div>
    </section>
    <section className="result-section"><div className="result-title"><span>{zh ? "能力边界" : "CAPABILITY ENVELOPE"}</span><h2>{zh ? "通过的不是单一模型，而是端到端动作保障链。" : "The evaluated unit is the end-to-end action assurance chain."}</h2></div><div className="capability-list">{profile.capabilities.map((capability, index) => <div key={capability}><b>{String(index + 1).padStart(2, "0")}</b><span>{capabilityLabels[capability]?.[zh ? "zh" : "en"] || capability.replaceAll("_", " ")}</span><i>{zh ? "已验证" : "VERIFIED"}</i></div>)}</div></section>
    <section className="result-section identities"><div className="result-title"><span>{zh ? "冻结身份" : "FROZEN IDENTITIES"}</span><h2>{zh ? "模型、校准与授权内核均可追溯。" : "Model, calibration and authorization identities are traceable."}</h2></div><div>{profile.artifact_identities.map((artifact) => <p key={artifact.artifact}><span>{artifactLabels[artifact.artifact]?.[zh ? "zh" : "en"] || artifact.artifact.replaceAll("_", " ")}</span><code>{artifact.sha256}</code></p>)}</div></section>
    <section className="result-section limits"><div className="result-title"><span>{zh ? "诚实边界" : "HONEST BOUNDARY"}</span><h2>{zh ? "我们明确系统做到了什么，也明确没有声称什么。" : "The boundary is part of the result."}</h2></div><div>{profile.limitations.map((limitation, index) => <article key={limitation.en}><b>0{index + 1}</b><p>{zh ? limitation.zh : limitation.en}</p></article>)}</div></section>
    <section className="result-section report-download"><div className="result-title"><span>{zh ? "提交资料" : "SUBMISSION MATERIALS"}</span><h2>{zh ? "英文报告、原始数据与复现说明已归档。" : "English report, raw evidence and reproduction notes are packaged."}</h2></div><div><a className="report-primary" href="/docs/Look-Twice-V8-Technical-Report.pdf" target="_blank">{zh ? "下载技术报告 PDF ↗" : "DOWNLOAD TECHNICAL REPORT PDF ↗"}</a><a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4" target="_blank">{zh ? "观看 3:59 英文演示 ↗" : "WATCH 3:59 ENGLISH DEMO ↗"}</a><a href="https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release" target="_blank">{zh ? "打开冻结源码分支 ↗" : "OPEN FROZEN SOURCE BRANCH ↗"}</a><a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt" target="_blank">{zh ? "下载冻结模型 ↗" : "DOWNLOAD FROZEN CHECKPOINT ↗"}</a><a href="/reproduce?locale=en">{zh ? "打开复现路径 →" : "OPEN REPRODUCTION PATH →"}</a><a href="/media/look-twice-replay-30s.mp4">{zh ? "下载 30 秒证据短片 ↓" : "DOWNLOAD 30-SECOND EVIDENCE REEL ↓"}</a></div></section>
  </main>;
}
