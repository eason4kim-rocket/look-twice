# V8 additive same-host CPU/GPU comparison result

- **Status:** passed
- **Formal run:** 2026-08-06, 10:13:12–10:25:57 UTC
- **Source fixed before the run:** `a7dd1178ea551cea346a734d3ffedd448d6b732d`

## Result

For the frozen 39.8M-parameter FP32 vision model, synchronized Radeon model
forwards were **1.76–2.04× faster** than the 64-thread CPU path on the same
Radeon Cloud host.

| Batch | CPU mean latency | Radeon mean latency | CPU throughput | Radeon throughput | Radeon speedup |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 393.90 ms | 193.53 ms | 2.54 images/s | 5.17 images/s | **2.04×** |
| 4 | 1,158.12 ms | 659.90 ms | 3.45 images/s | 6.06 images/s | **1.76×** |
| 8 | 2,533.74 ms | 1,285.37 ms | 3.16 images/s | 6.22 images/s | **1.97×** |

All output tensors matched at the declared `rtol=1e-3`, `atol=1e-4`
tolerance for all three batch sizes. The largest recorded absolute difference
was `0.000152587890625`.

## What was held fixed

- Exact checkpoint SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Runtime: PyTorch `2.9.1+gitff65f5b`, HIP
  `7.2.53211-e1a6bc5663`, FP32
- CPU: two AMD EPYC 9334 processors, 128 logical CPUs visible, PyTorch
  intra-op threads fixed at 64
- GPU: Radeon `gfx1100`, accessed through the PyTorch ROCm `cuda:0` API
- Inputs: the same deterministic, preloaded tensors at 256×256
- Measurements: 20 warm-ups followed by 100 synchronized forwards for each
  device and batch size

The protocol was committed before the formal run. It disclosed the earlier
feasibility probe and set no minimum speedup threshold, so the completed result
would have been published even if Radeon had been slower.

## Boundary

This is an additive compute comparison, not a new primary challenge result. It
measures the frozen model forward plus Python dispatch. It excludes Genesis
simulation and rendering, RGB-D preprocessing, Purify Go, storage and network
I/O, and closed-loop robot actuation. It is therefore **not** an end-to-end
robot-latency, mission-time, energy, physical-robot, or sim-to-real claim.

## Evidence

- [Precommitted protocol](V8_ADDITIVE_CPU_GPU_COMPARISON_PROTOCOL.md)
- [Formal JSON report](../release/v8-derived/frozen_cpu_gpu_comparison_a7dd117/REPORT.json)
- [Unfiltered execution log](../release/v8-derived/frozen_cpu_gpu_comparison_a7dd117/FORMAL.log)
- [Runner exit record](../release/v8-derived/frozen_cpu_gpu_comparison_a7dd117/FORMAL.status)
- [Portable SHA256 manifest](../release/v8-derived/frozen_cpu_gpu_comparison_a7dd117/SHA256SUMS)
- [Formal runner](../scripts/benchmark_v8_frozen_cpu_gpu.py)
