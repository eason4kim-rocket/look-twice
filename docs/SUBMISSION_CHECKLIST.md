# Look Twice V8 Competition Submission Checklist

Verified against the official event page, governing Rules and Conditions, and
official submission repository on 2026-08-05.

**Owner-review state:** `public_surfaces_ready_competition_pr_held_for_owner`

**Official PR opened:** `false`

**Confirmed entrant/team:** `Liu Liang` (solo entrant; GitHub:
`@eason4kim-rocket`)

## Governing facts

- [x] Track: Track 3 - Physical AI.
- [x] Deadline: 2026-08-06 23:59 UTC+8.
- [x] All submission materials, project descriptions, and the official PR are
      in English.
- [x] Required: technical report, dedicated source repository, detailed
      reproducibility README, and demonstration video.
- [x] Recommended video length: 3-5 minutes.
- [x] Preferred but not mandatory: complete Docker image/path.
- [x] PR title format: `Track 3, <team or entrant>, Look Twice`.

Official sources:

- https://huggingface.co/blog/LeRobot-worldwide-hackathon/amd-ai-devmaster
- https://luma.com/amd-4dhi
- https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07

## Eligibility and identity - owner confirmation

- [ ] Confirm Luma registration approval.
- [ ] Confirm AMD Developer Program membership for prize eligibility.
- [ ] Confirm entrant is at least 18 or the age of majority.
- [x] Confirm `Liu Liang` is the registered solo entrant/team label.
- [x] Do not print the registration email in the PR body, report, packaged
      submission files, video, or evidence site. Existing Git history metadata
      already contains it, so use the account's GitHub noreply identity for new
      submission commits rather than claiming the full repository history is
      private.
- [ ] Confirm the registration email and phone are monitored for seven days
      after judging.

## Positioning and evidence discipline

- [x] Position Look Twice as an evidence-assurance boundary immediately before
      action, complementary to perception, planning, and simulation.
- [x] Lead with the locked paired capability result: active direct 11/12 versus
      passive direct 0/12, a +91.7 percentage-point gain.
- [x] Present the preregistered 30-world challenge as an additive
      same-generator non-locked supplement: active full-chain direct 29/30
      versus passive 0/30, a +96.7 percentage-point paired gain.
- [x] Keep active 29/30 versus passive 0/30 as the preregistered primary
      endpoint; never relabel it as 30/30 from a later dynamics replay.
- [x] Retain the one conservative active detour in the denominator.
- [x] State that the paired result is descriptive for the fixed 12-world suite,
      not a population or real-world generalization.
- [x] Retain challenge seed 102515 as the sole active non-direct case and state
      that it completed safely by detour.
- [x] Publish the post-hoc descriptive oracle-feasibility audit separately:
      29/29 oracle-clear worlds direct via a clear corridor, 1/1 dual-blocked
      world safely detoured, and 30/30 active route outcomes matched offline
      feasibility. Keep oracle unavailable to the controller and retain the
      formal 29/30 preregistered endpoint.
- [x] State the non-locked seed-105400 application-value finding narrowly:
      loaded-carrier travel -23.24% through scout burden transfer.
- [x] Disclose that seed 105400 total robot travel increased 24.32% and does
      not support a total-distance or latency reduction claim.
- [x] Keep locked aggregate, input-only supplement, non-locked replay, and
      model-forward benchmark/telemetry scopes visibly separate.
- [x] Keep the preregistered challenge and its full-subprocess-wall telemetry
      separate from the locked aggregate, replay, and synthetic model-forward
      telemetry.
- [x] State that seeds 102500-102529 were evaluated once in the additive
      same-generator non-locked challenge; seeds 102530-102549 were separately
      evaluated once per policy in the public-before-run compound challenge;
      seeds 102550-102699 remain unevaluated. None is V8 OOD evidence.
- [x] Present the compound challenge as a complete-system intervention only:
      shared frozen seg-v3 dual ROI, physical-root unification, and
      contract-progress NBV; do not attribute its result to one component.
