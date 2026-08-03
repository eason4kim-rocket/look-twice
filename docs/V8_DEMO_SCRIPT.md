# Look Twice V8: Final 3:59 Demo Specification

Target duration: **239 seconds (3:59)**

Language: English narration and English on-screen text

Delivery: 1920 x 1080, 30 fps, H.264 `yuv420p`, AAC audio, browser-playable
MP4

Current state: the 239-second render and sidecar completed local media, content,
and privacy QA, then replaced the assets at the stable GitHub Release URL. The
exact official package is published on the official-fork review branch. Both
surfaces were verified without credentials; owner review remains pending and
no competition PR is open.

The executable source of truth is `scripts/build_v8_demo_video.py`. It derives
all frozen values from the locked report and the exact Radeon benchmark,
records a sanitized real terminal audit with `scripts/video/v8-audit.tape`,
and emits both the final MP4 and a machine-readable sidecar manifest.

## Production rules

- Use only V8 competition evidence. Historical V2/V3 demo assets are excluded.
- Treat the one-shot locked aggregate, the seed-105400 confirmatory replay, and
  the separate Radeon model-forward benchmark as three different scopes.
- Permanently burn
  `NON-LOCKED CONFIRMATORY REPLAY · SEED 105400 · RECORDED AMD GPU EVIDENCE`
  into the active replay footage.
- Render evidence slides with a fixed composition. The final builder removes
  `zoompan` and other Ken Burns-style drift so labels, numbers, and source
  identities remain stationary and readable. Recorded replay and terminal
  footage retain only their native motion.
- Use the hash-pinned narration assets declared in
  `assets/v8-demo-narration/manifest.json`: OpenAI `gpt-4o-mini-tts`, voice
  `cedar`.
- Disclose the synthetic voice on screen with
  `AI-GENERATED NARRATION · OPENAI TEXT-TO-SPEECH`. The sidecar also records
  `ai_generated=true`, provider, model, voice, and source hashes.
- Never present the CPU-only Evidence Console as live GPU execution.
- State `Simulation only` and the no-safety-certification boundary on screen.
- Do not show SSH details, private paths, tokens, unique hardware IDs, local
  usernames, or unredacted terminal prompts.

## Exact 239-second timeline

| Time | Duration | Chapter | Evidence purpose |
| --- | ---: | --- | --- |
| 0:00-0:21 | 21 s | Action assurance before action | Positioning and simulation boundary |
| 0:21-0:43 | 22 s | One capture is not a committee | Correlated evidence failure mode |
| 0:43-1:13 | 30 s | Lineage-aware action qualification | Architecture and dual authorization |
| 1:13-1:52 | 39 s | BeliefGap-driven active evidence repair | Full non-locked seed-105400 active replay |
| 1:52-2:11 | 19 s | Safety baseline versus recovered task utility | Locked active/passive comparison |
| 2:11-2:48 | 37 s | Opened once; denominator retained | Frozen locked result |
| 2:48-3:25 | 37 s | Radeon execution with a disclosed boundary | AMD/ROCm evidence and benchmark scope |
| 3:25-3:47 | 22 s | Receipts and hashes, not a black box | Real reproducibility terminal audit |
| 3:47-3:59 | 12 s | A concrete next observation | Final links and honest boundary |

## Narration and visual contract

The quoted narration below is the exact `spoken_text` input guarded by the
builder and narration manifest. Spoken forms such as `V-eight`, `R-G-B-D`, and
`rock-em` are intentional pronunciation controls; exact technical notation
remains visible in the artwork.

### 0:00-0:21 - Action assurance before action

**Visual:** Look Twice title, AMR corridor, `ACTION ASSURANCE BEFORE ACTION`,
and `MORE CLAIMS != MORE INDEPENDENT EVIDENCE`.

**Narration:**

> Many confident outputs can still come from one physical observation. Look
> Twice is an assurance layer before robot action. It asks whether the evidence
> is independent, fresh, calibrated, and specific to this corridor. If not,
> the robot looks again before it moves.

**Boundary:** `POSITIONING · SIMULATION-ONLY RESEARCH`

### 0:21-0:43 - One capture is not a committee

**Visual:** RGB, depth, and corridor ROI images labeled as one physical capture
root.

**Narration:**

