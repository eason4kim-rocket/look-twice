"use client";

import Link from "next/link";
import { SiteShell, useLanguage } from "./components/SiteShell";
import { challengeEvidence } from "./lib/challengeEvidence";
import { contractProgressEvidence } from "./lib/contractProgressEvidence";

const flow = [
  ["01", "Observe", "RGB-D claims arrive with time, scope, calibration and capture lineage.", "观察", "RGB-D 证据声明（Claim）携带时间、范围、校准与采集谱系。"],
  ["02", "Qualify", "Purify checks independence, prediction sets and the action contract.", "准入", "Purify 检查独立性、预测集与动作合同。"],
  ["03", "Repair", "When one snapshot is insufficient, the scout moves to an independent verification viewpoint.", "修证", "一张快照不足时，侦察车移动到独立复核视角。"],
  ["04", "Act", "Only Python ∧ Purify Go admission authorizes a direct physical action.", "行动", "只有 Python ∧ Purify Go 双重准入才授权直接物理行动。"],
];

export default function Home() {
  return (
    <SiteShell>
      <HomeContent />
    </SiteShell>
  );
}

function HomeContent() {
  const { language } = useLanguage();
  const zh = language === "zh";
  const href = (path: string) => `${path}?locale=${language}`;
  return (
    <main>
      <section className="hero section-grid">
        <div className="hero-copy">
          <div className="eyebrow"><span className="live-dot" /> {zh ? "AMD GPU · 物理 AI · 证据保障" : "AMD GPU · PHYSICAL AI · EVIDENCE ASSURANCE"}</div>
          <h1>{zh ? <>行动之前，<em>再看一次。</em></> : <>Before a robot acts,<br/><em>look twice.</em></>}</h1>
          <p className="hero-lead">{zh
            ? "Look Twice 将不稳定、冲突且同源的机器人观察，转化为可供物理动作依赖的可信事实；证据不足时，它主动修复证据。"
            : "Look Twice turns noisy, conflicting and correlated robot observations into action-qualified facts—and actively repairs evidence when confidence is not enough."}</p>
          <div className="challenge-proof" aria-label={zh ? "预注册主端点与事后可行性审计" : "Preregistered primary endpoint and post-hoc feasibility audit"}>
            <div className="challenge-proof-head">
              <span>{zh ? "预注册主端点 · 30 个成对世界" : "PREREGISTERED PRIMARY · 30 PAIRED WORLDS"}</span>
              <b>{zh ? "主动 29/30 · 被动 0/30" : "ACTIVE 29/30 · PASSIVE 0/30"}</b>
            </div>
            <div className="challenge-proof-grid">
              <div><strong>29<small>/30</small></strong><span>{zh ? "主动策略全链直行" : "active full-chain direct"}</span></div>
              <div><strong>0<small>/30</small></strong><span>{zh ? "被动策略全链直行" : "passive full-chain direct"}</span></div>
              <div><strong>60<small>/60</small></strong><span>{zh ? "任务成功 · 0 unsafe · 0 fallback" : "mission success · 0 unsafe · 0 fallback"}</span></div>
            </div>
            <p className="challenge-proof-note">{zh
              ? "次级事后 oracle 审计：29/29 个存在 clear 走廊的世界直行，1/1 个双廊阻塞世界绕行，即 30/30 路线符合离线可行性。oracle 从未提供给控制器，也不是预注册端点。"
              : "Secondary post-hoc oracle audit: 29/29 worlds with a clear corridor went direct and the 1/1 dual-blocked world detoured, so 30/30 routes matched offline feasibility. Oracle was never available to the controller; this is not a preregistered endpoint."}</p>
            <div className="challenge-proof-links">
              <a href={challengeEvidence.judgeCardUrl} target="_blank" rel="noreferrer">{zh ? "90 秒评委卡 ↗" : "90-SECOND JUDGE CARD ↗"}</a>
              <a href={challengeEvidence.feasibilityAuditUrl} target="_blank" rel="noreferrer">{zh ? "可行性审计 ↗" : "FEASIBILITY AUDIT ↗"}</a>
              <a href={challengeEvidence.rawArchiveUrl}>{zh ? "原始归档 ↗" : "RAW ARCHIVE ↗"}</a>
              <a href={challengeEvidence.verificationUrl}>{zh ? "验证回执 ↗" : "VERIFICATION ↗"}</a>
            </div>
          </div>
          <div className="challenge-proof" aria-label={zh ? "20 个成对世界的增量效率证据" : "Additive efficiency evidence across 20 paired worlds"}>
            <div className="challenge-proof-head">
              <span>{zh ? "增量效率层 · 20 个成对世界 / 40 个回合单元" : "ADDITIVE EFFICIENCY TIER · 20 PAIRED WORLDS / 40 CELLS"}</span>
              <b>{zh ? "直行保持 20/20 对 20/20" : "DIRECT HELD AT 20/20 VS 20/20"}</b>
            </div>
            <div className="challenge-proof-grid">
              <div><strong>−40.2563<small>%</small></strong><span>{zh ? "Scout 平均路径" : "mean scout path"}</span></div>
              <div><strong>−15.0306<small>%</small></strong><span>{zh ? "团队平均路径" : "mean team path"}</span></div>
              <div><strong>−27.5362<small>%</small></strong><span>{zh ? "平均物理采集数" : "mean physical captures"}</span></div>
            </div>
            <p className="challenge-proof-note">{zh
              ? "20/20 个 seed 的 Scout 与团队 candidate−baseline 路径差都为负；40/40 结构有效且任务成功，0 unsafe、collision、fallback、false-clear。候选侧共 30 次原生 selector 决策，0 次 delegated。"
              : "Scout and team candidate−baseline path deltas were negative on 20/20 seeds; 40/40 cells were structurally valid and mission-successful, with 0 unsafe, collision, fallback or false-clear outcomes. The candidate made 30 native selector decisions and 0 delegated decisions."}</p>
            <p className="challenge-proof-note">{zh
              ? "边界：同生成器、非锁定、非 OOD 的运动学仿真；formal_result_eligible=false，不是真机结果，也不替代上方 30-world 主证据。"
              : "Boundary: same-generator, non-locked, not-OOD kinematic simulation; formal_result_eligible=false. This is not physical-robot evidence and does not replace the 30-world primary tier above."}</p>
            <div className="challenge-proof-links">
              <Link href={`${href("/results")}#contract-progress-efficiency`}>{zh ? "审计效率层 →" : "AUDIT EFFICIENCY TIER →"}</Link>
              <a href={contractProgressEvidence.reportUrl} target="_blank">{zh ? "报告 JSON ↗" : "REPORT JSON ↗"}</a>
              <a href={contractProgressEvidence.verificationUrl} target="_blank">{zh ? "验证 JSON ↗" : "VERIFICATION JSON ↗"}</a>
              <a href={contractProgressEvidence.rocmTelemetryUrl} target="_blank">{zh ? "ROCm 遥测 ↗" : "ROCm TELEMETRY ↗"}</a>
              <a href={contractProgressEvidence.preregistrationBranchUrl} target="_blank" rel="noreferrer">{zh ? "公开预注册分支 ↗" : "PUBLIC PREREG BRANCH ↗"}</a>
              <a href={contractProgressEvidence.commitBUrl} target="_blank" rel="noreferrer">COMMIT B ↗</a>
            </div>
          </div>
          <div className="hero-actions">
            <Link className="button primary" href={href("/console")}>{zh ? "打开证据控制台" : "Open Evidence Console"}<span>↗</span></Link>
            <Link className="button ghost" href={href("/results")}>{zh ? "查看挑战结果" : "Inspect challenge result"}</Link>
          </div>
          <div className="truth-strip">
            <span>{zh ? "AMD 全流程墙钟遥测" : "AMD FULL-WALL TELEMETRY"}</span>
            <span>{zh ? "仅限仿真" : "SIMULATION ONLY"}</span>
            <span>{zh ? "冻结策略：一台共享 GENESIS 底盘" : "FROZEN POLICY: ONE SHARED GENESIS CHASSIS"}</span>
            <span>{zh ? "规模补充：60体 20/20 + 30体 10/10 · 累计90 · 最大同场60" : "SCALE COMPLEMENT: 20/20 @ 60-BODY + 10/10 @ 30-BODY · CUMULATIVE 90 · MAX CO-RESIDENT 60"}</span>
            <span>{zh ? "独立 V2：30/30 · 90 实体/30 场景" : "SEPARATE DYNAMICS: 30/30 · 90 BODIES / 30 SCENES"}</span>
          </div>
        </div>
        <div className="hero-system" aria-label={zh ? "Look Twice 系统状态" : "Look Twice system status"}>
          <div className="system-head"><span>{zh ? "仓储 AMR / C-04 区" : "WAREHOUSE AMR / ZONE C-04"}</span><b>{zh ? "证据保障在线" : "ASSURANCE ONLINE"}</b></div>
          <div className="warehouse-map">
            <div className="rack rack-a">{zh ? "货架 A" : "RACK A"}</div><div className="rack rack-b">{zh ? "货架 B" : "RACK B"}</div>
            <div className="corridor corridor-a"><span>{zh ? "走廊 A" : "CORRIDOR A"}</span></div>
            <div className="corridor corridor-b"><span>{zh ? "走廊 B" : "CORRIDOR B"}</span><i /></div>
            <div className="robot-marker"><b>LT</b><span>AMR-07</span></div>
            <div className="scan-cone" />
          </div>
          <div className="contract-mini">
            <div><span>{zh ? "动作" : "ACTION"}</span><b>{zh ? "穿越区域" : "CROSS REGION"}</b></div>
            <div><span>{zh ? "初始门控" : "INITIAL GATE"}</span><b className="denied">{zh ? "拒绝" : "DENIED"}</b></div>
            <div><span>{zh ? "下一动作" : "NEXT ACTION"}</span><b className="cyan">{zh ? "获取新证据根" : "ACQUIRE NEW ROOT"}</b></div>
          </div>
        </div>
      </section>

      <section className="section block-section">
        <div className="section-heading"><span>{zh ? "01 / 证据缺口" : "01 / THE GAP"}</span><h2>{zh ? "感知不是事实。数量也不是独立证据。" : "A perception is not a fact. More claims are not always more evidence."}</h2></div>
        <div className="problem-grid">
          <article><b>06</b><span>{zh ? "输入证据声明" : "incoming claims"}</span><p>{zh ? "看起来证据很多" : "Evidence appears abundant"}</p></article>
          <article className="warning"><b>01</b><span>{zh ? "物理采集根" : "physical capture root"}</span><p>{zh ? "同源复制不会增加确定性" : "Echoes add no independence"}</p></article>
          <article className="resolution"><b>{zh ? "拒绝" : "DENY"}</b><span>{zh ? "动作合同" : "ACTION CONTRACT"}</span><p>{zh ? "先修证据，再授权动作" : "Repair evidence before action"}</p></article>
        </div>
      </section>

      <section className="section flow-section">
        <div className="section-heading"><span>{zh ? "02 / 完整闭环" : "02 / CLOSED LOOP"}</span><h2>{zh ? "从观察到授权的完整闭环" : "One accountable loop from observation to action"}</h2></div>
        <div className="flow-grid">{flow.map((item) => <article key={item[0]}><span>{item[0]}</span><h3>{zh ? item[3] : item[1]}</h3><p>{zh ? item[4] : item[2]}</p></article>)}</div>
      </section>

      <section className="section policy-section">
        <div className="section-heading">
          <span>{zh ? "03 / 主动与被动" : "03 / THE DIFFERENCE"}</span>
          <h2>{zh ? "安全拒绝只是底线。主动修复证据，才让机器人重新获得行动能力。" : "Safe refusal is the baseline. Active repair earns useful action back."}</h2>
        </div>
        <div className="policy-comparison">
          <article>
            <span>{zh ? "被动策略" : "PASSIVE"}</span>
            <h3>{zh ? "拒绝并绕行" : "Deny and detour"}</h3>
            <p>{zh ? "证据不足时保持安全，但为不确定性付出路线成本。" : "Stays safe under uncertainty, but pays with a longer route."}</p>
            <b>{zh ? "预注册挑战：0/30 全链直行" : "PREREGISTERED CHALLENGE: 0/30 FULL-CHAIN DIRECT"}</b>
          </article>
          <article className="active-policy">
            <span>{zh ? "主动策略" : "ACTIVE"}</span>
            <h3>{zh ? "换视角、修证据、再行动" : "Move, repair, then act"}</h3>
            <p>{zh ? "侦察车 Scout 获取独立侧视根；Python 与 Purify 同时准入后，载具 Carrier 才直接通行。" : "A scout acquires an independent side-view root. Only Python ∧ Purify admission unlocks the carrier."}</p>
            <b>{zh ? "29/29 可直达世界安全直行 · 1/1 双阻塞绕行*" : "29/29 FEASIBLE WORLDS DIRECT · 1/1 DUAL-BLOCKED DETOUR*"}</b>
          </article>
        </div>
        <div className="platform-row">
          <div><span>AMD GPU</span><p>{zh ? "加速 Genesis RGB-D、空间视觉推理与实验矩阵。" : "Accelerates Genesis RGB-D, spatial vision inference and experiment matrices."}</p></div>
          <div><span>PURIFY</span><p>{zh ? "检查校准、谱系、独立根与动作合同，并生成规范化门控回执（GateReceipt）。" : "Checks calibration, lineage, independent roots and the action contract, then emits a canonical GateReceipt."}</p></div>
          <div><span>{zh ? "诚实边界" : "BOUNDARY"}</span><p>{zh ? "冻结完整策略仍是共享底盘运动学。独立非锁定 V2 在 30 个串行三实体场景中回放归档决策并通过 30/30；它不是实时策略重跑、同场 90 实体、双真机或安全认证。" : "The frozen full policy remains shared-chassis kinematic. A separate non-locked V2 replay passed 30/30 archived decisions in 30 serial three-body scenes; it is not a live-policy rerun, one 90-body scene, two physical robots or a safety certification."}</p></div>
        </div>
      </section>

      <section id="full-demo" className="section reel-section">
        <div className="section-heading">
          <span>{zh ? "04 / 完整演示视频" : "04 / COMPLETE DEMO VIDEO"}</span>
          <h2>{zh ? "直接观看完整 3:59 工作流：从 AMD GPU 执行到证据修复与最终动作。" : "Watch the complete 3:59 workflow—from AMD GPU execution to evidence repair and final action."}</h2>
        </div>
        <div className="reel-player">
          <video
            controls
            playsInline
            preload="metadata"
            poster="/og-contract-progress.png"
            aria-label={zh ? "Look Twice 3 分 59 秒完整英文演示" : "Look Twice complete 3 minute 59 second English demo"}
          >
            <source src="/media/Look-Twice-V8-Demo.mp4" type="video/mp4" />
          </video>
          <div>
            <b>{zh ? "录制的 3:59 AMD GPU 工作流" : "RECORDED 3:59 AMD GPU WORKFLOW"}</b>
            <p>{zh ? "1920×1080 · 30 FPS · 英文旁白与字幕 · 仅限仿真。视频展示命令行审计、Genesis/ROCm 执行、主动修证、双重准入和结果边界；它不是真机录像。" : "1920×1080 · 30 FPS · English narration and captions · Simulation only. The video shows command-line audit, Genesis/ROCm execution, active evidence repair, dual admission and result boundaries; it is not physical-robot footage."}</p>
            <a href="/media/Look-Twice-V8-Demo.mp4" target="_blank" rel="noreferrer">{zh ? "在浏览器中打开完整视频 ▶" : "OPEN THE FULL VIDEO IN BROWSER ▶"}</a>
            <a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4">{zh ? "下载哈希校验版 MP4 ↓" : "DOWNLOAD THE HASH-VERIFIED MP4 ↓"}</a>
            <a href="/media/look-twice-replay-30s.mp4" target="_blank" rel="noreferrer">{zh ? "观看 30 秒无旁白证据回放 ↗" : "WATCH THE 30-SECOND SILENT EVIDENCE REPLAY ↗"}</a>
            <a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt">{zh ? "下载冻结模型（SHA 固定）↗" : "DOWNLOAD THE SHA-PINNED CHECKPOINT ↗"}</a>
          </div>
        </div>
      </section>

      <section className="section cta-band">
        <div><span>{zh ? "预注册挑战已验证 · 原锁定测试仍保留" : "PREREGISTERED CHALLENGE VERIFIED · ORIGINAL LOCKED TEST PRESERVED"}</span><h2>{zh ? "先审计 30-world 主结果，再看单回合闭环如何产生回执。" : "Audit the 30-world result, then inspect how one replay produces its receipts."}</h2></div>
        <Link href={href("/results")} className="button primary">{zh ? "审计挑战" : "Audit the challenge"}<span>→</span></Link>
      </section>
    </main>
  );
}
