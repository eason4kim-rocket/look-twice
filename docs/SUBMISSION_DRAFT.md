# Track 3, Liu Liang, Look Twice

> **Owner-review preparation state - not yet filed:** the final 239-second
> video and the existing V8 review targets are public and anonymously verified.
> The additive dynamics evidence, new 30/30 decision-bound recovery V2 packet,
> refreshed report/site/official package, and Genesis upstream fix are prepared
> locally for owner review. No competition or external upstream PR is open.

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

The site replays recorded Genesis plus AMD GPU evidence. It does not create new
benchmark samples and does not require a live GPU.

## 90-second judge path

1. Open the one-page [V8 Frozen Challenge Judge Card](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md).
2. Confirm the public Commit A/Commit B timestamps, 30-pair endpoint, raw
   archive, and independent verification SHA.
3. Open the Evidence Console and watch the initial denial, BeliefGap, and
   independent side-view capture.
4. Confirm that direct motion requires Python admission and Purify Go
   admission.
5. Switch to passive mode and compare its safe detour.
6. Inspect the challenge's 844-sample full-wall ROCm telemetry and 30-world
   carrier/scout burden table.
7. Open Results and inspect the separate 30/30 decision-bound rigid-dynamics
   card, then the earlier 20/20 dual-body acceptance card.
8. Confirm that 30/30 is an archived-decision execution supplement and that
   the preregistered primary endpoint remains active 29/30 versus passive 0/30.
9. Follow the permanent locked metrics separately.

## Official Track 3 judging map

| Criterion | Evidence in this submission |
| --- | --- |
| Robot capability performance - 30 | Permanent locked evidence: active 11/12 direct versus passive 0/12. Publicly preregistered supplement: active 29/30 full-chain direct versus passive 0/30 (+96.7 pp, exact McNemar `p=3.73e-9`), 60/60 missions, 0/60 unsafe, 0/60 fallback. Separate additive decision-bound dynamics: 30/30 independent three-body scenes, all 90 distinct robot instantiations reached, 20.8183% paired loaded-carrier path reduction, and zero blocker/active-pair contact rows. This does not replace the 29/30 endpoint. |
| AMD Radeon GPU and ROCm adoption - 20 | Genesis 1.1.2 on `gs.amdgpu`, live RGB-D, tensor preprocessing, and the 39.8M-parameter model on PyTorch ROCm/HIP 7.2. The challenge retains 844 `rocm-smi` samples across its complete 1,685.5-second wall; the separate 20/20 and 30/30 wheel-dynamics runs retain reports, disclosed source bindings, and local verifiers. |
| Innovation and originality - 20 | Action-scoped spatial perception, physical-root lineage, split-conformal sets, dual Python/Go authorization, BeliefGap-driven repair, and canonical receipts. |
| Real-world application value - 20 | Across 30 warehouse pairs, active scouting reduced loaded-carrier logical path 22.5% while increasing total logical-role path 24.0%, with all missions completed safely. |
| Upstream open-source contribution - 10 | Project code, schemas, Purify Go reference core, validators, replay builder, and evidence site are open source. A focused Genesis URDF inertial-origin fix plus required regression test is prepared locally with baseline-fail/patch-pass evidence; no public external PR is claimed until owner approval. |

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
| Unsafe / fallback | 0 / 0 | 0 / 0 |

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

The Radeon run passed **20/20** fixed seeds with zero trial-blocker contacts,
zero carrier/scout pair contacts, and zero post-build pose writes. Maximum
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

## Deliverables

| Requirement | Location |
| --- | --- |
| One-page challenge Judge Card | [public preregistration, result, AMD telemetry, application burden, and verifier](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md) |
| Challenge machine evidence | [report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json) · [post-hoc feasibility audit](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json) · [verification](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/challenge_102500_102529/VERIFICATION.json) · [3.19 MB raw archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz) |
| Dual-body dynamics evidence | [20-seed result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md) · [machine report](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json) · timeout/recovery audits and `SHA256SUMS` in the same directory |
| Decision-bound dynamics V2 | [30-seed result note](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md) · [complete evidence directory](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release/release/v8-derived/decision_dynamics_recovery_v2_102500_102529) · formal and package checksum indexes, provenance review, and local verifier |
| Technical report | [release PDF](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf) · [source](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_TECHNICAL_REPORT.md) |
| Project source code | [dedicated V8 branch](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release) |
| Reproducibility README | [root judge path](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/README.md) · [detailed guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_REPRODUCTION.md) |
| Docker path | [Dockerfile](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/Dockerfile) · [Compose](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docker-compose.yml) |
| Public evidence site | [Evidence Console](https://eason4kim-rocket.github.io/) · [Results](https://eason4kim-rocket.github.io/results) · [Reproduce](https://eason4kim-rocket.github.io/reproduce) |
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
- Seeds 102500-102529 were used once for the public preregistered same-generator
  supplement; seeds 102530-102699 remain unevaluated. Neither is V8 OOD
  evidence.
- The public evidence path uses a kinematic Genesis motion backend.
- Carrier and scout in the frozen policy are logical-role poses on one shared
  Genesis chassis. A separate additive 20-seed supplement validates bounded
  sequential wheel motion by two non-fixed rigid bodies, but it is not a
  full-policy rerun, simultaneous cooperative control, or two physical devices.
- The additive decision-bound recovery V2 replays archived decisions across 30
  independent three-body scenes. Its 90 distinct bodies are not one
  simultaneous 90-body scene, and its 30/30 execution result does not replace
  the preregistered active 29/30 full-chain endpoint.
- The V2 attempt ledger and logs show no retry or replacement, but the original
  formal checksum set did not bind those files and the original source manifest
  omitted one direct runtime dependency. The post-run review is corroborating
  evidence, not cryptographic proof of no retry or complete dependency binding.
- The 159 MB checkpoint is published as a release asset and must match SHA256
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`.
- Later Integrity Shield R1/R2 and V9 research is not promoted into V8.
- A focused Genesis parser fix and regression test are ready locally. No
  public external upstream contribution is claimed until owner approval.

## Team

**Liu Liang - solo entrant.** GitHub:
[@eason4kim-rocket](https://github.com/eason4kim-rocket)

Project conception, simulation and robot loop, dataset protocol, V8 perception
model, conformal calibration, Purify Go reference core, experiment execution,
evidence integrity, website, documentation, and submission packaging.
