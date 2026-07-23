"use client";

import Link from "next/link";
import { SiteShell, useLanguage } from "./components/SiteShell";

const flow = [
  ["01", "Observe", "RGB-D claims arrive with time, scope, calibration and capture lineage.", "观察", "RGB-D Claim 携带时间、范围、校准与采集谱系。"],
  ["02", "Qualify", "Purify checks independence, prediction sets and the action contract.", "准入", "Purify 检查独立性、预测集与动作合同。"],
  ["03", "Repair", "When evidence is insufficient, the robot moves to the best diagnostic viewpoint.", "修证", "证据不足时，机器人移动到最有诊断价值的观察点。"],
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
  return (
    <main>
      <section className="hero section-grid">
        <div className="hero-copy">
          <div className="eyebrow"><span className="live-dot" /> AMD GPU · PHYSICAL AI · EVIDENCE ASSURANCE</div>
          <h1>{zh ? <>行动之前，<em>再看一次。</em></> : <>Before a robot acts,<br/><em>look twice.</em></>}</h1>
          <p className="hero-lead">{zh
            ? "Look Twice 将不稳定、冲突且同源的机器人观察，转化为可供物理动作依赖的可信事实；证据不足时，它主动修复证据。"
            : "Look Twice turns noisy, conflicting and correlated robot observations into action-qualified facts—and actively repairs evidence when confidence is not enough."}</p>
          <div className="hero-actions">
            <Link className="button primary" href="/console">{zh ? "打开证据控制台" : "Open Evidence Console"}<span>↗</span></Link>
            <Link className="button ghost" href="/results">{zh ? "查看冻结结果" : "Inspect frozen results"}</Link>
          </div>
          <div className="truth-strip">
            <span>RECORDED AMD GPU EVIDENCE</span><span>SIMULATION ONLY</span><span>NO LIVE GPU REQUIRED</span>
          </div>
        </div>
        <div className="hero-system" aria-label="Look Twice system status">
          <div className="system-head"><span>WAREHOUSE AMR / ZONE C-04</span><b>ASSURANCE ONLINE</b></div>
          <div className="warehouse-map">
            <div className="rack rack-a">RACK A</div><div className="rack rack-b">RACK B</div>
            <div className="corridor corridor-a"><span>CORRIDOR A</span></div>
            <div className="corridor corridor-b"><span>CORRIDOR B</span><i /></div>
            <div className="robot-marker"><b>LT</b><span>AMR-07</span></div>
            <div className="scan-cone" />
          </div>
          <div className="contract-mini">
            <div><span>ACTION</span><b>CROSS REGION</b></div>
            <div><span>INITIAL GATE</span><b className="denied">DENIED</b></div>
            <div><span>NEXT ACTION</span><b className="cyan">ACQUIRE NEW ROOT</b></div>
          </div>
        </div>
      </section>

      <section className="section block-section">
        <div className="section-heading"><span>01 / THE GAP</span><h2>{zh ? "感知不是事实。数量也不是独立证据。" : "A perception is not a fact. More claims are not always more evidence."}</h2></div>
        <div className="problem-grid">
          <article><b>06</b><span>{zh ? "输入 Claim" : "incoming claims"}</span><p>{zh ? "看起来证据很多" : "Evidence appears abundant"}</p></article>
          <article className="warning"><b>01</b><span>{zh ? "物理采集根" : "physical capture root"}</span><p>{zh ? "同源复制不会增加确定性" : "Echoes add no independence"}</p></article>
          <article className="resolution"><b>DENY</b><span>ACTION CONTRACT</span><p>{zh ? "先修证据，再授权动作" : "Repair evidence before action"}</p></article>
        </div>
      </section>

      <section className="section flow-section">
        <div className="section-heading"><span>02 / CLOSED LOOP</span><h2>{zh ? "从观察到授权的完整闭环" : "One accountable loop from observation to action"}</h2></div>
        <div className="flow-grid">{flow.map((item) => <article key={item[0]}><span>{item[0]}</span><h3>{zh ? item[3] : item[1]}</h3><p>{zh ? item[4] : item[2]}</p></article>)}</div>
      </section>

      <section className="section reel-section">
        <div className="section-heading">
          <span>03 / 30-SECOND REEL</span>
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
            <p>{zh ? "1920×1080 · 30 FPS · 无旁白 · Simulation only。全部状态来自同一 EpisodeBundle。" : "1920×1080 · 30 FPS · no narration · Simulation only. Every state comes from the same EpisodeBundle."}</p>
            <a href="/media/look-twice-replay-30s.mp4" download>{zh ? "下载 MP4 ↓" : "DOWNLOAD MP4 ↓"}</a>
          </div>
        </div>
      </section>

      <section className="section cta-band">
        <div><span>RECORDED CONFIRMATORY EPISODE</span><h2>{zh ? "看见每一条 Claim 如何改变机器人的行动资格。" : "See exactly how each claim changes what the robot is allowed to do."}</h2></div>
        <Link href="/console" className="button primary">{zh ? "播放闭环" : "Play the evidence loop"}<span>→</span></Link>
      </section>
    </main>
  );
}
