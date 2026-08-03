# Look Twice V8: Final 4:10 Demo Specification

Target duration: **250 seconds (4:10)**

Language: English narration and English on-screen text

Delivery: 1920 x 1080, 30 fps, H.264 `yuv420p`, AAC audio, browser-playable
MP4

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
- Never present the CPU-only Evidence Console as live GPU execution.
- State `Simulation only` and the no-safety-certification boundary on screen.
- Do not show SSH details, private paths, tokens, unique hardware IDs, local
  usernames, or unredacted terminal prompts.

## Exact 250-second timeline

| Time | Duration | Chapter | Evidence purpose |
| --- | ---: | --- | --- |
| 0:00-0:19 | 19 s | Action assurance before action | Positioning and simulation boundary |
| 0:19-0:43 | 24 s | One capture is not a committee | Correlated evidence failure mode |
| 0:43-1:13 | 30 s | Lineage-aware action qualification | Architecture and dual authorization |
| 1:13-1:58 | 45 s | BeliefGap-driven active evidence repair | Full non-locked seed-105400 active replay |
| 1:58-2:18 | 20 s | Safety baseline versus recovered task utility | Locked active/passive comparison |
| 2:18-2:55 | 37 s | Opened once; denominator retained | Frozen locked result |
| 2:55-3:33 | 38 s | Radeon execution with a disclosed boundary | AMD/ROCm evidence and benchmark scope |
| 3:33-3:58 | 25 s | Receipts and hashes, not a black box | Real reproducibility terminal audit |
| 3:58-4:10 | 12 s | A concrete next observation | Final links and honest boundary |

## Narration and visual contract

### 0:00-0:19 - Action assurance before action

**Visual:** Look Twice title, AMR corridor, `ACTION ASSURANCE BEFORE ACTION`,
and `MORE CLAIMS != MORE INDEPENDENT EVIDENCE`.

**Narration:**

> Many confident sensor outputs can still represent one physical observation.
> Look Twice is an action-assurance layer. Before a robot crosses, it asks
> whether the evidence is independent, current, calibrated, and specific to
> that corridor. If not, the robot looks again.

**Boundary:** `POSITIONING · SIMULATION-ONLY RESEARCH`

### 0:19-0:43 - One capture is not a committee

**Visual:** RGB, depth, and corridor ROI images labeled as one physical capture
root.

**Narration:**

> Our target is a warehouse mobile robot choosing whether to cross a designated
> corridor. RGB, depth, and maps can be noisy, stale, correlated, or
> conflicting. Counting derived outputs as independent votes can turn one
> camera capture into false certainty.

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

> V8 projects the intended corridor into the image and runs a spatial RGB-D
> model on an AMD Radeon GPU. Each output becomes a lineage-aware Claim. Split
> conformal prediction produces clear, blocked, or inconclusive sets. A scoped
> Action Contract then checks freshness, calibration, conflicts, and
> independent roots. Both Python and the standalone Purify Go core must admit
> the action.

### 1:13-1:58 - BeliefGap-driven active evidence repair

**Visual:** The recorded 30-second active replay, extended to the chapter
duration with the permanent scope banner. Show `DENIED`, `BeliefGap`, new root,
Python/Purify conjunction, and `DIRECT`.

**Narration:**

> The carrier's initial front snapshot predicts clear, but direct motion is
> denied because the contract requires an independent side-view root. The
> denial emits a machine-readable BeliefGap. The scout moves to a diagnostic
> viewpoint and captures new RGB-D evidence. RGB and depth from that capture
> still count as one root. Python and Purify re-evaluate the contract. Only
> their conjunction unlocks the direct route.

### 1:58-2:18 - Safety baseline versus recovered task utility

**Visual:** Locked paired cards: active direct 11/12, passive direct 0/12,
active uplift +91.7 pp, unsafe crossings 0/24; passive `DENY -> SAFE DETOUR`.

**Narration:**

> The passive policy receives the same initial denial and does not repair the
> evidence. It remains safe by taking the disclosed detour. This comparison
> separates the safety of denial from the task value recovered by active
> perception.

**Interpretation boundary:** Descriptive evidence for the fixed 12-world
locked suite; no population or real-world generalization.

### 2:18-2:55 - Opened once; denominator retained

**Visual:** Latest report plus source-derived locked cards: 3,200 samples,
3,001 decisive, ROI IoU 1.000, decisive balanced accuracy 1.000, blocked recall
1.000, coverage 1.000, active direct 11/12, unsafe 0/24. Display the locked
report SHA prefix.

