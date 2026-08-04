# Look Twice V8: Active Evidence Assurance for Physical AI

[![CPU contract tests](https://github.com/eason4kim-rocket/look-twice/actions/workflows/ci.yml/badge.svg?branch=v8-competition-release)](https://github.com/eason4kim-rocket/look-twice/actions/workflows/ci.yml?query=branch%3Av8-competition-release)

Look Twice is a pre-action evidence-assurance layer for embodied AI, not
another perception leaderboard. It asks not only what the model predicts, but
whether the evidence is independent, fresh, calibrated, and sufficient for the
intended action. When it is not, the robot acquires the missing view,
re-qualifies the same Action Contract, and either recovers useful motion or
fails closed.

```text
Genesis RGB-D observations
-> spatially grounded, lineage-aware Claims
-> split-conformal prediction sets
-> scoped Action Contract
-> Python AND Purify Go authorization
-> active evidence repair, safe detour, or fail closed
```

This is the frozen V8 competition candidate for Track 3 of the AMD AI
DevMaster Hackathon. It is a simulation research prototype, not a real-robot
deployment or a certified safety controller.

## 90-second judge path

1. Read the one-page [V8 Frozen Challenge Judge Card](docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md):
   public preregistration, 30 paired worlds, AMD full-wall telemetry, application
   burden, raw archive, and one-command verification.
2. Open the public [Evidence Console](https://eason4kim-rocket.github.io/) and
   play the active replay: initial denial -> independent side-view capture ->
   Python and Purify admission -> direct route.
3. Compare the passive replay: the same initial denial produces a safe detour.
4. Inspect the [frozen results](https://eason4kim-rocket.github.io/results/)
   and open the linked source JSON, including the separate 30/30
   decision-bound wheel-dynamics replay and the earlier 20/20 dual-body bar.
5. Use the CPU-only audit below to verify the replay bundles and frozen SHA
   boundary locally.

## Frozen V8 result

The candidate was opened once on the isolated locked split. No retuning,
refitting, or vision retraining followed the open.

| Evaluation | Result |
| --- | ---: |
| Locked offline population | 3,200 samples from seeds 102100-102499 |
| Corridor ROI IoU | 1.000 |
| Decisive balanced accuracy | 1.000 |
| Decisive blocked recall | 1.000 |
| False-clear singleton rate | 0.000 |
| Split-conformal coverage | 1.000 |
| Decisive predictions | 3,001 / 3,200 |
| Active full-chain direct actions | 11 / 12 |
| Passive full-chain direct actions | 0 / 12 |
| Paired direct-route gain | +91.7 percentage points |
| Mission completion | 12 / 12 active; 12 / 12 passive |
| Passive initial denials | 12 / 12 |
| Passive safe detours | 12 / 12 |
| Unsafe crossings | 0 / 24 policy runs |
| Unplanned fallback | 0 / 24 policy runs |
| Python / Purify Go decision agreement | 24 / 24 policy runs |

Authoritative source:
[`LOCKED_TEST_REPORT.json`](release/v8-frozen/results/LOCKED_TEST_REPORT.json).
The archived report SHA256 is
`5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb`.

The direct-route gain is a derivation from the permanent paired rows; V8 was
not rerun and the locked split was not reopened. The public replay is a
recorded non-locked confirmatory episode. It illustrates the evaluated
mechanism but is not substituted for the locked population.

### Preregistered frozen challenge supplement

After the locked result was permanent, a public two-commit preregistration
fixed the runner, validator, identities, seeds `102500-102529`, policy order,
full-chain endpoint, telemetry, and no-retry rule before any challenge episode.
All 60 episodes completed on Genesis live RGB-D and AMD ROCm and passed the
independent validator:

| Same-generator challenge endpoint | Active | Passive |
| --- | ---: | ---: |
| Full-chain direct | 29 / 30 (96.7%) | 0 / 30 (0.0%) |
| Wilson 95% interval | 83.3-99.4% | 0.0-11.4% |
| Mission success | 30 / 30 | 30 / 30 |
| Unsafe episode | 0 / 30 | 0 / 30 |
| Fallback | 0 / 30 | 0 / 30 |

The paired difference is **+96.7 percentage points** with exact two-sided
McNemar `p = 3.73e-9`. Full-chain direct requires mission success, direct
motion without detour, and Python + Purify Go + effective authorization for the
corridor actually executed. The sole active non-direct world remained safe and
completed by detour.

The preregistered primary endpoint remains **active 29/30 versus passive
0/30** (`p = 3.73e-9`). A separate
[post-hoc descriptive offline oracle-feasibility audit](release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json)
found that all **29/29** worlds with at least one oracle-clear corridor went
direct and selected an oracle-clear corridor. In the only exception, seed
`102515`, both corridors were oracle-blocked and the policy completed the
mission by safe detour. Thus **30/30 active route outcomes matched offline
feasibility**. Oracle labels were never available to the controller, and this
audit is not a preregistered endpoint. Across these 30 active records, unsafe
was false, collision count was zero, and fallback was false.

Receipt-level Python/Purify Go agreement was **250/268 (93.3%)**. All 18
differences were Python-admit/Go-deny and remained fail-closed with
`effective_admit=false`; no selected crossing relied on a disagreement.

This is an additive **same-generator non-locked** challenge, not a second
locked open, OOD result, rigid-body test, or physical-robot claim. See the
[Judge Card](docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md),
[machine report](release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json),
and [3.19 MB raw archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz).

### Additive locked-input evidence

The original pre-open locked input-and-label archive is now available as a
[972 MiB release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz).
Its SHA256 is
`0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba`.
The streaming verifier checks all 400 worlds, 3,200 metadata records, 22,800
file members, labels, seeds, paths, sidecar chronology, and permanent-result
hashes without extracting arrays or running inference. See the
[evidence note](docs/V8_LOCKED_INPUT_EVIDENCE.md) and
[manifest](release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json).

This is an input-only supplement. The preserved archive does not contain the
original 3,200 one-shot prediction rows or the 24 raw full-chain episodes, so
it cannot reconstruct or recompute the permanent aggregate. Those files were
not regenerated, and the locked split was not reopened.

## Task value: recover direct motion, shift carrier burden

Safe refusal is the baseline. In the 12 paired locked worlds, the passive
policy took a safe detour in 12/12, while active evidence repair converted the
same initial denial into a jointly authorized direct route in 11/12 - a +91.7
percentage-point gain with zero recorded unsafe crossings or fallbacks across
all 24 policy runs. Seed 102105 remained conservative and stays in the
denominator.

The 30-world preregistered challenge now provides the aggregate logical-role
cost ledger. Active repair reduced mean loaded-carrier path from 6.404 to 4.961
(-1.443, **-22.5%**). This was not free: mean scout path was 2.980 and total
logical-role team path rose from 6.404 to 7.941 (+1.538, **+24.0%**). The value
claim is burden shifting from a loaded carrier to diagnostic scouting, not
lower total motion, energy, or latency. Carrier and scout are separate logical
poses and capture roots on one shared Genesis chassis, not two physical robots
or simultaneous dual-body dynamics.

The older guarded non-locked seed 105400 replay remains the visual example; it
is not substituted for either the permanent locked aggregate or the new
preregistered 30-world supplement.

Challenge source: [validated 30-world report](release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json).
The older replay ledger remains in the
[task-utility derivation](release/v8-derived/V8_TASK_UTILITY_DERIVATION.json),
SHA256 `f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b`.

## Separate additive dual-body rigid dynamics

A predeclared submission-time supplement tests a narrower implementation
boundary without changing the frozen V8 endpoint. Across fixed seeds
`160820-160839`, one Genesis scene instantiated **40 distinct non-fixed robot
entities**: one loaded carrier and one scout per seed. The scout moved first
while its carrier stayed parked; the carrier then followed the clear corridor
while its scout stayed parked. The only post-build actuation API was wheel-DOF
`control_dofs_velocity`.

The complete Radeon/ROCm run passed **20/20** seeds with zero trial-blocker
contact rows, zero carrier/scout pair-contact rows, and zero script pose writes
after `scene.build()`. Maximum body tilt was 10.750 degrees and maximum parked
partner drift was 0.018061 m. Mean paths were 1.645 m for the scout and 4.760 m
for the carrier. The report passed the same verifier on the Radeon host and
locally and hashes to
`8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110`.

The first whole-process attempt hit an external 3,600-second watchdog before
writing a report or exposing any seed result. Recovery changed only that
watchdog to 10,800 seconds; commit, code and URDF bytes, fixed seeds, protocol,
and thresholds remained identical. Both attempts are retained in the sealed
directory. See the [result note](docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md),
[fixed protocol](docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_PROTOCOL.md), and
[machine report](release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json).

This is additive, non-locked evidence with `formal_result_eligible=false`. It
shows bounded wheel-actuated motion by two separate rigid bodies; it is not a
rerun of the frozen active/passive policy, simultaneous cooperative-policy
control, physical-robot validation, or sim-to-real evidence.

## Separate additive decision-bound dynamics replay

A second protocol closes the narrower decision-to-actuation gap without
changing the frozen endpoint. It consumes the immutable archived outcomes for
seeds `102500-102529` - 29 direct decisions and the one dual-blocked safe
detour - and replays each fixed decision in a fresh paired Genesis scene. Each
scene contains one active non-fixed scout, one active non-fixed loaded carrier,
and one passive non-fixed loaded carrier. Across 30 independent scenes this is
**90 distinct non-fixed robot instantiations**, not one simultaneous 90-body
scene.

The Radeon/ROCm run passed **30/30** fixed trials. All 90/90 bodies received
wheel commands and reached their goals; all 29 direct pairs saved at least
0.50 m of loaded-carrier path; the paired mean fell from 6.2433 m passive to
4.9435 m active (**20.8183%**); and seed `102515` executed its declared safe
outer detour. Recorded blocker-contact and active carrier/scout contact rows
were both zero, maximum tilt was 10.5796 degrees, maximum parked-partner drift
was 0.022329 m, and no script-level entity pose write occurred after build.

V1's all-90-body scene reached four-hour and 12-hour watchdogs before its
single final report write. V2 preserved the fixed seeds, archived decisions,
per-trial geometry, wheel controller, and acceptance bars while changing the
execution and persistence topology: one fixed seed per fresh subprocess, an
exclusive-published atomic checkpoint after every seed, fixed-order resume from
a verified checkpoint prefix, and no result-conditioned replacement. The complete V2 run then finished on
its first attempt with 30 sealed checkpoints and exit code zero. The failed V1
history remains visible and is not relabeled as a V2 result.

The byte-identical report passed the frozen verifier on the Radeon host and
locally and hashes to
`1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`.
A [post-run provenance review](release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json)
also discloses two proof-scope limits: the original formal checksum index did
not cover the attempt/progress/log files, and the source manifest omitted the
directly imported `src/v4_motion.py`. The retained ledger shows no retry or
replacement, and a clean 2,419-file post-run tree audit found no source
difference; these are stated as observed evidence, not upgraded into a
cryptographic guarantee.

See the [result note](docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md),
[fixed V2 protocol](docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROTOCOL.md),
and [machine report](release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json).
This is additive, non-locked, archived-decision simulation evidence with
`formal_result_eligible=false`. It is not a live perception-policy rerun,
simultaneous cooperative control, dynamic-obstacle response, real-robot or
sim-to-real validation, throughput, energy, or safety-certification evidence.

## What is novel

- **Evidence lineage, not sensor counting.** RGB and depth from one capture
  remain one measurement root; copied Claims do not create independence.
- **Action-scoped qualification.** Evidence is checked for a specific robot,
  corridor, action, time window, calibration identity, and root set.
- **Active repair instead of permanent refusal.** A denied contract emits a
  finite BeliefGap that selects a diagnostic side-view observation.
- **Dual authorization.** Direct motion requires both the Python policy path
  and the standalone Go reference core to admit the same action.
- **Auditable decisions.** Claims, prediction sets, GateReceipts, plan
  invalidations, artifact identities, and source episode hashes are retained.

## AMD Radeon and ROCm

The frozen evaluation ran on one Radeon Cloud `gfx1100` GPU through the ROCm
stack. The captured environment contains:

| Component | Frozen environment |
| --- | --- |
| GPU | AMD Radeon GPU, `gfx1100`, 48 GiB VRAM |
| Simulation | Genesis 1.1.2, `gs.amdgpu` |
| ML runtime | PyTorch 2.9.1 ROCm build |
| HIP runtime | 7.2.53211-e1a6bc5663 |
| Python | 3.12.3 |
| Model device | `cuda:0` (PyTorch ROCm device name) |

Genesis simulation, RGB-D rendering, tensor preprocessing, and spatial RGB-D
inference use the Radeon GPU. The deterministic Purify Go contract gate runs on
CPU. See [V8 AMD environment](docs/V8_AMD_ENVIRONMENT.md).

The exact frozen checkpoint also passed a separate FP32, preloaded-tensor
model-forward benchmark on that ROCm device. With 20 warm-up iterations and
100 synchronized measurements per batch, batch 1 measured 192.31 ms p50 and
199.18 ms p95; batch 8 delivered 6.25 images/s with 668.38 MiB peak allocated
memory. These are model-forward numbers, not Genesis or closed-loop latency.
See the
[benchmark JSON](release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json).

A separate 60-second run adds sustained ROCm telemetry for the
same exact checkpoint and batch-8 workload. The clean preflight found 0% GPU
use, 0% VRAM allocation, and no KFD process before model load. During 60.182
seconds of synchronized forwards, all 61 `rocm-smi` samples reported 100% GPU
use; mean graphics-package power was 135.33 W and p95 was 156 W. The run
processed 376 images (6.248 images/s). It still measures only synthetic,
preloaded FP32 model forwards - not accuracy, Genesis, preprocessing, the Go
gate, I/O, actuation, energy per mission, or end-to-end robot latency. See the
[raw telemetry JSON](release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json),
SHA256 `0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9`.

The new frozen challenge adds **full-pipeline** telemetry rather than another
model-forward loop. Across the complete 1,685.5-second wall of all 60 fresh
Genesis subprocesses, 844 two-second `rocm-smi` samples were retained,
including idle: GPU use mean/median/p95/max was 19.4/0/95/100%, VRAM p95/max
was 2/2%, and graphics-package power mean/p95/max was 35.7/81/109 W. All 60
episodes loaded the frozen checkpoint, used live Genesis RGB-D, and emitted
Purify Go receipts; totals were 268 RGB-D observations, 134 vision proposals,
and 268 Go invocations/receipts. These remain kinematic simulation results,
not control-loop latency, energy per mission, or physical actuation evidence.

The dual-body supplement separately ran Genesis 1.1.2 with `gs.amdgpu`,
PyTorch 2.9.1 and HIP 7.2 on the same Radeon class. It uses physics-based
non-fixed URDF bodies and wheel-joint velocity control rather than the frozen
policy's kinematic role poses. Its 4,299.992-second execution is an acceptance
run, not a throughput, energy, or control-loop-latency benchmark.

The decision-bound V2 replay used the same software stack and one fresh
three-body paired scene per fixed seed. It passed 30/30 across 90 distinct
non-fixed instantiations. Its approximately 18-minute wall is retained only as
an execution-audit fact; no throughput or latency comparison is derived from
it.

## Reproduce the submitted evidence

### CPU-only evidence audit

Requirements: Python 3.11+.

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
```

This verifies guarded source and artifact hashes, two public EpisodeBundles,
their source episode identities, and the single-use locked report import.

To audit the separately downloaded locked-input release asset without loading
the model or extracting the archive:

```bash
python3 scripts/verify_v8_locked_input_pack.py \
  --archive /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz \
  --sidecar /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.sidecar.json \
  --check-only
```

To reproduce the independent frozen-challenge verification, download and
extract the [raw challenge archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz),
then run:

```bash
python3 scripts/verify_v8_frozen_challenge.py \
  --results-dir v8-frozen-challenge-102500-102529 \
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \
  --repo-root . \
  --output v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
```

The deterministic verification file must hash to
`942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940`.

To verify the separate dual-body report and recovery chain without a GPU:

```bash
cd release/v8-derived/dual_body_dynamics_160820_160839
shasum -a 256 -c SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

To verify the checkpointed 30-seed decision-bound dynamics replay:

```bash
cd release/v8-derived/decision_dynamics_recovery_v2_102500_102529
shasum -a 256 -c SHA256SUMS
shasum -a 256 -c PACKAGE_SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json
```

### Run the evidence console

```bash
docker compose up --build
# open http://localhost:3000
```

The website replays recorded evidence and therefore needs no live AMD GPU,
Genesis process, or private Purify service.

### Test the public Purify reference core

```bash
cd purify_robotics
go test ./...
```

For the complete clean-clone procedure, evidence trace, AMD runtime command,
and checkpoint boundary, see [V8 reproduction](docs/V8_REPRODUCTION.md).

Frozen checkpoint: [download the 159,592,901-byte release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt)
and verify SHA256
`7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`.

## Track 3 judging map

| Criterion | Evidence |
| --- | --- |
| Robot capability performance - 30 | Permanent locked evidence: active 11/12 direct versus passive 0/12. Additive preregistered 30-world supplement: active 29/30 full-chain direct versus passive 0/30 (+96.7 pp, exact McNemar `p=3.73e-9`), 60/60 missions, 0/60 unsafe, 0/60 fallback. Separate non-locked decision-bound dynamics replay: 30/30 fixed scenes, 90/90 wheel-actuated bodies reached, 29/29 direct pairs retained a physical carrier-path advantage, one safe detour, and zero counted blocker/active-pair contact rows. |
| AMD Radeon GPU and ROCm adoption - 20 | Genesis `gs.amdgpu`, RGB-D rendering, spatial RGB-D inference, exact-checkpoint benchmark, 844 samples across the complete 1,685.5-second/60-episode Genesis + checkpoint + Go challenge wall, a 4,299.992-second dual-body component bar, and the separate 30-scene decision-bound rigid-dynamics replay. Dynamics wall times are audit facts, not throughput claims. |
| Innovation and originality - 20 | Lineage-aware Claims, conformal action qualification, dual authorization, BeliefGap-driven active repair, and canonical content-addressed receipts. |
| Real-world application value - 20 | Warehouse AMR burden trade measured over 30 logical-role pairs: active scouting reduced loaded-carrier logical path 22.5% while increasing total logical-role path 24.0%, with all missions completed safely. The separate wheel-dynamics replay retained a 20.82% paired loaded-carrier path reduction across all 30 fixed scenes; neither result is presented as energy or throughput evidence. |
| Upstream open-source contribution - 10 | The project, public schemas, Go reference core, validators, replay builder, and evidence site are open source. A focused Genesis URDF inertial-origin fix and required regression test are prepared locally with baseline-fail/patch-pass evidence; no public external PR is claimed until owner approval. |

## Submission deliverables

- [English V8 technical report](docs/V8_TECHNICAL_REPORT.md)
- [One-page V8 Frozen Challenge Judge Card](docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md)
- [Preregistered 30-world challenge report](release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json)
- [Verified 20-seed dual-body dynamics result](docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md)
- [Verified 30-seed decision-bound dynamics replay](docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md)
- [Independently verified raw challenge archive](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz)
- [Rendered technical report PDF](output/pdf/Look-Twice-V8-Technical-Report.pdf)
- [Detailed reproduction guide](docs/V8_REPRODUCTION.md)
- [Architecture and evidence boundary](docs/V8_EVIDENCE_BOUNDARY.md)
- [Locked-input evidence note](docs/V8_LOCKED_INPUT_EVIDENCE.md)
- [Sustained ROCm telemetry](release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json)
- [English 3-5 minute demo script](docs/V8_DEMO_SCRIPT.md)
- [Final 3:59 English workflow demo](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4)
- [Official PR body draft](docs/SUBMISSION_DRAFT.md)
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md)
- [Public Evidence Console](https://eason4kim-rocket.github.io/)
- [Recorded 30-second evidence reel](showcase/public/media/look-twice-replay-30s.mp4)

## Repository map

- `release/v8-frozen/` - compact frozen V8 evidence import;
- `release/V8_FROZEN_IMPORT_MANIFEST.json` - guarded SHA boundary;
- `src/` - robot loop, RGB-D model, Claims, repair planning, and adapters;
- `purify_robotics/` - standalone Go action-contract reference core;
- `schemas/` - public Robot Claim, Action Contract, and receipt schemas;
- `showcase/` - English-default bilingual Evidence Console;
- `scripts/build_competition_replays.py` - deterministic public replay builder;
- `scripts/benchmark_v8_frozen_inference.py` - hash-pinned ROCm model-forward
  benchmark;
- `scripts/benchmark_v8_frozen_telemetry.py` - clean-preflight 60-second ROCm
  utilization, power, temperature, and throughput evidence;
- `scripts/verify_v8_locked_input_pack.py` - streaming archive and chronology
  verifier that performs no inference or extraction;
- `scripts/derive_v8_task_utility.py` - locked paired-route and guarded replay
  cost derivation without rerunning V8;
- `scripts/verify_v8_rocm_environment.py` - exact ROCm core identity preflight;
- `scripts/run_v8_additive_dual_body_dynamics.py` - fixed-seed, wheel-actuated
  dual-body rigid-dynamics supplement;
- `scripts/verify_v8_additive_dual_body_dynamics.py` - fail-closed report,
  source-identity, AMD-environment, and all-seed verifier;
- `scripts/run_v8_additive_decision_dynamics_recovery_v2.py` - fixed-order,
  per-seed subprocess execution with exclusive-published atomic checkpoints;
- `scripts/verify_v8_additive_decision_dynamics_recovery_v2.py` - recomputes
  the 30 trial assessments, aggregate bar, checkpoint identities, and bound
  source surface;
- `scripts/finalize_v8_submission_package.py` - mechanically inventories all
  official-package payload files, regenerates the top-level checksum index,
  updates the handoff manifest, and provides an idempotent `--check` mode;
- `scripts/verify_frozen_foundation.py` - frozen-boundary verifier.

## Evidence boundary

V8 is the only competition candidate. Later Integrity Shield R1/R2 and V9
experiments do not alter the V8 result and are not promoted into the headline
tables. Seeds 102500-102529 were used exactly once for the publicly
preregistered same-generator supplement; seeds 102530-102699 remain
unevaluated. Neither subset is presented as OOD evidence. Source-recovery
completion is not treated as a calibration pass. See
[V8 evidence boundary](docs/V8_EVIDENCE_BOUNDARY.md).

The 20-seed dual-body rigid-dynamics result is a separate submission-time,
non-locked supplement. It does not overwrite the shared-chassis kinematic
realization used by the frozen V8 policy and does not become a new formal
endpoint.

The 30-seed decision-bound dynamics result is another separate submission-time,
non-locked archived-decision replay. It uses 30 serial independent scenes, not
one simultaneous 90-body scene, and does not become a new formal endpoint.

Apache-2.0. `NOTICE` defines the public Purify reference-core boundary.
