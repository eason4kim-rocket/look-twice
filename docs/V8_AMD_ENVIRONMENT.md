# V8 AMD Radeon and ROCm Environment

This record separates the environment captured with the frozen V8 result from
a read-only availability check performed during submission preparation.

## Frozen evaluation environment

Source: `release/v8-frozen/results/V8_IDENTITY_FREEZE_MANIFEST.json` and the
archived V8 episode environment blocks.

| Component | Value |
| --- | --- |
| Platform | Linux 6.8.0-79, x86_64, glibc 2.39 |
| Python | 3.12.3 |
| PyTorch | 2.9.1+gitff65f5b |
| HIP / ROCm | 7.2.53211-e1a6bc5663 |
| GPU name reported to PyTorch | AMD Radeon Graphics |
| GPU ISA | gfx1100 |
| Genesis | 1.1.2 |
| Genesis backend | `gs.amdgpu` |
| PyTorch device | `cuda:0` |

PyTorch retains the `cuda` device namespace for its ROCm backend; `cuda:0` in
these reports means the Radeon/HIP device, not an NVIDIA GPU.

## Submission-preparation availability check

A read-only check on 2026-08-03 confirmed the same Radeon Cloud host class:

- `gfx1100` Radeon device;
- 51,522,830,336 bytes of VRAM (approximately 48 GiB);
- PyTorch 2.9.1 ROCm build;
- HIP 7.2.53211-e1a6bc5663;
- Genesis 1.1.2.

Unique hardware identifiers, hostnames, SSH details, and local paths are not
published as competition evidence.

## GPU workload boundary

The Radeon GPU executes:

- Genesis physics/simulation stepping through `gs.amdgpu`;
- RGB, depth, and segmentation-proxy rendering;
- RGB-D tensor preprocessing;
- the V8 spatially grounded segmentation and traversability model;
- candidate observation evaluation used by the closed loop.

The CPU executes:

- the standalone Purify Go action-contract gate;
- canonical receipt hashing;
- replay packaging and the public evidence website.

The public website is intentionally CPU-only because it replays recorded AMD
GPU evidence. This design lets judges inspect the exact evidence chain without
requiring access to the competition cloud instance.

## Identity evidence

| Artifact | SHA256 |
| --- | --- |
| Vision checkpoint | `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783` |
| Vision conformal identity | `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f` |
| Go fusion conformal identity | `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97` |
| Purify Go binary | `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00` |
| Locked report file | `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb` |
| Frozen ROCm telemetry | `0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9` |
| Challenge report | `59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0` |
| Challenge full-wall telemetry | `463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0` |
| Challenge independent verification | `942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940` |
| Decision-dynamics recovery V2 report | `1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99` |
| Decision-dynamics recovery V2 source binding | `c40f6ba74a39ad761e4926ddb66326f33a1a645fef3c96364f9c53b9d5d3eb5d` |

Public checkpoint asset:
https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt

Before a new GPU reproduction, run:

```bash
/opt/venv/bin/python -m pip install -r requirements-rocm-v8.txt
/opt/venv/bin/python scripts/verify_v8_rocm_environment.py
```

The preflight checks Genesis, PyTorch, HIP, the ROCm device API, and the
`gfx1100` architecture against the frozen core. The competition image's
ABI-matched `torchvision` package must be retained.

## Frozen-model inference benchmark

Source: `release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json`.
Report SHA256:
`282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156`.

The benchmark verifies the checkpoint SHA before loading it, uses FP32 tensors
already resident on the Radeon GPU, performs 20 warm-up iterations, and then
records 100 synchronized model forwards for each batch size.

| Batch | p50 | p95 | Throughput | Peak allocated |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 192.31 ms | 199.18 ms | 5.18 images/s | 313.63 MiB |
| 4 | 659.08 ms | 667.85 ms | 6.06 images/s | 465.38 MiB |
| 8 | 1,279.72 ms | 1,288.29 ms | 6.25 images/s | 668.38 MiB |

The benchmark covers only the frozen V8 vision model forward pass plus Python
dispatch and synchronized ROCm execution. It excludes RGB-D preprocessing,
Genesis simulation, Go evidence fusion, storage/network I/O, and closed-loop
actuation. It is not an accuracy evaluation. This latency report does not by
itself support a GPU-utilization claim, and no performance value is inferred
from V4-V7.

## 60-second frozen ROCm telemetry

Source: `release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json`.
Report SHA256:
`0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9`.

This separate submission-time run verified the exact frozen checkpoint before
loading it. A clean-GPU preflight found no KFD compute processes and recorded
0% GPU use and 0% VRAM allocation before model load. The measured workload was
a sustained **synthetic, preloaded-tensor, FP32 model-forward benchmark** at
batch 8 and 256 x 256 input resolution. It used 20 warm-up iterations,
synchronized after every forward, and sampled `rocm-smi` once per second.

