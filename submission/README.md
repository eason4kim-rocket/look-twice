# Look Twice V8 Submission Handoff

This directory is the English-only owner-review handoff for the AMD AI
DevMaster Hackathon 2026, Track 3 - Physical AI.

**Owner-review control state at snapshot generation:** the integrated payload
was verified locally and `official_pr_opened=false`. Publication of the
additive review surfaces is complete and anonymously verified; the official
AMD PR remains subject to separate explicit owner authorization.

**Publication update:** the original frozen source/tag, refreshed
contract-progress source/PDF/site/mirror/personal fork, and Genesis issue/PR
are public. External receipts were anonymously verified at
`2026-08-06T02:53:18Z`. The AMD competition PR remains unopened.

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

The additional public Commit-A/Commit-B contract-progress challenge is a
separate additive efficiency result. Across seeds `102530–102549`, both the
frozen baseline and compound candidate remained **20/20 full-chain direct**.
The candidate reduced mean scout path **40.2563%**, mean team path
**15.0306%**, and physical captures **27.5362%** (50 versus 69). All 40
missions completed; unsafe, collision, fallback, and false clear were zero.
Every paired world favored the candidate on scout and team path. This is a
same-generator, non-locked, kinematic compound-system result with
`formal_result_eligible=false`; it is not a new-weight, OOD, physical-robot,
single-component causal, or replacement-primary claim.

The current additive decision-bound complement replays those immutable
archived route decisions without rerunning the frozen perception-policy loop.
It consists of exactly two independently verified, non-resumable Genesis scene
shards:

- seeds `102500-102519`: **20/20**, one 60-body scene; report SHA256
  `3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450`;
- seeds `102520-102529`: **10/10**, one 30-body scene; report SHA256
  `69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e`.

Together they cover **30/30** seeds in exactly **2** scenes and **90**
cumulative distinct non-fixed robot entities. The maximum co-resident count is
**60**; the 90 were never all co-resident. Weighted active/passive
loaded-carrier paths were **4.943605/6.245385 m**, a paired reduction of
**20.8439%**. All
**29/29** direct pairs saved at least 0.5 m, while the only dual-blocked world,
seed `102515`, completed by safe detour. Counted blocker/active-pair contact
rows and post-build pose writes remained zero. This is a combined claim over
two complete shard reports, not a cross-shard checkpoint/state resume or one
stitched simulator result.

The earlier 30-independent-scene recovery V2 remains retained as corroborating
historical evidence. Both it and the two-shard complement are additive,
non-locked, simulation-only, and `formal_result_eligible=false`. Neither
replaces the preregistered primary endpoint of active **29/30** versus passive
0/30 or establishes a live policy rerun, simultaneous cooperative control,
dynamic-obstacle response, real-robot or sim-to-real performance, throughput,
energy, or safety certification.

## Public target URLs

| Surface | Target |
| --- | --- |
| Evidence Console | <https://eason4kim-rocket.github.io/> |
| Public site mirror | <https://look-twice-evidence.jason-tuantuan1319.chatgpt.site/> |
| Frozen Results | <https://eason4kim-rocket.github.io/results> |
| Reproduction | <https://eason4kim-rocket.github.io/reproduce> |
| Additive review source branch | <https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv> |
| Original frozen V8 foundation | <https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-final-2026-08-05> |
| Release | <https://github.com/eason4kim-rocket/look-twice/releases/tag/v8-competition-candidate> |
| Technical report PDF | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf> |
| Frozen checkpoint | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt> |
| Locked input-and-label archive | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz> |
| Challenge raw archive | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz> |
| Challenge independent verification | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.VERIFICATION.json> |
| Browser-playable 3:59 English demo | <https://eason4kim-rocket.github.io/media/Look-Twice-V8-Demo.mp4> |
| 3:59 demo download/hash mirror | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4> |
| Genesis issue | <https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183> |
| Genesis PR | <https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184> |
| Genesis bounded validation | <https://github.com/eason4kim-rocket/look-twice/blob/v8-competition-final-2026-08-05/docs/V8_GENESIS_PR_3184_VALIDATION.md> |
| Competition-fork package | <https://github.com/eason4kim-rocket/Radeon-hackathon-2026-07/tree/submission/track3-liu-liang-look-twice-v8/submissions/Track3-Liu-Liang-Look-Twice> |

