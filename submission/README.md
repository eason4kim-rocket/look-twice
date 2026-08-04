# Look Twice V8 Submission Handoff

This directory is the English-only owner-review handoff for the AMD AI
DevMaster Hackathon 2026, Track 3 - Physical AI.

**Current state:** V2 evidence verified; owner review pending;
`official_pr_opened=false`. No source push, Pages deployment, release-asset
replacement, official-fork push, competition PR, or Genesis upstream PR for
this refresh may occur until the owner reviews and authorizes it.

Official PR title assumption:

```text
Track 3, Liu Liang, Look Twice
```

The confirmed entrant/team is **Liu Liang** (solo entrant). The GitHub account
is **[@eason4kim-rocket](https://github.com/eason4kim-rocket)**; the private
registration email is intentionally excluded from all public submission
materials. Submission deadline: **2026-08-06 23:59 UTC+8**.

## Submission positioning

Look Twice is the evidence-assurance layer immediately before robot motion. It
qualifies whether evidence is independent, fresh, calibrated, conflict-free,
and sufficient for a scoped action. A denial produces a machine-readable
`BeliefGap`; a scout acquires the missing view, and dual Python/Purify Go
authorization either recovers useful motion, selects a disclosed detour, or
fails closed.

The concrete target application is warehouse AMR corridor traversal: a loaded
carrier may use the direct route only after the action contract is satisfied;
otherwise a scout obtains an independent side view and the system re-evaluates
the route. All competition evidence is from recorded Genesis simulation on AMD
Radeon. No real-robot, field-deployment, or sim-to-real result is claimed.

The locked 12-world paired comparison is the central capability result:
active repair qualified 11/12 direct routes versus 0/12 for passive
(**+91.7 percentage points**), while both policies completed 12/12 missions
and unsafe crossings/fallbacks remained 0/24. A separately preregistered
30-world **same-generator non-locked supplement** produced 29/30 active
full-chain direct versus 0/30 passive (+96.7 percentage points), with 60/60
mission completion, zero unsafe episodes, and zero fallbacks. Its aggregate
logical-role ledger reduced loaded-carrier path by 22.5% while total team path
rose 24.0%. Carrier and scout are logical roles on one shared Genesis chassis,
not two physical devices or simultaneous dual-body dynamics.

The preregistered primary endpoint remains **active 29/30 versus passive
0/30** (exact two-sided McNemar `p=3.73e-9`). A separate post-hoc descriptive
offline oracle-feasibility audit found that all **29/29** worlds with at least
one oracle-clear corridor went direct and selected an oracle-clear corridor.
The only dual-blocked world, seed `102515`, completed by safe detour. Thus
**30/30 active route outcomes matched offline feasibility**. Oracle labels were
never available to the controller, and this audit is not a preregistered
endpoint. Across the 30 active records, unsafe was false, collision count was
zero, and fallback was false.

A separate additive decision-bound recovery V2 replays those immutable
archived route decisions without rerunning the frozen perception-policy loop.
It passed **30/30** fixed seeds as 30 independent Genesis scenes, with one
active scout, active loaded carrier, and passive loaded carrier per scene. All
**90/90** distinct non-fixed robot instantiations reached; these are 90 bodies
across the run, not one simultaneous 90-body scene. Mean active/passive loaded-
carrier paths were 4.944/6.243 m, a paired reduction of **20.8183%**, with zero
blocker-contact rows, zero active-pair-contact rows, and zero post-build pose
writes. This execution result is not a replacement for the preregistered
active **29/30** versus passive 0/30 primary endpoint.

V2 is additive, non-locked, simulation-only, and
`formal_result_eligible=false`. It does not establish a policy rerun,
simultaneous cooperative control, dynamic-obstacle response, real-robot or
sim-to-real performance, throughput, energy, or safety certification.

## Public target URLs

| Surface | Target |
| --- | --- |
| Evidence Console | <https://eason4kim-rocket.github.io/> |
| Frozen Results | <https://eason4kim-rocket.github.io/results> |
| Reproduction | <https://eason4kim-rocket.github.io/reproduce> |
| Dedicated source branch | <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release> |
| Release | <https://github.com/eason4kim-rocket/look-twice/releases/tag/v8-competition-candidate> |
| Technical report PDF | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf> |
| Frozen checkpoint | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt> |
| Locked input-and-label archive | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz> |
| Challenge raw archive | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz> |
| Challenge independent verification | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json> |
| Final 3:59 English demo | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4> |

These stable targets currently serve the previously verified public baseline.
The 239-second demo remains public and hash-verified. The new V2 evidence
package and local verifier are ready for owner review; the V2-integrated
technical report PDF, refreshed site, source-branch update, release-PDF
replacement, and regenerated official-fork package remain local review items.
No official competition or Genesis upstream PR is open.

## Handoff map

1. Owner-review checklist: `docs/SUBMISSION_CHECKLIST.md`
2. Exact English PR body: `docs/SUBMISSION_DRAFT.md`
3. Submission manifest: `submission/V8_SUBMISSION_MANIFEST.json`
4. Official-repository directory:
   `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/`
5. Technical report source: `docs/V8_TECHNICAL_REPORT.md`
6. Detailed reproduction guide: `docs/V8_REPRODUCTION.md`
7. Final demo specification: `docs/V8_DEMO_SCRIPT.md`
8. Preregistered challenge Judge Card:
   `docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md`
9. Additive dynamics result and recovery note:
   `docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md`
10. Decision-bound dynamics recovery V2 result and evidence:
    `docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md` and
    `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/`
11. Prepared Genesis upstream review packet:
    local sibling review directory; intentionally excluded from the public
    competition package until owner approval.

## Primary competition artifacts

| Artifact | Path | SHA256 / state |
| --- | --- | --- |
| Locked V8 report | `release/v8-frozen/results/LOCKED_TEST_REPORT.json` | `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb` |
| Locked-open seal | `release/v8-frozen/results/LOCKED_TEST_OPENED.json` | `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14` |
| Task-utility derivation | `release/v8-derived/V8_TASK_UTILITY_DERIVATION.json` | `f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b` |
| ROCm model-forward benchmark | `release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json` | `282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156` |
| Sustained ROCm telemetry | `release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json` | `0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9` |
| Locked input pack manifest | `release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json` | `421a0b1e2ebcfd20a84742a799e461fe060587fa2fc33438dfbf8cfc42f90818` |
| Locked input archive | release asset, 1,019,307,579 bytes | `0933053f28aca5254f13eb2eb11ce16c2f488e1880e4e282b1e4dfd7d957cfba` |
| Challenge report | `release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json` | `59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0` |
| Challenge full-wall telemetry | `release/v8-frozen/results/challenge_102500_102529/ROCM_TELEMETRY.json` | `463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0` |
| Challenge verification | `release/v8-frozen/results/challenge_102500_102529/VERIFICATION.json` | `942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940` |
| Challenge raw archive | release asset, 3,188,824 bytes | `171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2` |
| Post-hoc challenge feasibility audit | `release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json` | `dc1dc979c58e1a2c1155b144c8e826ffab5ffee4e2113e954351e92bb635c434` |
| Additive dual-body report | `release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json` | `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110` |
| Dual-body timeout audit | `release/v8-derived/dual_body_dynamics_160820_160839/ATTEMPT_1_TIMEOUT_AUDIT.json` | `711547fb5f0ab928ae5cc8b6195f4e0e964a98f6df44dfa2955c67e624705d55` |
| Dual-body recovery audit | `release/v8-derived/dual_body_dynamics_160820_160839/RECOVERY_EXECUTION_AUDIT.json` | `6c3ddfa0ec2b482c1ab01a160572d01451f0bb1b495137e09a18a96018f23e6e` |
| Decision-bound V2 report | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json` | `1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99` |
| Decision-bound V2 recovery audit | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/RECOVERY_EXECUTION_AUDIT.json` | `344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4` |
| Decision-bound V2 provenance review | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json` | `4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7` |
| Decision-bound V2 package index | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PACKAGE_SHA256SUMS` | 79 indexed evidence files; index SHA256 `24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540` |
| Rendered 15-page report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` | `29935428bf1eedd5942fa89e961fbc8b057e99130cc5df18a28fe3040c71d35e` |
| 30-second evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` | `46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2` |
| Final 3:59 demo | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/Look-Twice-V8-Demo.mp4` | `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05` |
| Official PR body | `docs/SUBMISSION_DRAFT.md` | English, target URLs complete |
| Official-repo package | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/` | 103 manifest entries, 104 checksum entries, 105 total files; `SHA256SUMS` SHA256 `e3fee90381052e4b8fe28ca937736292ae5dee670ef30e1abf0b6a258fdc63f9`; local only, no push or PR |

## Frozen checkpoint

- SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Size: 159,592,901 bytes.
- Public target: the `v8-competition-candidate` release asset linked above.
- The unchanged checkpoint asset remained available at the stable URL and its
  published SHA256 identity was rechecked.

## Verified local commands

The following passed during submission preparation on 2026-08-03:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
python3 scripts/derive_v8_task_utility.py
python3 -m unittest tests.test_v8_locked_input_pack tests.test_benchmark_v8_frozen_telemetry -v
python3 -m unittest tests.test_run_v8_frozen_challenge tests.test_verify_v8_frozen_challenge -v
python3 -m unittest tests.test_run_v8_additive_dual_body_dynamics tests.test_verify_v8_additive_dual_body_dynamics -v
python3 scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
python3 scripts/finalize_v8_submission_package.py --check
cd purify_robotics && go test ./...
cd showcase && npm run lint && npm test && npm audit
docker compose build
```

The refreshed Evidence Console build passed 35/35 tests, lint, production
build, and a zero-vulnerability dependency audit. The earlier public baseline
retains its hydrated desktop visual inspection; owner browser review of the V2
local build remains required before deployment. The frozen verifier reported
all 21 guarded files
green, and the task-utility derivation matched the fixed locked and
confirmatory source hashes without reopening the test. The input-pack verifier
also checked the real 400-world archive without extracting it or running the
model; the formal telemetry run did not access the locked split. The 31
challenge runner/validator tests passed; together with the three telemetry
helper tests, 34 combined tests passed. The independent validator recomputed
the 30-pair result from the full 195-file raw archive with zero errors.

The recovery V2 verifier accepted the byte-identical 30/30 report remotely and
locally. Owner review must still rerun both checksum indexes and the local
verifier from the final integrated tree:

```bash
cd release/v8-derived/decision_dynamics_recovery_v2_102500_102529
shasum -a 256 -c SHA256SUMS
shasum -a 256 -c PACKAGE_SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json
```

The final demo render is 239.000 seconds and 9,032,035 bytes. Its SHA256 is
`70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`;
the builder sidecar SHA256 is
`639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb`.
Narration is an AI-generated `cedar` voice from OpenAI
`gpt-4o-mini-tts`; that disclosure is burned into the video. Chapter visuals
use fixed composition with no `zoompan` motion.

## Evidence boundary

Only V8 is submitted. The locked aggregate, input-only pre-open supplement,
non-locked seed-105400 replay, preregistered same-generator challenge, and two
Radeon telemetry classes remain explicitly separated. The input supplement
lacks the original one-shot predictions and 24 raw locked live episodes; it
cannot reconstruct or recompute the permanent result. Seeds 102500-102529 were
evaluated once per policy in the additive challenge; seeds 102530-102699 remain
unevaluated. Neither subset is V8 OOD evidence. Challenge Python/Go receipt
agreement is 250/268 (93.3%); all 18 mismatches were Go vetoes with
`effective_admit=false`.
Integrity Shield R1/R2 and V9 are later research and do not change the locked
V8 result. The submission makes no real-robot, sim-to-real, safety-
certification, locked latency, mission-energy, or physical-duty-cycle claim.
The 61/61 utilization result applies only to the disclosed synthetic,
preloaded FP32 model-forward window. Separate challenge telemetry contains 844
two-second samples across the complete 1,685.5-second subprocess wall,
including idle; it is not control-loop latency. See
`docs/V8_EVIDENCE_BOUNDARY.md`.

The additive dual-body supplement is also simulation-only and non-locked. It
passed 20/20 fixed seeds with 40 non-fixed robot entities, zero blocker/pair
contact rows, and zero post-build pose writes. It validates bounded sequential
wheel motion by two rigid bodies; it does not rerun the frozen policy,
demonstrate simultaneous cooperative control, or establish a physical-robot or
safety result.

The decision-bound recovery V2 is a second, separately frozen additive
supplement. It consumes archived decisions in 30 independent three-body
scenes; it does not rerun the frozen policy and its 90 distinct bodies were not
simultaneous. Its retained ledger and logs show 30 first-attempt worker
completions, no completed-checkpoint rerun, and no seed replacement. However,
the formal checksum index did not originally cover attempts/progress/logs, and
the formal source manifest omitted the directly imported `src/v4_motion.py`.
The post-run tree audit and complete package index corroborate the retained
record; they are not cryptographic proof of continuous no-retry execution or a
fully bound runtime dependency closure.

## Final owner-review gate

- [ ] Confirm the registered entrant/team label and eligibility items.
- [ ] Inspect the final 3:59 MP4 visually and audibly; its verified SHA256,
      size, streams, and duration are already recorded in
      `V8_SUBMISSION_MANIFEST.json`.
- [x] Regenerate and verify the official-directory `SHA256SUMS` after every
      final artifact is in place.
- [x] Preserve and anonymously verify the existing public baseline assets.
- [ ] Review the complete V2 evidence package and rerun its formal/package
      checksum checks and local verifier.
- [ ] Review the V2-integrated technical report and visually inspect every PDF
      page after rebuild; record the replacement hash and page count.
- [ ] Review the V2 site additions and local build/tests before deployment.
- [ ] Review the regenerated official-package manifest, checksums, and exact
      staging-to-official-fork diff.
- [ ] After owner approval, publish the additive source/site/PDF/package
      refresh and verify every stable target without sign-in.
- [ ] Review the official-fork branch diff and the English PR body.
- [ ] Review the prepared Genesis issue/PR packet and authorize or reject
      upstream publication.
- [ ] Explicitly authorize opening the official competition PR.