- [x] Carry the compound result exactly: direct 20/20 for both arms, scout path
      -40.2563%, team path -15.0306%, physical captures -27.5362%, 40/40
      missions, and zero unsafe/collision/fallback/false-clear outcomes.
- [x] Carry all three deterministic paired-bootstrap 95% intervals and retain
      `formal_result_eligible=false`, same-generator, non-locked, non-OOD,
      kinematic, and non-physical-robot boundaries.
- [x] Disclose receipt-level Python/Go agreement as 250/268 (93.3%) and all 18
      mismatches as Go vetoes with `effective_admit=false`.
- [x] Label the mismatch localization as post-hoc descriptive: all 18 were
      active corridor-B evaluations with one qualifying Go root and
      `{clear, blocked}`; no selected crossing was authorized by a mismatch.
- [x] Disclose that the frozen policy realizes carrier and scout as two logical
      roles on one shared Genesis chassis.
- [x] Keep the separate 20-seed dual-body rigid-dynamics supplement additive,
      non-locked, and `formal_result_eligible=false`; do not relabel it as a
      frozen-policy rerun, simultaneous cooperative control, or real robot.
- [x] Report the fixed dynamics denominator exactly: 20/20 seeds, 40 non-fixed
      entities, zero counted blocker/pair contact rows, and zero post-build pose
      writes.
- [x] Retain the 3,600-second infrastructure-timeout audit and disclose that
      recovery changed only the outer watchdog to 10,800 seconds, with no seed
      result observed, retried, replaced, or resampled.
- [x] Present decision-bound recovery V2 as a separate additive, non-locked,
      simulation-only archived-decision replay: 30/30 fixed seeds across 30
      independent three-body scenes, not one simultaneous 90-body scene.
- [x] Report the V2 denominator and result exactly: 90 distinct non-fixed robot
      instantiations across the run, all reached; 29 direct decisions plus one
      safe detour; paired loaded-carrier path reduction 20.8183%; zero
      blocker-contact and active-pair-contact rows; zero post-build pose writes.
- [x] State that V2 consumes archived challenge decisions without rerunning the
      perception-policy loop and does not demonstrate simultaneous cooperative
      control, dynamic-obstacle response, a physical robot, sim-to-real, or a
      safety-certified system.
- [x] Disclose the V2 proof scope: the formal checksum index did not originally
      bind attempts/progress/logs, and the formal source manifest omitted the
      directly imported `src/v4_motion.py`. Treat the post-run tree audit and
      complete package index as corroboration, not cryptographic proof of no
      retry or a fully bound dependency closure.
- [x] Present the solver-scale complement as two independent archived-decision
      reports: 20/20 fixed decisions in one 60-body scene and 10/10 in a second
      30-body scene.
- [x] State the combined topology exactly: **exactly two scenes**, 90
      cumulative distinct non-fixed robots, maximum co-resident 60, and never
      all 90 co-resident. Do not call it a 90-body scene or one fleet run.
- [x] Report the two-shard outcome exactly: all 30 scouts, 30 active carriers,
      and 30 passive carriers reached; 29/29 direct pairs saved at least 0.50 m;
      seed `102515` completed its safe detour; weighted active/passive path
      4.943605/6.245385 m (20.8439% reduction); zero counted blocker/active-pair
      contacts and post-build pose writes; maximum tilt/drift
      10.583984 degrees/0.021342 m.
- [x] Keep both solver-scale shards additive, non-locked,
      `formal_result_eligible=false`, fixed-order serial, and simulation-only.
      Do not present them as a live policy rerun, simultaneous fleet control,
      dynamic-obstacle, physical-robot, sim-to-real, energy, throughput,
      latency, or safety-certification evidence.
- [x] Preserve the failed V1 all-90-body history and never relabel the two-shard
      success as completion of that one-scene attempt.
- [x] State the aggregate challenge task ledger in both directions:
      loaded-carrier logical path -22.5%, total logical-role team path +24.0%.
