# V8 additive decision-to-dynamics 60-body protocol

**Protocol fixed:** 2026-08-04 23:32:04 UTC, before any formal 60-body
execution

**Scope:** submission-time, additive, non-locked validation

**Formal-result eligible:** no

## Question

Can a fixed 20-seed prefix of the archived V8 route decisions execute in one
Genesis scene containing 60 co-resident, non-fixed robot bodies, while retaining
the V1 decision-to-actuation checks under the cost of one shared global solver?

This protocol tests only that single-scene execution boundary. The same seeds
and decisions have already appeared in the 30-world challenge and the separate
seed-isolated recovery V2, so this is not a new hidden split, independent
confirmation, or replacement endpoint.

## Immutable input and denominator

The only decision input is:

`release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json`

SHA256:
`59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0`

The denominator is exactly the continuous, ordered seed range `102500` through
`102519`, inclusive. It contains exactly:

- 20 trials;
- 19 archived active direct decisions, each with its archived selected
  corridor;
- one archived dual-blocked safe-detour decision, seed `102515`.

No seed may be reordered, substituted, omitted, resampled, or replaced. This is
deliberately a 20-seed prefix. Seeds `102520` through `102529` are outside this
protocol, and no outcome here may be described as a complete 30-seed result.

The scenario oracle is used only to reconstruct the initial fixed blockers and
to audit the already archived decision. It is not supplied to the wheel
controller. Perception, spatial-model inference, conformal calibration, Python
policy selection, and Purify Go authorization are not rerun.

## Frozen V1 identity

Except for reducing the fixed denominator from 30 to 20 and adding partial
checkpoint observability, the within-seed scientific design is V1. The
reference V1 implementation at protocol freeze is
`scripts/run_v8_additive_decision_dynamics_bridge.py`, SHA256
`6d885b8b004c816e663c5e346e2bf740e75440c24f97457931f237a824331b8c`.

The 60-body implementation must retain the V1:

- decision parser and oracle boundary;
- `trial_layout(case, index)` coordinates using original indices `0` through
  `19`, including the three-column grid, active/passive replica separation,
  starts, side viewpoints, corridor waypoints, outer detour, and blocker boxes;
- carrier and scout URDFs, wheel geometry, start heights, velocity gains, force
  limits, and wheel-only actuation;
- `DifferentialDriveControlLaw` and all controller gains and velocity limits;
- contact, path-length, tilt, drift, and goal-error measurement procedures;
- acceptance thresholds and aggregate path-reduction floor.

The fixed execution parameters are `dt=0.02 s`, `settle_steps=80`,
`maximum_steps_per_waypoint=1800`, `goal_tolerance=0.14 m`, `drive_sign=-1.0`,
and `record_stride=50`. The exact implementation, verifier, protocol, helper,
controller, scenario source, immutable input, and both URDF byte identities
must be recorded in a pre-run `SOURCE_BINDING.json` and remain unchanged for an
attempt.

## One-scene topology and serial execution

The runner initializes Genesis once and constructs exactly one scene. Before
the single `scene.build()` call, it instantiates all 20 isolated trial cells.
Each cell contains:

1. one active non-fixed loaded carrier;
2. one active non-fixed scout;
3. one passive non-fixed loaded carrier;
4. fixed blocker boxes matching the archived seed's initial corridor truth in
   both the active and passive replicas.

The scene therefore contains exactly 60 non-fixed robot bodies at the same time:
20 scouts, 20 active carriers, and 20 passive carriers. All 60 are co-resident
in one Genesis scene and share its solver. The V1 spatial offsets isolate cells
by design, but cross-seed scene sharing is still present and must not be rewritten
as 20 independent scenes.

After the one build and the fixed 80-step settle, trials advance serially in
seed order. For each seed:

1. drive only its active scout to the fixed side viewpoint while its active
   carrier is explicitly held at zero wheel target;
2. stop the scout, then drive only its active loaded carrier through the
   archived selected corridor or, for seed `102515`, the fixed outer detour;
3. drive only its passive loaded carrier through the fixed outer detour;
4. assess the complete three-body trial and atomically seal its checkpoint;
5. continue to the next seed without rebuilding or replacing the scene.

All other bodies retain zero wheel targets while a body is active. Every
`scene.step()` advances the complete 60-body scene. The phases are sequential;
the topology is not evidence of simultaneous cooperative-policy control.

After `scene.build()`, the runner may not call `set_pos`, `set_quat`, or
`set_qpos`. It configures the wheel controllers with `set_dofs_kp`,
`set_dofs_kv`, and `set_dofs_force_range`; after that configuration, the only
API used to produce robot motion is `control_dofs_velocity` on wheel DOFs.

## Atomic checkpoints and the no-stitch rule

