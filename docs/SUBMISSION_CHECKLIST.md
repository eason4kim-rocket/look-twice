# Look Twice V8 Competition Submission Checklist

Verified against the official event page, governing Rules and Conditions, and
official submission repository on 2026-08-03.

## Governing facts

- [x] Track: Track 3 - Physical AI.
- [x] Deadline: 2026-08-06 23:59 UTC+8.
- [x] All submission materials, project descriptions, and the official PR must
      be in English.
- [x] Required: technical report, dedicated source repository, detailed
      reproducibility README, and demonstration video.
- [x] Recommended video length: 3-5 minutes.
- [x] Preferred but not mandatory: complete Docker image/path.
- [x] PR title format: `Track 3, <team or entrant>, Look Twice`.

Official sources:

- https://huggingface.co/blog/LeRobot-worldwide-hackathon/amd-ai-devmaster
- https://luma.com/amd-4dhi
- https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07

## Eligibility and identity - human confirmation

- [ ] Confirm Luma registration approval.
- [ ] Confirm AMD Developer Program membership for prize eligibility.
- [ ] Confirm entrant is at least 18 or the age of majority.
- [ ] Confirm `eason4kim-rocket` is the intended solo entrant/team label; replace
      it consistently if the Luma registration uses another team name.
- [ ] Confirm the registration email and phone are monitored for seven days
      after judging.

## V8 evidence freeze

- [x] Candidate is `v8-frozen`.
- [x] V8 runtime, checkpoint, conformal artifacts, Purify binary, and locked
      report identities are frozen.
- [x] Locked test opened once.
- [x] Locked result passed with no retune, refit, or vision retraining.
- [x] Failed and non-promoted research is preserved.
- [x] R1/R2/V9 research is excluded from V8 headline claims.
- [x] Public replay is labeled non-locked confirmatory evidence.
- [x] Simulation-only and kinematic-motion boundaries are disclosed.
- [x] No upstream contribution is claimed.

## English submission materials

- [x] Root V8 README with a 90-second judge path.
- [x] V8 technical report source in `docs/V8_TECHNICAL_REPORT.md`.
- [x] Rendered and visually verified technical report PDF.
- [x] Detailed V8 reproduction guide.
- [x] AMD environment and workload boundary.
- [x] Evidence claim boundary.
- [x] Exact official PR body draft.
- [x] English 3-5 minute video script.
- [ ] Final 3-5 minute English demo video.
- [x] Recorded 30-second evidence reel.
- [x] English-default public Evidence Console.
- [x] Pre-submission artifact manifest and handoff index.
- [x] Self-contained official-repository staging directory with PDF, compact
      evidence, 30-second preview, README, and SHA256SUMS.
- [ ] Final submission SHA256 manifest.

## Reproducibility

- [ ] Push `v8-competition-release` to the public source repository.
- [ ] Verify the branch from a logged-out browser.
- [ ] Publish the 159 MB V8 checkpoint as a release/model asset.
- [ ] Verify the public checkpoint SHA256.
- [ ] Clean-clone the public branch in a new directory.
- [x] Run the CPU replay build and frozen-boundary verifier in the release
      worktree.
- [x] Run the six competition replay Python tests.
- [x] Run `go test ./...` for the Purify reference core.
- [ ] Build the Evidence Console with Docker from the clean clone.
- [x] Build and smoke-test the Evidence Console with Docker in the release
      worktree.
- [x] Lint, build, and run all 20 Evidence Console tests with Node 22.
- [ ] Verify every README command exactly as written.

## AMD Radeon evidence

- [x] Frozen environment records Genesis, PyTorch, HIP/ROCm, and GPU identity.
- [x] Current Radeon Cloud availability rechecked without mutating V8.
- [x] GPU/CPU workload boundary documented.
- [x] Run and archive a hash-pinned frozen-model V8 inference benchmark.
- [x] Record p50, p95, throughput, peak allocated memory, warm-up, measurement
      count, and exact checkpoint SHA in one machine-readable report.
- [x] Do not quote V4-V7 performance as V8 performance.

## Website

- [x] Public root route returns 200 without sign-in.
- [x] `/console`, `/results`, `/reproduce`, video, and source JSON return 200.
- [x] Default language is English.
- [x] Update Results with complete locked offline and live metrics.
- [x] Add explicit AMD execution evidence to Results.
- [x] Link the final report PDF and source repository.
- [x] Rebuild, run tests, and inspect desktop/mobile states.
- [ ] Republish the updated public site.
- [ ] Verify the updated public deployment from a logged-out browser.

## Video

- [ ] Capture the actual command-line workflow.
- [ ] Show active and passive evidence paths.
- [ ] Show recorded Radeon/ROCm execution evidence.
- [ ] Show the frozen source JSON and exact metrics.
- [ ] State `Simulation only` on screen and in narration.
- [ ] Ensure no SSH details, private paths, tokens, unique device IDs, or local
      usernames appear.
- [ ] Export 1920 x 1080 H.264, 30 fps, browser-playable MP4.
- [ ] Verify duration is between 3 and 5 minutes.
- [ ] Upload to a public no-sign-in URL and verify playback.
- [ ] Record the final video SHA256.

## IP, privacy, and repository hygiene

- [x] Apache-2.0 license present.
- [x] `NOTICE` defines the contest reference-core boundary.
- [ ] Re-read the final IP/license clauses before submission.
- [x] Search judge-facing/public surfaces for SSH commands, credentials,
      private Purify paths, internal APIs, databases, connectors, and
      commercial modules; remove transfer-only host records.
- [x] Review the submission PDF, preview MP4, social PNG, frozen Go binary, and
      other large tracked artifacts by file type and identity.
- [ ] Confirm all datasets and assets have legal, licensing, and ethical use.
- [x] Inspect the generated PDF and 30-second preview metadata; repeat this for
      the final 3-5 minute video after export.

## Official submission repository

- [ ] Fork `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`.
- [x] Stage an English submission directory locally containing the PR-facing
      index, technical report PDF, compact evidence, preview, and checksums.
- [ ] Copy the staged directory into the official fork and replace the final
      video placeholder.
- [ ] Use PR title `Track 3, eason4kim-rocket, Look Twice` unless the registered
      team name differs.
- [ ] Paste the final English body from `docs/SUBMISSION_DRAFT.md`.
- [ ] Open the PR before 2026-08-06 afternoon UTC+8, not at the final minute.
- [ ] Verify all PR links and files from a logged-out browser.
- [ ] Monitor CI and organizer comments until the deadline.

## Schedule

### 2026-08-03

- [x] Recover the clean V8 release worktree.
- [x] Audit official English requirements and existing materials.
- [x] Finish English docs, PDF, and website metrics.

### 2026-08-04

- [ ] Publish source branch and checkpoint mirror.
- [ ] Record and edit the final 3-5 minute video.
- [ ] Republish and verify the Evidence Console.

### 2026-08-05

- [ ] Perform two independent clean-clone reproductions.
- [ ] Freeze final PDF, video, website, source, and SHA manifest.
- [ ] Prepare the official fork submission directory.

### 2026-08-06

- [ ] Open the official English PR early.
- [ ] Resolve link, CI, or formatting problems.
- [ ] Stop all experimental work and preserve the submitted state.
