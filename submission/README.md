# Look Twice V8 Submission Handoff

This directory is the English-only owner-review handoff for the AMD AI
DevMaster Hackathon 2026, Track 3 - Physical AI.

**Current state:** review-ready package assembly; `official_pr_opened=false`.
No official competition PR may be opened until the owner reviews the final
render, links, entrant identity, and PR body.

Official PR title assumption:

```text
Track 3, eason4kim-rocket, Look Twice
```

The package currently assumes **eason4kim-rocket is a solo entrant**. Confirm
this against the registration record before opening the PR. Submission
deadline: **2026-08-06 23:59 UTC+8**.

## Submission positioning

Look Twice is the evidence-assurance layer immediately before robot motion. It
qualifies whether evidence is independent, fresh, calibrated, conflict-free,
and sufficient for a scoped action. A denial produces a machine-readable
`BeliefGap`; a scout acquires the missing view, and dual Python/Purify Go
authorization either recovers useful motion, selects a disclosed detour, or
fails closed.

The locked 12-world paired comparison is the central capability result:
active repair qualified 11/12 direct routes versus 0/12 for passive
(**+91.7 percentage points**), while both policies completed 12/12 missions
and unsafe crossings/fallbacks remained 0/24. The non-locked seed-105400 cost
ledger adds an honest application-value claim: active repair reduced loaded-
carrier travel by 23.24% by moving evidence-acquisition burden to a scout, but
increased total robot travel by 24.32% and did not reduce latency.

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
| Final 4:10 English demo | <https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4> |

These are the stable final targets. Logged-out availability must be verified
after publication and before the official PR is opened.

## Handoff map

1. Owner-review checklist: `docs/SUBMISSION_CHECKLIST.md`
2. Exact English PR body: `docs/SUBMISSION_DRAFT.md`
3. Submission manifest: `submission/V8_SUBMISSION_MANIFEST.json`
4. Official-repository directory:
   `submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/`
5. Technical report source: `docs/V8_TECHNICAL_REPORT.md`
6. Detailed reproduction guide: `docs/V8_REPRODUCTION.md`
7. Final demo specification: `docs/V8_DEMO_SCRIPT.md`

## Primary competition artifacts

| Artifact | Path | SHA256 / state |
| --- | --- | --- |
| Locked V8 report | `release/v8-frozen/results/LOCKED_TEST_REPORT.json` | `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb` |
| Locked-open seal | `release/v8-frozen/results/LOCKED_TEST_OPENED.json` | `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14` |
| Task-utility derivation | `release/v8-derived/V8_TASK_UTILITY_DERIVATION.json` | `f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b` |
| ROCm model-forward benchmark | `release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json` | `282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156` |
| Rendered 10-page report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` | `38ad3846bcb665d7a6554d6bb53ec73e4af7e6528db3cc0513bdd6ecd165d2f6` |
| 30-second evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` | `46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2` |
| Final 4:10 demo | `submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/Look-Twice-V8-Demo.mp4` | `906f4396cba9d04ff9e32c8d92ca7c7c85bab7a87f4bbdd2006c79c6474ba280` |
| Official PR body | `docs/SUBMISSION_DRAFT.md` | English, target URLs complete |
| Official-repo package | `submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/` | final 10-file checksum manifest verified |

## Frozen checkpoint

- SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Size: 159,592,901 bytes.
- Public target: the `v8-competition-candidate` release asset linked above.
- The release asset must be downloaded again without credentials and hash-
  verified before the PR is opened.

## Verified local commands

The following passed during submission preparation on 2026-08-03:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
python3 scripts/derive_v8_task_utility.py
cd purify_robotics && go test ./...
cd showcase && npm run lint && npm test && npm audit
docker compose build
```

The Evidence Console build passed 20/20 tests and reported zero known
dependency vulnerabilities. The frozen verifier reported all 21 guarded files
green, and the task-utility derivation matched the fixed locked and
confirmatory source hashes without reopening the test.

The final demo render is 250.000 seconds and 17,342,763 bytes. Its SHA256 is
`906f4396cba9d04ff9e32c8d92ca7c7c85bab7a87f4bbdd2006c79c6474ba280`;
the builder sidecar SHA256 is
`c8e8a505b5c3678b7a503446eb571798a1d3ef0668840b11cad7ac95a90347d9`.

## Evidence boundary

Only V8 is submitted. The locked aggregate, the non-locked seed-105400 replay,
and the separate model-forward Radeon benchmark remain explicitly separated.
Integrity Shield R1/R2 and V9 are later research and do not change the locked
V8 result. The submission makes no real-robot, sim-to-real, safety-
certification, locked latency, energy, or utilization claim. See
`docs/V8_EVIDENCE_BOUNDARY.md`.

## Final owner-review gate

- [ ] Confirm the registered entrant/team label and eligibility items.
- [ ] Inspect the final 4:10 MP4 visually and audibly; its verified SHA256,
      size, streams, and duration are already recorded in
      `V8_SUBMISSION_MANIFEST.json`.
- [x] Regenerate and verify the official-directory `SHA256SUMS` after every
      final artifact is in place.
- [ ] Verify the Pages site, source branch, PDF, checkpoint, and video without
      sign-in.
- [ ] Review the official-fork branch diff and the English PR body.
- [ ] Explicitly authorize opening the official competition PR.
