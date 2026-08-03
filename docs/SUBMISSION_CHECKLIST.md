# Look Twice V8 Competition Submission Checklist

Verified against the official event page, governing Rules and Conditions, and
official submission repository on 2026-08-03.

**Owner-review state:** `review_ready_no_pr`

**Official PR opened:** `false`

**Entrant assumption:** `eason4kim-rocket` (solo entrant; human confirmation
required)

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
- [ ] Confirm `eason4kim-rocket` is the intended solo entrant/team label;
      replace it consistently if registration uses another display name.
- [ ] Confirm the registration email and phone are monitored for seven days
      after judging.

## Positioning and evidence discipline

- [x] Position Look Twice as an evidence-assurance boundary immediately before
      action, complementary to perception, planning, and simulation.
- [x] Lead with the locked paired capability result: active direct 11/12 versus
      passive direct 0/12, a +91.7 percentage-point gain.
- [x] Retain the one conservative active detour in the denominator.
- [x] State that the paired result is descriptive for the fixed 12-world suite,
      not a population or real-world generalization.
- [x] State the non-locked seed-105400 application-value finding narrowly:
      loaded-carrier travel -23.24% through scout burden transfer.
- [x] Disclose that seed 105400 total robot travel increased 24.32% and does
      not support a total-distance or latency reduction claim.
- [x] Keep locked aggregate, non-locked replay, and non-locked model-forward
      benchmark scopes visibly separate.
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

## English submission materials

- [x] Root V8 README with a 90-second judge path.
- [x] V8 technical report source in `docs/V8_TECHNICAL_REPORT.md`.
- [x] Rendered 10-page technical report PDF, visually inspected page by page.
- [x] Detailed V8 reproduction guide.
- [x] AMD environment and workload boundary.
- [x] Evidence claim boundary.
- [x] Exact English official PR body draft with stable target URLs.
- [x] English 4:10 video script aligned to the deterministic builder.
- [x] Complete the final 4:10 English demo MP4 render.
- [ ] Complete owner visual and audible review of the final MP4.
- [x] Recorded 30-second evidence reel.
- [x] English-default Evidence Console build.
- [x] Owner-review artifact manifest and handoff index.
- [x] Self-contained official-repository staging directory with PDF, compact
      evidence, final 4:10 demo, preview, and judge-facing README.
- [x] Record final video and sidecar identities in the submission manifest.
- [x] Regenerate final `SHA256SUMS` and verify all 10 packaged files.

## Reproducibility

- [ ] Push `v8-competition-release` to the public source repository.
- [ ] Verify the branch from a logged-out browser or anonymous clean clone.
- [ ] Publish the 159 MB V8 checkpoint at the stable release URL.
- [ ] Download and verify the public checkpoint SHA256.
- [ ] Clean-clone the public branch in a new directory.
- [x] Reproduce the frozen local submission commit in a clean detached
      worktree before publication.
- [x] Run the CPU replay build and frozen-boundary verifier in the release
      worktree.
- [x] Run all six competition replay Python tests.
- [x] Run the deterministic task-utility derivation and verify its SHA256.
- [x] Run `go test ./...` for the Purify reference core.
- [x] Add exact ROCm dependency and environment preflight files.
- [x] Build and route-smoke the Evidence Console with Docker.
- [x] Lint, build, and run all 20 Evidence Console tests with Node 22.
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
- [x] Make no GPU-utilization claim without archived telemetry.

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
- [x] Site links the final report, source branch, checkpoint, and video targets.
- [x] Rebuilt, linted, tested, and inspected the prepared site.
- [ ] Publish the updated public Pages site.
- [ ] Verify all routes and binary assets without sign-in on desktop and mobile.

## Final video

- [x] Builder uses only V8 competition artifacts, not historical V2/V3 media.
- [x] Timeline is exactly 250 seconds (4:10), within the 3-5 minute target.
- [x] Script contains English narration and English on-screen text.
- [x] Active replay is permanently labeled
      `NON-LOCKED CONFIRMATORY REPLAY · SEED 105400`.
- [x] Script shows active and passive evidence paths, locked metrics, recorded
      Radeon/ROCm evidence, and a real CPU audit terminal capture.
- [x] Script states `Simulation only` and the model-forward timing boundary.
- [x] Script uses sanitized terminal prompts and excludes SSH details, private
      paths, tokens, unique device IDs, and local usernames.
- [x] Complete final render.
- [x] Verify 1920 x 1080 H.264, 30 fps, `yuv420p`, AAC audio, and 250-second
      duration with `ffprobe`.
- [ ] Inspect representative frames and listen to the full narration.
- [x] Confirm the 17,342,763-byte MP4 is below the release/package size limit.
- [x] Record MP4 SHA256
      `906f4396cba9d04ff9e32c8d92ca7c7c85bab7a87f4bbdd2006c79c6474ba280`
      and sidecar SHA256
      `c8e8a505b5c3678b7a503446eb571798a1d3ef0668840b11cad7ac95a90347d9`.
- [ ] Upload to the stable no-sign-in URL and verify playback.

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
- [ ] Repeat metadata/privacy inspection for the final 4:10 video.

## Official submission repository

- [ ] Fork `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`.
- [x] Stage an English submission directory locally containing the judge-facing
      index, report PDF, compact evidence, and preview.
- [x] Add the final demo artifact and stable target URL.
- [x] Regenerate and verify staging checksums.
- [ ] Copy the staged directory into a dedicated branch of the official fork.
- [ ] Verify the official-fork branch diff without opening a PR.
- [ ] Use PR title `Track 3, eason4kim-rocket, Look Twice` unless the registered
      team label differs.
- [ ] Paste the final English body from `docs/SUBMISSION_DRAFT.md`.
- [x] Keep `official_pr_opened=false` until owner review.
- [ ] Owner explicitly authorizes the official PR.
- [ ] Open the official English PR before 2026-08-06 23:59 UTC+8.
- [ ] Verify every PR link/file without sign-in and monitor organizer comments.

## Final no-PR review packet

- [ ] Entrant/team label confirmed.
- [ ] Final MP4 and sidecar inspected.
- [x] Final `SHA256SUMS` verifies cleanly.
- [ ] Public branch/site/release assets pass anonymous checks.
- [ ] Official-fork branch contains only intended submission files.
- [ ] Owner reviews `docs/SUBMISSION_DRAFT.md`.
- [ ] No official PR exists before explicit owner approval.
