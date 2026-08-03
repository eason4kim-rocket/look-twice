# Look Twice V8

**Track:** Track 3 - Physical AI

**Entrant / team:** Liu Liang (solo entrant)

**GitHub:** [@eason4kim-rocket](https://github.com/eason4kim-rocket)

**Project:** Active Evidence Assurance for Physical AI on AMD Radeon GPU

Look Twice is the evidence-assurance layer immediately before robot motion. It
does not ask only what a perception model predicts; it asks whether the
evidence is independent, fresh, calibrated, conflict-free, and sufficient for
this action. When it is not, the denial becomes a machine-readable
`BeliefGap`: a low-risk scout acquires the missing view, the same scoped Action
Contract is re-qualified, and the system either recovers useful motion, takes a
disclosed safe detour, or fails closed.

The target application is warehouse AMR corridor traversal. The carrier may
take the direct route only when both the Python policy path and the standalone
Purify Go reference core admit it. This makes Look Twice complementary to
perception, planning, and simulation systems: it turns uncertain evidence into
a concrete next observation and robot action into an auditable decision.

This entry is simulation-only. It does not claim real-robot validation,
sim-to-real transfer, or safety certification.

## Judge-first links

- One-page frozen challenge Judge Card:
  [packaged copy](V8-Frozen-Challenge-Judge-Card.md)
- Post-hoc descriptive offline route-feasibility audit:
  [packaged JSON](evidence/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json)
- Independent machine verification:
  [packaged JSON](evidence/challenge_102500_102529/VERIFICATION.json) ·
  [stable release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json)
- Independently verified 30-world raw archive:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz>
- Evidence Console target: <https://eason4kim-rocket.github.io/>
- Frozen-results target: <https://eason4kim-rocket.github.io/results>
- Reproduction target: <https://eason4kim-rocket.github.io/reproduce>
- Dedicated source branch:
  <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release>
- Technical report:
  [packaged PDF](Look-Twice-V8-Technical-Report.pdf) ·
  [stable release target](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf)
- Final 3:59 English demo target:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>
- Frozen checkpoint:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt>
- 30-second evidence preview:
  [Look-Twice-V8-Evidence-Reel-30s.mp4](Look-Twice-V8-Evidence-Reel-30s.mp4)

The 30-second file is a silent evidence preview. The 3:59 MP4 is the complete
narrated workflow demonstration. The replacement MP4 and sidecar were
downloaded from their stable release targets without credentials and matched
the packaged SHA256 identities on 2026-08-03. The final 12-page report is
packaged here and bound by `SHA256SUMS`; its release URL is the publication
target.

## 90-second judge path

1. Open the [packaged Judge Card](V8-Frozen-Challenge-Judge-Card.md) and confirm
   Commit A/Commit B preceded all 60 episodes.
2. Check active 29/30 versus passive 0/30, the exact paired test, and the
   zero-error [independent verification](evidence/challenge_102500_102529/VERIFICATION.json).
3. Play the active replay and inspect the denial, `BeliefGap`, and independent
   side-view RGB-D capture.
4. Confirm that direct travel requires Python **and** Purify Go admission.
5. Inspect the 844-sample full-wall Radeon telemetry and 30-world
   carrier/scout burden table.
6. Open Results and trace the permanent locked numbers separately.

## Why the result matters

The locked, same-world paired comparison separates safe denial from useful
motion recovery:

| Locked full-chain outcome | Active repair | Passive baseline |
| --- | ---: | ---: |
| Direct route | 11 / 12 | 0 / 12 |
| Mission complete | 12 / 12 | 12 / 12 |
| Unsafe crossing | 0 / 12 | 0 / 12 |
| Unplanned fallback | 0 / 12 | 0 / 12 |

Active repair therefore recovered **+91.7 percentage points** of direct-route
use on the fixed 12-world locked suite. One active seed remained conservative
and detoured; it stays in the denominator. This is descriptive evidence for
the predeclared suite, not a population or real-world generalization.

After that result was permanent, a public two-commit preregistration fixed 30
untouched same-generator worlds, two policies, runner and validator SHAs,
balanced order, full-chain endpoint, full-wall telemetry, and no retries before
execution:

| Preregistered supplement | Active repair | Passive baseline |
| --- | ---: | ---: |
| Full-chain direct | 29 / 30 (96.7%) | 0 / 30 (0.0%) |
| Wilson 95% CI | 83.3-99.4% | 0.0-11.4% |
| Mission complete | 30 / 30 | 30 / 30 |
| Unsafe / fallback | 0 / 30; 0 / 30 | 0 / 30; 0 / 30 |

The paired gain is **+96.7 percentage points** with exact two-sided McNemar
`p=3.73e-9`. The sole active non-direct world remained safe and completed by
detour. All 60 episodes and the independent validator passed without a retry.

The preregistered primary endpoint remains **active 29/30 versus passive
0/30**. A separate post-hoc descriptive offline oracle-feasibility audit found
all **29/29** worlds with at least one oracle-clear corridor went direct and
selected an oracle-clear corridor. Seed `102515` was the only world with both
corridors oracle-blocked and completed by safe detour. Thus **30/30 active
route outcomes matched offline feasibility**. Oracle labels were never
available to the controller, and this audit is not a preregistered endpoint.
Across the 30 active records, unsafe was false, collision count was zero, and
fallback was false.

Receipt-level Python/Purify Go agreement was **250/268 (93.3%)**. All 18
differences were Python-admit/Go-deny and remained fail-closed with
`effective_admit=false`; no selected crossing relied on a disagreement.

Across these 30 pairs, active repair reduced mean loaded-carrier logical path
from 6.404 to 4.961 (**-22.5%**). The scout added 2.980 path and total
logical-role path rose from 6.404 to 7.941 (**+24.0%**). The supported claim is
burden shifting to diagnostic scouting, not lower total motion, energy, or
latency. Carrier and scout are logical poses and capture roots on one shared
Genesis chassis, not two physical robots or simultaneous dual-body dynamics.

This supplement is same-generator and non-locked. It is not a second locked
open, OOD result, rigid-body test, or physical-robot result.

## Frozen V8 result

V8 was opened once on an isolated locked split. No retuning, refitting, or
vision retraining followed the open.

| Metric | Result |
| --- | ---: |
| Locked offline samples | 3,200 |
| Decisive samples | 3,001 / 3,200 (93.78%) |
| Corridor ROI IoU | 1.000 |
| Decisive balanced accuracy | 1.000 |
| Decisive blocked recall | 1.000 |
| False-clear singleton rate | 0.000 |
| Split-conformal coverage | 1.000 |
| Python / Purify Go decision agreement | 24 / 24 policy runs |
| Unsafe crossings | 0 / 24 policy runs |
| Unplanned fallback | 0 / 24 policy runs |

The perfect classification values are explicitly decisive-set metrics; 199
inconclusive samples remain visible and are not forced into a class. The
interactive seed-105400 replay is non-locked confirmatory evidence and is not
substituted for the locked aggregate.

The separately released pre-open input-and-label archive contains 400 worlds
and 3,200 records and hashes to
`0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba`.
The packaged manifest verifies its structure and chronology without inference.
This input-only pack does not contain the original one-shot prediction rows or
24 raw full-chain episodes and cannot recompute the permanent result; no
missing output was regenerated.

## AMD Radeon and ROCm

The frozen environment used Genesis 1.1.2 on `gs.amdgpu`, PyTorch
2.9.1+gitff65f5b, HIP 7.2.53211-e1a6bc5663, and one Radeon Cloud `gfx1100`
GPU with approximately 48 GiB VRAM. Genesis simulation, RGB-D rendering,
tensor preprocessing, and the 39.8M-parameter spatial RGB-D model used the
Radeon GPU. The deterministic Purify Go gate ran on CPU as an independent
authorization layer.

The exact hash-pinned checkpoint passed a separate FP32 preloaded-tensor
model-forward benchmark. Batch 1 measured 192.31 ms p50 and 199.18 ms p95;
batch 8 measured 6.25 images/s with 668.38 MiB peak allocated memory. These are
model-forward measurements, not end-to-end robot latency.

A separate clean-preflight, 60.182-second batch-8 run archived raw `rocm-smi`
telemetry for the exact checkpoint. All 61 samples reported 100% GPU use; mean
graphics-package power was 135.33 W and p95 was 156 W. It forwarded 376
synthetic preloaded FP32 images at 6.248 images/s. This supports only sustained
Radeon model-forward execution: it is not an accuracy, locked, mission-energy,
or end-to-end robot benchmark.

The 30-world supplement adds complete pipeline-wall evidence. It retained 844
two-second `rocm-smi` samples across 1,685.5 seconds of 60 Genesis + frozen
checkpoint + Purify Go subprocesses, including idle. GPU use
mean/median/p95/max was 19.4/0/95/100%; VRAM p95/max was 2/2%; package power
mean/p95/max was 35.7/81/109 W. All 60 episodes used live Genesis RGB-D and the
frozen checkpoint; totals were 268 RGB-D observations, 134 vision proposals,
and 268 real Go invocations/receipts. These are kinematic simulation and full
subprocess-wall measurements, not physical energy or control-loop latency.

## Reproduction and identities

The dedicated source branch provides a deterministic CPU evidence audit,
Docker Evidence Console, Go reference-core tests, the exact Radeon runtime
command, environment identities, and checkpoint SHA256. The 159,592,901-byte
checkpoint must hash to:

```text
7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783
```

The immutable locked report must hash to:

```text
5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb
```

The sustained ROCm telemetry must hash to:

```text
0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9
```

The frozen-challenge raw archive must hash to:

```text
171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2
```

The deterministic independent verification must hash to:

```text
942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940
```

The packaged machine-evidence files are byte-identical to the compact source
copies. Verify the complete official package from this directory with:

```bash
sha256sum -c SHA256SUMS
jq -e '.passed == true and (.errors | length) == 0' \
  evidence/challenge_102500_102529/VERIFICATION.json
```

The 239.000-second final demo is 9,032,035 bytes and must hash to:

```text
70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05
```

Its sidecar manifest must hash to:

```text
639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb
```

Narration is AI-generated with OpenAI `gpt-4o-mini-tts` using the `cedar`
voice; the disclosure is burned into the video. Chapter visuals use fixed
composition with no `zoompan` motion.

The compact [evidence directory](evidence/README.md) contains the scrubbed
locked report, exact-checkpoint Radeon benchmark, raw sustained telemetry,
locked-input manifest, frozen import manifest, machine-readable task-utility
derivation, and the preregistered challenge report, run manifest, full-wall
ROCm telemetry, independent verification, and raw-archive checksum index.
The machine-readable [package manifest](SUBMISSION_PACKAGE.json) states the
included payload and evidence boundaries. Every packaged regular file except
the checksum index itself is bound by [SHA256SUMS](SHA256SUMS).
