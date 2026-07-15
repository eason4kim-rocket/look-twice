# Track 3, Look Twice v4 — submission draft

> Status note, 2026-07-15: this draft accurately describes implemented v4
> architecture. Sections explicitly marked **pending measurement** must be
> replaced with archived W7900D results before submission. Synthetic smoke
> output is not competition evidence.

## Project

**Look Twice v4 — Active Evidence Assurance**

**A Purify-powered, lineage-aware action qualification and active evidence
repair system for Physical AI on AMD GPU.**

Look Twice qualifies whether changing and conflicting physical observations are
reliable enough to support a scoped robot action. When they are not, it explains
the evidence gap and moves the robot to acquire a measurement intended to
repair that gap.

## Problem

Counting sensor outputs is not the same as counting independent evidence. A
depth rule and a semantic rule may both derive from one camera capture; a
forwarded model output may be an echo of the same artifact; a map may be stale;
modalities may be time-skewed; and a confident sensor may be outside its
calibration domain.

For a high-risk crossing, the robot should answer:

1. What fact is being claimed, for which robot, payload, region, and action?
2. Which physical measurements support it, and which Claims share a root?
3. Are the evidence and calibration still valid?
4. If the contract fails, what observation could make it decidable?

## Method

```text
Depth Claim + Semantic Claim + Static Map Claim
→ capture/artifact/parent lineage collapse
→ root-aware evidence fusion
→ class-conditional conformal prediction set
→ scoped Action Contract
→ deterministic GateReceipt
→ BeliefGap-driven physical observation
→ revised fact + PlanInvalidationReceipt
→ cross, detour, or fail closed
```

The default crossing contract requires singleton `{clear}`, evidence age no
greater than 60 simulation steps, at least two physical measurement roots,
modality skew no greater than two steps, zero unresolved conflicts, matching
scope, and an applicable calibration artifact.

Unresolved, stale, conflicting, or OOD evidence cannot qualify direct passage.
A conservative detour is labelled `safe_fallback`; it is never presented as a
fabricated `confirmed_blocked` conclusion.

## Purify Robotics Reference Core

The contest repository contains a standalone Go 1.23 reference core and public
JSON Schemas. Python communicates through a persistent deterministic NDJSON
protocol with two operations:

- `evaluate_action` → GateReceipt;
- `invalidate_plan` → PlanInvalidationReceipt.

Receipts expose every contract clause, accepted/discounted Claim, lineage root,
prediction set, validity window, BeliefGap, assumption, and canonical SHA256.
Protocol errors and timeouts fail closed.

This reference core is an independent contest implementation. The repository
does not include or depend on the private Purify product, its unfinished
assimilation engine, production connectors, databases, internal APIs, or
commercial modules.

## Active evidence repair

The system distinguishes stale evidence, shared roots, insufficient roots,
modality conflict, time skew, low coverage, and calibration inapplicability.
It ranks synchronous recapture, wait-and-recapture, and four side-view actions
by expected contract repair, new-root gain, conflict discrimination, predicted
coverage, travel, revisit, degradation, and physical risk.

The planner cannot receive unknown obstacle truth, seed, scenario profile,
future events, realised faults, realised noise, or clean segmentation. It has a
fixed four-observation/two-replan budget.

## Robot and sensor simulation

The v4 Genesis runtime provides:

- a four-wheel skid-steer URDF with velocity-controlled continuous wheel joints;
- a fast kinematic backend for large paired experiments;
- a camera pose derived from the chassis on every capture;
- RGB, depth, and entity segmentation;
- projected risk-region depth ROI independent of segmentation;
- contact, control, trajectory, path, and timing records.

The kinematic Genesis backend applies integrated poses with `set_pos()` and is
disclosed as a batch backend. The skid-steer path is the intended physical-
behaviour demo. Its formal W7900D acceptance is pending.

Genesis clean entity segmentation is evaluation truth. The online semantic
Claim receives only controlled corrupted segmentation and is explicitly
described as a simulated semantic sensor proxy, not a trained vision model.

## AMD Radeon use

The v4 workload assigns the AMD Radeon PRO W7900D to:

- Genesis 1.1.2 physics through `gs.amdgpu`;
- RGB-D/entity-segmentation rendering;
- view/fault-dependent sensor corruption on PyTorch ROCm tensors;
- independent depth/semantic evidence processing;
- batched candidate evaluation and experiment throughput.

