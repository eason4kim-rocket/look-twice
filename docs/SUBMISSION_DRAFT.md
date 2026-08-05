# Track 3, Liu Liang, Look Twice

## Judge Snapshot

- **29/30 vs 0/30** — preregistered 30-world full-chain direct routes, active
  versus passive; the sole active non-direct case completed by safe detour.
- **60/60 missions · 0/60 unsafe · 0/60 fallback** — all active and passive
  challenge episodes completed under the fixed protocol.
- **60/60 live RGB-D episodes** — every episode used Genesis live RGB-D and the
  frozen 39.8M-parameter learned checkpoint; Python and Purify Go remained
  fail-closed.
- **844 samples · 1,685.5 s** — complete Python + Genesis + checkpoint + Purify
  Go subprocess-wall telemetry on AMD ROCm, including idle; not control-loop
  latency or physical energy.
- **40.2563% scout · 15.0306% team · 27.5362% captures** — separately
  preregistered compound contract-progress reductions across 20 paired worlds;
  both arms remained 20/20 full-chain direct, with 40/40 missions and zero
  unsafe, collision, fallback, or false-clear outcomes.
- **20 @ 60 bodies + 10 @ 30 bodies** — two independently verified
  archived-decision wheel-dynamics scenes: 90 cumulative distinct robots,
  maximum 60 co-resident, never all 90; not a live-policy rerun.
- **Genesis PR #3184** — open, non-draft two-file URDF inertial-origin fix
  linked to issue #3183; a bounded serial-CPU regression passed 3/3 selected
  nodes at the exact head. It is unmerged, with no full-suite, review, or
  acceptance claim.

## Project

**Look Twice V8 - Active Evidence Assurance for Physical AI on AMD Radeon GPU**

Look Twice is the evidence-assurance layer immediately before robot motion. It
asks not only what a model predicts, but whether the evidence is independent,
fresh, calibrated, conflict-free, and sufficient for this action. When it is
not, a denial becomes a machine-readable BeliefGap: the robot acquires the
missing view, re-qualifies the same Action Contract, and either recovers useful
motion, takes a disclosed safe detour, or fails closed.

The target application is warehouse AMR corridor traversal. A carrier may take
the direct route only when a scoped Action Contract is satisfied. Otherwise a
scout acquires a diagnostic side-view observation, the plan is re-evaluated,
and the system either qualifies direct travel, takes a disclosed safe detour,
or fails closed.

Look Twice is therefore complementary to a perception model, planner, or world
simulator. Its contribution is the auditable boundary that decides whether the
available evidence is strong enough to authorize a particular action, and what
observation is needed when it is not.

## Try it first

Public Evidence Console, no sign-in required:

https://eason4kim-rocket.github.io/

The deployed baseline site replays recorded Genesis plus AMD GPU evidence. It
does not create new benchmark samples and does not require a live GPU. The
authorized contract-progress Results/Reproduce refresh has passed local build
and evidence tests; publication and no-sign-in verification are in progress.

## 90-second judge path

1. Open the compact [V8 Frozen Challenge Judge Card](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md).
2. Confirm the public Commit A/Commit B timestamps, 30-pair endpoint, raw
   archive, and independent verification SHA.
3. Open the Evidence Console and watch the initial denial, BeliefGap, and
   independent side-view capture.
4. Confirm that direct motion requires Python admission and Purify Go
   admission.
5. Switch to passive mode and compare its safe detour.
6. Inspect the challenge's 844-sample full-wall ROCm telemetry and 30-world
   carrier/scout burden table.
7. Inspect the separate compound contract-progress result: 20/20 direct in
   both arms, with every paired world reducing scout and team path.
8. Open Results and inspect the separate 30/30 decision-bound rigid-dynamics
   card, then the earlier 20/20 dual-body acceptance card.
9. Inspect its independently verified solver-scale complement: 20/20 in one
   60-body scene and 10/10 in a second 30-body scene--exactly two scenes, 90
   cumulative distinct robots, maximum co-resident 60, never all 90
   co-resident.
10. Confirm that all dynamics results are archived-decision execution
   supplements and that the preregistered primary endpoint remains active
   29/30 versus passive 0/30.
11. Follow the permanent locked metrics separately.

## Official Track 3 judging map