The homepage social card and native browser playback of the complete 3:59 demo
are published and anonymously verified. The last non-self-referential source
content receipt `9164d13b66a4e699dc183be3c6238485e509d1e9` is public on default
branch `v8-contract-progress-nbv`; the later seal-only commit records these
publication receipts. GitHub Pages commit
`ab1d8df2a5b173ff57258f197ec38886561d98cb` was deployed by successful
Actions run `31071921133`; the personal-fork package is public at
`70797708f562d10f5b170ce938f4b085fdd98bcb`; and the mirror is Sites version
16 from source commit `1c9bab9ffc97e6b5f4c6928e4445737108f9c7b6` at
<https://look-twice-evidence.jason-tuantuan1319.chatgpt.site/>. Both public
sites return the full MP4 as `video/mp4`; GitHub Pages supports byte ranges,
and anonymous downloads match SHA256
`70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`.
The social card and report were also anonymously hash-verified. The stable
Release asset remains the download/hash mirror. Genesis issue #3183 and PR
#3184 are public; the PR is open and unmerged. A
post-publication bounded serial-CPU run passed 3/3 named regression nodes at
its exact head; it is not a full-suite or maintainer-CI claim. No PR has been
opened against the official AMD competition repository.

## Handoff map

1. Owner-review checklist: `docs/SUBMISSION_CHECKLIST.md`
2. Owner-review English PR-body draft: `docs/SUBMISSION_DRAFT.md`; immediately
   before filing, replace its preparation-state preamble with the actual
   publication state and rerun the stale-state scan.
3. Submission manifest: `submission/V8_SUBMISSION_MANIFEST.json`
4. Official-repository directory:
   `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/`
5. Technical report source: `docs/V8_TECHNICAL_REPORT.md`
6. Detailed reproduction guide: `docs/V8_REPRODUCTION.md`
7. Final demo specification: `docs/V8_DEMO_SCRIPT.md`
8. Preregistered challenge Judge Card:
   `docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md`
9. Additive compound contract-progress result and evidence:
   `docs/V8_CONTRACT_PROGRESS_CHALLENGE_RESULT.md` and
   `release/v8-derived/contract_progress_challenge_102530_102549/`
10. Additive dynamics result and recovery note:
   `docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_RESULT.md`
11. Retained decision-bound dynamics recovery V2 result and evidence:
    `docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md` and
    `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/`
12. Two-shard decision-bound protocols and evidence:
    `docs/V8_ADDITIVE_DECISION_DYNAMICS_60_PROTOCOL.md`,
    `docs/V8_ADDITIVE_DECISION_DYNAMICS_30_SUFFIX_PROTOCOL.md`,
    `release/v8-derived/decision_dynamics_single_scene_60_102500_102519/`,
    and
    `release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529/`