**Narration:**

> V8 was opened once on a predeclared locked split. Nothing was retuned, refit,
> or retrained afterward. Across 3,200 offline samples, intersection over
> union, decisive balanced accuracy, blocked recall, and coverage were 1.0,
> with zero false-clear singletons. In 12 paired live seeds, active repair
> qualified 11 direct routes. Across all 24 policy runs, unsafe crossings and
> unplanned fallbacks were both zero. The one conservative active detour
> remains in the denominator.

The word `decisive` remains visible; the video must not imply forced accuracy
over all 3,200 samples.

### 2:55-3:33 - Radeon execution with a disclosed boundary

**Visual:** AMD environment/report page and exact frozen benchmark cards:
`gfx1100`, HIP 7.2, FP32 39.8M parameters, batch-1 p50 192.31 ms, batch-1
p95 199.18 ms, batch-8 6.25 images/s, batch-8 peak allocated 668.38 MiB.

**Narration:**

> The closed loop ran on one Radeon Cloud gfx1100 GPU through ROCm: Genesis
> simulation and RGB-D rendering, tensor preprocessing, and spatial model
> inference. The Purify contract gate remained a small CPU Go process. A
> separate hash-pinned FP32 model-forward benchmark measured 192.31
> milliseconds p50 at batch one, and 6.25 images per second at batch eight. It
> is not end-to-end robot latency.

**Boundary caption:** `MODEL FORWARD ONLY · NOT END-TO-END LATENCY`

### 3:33-3:58 - Receipts and hashes, not a black box

**Visual:** Real VHS terminal recording of the frozen verifier, locked report
identity, Go tests, and replay identity. The prompt is sanitized.

**Narration:**

> Judges can rebuild both public replays, verify every guarded cryptographic
> hash, inspect the source episodes and gate receipts, run the Go tests, and
> start the Evidence Console with Docker. The public site needs no live GPU
> because it replays the exact recorded AMD simulation evidence.

### 3:58-4:10 - A concrete next observation

**Visual:** Final card held for 12 seconds:

- `github.com/eason4kim-rocket/look-twice`
- `eason4kim-rocket.github.io`
- `TRACK 3 · PHYSICAL AI`
- `SIMULATION ONLY · NOT SAFETY CERTIFICATION`

**Narration:**

> Look Twice turns uncertainty into a concrete next observation, and robot
> action into an auditable decision. Simulation only; no safety-certification
> claim.

## Build

From the repository root on macOS with `ffmpeg`, `ffprobe`, `vhs`, Poppler,
Pillow, and the system `say` voice available:

```bash
python3 scripts/build_v8_demo_video.py --work-dir /tmp/look-twice-v8-demo-work
```

Expected official-staging outputs:

```text
submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/Look-Twice-V8-Demo.mp4
submission/official-repo/submissions/Track3-eason4kim-rocket-Look-Twice/Look-Twice-V8-Demo.manifest.json
```

Public target:

<https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Demo.mp4>

Rendered identity:

| Item | Value |
| --- | --- |
| Duration | 250.000 seconds |
| Size | 17,342,763 bytes |
| MP4 SHA256 | `906f4396cba9d04ff9e32c8d92ca7c7c85bab7a87f4bbdd2006c79c6474ba280` |
| Sidecar SHA256 | `c8e8a505b5c3678b7a503446eb571798a1d3ef0668840b11cad7ac95a90347d9` |

## Final media QA

- [x] Builder completes without a source-hash or metric guard failure.
- [x] Sidecar reports exactly one H.264 video stream and one AAC audio stream.
- [x] Resolution is 1920 x 1080; frame rate is 30 fps; pixel format is
      `yuv420p`; audio sample rate is 48 kHz.
- [x] Duration is 250.000 seconds within the builder tolerance.
- [x] File size is 17,342,763 bytes, below 50 MiB.
- [ ] Representative frames from all nine chapters are readable at 100% and at
      common laptop playback size.
- [ ] Full narration is audible, paced correctly, and free of truncation.
- [ ] Active replay scope label remains burned in for the entire chapter.
- [ ] Frozen numbers and SHA identities match their source JSON.
- [ ] No SSH details, private paths, tokens, device IDs, or local usernames are
      visible or embedded in metadata.
- [ ] MP4 SHA256 and size are copied from the verified sidecar into
      `submission/V8_SUBMISSION_MANIFEST.json` and final `SHA256SUMS`.
- [ ] Public URL plays without sign-in from a logged-out browser.