A per-trial checkpoint may be published only after all three bodies for that
seed have completed their phases and the trial record has been validated. It is
written to a same-directory temporary file opened with exclusive creation
(`O_EXCL`, Python `xb` mode), flushed, and file-`fsync`ed. The runner then uses
an exclusive hard-link publication to create `TRIALS/<seed>.json` from that
temporary inode and `fsync`s the containing directory before removing the
temporary name. If either the temporary name or final target already exists,
publication fails closed; rename, replace, and overwrite are forbidden. Each
checkpoint must bind at least the attempt ID,
single-scene ID, process identity, seed ordinal, source-binding hash, previous
prefix hash, and its own content hash.

Every checkpoint is explicitly **partial evidence**. It may support progress
monitoring and diagnosis, but it is not a formal pass, even when the sealed
prefix itself contains only passing trials. `PROGRESS.json` may expose only the
sealed ordered prefix and checkpoint identities and must never state or imply a
complete-run pass.

Checkpoints from different processes, attempts, scene builds, output
directories, commits, or source bindings must never be concatenated, copied, or
stitched into a complete result. There is no checkpoint resume mode for this
single-scene protocol because a new process cannot resume the original Genesis
scene state.

If an attempt is interrupted before the complete report is atomically sealed,
that attempt remains incomplete and all of its checkpoints remain labelled
partial. An infrastructure restart must use a new attempt directory, initialize
a new scene, and start again at seed `102500`; it may not skip the retained
prefix. All incomplete attempts must be preserved. The first attempt that
reaches a complete 20-seed report is authoritative. A complete failed attempt
cannot be replaced by rerunning until a pass under the same protocol.

The runner writes `REPORT.json` atomically only after all 20 trials from the
same process and the same scene have been assessed. Absence of that report means
there is no complete result. A report with fewer than 20 trials, or with any
cross-attempt checkpoint, is invalid rather than failed or passed.

## Fixed acceptance bar

The complete report passes only if every condition below is true:

- the report and all checkpoint records bind to one attempt, one process, one
  Genesis initialization, one scene build, and one source binding;
- exactly 20 trials appear in order `102500` through `102519`;
- exactly 19 archived direct decisions and the one seed-`102515` archived safe
  detour appear;
- exactly 20 scouts, 20 active carriers, and 20 passive carriers were
  instantiated together in the scene and all 60 reach their final waypoints
  within `0.14 m`;
- all 60 bodies receive non-zero wheel targets;
- every scout path is at least `0.50 m`, and every active and passive carrier
  path is at least `3.50 m`;
- every one of the 19 direct active carriers saves at least `0.50 m` of measured
  simulated rigid-body path relative to its paired passive carrier;
- paired mean active loaded-carrier path is at least 15% shorter than paired
  mean passive loaded-carrier path;
- seed `102515` completes the fixed safe outer detour;
- maximum parked-partner drift is at most `0.08 m`;
- maximum body tilt is at most 20 degrees;
- blocker-contact rows and active carrier/scout pair-contact rows are both zero;
- script-level entity pose writes after build are zero;
- every pose is finite and every per-trial, checkpoint, source-binding,
  single-scene-topology, and aggregate check passes.

There is no early-success stop, individual-seed retry, result-based retry,
threshold tuning, decision change, or seed replacement. If a trial fails but
the process remains healthy, the unchanged scene continues through the full
denominator and the complete report is retained as a failure.

## Fixed commands

Formal execution, into a new empty attempt directory:

```bash
python scripts/run_v8_additive_decision_dynamics_60.py \
  --backend amdgpu \
  --output-dir /workspace/look-twice-dynamics-60-formal
```

There is intentionally no `--resume` command. After an incomplete
infrastructure attempt, use a new empty directory and rerun the same command
from seed `102500`.

Verification:

```bash
python scripts/verify_v8_additive_decision_dynamics_60.py \
  /workspace/look-twice-dynamics-60-formal/REPORT.json
```

The verifier must reject a report unless all 20 trials and all 60 co-resident
bodies belong to the same bound attempt and single scene.

## Interpretation boundary

A full 20/20 pass supports only this statement:

> In one Genesis/ROCm scene containing 60 co-resident non-fixed robot bodies,
> the fixed 20-seed archived-decision prefix completed the V1 serial
> wheel-actuation bar: all bodies reached, the 19 direct active carriers retained
> the predeclared paired path advantage, and the one dual-blocked seed completed
> its safe detour without counted blocker or active-pair contact.

This result is additive, non-locked, and simulation-only. It covers only seeds
`102500` through `102519`; it is not the complete 30-seed challenge, not a 90-body
result, and not a replacement for either the V8 29/30 primary endpoint or the
separate V2 30/30 archived-decision replay. It does not rerun the live frozen
perception-policy loop, demonstrate simultaneous cooperative control or dynamic
obstacle response, validate a physical robot, establish sim-to-real transfer,
measure energy or throughput, or provide safety certification.