13. Published Genesis upstream contribution:
    issue [#3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183)
    and open, non-draft PR
    [#3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184) at
    exact head `0fa0f4ae5c83e964282fea1d6ad44aa333ee1850`.

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
| Compound challenge report | `release/v8-derived/contract_progress_challenge_102530_102549/formal_run/REPORT.json` | 20 worlds / 40 cells; `promotion_pass=true`; `8dc2d5026f697312bd39ddf6be7a65aa3ee08ac0e2799d0ca24cf4348c439a44` |
| Compound challenge verification | `release/v8-derived/contract_progress_challenge_102530_102549/formal_run/VERIFICATION.json` | `911495a29a51b0eb6d64c85e231e51a28713b570431b4f7dfffb60806dfb76be` |
| Compound challenge telemetry | `release/v8-derived/contract_progress_challenge_102530_102549/formal_run/ROCM_TELEMETRY.json` | 554 samples; full-window coverage valid; `11e7442fa7b1c606f6951fc4e1655ce17452eb539841ddbc5f5941ea6f71ec6a` |
| Compound challenge run manifest | `release/v8-derived/contract_progress_challenge_102530_102549/formal_run/RUN_MANIFEST.json` | `d5fc5402656739d95bd5845592499a3382734b27fc89ef0b886c0544461c948e` |
| Additive dual-body report | `release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json` | `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110` |
| Dual-body timeout audit | `release/v8-derived/dual_body_dynamics_160820_160839/ATTEMPT_1_TIMEOUT_AUDIT.json` | `711547fb5f0ab928ae5cc8b6195f4e0e964a98f6df44dfa2955c67e624705d55` |
| Dual-body recovery audit | `release/v8-derived/dual_body_dynamics_160820_160839/RECOVERY_EXECUTION_AUDIT.json` | `6c3ddfa0ec2b482c1ab01a160572d01451f0bb1b495137e09a18a96018f23e6e` |
| Retained historical decision-bound V2 report | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json` | `1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99` |
| Retained historical V2 recovery audit | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/RECOVERY_EXECUTION_AUDIT.json` | `344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4` |
| Retained historical V2 provenance review | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json` | `4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7` |
| Retained historical V2 package index | `release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PACKAGE_SHA256SUMS` | 79 indexed evidence files; index SHA256 `24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540` |
| Two-shard 60-body prefix report | `release/v8-derived/decision_dynamics_single_scene_60_102500_102519/REPORT.json` | 20/20; `3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450` |
| Two-shard 30-body suffix report | `release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529/REPORT.json` | 10/10; `69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e` |
| Rendered technical report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` | 19 pages; 1,104,864 bytes; SHA256 `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`; 19/19 visual QA; output/site/official copies byte-identical |
| Contract-progress social card | `showcase/public/og-contract-progress.png` | `68f2f3e4f4b769edceb08c28d73440c5a1a80008bec267ea3a524d69d3213b1a`; disclosed simulation-only conceptual artwork, not an experiment capture |
| 30-second evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` | `46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2` |
| 13-second 1080p judge motion hook | `showcase/public/media/look-twice-repair-to-action-proof.mp4` | Recorded simulation excerpt; repair → dual admission → direct motion → final result; `a2fd07abfc59187e170d1151981c0d9225ca08bb20410ebf26e26729d61aaeb0` |
| Final 3:59 demo | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/Look-Twice-V8-Demo.mp4` | `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05` |
| Official PR body | `docs/SUBMISSION_DRAFT.md` | English, target URLs complete |
| Official-repo package | `submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/` | Published personal-fork package at `70797708f562d10f5b170ce938f4b085fdd98bcb`: 158 manifest entries, 159/159 checksum entries, and 160 total files; top-level checksum-index SHA256 `daaaab06a5a82b805b85581519a354f7206224a5891b6687e124f14d7cf6d4a8`; official PR not opened |

## Frozen checkpoint

- SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Size: 159,592,901 bytes.
- Public target: the `v8-competition-candidate` release asset linked above.
- The unchanged checkpoint asset remained available at the stable URL and its
  published SHA256 identity was rechecked.

## Verified local commands

The following core checks passed during submission preparation; the final
two-shard refresh checks were completed on 2026-08-05:

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

The refreshed Evidence Console passed **44/44** tests, lint, production build,
and a zero-vulnerability dependency audit. The homepage social card and native
playback of the complete 3:59 MP4 are published to GitHub Pages and the public
mirror and were anonymously verified at `2026-08-06T02:53:18Z`. Its
contract-progress social card
hashes to
`68f2f3e4f4b769edceb08c28d73440c5a1a80008bec267ea3a524d69d3213b1a`;
the card is disclosed simulation-only explanatory artwork, not an experiment
capture, simulator frame, or screenshot.

The frozen verifier reported all 21 guarded files green, and the task-utility
derivation matched the fixed locked and
confirmatory source hashes without reopening the test. The input-pack verifier
also checked the real 400-world archive without extracting it or running the
model; the formal telemetry run did not access the locked split. The 31
challenge runner/validator tests passed; together with the three telemetry
helper tests, 34 combined tests passed. The independent validator recomputed
the 30-pair result from the full 195-file raw archive with zero errors.

The retained recovery V2 verifier accepted its byte-identical 30/30 report
remotely and locally. The two-shard prefix and suffix dedicated verifiers
accepted **20/20** and **10/10**, and both shards' formal and complete package
indexes passed. The final official-directory finalizer `--check` passed, as did
all **159** entries in its top-level `SHA256SUMS`:

```bash
python3 scripts/verify_v8_additive_decision_dynamics_60.py \
  release/v8-derived/decision_dynamics_single_scene_60_102500_102519/REPORT.json
python3 scripts/verify_v8_additive_decision_dynamics_30_suffix.py \
  release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529/REPORT.json
python3 scripts/finalize_v8_submission_package.py --check
cd submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice
shasum -a 256 -c SHA256SUMS
```

The final contract-progress-integrated report is **19 pages**, **1,104,864
bytes**, and has SHA256
`7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`.
All 19/19 rendered pages passed visual QA, and the canonical output, site copy,
and official-package copy are byte-identical.

The final demo render is 239.000 seconds and 9,032,035 bytes. Its SHA256 is
`70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`;
the builder sidecar SHA256 is
`639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb`.
Narration is an AI-generated `cedar` voice from OpenAI
`gpt-4o-mini-tts`; that disclosure is burned into the video. Chapter visuals
use fixed composition with no `zoompan` motion.

The complete MP4 is published for native browser playback at both Evidence
Console deployments. Both returned `video/mp4` without authentication, GitHub
Pages accepted a byte-range request, and both public copies matched the SHA256
above. The stable GitHub Release URL remains the download/hash mirror.

## Evidence boundary

Only V8 is submitted. The locked aggregate, input-only pre-open supplement,
non-locked seed-105400 replay, preregistered same-generator challenge, and two
Radeon telemetry classes remain explicitly separated. The input supplement
lacks the original one-shot predictions and 24 raw locked live episodes; it
cannot reconstruct or recompute the permanent result. Seeds 102500-102529 were
evaluated once per policy in the frozen challenge. Seeds 102530-102549 were
separately evaluated once per policy in the compound challenge. Both are
same-generator, non-locked supplements, not V8 OOD evidence; seeds
102550-102699 remain unevaluated. Challenge Python/Go receipt
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

The earlier decision-bound recovery V2 remains a separately frozen additive
supplement. It consumes archived decisions in 30 independent three-body scenes;
it does not rerun the frozen policy and its 90 distinct bodies were not
simultaneous. Its retained ledger and logs show 30 first-attempt worker
completions, no completed-checkpoint rerun, and no seed replacement. However,
the formal checksum index did not originally cover attempts/progress/logs, and
the formal source manifest omitted the directly imported `src/v4_motion.py`.
The post-run tree audit and complete package index corroborate the retained
record; they are not cryptographic proof of continuous no-retry execution or a
fully bound runtime dependency closure.

The current two-shard complement changes only the solver-scale execution
topology: one 60-body scene covers 20 seeds and one 30-body scene covers the
remaining 10. It binds two complete, independently verified reports into a
30-seed claim; it does not claim that all 90 bodies were co-resident, that state
was resumed across shards, or that the two scenes form one simulator result.
The same archived decisions and preregistered active **29/30** endpoint remain
unchanged. This complement is likewise non-locked, simulation-only, and
`formal_result_eligible=false`.

A focused Genesis URDF inertial-origin patch is public at commit
`0fa0f4ae5c83e964282fea1d6ad44aa333ee1850` through issue #3183 and open,
non-draft PR #3184. It is not part of the sealed competition evidence result,
remains unmerged, and carries no claim of maintainer review, acceptance, or
upstream-release inclusion.

## Final owner-review gate

- [ ] Confirm the registered entrant/team label and eligibility items.
- [ ] Inspect the final 3:59 MP4 visually and audibly; its verified SHA256,
      size, streams, and duration are already recorded in
      `V8_SUBMISSION_MANIFEST.json`.
- [x] Regenerate and verify the official-directory `SHA256SUMS` after every
      final artifact is in place.
- [x] Publish and anonymously verify the refreshed source, browser-playable
      full demo, evidence site, public mirror, and personal-fork package;
      receipts were recorded at `2026-08-06T02:53:18Z`.
- [ ] Review both complete two-shard evidence packages and their dedicated
      verifier/checksum records; automated verification is already green.
- [x] Rebuild the contract-progress-integrated technical report, verify its
      final identity across output/site/official copies, and inspect all 19/19
      rendered pages.
- [x] Run the contract-progress-integrated site tests, lint, production build,
      and dependency audit: 44/44, pass, pass, and zero known vulnerabilities.
- [ ] Complete owner visual review of the published Results/Reproduce refresh;
      automated local Chrome QA has already passed desktop English/Chinese and
      true 390 px mobile layouts with no horizontal overflow.
- [x] Regenerate and verify the contract-progress-integrated official-package
      manifest and every top-level checksum entry; record the final counts and
      checksum-index identity mechanically.
- [x] Publish the current homepage/demo/source/site/package refresh and verify
      every stable target without sign-in.
- [ ] Review the official-fork branch diff and the English PR body.
- [x] Review the Genesis issue/PR packet and authorize upstream publication;
      issue #3183 and PR #3184 are public.
- [ ] Explicitly authorize opening the official competition PR.
