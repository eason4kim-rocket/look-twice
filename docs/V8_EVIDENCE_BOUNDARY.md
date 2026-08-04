# V8 Competition Evidence Boundary

This document defines what may and may not appear as a Look Twice V8
competition claim. It is intended to prevent development, recovery, research,
and locked-test results from being blended together.

## Primary competition evidence

### Frozen candidate

- Candidate: `v8-frozen`
- Runtime tag: `V8_RUNTIME_FROZEN`
- Vision checkpoint SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Vision conformal identity:
  `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f`
- Go fusion conformal identity:
  `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97`
- Purify binary SHA256:
  `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00`

The imported file boundary is recorded in
`release/V8_FROZEN_IMPORT_MANIFEST.json`. The verifier recalculates every
guarded file hash.

### One-shot locked evaluation

The authoritative report is
`release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_REPORT.json`.

- Report file SHA256:
  `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb`
- Open-seal SHA256:
  `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14`
- Permanent: true
- No retune: true
- No refit: true
- No vision retrain: true
- Errors: none

These numbers may be used in the README, report, website, video, and PR body.

### Locked input archive (input-only)

The additive input-evidence pack is documented in
`docs/V8_LOCKED_INPUT_EVIDENCE.md`; its path-neutral manifest is
`release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json`.

- Archive: 1,019,307,579 bytes, SHA256
  `0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba`.
- Sidecar SHA256:
  `eaecfd450b807183aa0b26fad1cb6fc792202eda54d3abbcd8332f6373a84766`.
- Manifest content identity:
  `ed6f1bbf27aea692ba5e4b47cb7a1fb1e216e0978a473d70d0192bb2eb2a9d30`.
- Population: 400 seeds and 3,200 metadata records, with all 3,600 JSON
  records checked and no machine-local absolute paths.

Verify a local copy without extracting it or running inference:

```bash
python3 scripts/verify_v8_locked_input_pack.py \
  --archive /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz \
  --sidecar /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.sidecar.json \
  --check-only
```

This is an **input-only** evidence class. The verifier performs no model
inference, does not reopen or rerun the locked split, and does not recompute
the locked aggregate. The archive does not contain the original 3,200
one-shot per-sample predictions or the 24 raw live full-chain episode files;
the permanent report contains summaries, not substitutes for those raw
outputs. The sidecar timestamp is first-party provenance and a post-run public
binding, not an external timestamp authority.

### Submission-time derivation

`release/v8-derived/V8_TASK_UTILITY_DERIVATION.json` reads only the permanent
locked report and the two guarded seed-105400 replay episodes. It reruns no V8
episode, does not reopen the locked split, and changes no model, calibration,
contract, or threshold. Its SHA256 is
`f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b`.

Allowed locked derivations include:

- active 11/12 direct versus passive 0/12 direct;
- paired direct-route gain of 91.7 percentage points;
- 12/12 mission completion for each policy;
- zero unsafe crossings and fallbacks across 24 policy runs;
- 24/24 Python/Go decision agreement;
- 3,001/3,200 decisive predictions (93.78%), without relabeling the 199
  non-decisive samples as errors or forced classifications.

The exact paired test is descriptive only for the fixed seed suite. It must not
be generalized to real robots or an unspecified world population.

### Preregistered same-generator challenge supplement

The additive challenge uses 30 previously untouched worlds, seeds
`102500-102529`, from the reserved range. It was publicly bound before any
challenge episode by protocol Commit A
`9e14cbb999824d35a21749f4ff420ab63f81847d` and preregistration Commit B
`3a52ba548de26858a7fdcad1c1ce7237b709fe69`. The preregistration SHA256 is
`90679e84f835c6e46983c1b219c1196506164e3c82dd1dfffec33469a73e28a2`.
Each seed-policy cell was attempted exactly once, with no retry, replacement
seed, early stop, model change, calibration change, or threshold change.

The independently verified result is a **same-generator non-locked
supplement**, separate from the permanent 12-pair locked result:

- active full-chain direct 29/30 (96.7%; Wilson 95% CI 83.3-99.4%) versus
  passive 0/30 (Wilson 95% CI 0-11.4%);
- paired difference +96.7 percentage points; two-sided exact McNemar
  `p=3.725290298461914e-9`;
- 60/60 missions completed, zero unsafe episodes, and zero fallbacks;
- 250/268 comparable Python/Go receipts agreed (93.3%); all 18 disagreements
  were Python-admit/Go-deny with `effective_admit=false`, so no disagreement
  opened the gate;
