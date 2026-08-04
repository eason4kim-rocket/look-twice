"use client";
import { SiteShell, useLanguage } from "../components/SiteShell";
import { challengeEvidence } from "../lib/challengeEvidence";
import { decisionDynamicsEvidence } from "../lib/decisionDynamicsEvidence";
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
          <span className="eyebrow">{zh ? "挑战优先的复现方式" : "CHALLENGE-FIRST REPRODUCTION"}</span>
          <h1>{zh ? "无需 GPU，也能验证预注册结果。" : "Verify the preregistered result without a GPU."}</h1>
        </div>
        <p>{zh ? "先验证 30-world 原始归档，再回放独立的非锁定 seed 105400 confirmatory 回合。原 12-pair locked test 作为单独聚合证据保留。验证器和网站都不需要 Genesis、ROCm、私有 Purify 或在线云实例。" : "Verify the 30-world raw archive first, then replay the separate non-locked seed 105400 confirmatory episodes. The original 12-pair locked test remains preserved as separate aggregate evidence. Neither the validator nor the site needs Genesis, ROCm, private Purify code or a live cloud instance."}</p>
      </header>
      <section className="challenge-repro">
        <div>
          <span>{zh ? "预注册挑战 · CLEAN-CLONE 验证" : "PREREGISTERED CHALLENGE · CLEAN-CLONE VERIFICATION"}</span>
          <h2>{zh ? "195 个文件，194/194 由内部 SHA256SUMS 绑定。" : "195 files; internal SHA256SUMS binds 194/194 others."}</h2>
          <p>{zh ? "验证输出必须写在解压目录之外。预期本地验证 SHA 与发布的独立验证回执完全一致。" : "Write validator output outside the extracted results directory. The expected local-verification SHA exactly matches the published independent receipt."}</p>
          <div className="challenge-repro-links">
            <a href={challengeEvidence.judgeCardUrl} target="_blank" rel="noreferrer">{zh ? "评委卡 ↗" : "JUDGE CARD ↗"}</a>
            <a href={challengeEvidence.rawArchiveUrl}>{zh ? "原始归档 ↗" : "RAW ARCHIVE ↗"}</a>
            <a href={challengeEvidence.verificationUrl}>{zh ? "发布验证回执 ↗" : "PUBLISHED VERIFICATION ↗"}</a>
          </div>
        </div>
        <div>
          <pre><code>{`git clone --branch v8-competition-release \\
  https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
curl -LO ${challengeEvidence.rawArchiveUrl}
shasum -a 256 v8-frozen-challenge-102500-102529.raw.tar.gz
tar -xzf v8-frozen-challenge-102500-102529.raw.tar.gz
python3 scripts/verify_v8_frozen_challenge.py \\
  --results-dir v8-frozen-challenge-102500-102529 \\
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \\
  --repo-root . \\
  --output v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
shasum -a 256 v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json`}</code></pre>
          <p><b>RAW</b><code>{challengeEvidence.rawArchiveSha256}</code></p>
          <p><b>VERIFICATION</b><code>{challengeEvidence.verificationSha256}</code></p>
        </div>
      </section>
      <section className="challenge-repro">
        <div>
          <span>{zh ? "动力学 V2 · 无需 GPU 的完整复核" : "DYNAMICS V2 · COMPLETE GPU-FREE AUDIT"}</span>
          <h2>{zh ? "30 个原子 checkpoint，30/30 报告，双层校验索引。" : "30 atomic checkpoints, one 30/30 report, and two checksum layers."}</h2>
          <p>{zh ? "先检查 formal 核心文件，再检查包含尝试账本、进度、日志与事后证明范围审计的完整外层包；最后由冻结 verifier 重算每个 trial 和聚合门槛。" : "Check the formal core first, then the complete outer package containing the attempt ledger, progress, logs and post-run proof-scope review. The frozen verifier then recomputes every trial and aggregate threshold."}</p>
          <div className="challenge-repro-links">
            <a href={decisionDynamicsEvidence.reportUrl} target="_blank">{zh ? "30/30 报告 ↗" : "30/30 REPORT ↗"}</a>
            <a href={decisionDynamicsEvidence.provenanceReviewUrl} target="_blank">{zh ? "证明范围审计 ↗" : "PROVENANCE REVIEW ↗"}</a>
            <a href={decisionDynamicsEvidence.packageChecksumsUrl} target="_blank">{zh ? "完整包校验 ↗" : "PACKAGE CHECKSUMS ↗"}</a>
          </div>
        </div>
        <div>
          <pre><code>{`DYN=release/v8-derived/decision_dynamics_recovery_v2_102500_102529
(cd "$DYN" && shasum -a 256 -c SHA256SUMS)
(cd "$DYN" && shasum -a 256 -c PACKAGE_SHA256SUMS)
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \\
  "$DYN/REPORT.json"`}</code></pre>
          <p><b>REPORT</b><code>{decisionDynamicsEvidence.reportSha256}</code></p>
          <p><b>PACKAGE INDEX</b><code>{decisionDynamicsEvidence.packageChecksumsSha256}</code></p>
        </div>
      </section>
      <section className="repro-grid">
        <article>
          <span>{zh ? "01 / 回放站点" : "01 / REPLAY SITE"}</span>
          <h2>{zh ? "一条命令" : "One command"}</h2>
          <pre><code>docker compose up --build</code></pre>
          <p>{zh ? "打开 http://localhost:3000。证据回放可在纯 CPU 环境完整运行。" : "Open http://localhost:3000. Evidence replay runs in a CPU-only environment."}</p>
        </article>
        <article>
          <span>{zh ? "02 / 冻结基础" : "02 / FROZEN FOUNDATION"}</span>
          <h2>{zh ? "冻结 SHA 守卫" : "Frozen SHA guard"}</h2>
          <pre><code>python3 scripts/verify_frozen_foundation.py</code></pre>
          <p>{zh ? "检查 V8 运行时、两份校准产物、Purify 二进制、回合数据与公共证据包。" : "Checks frozen runtime, both calibration artifacts, Purify binary, episodes and public bundles."}</p>
        </article>
        <article>
          <span>{zh ? "03 / 非锁定确认回放" : "03 / NON-LOCKED CONFIRMATORY REPLAY"}</span>
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