> Our test case is a warehouse robot deciding whether to cross a corridor.
> Camera, depth, and map evidence may be noisy, stale, correlated, or
> contradictory. If several outputs come from the same capture, counting them
> as independent votes creates confidence without new evidence.

**Boundary:** `V8 SENSOR SNAPSHOTS · ONE PHYSICAL CAPTURE ROOT`

### 0:43-1:13 - Lineage-aware action qualification

**Visual:** Latest technical-report architecture and the complete V8 pipeline:

```text
RGB-D + corridor geometry
  -> spatial Claims + physical lineage
  -> split-conformal prediction sets
  -> scoped Action Contract
  -> Python admit AND Purify Go admit
  -> direct, repair, detour, or fail closed
```

**Narration:**

> V-eight projects the intended corridor into the image and runs a spatial
> R-G-B-D model on an A-M-D Radeon G-P-U. Every output becomes a Claim with
> time, scope, calibration, and physical lineage. Conformal prediction marks
> the corridor clear, blocked, or inconclusive. A scoped Action Contract checks
> the evidence. Direct motion requires agreement from both the Python
> controller and the independent Purify Go core.

**Boundary:** `LATEST TECHNICAL REPORT · SYSTEM ARCHITECTURE`

### 1:13-1:52 - BeliefGap-driven active evidence repair

**Visual:** The recorded 30-second active replay, centered within the 39-second
chapter with the permanent scope banner. Show `DENIED`, `BeliefGap`, new root,
Python/Purify conjunction, and `DIRECT`.

**Narration:**

> In this non-locked confirmatory replay, the carrier's front view suggests
> that the corridor is clear. The contract still denies direct motion because
> that view provides only one physical root. The denial reports a Belief Gap:
> acquire an independent side view. A scout moves to the diagnostic viewpoint
> and captures new R-G-B-D evidence. Color and depth from that capture still
> count as one root. The contract is evaluated again. Only agreement between
> Python and Purify unlocks the direct route.

**Boundary:** `NON-LOCKED CONFIRMATORY REPLAY · SEED 105400`

### 1:52-2:11 - Safety baseline versus recovered task utility

**Visual:** Locked paired cards: active direct 11/12, passive direct 0/12,
active uplift +91.7 pp, unsafe crossings 0/24; passive `DENY -> SAFE DETOUR`.

**Narration:**

> The passive policy receives the same initial denial but does not acquire more
> evidence. It stays safe by taking the disclosed detour. The comparison
> separates two ideas: denial prevents an unsupported action; active perception
> can recover useful motion.

**Boundary:** `LOCKED FULL-CHAIN · 12 PAIRED SEEDS`

**Interpretation boundary:** Descriptive evidence for the fixed 12-world
locked suite; no population or real-world generalization.

### 2:11-2:48 - Opened once; denominator retained

**Visual:** Latest report plus source-derived locked cards: 3,200 samples,
3,001 decisive, ROI IoU 1.000, decisive balanced accuracy 1.000, blocked recall
1.000, coverage 1.000, active direct 11/12, unsafe 0/24. Display the locked
report SHA prefix.

**Narration:**

> The locked test was opened once, with no retuning or retraining afterward. It
> includes three thousand two hundred offline samples and twelve paired live
> worlds. The predeclared offline gates passed, with three thousand one
> decisive samples and no false-clear singletons. Active repair qualified the
> direct route in eleven of twelve worlds; passive qualified none, a
> ninety-one point seven percentage-point gain. Both completed every mission.
> Across all twenty-four policy runs, unsafe crossings and unplanned fallbacks
> were zero. The conservative active detour remains in the denominator.

**Boundary:** `AUTHORITATIVE LOCKED REPORT · OPENED ONCE`

The word `decisive` remains visible; the video does not imply forced accuracy
over all 3,200 samples.

### 2:48-3:25 - Radeon execution with a disclosed boundary

**Visual:** AMD environment/report page and exact frozen benchmark cards:
`gfx1100`, HIP 7.2, FP32 39.8M parameters, batch-1 p50 192.31 ms, batch-1
p95 199.18 ms, batch-8 6.25 images/s, batch-8 peak allocated 668.38 MiB.

**Narration:**