- all 60 episodes used Genesis live RGB-D, loaded the frozen checkpoint, and
  produced Purify Go receipts.

A post-hoc descriptive audit of the raw archive further localizes the 18
receipt disagreements. All occurred during active-policy evaluations of
corridor B. In each case Go found only one qualifying root and retained the
conformal prediction set `{clear, blocked}`, so it denied while Python
proposed admission. Four concerned a corridor that was not ultimately
selected. The other 14 were temporary evaluations of the ultimately selected
corridor and were followed by a separate joint Python+Go admit before direct
crossing. Thus no selected crossing was authorized by a disagreement. This
audit changes no preregistered endpoint, runtime byte, calibration, or
threshold and is not promoted into a new confirmatory endpoint.

The separate
`release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json` is a post-hoc
descriptive offline oracle-feasibility audit. It does not replace the
preregistered primary endpoint, which remains active 29/30 versus passive 0/30
(exact two-sided McNemar `p=3.73e-9`). Of the 30 active worlds, all 29/29 with
at least one oracle-clear corridor went direct and selected an oracle-clear
corridor. The only dual-blocked world, seed `102515`, completed by safe detour;
therefore 30/30 active route outcomes matched offline feasibility. Oracle
labels were never available to the controller. Across the active records,
unsafe was false, collision count was zero, and fallback was false. This audit
is not a preregistered endpoint and must never be presented as a perfect
direct-route score.

The primary full-chain endpoint requires mission success, direct/no-detour
routing, and a same-corridor `cross_corridor` receipt for which Python, Go, and
the effective decision all admit. Route-only direct is secondary.

Machine evidence is retained in
`release/v8-frozen/results/challenge_102500_102529/`:

| Artifact | SHA256 |
| --- | --- |
| Challenge report | `59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0` |
| Run manifest | `7cbafaadd0a9eb237d24999919d401866a488f76395e636b253feb409ab8681d` |
| Full-wall ROCm telemetry | `463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0` |
| Recursive result checksums | `90d70a11d4a6fd91727c3849536e7a41124196c1c0b4e0f51779419e99105b6d` |
| Independent verification | `942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940` |

The complete 195-file raw archive is a stable release asset with SHA256
`171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2`.
Its internal `SHA256SUMS` binds all other 194 regular files. The independent
validator passed with zero errors and reproduced the committed compact report.

This supplement is not a second locked test, OOD evidence, or a physical-robot
result. Its exact-test p-value is descriptive for the preregistered 30-pair
suite and must not be generalized to an unspecified world population.

## Supporting evidence

The development and confirmatory smokes establish runtime wiring before the
locked open:

- Development smoke, seeds 105300-105311: 10/12 active direct chains.
- Confirmatory smoke, seeds 105400-105411: 9/12 active direct chains.
- Both smokes: 12/12 passive deny, 12/12 passive detour, zero unsafe, zero
  fallback.

They may be described as pre-locked checks, not locked results.

### Frozen ROCm telemetry

`release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json` (SHA256
`0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9`)
records a clean-GPU preflight and a 60.182-second sustained synthetic,
preloaded-tensor, FP32 model-forward workload at batch 8. It forwarded 376
images; all 61/61 telemetry samples reported 100% GPU use, with 135.33 W mean
and 156 W p95 graphics-package power.

This telemetry applies only to the exact frozen model-forward workload. It is
not end-to-end robot latency or throughput, excludes preprocessing, Genesis,
Go fusion, I/O, and actuation, and is not an accuracy result. It did not open
the locked split or change model weights, calibration, or thresholds.

### Preregistered challenge full-wall ROCm telemetry

The challenge adds a separate full-pipeline execution record at
`release/v8-frozen/results/challenge_102500_102529/ROCM_TELEMETRY.json` (SHA256
`463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0`).
It contains 844 samples at a fixed two-second interval across the complete
1,685.5-second challenge subprocess wall, including idle samples. All 60
episode subprocesses are in the denominator. The sample summaries are GPU use
mean/median/p95/max 19.4/0/95/100%, VRAM allocation p95/max 2/2%, and graphics
package power mean/p95/max 35.7/81/109 W.

This second telemetry class covers the complete Python + Genesis + frozen
checkpoint + Purify Go challenge execution wall. It is not control-loop
latency, mission energy, physical duty cycle, or rigid-body/real-robot
validation. It does not replace or broaden the separate synthetic
model-forward telemetry claim above.

### Submission-time dual-body rigid-dynamics supplement

