# Look Twice V8 Submission Handoff

This directory is the English-only owner-review handoff for the AMD AI
DevMaster Hackathon 2026, Track 3 - Physical AI.

**Current state:** review-ready package assembly; `official_pr_opened=false`.
No official competition PR may be opened until the owner reviews the final
render, links, entrant identity, and PR body.

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

These are the stable final targets. The 239-second replacement, updated report,
source branch, release assets, and refreshed official-fork package were
published and verified without credentials on 2026-08-03. The refreshed Pages
site was also deployed and anonymously route-verified. No official competition
PR was opened.

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
| Rendered 12-page report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` | `d73e47c53a6e87cd8e8546592465753746513cf31fd4e5b0a1b8dd4747e614aa` |
| 30-second evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` | `46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2` |
| Final 3:59 demo | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/Look-Twice-V8-Demo.mp4` | `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05` |
| Official PR body | `docs/SUBMISSION_DRAFT.md` | English, target URLs complete |
| Official-repo package | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/` | 20 checksummed artifacts verified; 21 total files including `SHA256SUMS` |

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
cd purify_robotics && go test ./...
cd showcase && npm run lint && npm test && npm audit
docker compose build
```

The Evidence Console build passed 26/26 tests and reported zero known
dependency vulnerabilities. The frozen verifier reported all 21 guarded files
green, and the task-utility derivation matched the fixed locked and
confirmatory source hashes without reopening the test. The input-pack verifier
also checked the real 400-world archive without extracting it or running the
model; the formal telemetry run did not access the locked split. The 31
challenge runner/validator tests passed; together with the three telemetry
helper tests, 34 combined tests passed. The independent validator recomputed
the 30-pair result from the full 195-file raw archive with zero errors.

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

## Final owner-review gate

- [ ] Confirm the registered entrant/team label and eligibility items.
- [ ] Inspect the final 3:59 MP4 visually and audibly; its verified SHA256,
      size, streams, and duration are already recorded in
      `V8_SUBMISSION_MANIFEST.json`.
- [x] Regenerate and verify the official-directory `SHA256SUMS` after every
      final artifact is in place.
- [x] Publish the final replacement assets, then verify the Pages site, source
      branch, PDF, checkpoint, and video without
      sign-in.
- [ ] Review the official-fork branch diff and the English PR body.
- [ ] Explicitly authorize opening the official competition PR.
