# Track 3, Liu Liang, Look Twice

> **Owner-review preparation state - not yet filed:** the final 239-second
> video, sidecar, report, public site, source branch, and official-fork branch
> are published at stable review targets and were verified without credentials.
> No competition PR is open.

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

1. Open the Evidence Console and play the active replay.
2. Watch the initial contract denial and inspect its BeliefGap.
3. Follow the scout to an independent side-view capture.
4. Confirm that direct motion requires Python admission and Purify Go
   admission.
5. Switch to passive mode and compare its safe detour.
6. Open Results and follow the locked metric links to source JSON.
7. Inspect the separate seed-105400 cost ledger for the operational trade.

## Official Track 3 judging map

| Criterion | Evidence in this submission |
| --- | --- |
| Robot capability performance - 30 | Same-world paired evidence: active 11/12 direct versus passive 0/12 (+91.7 pp); both policies completed 12/12 missions; unsafe crossing and fallback 0/24. |
| AMD Radeon GPU and ROCm adoption - 20 | Genesis 1.1.2 on `gs.amdgpu`, RGB-D rendering, tensor preprocessing, and the 39.8M-parameter spatial RGB-D model on PyTorch ROCm/HIP 7.2. Hash-pinned FP32 model-forward benchmark: batch-1 p50 192.31 ms; batch-8 throughput 6.25 images/s. |
| Innovation and originality - 20 | Action-scoped spatial perception, physical-root lineage, split-conformal sets, dual Python/Go authorization, BeliefGap-driven repair, and canonical receipts. |
| Real-world application value - 20 | An auditable evidence-assurance boundary for warehouse AMRs and other robots operating under correlation, conflict, and partial observability. |
| Upstream open-source contribution - 10 | Project code, schemas, Purify Go reference core, validators, replay builder, and evidence site are open source. No external upstream PR is claimed. |

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

## Task-value cost ledger

On the guarded non-locked confirmatory replay at seed 105400, active repair
reduced loaded-carrier travel from 6.404 m to 4.915 m (-23.24%) while both runs
delivered the payload without a recorded collision. This was a deliberate
trade, not a free speedup: the scout traveled 3.046 m, total robot travel rose
from 6.404 m to 7.961 m, and the active episode took more steps. The evidence
supports a narrower operational claim - shifting motion burden from the loaded
carrier to a scout - not lower total distance or latency.

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

## Deliverables

| Requirement | Location |
| --- | --- |
| Technical report | [release PDF](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf) · [source](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_TECHNICAL_REPORT.md) |
| Project source code | [dedicated V8 branch](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release) |
| Reproducibility README | [root judge path](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/README.md) · [detailed guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docs/V8_REPRODUCTION.md) |
| Docker path | [Dockerfile](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/Dockerfile) · [Compose](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/docker-compose.yml) |
| Public evidence site | [Evidence Console](https://eason4kim-rocket.github.io/) · [Results](https://eason4kim-rocket.github.io/results) · [Reproduce](https://eason4kim-rocket.github.io/reproduce) |
| Frozen evidence | [V8 archive](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release/release/v8-frozen) · [import manifest](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/V8_FROZEN_IMPORT_MANIFEST.json) |
| Task-utility derivation | [JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-derived/V8_TASK_UTILITY_DERIVATION.json) |
| ROCm model-forward benchmark | [JSON](https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-release/release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json) |
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
- The public evidence path uses a kinematic Genesis motion backend.
- The 159 MB checkpoint is published as a release asset and must match SHA256
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`.
- Later Integrity Shield R1/R2 and V9 research is not promoted into V8.
- No external upstream contribution is claimed.

## Team

**Liu Liang - solo entrant.** GitHub:
[@eason4kim-rocket](https://github.com/eason4kim-rocket)

Project conception, simulation and robot loop, dataset protocol, V8 perception
model, conformal calibration, Purify Go reference core, experiment execution,
evidence integrity, website, documentation, and submission packaging.
