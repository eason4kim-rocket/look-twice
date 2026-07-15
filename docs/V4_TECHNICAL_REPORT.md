# Look Twice v4 — Active Evidence Assurance

**Technical report (English contest entry materials)**

A Purify-powered, lineage-aware action qualification and active evidence repair
system for Physical AI on AMD GPU.

## 1. Problem

When depth, semantic perception, and a static map disagree on whether a
high-risk region is `clear` or `blocked`, a robot must decide whether the
evidence is **fresh, independent, and calibration-applicable**, and whether the
next physical observation can repair the action-admission gap. Ordinary
majority voting and single-shot confidence inflate when the same physical
measurement is echoed under different modalities or modules.

## 2. System closed loop

```text
Depth / Semantic / Static Map Claims
→ lineage-aware root fusion
→ class-conditional conformal prediction set
→ Action Contract → GateReceipt
→ BeliefGap-driven physical observation
→ revised facts + PlanInvalidationReceipt
→ cross, labelled safe_fallback detour, or fail closed
```

Governance (`evaluate_action`, `invalidate_plan`) runs in a standalone Go 1.23
standard-library **Purify Robotics Reference Core** over NDJSON. Sensing,
corruption, and motion adapters run on Genesis + ROCm PyTorch. Oracle scene
truth is stored only under the episode `oracle` channel and never enters Claims,
the Go core, or the repair planner.

## 3. Intellectual property boundary

The contest repository is Apache-2.0 and contains only:

- Purify Robotics Reference Core v0.1;
- public Robot Evidence Contracts / JSON Schemas;
- Look Twice robotics adapter and stress benchmark;
- reproduction scripts and representative results.

It does **not** contain the private Purify product, assimilation engine,
production connectors, or commercial APIs. See `NOTICE`.

## 4. Evidence and safety contract

Default `cross_region` admission requires a fresh singleton `{clear}` prediction
set, at least two distinct physical measurement roots, acceptable modality skew,
matching scope, applicable calibration, and zero unresolved conflicts.
Unresolved, stale, conflict, and OOD outcomes never enter the risk region. A
collision-checked detour is an explicitly labelled `safe_fallback` and does not
masquerade as a confirmed blocked fact when the world remains unresolved.

## 5. Hardware and software (W7900D)

| Component | Version / note |
| --- | --- |
| GPU | AMD Radeon PRO W7900D |
| Genesis | 1.1.2, `gs.amdgpu` |
| PyTorch | 2.9.1+rocm7.2 |
| Python | `/opt/venv` 3.12 |
| Go core | Linux amd64 static binary + SHA256 |
| Motion (formal matrices) | **kinematic** after skid-steer acceptance failure (see §7) |

## 6. Experiment protocol (summary)

- Calibration: 7 ID profiles × seeds `30000–30049` (350), no OOD.
- Validation seeds `40000–40019` for integration only.
- Locked test: seeds `50000+`; formal closed-loop uses test seeds without
  retuning rules after reading test aggregates.
- Policies: naive-majority, v3-logodds, conformal-only, lineage-only,
  purify-passive, purify-active.
- Profiles: independent-noise, shared-occlusion, evidence-echo, time-skew,
  pose-calibration-drift, structured-depth-dropout, dynamic-change, ood-severity.

Promotion thresholds (Full Purify) are evaluated honestly with Wilson CIs where
applicable; failures are retained. Synthetic CPU episodes are never reported as
GPU formal results.

## 7. Motion acceptance and demotion

The four-wheel skid-steer URDF and wheel-velocity controller were implemented
and unit-tested. On W7900D Genesis 1.1.2, the 10-seed × 4-viewpoint acceptance
gate (`error < 0.10 m`) **failed** (14 viewpoint failures; multi-scene teardown
also produced a process SIGSEGV). Per the frozen plan, large-scale evidence
experiments and formal matrices demote to the **kinematic** backend (bounded
heading/distance control law with chassis-derived camera pose). Skid-steer code
and probe JSON remain for honest reporting; demos may still attempt skid-steer
but formal claims use kinematic physics_backend.

## 8. Results packaging

Episode JSON includes: configuration, environment (GPU/ROCm/Genesis), Claims,
GateReceipts, repair decisions, plan invalidations, motion segments, metrics,
and a separated `oracle` channel. Summaries are produced by
`scripts/summarize_v4_experiments.py` with SHA256 manifests under `results/`.

## 9. Upstream contribution status

A one-day window is reserved for a minimal Genesis AMD RGB-D → contiguous NumPy
→ ROCm Tensor example/PR documenting negative-stride contiguous conversion. PR
status will be marked honestly if unmerged at submission time.

## 10. Reproduction

See `docs/V4_REPRODUCTION.md` and the repository `README.md` for fresh-clone CPU
tests, Go core build, and pinned W7900D commands. Cloud runs require the contest
AMD image; do not install Genesis/ROCm on a developer Mac for formal claims.
