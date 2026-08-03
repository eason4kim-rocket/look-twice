# Look Twice V8

**Track:** Track 3 - Physical AI

**Entrant:** eason4kim-rocket (solo entrant)

**Project:** Active Evidence Assurance for Physical AI on AMD Radeon GPU

Look Twice is the evidence-assurance layer immediately before robot motion. It
does not ask only what a perception model predicts; it asks whether the
evidence is independent, fresh, calibrated, conflict-free, and sufficient for
this action. When it is not, the denial becomes a machine-readable
`BeliefGap`: a low-risk scout acquires the missing view, the same scoped Action
Contract is re-qualified, and the system either recovers useful motion, takes a
disclosed safe detour, or fails closed.

The target application is warehouse AMR corridor traversal. The carrier may
take the direct route only when both the Python policy path and the standalone
Purify Go reference core admit it. This makes Look Twice complementary to
perception, planning, and simulation systems: it turns uncertain evidence into
a concrete next observation and robot action into an auditable decision.

This entry is simulation-only. It does not claim real-robot validation,
sim-to-real transfer, or safety certification.

## Judge-first links

- Live Evidence Console: <https://eason4kim-rocket.github.io/>
- Frozen results: <https://eason4kim-rocket.github.io/results>
- Reproduction path: <https://eason4kim-rocket.github.io/reproduce>
- Dedicated source branch:
  <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release>
- Technical report:
  [packaged PDF](Look-Twice-V8-Technical-Report.pdf) ·
  [public release asset](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf)
- Final 4:10 English demo:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>
- Frozen checkpoint:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt>
- 30-second evidence preview:
  [Look-Twice-V8-Evidence-Reel-30s.mp4](Look-Twice-V8-Evidence-Reel-30s.mp4)

The 30-second file is a silent evidence preview. The 4:10 release asset is the
complete narrated workflow demonstration.

## 90-second judge path

1. Play the active replay and inspect the initial Action Contract denial.
2. Follow the `BeliefGap` to the scout's independent side-view RGB-D capture.
3. Confirm that direct travel requires Python **and** Purify Go admission.
4. Switch to passive mode and compare its safe detour.
5. Open Results and trace every locked number to the public source JSON.
6. Inspect the non-locked seed-105400 cost ledger for the operational trade.

## Why the result matters

The locked, same-world paired comparison separates safe denial from useful
motion recovery:

| Locked full-chain outcome | Active repair | Passive baseline |
| --- | ---: | ---: |
| Direct route | 11 / 12 | 0 / 12 |
| Mission complete | 12 / 12 | 12 / 12 |
| Unsafe crossing | 0 / 12 | 0 / 12 |
| Unplanned fallback | 0 / 12 | 0 / 12 |

Active repair therefore recovered **+91.7 percentage points** of direct-route
use on the fixed 12-world locked suite. One active seed remained conservative
and detoured; it stays in the denominator. This is descriptive evidence for
the predeclared suite, not a population or real-world generalization.

The guarded non-locked confirmatory replay at seed `105400` adds a deliberately
separate task-cost ledger. Active repair reduced loaded-carrier travel from
6.404 m to 4.915 m (-23.24%), while both policies delivered the payload without
a recorded collision. The scout traveled 3.046 m, so total robot travel
increased from 6.404 m to 7.961 m (+24.32%) and the active run took more steps.
The supported operational claim is narrower and useful: Look Twice can shift
movement burden away from the loaded carrier to a scout; it does not reduce
total distance or latency.

## Frozen V8 result

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
| Python / Purify Go decision agreement | 24 / 24 policy runs |
| Unsafe crossings | 0 / 24 policy runs |
| Unplanned fallback | 0 / 24 policy runs |

The perfect classification values are explicitly decisive-set metrics; 199
inconclusive samples remain visible and are not forced into a class. The
interactive seed-105400 replay is non-locked confirmatory evidence and is not
substituted for the locked aggregate.

## AMD Radeon and ROCm

The frozen environment used Genesis 1.1.2 on `gs.amdgpu`, PyTorch
2.9.1+gitff65f5b, HIP 7.2.53211-e1a6bc5663, and one Radeon Cloud `gfx1100`
GPU with approximately 48 GiB VRAM. Genesis simulation, RGB-D rendering,
tensor preprocessing, and the 39.8M-parameter spatial RGB-D model used the
Radeon GPU. The deterministic Purify Go gate ran on CPU as an independent
authorization layer.

The exact hash-pinned checkpoint passed a separate FP32 preloaded-tensor
model-forward benchmark. Batch 1 measured 192.31 ms p50 and 199.18 ms p95;
batch 8 measured 6.25 images/s with 668.38 MiB peak allocated memory. These are
model-forward measurements, not end-to-end robot latency.

## Reproduction and identities

The dedicated source branch provides a deterministic CPU evidence audit,
Docker Evidence Console, Go reference-core tests, the exact Radeon runtime
command, environment identities, and checkpoint SHA256. The 159,592,901-byte
checkpoint must hash to:

```text
7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783
```

The immutable locked report must hash to:

```text
5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb
```

The 250.000-second final demo is 17,342,763 bytes and must hash to:

```text
906f4396cba9d04ff9e32c8d92ca7c7c85bab7a87f4bbdd2006c79c6474ba280
```

The compact [evidence directory](evidence/README.md) contains the scrubbed
locked report, exact-checkpoint Radeon benchmark, frozen import manifest, and
machine-readable task-utility derivation. All packaged file identities are
listed in [SHA256SUMS](SHA256SUMS).
