# Look Twice V8: 3-5 Minute Demo Script

Target duration: 4 minutes 10 seconds.

Language: English narration and English on-screen text.
Required capture: 1920 x 1080, 30 fps, readable terminal text.

## Production rule

The video must show the actual project workflow. Recorded replay footage may be
used, but it must be labeled as recorded AMD GPU simulation evidence. Do not
present the public CPU-only website as live GPU execution.

## Timeline and narration

### 0:00-0:20 - Hook

**Visual:** Carrier faces the corridor. Flash several RGB-D Claims, then collapse
them to one physical root. Show `ACTION DENIED`.

**Narration:**

> A robot can receive many confident answers and still have only one piece of
> physical evidence. Look Twice asks whether the evidence is strong enough for
> a specific action. If it is not, the robot looks again before it moves.

**Overlay:** `More claims != more independent evidence`

### 0:20-0:50 - Problem and application

**Visual:** Website home page, warehouse diagram, target corridor highlighted.

**Narration:**

> Our target is a warehouse mobile robot deciding whether to cross a designated
> corridor. Depth, RGB perception, and maps can be noisy, stale, correlated, or
> in conflict. A majority vote can turn copies of one camera capture into false
> certainty.

### 0:50-1:25 - Architecture

**Visual:** Reveal the pipeline one block at a time.

```text
RGB-D -> spatial Claims -> conformal sets -> Action Contract
      -> Python AND Purify Go -> action or BeliefGap
```

**Narration:**

> V8 projects the corridor into the image and runs a spatial RGB-D model on an
> AMD Radeon GPU. Each output becomes a Claim with time, scope, calibration,
> capture lineage, and device lineage. Split conformal prediction turns scores
> into clear, blocked, or inconclusive sets. The Python controller and the
> standalone Purify Go core must both admit the action.

### 1:25-2:15 - Active evidence repair

**Visual:** Play the active Evidence Console replay. Pause briefly at the
initial gate, side-view capture, and final gate.

**Narration:**

> The carrier's front view is initially denied because it lacks an independent
> side-view root. The denial emits a machine-readable BeliefGap. The scout moves
> to a diagnostic viewpoint and captures new RGB-D evidence. RGB and depth from
> that capture still count as one root. After the new Claims arrive, Python and
> Purify evaluate the contract again. Only their conjunction unlocks the direct
> route.

**Overlays:**

- `Initial gate: DENIED`
- `BeliefGap: missing independent side-view root`
- `New capture root acquired`
- `Python admit AND Purify admit`
- `Qualified action: DIRECT`

### 2:15-2:40 - Passive comparison

**Visual:** Switch to the passive replay and show the detour.

**Narration:**

> The passive policy sees the same initial denial but does not attempt repair.
> It remains safe by taking a disclosed detour. This comparison separates the
> safety baseline from the value of active evidence acquisition.

### 2:40-3:15 - Frozen result

**Visual:** Website results page, then source locked JSON.

**Narration:**

> V8 was opened once on an isolated locked split, with no retuning, refitting,
> or vision retraining afterward. The offline test contained 3,200 samples and
> achieved perfect corridor IoU, decisive balanced accuracy, blocked recall,
> and conformal coverage, with zero false-clear singletons. In 12 paired live
> seeds, active repair qualified 11 direct routes. Across 24 active and passive
> policy runs, unsafe crossings and unplanned fallbacks were both zero.

**Overlay:** `LOCKED ONCE | 3,200 samples | 11/12 active chains | 0/24 unsafe`

### 3:15-3:40 - AMD Radeon proof

**Visual:** Terminal showing ROCm environment and a new frozen-model inference
benchmark, followed by a short Genesis GPU clip.

**Narration:**

> Genesis simulation, RGB-D rendering, tensor preprocessing, and spatial model
> inference run on one Radeon Cloud gfx1100 GPU through ROCm. The frozen stack
> uses Genesis 1.1.2, PyTorch 2.9.1, and HIP 7.2. The deterministic Go contract
> gate stays on CPU as a small independent authorization layer. A hash-pinned
> FP32 model-forward benchmark measured 192.31 milliseconds p50 at batch one
> and 6.25 images per second at batch eight.

**Overlay:** `FROZEN MODEL FORWARD · FP32 · B1 P50 192.31 ms · B8 6.25 img/s`

**Boundary caption:** `Preloaded tensor; excludes preprocessing, Genesis, Go,
I/O, and actuation. Not end-to-end latency.`

### 3:40-4:00 - Reproduction

**Visual:** Terminal runs the three CPU audit commands, then opens the local
Docker site.

**Narration:**

> Judges can rebuild the public replay, verify every guarded SHA, inspect the
> source episode and GateReceipts, test the Go core, and run the Evidence Console
> with Docker. The website needs no live GPU because it replays the exact
> recorded evidence.

### 4:00-4:10 - Close and limitations

**Visual:** Final title card with repository, website, and `Simulation only`.

**Narration:**

> Look Twice turns uncertainty into a concrete next observation, and turns
> robot action into an auditable decision. This is simulation-only research,
> not a real-robot or safety-certification claim.

## Required final links

Show these on the final card for at least five seconds:

- `github.com/eason4kim-rocket/look-twice`
- `look-twice-evidence-console.eason1319.workers.dev`
- `Track 3 - Physical AI`
- `Simulation only`

## Capture checklist

- [ ] English narration and English default website state.
- [ ] 3-5 minute final duration.
- [ ] Actual terminal commands and resulting output are readable.
- [ ] AMD/ROCm environment is visible.
- [ ] Benchmark boundary caption remains readable when performance values are
      shown.
- [ ] Active and passive workflows are both shown.
- [ ] Frozen numbers match the locked source JSON exactly.
- [ ] Confirmatory replay and locked aggregate are not conflated.
- [ ] No private paths, SSH details, tokens, unique hardware IDs, or usernames
      appear in the recording.
- [ ] Video is playable without sign-in from a logged-out browser.
- [ ] Final MP4 SHA256 is recorded in the submission manifest.
