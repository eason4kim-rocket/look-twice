"use client";

import Link from "next/link";
import { SiteShell, useLanguage } from "./components/SiteShell";
import { challengeEvidence } from "./lib/challengeEvidence";
import { contractProgressEvidence } from "./lib/contractProgressEvidence";

const flow = [
  ["01", "Observe", "RGB-D Claims arrive with time, scope, calibration, and capture lineage.", "观察", "RGB-D 证据声明（Claim）携带时间、范围、校准与采集谱系。"],
  ["02", "Qualify", "The system checks physical roots, prediction sets, and the Action Contract.", "准入", "系统检查物理证据根、预测集与动作合同。"],
  ["03", "Repair", "A BeliefGap tells the scout which failed clause the next viewpoint should target.", "补证", "BeliefGap 告诉侦察车下一视角应针对哪条失败条款。"],
  ["04", "Act", "Direct motion opens only when the Python policy and Purify Go both agree.", "行动", "只有 Python 策略与 Purify Go 同时同意，才会开放直接通行。"],
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
            ? "仓储机器人不该把同一帧相机画面复制出的六条结论，当成六次独立观察。Look Twice 先判断证据是否足以支持下一步动作；证据不够时，让侦察车换一个视角再看。"
            : "A warehouse robot should not treat six claims copied from one camera frame as six independent observations. Look Twice checks the evidence for the next action—and asks the scout for a new view before the carrier moves."}</p>

          <div className="hero-actions">
            <a className="button primary" href="#full-demo">{zh ? "观看 3:59 完整演示" : "Watch the 3:59 demo"}<span>▶</span></a>
            <Link className="button ghost" href={href("/console")}>{zh ? "打开证据控制台" : "Open Evidence Console"}<span>↗</span></Link>
          </div>

          <div className="challenge-proof" aria-label={zh ? "预注册主结果" : "Preregistered primary result"}>
            <div className="challenge-proof-head">
              <span>{zh ? "预注册主结果 · 30 个成对世界" : "PREREGISTERED PRIMARY · 30 PAIRED WORLDS"}</span>
              <b>{zh ? "主动 29/30 · 被动 0/30" : "ACTIVE 29/30 · PASSIVE 0/30"}</b>
            </div>
            <div className="challenge-proof-grid">
              <div><strong>29<small>/30</small></strong><span>{zh ? "主动策略全链直行" : "active full-chain direct"}</span></div>
              <div><strong>0<small>/30</small></strong><span>{zh ? "被动策略全链直行" : "passive full-chain direct"}</span></div>
              <div><strong>60<small>/60</small></strong><span>{zh ? "任务完成 · 0 unsafe · 0 fallback" : "missions · 0 unsafe · 0 fallback"}</span></div>
            </div>
            <p className="challenge-proof-note">{zh
              ? "事后可行性核查：29 个存在畅通走廊的世界全部直行；唯一双廊阻塞世界安全绕行。离线标签从未提供给控制器，也不是预注册端点。"
              : "Secondary post-hoc feasibility check: all 29 worlds with a feasible corridor went direct; the only dual-blocked world took the safe detour. Offline labels were never available to the controller, and this was not the preregistered endpoint."}</p>
            <div className="challenge-proof-links">
              <Link href={href("/results")}>{zh ? "查看完整结果 →" : "SEE THE FULL RESULT →"}</Link>
              <a href={challengeEvidence.judgeCardUrl} target="_blank" rel="noreferrer">{zh ? "简明证据卡 ↗" : "COMPACT EVIDENCE CARD ↗"}</a>
              <a href={challengeEvidence.rawArchiveUrl}>{zh ? "原始归档 ↗" : "RAW ARCHIVE ↗"}</a>
              <a href={challengeEvidence.verificationUrl}>{zh ? "验证器输出 ↗" : "VERIFIER OUTPUT ↗"}</a>
            </div>
          </div>

          <div className="truth-strip">
            <span>{zh ? "AMD 全流程遥测" : "AMD FULL-RUN TELEMETRY"}</span>
            <span>{zh ? "仓储 AMR 仿真" : "WAREHOUSE AMR SIMULATION"}</span>
            <span>{zh ? "Python ∧ Purify Go" : "PYTHON ∧ PURIFY GO"}</span>
            <span>{zh ? "Liu Liang · Track 3" : "LIU LIANG · TRACK 3"}</span>
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
        <div className="section-heading"><span>{zh ? "01 / 问题" : "01 / THE PROBLEM"}</span><h2>{zh ? "结论多，不等于证据独立。" : "More conclusions do not mean more independent evidence."}</h2></div>
        <div className="problem-grid">
          <article><b>06</b><span>{zh ? "输入证据声明" : "incoming claims"}</span><p>{zh ? "软件层面看起来证据很多" : "The software sees plenty of messages"}</p></article>
          <article className="warning"><b>01</b><span>{zh ? "物理采集根" : "physical capture root"}</span><p>{zh ? "同源复制不会增加确定性" : "Copies add no independent support"}</p></article>
          <article className="resolution"><b>{zh ? "拒绝" : "DENY"}</b><span>{zh ? "当前动作合同" : "CURRENT ACTION CONTRACT"}</span><p>{zh ? "先补齐缺失证据，再决定是否行动" : "Collect what is missing, then decide"}</p></article>
        </div>
      </section>

      <section className="section flow-section">
        <div className="section-heading"><span>{zh ? "02 / 方法" : "02 / THE LOOP"}</span><h2>{zh ? "拒绝不是终点，而是下一次观察的起点。" : "A denial becomes the starting point for the next observation."}</h2></div>
        <div className="flow-grid">{flow.map((item) => <article key={item[0]}><span>{item[0]}</span><h3>{zh ? item[3] : item[1]}</h3><p>{zh ? item[4] : item[2]}</p></article>)}</div>
      </section>

      <section className="section policy-section">
        <div className="section-heading">
          <span>{zh ? "03 / 创新" : "03 / WHY IT IS DIFFERENT"}</span>
          <h2>{zh ? "模型负责看，动作合同负责决定现在能不能动。" : "The model interprets the scene. The Action Contract decides whether the robot may move."}</h2>
        </div>

        <div className="platform-row innovation-grid">
          <div><span>{zh ? "物理证据根" : "PHYSICAL ROOTS"}</span><p>{zh ? "RGB、深度和转发 Claim 如果来自同一次采集，只算一个物理观察。" : "RGB, depth, and forwarded Claims from one capture count as one physical observation."}</p></div>
          <div><span>{zh ? "动作合同" : "ACTION CONTRACT"}</span><p>{zh ? "证据必须匹配具体机器人、载荷、走廊、动作、时间窗、校准与独立根要求。" : "Evidence must match the robot, payload, corridor, action, time window, calibration, and root requirement."}</p></div>
          <div><span>BELIEF GAP</span><p>{zh ? "拒绝会给出缺失内容；固定、可审计的排序据此选择针对缺口的新视角，而不是重复同一画面。" : "A denial names what is missing. A fixed, auditable ranking selects a new view that targets the gap instead of repeating the same one."}</p></div>
          <div><span>PURIFY GO</span><p>{zh ? "Purify 不是另一个模型，而是独立编译的 Go 合同门。Python 与 Go 必须同时准入，直接通行才会开放。" : "Purify is not another model. It is a separately compiled Go contract gate; direct motion requires Python and Go to agree."}</p></div>
        </div>

        <div className="policy-comparison">
          <article>
            <span>{zh ? "被动策略" : "PASSIVE"}</span>
            <h3>{zh ? "拒绝并绕行" : "Deny and detour"}</h3>
            <p>{zh ? "证据不足时保持安全，但每个世界都为不确定性付出更长路线。" : "It stays safe when evidence is weak, but pays for uncertainty with a longer route in every world."}</p>
            <b>{zh ? "预注册挑战：0/30 全链直行" : "PREREGISTERED CHALLENGE: 0/30 FULL-CHAIN DIRECT"}</b>
          </article>
          <article className="active-policy">
            <span>{zh ? "主动策略" : "ACTIVE"}</span>
            <h3>{zh ? "换视角、补证、再行动" : "Move, repair, then act"}</h3>
            <p>{zh ? "侦察车获取独立侧视证据；只有 Python 与 Purify Go 同时准入后，载荷车才直接通行。" : "The scout acquires an independent side view. The loaded carrier goes direct only after Python and Purify Go both admit the action."}</p>
            <b>{zh ? "29/29 可直达世界直行 · 1/1 双阻塞绕行" : "29/29 FEASIBLE WORLDS DIRECT · 1/1 DUAL-BLOCKED DETOUR"}</b>
          </article>
        </div>

        <div className="challenge-proof secondary-proof" aria-label={zh ? "主动视角选择效率补充" : "Active-view selector efficiency supplement"}>
          <div className="challenge-proof-head">
            <span>{zh ? "主动视角选择补充 · 20 个成对世界" : "ACTIVE-VIEW SELECTOR SUPPLEMENT · 20 PAIRED WORLDS"}</span>
            <b>{zh ? "直行结果保持 20/20" : "DIRECT OUTCOME HELD AT 20/20"}</b>
          </div>
          <div className="challenge-proof-grid">
            <div><strong>−40.3<small>%</small></strong><span>{zh ? "Scout 平均路径" : "mean scout path"}</span></div>
            <div><strong>−15.0<small>%</small></strong><span>{zh ? "团队平均路径" : "mean team path"}</span></div>
            <div><strong>−27.5<small>%</small></strong><span>{zh ? "平均物理采集数" : "mean physical captures"}</span></div>
          </div>
          <p className="challenge-proof-note">{zh
            ? "候选选择器与基线都在 20/20 个世界完成直行；候选用更短的侦察路线和更少的物理采集获得相同动作结果。这个补充是同生成器、非锁定的运动学仿真，不是真机结果，也不替代上方预注册主结果。"
            : "Candidate and baseline both finished direct in 20/20 worlds; the candidate reached the same action outcome with a shorter scout route and fewer physical captures. This is a separate same-generator, non-locked kinematic simulation—not a physical-robot result or a replacement for the primary result above."}</p>
          <div className="challenge-proof-links">
            <Link href={`${href("/results")}#contract-progress-efficiency`}>{zh ? "查看效率证据 →" : "INSPECT THE EFFICIENCY EVIDENCE →"}</Link>
            <a href={contractProgressEvidence.reportUrl} target="_blank">{zh ? "报告 JSON ↗" : "REPORT JSON ↗"}</a>
            <a href={contractProgressEvidence.verificationUrl} target="_blank">{zh ? "验证 JSON ↗" : "VERIFICATION JSON ↗"}</a>
            <a href={contractProgressEvidence.rocmTelemetryUrl} target="_blank">{zh ? "ROCm 遥测 ↗" : "ROCM TELEMETRY ↗"}</a>
          </div>
        </div>
      </section>

      <section id="full-demo" className="section reel-section">
        <div className="section-heading">
          <span>{zh ? "04 / 完整演示" : "04 / COMPLETE DEMO"}</span>
          <h2>{zh ? "直接在网页中观看：AMD GPU 执行、主动补证、双重准入与最终动作。" : "Watch the complete workflow in place: AMD GPU execution, active evidence repair, dual admission, and the final action."}</h2>
        </div>
        <div className="reel-player">
          <video controls playsInline preload="metadata" poster="/og-contract-progress.png" aria-label={zh ? "Look Twice 3 分 59 秒完整英文演示" : "Look Twice complete 3 minute 59 second English demo"}>
            <source src="/media/Look-Twice-V8-Demo.mp4" type="video/mp4" />
          </video>
          <div>
            <b>{zh ? "录制的 3:59 AMD GPU 工作流" : "RECORDED 3:59 AMD GPU WORKFLOW"}</b>
            <p>{zh ? "1920×1080 · 30 FPS · 英文旁白与字幕 · 仅限仿真。视频展示命令行审计、Genesis/ROCm 执行、主动补证、双重准入和结果边界；它不是真机录像。" : "1920×1080 · 30 FPS · English narration and captions · Simulation only. The video shows the command-line audit, Genesis/ROCm execution, active evidence repair, dual admission, and result boundaries; it is not physical-robot footage."}</p>
            <a href="/media/Look-Twice-V8-Demo.mp4" target="_blank" rel="noreferrer">{zh ? "在新标签页打开视频 ▶" : "OPEN VIDEO IN A NEW TAB ▶"}</a>
            <a href="https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/showcase/public/media/Look-Twice-V8-Demo.mp4" target="_blank" rel="noreferrer">{zh ? "查看仓库内的视频文件 ↗" : "VIEW THE VIDEO FILE IN THE REPOSITORY ↗"}</a>
            <a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4">{zh ? "下载哈希校验版 MP4 ↓" : "DOWNLOAD THE HASH-VERIFIED MP4 ↓"}</a>
            <a href="/media/look-twice-replay-30s.mp4" target="_blank" rel="noreferrer">{zh ? "观看 30 秒无旁白回放 ↗" : "WATCH THE 30-SECOND SILENT REPLAY ↗"}</a>
          </div>
        </div>
      </section>

      <section className="section cta-band">
        <div><span>{zh ? "完整网站源码与数据均在 GitHub" : "FULL WEBSITE SOURCE AND DATA ARE ON GITHUB"}</span><h2>{zh ? "进入证据控制台，亲自回放主动与被动策略的每一步。" : "Open the Evidence Console and replay every step of the active and passive policies."}</h2></div>
        <div className="cta-actions">
          <Link href={href("/console")} className="button primary">{zh ? "打开控制台" : "Open the console"}<span>→</span></Link>
          <a href="https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv/showcase" className="button ghost" target="_blank" rel="noreferrer">{zh ? "查看网站源码" : "View website source"}<span>↗</span></a>
        </div>
      </section>
    </main>
  );
}
