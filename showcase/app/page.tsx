"use client";

import Link from "next/link";
import { SiteShell, useLanguage } from "./components/SiteShell";

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
          <div className="hero-actions">
            <Link className="button primary" href={href("/console")}>{zh ? "打开证据控制台" : "Open Evidence Console"}<span>↗</span></Link>
            <Link className="button ghost" href={href("/results")}>{zh ? "查看冻结结果" : "Inspect frozen results"}</Link>
          </div>
          <div className="truth-strip">
            <span>{zh ? "录制的 AMD GPU 证据" : "RECORDED AMD GPU EVIDENCE"}</span>
            <span>{zh ? "仅限仿真" : "SIMULATION ONLY"}</span>
            <span>{zh ? "无需在线 GPU" : "NO LIVE GPU REQUIRED"}</span>
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
            <b>{zh ? "拒绝 → 安全绕行" : "DENY → SAFE DETOUR"}</b>
          </article>
          <article className="active-policy">
            <span>{zh ? "主动策略" : "ACTIVE"}</span>
            <h3>{zh ? "换视角、修证据、再行动" : "Move, repair, then act"}</h3>
            <p>{zh ? "侦察车 Scout 获取独立侧视根；Python 与 Purify 同时准入后，载具 Carrier 才直接通行。" : "A scout acquires an independent side-view root. Only Python ∧ Purify admission unlocks the carrier."}</p>
            <b>{zh ? "拒绝 → 修证 → 直行" : "DENY → REPAIR → DIRECT"}</b>
          </article>
        </div>
        <div className="platform-row">
          <div><span>AMD GPU</span><p>{zh ? "加速 Genesis RGB-D、空间视觉推理与实验矩阵。" : "Accelerates Genesis RGB-D, spatial vision inference and experiment matrices."}</p></div>
          <div><span>PURIFY</span><p>{zh ? "检查校准、谱系、独立根与动作合同，并签发门控回执（GateReceipt）。" : "Checks calibration, lineage, independent roots and the action contract, then signs the GateReceipt."}</p></div>
          <div><span>{zh ? "诚实边界" : "BOUNDARY"}</span><p>{zh ? "录制的仿真证据；不声称真实机器人或安全认证。" : "Recorded simulation evidence; no real-robot or safety-certification claim."}</p></div>
        </div>
      </section>

      <section className="section reel-section">
        <div className="section-heading">
          <span>{zh ? "04 / 30 秒演示" : "04 / 30-SECOND REEL"}</span>
          <h2>{zh ? "不需要解释：看机器人为什么停、如何修证、何时获准行动。" : "No explanation required: see why the robot stops, repairs evidence, and earns permission to act."}</h2>
        </div>
        <div className="reel-player">
          <video
            controls
            playsInline
            preload="metadata"
            poster="/media/look-twice-replay-30s.poster.webp"
          >
            <source src="/media/look-twice-replay-30s.mp4" type="video/mp4" />
          </video>
          <div>
            <b>{zh ? "录制的 AMD GPU 证据回放" : "RECORDED AMD GPU EVIDENCE REPLAY"}</b>
            <p>{zh ? "1920×1080 · 30 FPS · 无旁白 · 英文画面字幕（比赛默认）· 仅限仿真。全部状态来自同一回合证据包。" : "1920×1080 · 30 FPS · no narration · Simulation only. Every state comes from the same EpisodeBundle."}</p>
            <a href="/media/look-twice-replay-30s.mp4" download>{zh ? "下载 MP4 ↓" : "DOWNLOAD MP4 ↓"}</a>
          </div>
        </div>
      </section>

      <section className="section cta-band">
        <div><span>{zh ? "仅评测一次 · 含完整回执" : "LOCKED ONCE · RECEIPTS INCLUDED"}</span><h2>{zh ? "看见每一条证据声明如何改变机器人的行动资格。" : "See exactly how each claim changes what the robot is allowed to do."}</h2></div>
        <Link href={href("/console")} className="button primary">{zh ? "播放闭环" : "Play the evidence loop"}<span>→</span></Link>
      </section>
    </main>
  );
}
