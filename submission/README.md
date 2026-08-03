# Look Twice V8 Submission Index

This directory is the English-only handoff index for the AMD AI DevMaster
Hackathon 2026, Track 3 - Physical AI.

Official PR title:

```text
Track 3, eason4kim-rocket, Look Twice
```

Submission deadline: **2026-08-06 23:59 UTC+8**.

## Judge-first links

1. Public Evidence Console:
   <https://look-twice-evidence-console.eason1319.workers.dev/>
2. Frozen results:
   <https://look-twice-evidence-console.eason1319.workers.dev/results>
3. Technical report PDF:
   `output/pdf/Look-Twice-V8-Technical-Report.pdf`
4. Reproduction guide: `docs/V8_REPRODUCTION.md`
5. Official PR body: `docs/SUBMISSION_DRAFT.md`
6. Official-repository staging directory:
   `submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/`

## Primary competition artifacts

| Artifact | Path | SHA256 / state |
| --- | --- | --- |
| Locked V8 report | `release/v8-frozen/results/LOCKED_TEST_REPORT.json` | `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb` |
| Locked-open seal | `release/v8-frozen/results/LOCKED_TEST_OPENED.json` | `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14` |
| ROCm model-forward benchmark | `release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json` | `282b0a1bf5180d9aca75cb068b60100222eb07bf6aea9fc8a2ca46c655b14156` |
| English technical report | `docs/V8_TECHNICAL_REPORT.md` | source |
| Rendered report | `output/pdf/Look-Twice-V8-Technical-Report.pdf` | `23c5edc768cb9d831ac90089bad00bf664c8e5bfcaae5d4472aa3666c9e52b15` |
| Detailed reproduction | `docs/V8_REPRODUCTION.md` | ready |
| 4:10 demo script | `docs/V8_DEMO_SCRIPT.md` | ready |
| 30-second evidence reel | `showcase/public/media/look-twice-replay-30s.mp4` | `46d1d70298a991a6ad9ec7996a587f441ea15a55f2d09374b4102a417016f0e2` |
| Final 3-5 minute video | public URL | **not recorded yet** |
| Submission PR text | `docs/SUBMISSION_DRAFT.md` | ready except final URLs |
| Official-repo package | `submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/` | ready except final video URL and registered team check |

## Frozen checkpoint

- SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Size: 159,592,901 bytes.
- Local/GPU copies are preserved outside the Git worktree.
- A public release asset or model-hosting URL is still required because the
  file exceeds GitHub's normal 100 MB blob limit.

## Verified commands

The following passed during submission preparation on 2026-08-03:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
cd purify_robotics && go test ./...
cd showcase && npm run lint && npm test
cd showcase && npm audit
docker compose build
cd submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice
shasum -a 256 -c SHA256SUMS
```

The same checks were repeated from a clean detached worktree at the frozen
submission commit. The Evidence Console was started from that clean Docker
image; the four app routes, report PDF, locked JSON, benchmark JSON, and social
card all returned HTTP 200. The final pinned Node dependency graph reported
zero known `npm audit` vulnerabilities on 2026-08-03.

## Evidence boundary

Only V8 is submitted. Integrity Shield R1/R2 and V9 are later research and do
not change the locked V8 result. The R1 recovery source being complete does not
constitute a calibration pass. See `docs/V8_EVIDENCE_BOUNDARY.md`.

## Remaining pre-PR actions

1. Confirm the registered team display name; the package currently uses the
   GitHub handle `eason4kim-rocket` as a solo entrant.
2. Push `v8-competition-release` and verify it from a logged-out browser.
3. Publish the frozen checkpoint at a stable public URL and add it to the
   reproduction guide and PR body.
4. Record the scripted 3-5 minute English demo, publish it without sign-in,
   and record its SHA256.
5. Replace the preparation warning and video placeholder in
   `docs/SUBMISSION_DRAFT.md` and the staged official-repository `README.md`.
6. Copy the staged `submissions/Track3-eason4kim-rocket-Look-Twice/`
   directory into the official fork.
7. Open the official English PR only after the links above have been checked.