The Go Action Contract core remains on CPU because it is a small governance
layer. Formal reporting separates simulation, rendering, tensor kernel,
transfer, Go gate, and end-to-end time.

The preserved v3 project has already run Genesis and ROCm workloads on a Radeon
PRO W7900D with ROCm 7.2 and PyTorch 2.9.1. That verifies the base stack, but it
is not presented as proof that the new v4 path has completed.

**Pending measurement:** v4 Genesis/skid-steer acceptance, batch 1/8/32/128
benchmark, optional `n_envs=8` feasibility, and archived environment trace.

## Evaluation protocol

Policies:

```text
Naive Majority          V3 Log-Odds
Conformal Only          Lineage Only
Purify Passive          Purify Active
```

Profiles:

```text
independent-noise       shared-occlusion
evidence-echo           time-skew
pose-calibration-drift  structured-depth-dropout
dynamic-change          ood-severity
```

Frozen splits:

- calibration: seven ID profiles × seeds `30000–30049` = 350;
- validation: seven ID profiles × seeds `40000–40019` = 140;
- locked test: eight profiles × seeds `50000–50099` = 800;
- main paired experiment: six policies × eight profiles × first 20 locked
  seeds = 960 episodes;
- physical backend: three policies × four profiles × five seeds = 60 episodes.

All policies receive the same paired world and absolute-time dynamic event.
Calibration data never enters validation or locked test. `ood-severity` is
excluded from calibration.

Metrics include unsafe crossing, safe task success, wrong detour, contract
repair, plan invalidation, evidence-echo rejection, observation and path cost,
Brier score, ECE, conformal coverage/miscoverage with Wilson 95% intervals,
collision, and GPU throughput/latency.

**Pending measurement:** the 96 smoke, 960 formal, and 60 skid-steer matrices
have not yet been run. No v4 rate or speedup is claimed in this draft.

## Current verification evidence

Implemented and locally verified:

- public wire contracts and Schemas;
- conservative lineage and root-aware fusion;
- Go core, canonical receipts, and persistent Python bridge;
- conformal artifact construction and OOD applicability;
- six policy boundaries and seven BeliefGap repairs;
- deterministic paired scenarios and absolute event clock;
- motion control laws and skid-steer asset structure;
- atomic result/calibration tools;
- synthetic end-to-end smoke orchestration.

Synthetic runs state `formal_result_eligible=false` and use a labelled smoke
calibration fixture. They are development evidence only.

## Preserved v3 evidence

V3 remains frozen and is not rewritten as v4 evidence. Its verified five-policy
matrix contains 500 paired episodes. Its optional Learned NBV reduced held-out
oracle regret from 0.0669 to 0.0421 on its isolated v3 dataset and retained 100%
safe success in a separate 100-episode v3 closed-loop evaluation. It did not
outperform the heuristic on every path-efficiency metric; that limitation
remains public.

## Demo plan

The 3–5 minute final video will show:

```text
many apparent Claims
→ lineage graph reveals one shared capture root
→ Action Contract denied
→ BeliefGap explains missing independent evidence
→ skid-steer robot moves to a diagnostic side view
→ new physical capture root
→ conformal prediction set becomes decisive
→ prior route is invalidated if required
→ robot crosses or detours safely
→ paired and AMD benchmark results
```

**Pending:** final W7900D footage and result panels.

## Limitations

- Simulation only; no real-robot or sim-to-real claim.
- Entity segmentation is a disclosed simulated sensor proxy.
- The kinematic batch backend still applies integrated poses through
  `set_pos()`; wheel physics is assessed only with the skid-steer backend.
- Statistical coverage applies only to the declared simulated ID distribution;
  OOD fails closed without a coverage claim.
- The reference core is not the complete Purify product and is not a certified
  safety controller.
- No v4 formal GPU result or upstream PR is claimed before a public artifact or
  URL exists.

## Links

- Source: https://github.com/eason4kim-rocket/look-twice
- Architecture: `docs/ARCHITECTURE.md`
- Reproduction: `docs/V4_REPRODUCTION.md`
- Experiment protocol: `docs/V4_EXPERIMENT_PROTOCOL.md`
- Failure-case record: `docs/V4_FAILURE_CASES.md`
- Preserved v3 result: `results/2026-07-15_v3-formal/`
