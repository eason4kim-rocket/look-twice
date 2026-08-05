"use client";

import { useEffect, useState } from "react";
import { SiteShell, useLanguage } from "../components/SiteShell";
import { challengeEvidence } from "../lib/challengeEvidence";
import {
  decisionDynamicsEvidence,
  type DecisionDynamicsReport,
} from "../lib/decisionDynamicsEvidence";
import {
  twoShardDynamicsEvidence,
  type SingleSceneDecisionDynamicsReport,
} from "../lib/twoShardDynamicsEvidence";
import {
  dynamicsEvidence,
  type DynamicsReport,
} from "../lib/dynamicsEvidence";
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
  const [decisionDynamics, setDecisionDynamics] =
    useState<DecisionDynamicsReport | null>(null);
  const [scalePrefix, setScalePrefix] =
    useState<SingleSceneDecisionDynamicsReport | null>(null);
  const [scaleSuffix, setScaleSuffix] =
    useState<SingleSceneDecisionDynamicsReport | null>(null);
  const [dynamics, setDynamics] = useState<DynamicsReport | null>(null);
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
    fetch(dynamicsEvidence.reportUrl)
      .then((response) => {
        if (!response.ok) throw new Error("dynamics report unavailable");
        return response.json();
      })
      .then(setDynamics)
      .catch(() => setDynamics(null));
    fetch(decisionDynamicsEvidence.reportUrl)
      .then((response) => {
        if (!response.ok) throw new Error("decision dynamics report unavailable");
        return response.json();
      })
      .then(setDecisionDynamics)
      .catch(() => setDecisionDynamics(null));
    fetch(twoShardDynamicsEvidence.prefixReportUrl)
      .then((response) => {
        if (!response.ok) throw new Error("60-body scale report unavailable");
        return response.json();
      })
      .then(setScalePrefix)
      .catch(() => setScalePrefix(null));
    fetch(twoShardDynamicsEvidence.suffixReportUrl)
      .then((response) => {
        if (!response.ok) throw new Error("30-body suffix report unavailable");
        return response.json();
      })
      .then(setScaleSuffix)
      .catch(() => setScaleSuffix(null));
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
  const dynamicsPoseWrites =
    dynamics?.trials.reduce(
      (total, trial) => total + trial.script_entity_set_pos_calls_after_build,
      0,
    ) ?? 0;
  const scaleTrials =
    (scalePrefix?.summary.trials ?? 0) + (scaleSuffix?.summary.trials ?? 0);
  const scaleActiveMean = scaleTrials
    ? ((scalePrefix?.summary.trials ?? 0) * (scalePrefix?.summary.mean_active_loaded_carrier_path_m ?? 0) +
        (scaleSuffix?.summary.trials ?? 0) * (scaleSuffix?.summary.mean_active_loaded_carrier_path_m ?? 0)) /
      scaleTrials
    : 0;
  const scalePassiveMean = scaleTrials
    ? ((scalePrefix?.summary.trials ?? 0) * (scalePrefix?.summary.mean_passive_loaded_carrier_path_m ?? 0) +
        (scaleSuffix?.summary.trials ?? 0) * (scaleSuffix?.summary.mean_passive_loaded_carrier_path_m ?? 0)) /
      scaleTrials
    : 0;
  const scaleReduction = scalePassiveMean
    ? (1 - scaleActiveMean / scalePassiveMean) * 100
    : 0;
  const twoShardComplete = Boolean(
    scalePrefix?.summary.all_passed &&
      scaleSuffix?.summary.all_passed &&
      scaleSuffix.combined_claim_boundary?.shard_count === 2 &&
      scaleSuffix.combined_claim_boundary.cumulative_non_fixed_robot_entities === 90 &&
      scaleSuffix.combined_claim_boundary.maximum_co_resident_non_fixed_robot_entities === 60 &&
      !scaleSuffix.combined_claim_boundary.all_90_co_resident,
  );
  return <main>
    <header className="page-header challenge-page-header"><div><span className="eyebrow">{zh ? "公开预注册挑战 / 独立验证通过" : "PUBLICLY PREREGISTERED CHALLENGE / INDEPENDENTLY VERIFIED"}</span><h1>{zh ? "结果，带着回执。" : "Results, with receipts."}</h1></div><p>{zh ? "首屏是 30 个同生成器世界、60 个预注册回合的挑战结果。原 12-pair permanent locked test 与旧 synthetic 60s 前向演示在下方分开保留。" : "The first evidence tier is the preregistered 30-world, 60-episode same-generator challenge. The original 12-pair permanent locked test and the older synthetic 60s forward demo remain explicitly separate below."}</p></header>
    <section className="result-section challenge-primary-evidence">
      <div className="result-title">
        <span>{zh ? "主计分证据 · 30 个成对世界" : "PRIMARY SCORING EVIDENCE · 30 PAIRED WORLDS"}</span>
        <h2>{zh ? "主动修复恢复 29/30 全链直行；被动策略保持 0/30。" : "Active repair restored 29/30 full-chain direct; passive remained at 0/30."}</h2>
        <p>{zh ? `种子 ${challenge.analysis.evidence_scope.seed_range[0]}–${challenge.analysis.evidence_scope.seed_range[1]} 在公开预注册之后仅评测一次。该挑战与原 12-pair locked test 分开，来自相同生成器家族，不是 OOD。` : `Seeds ${challenge.analysis.evidence_scope.seed_range[0]}–${challenge.analysis.evidence_scope.seed_range[1]} were evaluated once after public preregistration. This challenge is separate from the original 12-pair locked test, comes from the same generator family, and is not OOD.`}</p>
      </div>
      <div className="benchmark-panel challenge-panel">
        <div className="benchmark-tags"><span>PUBLIC PREREGISTRATION</span><span>30 PAIRED WORLDS</span><span>60 / 60 VALID</span><span>VERIFIER PASS</span></div>
        <div className="benchmark-grid challenge-primary-grid">
          <article><span>{zh ? "主动全链直行" : "ACTIVE FULL-CHAIN DIRECT"}</span><strong>{primary.active.count}<small>/{primary.active.total}</small></strong><i>95% Wilson 83.3–99.4%</i></article>
          <article><span>{zh ? "被动全链直行" : "PASSIVE FULL-CHAIN DIRECT"}</span><strong>{primary.passive.count}<small>/{primary.passive.total}</small></strong><i>95% Wilson 0.0–11.4%</i></article>
          <article><span>{zh ? "成对差值" : "PAIRED DIFFERENCE"}</span><strong>+{primary.active_minus_passive.percentage_points.toFixed(1)}<small> pp</small></strong><i>29 active-only · 1 neither</i></article>
          <article><span>{zh ? "双侧精确 McNemar" : "EXACT TWO-SIDED McNEMAR"}</span><strong>3.725×10<sup>−9</sup></strong><i>p-value · no success threshold</i></article>
        </div>
        <div className="feasibility-proof">
          <article><span>{zh ? "次级事后审计 · 离线可行性一致路线" : "SECONDARY POST-HOC AUDIT · FEASIBILITY-CONSISTENT ROUTES"}</span><strong>30<small>/30</small></strong></article>
          <article><span>{zh ? "存在 CLEAR 走廊时安全直行" : "DIRECT WITH AN ORACLE-CLEAR CORRIDOR"}</span><strong>29<small>/29</small></strong></article>
          <article><span>{zh ? "双廊均阻塞时安全绕行" : "SAFE DETOUR WHEN BOTH WERE BLOCKED"}</span><strong>1<small>/1</small></strong></article>
          <p>{zh ? "* 事后描述性 oracle 审计，不是预注册端点；oracle 从未提供给控制器。上方预注册主端点保持 29/30 对 0/30。" : "* Post-hoc descriptive oracle audit, not a preregistered endpoint; oracle was never available to the controller. The preregistered primary above remains 29/30 versus 0/30."}</p>
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
    {twoShardComplete && scalePrefix && scaleSuffix && <section className="result-section dynamics-evidence">
      <div className="result-title">
        <span>{zh ? "SOLVER-SCALE 补充 · 两个完整场景分片" : "SOLVER-SCALE COMPLEMENT · TWO COMPLETED SCENE SHARDS"}</span>
        <h2>{zh ? "60体场景 20/20，加30体场景 10/10：固定30 seeds覆盖完成。" : "20/20 in one 60-body scene plus 10/10 in one 30-body scene: all 30 fixed seeds covered."}</h2>
        <p>{zh ? "两份报告分别通过独立 verifier。它们合计实例化90个不同非固定机器人，最大同时驻留60个；90个机器人从未处于同一场景。主端点仍是主动29/30、被动0/30。" : "Each report passed its independent verifier. Together they instantiate 90 distinct non-fixed robots, with at most 60 co-resident. The 90 robots were never co-resident in one scene. The primary remains active 29/30 versus passive 0/30."}</p>
      </div>
      <div className="benchmark-panel dynamics-panel">
        <div className="benchmark-tags"><span>ADDITIVE NON-LOCKED</span><span>EXACTLY 2 SCENE SHARDS</span><span>CUMULATIVE 90 · MAX CO-RESIDENT 60</span><span>2× VERIFIER PASS</span></div>
        <div className="benchmark-grid dynamics-grid">
          <article><span>{zh ? "固定 SEEDS 通过" : "FIXED SEEDS PASSED"}</span><strong>{scaleTrials}<small>/30</small></strong></article>
          <article><span>{zh ? "场景分片" : "SCENE SHARDS"}</span><strong>2<small> completed</small></strong></article>
          <article><span>{zh ? "累计 / 最大同场机器人" : "CUMULATIVE / MAX CO-RESIDENT"}</span><strong>90<small> / 60</small></strong></article>
          <article><span>{zh ? "载荷车合并路径缩短" : "COMBINED CARRIER REDUCTION"}</span><strong>{scaleReduction.toFixed(2)}<small>%</small></strong></article>
        </div>
        <div className="dynamics-audit-grid">
          <article><b>{zh ? "两个完整分片" : "TWO COMPLETE SHARDS"}</b><strong>20<small>/20 @ 60</small> + 10<small>/10 @ 30</small></strong><p>{zh ? "前缀覆盖 seeds 102500–102519；后缀覆盖 102520–102529。两个场景 ID 不同，不做跨分片恢复或结果拼接。" : "The prefix covers seeds 102500–102519; the suffix covers 102520–102529. Their scene IDs differ, with no cross-shard resume or outcome stitching."}</p></article>
          <article><b>{zh ? "决策绑定的刚体结果" : "DECISION-BOUND RIGID OUTCOME"}</b><strong>90<small>/90 reached</small></strong><p>{zh ? "30个 Scout、30个主动载荷车与30个被动载荷车全部到达；29个直行配对各节省至少0.50 m，唯一双廊阻塞场景安全外绕。" : "All 30 scouts, 30 active carriers and 30 passive carriers reached. Every one of 29 direct pairs saved at least 0.50 m; the sole dual-blocked case took the safe outer detour."}</p></article>
          <article><b>{zh ? "接触、稳定性与驱动" : "CONTACTS, STABILITY + ACTUATION"}</b><strong>0<small>{zh ? " 障碍物/主动配对接触记录行" : " blocker / active-pair contact rows"}</small></strong><p>{zh ? `build后位姿写入为0，仅使用轮速控制；最大倾角 ${Math.max(scalePrefix.summary.maximum_tilt_deg, scaleSuffix.summary.maximum_tilt_deg).toFixed(3)}°，最大停车漂移 ${(Math.max(scalePrefix.summary.maximum_stationary_partner_drift_m, scaleSuffix.summary.maximum_stationary_partner_drift_m) * 100).toFixed(3)} cm。` : `Zero post-build pose writes; wheel-velocity control only. Maximum tilt was ${Math.max(scalePrefix.summary.maximum_tilt_deg, scaleSuffix.summary.maximum_tilt_deg).toFixed(3)}° and maximum parked drift was ${(Math.max(scalePrefix.summary.maximum_stationary_partner_drift_m, scaleSuffix.summary.maximum_stationary_partner_drift_m) * 100).toFixed(3)} cm.`}</p></article>
          <article className="boundary-warning"><b>{zh ? "必须保留的边界" : "REQUIRED BOUNDARY"}</b><strong>{zh ? "累计90 ≠ 90同场" : "CUMULATIVE 90 ≠ 90 CO-RESIDENT"}</strong><p>{zh ? "这是归档决策的固定顺序串行轮驱重放，不是在刚体运行中重新执行实时感知策略，不是同步多机器人协作、真机测试、sim-to-real或安全认证。" : "This is a fixed-order serial wheel replay of archived decisions—not a live perception-policy rerun inside the rigid-body run, simultaneous multi-robot cooperation, a physical-robot test, sim-to-real evidence or safety certification."}</p></article>
        </div>
        <div className="challenge-identities dynamics-identities">
          <span><b>60-BODY REPORT SHA256</b><code>{twoShardDynamicsEvidence.prefixReportSha256}</code></span>
          <span><b>30-BODY REPORT SHA256</b><code>{twoShardDynamicsEvidence.suffixReportSha256}</code></span>
        </div>
        <div className="evidence-links">
          <a href={twoShardDynamicsEvidence.prefixReportUrl} target="_blank">{zh ? "60体报告 ↗" : "60-BODY REPORT ↗"}</a>
          <a href={twoShardDynamicsEvidence.suffixReportUrl} target="_blank">{zh ? "30体后缀报告 ↗" : "30-BODY SUFFIX REPORT ↗"}</a>
          <a href={twoShardDynamicsEvidence.prefixPackageChecksumsUrl} target="_blank">{zh ? "60体完整包校验索引（需克隆）↗" : "60-BODY PACKAGE INDEX (CLONE REQUIRED) ↗"}</a>
          <a href={twoShardDynamicsEvidence.suffixPackageChecksumsUrl} target="_blank">{zh ? "30体完整包校验索引（需克隆）↗" : "30-BODY PACKAGE INDEX (CLONE REQUIRED) ↗"}</a>
          <a href={twoShardDynamicsEvidence.prefixProtocolUrl} target="_blank" rel="noreferrer">{zh ? "60体协议 ↗" : "60-BODY PROTOCOL ↗"}</a>
          <a href={twoShardDynamicsEvidence.suffixProtocolUrl} target="_blank" rel="noreferrer">{zh ? "30体后缀协议 ↗" : "30-BODY SUFFIX PROTOCOL ↗"}</a>
        </div>
      </div>
    </section>}
    {decisionDynamics?.summary.all_passed && <section className="result-section dynamics-evidence">
      <div className="result-title">
        <span>{zh ? "独立补充 · 归档决策到轮驱动力学" : "SEPARATE ADDITIVE · ARCHIVED DECISIONS TO WHEEL DYNAMICS"}</span>
        <h2>{zh ? "30/30 固定场景通过；90/90 非固定刚体到达；29/29 直行配对保留仿真刚体路径优势。" : "30/30 fixed scenes passed. 90/90 non-fixed bodies reached. All 29 direct pairs kept a simulated rigid-body path advantage."}</h2>
        <p>{zh ? "V2 将已归档的 29 个直行决策与唯一安全绕行，分别绑定到 30 个独立 Genesis 三实体场景。它不是实时感知策略重跑，也不是同场 90 实体；上方预注册主端点仍为主动 29/30 对被动 0/30。" : "V2 binds the 29 archived direct decisions and the single safe detour to 30 independent three-body Genesis scenes. It is not a live perception-policy rerun or one simultaneous 90-body scene; the preregistered primary above remains active 29/30 versus passive 0/30."}</p>
      </div>
      <div className="benchmark-panel dynamics-panel">
        <div className="benchmark-tags"><span>ADDITIVE NON-LOCKED</span><span>30 FIXED SEEDS</span><span>30 INDEPENDENT SCENES</span><span>REMOTE + LOCAL VERIFIER PASS</span></div>
        <div className="benchmark-grid dynamics-grid">
          <article><span>{zh ? "固定试验通过" : "FIXED TRIALS PASSED"}</span><strong>{decisionDynamics.summary.passed}<small>/{decisionDynamics.summary.trials}</small></strong></article>
          <article><span>{zh ? "到达的非固定实体" : "NON-FIXED BODIES REACHED"}</span><strong>90<small>/90</small></strong></article>
          <article><span>{zh ? "载荷车成对均值缩短" : "PAIRED MEAN CARRIER REDUCTION"}</span><strong>{decisionDynamics.summary.paired_mean_path_reduction_percent.toFixed(2)}<small>%</small></strong></article>
          <article><span>{zh ? "BLOCKER / ACTIVE-PAIR 接触行" : "BLOCKER / ACTIVE-PAIR CONTACT ROWS"}</span><strong>{decisionDynamics.summary.total_blocker_contact_rows}<small> / {decisionDynamics.summary.total_active_pair_contact_rows}</small></strong></article>
        </div>
        <div className="dynamics-audit-grid">
          <article><b>{zh ? "决策与到达完整性" : "DECISION + ARRIVAL COMPLETENESS"}</b><strong>{decisionDynamics.summary.active_direct_decisions}<small> direct</small> + {decisionDynamics.summary.active_safe_detours}<small> detour</small></strong><p>{zh ? "所有 30 个 Scout、30 个 active Carrier 与 30 个 passive Carrier 均以轮速驱动并到达。双廊阻塞 seed 102515 执行预声明安全外绕。" : "All 30 scouts, 30 active carriers and 30 passive carriers were wheel-actuated and reached. Dual-blocked seed 102515 executed the declared safe outer detour."}</p></article>
          <article><b>{zh ? "成对载荷车负担" : "PAIRED LOADED-CARRIER BURDEN"}</b><strong>{decisionDynamics.summary.mean_active_loaded_carrier_path_m.toFixed(2)}<small> vs {decisionDynamics.summary.mean_passive_loaded_carrier_path_m.toFixed(2)} m</small></strong><p>{zh ? `${decisionDynamics.summary.direct_pairs_saving_at_least_0_50_m}/29 个直行配对全部至少节省 0.50 m。该结果不等同团队总路程、能耗、任务时间或吞吐改善。` : `${decisionDynamics.summary.direct_pairs_saving_at_least_0_50_m}/29 direct pairs each saved at least 0.50 m. This is not a claim about total team travel, energy, task time or throughput.`}</p></article>
          <article><b>{zh ? "可恢复执行" : "RECOVERABLE EXECUTION"}</b><strong>30<small> sealed checkpoints</small></strong><p>{zh ? "V1 的 90 实体同场运行在 4 小时和 12 小时 watchdog 前均未写报告。V2 每完成一个固定 seed 即原子落盘；留存 ledger 显示 30 个 worker 均首次退出 0，无替换。" : "V1's one-scene 90-body layout wrote no report before its four- and 12-hour watchdogs. V2 atomically sealed every fixed seed; the retained ledger shows 30 first-attempt worker exits at zero, with no replacement."}</p></article>
          <article className="boundary-warning"><b>{zh ? "证明范围已披露" : "PROOF SCOPE DISCLOSED"}</b><strong>{zh ? "观察证据 ≠ 完美证明" : "OBSERVED, NOT OVERCLAIMED"}</strong><p>{zh ? "原始 formal SHA 未覆盖 attempts/progress/logs，source binding 也漏列直接依赖 v4_motion.py。完整外层校验现已固定所有留存文件，且 2,419 文件的事后整树审计为 clean；这些是补强证据，不宣称连续密码学证明。" : "The original formal SHA omitted attempts/progress/logs, and source binding omitted the direct v4_motion.py dependency. A complete outer checksum now fixes every retained file and a 2,419-file post-run tree audit was clean; these corroborate the run without claiming continuous cryptographic attestation."}</p></article>
        </div>
        <div className="challenge-identities dynamics-identities">
          <span><b>REPORT SHA256</b><code>{decisionDynamicsEvidence.reportSha256}</code></span>
          <span><b>SOURCE BINDING SHA256</b><code>{decisionDynamicsEvidence.sourceBindingSha256}</code></span>
          <span><b>PROVENANCE REVIEW SHA256</b><code>{decisionDynamicsEvidence.provenanceReviewSha256}</code></span>
          <span><b>SOURCE COMMIT</b><code>{decisionDynamicsEvidence.sourceCommit}</code></span>
        </div>
        <div className="evidence-links">
          <a href={decisionDynamicsEvidence.reportUrl} target="_blank">{zh ? "机器报告 ↗" : "MACHINE REPORT ↗"}</a>
          <a href={decisionDynamicsEvidence.executionAuditUrl} target="_blank">{zh ? "执行审计 ↗" : "EXECUTION AUDIT ↗"}</a>
          <a href={decisionDynamicsEvidence.provenanceReviewUrl} target="_blank">{zh ? "证明范围审计 ↗" : "PROVENANCE REVIEW ↗"}</a>
          <a href={decisionDynamicsEvidence.packageChecksumsUrl} target="_blank">{zh ? "完整包校验 ↗" : "COMPLETE PACKAGE CHECKSUMS ↗"}</a>
          <a href={decisionDynamicsEvidence.attemptsUrl} target="_blank">{zh ? "尝试账本 ↗" : "ATTEMPT LEDGER ↗"}</a>
          <a href={decisionDynamicsEvidence.protocolUrl} target="_blank" rel="noreferrer">{zh ? "固定 V2 协议 ↗" : "FIXED V2 PROTOCOL ↗"}</a>
          <a href={decisionDynamicsEvidence.resultNoteUrl} target="_blank" rel="noreferrer">{zh ? "结果说明 ↗" : "RESULT NOTE ↗"}</a>
        </div>
      </div>
    </section>}
    {dynamics?.summary.all_passed && <section className="result-section dynamics-evidence">
      <div className="result-title">
        <span>{zh ? "独立补充 · 双实体刚体动力学" : "SEPARATE ADDITIVE · DUAL-BODY RIGID DYNAMICS"}</span>
        <h2>{zh ? "两个非固定实体；只用轮速驱动；20 个固定种子全通过。" : "Two non-fixed bodies. Wheel actuation only. All 20 fixed seeds passed."}</h2>
        <p>{zh ? "该补充回答一个窄问题：逻辑 Carrier 与 Scout 能否另行实例化为两个 Genesis 刚体并完成有界仓储运动。它不是冻结 V8 策略重跑，也不替换上方 29/30 主结果。" : "This supplement answers one narrow question: can the logical Carrier and Scout roles also be instantiated as two Genesis rigid bodies and complete bounded warehouse motion? It is not a frozen-policy rerun and does not replace the 29/30 primary result above."}</p>
      </div>
      <div className="benchmark-panel dynamics-panel">
        <div className="benchmark-tags"><span>ADDITIVE NON-LOCKED</span><span>20 FIXED SEEDS</span><span>AMD ROCm</span><span>REMOTE + LOCAL VERIFIER PASS</span></div>
        <div className="benchmark-grid dynamics-grid">
          <article><span>{zh ? "通过" : "PASSED"}</span><strong>{dynamics.summary.passed}<small>/{dynamics.summary.trials}</small></strong></article>
          <article><span>{zh ? "非固定机器人实体" : "NON-FIXED ROBOT ENTITIES"}</span><strong>{dynamics.summary.distinct_non_fixed_robot_entities}</strong></article>
          <article><span>{zh ? "障碍物 / 双车接触行" : "BLOCKER / PAIR CONTACT ROWS"}</span><strong>{dynamics.summary.total_obstacle_contact_rows}<small> / {dynamics.summary.total_pair_robot_contact_rows}</small></strong></article>
          <article><span>{zh ? "BUILD 后脚本位姿写入" : "SCRIPT POSE WRITES AFTER BUILD"}</span><strong>{dynamicsPoseWrites}</strong></article>
        </div>
        <div className="dynamics-audit-grid">
          <article><b>{zh ? "稳定性" : "STABILITY"}</b><strong>{dynamics.summary.maximum_tilt_deg.toFixed(2)}°</strong><p>{zh ? `最大倾角；固定上限 20°。最大静止伙伴漂移 ${(dynamics.summary.maximum_stationary_partner_drift_m * 100).toFixed(2)} cm，上限 8 cm。` : `Maximum tilt against a fixed 20° ceiling. Maximum parked-partner drift was ${(dynamics.summary.maximum_stationary_partner_drift_m * 100).toFixed(2)} cm against an 8 cm ceiling.`}</p></article>
          <article><b>{zh ? "有界刚体运动（仿真）" : "BOUNDED NONTRIVIAL MOTION"}</b><strong>{dynamics.summary.mean_carrier_path_m.toFixed(2)}<small> m</small></strong><p>{zh ? `载荷车平均路径；Scout 平均 ${dynamics.summary.mean_scout_path_m.toFixed(2)} m。后构建唯一驱动 API 是 ${dynamics.protocol.post_build_actuation_api}。` : `Mean carrier path; the scout mean was ${dynamics.summary.mean_scout_path_m.toFixed(2)} m. The only post-build actuation API was ${dynamics.protocol.post_build_actuation_api}.`}</p></article>
          <article className="boundary-warning"><b>{zh ? "解释边界" : "INTERPRETATION BOUNDARY"}</b><strong>{zh ? "顺序驱动" : "SEQUENTIAL PHASES"}</strong><p>{zh ? "先驱动 Scout、Carrier 保持停车；再驱动 Carrier、Scout 保持停车。这证明双实体轮驱动力学，不证明完整策略已迁移为双机同时协作，也不是真机结果。" : "The scout moved while the carrier stayed parked, then the carrier moved while the scout stayed parked. This validates dual-body wheel dynamics—not a full-policy conversion to simultaneous cooperative control, and not a physical-robot result."}</p></article>
          <article><b>{zh ? "恢复透明度" : "RECOVERY TRANSPARENCY"}</b><strong>3600 → 10800<small> s</small></strong><p>{zh ? "第一次只有外部 watchdog 超时，未写报告、未观察 seed 结果。第二次仅增加 watchdog；代码、20 seeds、阈值完全不变。" : "Attempt 1 hit only the external watchdog before any report or seed outcome was observed. Attempt 2 changed only that watchdog; code, 20 seeds and thresholds stayed fixed."}</p></article>
        </div>
        <div className="challenge-identities dynamics-identities">
          <span><b>REPORT SHA256</b><code>{dynamicsEvidence.reportSha256}</code></span>
          <span><b>RECOVERY AUDIT SHA256</b><code>{dynamicsEvidence.recoveryAuditSha256}</code></span>
          <span><b>SOURCE COMMIT</b><code>{dynamicsEvidence.sourceCommit}</code></span>
        </div>
        <div className="evidence-links">
          <a href={dynamicsEvidence.reportUrl} target="_blank">{zh ? "机器报告 ↗" : "MACHINE REPORT ↗"}</a>
          <a href={dynamicsEvidence.timeoutAuditUrl} target="_blank">{zh ? "超时审计 ↗" : "TIMEOUT AUDIT ↗"}</a>
          <a href={dynamicsEvidence.recoveryAuditUrl} target="_blank">{zh ? "RECOVERY 审计 ↗" : "RECOVERY AUDIT ↗"}</a>
          <a href={dynamicsEvidence.checksumsUrl} target="_blank">SHA256SUMS ↗</a>
          <a href={dynamicsEvidence.protocolUrl} target="_blank" rel="noreferrer">{zh ? "固定协议 ↗" : "FIXED PROTOCOL ↗"}</a>
          <a href={dynamicsEvidence.resultNoteUrl} target="_blank" rel="noreferrer">{zh ? "结果说明 ↗" : "RESULT NOTE ↗"}</a>
        </div>
      </div>
    </section>}
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
