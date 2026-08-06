# Look Twice V8

**Track:** Track 3 - Physical AI

**Entrant / team:** Liu Liang (solo entrant)

**GitHub:** [@eason4kim-rocket](https://github.com/eason4kim-rocket)

**Project:** Active Evidence Assurance for Physical AI on AMD Radeon GPU

[![Look Twice V8 — contract-aware active perception on AMD GPU](Look-Twice-V8-Social-Card.png)](https://eason4kim-rocket.github.io/#full-demo)

**[▶ Watch the complete 3:59 Demo in your browser](https://eason4kim-rocket.github.io/media/Look-Twice-V8-Demo.mp4)** ·
[open the 30-second evidence replay](https://eason4kim-rocket.github.io/#full-demo) ·
[download the hash-verified MP4](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4)

The browser copy and Release download are the same 239-second, 1920×1080
simulation-only AMD Radeon/ROCm workflow video at SHA256
`70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`.

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

> **Current owner-review state:** the independently verified compound
> contract-progress result is integrated into the human-readable source and a
> compact evidence index. The final 19-page technical-report PDF passed 19/19
> rendered-page QA, and its output/site/official copies are byte-identical at
> SHA256 `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`.
> Package manifests/checksums are mechanically finalized from this tree. No
> competition PR has been opened.

## Judge-first links

- Compact frozen challenge Judge Card:
  [packaged copy](V8-Frozen-Challenge-Judge-Card.md)
- Compound contract-progress result:
  [compact result](evidence/contract_progress_challenge_102530_102549/RESULT_SUMMARY.md) ·
  [evidence index](evidence/contract_progress_challenge_102530_102549/EVIDENCE_INDEX.json)
- Post-hoc descriptive offline route-feasibility audit:
  [packaged JSON](evidence/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json)
- Separate additive dual-body dynamics result:
  [machine report](evidence/dual_body_dynamics_160820_160839/REPORT.json) ·
  [recovery audit](evidence/dual_body_dynamics_160820_160839/RECOVERY_EXECUTION_AUDIT.json) ·
  [checksums](evidence/dual_body_dynamics_160820_160839/SHA256SUMS)
- Separate additive decision-bound dynamics replay:
  [30/30 machine report](evidence/decision_dynamics_recovery_v2_102500_102529/REPORT.json) ·
  [execution audit](evidence/decision_dynamics_recovery_v2_102500_102529/RECOVERY_EXECUTION_AUDIT.json) ·
  [proof-scope review](evidence/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json) ·
  [complete package checksums](evidence/decision_dynamics_recovery_v2_102500_102529/PACKAGE_SHA256SUMS)
- Separate solver-scale two-shard complement:
  [20/20 60-body prefix report](evidence/decision_dynamics_single_scene_60_102500_102519/REPORT.json) ·
  [prefix complete-package checksums](evidence/decision_dynamics_single_scene_60_102500_102519/PACKAGE_SHA256SUMS) ·
  [10/10 30-body suffix report](evidence/decision_dynamics_single_scene_30_suffix_102520_102529/REPORT.json) ·
  [suffix complete-package checksums](evidence/decision_dynamics_single_scene_30_suffix_102520_102529/PACKAGE_SHA256SUMS) ·
  [prefix protocol](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_60_PROTOCOL.md) ·
  [suffix protocol](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_30_SUFFIX_PROTOCOL.md)
- Independent machine verification:
  [packaged JSON](evidence/challenge_102500_102529/VERIFICATION.json) ·
  [stable release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json)
- Independently verified 30-world raw archive:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz>
- Evidence Console target: <https://eason4kim-rocket.github.io/>
- Frozen-results target: <https://eason4kim-rocket.github.io/results>
- Reproduction target: <https://eason4kim-rocket.github.io/reproduce>
- Frozen-primary source branch:
  <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release>
- Additive contract-progress source and complete evidence branch:
  <https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv>
- Technical report:
  [packaged contract-progress-integrated PDF](Look-Twice-V8-Technical-Report.pdf) ·
  [replacement publication target](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf)
- Final 3:59 English demo target:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>
- Frozen checkpoint:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt>
- 30-second evidence preview:
  [Look-Twice-V8-Evidence-Reel-30s.mp4](Look-Twice-V8-Evidence-Reel-30s.mp4)

The 30-second file is a silent evidence preview. The 3:59 MP4 is the complete
narrated workflow demonstration. The replacement MP4 and sidecar matched their
published SHA256 identities on 2026-08-03. The contract-progress-integrated
technical-report PDF is 19 pages and 1,104,864 bytes; all 19 rendered pages
passed visual QA, and output/site/official copies are byte-identical at SHA256
`7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`.
The finalized package has 155 manifest entries, 156 checksum entries, and 157
total files.

## Judge-first review path

1. Open the [packaged Judge Card](V8-Frozen-Challenge-Judge-Card.md) and confirm
   Commit A/Commit B preceded all 60 episodes.
2. Check active 29/30 versus passive 0/30, the exact paired test, and the
   zero-error [independent verification](evidence/challenge_102500_102529/VERIFICATION.json).
3. Play the active replay and inspect the denial, `BeliefGap`, and independent
   side-view RGB-D capture.
4. Confirm that direct travel requires Python **and** Purify Go admission.
5. Inspect the 844-sample full-wall Radeon telemetry and 30-world
   carrier/scout burden table.
6. Inspect the separately preregistered compound result: both arms 20/20
   direct, with lower scout and team path in every paired world.
7. Inspect the separately labeled 30/30 decision-bound wheel-dynamics replay:
   90/90 bodies reached across 30 independent scenes; 29/29 direct pairs kept
   a simulated loaded-carrier path advantage; the one dual-blocked case safely
   detoured.
8. Inspect the solver-scale complement separately: 20/20 fixed decisions in
   one 60-body scene plus 10/10 in a second 30-body scene. This is exactly two
   scene shards, 90 cumulative distinct robots, and at most 60 co-resident--not
   one 90-body scene.
9. Inspect the earlier 20/20 dual-body wheel-dynamics component bar and its
   retained timeout/recovery chain.
10. Open Results and trace the permanent locked numbers separately.

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

## Additive compound contract-progress efficiency

Commit A `6c7b46dc3ac5044c7ed0c422fc30dee1d5b1ba1e` fixed the compound
candidate and Commit B `427f2f729ce653df91a20db56c9fdbd16911a014`
changed only the preregistration binding before seeds `102530–102549` were
opened. The fixed 20-world, 40-cell paired run passed every mandatory and
capability gate:

| Preregistered endpoint | Baseline | Compound candidate | Reduction |
| --- | ---: | ---: | ---: |
| Full-chain direct | 20/20 | 20/20 | no regression |
| Mean scout path | 2.9229 m | 1.7462 m | **40.2563%** |
| Mean team path | 7.8326 m | 6.6553 m | **15.0306%** |
| Physical captures | 69 | 50 | **27.5362%** |

The three paired-bootstrap 95% intervals were 36.0505–45.0271%,
12.2563–17.6227%, and 15.6250–37.8378%. All 20 scout and team deltas were
negative. Mission success was 40/40; unsafe, collision, fallback, and false
clear were zero. Candidate decisions were 30 native and zero delegated. Exact
path set, checksums, pre/post and public-remote bindings, frozen-Go receipts,
attempt reconstruction, and 554-sample telemetry all validated;
`promotion_pass=true`.

This is a compound-system result for shared frozen dual-ROI inference,
physical-root unification, and contract-aware NBV together. It does not use new
weights, calibration, gates, or thresholds and is not a single-component
causal claim. It remains same-generator, non-locked, kinematic simulation with
`formal_result_eligible=false`—not OOD, physical-robot, sim-to-real, or
safety-certification evidence—and does not replace the frozen primary.

## Separate additive dual-body rigid dynamics

A fixed submission-time protocol tested one narrow implementation gap without
rerunning or relabeling the frozen policy endpoint. Seeds `160820-160839`
instantiated a loaded carrier and a scout as separate non-fixed Genesis URDF
bodies: **40 distinct robot entities in one Genesis scene containing 20
spatially isolated trial worlds**. The
scout moved while the carrier stayed parked, then the carrier moved while the
scout stayed parked. The only post-build actuation API was wheel-DOF
`control_dofs_velocity`; the script made no pose write after `scene.build()`.

The AMD Radeon/ROCm acceptance run passed **20/20** fixed seeds with zero
trial-blocker contact rows, zero carrier/scout pair-contact rows, and zero
post-build pose writes. Maximum tilt was 10.750 degrees, maximum parked-partner
drift was 0.018061 m, and mean scout/carrier paths were 1.645/4.760 m. The
byte-identical report passed the same verifier remotely and locally and hashes
to `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110`.

The first whole-process attempt reached only an external 3,600-second watchdog
before any report or seed result was observed. Recovery changed only that
watchdog to 10,800 seconds; source commit, runner/URDF bytes, fixed seeds,
protocol, and thresholds stayed unchanged. Both audits are packaged. This is
additive, non-locked evidence with `formal_result_eligible=false`: it validates
bounded wheel motion by two rigid bodies, not a frozen-policy rerun,
simultaneous cooperative control, a physical robot, sim-to-real transfer, or
safety certification.

## Separate additive decision-bound dynamics replay

The fixed V2 protocol consumed the immutable archived decisions for seeds
`102500-102529`: 29 direct decisions and the single safe outer detour at seed
`102515`. Each seed ran serially in a fresh paired Genesis scene containing one
active non-fixed scout, one active non-fixed loaded carrier, and one passive
non-fixed loaded carrier. Across 30 independent scenes this instantiated 90
distinct bodies; it was not one simultaneous 90-body scene.

The AMD Radeon/ROCm run passed **30/30**. All 90/90 bodies were wheel-actuated
and reached; all 29 direct pairs saved at least 0.50 m of loaded-carrier path;
mean active/passive carrier paths were 4.943529/6.243270 m, a paired reduction
of **20.8183%**. Counted Genesis blocker and active carrier/scout contact rows were
0/0; maximum tilt was 10.579607 degrees and maximum parked-partner drift was
0.022329 m.

V1's one-scene 90-body layout reached four-hour and 12-hour external watchdogs
before writing any report. V2 kept seeds, archived decisions, within-seed
geometry, controller, and thresholds fixed while changing the failure domain:
one fresh subprocess and one atomic checkpoint per seed. The retained ledger
shows 30 attempt-one worker exits at zero, with no observed retry or
replacement. The report passed the frozen verifier remotely and locally and
hashes to
`1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`.

The bundled provenance review deliberately records two proof-scope limits.
The original inner checksum index did not cover attempts/progress/logs, and
the source binding omitted the directly imported `src/v4_motion.py`. The
complete outer package index now fixes every retained artifact, while a clean
2,419-file post-run audit found no source difference. These facts corroborate
the execution; they are not described as continuous cryptographic attestation.

This is additive, non-locked, archived-decision simulation evidence with
`formal_result_eligible=false`. It does not replace the frozen 29/30 primary,
rerun live perception/policy inference, demonstrate simultaneous cooperation,
dynamic-obstacle response, real-robot or sim-to-real validation, throughput,
energy, or safety certification.

## Separate solver-scale two-shard complement

A further fixed submission-time complement consumed the same immutable 30
archived decisions without rerunning perception or policy inference. Seeds
`102500-102519` passed **20/20** in one Genesis scene containing **60
co-resident non-fixed robots**: 20 scouts, 20 active loaded carriers, and 20
passive loaded carriers. Seeds `102520-102529` independently passed **10/10**
in a second Genesis scene containing **30 co-resident non-fixed robots**, ten
of each role.

Each shard used one Genesis initialization and one scene build, then actuated
its assigned trials in fixed serial order using wheel-DOF velocity control.
Neither shard supported resume. The two exact reports independently passed
their source-aware verifiers and checksum indexes. Their only combined topology
statement is **exactly two completed scene shards, 90 cumulative distinct robot
instantiations, and a maximum of 60 co-resident robots**. The 90 robots were
never co-resident in a single scene; there is no synthetic combined execution
report and the result does not convert V1's timed-out one-scene 90-body attempt
into a pass.

Across the two reports, all 30 scouts, 30 active carriers, and 30 passive
carriers reached. All **29/29** direct pairs saved at least 0.50 m of simulated
loaded-carrier path, while seed `102515` completed its archived safe detour.
The fixed-denominator weighted mean was **4.943605 m active versus 6.245385 m
passive**, a **20.8439%** reduction. Counted blocker-contact and active-pair
contact rows were zero; post-build script pose writes were zero; maximum tilt
was **10.583984 degrees** and maximum parked-partner drift was **0.021342 m**.

The 60-body report SHA256 is
`3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450`;
the 30-body suffix report SHA256 is
`69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e`.
Both remain additive, non-locked, archived-decision, fixed-order serial,
simulation-only evidence with `formal_result_eligible=false`. They are not a
live perception-policy rerun, simultaneous cooperative fleet control,
dynamic-obstacle evidence, physical-robot validation, sim-to-real evidence,
throughput or energy evidence, or safety certification. The preregistered
primary remains **active 29/30 versus passive 0/30**.

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

The dual-body supplement separately retained a 4,299.992-second Genesis
1.1.2/`gs.amdgpu` execution on the Radeon host. This is a fixed-seed acceptance
bar, not throughput, mission energy, control-loop latency, or a physical-device
benchmark.

The decision-bound V2 replay used the same Radeon/ROCm software class with one
fresh three-body scene per fixed seed. Its approximately 18-minute wall is an
execution-audit fact only, not a throughput or latency benchmark.

The separate solver-scale prefix and suffix used Genesis 1.1.2 on
`gs.amdgpu` with 60 and 30 co-resident non-fixed bodies respectively. Their
body counts, scene counts, and elapsed walls are solver-topology acceptance
facts, not fleet throughput, utilization, latency, or energy benchmarks.

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
(cd evidence/dual_body_dynamics_160820_160839 && \
  shasum -a 256 -c SHA256SUMS)
(cd evidence/decision_dynamics_recovery_v2_102500_102529 && \
  shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PACKAGE_SHA256SUMS)
(cd evidence/decision_dynamics_single_scene_60_102500_102519 && \
  shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PACKAGE_SHA256SUMS)
(cd evidence/decision_dynamics_single_scene_30_suffix_102520_102529 && \
  shasum -a 256 -c SHA256SUMS && shasum -a 256 -c PACKAGE_SHA256SUMS)
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
ROCm telemetry, independent verification, raw-archive checksum index, the
separately labeled dual-body report and timeout/recovery audit chain, plus the
complete 30-seed decision-bound checkpoint/report/provenance package, and the
complete 60-body prefix and 30-body suffix solver-scale evidence directories.
The machine-readable [package manifest](SUBMISSION_PACKAGE.json) states the
included payload and evidence boundaries. Its final inventory contains 155
manifest entries and [SHA256SUMS](SHA256SUMS) binds all other 156 package
files in the 157-file package. The checksum index's own identity is recorded
outside the package to avoid a circular self-reference.
