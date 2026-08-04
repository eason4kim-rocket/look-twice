# V8 additive decision-to-dynamics recovery V2 protocol

**Protocol fixed:** 2026-08-04 16:24:30 UTC, after excluded V2 engineering
smoke and before any V2 formal seed was opened

**Scope:** submission-time, additive, non-locked validation

**Formal-result eligible:** no

## Why a V2 recovery layout is necessary

V1 instantiated all 30 independent worlds in one Genesis scene and drove their
90 non-fixed robot bodies sequentially. Every `scene.step()` therefore paid the
global solver cost for all 90 bodies even though bodies belonging to different
seeds were spatially isolated and were never intended to interact.

The first complete V1 invocation reached a four-hour external watchdog without
writing its single end-of-run report. An unchanged recovery reached a 12-hour
external watchdog with exit code `124`, again before any report or per-seed
result was written. Neither invocation exposed a formal outcome. A third,
unchanged 36-hour V1 recovery was already running when V2 engineering began and
is not modified by this work.

V2 changes only the execution layout and recovery observability. It does not
change the immutable decisions, fixed seed order, within-seed scene geometry,
robot assets, controller, waypoints, physics parameters, thresholds, or final
30-seed acceptance bar.

## Immutable decision input and seed order

The formal decision input remains:

`release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json`

SHA256:
`59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0`

Formal seeds execute once in the fixed order `102500` through `102529`. The
archived outcomes remain 29 direct corridor selections and the single
dual-blocked safe detour at seed `102515`.

## Seed-isolated execution

Each seed runs in a fresh Genesis subprocess and a fresh scene. The scene keeps
the complete paired design for that seed:

1. one active non-fixed loaded carrier;
2. one active non-fixed scout;
3. one passive non-fixed loaded carrier;
4. the same fixed blockers and active/passive replica separation as V1.

The original V1 spatial index is retained, so starts, waypoints and blockers
have byte-equivalent coordinates. Active and passive replicas for a seed still
share one scene. Only unrelated bodies from other seeds are absent. Across the
fixed denominator, 30 scenes instantiate 90 distinct non-fixed robot entities;
V2 does **not** claim that all 90 coexist or move simultaneously in one scene.

After each `scene.build()`, the worker makes no `set_pos`, `set_quat`, or
`set_qpos` call. The only actuation API remains `control_dofs_velocity` on wheel
DOFs.

## Atomic checkpoint and resume rules

Before the first formal seed, the coordinator seals `SOURCE_BINDING.json` with
the commit, initial clean-tree status, scientific parameters, immutable input
identity, and SHA256 of every executable source, protocol, engineering audit,
URDF and scenario file. Formal outputs are written outside the separate source
snapshot. Every worker requires the same binding both before and after physics;
the formal host also marks the source snapshot read-only before execution.

For each seed, the coordinator:

1. starts one worker in fixed order;
2. lets the worker run the complete three-body trial;
3. validates the returned trial against the source binding and archived
   decision;
4. atomically renames it to `TRIALS/<seed>.json`;
5. updates an outcome-free `PROGRESS.json` containing only the sealed prefix and
   checkpoint hashes.

A sealed seed is never rerun, replaced, deleted, or omitted, whether it passes
or fails. Resume accepts only an exact prefix of the fixed seed order and only
when the commit, parameters and all bound source bytes remain identical. A
worker interrupted before atomic sealing has no formal checkpoint and may be
restarted under the same binding. Every launch, timeout, exit and seal is
retained in `ATTEMPTS.jsonl`.

If a sealed trial fails, the unchanged run continues through the complete
denominator. No threshold, controller or source change is permitted after any
formal checkpoint exists.

## Fixed acceptance bar

The final V2 report passes only if the same V1 conditions all hold:

- exactly 30 trials in order `102500`–`102529`;
- exactly 29 archived direct decisions and one archived safe detour;
- all 30 scouts, 30 active carriers and 30 passive carriers reach within
  `0.14 m`;
- all 90 bodies receive non-zero wheel targets;
- every scout path is at least `0.50 m` and every carrier path at least
  `3.50 m`;
- each of the 29 direct active carriers saves at least `0.50 m` of measured
  physical path against its paired passive carrier;
- paired mean active loaded-carrier path is at least 15% shorter than passive;
- the dual-blocked active outcome completes the safe outer detour;
- maximum parked-partner drift is at most `0.08 m`;
- maximum body tilt is at most 20 degrees;
- zero blocker-contact rows and zero active carrier/scout pair-contact rows;
- zero script-level entity pose writes after build;
- every per-trial, checkpoint, source-binding and aggregate check passes.

There is no seed substitution, result-based retry, threshold tuning, early
success stop, or replacement rule.

## Excluded engineering smoke

Only synthetic seeds `170800`, `170801`, and `170802` may be used before the
formal V2 binding. They cover corridor A direct, corridor B direct and the
dual-blocked detour. Their artifacts and any code corrections precede the final
protocol timestamp and are excluded from every formal count and claim.

Engineering attempt 1 completed 3/3 and its report independently verified, but
two workers faulted during Genesis interpreter-global teardown after their
immutable checkpoints had already been published. The standalone verifier also
required an explicit repository `PYTHONPATH`. Before this protocol was fixed,
worker termination was changed to exit immediately after checkpoint
`fsync`/exclusive publication, and the verifier added its repository root to
the module path. Neither change touches physics or an outcome.

Engineering attempt 2 then passed 3/3 in 115 seconds. All three workers exited
zero; runner and verifier exited zero; blocker and active-pair contact rows were
zero; maximum tilt was 10.4957 degrees; maximum parked-partner drift was
0.020809 m. The report SHA256 is
`965b90086bb1b15ba8831987fb4a3394ea8cd241fd6923e826117a4395f7e30e`.
Full attempt identities are retained in
`docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_ENGINEERING_AUDIT.json`.

## Fixed commands

Initial formal execution:

```bash
python scripts/run_v8_additive_decision_dynamics_recovery_v2.py \
  --backend amdgpu \
  --output-dir /workspace/look-twice-v2-formal-output
```

Infrastructure resume, only under the unchanged sealed binding:

```bash
python scripts/run_v8_additive_decision_dynamics_recovery_v2.py \
  --backend amdgpu \
  --output-dir /workspace/look-twice-v2-formal-output \
  --resume
```

Verification:

```bash
python scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  /workspace/look-twice-v2-formal-output/REPORT.json
```

## Interpretation boundary

A full pass supports only this statement:

> Across 30 fixed, independent Genesis/ROCm scenes, the archived V8 route
> outcomes were bound to 90 distinct non-fixed robot bodies; paired active
> loaded carriers retained the predeclared physical path advantage while every
> body reached its goal without blocker or active-pair contact.

It remains an archived-decision replay in simulation. It is not a live rerun of
the frozen perception-policy loop, one simultaneous 90-body scene, simultaneous
cooperative motion, dynamic-obstacle response, physical-robot validation,
sim-to-real evidence, energy savings, throughput evidence, or safety
certification.