> The recorded closed loop used one Radeon Cloud G-F-X eleven hundred G-P-U
> through rock-em. Genesis simulation, R-G-B-D rendering, tensor preprocessing,
> and spatial model inference ran on the G-P-U. The Purify contract gate
> remained a small, independent Go process on the C-P-U. A separate,
> hash-pinned F-P thirty-two benchmark measured one hundred ninety-two point
> three one milliseconds at P-fifty for batch one, and six point two five
> images per second for batch eight. These are model-forward results with
> preloaded tensors, not end-to-end robot latency.

**Boundary:** `HASH-PINNED FROZEN MODEL · MODEL FORWARD ONLY`

### 3:25-3:47 - Receipts and hashes, not a black box

**Visual:** Real VHS terminal recording of the frozen verifier, locked report
identity, Go tests, and replay identity. The prompt is sanitized.

**Narration:**

> Judges can rebuild the public replays, verify every guarded hash, inspect the
> source episodes and gate receipts, test the Go core, and start the Evidence
> Console with Docker. The site needs no live G-P-U; it replays the exact
> recorded A-M-D simulation evidence.

**Boundary:** `REAL COMMAND OUTPUT · CPU EVIDENCE AUDIT`

### 3:47-3:59 - A concrete next observation

**Visual:** Final card held for 12 seconds:

- `github.com/eason4kim-rocket/look-twice`
- `eason4kim-rocket.github.io`
- `TRACK 3 · PHYSICAL AI`
- `SIMULATION ONLY · NOT SAFETY CERTIFICATION`
- `AI-GENERATED NARRATION · OPENAI TEXT-TO-SPEECH`

**Narration:**

> If not, the robot looks again.

**Boundary:** `TRACK 3 · PHYSICAL AI · SIMULATION ONLY`

## Build

The builder consumes the nine hash-pinned MP3 narration files and
`assets/v8-demo-narration/manifest.json`; it does not synthesize narration
during the build. From the repository root on macOS with `ffmpeg`, `ffprobe`,
`vhs`, Poppler, and Pillow available:

```bash
python3 scripts/build_v8_demo_video.py --work-dir /tmp/look-twice-v8-demo-work --force
```

Expected official-staging outputs:

```text
submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/Look-Twice-V8-Demo.mp4
submission/official-repo/submissions/Track3-Liu-Liang-Look-Twice/Look-Twice-V8-Demo.manifest.json
```

Stable public target, published and verified without credentials:

<https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>

Published and anonymously verified rendered identity:

| Item | Value |
| --- | --- |
| Duration | 239.000 seconds |
| Size | 9,032,035 bytes |
| MP4 SHA256 | `70f0cb035498ed617421163b192a4c42856d0d8ede474582e550c1e3f9d81d05` |
| Sidecar SHA256 | `639c0c5e076798c74c6ec115f2adeb88b45bcc6d14698adbd566e7eb9a3cf6bb` |

## Final media QA

- [x] Builder completes without a source-hash or metric guard failure.
- [x] Sidecar reports exactly one H.264 video stream and one AAC audio stream.
- [x] Resolution is 1920 x 1080; frame rate is 30 fps; pixel format is
      `yuv420p`; audio sample rate is 48 kHz.
- [x] Duration is 239.000 seconds within the builder tolerance and the event's
      3-5 minute target.
- [x] File size is 9,032,035 bytes, below 50 MiB.
- [x] Fixed-composition slides contain no `zoompan` drift.
- [x] Representative frames from all nine chapters are readable at 100% and at
      common laptop playback size.
- [x] Local narration QA confirms the complete OpenAI `gpt-4o-mini-tts`
      `cedar` track is audible and free of truncation.
- [x] The AI-generated narration disclosure is burned into the closing card
      and recorded in the sidecar.
- [x] The active replay scope label remains burned in for the entire chapter.
- [x] Frozen numbers and SHA identities match their source JSON.
- [x] Local metadata/privacy inspection found no SSH details, private paths,
      tokens, device IDs, or local usernames.
- [ ] Owner completes final visual and audible review.
- [x] Copy the new identities into `submission/V8_SUBMISSION_MANIFEST.json` and
      regenerate the official package `SHA256SUMS`.
- [x] Replace the MP4 and sidecar at the stable GitHub Release URL and verify
      both anonymously.
- [x] Sync and push the exact package to the official competition fork.
- [x] No official competition PR is open.
