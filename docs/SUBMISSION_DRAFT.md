# Track 3, eason4kim-rocket, Look Twice

> Submission-preparation draft. The official PR must not be opened until the
> final 3-5 minute video, public V8 branch, PDF, and checkpoint mirror have been
> verified from a logged-out browser.

## Project

**Look Twice V8 - Active Evidence Assurance for Physical AI on AMD Radeon GPU**

Look Twice prevents a robot from treating noisy, correlated, stale, or
conflicting observations as action-ready facts. When the evidence is
insufficient, it actively acquires an independent RGB-D observation and asks a
standalone Purify Go gate to qualify the action again.

The target application is warehouse AMR corridor traversal. A carrier may take
the direct route only when a scoped Action Contract is satisfied. Otherwise a
scout acquires a diagnostic side-view observation, the plan is re-evaluated,
and the system either qualifies direct travel, takes a disclosed safe detour,
or fails closed.

## Try it first

Public Evidence Console, no sign-in required:

https://look-twice-evidence-console.eason1319.workers.dev/

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

## Official Track 3 judging map

| Criterion | Evidence in this submission |
| --- | --- |
| Robot capability performance - 30 | End-to-end deny, active observation, re-qualification, direct traversal, and safe detour. Locked active full-chain direct 11/12; passive deny and detour 12/12; unsafe crossing 0/24. |
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
| Corridor ROI IoU | 1.000 |
| Decisive balanced accuracy | 1.000 |
| Decisive blocked recall | 1.000 |
| False-clear singleton rate | 0.000 |
| Split-conformal coverage | 1.000 |
| Active full-chain direct | 11 / 12 |
| Passive deny and safe detour | 12 / 12 |
| Unsafe crossings | 0 / 24 policy runs |
| Unplanned fallback | 0 / 24 policy runs |

Authoritative report:
`release/v8-frozen/results/LOCKED_TEST_REPORT.json`

Report SHA256:
`5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb`

One active locked seed remained conservative and detoured. It remains in the
denominator.

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
`release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json` (SHA256
`282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156`).

## Deliverables

| Requirement | Location |
| --- | --- |
| Technical report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` and source `docs/V8_TECHNICAL_REPORT.md` |
| Project source code | https://github.com/eason4kim-rocket/look-twice |
| Reproducibility README | `README.md` and `docs/V8_REPRODUCTION.md` |
| Docker path | `Dockerfile` and `docker-compose.yml` |
| Public evidence site | https://look-twice-evidence-console.eason1319.workers.dev/ |
| Frozen evidence | `release/v8-frozen/` and `release/V8_FROZEN_IMPORT_MANIFEST.json` |
| ROCm model-forward benchmark | `release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json` |
| Demo video | Final 3-5 minute public URL must be added before opening the PR |
| Short evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` |

## Reproduction

CPU-only audit:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
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
hashes are in `docs/V8_REPRODUCTION.md`.

## Honest boundary

- Simulation only; no real-robot, sim-to-real, or safety-certification claim.
- The public replay is a non-locked confirmatory example, not the locked
  aggregate.
- The public evidence path uses a kinematic Genesis motion backend.
- The 159 MB checkpoint is identified by SHA and requires a public release
  asset or model-hosting mirror before final submission.
- Later Integrity Shield R1/R2 and V9 research is not promoted into V8.
- No external upstream contribution is claimed.

## Team

**eason4kim-rocket - solo entrant**

Project conception, simulation and robot loop, dataset protocol, V8 perception
model, conformal calibration, Purify Go reference core, experiment execution,
evidence integrity, website, documentation, and submission packaging.