- [x] State simulation-only, kinematic-motion, and no-safety-certification
      boundaries.
- [x] Make no public external upstream PR claim before owner approval; after
      approval, publish only the truthful open/unmerged issue and PR state.

## V8 evidence freeze

- [x] Candidate is `v8-frozen`.
- [x] V8 runtime, checkpoint, conformal artifacts, Purify binary, and locked
      report identities are frozen.
- [x] Locked test opened once.
- [x] Locked result passed with no retune, refit, or vision retraining.
- [x] Failed and non-promoted research is preserved.
- [x] R1/R2/V9 research is excluded from V8 headline claims.
- [x] Public replay is labeled non-locked confirmatory evidence.
- [x] Perfect classification metrics are labeled decisive-set metrics; 199
      non-decisive samples remain visible.
- [x] Deterministic task-utility derivation verifies locked and confirmatory
      source hashes without rerunning V8 or reopening the test.
- [x] Verify the pre-open 400-world input-and-label archive without extraction
      or inference; disclose that original predictions and 24 raw episodes are
      not present and were not regenerated.
- [x] Publicly bind the finalized challenge protocol, runner, validator, seed
      schedule, endpoints, and frozen identities before execution.
- [x] Run all 60 preregistered challenge cells exactly once with zero retries,
      replacement seeds, early stopping, retuning, or threshold changes.
- [x] Preserve and recursively checksum all 60 raw challenge episodes and
      every other emitted result file.
- [x] Independently recompute and verify the complete challenge report with
      zero validation errors.
- [x] Fix dual-body smoke seeds and confirmatory seeds before the formal run;
      exclude all three engineering-smoke seeds.
- [x] Run the fixed 20-seed dual-body bar on AMD ROCm: 20/20 passed, failed
      list empty, process exit 0.
- [x] Verify the byte-identical dual-body report both remotely and locally.
- [x] Seal report, timeout audit, recovery audit, and directory checksums at
      report SHA256 `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110`.
- [x] Fix the recovery V2 protocol before formal execution and preserve the
      failed V1 history without relabeling its timeouts as scientific results.
- [x] Verify the byte-identical V2 report remotely and locally: 30/30, report
      SHA256 `1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99`.
- [x] Preserve all 30 V2 checkpoints, the attempt ledger, worker logs, recovery
      audit, provenance review, and both formal and complete-package checksum
      indexes for owner review.
- [x] Freeze and verify the 60-body prefix: 20/20, report SHA256
      `3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450`,
      dedicated verifier pass, and both checksum indexes pass.
- [x] Freeze and verify the 30-body suffix: 10/10, report SHA256
      `69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e`,
      dedicated verifier pass, and both checksum indexes pass.
- [x] Confirm the two reports cover disjoint fixed seed ranges
      `102500-102519` and `102520-102529`, use distinct scene identities, and
      have no cross-shard resume or result stitching.

## English submission materials

- [x] Root V8 README with a 90-second judge path.
- [x] Compact frozen-challenge Judge Card with the public-before-execution
      binding, result, safety, AMD execution, task trade, two-shard complement,
      and honest scope.
- [x] V8 technical report source in `docs/V8_TECHNICAL_REPORT.md`, updated with
      the independently verified two-shard result and boundary.
- [x] Retain the rendered 15-page V2-integrated report PDF as the previous
      pre-two-shard snapshot.
- [x] Preserve the prior two-shard 18-page report identity only as a
      superseded historical snapshot; it is not the current submission PDF.
- [x] Rebuild the contract-progress-integrated technical report as a 19-page
      PDF; record 1,104,864 bytes and SHA256
      `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`;
      complete rendered page-by-page visual QA for all 19/19 pages.
- [x] Verify the canonical output, site copy, and official-package copy are
      byte-identical at the final 19-page SHA256.
- [x] Detailed V8 reproduction guide, including independent checksum/verifier
      commands for both solver-scale shards.
