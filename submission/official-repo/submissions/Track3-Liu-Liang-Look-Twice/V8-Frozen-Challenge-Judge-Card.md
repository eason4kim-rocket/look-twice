# V8 Frozen Challenge — Judge Card

**Entrant / team:** Liu Liang (solo) · GitHub `@eason4kim-rocket` · Track 3
Physical AI

**Status:** independently verified `PASS` · 30 paired worlds · 60/60 valid
episodes · no retry, replacement seed, early stop, model change, calibration
change, or threshold change.

This is an additive, preregistered **same-generator non-locked supplement** to
the permanent 12-pair V8 locked result. It is not an OOD, rigid-body, or
physical-robot claim.

## Five judge checks

| Check | Result | Machine evidence |
|---|---|---|
| Public before execution | [Commit A](https://github.com/eason4kim-rocket/look-twice/commit/9e14cbb999824d35a21749f4ff420ab63f81847d) published `2026-08-03 10:01:53Z`; [Commit B](https://github.com/eason4kim-rocket/look-twice/commit/3a52ba548de26858a7fdcad1c1ce7237b709fe69) published `2026-08-03 10:02:22Z`. B changed only the A-hash field. Preregistration SHA-256: `90679e84f835c6e46983c1b219c1196506164e3c82dd1dfffec33469a73e28a2`. | [Protocol](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_PROTOCOL.md) · [preregistration JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json) · [packaged run manifest](evidence/challenge_102500_102529/RUN_MANIFEST.json) |
| Capability | Active full-chain direct: **29/30 = 96.7%**, Wilson 95% CI **83.3–99.4%**. Passive: **0/30**, CI **0–11.4%**. Paired gain: **+96.7 percentage points**; exact two-sided McNemar **p = 3.73×10⁻⁹**. “Full-chain” requires mission success, direct/no-detour, and a Python+Go+effective joint admit for the corridor actually executed. | [packaged challenge report](evidence/challenge_102500_102529/CHALLENGE_REPORT.json) |
| Mission and safety | **60/60 mission success**, **0/60 unsafe**, **0/60 fallback**. The sole active non-direct case, seed `102515`, remained safe and completed by detour. All 18/268 Python/Go receipt disagreements were Python-admit/Go-deny with `effective_admit=false`; no disagreement opened the gate. In every disagreement, Go independently found only one qualifying root and the inconclusive set `{clear, blocked}`. | [packaged verification report](evidence/challenge_102500_102529/VERIFICATION.json) · [raw archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz) |
| AMD full-pipeline execution | **60/60** episodes used Genesis live RGB-D, the frozen checkpoint, and Purify Go receipts: 268 RGB-D observations, 134 vision proposals, and 268 Go invocations/receipts. Full subprocess-wall telemetry retained **844** two-second ROCm samples across **1,685.5 s**, including idle: GPU mean/median/p95/max **19.4/0/95/100%**; VRAM p95/max **2/2%**; package power mean/p95/max **35.7/81/109 W**. | [packaged ROCm telemetry](evidence/challenge_102500_102529/ROCM_TELEMETRY.json) |
| Warehouse operational trade | Active scouting reduced loaded-carrier logical path from **6.404 to 4.961** (`−1.443`, **−22.5%**) while adding **2.980** scout path; total logical-role team path rose from **6.404 to 7.941** (`+1.538`, **+24.0%**). This is kinematic path burden, not energy, throughput, latency, or physical duty cycle. | [packaged per-seed and burden tables](evidence/challenge_102500_102529/CHALLENGE_REPORT.json) |

## Scope that must travel with the result

- Genesis 1.1.2 kinematic simulation on AMD ROCm, not contact validation.
- Carrier and scout are separate logical-role poses, viewpoints, and capture
  roots on **one shared Genesis chassis**; they are not two physical devices or
  simultaneous dual-body dynamics.
- Seeds `102500–102529` are a previously untouched reserved subset from the
  same generator family. The result is not called OOD or population-level
  generalization.
- Receipt-level Python/Go agreement is **250/268 = 93.3%**. The Go side vetoed
  every disagreement, and the effective authorization remained fail-closed.
  A post-hoc descriptive audit (not a preregistered endpoint) found that all 18
  shared one signature: active policy, corridor B, a single Go-qualified root,
  and the inconclusive Go set `{clear, blocked}`. Four were on a non-selected
  corridor; 14 were transient evaluations before the final selected-corridor
  joint admit. This audit changed no runtime, calibration, or threshold.

## Clean-clone verification

The raw archive contains 195 files. Its internal `SHA256SUMS` binds every other
regular file (194/194). Validator output must remain outside the extracted
results directory.

```bash
git clone --branch v8-competition-release \
  https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
curl -LO https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz
tar -xzf v8-frozen-challenge-102500-102529.raw.tar.gz
python3 scripts/verify_v8_frozen_challenge.py \
  --results-dir v8-frozen-challenge-102500-102529 \
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \
  --repo-root . \
  --output v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
sha256sum v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
```

Expected verification SHA-256:
`942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940`.

Raw archive SHA-256:
`171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2`.

The complete machine result is also available as a stable
[release verification asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json).