| Criterion | Evidence in this submission |
| --- | --- |
| Robot capability performance - 30 | Permanent locked evidence: active 11/12 direct versus passive 0/12. Publicly preregistered primary: active **29/30** full-chain direct versus passive 0/30 (+96.7 pp, exact McNemar `p=3.73e-9`), 60/60 missions, 0/60 unsafe, 0/60 fallback. Separate compound challenge: both arms 20/20 direct while the candidate reduced scout path 40.2563%, team path 15.0306%, and captures 27.5362%, with 40/40 missions and zero unsafe/collision/fallback/false-clear. Separate V2: 30/30 archived decisions in 30 independent three-body scenes. Solver-scale complement: **20/20 in one 60-body scene + 10/10 in a second 30-body scene**, 90/90 cumulative bodies reached, maximum co-resident 60, never all 90 co-resident, 29/29 direct pairs saved at least 0.50 m, one safe detour, and zero counted blocker/active-pair contact rows. None replaces the 29/30 endpoint. |
| AMD Radeon GPU and ROCm adoption - 20 | Genesis 1.1.2 on `gs.amdgpu`, live RGB-D, tensor preprocessing, and the 39.8M-parameter model on PyTorch ROCm/HIP 7.2. The challenge retains 844 `rocm-smi` samples across its complete 1,685.5-second wall; the separate dual-body, V2, single-scene 60-body, and second-scene 30-body wheel-dynamics runs retain reports, source bindings, checksums, and local verifiers. Body counts and elapsed walls are acceptance facts, not throughput claims. |
| Innovation and originality - 20 | Action-scoped spatial perception, physical-root lineage, split-conformal sets, dual Python/Go authorization, BeliefGap-driven repair, and canonical receipts. |
| Real-world application value - 20 | Across 30 simulated warehouse-AMR logical-role pairs, active scouting reduced loaded-carrier logical path 22.5% while increasing total logical-role path 24.0%; all simulated missions completed without an unsafe or fallback outcome. The separate two-shard wheel replay retained a weighted 20.8439% loaded-carrier path reduction; neither result is energy or throughput evidence. |
| Upstream open-source contribution - 10 | Project code, schemas, Purify Go reference core, validators, replay builder, and evidence site are open source. Public Genesis [issue #3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183) and open, non-draft [PR #3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184) carry a focused two-file URDF inertial-origin fix at `0fa0f4a`. On tested upstream `main` `207db28`, the identical required test failed and passed with the patch; complete `scene.build()` comparison preserved authored principal moments only with the patch while retaining geometry fallback for an absent `<inertial>` in both trees. A later [bounded serial-CPU validation](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-final-2026-08-05/docs/V8_GENESIS_PR_3184_VALIDATION.md) at the exact PR head passed 3/3 selected regression nodes; it is not a full-suite claim. The PR is open and unmerged; no review, acceptance, or upstream-release inclusion is claimed. |

## Verified frozen result

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
| Active full-chain direct | 11 / 12 |
| Passive full-chain direct | 0 / 12 |
| Paired direct-route gain | +91.7 percentage points |
| Mission completion | 12 / 12 active; 12 / 12 passive |
| Passive deny and safe detour | 12 / 12 |
| Unsafe crossings | 0 / 24 policy runs |
| Unplanned fallback | 0 / 24 policy runs |
| Python / Purify Go decision agreement | 24 / 24 policy runs |

Authoritative report:
<https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/LOCKED_TEST_REPORT.json>

Report SHA256:
`5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb`

One active locked seed remained conservative and detoured. It remains in the
denominator.

This table is derived from the permanent paired rows without rerunning V8 or
reopening the locked split. The
[machine-readable derivation](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/V8_TASK_UTILITY_DERIVATION.json)
has SHA256
`f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b`.
The paired comparison is descriptive evidence for this fixed seed suite, not a
population or real-world generalization.

The original pre-open input-and-label archive is published as a 1,019,307,579-
byte release asset with SHA256
`0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba`.
Its streaming verifier passed 400 worlds, 3,200 metadata records, 22,800 file
members, label/seed/path checks, sidecar chronology, and permanent-result hash
binding without inference or extraction. This is input-only evidence: it does
not contain the original one-shot prediction rows or 24 raw full-chain
episodes and cannot recompute the permanent result. Nothing was regenerated.

## Preregistered 30-world frozen challenge

After the locked report was permanent, two public commits fixed the runner,
independent validator, identities, 30 untouched same-generator seeds, balanced
policy order, primary endpoint, telemetry, timeout, and no-retry rule before
execution. [Commit A](https://github.com/eason4kim-rocket/look-twice/commit/9e14cbb999824d35a21749f4ff420ab63f81847d)
was published at `2026-08-03T10:01:53Z`; [Commit B](https://github.com/eason4kim-rocket/look-twice/commit/3a52ba548de26858a7fdcad1c1ce7237b709fe69)
at `2026-08-03T10:02:22Z`. B changed only the A-hash field.

| Preregistered endpoint | Active | Passive |
| --- | ---: | ---: |
| Full-chain direct | 29/30 (96.7%) | 0/30 (0.0%) |
| Wilson 95% CI | 83.3-99.4% | 0.0-11.4% |
| Mission success | 30/30 | 30/30 |
| Unsafe | 0/30 | 0/30 |
| Fallback | 0/30 | 0/30 |

The paired gain is **+96.7 percentage points**; exact two-sided McNemar
`p=3.73e-9`. Full-chain direct requires mission success, direct/no-detour, and
Python + Go + effective authorization for the corridor actually executed. The
sole active non-direct case completed safely by detour. The independent
validator passed with zero errors; deterministic verification SHA256 is
`942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940`.

The preregistered primary endpoint remains **active 29/30 versus passive
0/30**. A separate post-hoc descriptive offline oracle-feasibility audit found
that all **29/29** worlds with at least one oracle-clear corridor went direct
and selected an oracle-clear corridor. The only dual-blocked world, seed
`102515`, completed by safe detour. Thus **30/30 active route outcomes matched
offline feasibility**. Oracle labels were never available to the controller,
and this audit is not a preregistered endpoint. Across the 30 active records,
unsafe was false, collision count was zero, and fallback was false.

Receipt-level Python/Purify Go agreement was **250/268 (93.3%)**. All 18
differences were Python-admit/Go-deny and remained fail-closed with
`effective_admit=false`; no selected crossing relied on a disagreement.

This is an additive **same-generator non-locked** challenge, not a second
locked open, OOD result, rigid-body test, or physical-robot result. Full details
and a clean-clone command are on the [Judge Card](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md).

## Additive compound contract-progress efficiency challenge

A separate public binding evaluated frozen V8 against the opt-in compound
candidate on seeds `102530–102549`. Commit A
[`6c7b46d`](https://github.com/eason4kim-rocket/look-twice/commit/6c7b46dc3ac5044c7ed0c422fc30dee1d5b1ba1e)
fixed the executable candidate; Commit B
[`427f2f7`](https://github.com/eason4kim-rocket/look-twice/commit/427f2f729ce653df91a20db56c9fdbd16911a014)
changed only the preregistration binding before the 20-world, 40-cell run.

| Preregistered endpoint | Baseline | Compound candidate | Reduction |
| --- | ---: | ---: | ---: |
| Full-chain direct | 20/20 | 20/20 | no regression |
| Mean scout path | 2.9229 m | 1.7462 m | **40.2563%** |
| Mean team path | 7.8326 m | 6.6553 m | **15.0306%** |
| Physical captures | 69 | 50 | **27.5362%** |

Paired-bootstrap 95% intervals were **36.05–45.03%**, **12.26–17.62%**,
and **15.625–37.838%**, respectively. Scout and team deltas favored the
candidate in 20/20 worlds. Mission success was 40/40; unsafe, collision,
fallback, and false clear were zero. All 30 candidate decisions were native
contract-progress choices; delegated decisions were zero. The independent
verifier reported `promotion_pass=true` and validated exact path-set,
checksum, public-remote, source, receipt, attempt, and telemetry bindings.

This is a compound V8 intervention—shared frozen dual-ROI inference,
physical-root unification, and contract-aware NBV together—not new weights or
a single-component causal claim. It is additive same-generator, non-locked,
kinematic simulation with `formal_result_eligible=false`; it is not OOD,
physical-robot, sim-to-real, or safety-certification evidence and does not
replace the frozen primary. [Result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_CONTRACT_PROGRESS_CHALLENGE_RESULT.md).

## Task-value cost ledger

Across the 30 preregistered pairs, active repair reduced mean loaded-carrier
logical path from 6.404 to 4.961 (-1.443, **-22.5%**). This was a deliberate
trade, not a free speedup: mean scout path was 2.980 and total logical-role path
rose from 6.404 to 7.941 (+1.538, **+24.0%**). The claim is burden shifting
from a loaded carrier to diagnostic scouting, not lower total distance,
energy, or latency. Carrier and scout are distinct logical poses and capture
roots on one shared Genesis chassis, not two physical robots or simultaneous
dual-body dynamics.

## Separate additive dual-body rigid dynamics

A fixed submission-time protocol then tested that narrow realization gap
without rerunning the policy endpoint. Seeds `160820-160839` instantiated one
loaded carrier and one scout each as separate non-fixed Genesis URDF bodies:
**40 robot entities** in one non-overlapping scene. The scout and carrier moved
in sequential phases using wheel-DOF velocity targets only; the script issued
no entity pose write after `scene.build()`.

The Radeon run passed **20/20** fixed seeds with zero counted trial-blocker
contact rows, zero counted carrier/scout-pair contact rows, and zero post-build
pose writes. Maximum
tilt was 10.750 degrees and maximum parked-partner drift was 0.018061 m. The
source-bound report passed the same verifier remotely and locally and hashes
to `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110`.

Attempt 1 reached an external 3,600-second watchdog before any report or seed
outcome was observed. Recovery changed only that watchdog to 10,800 seconds;
commit, runner/URDF bytes, seeds, protocol, and thresholds were unchanged. The
failed infrastructure attempt is retained beside the completed report.

This result is additive, non-locked, and `formal_result_eligible=false`. It
validates bounded wheel motion by two rigid bodies, not a full-policy
conversion to simultaneous cooperative control, a physical robot, or
sim-to-real transfer.

## Separate additive decision-bound dynamics recovery V2

Recovery V2 closes a narrower decision-to-actuation gap without reopening the
locked split or changing the preregistered challenge endpoint. It replays the
immutable archived challenge decisions -- 29 direct corridor decisions and
the single dual-blocked safe detour at seed `102515` -- without rerunning the
frozen perception-policy loop.

Seeds `102500-102529` ran as **30 independent Genesis scenes**, one fresh
subprocess and one paired three-body scene per seed: an active scout, active
loaded carrier, and passive loaded carrier. All **30/30** seeds passed and all
**90/90** distinct non-fixed robot instantiations reached their goals. The 90
bodies are counted across the 30 scenes; they were not simulated together in
one simultaneous 90-body scene.

Across the 29 archived direct decisions, every active/passive carrier pair
saved at least 0.50 m. Mean active and passive loaded-carrier paths were 4.944
m and 6.243 m, a paired reduction of **20.8183%**. The retained records contain
zero blocker-contact rows, zero active carrier/scout contact rows, and zero
post-build entity pose writes. The single archived safe-detour decision also
reached its declared goal.

This remains additive, non-locked, simulation-only evidence with
`formal_result_eligible=false`. It does not turn the preregistered active
**29/30** full-chain endpoint into 30/30, and it is not a frozen-policy rerun,
simultaneous cooperative-control test, dynamic-obstacle test, physical-robot
result, sim-to-real result, throughput claim, or safety certification.

The report hashes to
`1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`
and passed the same verifier on the Radeon host and local source snapshot. The
retained attempt ledger and worker logs show 30 first-attempt completions with
exit code zero, no completed-checkpoint rerun, and no seed replacement.
Proof scope is narrower than those observations: the formal checksum index did
not originally cover attempt, progress, or log files, and the formal source
manifest omitted the directly imported `src/v4_motion.py`. A post-run tree
audit and the complete package index provide corroboration, not cryptographic
proof of continuous no-retry execution or a fully bound runtime dependency
closure.

## Separate solver-scale two-shard complement

A further fixed submission-time complement tests the same archived decisions
with unrelated bodies resident in each Genesis solver. Seeds `102500-102519`
passed **20/20** in one scene containing 60 co-resident non-fixed robots. Seeds
`102520-102529` passed **10/10** in a second scene containing 30 co-resident
robots. Each scene had one scout, one active loaded carrier, and one passive
loaded carrier per assigned seed; used one Genesis initialization and one
scene build; actuated trials in fixed serial order with wheel velocity control;
and produced a separate, non-resumable, independently verified report.

Across **exactly two completed scene shards**, all 30 scouts, 30 active
carriers, and 30 passive carriers reached. The two reports therefore contain
**90 cumulative distinct robot entities**, with **maximum co-resident 60**;
the 90 robots were **never all co-resident**. There was no cross-shard resume
or report stitching. All 29 archived direct pairs saved at least 0.50 m, seed
`102515` completed its archived safe detour, and the weighted loaded-carrier
mean was **4.943605 m active versus 6.245385 m passive**, a **20.8439%**
reduction. Counted blocker/active-pair contact rows and post-build pose writes
were zero; maximum tilt/drift was **10.583984 degrees / 0.021342 m**.

The 60-body prefix report SHA256 is
`3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450`;
the 30-body suffix report SHA256 is
`69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e`.
Both exact reports must verify independently before the two-shard summary is
used. This does not relabel the timed-out V1 all-90-body attempt as successful.

The complement is additive, non-locked, archived-decision, fixed-order serial,
simulation-only evidence with `formal_result_eligible=false`. It is not a live
perception-policy rerun, simultaneous cooperative fleet-control test,
dynamic-obstacle test, physical-robot or sim-to-real result, energy/throughput
claim, or safety certification. The preregistered primary remains active
**29/30** full-chain direct versus passive **0/30**.

## What runs on the AMD Radeon GPU

| Stage | Execution |
| --- | --- |
| Genesis simulation | Radeon GPU, `gs.amdgpu` |
| RGB-D rendering | Radeon GPU |
| RGB-D preprocessing | PyTorch ROCm tensors |
| Spatial RGB-D inference | Radeon GPU, PyTorch device `cuda:0` |
| Purify contract gate | CPU, standalone Go process |
| Public Evidence Console | CPU-only replay of recorded GPU evidence |

Frozen environment: Linux x86_64, Python 3.12.3, Genesis 1.1.2, PyTorch
2.9.1+gitff65f5b, HIP 7.2.53211-e1a6bc5663, one Radeon Cloud `gfx1100`
GPU with approximately 48 GiB VRAM.

The exact checkpoint passed a preloaded-tensor FP32 model-forward benchmark:
batch 1 p50 192.31 ms and p95 199.18 ms; batch 8 throughput 6.25 images/s
with 668.38 MiB peak allocated memory. These values exclude preprocessing,
Genesis, Go fusion, I/O, and actuation and are not end-to-end latency. Source:
[machine-readable benchmark](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json)
(SHA256
`282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156`).

The supplemental 60-second batch-8 telemetry run began with 0% GPU use, 0%
VRAM allocation, and no KFD process. All 61 measured `rocm-smi` samples
reported 100% GPU use; mean graphics-package power was 135.33 W, p95 power was
156 W, and throughput was 6.248 images/s. It used synthetic preloaded FP32
tensors and is neither an accuracy run nor an end-to-end latency/energy claim.
[Raw telemetry](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json)
has SHA256
`0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9`.

The preregistered challenge adds full-pipeline telemetry rather than another
synthetic model loop. Its 844 two-second samples span 1,685.5 seconds and keep
idle periods: GPU use mean/median/p95/max was 19.4/0/95/100%, VRAM p95/max was
2/2%, and package power mean/p95/max was 35.7/81/109 W. All 60 episodes used
Genesis live RGB-D, loaded the frozen checkpoint, and produced Purify Go
receipts: 268 RGB-D observations, 134 vision proposals, and 268 Go
invocations/receipts. These are complete subprocess-wall measurements, not
control-loop latency or physical energy per mission.

The solver-scale complement separately ran one 60-body and one 30-body scene
on the same Genesis/ROCm class. Both scene shards passed their fixed acceptance
bars and independent verifiers. Their co-resident body counts and elapsed
walls are execution-topology facts, not GPU throughput, utilization,
control-loop latency, or mission-energy claims.

## Deliverables

| Requirement | Location |
| --- | --- |
| Compact challenge Judge Card | [public preregistration, result, AMD telemetry, application burden, and verifier](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md) |
| Challenge machine evidence | [report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json) · [post-hoc feasibility audit](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json) · [verification](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/challenge_102500_102529/VERIFICATION.json) · [3.19 MB raw archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz) |
| Compound efficiency evidence | [result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_CONTRACT_PROGRESS_CHALLENGE_RESULT.md) · [evidence index](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/release/v8-derived/contract_progress_challenge_102530_102549/EVIDENCE_INDEX.json) · complete report, verification, telemetry, run manifest, checksum index, and raw records under the same release evidence root |
| Dual-body dynamics evidence | [20-seed result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md) · [machine report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json) · timeout/recovery audits and `SHA256SUMS` in the same directory |
| Decision-bound dynamics V2 | [30-seed result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md) · [complete evidence directory](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release/release/v8-derived/decision_dynamics_recovery_v2_102500_102529) · formal and package checksum indexes, provenance review, and local verifier |
| Solver-scale two-shard evidence | Published [20/20 60-body prefix report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/decision_dynamics_single_scene_60_102500_102519/REPORT.json) · published [10/10 30-body suffix report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529/REPORT.json). Both sealed directories include their protocols, source bindings, trial checkpoints, checksum indexes, and verifier results. |
| Technical report | [Report source](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_TECHNICAL_REPORT.md) and [authorized stable publication target](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf): **19 pages, 1,104,864 bytes, SHA256 `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`; output/site/official copies byte-identical; 19/19 rendered pages visually inspected.** |
| Project source code | [additive contract-progress review branch](https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv) · [original frozen V8 foundation tag](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-final-2026-08-05) |
| Reproducibility README | [root judge path](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/README.md) · [detailed guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_REPRODUCTION.md) |
| Docker path | [Dockerfile](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/Dockerfile) · [Compose](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docker-compose.yml) |
| Public evidence site | [Evidence Console](https://eason4kim-rocket.github.io/) · [Results](https://eason4kim-rocket.github.io/results#contract-progress-efficiency) · [Reproduce](https://eason4kim-rocket.github.io/reproduce) · [public mirror](https://look-twice-evidence.jason-tuantuan1319.chatgpt.site/). Both deployments and their contract-progress JSON, PDF, and social preview were verified without sign-in. |
| Genesis upstream contribution | [Issue #3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183) · open, non-draft [PR #3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184) · [bounded 3/3 validation record](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-final-2026-08-05/docs/V8_GENESIS_PR_3184_VALIDATION.md) · exact fork head `0fa0f4ae5c83e964282fea1d6ad44aa333ee1850`. Open and unmerged; no full-suite, review, or acceptance is claimed. |
| Competition-fork package | [Authorized personal-fork review target](https://github.com/eason4kim-rocket/Radeon-hackathon-2026-07/tree/submission/track3-liu-liang-look-twice-v8/submissions/Track3-Liu-Liang-Look-Twice) at `4489022`: 154 manifest entries, 155/155 verified checksum entries, and 156 total files; checksum-index SHA256 `439e0bc71b82317cdf873a1741ff6da7c1e55e3f27bd3ee2585cae6373dc949d`. The official competition PR is not open. |
| Frozen evidence | [V8 archive](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release/release/v8-frozen) · [import manifest](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/V8_FROZEN_IMPORT_MANIFEST.json) |
| Task-utility derivation | [JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/V8_TASK_UTILITY_DERIVATION.json) |
| ROCm model-forward benchmark | [JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json) |
| Sustained ROCm telemetry | [raw 60-second JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json) |
| Locked input evidence | [972 MiB archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz) · [manifest](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json) · [boundary note](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_LOCKED_INPUT_EVIDENCE.md) |
| Frozen checkpoint | [159 MB release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt) |
| Demo video | [3:59 English MP4 - stable release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4) |
| Short evidence reel | [30-second preview](https://eason4kim-rocket.github.io/media/look-twice-replay-30s.mp4) |

Published and anonymously verified final demo identity: 239.000 seconds,
9,032,035 bytes, MP4
SHA256
`70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`;
sidecar SHA256
`639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb`.
The narration is AI-generated with OpenAI `gpt-4o-mini-tts`, voice `cedar`.
The closing card burns in
`AI-GENERATED NARRATION · OPENAI TEXT-TO-SPEECH`, and the sidecar records the
provider, model, voice, and hash-pinned narration provenance. Evidence slides
use a fixed composition with `zoompan` removed.

## Reproduction

CPU-only audit:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
python3 scripts/derive_v8_task_utility.py
```

Independent challenge audit after extracting the release archive:

```bash
python3 scripts/verify_v8_frozen_challenge.py \
  --results-dir v8-frozen-challenge-102500-102529 \
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \
  --repo-root . \
  --output v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
```

Optional no-inference locked-input audit after downloading the archive and its
sidecar:

```bash
python3 scripts/verify_v8_locked_input_pack.py \
  --archive /path/to/locked.tar.gz --sidecar /path/to/locked.sidecar.json \
  --check-only
```

Dual-body report and recovery-chain audit, also without a GPU:

```bash
cd release/v8-derived/dual_body_dynamics_160820_160839
shasum -a 256 -c SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

Decision-bound dynamics V2 package and report audit, also without a GPU:

```bash
cd release/v8-derived/decision_dynamics_recovery_v2_102500_102529
shasum -a 256 -c SHA256SUMS
shasum -a 256 -c PACKAGE_SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json
```

Solver-scale two-shard audit, also without a GPU and without stitching the
reports:

```bash
P60=release/v8-derived/decision_dynamics_single_scene_60_102500_102519
S30=release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529
(cd "$P60" && shasum -a 256 -c SHA256SUMS && \
  shasum -a 256 -c PACKAGE_SHA256SUMS)
(cd "$S30" && shasum -a 256 -c SHA256SUMS && \
  shasum -a 256 -c PACKAGE_SHA256SUMS)
python3 scripts/verify_v8_additive_decision_dynamics_60.py "$P60/REPORT.json"
python3 scripts/verify_v8_additive_decision_dynamics_30_suffix.py \
  "$S30/REPORT.json"
```

Local Evidence Console:

```bash
docker compose up --build
```

Purify Go reference core:

```bash
cd purify_robotics
go test ./...
```

Detailed instructions, the GPU runtime command, expected outputs, and artifact
hashes are in the
[V8 reproduction guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_REPRODUCTION.md).

## Honest boundary

- Simulation only; no real-robot, sim-to-real, or safety-certification claim.
- The public replay is a non-locked confirmatory example, not the locked
  aggregate.
- The locked-input supplement is input-only; original per-sample predictions
  and 24 raw full-chain episodes are unavailable and were not regenerated.
- Seeds 102500-102529 were used once for the frozen challenge; seeds
  102530-102549 were separately evaluated once per policy for the compound
  challenge. Both are same-generator, non-locked supplements, not V8 OOD
  evidence. Seeds 102550-102699 remain unevaluated.
- The public evidence path uses a kinematic Genesis motion backend.
- Carrier and scout in the frozen policy are logical-role poses on one shared
  Genesis chassis. A separate additive 20-seed supplement validates bounded
  sequential wheel motion by two non-fixed rigid bodies, but it is not a
  full-policy rerun, simultaneous cooperative control, or two physical devices.
- The additive decision-bound recovery V2 replays archived decisions across 30
  independent three-body scenes. Its 90 distinct bodies are not one
  simultaneous 90-body scene, and its 30/30 execution result does not replace
  the preregistered active 29/30 full-chain endpoint.
- The solver-scale complement replays the same archived decisions in exactly
  two separate, non-resumable, fixed-order serial scenes: a 20/20 60-body
  prefix and a 10/10 30-body suffix. It contains 90 cumulative distinct robots,
  but maximum co-resident is 60 and the 90 robots were never all co-resident.
  It is not a live perception-policy rerun, simultaneous cooperative fleet
  control, completion of the failed V1 all-90-body attempt, or a replacement
  for the primary 29/30 endpoint.
- The V2 attempt ledger and logs show no retry or replacement, but the original
  formal checksum set did not bind those files and the original source manifest
  omitted one direct runtime dependency. The post-run review is corroborating
  evidence, not cryptographic proof of no retry or complete dependency binding.
- The 159 MB checkpoint is published as a release asset and must match SHA256
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`.
- Later Integrity Shield R1/R2 and V9 research is not promoted into V8.
- The focused Genesis parser fix is public as issue #3183 and open PR #3184.
  It remains unmerged; no maintainer review, acceptance, or released upstream
  behavior is claimed.

## Team

**Liu Liang - solo entrant.** GitHub:
[@eason4kim-rocket](https://github.com/eason4kim-rocket)

Project conception, simulation and robot loop, dataset protocol, V8 perception
model, conformal calibration, Purify Go reference core, experiment execution,
evidence integrity, website, documentation, and submission packaging.
