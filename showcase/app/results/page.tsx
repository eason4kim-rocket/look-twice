"use client";

import { useEffect, useState } from "react";
import { SiteShell, useLanguage } from "../components/SiteShell";
import { challengeEvidence } from "../lib/challengeEvidence";
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

type ChallengeRate = {
  count: number;
  total: number;
  rate: number;
  wilson_95: { lower: number; upper: number };
};

type ChallengeReport = {
  schema_version: string;
  preregistration_sha256: string;
  analysis: {
    evidence_scope: {
      worlds: number;
      paired_episodes: number;
      seed_range: [number, number];
      generator_family: string;
      motion_backend: string;
      not_ood: boolean;
      not_physical_robot: boolean;
      agent_realization: string;
      not_simultaneous_dual_body_dynamics: boolean;
    };
    primary_endpoint: {
      active: ChallengeRate;
      passive: ChallengeRate;
      active_minus_passive: { percentage_points: number };
      exact_mcnemar_two_sided_p: number;
    };
    secondary_endpoints: {
      mission_success: { all_episodes: ChallengeRate };
      unsafe: { all_episodes: ChallengeRate };
      fallback_used: { all_episodes: ChallengeRate };
      python_go_gate_agreement: { comparable_receipts: ChallengeRate };
    };
    full_wall_rocm_telemetry: {
      sample_count: number;
      sample_interval_seconds: number;
      measured_wall_seconds: number;
      gpu_use_percent: { mean: number; p95: number; maximum: number };
      gpu_busy_sample_rate: { busy_samples: number; total_samples: number; rate: number };
      graphics_package_power_w: { mean: number; p95: number; maximum: number };
      episode_subprocess_wall_seconds: { all: { mean: number; p95: number } };
    };
    logical_role_kinematic_operational_burden: {
      loaded_carrier: {
        active: { mean: number };
        passive: { mean: number };
      };
      active_scout: { mean: number };
      total_team: {
        active: { mean: number };
        passive: { mean: number };
      };
    };
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
  const [challenge, setChallenge] = useState<ChallengeReport | null>(null);
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
    fetch(challengeEvidence.reportUrl)
      .then((response) => {
        if (!response.ok) throw new Error("challenge report unavailable");
        return response.json();
      })
      .then(setChallenge)
      .catch(() => setChallenge(null));
  }, []);
  if (!profile || !challenge) return <div className="loading">{zh ? "正在加载已验证挑战证据…" : "LOADING VERIFIED CHALLENGE EVIDENCE…"}</div>;
  const batchOne = benchmark?.results.find((item) => item.batch_size === 1);
  const batchEight = benchmark?.results.find((item) => item.batch_size === 8);
  const primary = challenge.analysis.primary_endpoint;
  const challengeSafety = challenge.analysis.secondary_endpoints;
  const receipts = challengeSafety.python_go_gate_agreement.comparable_receipts;
  const receiptMismatches = receipts.total - receipts.count;
  const challengeTelemetry = challenge.analysis.full_wall_rocm_telemetry;
  const burden = challenge.analysis.logical_role_kinematic_operational_burden;
  const carrierReduction =
    (1 - burden.loaded_carrier.active.mean / burden.loaded_carrier.passive.mean) * 100;
  const teamIncrease =
    (burden.total_team.active.mean / burden.total_team.passive.mean - 1) * 100;
  return <main>
    <header className="page-header challenge-page-header"><div><span className="eyebrow">{zh ? "公开预注册挑战 / 独立验证通过" : "PUBLICLY PREREGISTERED CHALLENGE / INDEPENDENTLY VERIFIED"}</span><h1>{zh ? "结果，带着回执。" : "Results, with receipts."}</h1></div><p>{zh ? "首屏是 30 个同生成器世界、60 个预注册回合的挑战结果。原 12-pair permanent locked test 与旧 synthetic 60s 前向演示在下方分开保留。" : "The first evidence tier is the preregistered 30-world, 60-episode same-generator challenge. The original 12-pair permanent locked test and the older synthetic 60s forward demo remain explicitly separate below."}</p></header>
    <section className="result-section challenge-primary-evidence">
      <div className="result-title">
        <span>{zh ? "主计分证据 · 30 个成对世界" : "PRIMARY SCORING EVIDENCE · 30 PAIRED WORLDS"}</span>
        <h2>{zh ? "能安全直行时全部直行；唯一双廊阻塞世界正确绕行。" : "Direct whenever physically feasible; detour when both corridors are blocked."}</h2>
        <p>{zh ? `种子 ${challenge.analysis.evidence_scope.seed_range[0]}–${challenge.analysis.evidence_scope.seed_range[1]} 在公开预注册之后仅评测一次。该挑战与原 12-pair locked test 分开，来自相同生成器家族，不是 OOD。` : `Seeds ${challenge.analysis.evidence_scope.seed_range[0]}–${challenge.analysis.evidence_scope.seed_range[1]} were evaluated once after public preregistration. This challenge is separate from the original 12-pair locked test, comes from the same generator family, and is not OOD.`}</p>
      </div>
      <div className="benchmark-panel challenge-panel">
        <div className="feasibility-proof">
          <article><span>{zh ? "离线可行性一致路线结果*" : "OFFLINE FEASIBILITY-CONSISTENT ROUTES*"}</span><strong>30<small>/30</small></strong></article>
          <article><span>{zh ? "存在 CLEAR 走廊时安全直行" : "DIRECT WITH AN ORACLE-CLEAR CORRIDOR"}</span><strong>29<small>/29</small></strong></article>
          <article><span>{zh ? "双廊均阻塞时安全绕行" : "SAFE DETOUR WHEN BOTH WERE BLOCKED"}</span><strong>1<small>/1</small></strong></article>
          <p>{zh ? "* 事后描述性 oracle 审计，不是预注册端点；oracle 从未提供给控制器。下方保留原预注册主端点 29/30 对 0/30。" : "* Post-hoc descriptive oracle audit, not a preregistered endpoint; oracle was never available to the controller. The original preregistered primary, 29/30 versus 0/30, remains below."}</p>
        </div>
        <div className="benchmark-tags"><span>PUBLIC PREREGISTRATION</span><span>30 PAIRED WORLDS</span><span>60 / 60 VALID</span><span>VERIFIER PASS</span></div>
        <div className="benchmark-grid challenge-primary-grid">
          <article><span>{zh ? "主动全链直行" : "ACTIVE FULL-CHAIN DIRECT"}</span><strong>{primary.active.count}<small>/{primary.active.total}</small></strong><i>95% Wilson 83.3–99.4%</i></article>
          <article><span>{zh ? "被动全链直行" : "PASSIVE FULL-CHAIN DIRECT"}</span><strong>{primary.passive.count}<small>/{primary.passive.total}</small></strong><i>95% Wilson 0.0–11.4%</i></article>
          <article><span>{zh ? "成对差值" : "PAIRED DIFFERENCE"}</span><strong>+{primary.active_minus_passive.percentage_points.toFixed(1)}<small> pp</small></strong><i>29 active-only · 1 neither</i></article>
          <article><span>{zh ? "双侧精确 McNemar" : "EXACT TWO-SIDED McNEMAR"}</span><strong>3.725×10<sup>−9</sup></strong><i>p-value · no success threshold</i></article>
        </div>
        <div className="challenge-audit-grid">
          <article>
            <b>{zh ? "安全与完整分母" : "SAFETY + FULL DENOMINATOR"}</b>
            <strong>{challengeSafety.mission_success.all_episodes.count}/{challengeSafety.mission_success.all_episodes.total}</strong>
            <p>{zh ? `${challengeSafety.unsafe.all_episodes.count} unsafe · ${challengeSafety.fallback_used.all_episodes.count} fallback；60/60 均加载冻结 checkpoint、Genesis live RGB-D 与 Purify Go 回执。` : `${challengeSafety.unsafe.all_episodes.count} unsafe · ${challengeSafety.fallback_used.all_episodes.count} fallback; all 60 loaded the frozen checkpoint and produced Genesis live RGB-D plus Purify Go receipts.`}</p>
          </article>
          <article>
            <b>{zh ? "回执一致与失效关闭" : "RECEIPT AGREEMENT + FAIL-CLOSED"}</b>
            <strong>{(receipts.rate * 100).toFixed(1)}%</strong>
            <p>{zh ? `${receipts.count}/${receipts.total} 个可比回执一致。事后描述性审计（不是预注册端点）：${receiptMismatches} 个差异全部出现在 active corridor B，Python=true、Go=false、effective=false；Go 只认到 1 个根并给出 {clear, blocked}。其中 4 个在未选走廊，14 个是最终 joint admit 前的临时评估；没有 selected crossing 靠差异授权。` : `${receipts.count}/${receipts.total} comparable receipts agree. Post-hoc descriptive audit (not a preregistered endpoint): all ${receiptMismatches} differences were active corridor B with Python=true, Go=false, effective=false; Go found one root and returned {clear, blocked}. Four were on the unselected corridor and 14 were transient checks before a later joint admit; no selected crossing relied on a disagreement.`}</p>
          </article>
          <article>
            <b>{zh ? "AMD 全流程墙钟遥测" : "AMD FULL-WALL TELEMETRY"}</b>
            <strong>{challengeTelemetry.sample_count}</strong>
            <p>{zh ? `${challengeTelemetry.measured_wall_seconds.toFixed(3)} 秒，每 ${challengeTelemetry.sample_interval_seconds.toFixed(0)} 秒采样，包含 0% idle；GPU use 平均 ${challengeTelemetry.gpu_use_percent.mean.toFixed(1)}%、P95 ${challengeTelemetry.gpu_use_percent.p95.toFixed(0)}%。完整回合子进程 P95 ${challengeTelemetry.episode_subprocess_wall_seconds.all.p95.toFixed(3)} 秒，不是控制环延迟。` : `${challengeTelemetry.measured_wall_seconds.toFixed(3)} s at ${challengeTelemetry.sample_interval_seconds.toFixed(0)} s intervals, including 0% idle; GPU use mean ${challengeTelemetry.gpu_use_percent.mean.toFixed(1)}%, P95 ${challengeTelemetry.gpu_use_percent.p95.toFixed(0)}%. Complete episode-subprocess P95 was ${challengeTelemetry.episode_subprocess_wall_seconds.all.p95.toFixed(3)} s—not control-loop latency.`}</p>
          </article>
          <article className="boundary-warning">
            <b>{zh ? "一个共享底盘的诚实边界" : "ONE-SHARED-CHASSIS BOUNDARY"}</b>
            <strong>{zh ? "逻辑双角色" : "LOGICAL ROLES"}</strong>
            <p>{zh ? `Carrier 与 Scout 是同一台共享 Genesis 底盘上的独立逻辑姿态、视角和采集根；不是双机同时动力学。运动学负担中，载荷车均值降低 ${carrierReduction.toFixed(1)}%，但团队总路径增加 ${teamIncrease.toFixed(1)}%，不等同能耗或吞吐提升。` : `Carrier and Scout are separate logical poses, viewpoints and capture roots on one shared Genesis chassis—not simultaneous two-body dynamics. Loaded-carrier mean path fell ${carrierReduction.toFixed(1)}%, while total team path rose ${teamIncrease.toFixed(1)}%; this is not an energy or throughput gain.`}</p>
          </article>
        </div>
        <div className="challenge-identities">
          <span><b>REPORT SHA256</b><code>{challengeEvidence.reportSha256}</code></span>
          <span><b>FEASIBILITY AUDIT SHA256</b><code>{challengeEvidence.feasibilityAuditSha256}</code></span>
          <span><b>RAW SHA256</b><code>{challengeEvidence.rawArchiveSha256}</code></span>
          <span><b>VERIFICATION SHA256</b><code>{challengeEvidence.verificationSha256}</code></span>
        </div>
        <div className="evidence-links challenge-links">
          <a href={challengeEvidence.judgeCardUrl} target="_blank" rel="noreferrer">{zh ? "打开 90 秒评委卡 ↗" : "OPEN 90-SECOND JUDGE CARD ↗"}</a>
          <a href={challengeEvidence.reportUrl} target="_blank">{zh ? "机器可读报告 ↗" : "MACHINE-READABLE REPORT ↗"}</a>
          <a href={challengeEvidence.feasibilityAuditUrl} target="_blank">{zh ? "可行性审计 JSON ↗" : "FEASIBILITY AUDIT JSON ↗"}</a>
          <a href={challengeEvidence.rawArchiveUrl}>{zh ? "下载原始归档 ↗" : "DOWNLOAD RAW ARCHIVE ↗"}</a>
          <a href={challengeEvidence.verificationUrl}>{zh ? "独立验证 JSON ↗" : "INDEPENDENT VERIFICATION JSON ↗"}</a>
        </div>
      </div>
    </section>
    <div className="evidence-tier-note"><span>{zh ? "原始永久锁定证据 · 与上方挑战分开" : "ORIGINAL PERMANENT LOCKED EVIDENCE · SEPARATE FROM THE CHALLENGE ABOVE"}</span><p>{zh ? "以下 11/12、0/24 与 3,200-sample 结果仍按原报告保留，不由新挑战覆盖。" : "The 11/12, 0/24 and 3,200-sample results below remain attached to their original report; the new challenge does not overwrite them."}</p></div>
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
        <p className="range-boundary">{zh ? "预留范围同属一个生成器家族：102500–102529 已在公开预注册后评测一次；102530–102699 仍未评测。两者都不表述为 OOD。预开启时间来自第一方 sidecar，并非外部时间戳认证。" : "The reserved range belongs to the same generator family: seeds 102500–102529 were evaluated once after public preregistration; seeds 102530–102699 remain unevaluated. Neither is presented as OOD. Pre-open chronology comes from a first-party sidecar, not an external timestamp authority."}</p>
        <div className="evidence-links">
          <a href={lockedInputEvidence.archiveUrl} target="_blank" rel="noreferrer">{zh ? "下载 1,019,307,579 字节归档 ↗" : "DOWNLOAD 1,019,307,579-BYTE ARCHIVE ↗"}</a>
          <a href={lockedInputEvidence.noteUrl} target="_blank" rel="noreferrer">{zh ? "阅读证据说明 ↗" : "READ EVIDENCE NOTE ↗"}</a>
          <a href={lockedInputEvidence.manifestUrl} target="_blank" rel="noreferrer">{zh ? "检查路径中立 MANIFEST ↗" : "INSPECT PATH-NEUTRAL MANIFEST ↗"}</a>
        </div>
      </div>
    </section>
    {utility && <section className="result-section utility-evidence">
      <div className="result-title"><span>{zh ? "原始永久锁定 · 12-pair 任务效用" : "ORIGINAL PERMANENT LOCKED · 12-PAIR TASK UTILITY"}</span><h2>{zh ? "安全拒绝是底线；主动修证让有用行动重新发生。" : "Safe refusal is the baseline. Active repair earns useful action back."}</h2><p>{zh ? "这是原 12 个相同世界、两种策略的 permanent locked test，不是上方 30-world 预注册挑战。24 个回合均从初始拒绝开始。" : "This is the original permanent locked test across 12 identical paired worlds—not the 30-world preregistered challenge above. All 24 episodes began with the same initial denial."}</p></div>
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
      <div className="result-title"><span>{zh ? "独立补充 · 模型前向基准" : "SEPARATE SUPPLEMENT · MODEL-FORWARD BENCHMARK"}</span><h2>{zh ? "同一冻结权重，单独测量模型前向。" : "The same frozen weights, measured as model forward only."}</h2><p>{benchmark.runtime.device_name} · {benchmark.runtime.gcn_arch_name} · HIP {benchmark.runtime.hip}</p></div>
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
        <span>{zh ? "旧版独立补充 · SYNTHETIC 60 秒前向演示" : "OLDER SEPARATE SUPPLEMENT · SYNTHETIC 60s FORWARD DEMO"}</span>
        <h2>{zh ? "持续一分钟的受控前向负载，GPU 全程有据可查。" : "One sustained minute of controlled forwards, with the GPU accounted for."}</h2>
        <p>{zh ? "这是旧版、独立的提交期 synthetic forward-only 测量，不是上方预注册挑战的全流程墙钟遥测。准确 checkpoint 在加载前通过 SHA 校验，clean preflight 在模型加载前记录到零 KFD 计算进程、0% GPU 使用率和 0% VRAM 分配。" : "This is the older, separate submission-time synthetic forward-only measurement—not the preregistered challenge's full-wall telemetry above. The exact checkpoint passed SHA verification before load; a clean preflight recorded zero KFD compute processes, 0% GPU use and 0% VRAM allocation before model load."}</p>
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
    <section className="result-section report-download">
      <div className="result-title"><span>{zh ? "提交资料" : "SUBMISSION MATERIALS"}</span><h2>{zh ? "评委卡、原始挑战数据、独立验证与复现说明均已归档。" : "The judge card, raw challenge evidence, independent verification and reproduction notes are packaged."}</h2></div>
      <div>
        <a className="report-primary" href={challengeEvidence.judgeCardUrl} target="_blank" rel="noreferrer">{zh ? "打开 90 秒英文评委卡 ↗" : "OPEN 90-SECOND ENGLISH JUDGE CARD ↗"}</a>
        <a href={challengeEvidence.rawArchiveUrl}>{zh ? "下载 30-world 原始挑战归档 ↗" : "DOWNLOAD 30-WORLD RAW CHALLENGE ARCHIVE ↗"}</a>
        <a href={challengeEvidence.verificationUrl}>{zh ? "打开独立验证 JSON ↗" : "OPEN INDEPENDENT VERIFICATION JSON ↗"}</a>
        <a href="/docs/Look-Twice-V8-Technical-Report.pdf" target="_blank">{zh ? "下载技术报告 PDF ↗" : "DOWNLOAD TECHNICAL REPORT PDF ↗"}</a>
        <a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4" target="_blank">{zh ? "观看 3:59 英文演示 ↗" : "WATCH 3:59 ENGLISH DEMO ↗"}</a>
        <a href="https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release" target="_blank">{zh ? "打开冻结源码分支 ↗" : "OPEN FROZEN SOURCE BRANCH ↗"}</a>
        <a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt" target="_blank">{zh ? "下载冻结模型 ↗" : "DOWNLOAD FROZEN CHECKPOINT ↗"}</a>
        <a href="/reproduce?locale=en">{zh ? "打开复现路径 →" : "OPEN REPRODUCTION PATH →"}</a>
        <a href="/media/look-twice-replay-30s.mp4">{zh ? "下载 30 秒证据短片 ↓" : "DOWNLOAD 30-SECOND EVIDENCE REEL ↓"}</a>
      </div>
    </section>
  </main>;
}