- [x] AMD environment and workload boundary.
- [x] Evidence claim boundary.
- [x] Exact English official PR body draft with stable target URLs.
- [x] English 3:59 video script aligned to the deterministic builder and its
      exact nine-chapter narration inputs.
- [x] Complete the final 239-second English demo MP4 render and local QA.
- [ ] Complete owner visual and audible review of the final MP4.
- [x] Recorded 30-second evidence reel.
- [x] English-default Evidence Console build.
- [x] Owner-review artifact manifest and handoff index.
- [x] Refresh the self-contained official-repository staging directory with
      the locally verified 3:59 demo, sidecar, identities, and judge-facing
      README.
- [x] Record the 239-second video and sidecar identities in the submission
      manifest.
- [x] Regenerate the final local `SHA256SUMS` and verify all 104 checksummed
      artifacts (105 total files including `SHA256SUMS`) for the prior V2-only
      staging snapshot; verify that its machine manifest inventories all 103
      payload files in its scope.
- [x] Integrate the V2 result note and complete 80-file locally indexed
      evidence directory.
- [ ] Owner reviews the contract-progress-integrated technical-report source
      and staged 19-page PDF, including its identity and 19/19 visual-QA
      record.
- [ ] Owner completes final browser review of the staged contract-progress
      Results/Reproduce presentation; code/test/build/lint/audit checks are
      complete, and publication is in progress.
- [ ] Owner reviews the complete V2 and two-shard evidence payload in local
      official-package staging, the finalized top-level manifests, and the
      exact package diff.
- [x] Integrate the 60-body prefix and 30-body suffix claims into the root
      README, Judge Card, evidence boundary, technical-report source,
      reproduction guide, PR draft, and this checklist.
- [x] Integrate both sealed solver-scale evidence directories into the local
      site and official-package staging; preserve their internal checksum
      indexes and dedicated verifier passes.
- [x] Run the official-package finalizer at `2026-08-06T02:32:52Z` and write
      the current unsealed top-level machine manifests, checksum index, file
      counts, and package identity; its subsequent `--check` passes.
- [x] Record 155 manifest inventory entries, 156 checksum entries, and 157
      total regular files including `SHA256SUMS`; all 156 `shasum` checks pass.
      The top-level `SHA256SUMS` SHA256 is
      `433b00485399a8794a55c294cf662d5273784e3e65f54b7b93af48d2c87297f6`.
- [ ] Owner reviews the two-shard Results/Reproduce presentation, rebuilt PDF,
      official-package diff, and exact `cumulative90/max60/never90` wording.

## Reproducibility

- [x] Prior public baseline: push the 239-second demo, hash-pinned narration
      provenance, and its then-current review documentation to
      `v8-competition-release`.
- [x] Verify the updated final branch HEAD from an anonymous clean clone.
- [x] Publish the 159 MB V8 checkpoint at the stable release URL.
- [x] Download the public checkpoint without credentials and verify its SHA256.
- [x] Clean-clone the public branch in a new directory.
- [x] Reproduce the frozen local submission commit in a clean detached
      worktree before publication.
- [x] Run the CPU replay build and frozen-boundary verifier in the release
      worktree.
- [x] Run all six competition replay Python tests.
- [x] Run the deterministic task-utility derivation and verify its SHA256.
- [x] Run all five locked-input verifier tests and all three ROCm telemetry
      helper tests.
- [x] Run all 31 challenge runner/validator tests; together with the three
      ROCm telemetry helper tests, 34 combined tests passed. Preserve the
      frozen runner and validator source identities.
- [x] Reproduce the challenge validator output from the public raw archive in
      a clean local extraction; verification SHA256
      `942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940`.
- [x] Stream-verify the real 1,019,307,579-byte locked input archive: 400
      worlds, 3,200 metadata records, no extraction, no inference.
- [x] Run `go test ./...` for the Purify reference core.
- [x] Add exact ROCm dependency and environment preflight files.
- [x] Build and route-smoke the Evidence Console with Docker.
- [x] Lint, production-build, and run all 38 Evidence Console tests with Node
      22 after the two-shard Results/Reproduce integration.
