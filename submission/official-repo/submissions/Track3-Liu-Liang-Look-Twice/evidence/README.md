# Look Twice V8 Compact Evidence

This directory is the compact, judge-facing evidence surface. The dedicated
[`v8-competition-release`](https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release)
source branch remains authoritative for source code, validators, schemas,
replay media, complete reproduction instructions, and the immutable raw
archive.

## Files

- `LOCKED_TEST_REPORT.public.json` is a deterministic public rendering of the
  one-shot locked report. It removes only machine-location fields named
  `path`, `opened_seal`, and `live_rows_path`; metric values, gates, identities,
  population counts, discipline flags, and timestamps are preserved.
- `V8_FROZEN_INFERENCE_BENCHMARK.json` records the exact-checkpoint FP32
  preloaded-tensor model-forward benchmark on the captured Radeon/ROCm host.
- `V8_FROZEN_ROCM_TELEMETRY.json` records a clean-GPU preflight followed by 61
  raw `rocm-smi` samples during a 60-second exact-checkpoint model-forward run.
- `V8_LOCKED_INPUT_PACK_MANIFEST.json` verifies the separately released
  pre-open 400-world, 3,200-record input-and-label archive without model
  inference, array extraction, or a locked-test rerun.
- `V8_FROZEN_IMPORT_MANIFEST.json` identifies the 21 guarded source and
  evidence files used by the deterministic repository verifier.
- `V8_TASK_UTILITY_DERIVATION.json` derives the paired locked task-utility table
  and the separate non-locked seed-105400 cost ledger from already archived
  evidence. It does not rerun V8, reopen the locked test, or change a model or
  threshold.
- `challenge_102500_102529/CHALLENGE_REPORT.json` is the preregistered
  30-world paired analysis, including the primary full-chain endpoint,
  per-seed outcomes, confidence intervals, receipt agreement, operational
  burden, and telemetry summary.
- `challenge_102500_102529/RUN_MANIFEST.json` binds the public
  preregistration, runner/validator identities, frozen runtime closure,
  balanced schedule, one-shot execution contract, and completion status.
- `challenge_102500_102529/ROCM_TELEMETRY.json` retains every two-second
  full-subprocess-wall `rocm-smi` sample, including idle periods.
- `challenge_102500_102529/VERIFICATION.json` is the deterministic,
  independently reproduced validator result. It reports `passed=true`,
  zero errors, and 60/60 expected raw episode records read.
- `challenge_102500_102529/RAW_ARCHIVE_SHA256SUMS` is a packaged copy of the
  raw archive's internal checksum index. It binds all 194 other files inside
  that 195-file archive; its paths are archive-relative and are not a second
  checksum index for this compact package.

## Judge-facing findings

### Locked same-world comparison

Across 12 paired Genesis worlds, active repair qualified 11/12 direct routes
while the passive baseline qualified 0/12: a **+91.7 percentage-point** paired
gain. Both policies completed 12/12 missions. Unsafe crossings and unplanned
fallbacks were 0/24 across all policy runs, and Python/Purify Go decisions
agreed 24/24. The one conservative active detour remains in the denominator.

This is descriptive evidence for the fixed locked seed suite; it is not a
population or real-world generalization.

### Non-locked confirmatory cost ledger

Seed `105400` has `formal_result_eligible=false` and is kept separate from the
locked aggregate. Active repair reduced loaded-carrier travel from 6.404 m to
4.915 m (-23.24%) while both policies delivered the payload with zero recorded
collisions. The scout traveled 3.046 m, total robot travel increased from
6.404 m to 7.961 m (+24.32%), and the active episode took more steps. The
supported claim is movement-burden transfer from the loaded carrier to the
scout, not lower total distance or latency.

### Publicly preregistered same-generator supplement

Before execution, Commit A fixed the challenge protocol, seeds `102500-102529`,
runner, validator, frozen runtime dependencies, endpoint, telemetry cadence,
balanced order, and no-retry rule; Commit B changed only the preregistration's
Commit-A binding. The one-shot execution then produced 60/60 valid episodes:

| Full-chain outcome | Active repair | Passive baseline |
| --- | ---: | ---: |
| Direct route | 29 / 30 (96.7%) | 0 / 30 (0.0%) |
| Wilson 95% CI | 83.3-99.4% | 0.0-11.4% |
| Mission complete | 30 / 30 | 30 / 30 |
| Unsafe | 0 / 30 | 0 / 30 |
| Fallback | 0 / 30 | 0 / 30 |