The fixed protocol in `docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_PROTOCOL.md` was
written before the confirmatory range `160820:160840` ran. Engineering-smoke
seeds `160800-160802` were excluded. The complete report is
`release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json`, SHA256
`8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110`.

Allowed claims are:

- 20/20 fixed seeds passed and failed seeds were empty;
- 40 distinct non-fixed robot entities were instantiated, one loaded carrier
  and one scout per seed;
- the only post-build actuation API was wheel-DOF
  `control_dofs_velocity`;
- total trial-blocker contacts, carrier/scout pair contacts, and script entity
  pose writes after build were all zero;
- maximum tilt was 10.749536 degrees and maximum parked-partner drift was
  0.018061 m;
- the same report passed the source-bound verifier on the Radeon host and
  locally.

Attempt 1 ended at the external 3,600-second watchdog before the script wrote
its end-of-run report. It exposed no seed outcome. Recovery restarted the
whole process with only the watchdog increased to 10,800 seconds; source
commit `c17c3a17904af34ba514d68e6e5ad8d1d96a353b`, source bytes, seeds,
parameters, and thresholds were unchanged. No seed was individually retried,
replaced, or resampled. The timeout audit, recovery audit, report, and
directory-level `SHA256SUMS` are retained together.

This evidence class is **submission-time, additive, non-locked**, and the
report declares `formal_result_eligible=false`. It does not rerun or convert
the full frozen V8 active/passive policy, change its shared-chassis kinematic
realization, prove simultaneous cooperative-policy control, or establish a
physical-robot, sim-to-real, energy, throughput, or safety result.

### Submission-time decision-bound rigid-dynamics recovery V2

The fixed recovery V2 protocol in
`docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROTOCOL.md` was sealed after
excluded engineering seeds `170800-170802` and before any formal V2 seed was
opened. Its complete report is
`release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json`,
SHA256
`1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`.

This is a separate, additive replay of the immutable archived challenge
decisions. It does not rerun perception or policy inference. The fixed mix
remains 29 archived direct decisions plus the safe outer detour for the sole
dual-blocked world, seed `102515`. Each seed ran serially in a fresh Genesis
subprocess and a fresh three-body scene containing one active scout, one
active loaded carrier, and one passive loaded carrier. The 90 non-fixed robot
entities are therefore distinct instantiations across 30 independent scenes;
they did not coexist in one 90-body scene or move as a simultaneous fleet.

Allowed claims are:

- 30/30 fixed seeds passed, with all 30 scouts, 30 active carriers, and 30
  passive carriers reaching their goals under wheel-DOF velocity control;
- all 29/29 direct active carriers saved at least 0.50 m against their paired
  passive carrier; the observed minimum saving was 1.333621 m;
- mean loaded-carrier path was 4.943529 m active versus 6.243270 m passive, a
  paired reduction of 20.8183% against the fixed 15% floor;
- the dual-blocked archived decision completed its declared safe outer
  detour;
- counted blocker-contact rows and active carrier/scout contact rows were both
  zero, as were script-level entity pose writes after `scene.build()`;
- maximum body tilt was 10.579607 degrees and maximum parked-partner drift was
  0.022329 m; and
- the same byte-identical report passed the source-aware verifier on the AMD
  host and locally.

This result closes a decision-to-actuation evidence gap, but it does not
replace or upgrade the preregistered challenge primary endpoint. That endpoint
remains active full-chain direct **29/30**, not 30/30. The V2 report declares
`additive_non_locked=true` and `formal_result_eligible=false`. “Zero contact”
means zero counted Genesis contact rows under this fixed instrumentation, not
a general collision-free or certified-safety guarantee. The carrier-path
reduction is not a reduction in total team travel, energy, task time, or
throughput.

The integrity evidence also has two explicit proof-scope limits. The formal
`SOURCE_BINDING.json` binds the named protocol, runner, verifier, archived
input, assets, scenario, and helper files, but omits the directly imported
`src/v4_motion.py`; it is therefore not a complete transitive source closure.
A post-run tree audit found that file byte-identical to clean commit
`b0c4f0d33b0a2d0c647dda0b2b3b7c03279a511a`, which is corroborating evidence
and does not retroactively expand the formal binding. The original inner
`SHA256SUMS` binds `SOURCE_BINDING.json`, all 30 trial checkpoints, and
`REPORT.json`, but not `ATTEMPTS.jsonl`, `PROGRESS.json`, or `WORKER_LOGS`.
Those retained records were inspected and show 30 first-attempt, zero-exit
worker completions with no observed retry or seed replacement; they must not
be described as cryptographic proof that no additional unsealed attempt ever
existed. The scope audit is retained as
`release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json`.