- [x] Pin patched Web dependencies and obtain zero known `npm audit`
      vulnerabilities. The refreshed site remains local and undeployed;
      owner browser review is still required.
- [x] Run all seven additive dynamics unit/verifier tests and Ruff checks.
- [x] Run the recovery V2 report verifier on the Radeon host and on the
      byte-identical local report; both accepted the 30/30 report SHA.
- [x] Verify both solver-scale evidence directories locally: formal and package
      checksum indexes pass, the 60-body verifier accepts 20/20, and the
      30-body suffix verifier accepts 10/10.
- [x] Independently recompute the exact weighted two-shard summary from the
      fixed 20+10 denominators: active/passive 4.943605/6.245385 m and 20.8439%
      reduction; do not create or imply a synthetic combined report.
- [ ] Owner reruns the formal and complete-package checksum indexes plus the V2
      local verifier from the final integrated review tree.
- [ ] Owner reruns both solver-scale checksum suites and dedicated verifiers
      from the final integrated review tree.
- [ ] Verify every README command exactly as written from the public clean
      clone.

## AMD Radeon evidence

- [x] Frozen environment records Genesis, PyTorch, HIP/ROCm, and GPU identity.
- [x] GPU/CPU workload boundary is documented.
- [x] Run and archive a hash-pinned frozen-model V8 inference benchmark.
- [x] Record p50, p95, throughput, peak allocated memory, warm-up, measurement
      count, and exact checkpoint SHA in one machine-readable report.
- [x] State that the benchmark uses preloaded synthetic tensors and measures
      model forward only, not end-to-end robot latency.
- [x] Do not quote V4-V7 performance as V8 performance.
- [x] Archive a clean-preflight 60-second exact-checkpoint ROCm telemetry run.
- [x] Limit the 61/61 100%-GPU-use claim to the disclosed synthetic,
      preloaded FP32 model-forward window; do not call it end-to-end.
- [x] Archive a separate full-subprocess-wall challenge telemetry record: 844
      two-second samples across 1,685.5 seconds for all 60 episodes, including
      idle.
- [x] Limit that broader record to complete Python + Genesis live RGB-D +
      frozen checkpoint + Purify Go subprocess execution; do not call it
      control-loop latency, mission energy, or physical duty cycle.
- [x] Archive the separate 4,299.992-second dual-body Radeon acceptance run and
      bind Genesis, PyTorch, HIP, GPU, runner, and URDF identities.
- [x] State that the dynamics execution is an acceptance bar, not throughput,
      mission energy, control-loop latency, or a physical-device benchmark.
- [x] Archive the separate recovery V2 execution as 30 fresh Genesis
      subprocesses on AMD ROCm; keep its 1,101-second wall time as an
      engineering record, not throughput or latency evidence.
- [x] Archive the single-scene 60-body Radeon execution and independently
      verified 20/20 report; limit the claim to one scene, fixed-order serial
      actuation, and 60 co-resident bodies.
- [x] Archive the second-scene 30-body Radeon suffix execution and independently
      verified 10/10 report; limit the combined statement to exactly two
      scenes, cumulative 90 distinct robots, maximum co-resident 60, and never
      all 90 co-resident.
- [x] Treat both solver-scale body counts and execution walls as acceptance and
      topology facts, not GPU throughput, latency, utilization, or energy
      benchmarks.

## Website and public URLs

Stable targets:

- Evidence Console: https://eason4kim-rocket.github.io/
- Results: https://eason4kim-rocket.github.io/results
- Reproduction: https://eason4kim-rocket.github.io/reproduce
- Frozen-primary source branch:
  https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release
- Additive contract-progress source/evidence branch:
  https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv
- Immutable final source:
  https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-final-2026-08-05
- Candidate release:
  https://github.com/eason4kim-rocket/look-twice/releases/tag/v8-competition-candidate

