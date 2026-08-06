# V8 additive same-host CPU/GPU comparison protocol

**Protocol fixed:** 2026-08-06 10:07:34 UTC, before the formal comparison.

**Run class:** submission-time, additive, non-locked benchmark.

## Question

For the exact frozen V8 spatial RGB-D checkpoint, how does synchronized FP32
model-forward performance compare between the Radeon Cloud host CPU and the
Radeon GPU when both receive the same preloaded tensors?

This comparison is intentionally narrower than the primary Look Twice result.
It measures model forward only. It does not measure Genesis, RGB-D
preprocessing, Purify Go, control-loop latency, mission time, energy, or robot
throughput.

## Disclosed feasibility probe

Before fixing this protocol, one CPU-only feasibility probe loaded the frozen
checkpoint and exposed three batch-1 forward times: approximately 398, 395,
and 316 ms with 64 PyTorch intra-op threads. The already published Radeon
batch-1 result was also known. Neither value is part of the formal comparison.
The formal result will be published without a minimum speedup gate, including
if the GPU is slower.

## Fixed identities

- Checkpoint SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Runtime backend: `deeplabv3_resnet50`
- Host: Radeon Cloud instance `u-7749-4ed3e710`
- CPU: two AMD EPYC 9334 32-Core processors, 128 logical CPUs visible
- CPU intra-op threads: 64
- GPU: one `gfx1100` Radeon device through the PyTorch ROCm `cuda:0` API
- PyTorch: `2.9.1+gitff65f5b`
- HIP: `7.2.53211-e1a6bc5663`
- Formal runner: `scripts/benchmark_v8_frozen_cpu_gpu.py` at the first public
  commit containing this protocol; the command must pass that exact commit as
  `--expected-source-commit`.

## Fixed method

1. Verify the checkpoint SHA before loading it.
2. Refuse a dirty tracked worktree or a source-commit mismatch.
3. Execute devices in the fixed order `cpu`, then `cuda:0`.
4. Use FP32 and deterministic synthetic tensors generated from seed
   `20260803 + batch_size`.
5. Use batch sizes 1, 4, and 8.
6. For every device and batch, run 20 warm-ups followed by 100 measured
   forwards.
7. Create and transfer inputs before timing. CPU calls are synchronous; the
   Radeon path synchronizes after every measured forward.
8. Report mean, p50, p95, minimum, maximum, and images/s for each device and
   batch.
9. Report GPU-over-CPU ratios without a minimum required ratio.
10. Record same-input output differences as an informational implementation
    check, not as a speed acceptance gate.

## Acceptance and publication

The run is complete only if:

- the exact source commit and checkpoint hash match;
- both devices finish all fixed warm-ups and measurements;
- every recorded duration and output is finite;
- CPU and GPU load the same model identity and output tensor structure; and
- the JSON report, its SHA256, and the execution log are retained.

Any completed formal result is published regardless of direction or magnitude.
A timeout, crash, source mismatch, missing device, or incomplete denominator is
reported as an attempt and is not converted into a performance claim.

## Boundary

This benchmark does not change the frozen V8 endpoint, train or tune the
model, open the locked dataset, rerun the 30-world challenge, or establish a
physical-robot or sim-to-real result. It is a same-host compute comparison for
one frozen model and one synthetic input construction.
