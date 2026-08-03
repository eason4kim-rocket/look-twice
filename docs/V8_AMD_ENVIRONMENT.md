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

## Challenge-range terminology

The historical `ood_test` label for seeds 102500-102699 refers only to a
reserved challenge range from the same generator family. V8 did not evaluate
that range, and neither the latency benchmark nor the telemetry run changes
that boundary. No OOD or out-of-distribution generalization result is claimed.