The paired gain is **+96.7 percentage points**; exact two-sided McNemar
`p=3.73e-9`. The sole active non-direct case, seed `102515`, remained safe
and completed by detour. Receipt-level Python/Go agreement was 250/268
(93.3%); all 18 disagreements were Python-admit/Go-deny and remained
`effective_admit=false`. A post-hoc descriptive audit (not a preregistered
endpoint) found the same inspectable Go signature in all 18: active-policy
corridor B, one Go-qualified root, and the inconclusive set
`{clear, blocked}`. Four concerned a non-selected corridor; the other 14
preceded the final selected-corridor joint admit. This audit changed no
runtime, calibration, or threshold.

Active repair reduced mean loaded-carrier logical path from 6.404 to 4.961
(-22.5%) while adding 2.980 scout path; total logical-role path increased from
6.404 to 7.941 (+24.0%). This is a burden-shifting result on one shared
Genesis chassis, not a claim of lower total motion, energy, throughput,
latency, or two simultaneously simulated physical robots.

## Authoritative identities

| Item | SHA256 |
| --- | --- |
| Immutable raw locked report | `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb` |
| Locked-open seal | `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14` |
| Frozen vision checkpoint | `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783` |
| Final 239-second demo video | `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05` |
| Final demo builder sidecar | `639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb` |
| Task-utility derivation | `f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b` |
| Radeon model-forward benchmark | `282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156` |
| Sustained Radeon telemetry | `0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9` |
| Locked input archive | `0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba` |
| Locked input manifest file | `421a0b1e2ebcfd20a84742a799e461fe060587fa2fc33438dfbf8cfc42f90818` |
| Vision conformal artifact | `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f` |
| Go-fusion conformal artifact | `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97` |
| Purify Linux reference binary | `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00` |
| Challenge preregistration | `90679e84f835c6e46983c1b219c1196506164e3c82dd1dfffec33469a73e28a2` |
| Challenge report | `59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0` |
| Challenge run manifest | `7cbafaadd0a9eb237d24999919d401866a488f76395e636b253feb409ab8681d` |
| Challenge full-wall ROCm telemetry | `463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0` |
| Challenge independent verification | `942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940` |
| Raw archive internal checksum index | `90d70a11d4a6fd91727c3849536e7a41124196c1c0b4e0f51779419e99105b6d` |
| Complete challenge raw archive | `171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2` |

The public locked-report copy has a different file SHA because location-only
fields are omitted. Its content is generated by
`scripts/build_competition_replays.py`, tested for machine-path hygiene, and
can be compared with the immutable source report in the dedicated repository.

## Stable target anchors

- Evidence Console: <https://eason4kim-rocket.github.io/>
- Technical report:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf>
- Final 3:59 demo:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>
- Frozen checkpoint:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt>
- Locked input-and-label archive:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz>
- Frozen challenge Judge Card:
  [packaged copy](../V8-Frozen-Challenge-Judge-Card.md)
- Complete 30-world raw archive:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz>
- Challenge verification release asset:
  <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json>

The 239-second replacement MP4 and sidecar were downloaded from their stable
targets without credentials and matched the packaged SHA256 identities on
2026-08-03. The final 12-page report is packaged one directory above and bound
by the package-level `SHA256SUMS`; its release URL is the publication target.

## Scope

- Simulation only; no physical-robot or safety-certification claim.
- The permanent 12-pair locked aggregate, the seed-105400 non-locked public
  replay, and the 30-pair preregistered non-locked supplement are separate
  evidence surfaces.
- Perfect offline classification values apply to 3,001 decisive samples; 199
  inconclusive samples remain visible.
- Model-forward timing excludes preprocessing, Genesis, Go fusion, I/O, and
  actuation.
- The input supplement lacks original per-sample predictions and 24 raw locked
  episodes; it does not reconstruct or recompute the one-shot run.
- The 61/61 utilization result applies only to the disclosed synthetic,
  preloaded FP32 model-forward workload. No locked aggregate path-length,
  latency, mission-energy, or end-to-end utilization claim is made.
- Seeds `102500-102529` were evaluated exactly once under the public
  preregistration. They are a same-generator, non-locked supplement, not OOD
  or a second locked open. Seeds `102530-102699` remain unevaluated.
- Carrier and scout in the supplement are distinct logical-role poses,
  viewpoints, and capture roots on one shared Genesis chassis; the result does
  not demonstrate two physical devices, dual-body rigid dynamics, real-robot
  validation, sim-to-real transfer, or safety certification.
- Full-wall challenge telemetry includes idle periods and supports Radeon/ROCm
  execution of Genesis, frozen checkpoint inference, and Purify Go
  subprocesses. It is not control-loop latency, mission energy, or physical
  duty-cycle evidence.
- Demo narration is AI-generated with OpenAI `gpt-4o-mini-tts`, using the
  `cedar` voice and an on-screen disclosure. Chapter visuals use fixed
  composition with no `zoompan` motion.
- Integrity Shield R1/R2 and V9 research is outside the V8 submission.