- [x] Prepared English root, `/console`, `/results`, and `/reproduce` routes.
- [x] Results contains the complete locked offline/live metrics, +91.7 pp
      paired result, and separate seed-105400 cost ledger.
- [x] Results contains the exact AMD execution evidence and scope boundary.
- [x] Results contains the input-only locked archive and 60-second telemetry
      supplements, with missing-output and non-OOD boundaries visible.
- [x] Prepare a separate dual-body Results card sourced from byte-identical
      report and audit copies, while preserving the frozen shared-chassis
      boundary.
- [x] Site links the stable report, source branch, checkpoint, and video
      targets. The published contract-progress-integrated report is 19 pages
      with SHA256
      `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`;
      the stable release asset was replaced and anonymously hash-verified.
- [x] Results and the global footer expose the immutable final-source tag,
      exact Genesis issue/PR head, personal competition-fork head, final PDF
      identity, and an explicit no-merge/no-acceptance boundary.
- [x] Rebuild, lint, run all 44 tests, and obtain a zero-vulnerability
      dependency audit for the full-demo-integrated site.
- [ ] Publish that verified build to GitHub Pages and the public site mirror;
      publication is in progress.
- [ ] Owner reviews the separate 30/30 decision-bound V2 Results card and
      reproduction audit, including the 29/30 primary endpoint and the
      non-simultaneous 90-body boundary, after all site checks pass.
- [x] Add a distinct solver-scale two-shard Results card and Reproduce audit;
      keep V2 separate and show 20/20 at 60 co-resident plus 10/10 at 30
      co-resident, exactly two scenes, cumulative 90, maximum 60, never 90.
- [x] Add six byte-identical report/checksum public-data copies to the local
      site tree for the two sealed shards, and cover disjoint seeds, distinct
      scenes, 60/30 body counts, cumulative 90, maximum 60, and
      `all_90_co_resident=false` in the evidence tests.
- [x] Run site lint, production build, all 44 tests, and dependency audit after
      the full-demo integration.
- [ ] Complete owner browser review of the staged Results/Reproduce/full-demo presentation.
- [ ] Publish the refreshed homepage and full-demo site; publication is in progress.
- [x] Keep HTTPS enforced on the refreshed GitHub Pages deployment.
- [x] Verify `/`, `/console`, `/results`, `/reproduce`, the report PDF, and
      referenced evidence assets without sign-in on the public deployments.
- [x] Replace the MP4 and sidecar at the unchanged candidate-release URLs.
- [x] Download the replacement assets without sign-in and verify both hashes.

## Final video

- [x] Builder uses only V8 competition artifacts, not historical V2/V3 media.
- [x] Timeline is exactly 239 seconds (3:59), within the 3-5 minute target.
- [x] Script contains English narration and English on-screen text.
- [x] Narration uses hash-pinned OpenAI `gpt-4o-mini-tts` audio with voice
      `cedar`.
- [x] The closing card discloses
      `AI-GENERATED NARRATION · OPENAI TEXT-TO-SPEECH`, and the sidecar records
      provider, model, voice, and source provenance.
- [x] Fixed-composition evidence slides remove `zoompan` and other synthetic
      camera drift; recorded replay and audit footage retain native motion.
- [x] Active replay is permanently labeled
      `NON-LOCKED CONFIRMATORY REPLAY · SEED 105400`.
- [x] Script shows active and passive evidence paths, locked metrics, recorded
      Radeon/ROCm evidence, and a real CPU audit terminal capture.
- [x] Script states `Simulation only` and the model-forward timing boundary.
- [x] Script uses sanitized terminal prompts and excludes SSH details, private
      paths, tokens, unique device IDs, and local usernames.
- [x] Complete the final local render and media QA.
- [x] Verify 1920 x 1080 H.264, 30 fps, `yuv420p`, AAC audio, and 239-second
      duration with `ffprobe`.
