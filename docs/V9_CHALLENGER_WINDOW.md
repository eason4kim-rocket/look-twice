# Look Twice V9 Challenger Window

Status: preregistered challenger plan  
Primary candidate: frozen V8  
Decision deadline: 2026-07-30 (Asia/Shanghai)  
Allowed decision: `V9_PROMOTED` or `V8_REMAINS_PRIMARY`

## Objective

V9 is **Contract-Aware Counterfactual Evidence Repair**. It does not replace the
frozen V8 spatial RGB-D model or Purify authorization. It learns which physical
viewpoint is most likely to repair the currently failing Action Contract at the
lowest motion and observation cost.

The unchanged product story is:

> Claim → Purify qualification → BeliefGap → active evidence repair → action.

V8 already proves this closed loop. V9 may be promoted only if it makes the
repair action materially better on new paired worlds without weakening safety,
calibration discipline, or traceability.

## Frozen boundary

V9 MUST NOT modify:

- the V8 checkpoint recorded by `release/V8_FROZEN_IMPORT_MANIFEST.json`;
- the V8 Vision conformal artifact;
- the V8 Go-fusion conformal artifact;
- the Purify Go authorization semantics or binary;
- the V8 locked-test archive or its one-open seal;
- either V8 competition Replay Pack;
- the meaning of `effective_admit = python_admit AND purify_go_admit`.

The release SHA guard must pass before and after every V9 formal phase. V9 code
lives behind a new planner adapter and produces `EpisodeBundle v1`; it may not
add V9-specific branches to the Evidence Console.

## V9 capability

### Runtime input (no oracle)

For every eligible observation candidate, the policy receives only:

- current RGB-D evidence embedding;
- target corridor mask and public corridor geometry;
- current BeliefGap and failed Action Contract clauses;
- candidate pose relative to the robot and target corridor;
- visited-view mask, travel cost, predicted visibility, and physical-risk proxy;
- lineage summary containing counts and root relationships, not truth labels.

It MUST NOT receive obstacle truth, future sensor frames, actual degradation
parameters, future Gate decisions, or the label used to train the candidate.

### Counterfactual training target

During dataset generation only, Genesis evaluates every eligible candidate view
from the same frozen world state. Each candidate is labelled with:

- whether a new independent physical root was obtained;
- whether the observed claim repaired the failed contract;
- whether Python and Purify Go both admitted after repair;
- whether direct traversal was physically valid;
- observation travel distance, elapsed steps, coverage, and collision risk.

A small shared RGB-D encoder plus candidate-pose head predicts:

1. probability of effective contract repair;
2. probability of safe direct recovery after repair;
3. expected visibility/coverage;
4. epistemic uncertainty for fail-closed abstention.

The planner ranks candidates by expected repair value minus motion, revisit,
degradation, uncertainty, and physical-risk costs. The actual post-move V8
observation and the frozen Purify Gate remain authoritative.

### Why this is a Physical AI upgrade

V8 uses geometry-aligned NBV rules. V9 learns the relationship between physical
viewpoint, occlusion, evidence independence, contract repair, and action outcome.
It changes where the robot moves to sense, not merely how a dashboard looks or
how many parameters the perception model has.

## Preregistered partitions

All partitions are disjoint from V8 and from one another:

| Phase | Seeds | Use |
| --- | --- | --- |
| counterfactual train | 110000–111499 | candidate-view labels and training |
| validation | 112000–112199 | architecture/early-stop selection only |
| calibration | 113000–113199 | uncertainty and abstention calibration only |
| development smoke | 114000–114039 | wiring and failure diagnosis; non-formal |
| confirmatory paired | 115000–115059 | frozen V8 vs frozen V9 comparison |
| locked paired | 116000–116099 | one opening, only after every prior gate passes |

Changing these ranges, recycling failed seeds, or using the locked partition for
model selection invalidates V9 promotion.

## Five-day execution window

### Day 3 — Counterfactual pack and leakage audit

- implement the candidate-view pack schema and generator;
- run a 20-world preflight on AMD GPU;
- prove identical world state across candidates;
- prove runtime features contain no oracle, future frame, or noise parameter;
- measure candidate-label balance and whether viewpoints are discriminable;
- freeze a dataset manifest and source fingerprint.

Stop if the preflight has label conflicts, world drift, leakage, or fewer than
20% positive repair candidates.

### Day 4 — GPU training and calibration

- generate the full counterfactual training/validation/calibration packs;
- train the repair-ranking head on ROCm with mixed precision;
- report GPU utilization, samples/s, peak VRAM, CPU baseline, and speed-up;
- calibrate repair uncertainty on calibration seeds only;
- freeze checkpoint, calibration, preprocessing, dataset, and source SHAs.

Stop if validation ranking AUROC is below 0.80, calibration coverage is below
0.95, or a mask/pose-only shortcut materially predicts the target.

### Day 5 — Closed-loop adapter and development smoke

- install `v9_adapter` without modifying V8 artifacts or console components;
- run V8 and V9 on paired development seeds;
- verify complete Claim DAG, candidate scores, GateReceipts, motion, and outcome;
- verify V9 selects a real changed viewpoint and obtains a new root;
- retain every failure case.

Stop if unsafe is nonzero, Purify is bypassed, fallback is silent, or source and
artifact identities differ across episodes.

### Day 6 — Frozen confirmatory comparison

- freeze the planner and run paired seeds 115000–115059 exactly once;
- compute paired full-chain delta, wrong-detour delta, observation distance,
  observation count, elapsed steps, and 95% bootstrap confidence intervals;
- run AMD inference benchmark at batch 1/8/32/128;
- generate one V9 `ReleaseProfile` and three candidate-neutral Replay Packs.

Locked remains closed unless every safety, calibration, provenance, and
confirmatory gate passes.

### Day 7 — One locked evaluation and candidate decision

- atomically record `LOCKED_TEST_OPENED.json` before reading locked samples;
- run frozen V8 and V9 on the paired locked partition once;
- refuse a second run;
- write the immutable result and one of the two allowed decision files;
- do not tune after seeing locked results.

At 2026-07-30, unresolved work is a V9 failure, not an extension request.

## Promotion gates

All mandatory gates:

- `unsafe == 0` for V8 and V9;
- V9 false-clear admits do not exceed V8;
- blocked recall is not lower than V8 by more than 0.01;
- no Purify bypass; every direct action has a live Python-and-Go admit;
- no oracle/future/noise leakage;
- Vision, Go, policy, dataset, source, and episode identities are reproducible;
- V9 produces valid `ReleaseProfile v1` and `EpisodeBundle v1` artifacts;
- AMD GPU contribution is measured rather than asserted.

V9 must additionally win at least one preregistered capability gate on the
confirmatory paired set and preserve it on locked evaluation:

1. full-chain recovery improves by at least 10 percentage points; or
2. full-chain is non-inferior (no worse than 3 percentage points) and median
   repair travel distance improves by at least 25%; or
3. full-chain is non-inferior and wrong detours fall by at least 30%.

Report paired counts and 95% bootstrap confidence intervals. A prettier video,
larger network, or isolated best seed cannot promote V9.

## Decision files

`V9_PROMOTED.json` is legal only when all mandatory gates and one capability
gate pass. It switches the release manifest default candidate to V9 without any
console code change.

Otherwise write `V8_REMAINS_PRIMARY.json`, preserve V9 as an honest challenger
experiment, and spend 2026-07-31 through 2026-08-03 only on the V8 presentation,
formal results, benchmark, video, README, and submission materials.

