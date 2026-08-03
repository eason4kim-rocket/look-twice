# Look Twice V8 Competition Submission Checklist

Verified against the official event page, governing Rules and Conditions, and
official submission repository on 2026-08-03.

**Owner-review state:** `public_review_packet_ready_no_pr`

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
- [x] Keep the registration email private; do not publish it in the PR,
      report, repository, video, or evidence site.
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
      same-generator non-locked challenge; seeds 102530-102699 remain
      unevaluated; neither is V8 OOD evidence.
- [x] Disclose receipt-level Python/Go agreement as 250/268 (93.3%) and all 18
      mismatches as Go vetoes with `effective_admit=false`.
- [x] Label the mismatch localization as post-hoc descriptive: all 18 were
      active corridor-B evaluations with one qualifying Go root and
      `{clear, blocked}`; no selected crossing was authorized by a mismatch.
- [x] Disclose that carrier and scout are two logical roles on one shared
      Genesis chassis, not two physical devices or simultaneous dual-body
      dynamics.
- [x] State the aggregate challenge task ledger in both directions:
      loaded-carrier logical path -22.5%, total logical-role team path +24.0%.
- [x] State simulation-only, kinematic-motion, and no-safety-certification
      boundaries.
- [x] Make no external upstream PR claim.

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

## English submission materials

- [x] Root V8 README with a 90-second judge path.
- [x] One-page frozen-challenge Judge Card with the public-before-execution
      binding, result, safety, AMD execution, task trade, and honest scope.
- [x] V8 technical report source in `docs/V8_TECHNICAL_REPORT.md`.
- [x] Rendered 12-page technical report PDF, visually inspected page by page.
- [x] Detailed V8 reproduction guide.
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
- [x] Regenerate final `SHA256SUMS` and verify all 20 checksummed artifacts
      (21 total files including `SHA256SUMS`).

## Reproducibility

- [x] Push the current 239-second demo, hash-pinned narration provenance, and
      owner-review documentation to `v8-competition-release`.
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
- [x] Lint, build, and run all 26 Evidence Console tests with Node 22.
- [x] Pin patched Web dependencies and obtain zero known `npm audit`
      vulnerabilities.
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

## Website and public URLs

Stable targets:

- Evidence Console: https://eason4kim-rocket.github.io/
- Results: https://eason4kim-rocket.github.io/results
- Reproduction: https://eason4kim-rocket.github.io/reproduce
- Source branch:
  https://github.com/eason4kim-rocket/look-twice/tree/v8-competition-release
- Candidate release:
  https://github.com/eason4kim-rocket/look-twice/releases/tag/v8-competition-candidate

- [x] Prepared English root, `/console`, `/results`, and `/reproduce` routes.
- [x] Results contains the complete locked offline/live metrics, +91.7 pp
      paired result, and separate seed-105400 cost ledger.
- [x] Results contains the exact AMD execution evidence and scope boundary.
- [x] Results contains the input-only locked archive and 60-second telemetry
      supplements, with missing-output and non-OOD boundaries visible.
- [x] Site links the final report, source branch, checkpoint, and video targets.
- [x] Rebuilt, linted, tested, and inspected the prepared site.
- [x] Publish the refreshed public Pages site with HTTPS enforced.
- [x] Verify all refreshed routes and referenced client/binary assets without
      sign-in.
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

## Official submission repository

- [x] Fork `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`.
- [x] Stage an English submission directory locally containing the judge-facing
      index, report PDF, compact evidence, and preview.
- [x] Add the locally verified demo artifact and unchanged stable target URL.
- [x] Regenerate and verify staging checksums for the 239-second identity.
- [x] Copy the refreshed staged directory into the dedicated branch of the
      official fork and push it.
- [x] Verify the refreshed official-fork branch at commit
      `32cff1a1e77952e689f4730ff21b8a8a8ad01a63` contains only the 21 intended
      files (20 checksummed artifacts plus `SHA256SUMS`) without opening a PR.
- [ ] Use PR title `Track 3, Liu Liang, Look Twice`.
- [ ] Paste the final English body from `docs/SUBMISSION_DRAFT.md`.
- [x] Keep `official_pr_opened=false` until owner review.
- [ ] Owner explicitly authorizes the official PR.
- [ ] Open the official English PR before 2026-08-06 23:59 UTC+8.
- [ ] Verify every PR link/file without sign-in and monitor organizer comments.

## Final no-PR review packet

- [x] Entrant/team label confirmed as `Liu Liang`.
- [x] Final MP4 and sidecar pass local QA for the recorded 239-second identity.
- [ ] Owner completes final visual and audible review.
- [x] Final `SHA256SUMS` verifies cleanly after identity propagation.
- [x] Replacement public branch/release assets pass anonymous checks; the
      stable URLs remain unchanged.
- [x] Refreshed official-fork branch contains only intended submission files.
- [ ] Owner reviews `docs/SUBMISSION_DRAFT.md`.
- [x] No official PR exists before explicit owner approval.