- [x] Inspect representative frames across all nine chapters.
- [ ] Complete owner listening review of the full narration.
- [x] Confirm the 9,032,035-byte MP4 is below the release/package size limit.
- [x] Record MP4 SHA256
      `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05`
      and sidecar SHA256
      `639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb`.
- [x] Complete local format, decode, frame, audio, evidence-label, and privacy
      QA for this exact identity.
- [x] Replace the earlier assets at the stable no-sign-in URL and verify the
      downloaded MP4 and sidecar hashes.

## IP, privacy, and repository hygiene

- [x] Apache-2.0 license present.
- [x] `NOTICE` defines the V8 contest reference-core boundary.
- [ ] Re-read the final IP/license clauses before submission.
- [x] Search judge-facing/public surfaces for SSH commands, credentials,
      private paths, internal APIs, databases, connectors, and commercial
      modules; remove transfer-only host records.
- [x] Review the submission PDF, preview MP4, social PNG, frozen Go binary, and
      other large tracked artifacts by file type and identity.
- [ ] Confirm all datasets and assets have legal, licensing, and ethical use.
- [x] Repeat metadata/privacy inspection for the final 3:59 video.

## Genesis upstream contribution

- [x] Reproduce the omitted-URDF-inertial-origin bug on official Genesis
      `main` and identify the parser/finalization boundary.
- [x] Implement a two-file minimal fix: missing origin on an existing inertial
      becomes the identity transform; a fully absent inertial keeps the
      geometry fallback.
- [x] Add a `required` parser regression test covering mass, identity inertial
      frame, and a non-diagonal symmetric inertia tensor.
- [x] Record official-main failure and patch success; run Ruff check, Ruff
      format check, and `git diff --check`.
- [x] Search open and closed Genesis issues/PRs for exact duplicates.
- [x] Prepare exact English issue body, PR body, validation record, and
      publication sequence locally.
- [x] Re-fetch upstream main on 2026-08-05, replay the identical patch without
      conflict, and publish the validated replay at commit
      `0fa0f4ae5c83e964282fea1d6ad44aa333ee1850`; its
      stable patch-id matches the earlier `31b58c4` review commit.
- [x] Identify merged PR #2499 as the related prior change and position this
      patch as a narrow follow-up to the current parser/finalizer regression,
      not an unacknowledged duplicate.
- [x] Confirm GitHub authentication and the pre-publication absence of a
      personal Genesis fork, issue, branch, or PR.
