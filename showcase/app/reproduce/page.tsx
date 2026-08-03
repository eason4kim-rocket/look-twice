"use client";
import { SiteShell, useLanguage } from "../components/SiteShell";
import "./reproduce.css";

export default function ReproducePage() {
  return <SiteShell><Reproduce /></SiteShell>;
}

function Reproduce() {
  const { language } = useLanguage();
  const zh = language === "zh";
  return (
    <main>
      <header className="page-header">
        <div>
          <span className="eyebrow">{zh ? "回放优先的复现方式" : "REPLAY-FIRST REPRODUCTION"}</span>
          <h1>{zh ? "无需 GPU，也能审计闭环。" : "Audit the loop without a GPU."}</h1>
        </div>
        <p>{zh ? "公开网站只回放已记录的 AMD GPU 证据。Docker 不依赖 Genesis、ROCm、私有 Purify 或在线云实例。" : "The public site replays recorded AMD GPU evidence. Docker needs no Genesis, ROCm, private Purify code or live cloud instance."}</p>
      </header>
      <section className="repro-grid">
        <article>
          <span>{zh ? "01 / 启动" : "01 / START"}</span>
          <h2>{zh ? "一条命令" : "One command"}</h2>
          <pre><code>docker compose up --build</code></pre>
          <p>{zh ? "打开 http://localhost:3000。证据回放可在纯 CPU 环境完整运行。" : "Open http://localhost:3000. Evidence replay runs in a CPU-only environment."}</p>
        </article>
        <article>
          <span>{zh ? "02 / 校验" : "02 / VERIFY"}</span>
          <h2>{zh ? "冻结 SHA 守卫" : "Frozen SHA guard"}</h2>
          <pre><code>python3 scripts/verify_frozen_foundation.py</code></pre>
          <p>{zh ? "检查 V8 运行时、两份校准产物、Purify 二进制、回合数据与公共证据包。" : "Checks frozen runtime, both calibration artifacts, Purify binary, episodes and public bundles."}</p>
        </article>
        <article>
          <span>{zh ? "03 / 审计" : "03 / INSPECT"}</span>
          <h2>{zh ? "原始证据" : "Raw evidence"}</h2>
          <pre><code>showcase/public/data/replays/*.json</code></pre>
          <p>{zh ? "每个结论均可追溯到证据声明（Claim）、采集根、门控回执（GateReceipt）和源回合 SHA。" : "Every claim links to capture roots, GateReceipts and the source episode SHA."}</p>
        </article>
      </section>
      <section className="boundary">
        <span>{zh ? "诚实边界" : "BOUNDARY"}</span>
        <h2>{zh ? "比赛参考实现，不是安全认证。" : "Contest reference implementation, not a safety certification."}</h2>
        <div>
          <p>✓ {zh ? "录制的 Genesis + AMD GPU 证据" : "Recorded Genesis + AMD GPU evidence"}</p>
          <p>✓ {zh ? "冻结模型与 Conformal 身份" : "Frozen model and conformal identities"}</p>
          <p>✓ {zh ? "Purify Go 授权回执" : "Purify Go authorization receipts"}</p>
          <p>× {zh ? "不声称真实机器人验证" : "No real-robot claim"}</p>
          <p>× {zh ? "网站不依赖在线 GPU" : "No live GPU website dependency"}</p>
          <p>× {zh ? "不包含完整私有 Purify 产品" : "No complete private Purify product"}</p>
        </div>
      </section>
      <section className="boundary">
        <span>{zh ? "冻结模型" : "FROZEN CHECKPOINT"}</span>
        <h2>{zh ? "公开下载后先校验 256 位哈希。" : "Download publicly, then verify the SHA256 before inference."}</h2>
        <div>
          <p><a href="https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt">{zh ? "下载 159,592,901 字节 checkpoint ↗" : "Download the 159,592,901-byte checkpoint ↗"}</a></p>
          <p><code>7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783</code></p>
          <p><a href="https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release">{zh ? "完整复现说明与环境检查 ↗" : "Full reproduction guide and environment check ↗"}</a></p>
        </div>
      </section>
    </main>
  );
}