| Measure | Recorded value |
| --- | ---: |
| Measured interval | 60.182 seconds |
| Measured forwards | 47 |
| Images forwarded | 376 |
| Throughput | 6.2477 images/s |
| GPU-use samples | 61/61 at 100% |
| Mean graphics-package power | 135.33 W |
| p95 graphics-package power | 156 W |

The 61/61 result supports a utilization claim only for this controlled frozen
model-forward workload. It is not end-to-end robot throughput or latency: it
excludes RGB-D preprocessing, Genesis simulation and rendering, Go evidence
fusion, I/O, and actuation. It is not an accuracy evaluation, did not access
or open the locked split, and did not modify model weights, calibration, or
thresholds.

## Preregistered challenge full-wall telemetry

Source:
`release/v8-frozen/results/challenge_102500_102529/ROCM_TELEMETRY.json`.
Report SHA256:
`463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0`.

This is a distinct full-pipeline execution record for the additive
same-generator non-locked challenge. It samples the entire challenge
subprocess wall at a fixed two-second interval and retains idle samples rather
than selecting model-forward-only windows.

| Measure | Recorded value |
| --- | ---: |
| Challenge subprocess wall | 1,685.504 seconds |
| Episode subprocesses | 60/60 |
| ROCm samples | 844 |
| GPU use mean / median / p95 / max | 19.4 / 0 / 95 / 100% |
| VRAM allocation p95 / max | 2 / 2% |
| Graphics-package power mean / p95 / max | 35.7 / 81 / 109 W |
| Samples at or above 1% GPU use | 228/844 (27.0%) |

All 60 episodes used Genesis live RGB-D, loaded the frozen checkpoint, and
produced Purify Go receipts. The denominator includes complete Python +
Genesis + checkpoint + episode subprocess execution, not only inference. It
is not control-loop latency, mission energy, physical duty cycle, rigid-body
contact validation, or a real-robot benchmark. Carrier and scout are logical
roles on one shared Genesis chassis, not simultaneous dual-body dynamics.

## Decision-bound rigid-dynamics recovery V2

Source:
`release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json`.
Report SHA256:
`1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`.

This separate submission-time run used Python 3.12.3, Genesis 1.1.2,
PyTorch `2.9.1+gitff65f5b`, HIP `7.2.53211-e1a6bc5663`, and the requested
`amdgpu` backend. All worker environment records were identical. One AMD GPU
executed the fixed seeds serially, with one fresh Genesis subprocess and one
independent three-body scene per seed. Each scene contained an active
non-fixed scout, an active non-fixed loaded carrier, and a passive non-fixed
loaded carrier. Thus the run instantiated 90 distinct non-fixed bodies across
30 scenes, never 90 bodies in one simultaneous scene.

The run consumed, rather than recomputed, the archived 29 direct decisions and
one dual-blocked safe-detour decision. It passed 30/30: all 90 bodies reached,
the 29/29 direct carrier pairs each retained at least 0.50 m of physical-path
saving, and mean active loaded-carrier path was 20.8183% below the paired
passive path. Counted blocker-contact and active carrier/scout contact rows
were both zero. The only post-build actuation was wheel-DOF velocity control;
script-level entity pose writes after build were zero.

This is AMD rigid-dynamics execution evidence, not a live rerun of the frozen
perception-policy loop. It is additive, non-locked, and declares
`formal_result_eligible=false`; the frozen challenge primary remains 29/30.
It is not simultaneous cooperative motion, dynamic-obstacle, real-robot,
sim-to-real, energy, latency, throughput, or safety-certification evidence.
The V2 directory contains no dedicated utilization or power telemetry, so no
ROCm utilization or performance claim is inferred from its successful run.

The formal source binding covers the listed V2 sources and clean commit
`b0c4f0d`, but omits the directly imported `src/v4_motion.py`; a post-run audit
matched that file to the commit, which is corroboration rather than an
expanded formal binding. The original inner `SHA256SUMS` covers the source
binding, 30 trial checkpoints, and report, but not the attempt ledger,
progress file, or worker logs. Those retained records show 30 first-attempt
workers with zero exit codes and no observed retry or replacement, but that
observation is not a cryptographic proof over unsealed attempts.

## Challenge-range terminology

The historical `ood_test` label for seeds 102500-102699 refers only to a
reserved challenge range from the same generator family. Seeds 102500-102529
were evaluated exactly once per policy in the publicly preregistered,
same-generator non-locked supplement. Seeds 102530-102549 were separately
evaluated once per policy cell in the public-before-run compound
contract-progress challenge; seeds 102550-102699 remain unevaluated. Neither
telemetry class changes that boundary. No OOD, out-of-distribution, or
population-generalization result is claimed.