### Reserved challenge range status

The historical `ood_test` label for seeds 102500-102699 denotes only a
**reserved challenge range** from the **same generator family**. Seeds
`102500-102529` were evaluated once in the publicly preregistered non-locked
supplement above. Seeds `102530-102699` remain unevaluated. Neither subset is
called OOD, and no out-of-distribution or population-generalization result is
claimed.

## Public replay status

The website uses the confirmatory seed 105400 active and passive episodes. The
replay is a deterministic presentation of recorded AMD GPU evidence and links
back to each source episode SHA.

It must be described as:

- recorded Genesis plus AMD GPU evidence;
- a non-locked confirmatory example;
- simulation only;
- replayable without a live GPU.

It must not be described as a new benchmark run, a locked-test episode, a live
cloud execution, or a real-robot recording.

Seed 105400 may also support the following explicitly non-locked cost ledger:
loaded-carrier travel 4.915 m active versus 6.404 m passive (-23.24%), scout
travel 3.046 m active, and total robot travel 7.961 m active versus 6.404 m
passive (+24.32%). This supports motion-burden shifting, not lower total
distance, latency, energy use, or locked-population path efficiency.

The 30-world challenge supports a separate aggregate logical-role ledger:
loaded-carrier mean path 4.961 active versus 6.404 passive (-1.443, -22.5%),
active scout mean path 2.980, and total logical-role team path 7.941 active
versus 6.404 passive (+1.538, +24.0%). Carrier and scout are distinct logical
poses, viewpoints, and capture roots realized on **one shared Genesis
chassis**. These values are kinematic motion burden, not two physical devices,
simultaneous dual-body dynamics, energy, latency, throughput, or physical duty
cycle.

## Later research excluded from V8 claims

The following work remains scientifically useful but is not promoted into the
V8 competition result:

- V9 challenger experiments;
- Integrity Shield Research R1, whose one-shot calibration failed;
- Integrity Shield Research R2, whose protocol is explicitly
  `research_only` and `competition_promotion_forbidden`, and whose one-shot
  calibration failed;
- any shortcut-only pass that lacks its required terminal calibration pass;
- any failed or invalid implementation report.

The R1 recovery source result of 150/150 worlds, zero failed jobs, and one
recaptured seed establishes data completeness only. It does not change the R1
terminal calibration decision and does not alter V8.

Failed reports remain preserved. They are not overwritten, relabeled, or
silently omitted from the research archive.

## Honest limitations

- Simulation only; no real-robot or sim-to-real result.
- The public replay uses a kinematic Genesis motion backend.
- The preregistered challenge also uses the kinematic motion backend; its
  carrier and scout are two logical roles on one shared chassis, not two
  physical robots or simultaneous dual-body dynamics. A separate additive
  20-seed supplement validates bounded sequential wheel motion by two
  non-fixed rigid bodies. The separate 30-seed recovery V2 binds archived
  challenge decisions to three non-fixed bodies per independent scene. Neither
  supplement is a live full-policy rerun or simultaneous 90-body execution.
- The public replay episode carries `formal_result_eligible=false`; it is a
  presentation artifact, not the locked aggregate.
- The 30-world challenge is a same-generator non-locked supplement, not a
  reopened locked split, OOD result, or physical validation.
- Receipt-level Python/Go agreement in that supplement is 250/268 (93.3%);
  all 18 mismatches were Go vetoes that remained fail-closed.
- The mismatch localization above is a post-hoc descriptive raw-archive audit,
  not a preregistered endpoint or a tuning action.
- The locked result is an internal one-shot simulated evaluation, not a safety
  certification.
- The locked input evidence pack is input-only; original one-shot predictions
  and raw locked live episodes are not available in that pack.
- The 159 MB frozen checkpoint is identified by SHA and distributed as a
  GitHub release asset because it exceeds GitHub's 100 MB file limit.
- A focused Genesis parser fix and regression test are prepared locally with
  baseline-fail/patch-pass evidence. No public external upstream contribution
  is claimed until owner approval and publication.

## Claim approval rule

A number is submission-ready only when it has:

1. a named source file;
2. a stable SHA or frozen identity;
3. a declared split and population;
4. an honest label such as locked, same-generator non-locked supplement,
   confirmatory, replay, or research;
5. no conflict with this boundary.
