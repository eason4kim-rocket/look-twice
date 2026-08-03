# Look Twice V8

> Pre-submission staging copy. Replace the final demo-video placeholder and
> verify every public link before this directory is added to the official
> competition repository.

**Track:** Track 3 - Physical AI

**Entrant:** eason4kim-rocket (solo entrant; confirm against registration)

**Project:** Active Evidence Assurance for Physical AI on AMD Radeon GPU

Look Twice prevents a robot from treating noisy, correlated, stale, or
conflicting observations as action-ready facts. In a Genesis warehouse AMR
scenario, an initial Action Contract denial can trigger a diagnostic side-view
RGB-D observation. Direct motion is permitted only when both the Python policy
path and the standalone Purify Go reference core admit the same scoped action;
otherwise the robot takes a disclosed safe detour or fails closed.

This entry is simulation-only. It does not claim real-robot validation,
sim-to-real transfer, or safety certification.

## Judge-first links

- Evidence Console: <https://look-twice-evidence-console.eason1319.workers.dev/>
- Frozen Results: <https://look-twice-evidence-console.eason1319.workers.dev/results>
- Source and reproduction: <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release>
- Technical report: [Look-Twice-V8-Technical-Report.pdf](Look-Twice-V8-Technical-Report.pdf)
- Final 3-5 minute English demo: `FINAL_3_TO_5_MINUTE_VIDEO_URL`
- 30-second evidence preview: [Look-Twice-V8-Evidence-Reel-30s.mp4](Look-Twice-V8-Evidence-Reel-30s.mp4)

The 30-second file is a silent evidence preview, not a substitute for the final
3-5 minute workflow demonstration.

## 90-second judge path

1. Play the active replay and inspect the initial contract denial.
2. Follow the scout to the independent side-view RGB-D capture.
3. Confirm that direct travel requires Python and Purify Go admission.
4. Switch to passive mode and compare the safe detour.
5. Open Results and trace the locked table to the public JSON evidence.

## Frozen V8 result

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

One active locked seed remained conservative and detoured; it stays in the
denominator. The interactive replay is a non-locked confirmatory episode and
is not substituted for the locked aggregate.

## AMD Radeon and ROCm

The frozen environment used Genesis 1.1.2 on `gs.amdgpu`, PyTorch
2.9.1+gitff65f5b, HIP 7.2.53211-e1a6bc5663, and one Radeon Cloud `gfx1100`
GPU with approximately 48 GiB VRAM. Genesis simulation, RGB-D rendering,
tensor preprocessing, and the 39.8M-parameter spatial RGB-D model used the
Radeon GPU. The deterministic Purify Go gate ran on CPU.

The exact hash-pinned checkpoint passed a separate FP32 preloaded-tensor
model-forward benchmark. Batch 1 measured 192.31 ms p50 and 199.18 ms p95;
batch 8 measured 6.25 images/s with 668.38 MiB peak allocated memory. These are
model-forward measurements, not end-to-end robot latency.

## Reproduction

The public source repository provides a deterministic CPU evidence audit,
Docker Evidence Console, Go reference-core tests, the exact Radeon runtime
command, environment identities, and checkpoint SHA256. The 159,592,901-byte
checkpoint must be downloaded from the final public model/release mirror and
must hash to:

```text
7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783
```

## Evidence files

The compact evidence directory contains the machine-path-scrubbed locked
report, the exact-checkpoint Radeon benchmark, and the frozen import manifest.
See [evidence/README.md](evidence/README.md) for provenance and scope.

All packaged file identities are listed in [SHA256SUMS](SHA256SUMS).
