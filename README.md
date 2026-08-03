# Look Twice V8: Active Evidence Assurance for Physical AI

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

1. Open the public [Evidence Console](https://eason4kim-rocket.github.io/).
2. Play the active replay: initial denial -> independent side-view capture ->
   Python and Purify admission -> direct route.
3. Compare the passive replay: the same initial denial produces a safe detour.
4. Inspect the [frozen results](https://eason4kim-rocket.github.io/results/)
   and open the linked source JSON.
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

## Task value: recover direct motion, shift carrier burden

Safe refusal is the baseline. In the 12 paired locked worlds, the passive
policy took a safe detour in 12/12, while active evidence repair converted the
same initial denial into a jointly authorized direct route in 11/12 - a +91.7
percentage-point gain with zero recorded unsafe crossings or fallbacks across
all 24 policy runs. Seed 102105 remained conservative and stays in the
denominator.

The guarded non-locked seed 105400 replay provides a narrower cost ledger.
Active repair reduced loaded-carrier travel from 6.404 m to 4.915 m (-23.24%)
while both policies delivered the payload without a recorded collision. This
was not a free speedup: the scout traveled 3.046 m, total robot travel rose
from 6.404 m to 7.961 m, and the active episode took more steps. The value
claim is burden shifting from a loaded carrier to a diagnostic scout, not lower
total distance or latency.

Source: [task-utility derivation](release/v8-derived/V8_TASK_UTILITY_DERIVATION.json),
SHA256 `f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b`.

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
| Robot capability performance - 30 | Same-world paired evidence: active 11/12 direct versus passive 0/12 (+91.7 pp), with 12/12 mission completion for both policies and 0/24 unsafe crossings. |
| AMD Radeon GPU and ROCm adoption - 20 | Genesis `gs.amdgpu`, RGB-D rendering, spatial RGB-D model inference, ROCm tensor path, and frozen environment identities. |
| Innovation and originality - 20 | Lineage-aware Claims, conformal action qualification, dual authorization, BeliefGap-driven active repair, and signed receipts. |
| Real-world application value - 20 | An evidence-assurance layer for warehouse AMRs and other robots operating under sensor correlation, conflict, and partial observability. |
| Upstream open-source contribution - 10 | The project, public schemas, Go reference core, validators, replay builder, and evidence site are open source. No external upstream PR is claimed. |

## Submission deliverables

- [English V8 technical report](docs/V8_TECHNICAL_REPORT.md)
- [Rendered technical report PDF](output/pdf/Look-Twice-V8-Technical-Report.pdf)
- [Detailed reproduction guide](docs/V8_REPRODUCTION.md)
- [Architecture and evidence boundary](docs/V8_EVIDENCE_BOUNDARY.md)
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
- `scripts/derive_v8_task_utility.py` - locked paired-route and guarded replay
  cost derivation without rerunning V8;
- `scripts/verify_v8_rocm_environment.py` - exact ROCm core identity preflight;
- `scripts/verify_frozen_foundation.py` - frozen-boundary verifier.

## Evidence boundary

V8 is the only competition candidate. Later Integrity Shield R1/R2 and V9
experiments do not alter the V8 result and are not promoted into the headline
tables. Source-recovery completion is not treated as a calibration pass. See
[V8 evidence boundary](docs/V8_EVIDENCE_BOUNDARY.md).

Apache-2.0. `NOTICE` defines the public Purify reference-core boundary.