- [x] Owner explicitly authorized external upstream publication.
- [x] Re-fetch official main, repeat duplicate search, file public
      [issue #3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183),
      push the exact patch to the fork, and open non-draft
      [PR #3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184).
- [x] Update judging materials with the real open/unmerged issue/PR URLs and
      observed CI state; do not claim merge or acceptance.
- [x] Run a bounded serial CPU mini-regression at exact PR head `0fa0f4a`:
      3/3 selected URDF-loading boundary nodes passed; publish the exact
      identities and state that neither a full suite nor maintainer CI is
      claimed.

## Official submission repository

- [x] Fork `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`.
- [x] Stage an English submission directory locally containing the judge-facing
      index, report PDF, compact evidence, and preview.
- [x] Add the locally verified demo artifact and unchanged stable target URL.
- [x] Preserve the prior V2-only staging snapshot with its 15-page report,
      four-file dual-body report/recovery chain, and complete 80-file
      decision-bound recovery V2 evidence directory.
- [x] Record the prior V2-only snapshot's 104 local checksum entries (105 total
      files including `SHA256SUMS`); checksum-index SHA256
      `e3fee90381052e4b8fe28ca937736292ae5dee670ef30e1abf0b6a258fdc63f9`.
- [x] Preserve the previously published official-fork baseline at commit
      `32cff1a1e77952e689f4730ff21b8a8a8ad01a63` without opening a PR.
- [x] Add the complete decision-bound recovery V2 evidence directory, updated
      V2 report PDF, Judge Card, and README to the prior local official-package
      staging tree; regenerate its `SUBMISSION_PACKAGE.json` and top-level
      `SHA256SUMS`.
- [x] Copy that prior V2 staging directory byte-for-byte to the local
      official-fork worktree and verify a clean `diff -qr` plus 104/104 package
      checksums before any push.
- [x] Stage the complete sealed 60-body prefix and 30-body suffix evidence
      directories plus refreshed README, Judge Card, and byte-identical
      19-page PDF in the local official package; both directories pass their
      internal formal/package checksum indexes and dedicated verifiers.
- [x] Regenerate `SUBMISSION_PACKAGE.json`, top-level `SHA256SUMS`, handoff
      manifest, release notes, all file counts, and every affected SHA after
      the two-shard payload is final. The superseded counts were 152 manifest
      entries, 153 checksum entries, and 154 total regular files; the prior
      103/104/105 counts and `e3fee903…` checksum identity remain archived only.
- [x] Verify all 156 top-level checksums after the full-demo refresh,
      rerun the finalizer with `--check`,
      and pass both staged solver-scale dedicated verifiers. The current
      top-level checksum-index SHA256 is
      `433b00485399a8794a55c294cf662d5273784e3e65f54b7b93af48d2c87297f6`.
- [x] Copy the final two-shard staging directory byte-for-byte to the local
      official-fork worktree and verify `diff -qr` plus every checksum before
      any push.
- [ ] Push the reviewed full-demo package to the dedicated official-fork branch
      without opening a PR; publication is in progress and no future commit is
      claimed here.
- [x] Use planned PR title `Track 3, Liu Liang, Look Twice`.
- [x] Replace the owner-review preamble in
      `docs/SUBMISSION_DRAFT.md` with the actual publication state and rerun
      the no-stale-state scan; do not file a body that still says “not yet
      filed” or “PR pending.”
- [ ] Paste the final English body from `docs/SUBMISSION_DRAFT.md`.
- [x] Keep `official_pr_opened=false` until owner review.
- [ ] Owner explicitly authorizes the official PR.
- [ ] Open the official English PR before 2026-08-06 23:59 UTC+8.
- [ ] Verify every PR link/file without sign-in and monitor organizer comments.

## Final no-PR review packet

- [x] Entrant/team label confirmed as `Liu Liang`.
- [x] Final MP4 and sidecar pass local QA for the recorded 239-second identity.
- [ ] Owner completes final visual and audible review.
- [x] The prior V2-only 104-entry `SHA256SUMS` verifies cleanly; its 103-entry
      package inventory has exact path coverage for that snapshot only.
- [ ] Publish and anonymously verify the refreshed public branch/site assets;
      the stable Release download/hash mirror remains unchanged.
- [ ] Publish and anonymously verify the current official-fork package; no
      official competition PR has been opened.
- [x] Freeze the final judge-facing source in the new annotated tag
      `v8-competition-final-2026-08-05` without moving the historical
      `v8-competition-candidate` tag.
- [x] The current staging contains both sealed solver-scale evidence
      directories, the compact compound-result files, and the byte-identical
      19-page PDF with SHA256
      `7dc0b453191a4ea215e432f22de6b374319c8df72580026f3adc8fa064291143`.
- [x] Run the official-package finalizer at `2026-08-06T02:32:52Z` and record
      the current unsealed top-level manifests and 155/156/157 counts. Its
      `--check`, all 156 checksum validations, and both staged dedicated
      verifiers pass; the top-level
      `SHA256SUMS` SHA256 is
      `433b00485399a8794a55c294cf662d5273784e3e65f54b7b93af48d2c87297f6`.
- [ ] Owner reviews the complete V2 evidence package, local verifier output,
      rebuilt PDF, refreshed site, and exact official-package diff.
- [ ] Owner reviews both solver-scale reports and verifier outputs, the rebuilt
      two-shard PDF/site, regenerated package identities/counts, and exact
      official-package diff.
- [ ] Owner reviews `docs/SUBMISSION_DRAFT.md`.
- [x] No official PR exists before explicit owner approval.
