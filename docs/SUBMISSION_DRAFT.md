# Track 3, Liu Liang, Look Twice

## Active evidence assurance for warehouse robots on AMD Radeon

Look Twice is a decision layer between perception and motion. It asks a simple
question before a robot acts: **is the available evidence good enough for this
specific action?**

In a warehouse, six Claims copied from one camera frame are not six independent
observations. Look Twice traces them back to their physical capture, checks a
contract for the proposed route, and either authorizes motion, asks a scout for
the missing view, chooses a safe detour, or fails closed.

**Team:** Liu Liang, solo entrant<br>
**Track:** Track 3 — Physical AI Challenge<br>
**Repository:** [eason4kim-rocket/look-twice](https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv)

## Start here

- [Open the live Evidence Console](https://eason4kim-rocket.github.io/console)
- [Watch the 3:59 demo in the page](https://eason4kim-rocket.github.io/#full-demo)
- [Open the demo video stored in the repository](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/showcase/public/media/Look-Twice-V8-Demo.mp4)
- [Read the 19-page technical report](https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/Look-Twice-V8-Technical-Report.pdf)
- [Follow the reproduction guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_REPRODUCTION.md)

The website is a replay of recorded AMD GPU evidence, so it works without a
GPU or sign-in. The complete site source is included under
[`showcase/`](https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv/showcase).

## The warehouse problem

A loaded carrier reaches a corridor with incomplete or correlated evidence.
A conventional confidence threshold can be high while the evidence is still
unfit for the next action. Look Twice instead evaluates an action-scoped
contract:

1. Genesis produces live RGB-D observations.
2. The learned model proposes corridor-clearance Claims.
3. Claims are grouped by their original physical captures.
4. A split-conformal prediction set preserves ambiguity instead of forcing a
   class.
5. Python and the separately compiled Purify Go core evaluate the same Action
   Contract.
6. A denial explains what is missing. A fixed heuristic ranks the next scout
   view against that gap, and the same action is evaluated again.

The result is a visible sequence: **deny → diagnose → observe → re-qualify**.
If the contract still cannot be satisfied, the carrier detours or stops.

## What is new

### Physical-root lineage

Look Twice counts physical evidence, not message count. RGB, depth, derived
artifacts, and forwarded Claims from one capture share one root and cannot vote
as independent observations.

### Action Contract

A perception score is never treated as permission to move. Evidence must match
the robot, payload, corridor, action, time window, calibration context, and
independent-root requirement of the proposed motion.

### BeliefGap active repair

A denial is useful output, not a dead end. BeliefGap states which clause failed
and which observation could repair it. A deterministic next-best-view heuristic
sends the scout to collect that view before the loaded carrier moves.

### Split-conformal ambiguity

The model carries a calibrated prediction set into the contract. An ambiguous
set, or an observation outside the declared calibration scope, cannot silently
authorize a direct crossing.

### Python ∧ Purify Go

Purify is not another perception model. It is a standalone Go implementation of
the evidence gate. Direct motion requires both the Python decision and the Go
decision; a missing service or disagreement denies. In the 30-world challenge,
all 18 disagreements were conservative Go vetoes and no crossing relied on a
disagreement.

### Replayable receipts

Every decision produces a GateReceipt containing the Claims used, correlated
Claims discounted, failed clause, validity window, and final authorization.
Receipts can later be invalidated when evidence, calibration, action, or time
context changes.

## Results

### Frozen V8 evaluation

V8 was opened once on an isolated locked split. No vision retraining, refitting,
or threshold tuning followed the open.

| Result | Active evidence repair | Passive baseline |
| --- | ---: | ---: |
| Full-chain direct route | **11/12** | **0/12** |
| Mission completion | 12/12 | 12/12 |
| Unsafe crossings | 0/12 | 0/12 |
| Unplanned fallback | 0/12 | 0/12 |

The conservative active case remains in the denominator and completed by safe
detour. The locked offline set contained 3,200 samples; decisive balanced
accuracy, blocked recall, corridor ROI IoU, conformal coverage, and false-clear
singleton checks all met their declared acceptance bars.

### Preregistered 30-world challenge

The runner, seeds, endpoint, order, timeout, telemetry, validator, and no-retry
rule were published before execution.

| Preregistered endpoint | Active | Passive |
| --- | ---: | ---: |
| Full-chain direct route | **29/30** | **0/30** |
| Mission completion | 30/30 | 30/30 |
| Unsafe outcome | 0/30 | 0/30 |
| Unplanned fallback | 0/30 | 0/30 |

The only active non-direct world had both corridors blocked and completed by
safe detour. All 60 episodes used Genesis live RGB-D, the frozen 39.8M-parameter
checkpoint, and a Purify Go receipt. The project verifier passed.

[Challenge evidence and compact result card](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_FROZEN_CHALLENGE_JUDGE_CARD.md)

## Additional execution evidence

These tests answer narrower engineering questions and do not replace the
preregistered 29/30 versus 0/30 endpoint.

| Supplement | Result | What it adds |
| --- | --- | --- |
| Contract-progress efficiency, 20 paired worlds | Both arms 20/20 direct; scout path **−40.3%**, team path **−15.0%**, captures **−27.5%** | The active repair loop can collect less evidence without losing the direct-route result. |
| Decision-bound wheel dynamics, 30 scenes | 30/30 archived decisions completed; 90/90 cumulative robot bodies reached | The frozen route decisions can drive non-fixed scout, active-carrier, and passive-carrier bodies using wheel-speed control. |
| Two solver-scale scenes | 20/20 seeds in one 60-body scene and 10/10 in one 30-body scene | The same archived decisions were checked with up to 60 robots resident in one Genesis solver. |

Across the 29 direct dynamics pairs, each active loaded carrier saved at least
0.5 m relative to its passive counterpart. The dual-blocked case completed its
safe detour. Recorded blocker/active-pair contacts and post-build pose writes
were zero; tilt and parked drift stayed within the fixed limits.

The 90 robots are cumulative across the tested scenes: maximum co-resident body
count was 60, and all 90 were never simulated in one scene.

- [Efficiency result](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_CONTRACT_PROGRESS_CHALLENGE_RESULT.md)
- [Decision-bound dynamics result](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md)
- [Machine-readable evidence directories](https://github.com/eason4kim-rocket/look-twice/tree/v8-contract-progress-nbv/release/v8-derived)

## AMD Radeon and ROCm

| Stage | Runtime |
| --- | --- |
| Genesis 1.1.2 simulation | Radeon GPU through `gs.amdgpu` |
| RGB-D rendering | Radeon GPU |
| RGB-D preprocessing and 39.8M-parameter model | PyTorch ROCm/HIP on `cuda:0` |
| Action Contract gate | Standalone Go process on CPU |
| Evidence Console | Browser replay of recorded GPU evidence |

The preregistered challenge retained 844 `rocm-smi` samples across the complete
1,685.5-second subprocess wall, including idle periods. These measurements show
where the workload ran; they are not claims about control-loop latency, robot
energy, or fleet throughput.

## Open-source contribution

The repository includes the Python loop, schemas, Purify Go reference core,
validators, evidence site, and recorded results. Work on the project also found
a Genesis URDF inertial-origin parsing issue:

- [Genesis issue #3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183)
- [Open Genesis PR #3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184)
- [Bounded regression record](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_GENESIS_PR_3184_VALIDATION.md)

The upstream PR is open and unmerged. No maintainer acceptance or full-suite
validation is claimed.

## Reproduce and inspect

CPU-only evidence checks:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/derive_v8_task_utility.py
```

The original source-SHA guard runs from the immutable frozen-foundation tag:

```bash
git clone --branch v8-competition-final-2026-08-05 --single-branch \
  https://github.com/eason4kim-rocket/look-twice.git look-twice-frozen
cd look-twice-frozen
python3 scripts/verify_frozen_foundation.py
```

Purify Go tests:

```bash
cd purify_robotics
go test ./...
```

Evidence website:

```bash
cd showcase
npm ci
npm test
npm run dev
```

Or launch the packaged replay with Docker:

```bash
docker compose up --build
```

The [full reproduction guide](https://github.com/eason4kim-rocket/look-twice/blob/v8-contract-progress-nbv/docs/V8_REPRODUCTION.md)
contains the GPU command, expected outputs, archive checks, and environment
details.

## Submission package

The competition package contains:

- `README.md` — judge-facing overview and reproduction entry point
- `Look-Twice-V8-Demo.mp4` — complete 3:59 English demo
- `Look-Twice-V8-Evidence-Reel-30s.mp4` — short preview
- `Look-Twice-V8-Technical-Report.pdf` — 19-page report
- `V8-Frozen-Challenge-Judge-Card.md` — compact primary-result record
- `evidence/` — primary, efficiency, dynamics, and scale machine evidence
- `SHA256SUMS` and `SUBMISSION_PACKAGE.json` — integrity and file index

[Browse the prepared competition package](https://github.com/eason4kim-rocket/Radeon-hackathon-2026-07/tree/submission/track3-liu-liang-look-twice-v8/submissions/Track3-Liu-Liang-Look-Twice)

## Scope

This submission reports same-generator warehouse simulation. It does not claim
physical-robot validation, sim-to-real transfer, out-of-distribution coverage,
safety certification, energy savings, or fleet throughput. The Action Contract
is an engineering admission rule, not a formal safety proof. Physical-root
lineage checks the provenance declared in each record; it cannot detect a
maliciously hidden source. The next-best-view policy is a deterministic
one-step heuristic, not a proof of globally optimal sensing.

In the primary kinematic runs, carrier and scout are logical poses, viewpoints,
and capture roots on one shared Genesis chassis—not two robots moving
simultaneously. The separately labeled wheel-dynamics studies instantiate
non-fixed bodies and replay archived decisions.

The dynamics and efficiency studies are additive, non-locked supplements. They
replay or extend frozen V8 decisions without changing the preregistered primary
endpoint.

## Team

**Liu Liang — solo entrant**<br>
GitHub: [@eason4kim-rocket](https://github.com/eason4kim-rocket)

Project conception, warehouse simulation, perception and contract loop,
calibration, Purify Go reference core, experiments, evidence tooling, website,
documentation, and submission packaging.
