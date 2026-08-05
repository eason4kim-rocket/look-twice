# V8 additive decision-to-dynamics 30-body suffix protocol

**Protocol fixed:** 2026-08-05 05:49:25 UTC, before any formal suffix
execution

**Scope:** submission-time, additive, non-locked validation

**Formal-result eligible:** no

## Question

Can the predeclared 10-seed suffix of the archived V8 route decisions execute
in one Genesis scene containing 30 co-resident, non-fixed robot bodies, while
retaining the V1 decision-to-actuation checks under a shared global solver?

This suffix experiment complements the already completed 20-seed, 60-body
prefix. It does not alter or rerun that prefix, and it does not turn the two
scene shards into a 90-body co-resident experiment.

## Immutable input and denominator

The only decision input is:

`release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json`

SHA256:
`59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0`

The denominator is exactly the continuous, ordered seed range `102520` through
`102529`, inclusive. It contains exactly 10 trials and exactly 10 archived
active direct decisions, each with its archived selected corridor. No seed may
be reordered, substituted, omitted, resampled, or replaced.

The runner must preserve the original V1 layout identities: seed `102520` uses
original challenge index `20`, seed `102521` uses index `21`, and so on through
seed `102529` at index `29`. The suffix must not be spatially reindexed to
`0` through `9`.

The scenario oracle is used only to reconstruct the initial fixed blockers and
to audit the already archived decision. It is not supplied to the wheel
controller. Perception, spatial-model inference, conformal calibration, Python
policy selection, and Purify Go authorization are not rerun.

## Predeclared relation to the completed prefix

The prior completed 60-body prefix report is archived at:

`release/v8-derived/decision_dynamics_single_scene_60_102500_102519/REPORT.json`

SHA256:

`3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450`

The exact prefix artifact must exist at that path and match that digest before a
formal suffix attempt may launch. This byte-identity check is a source-binding
launch and provenance prerequisite. The runner must not parse or consult the
prefix report's outcome fields. The artifact is not a suffix scientific-
acceptance, controller, scenario, initial-state, route, seed, threshold, retry,
or suffix-trial-record input, and the suffix execution must not depend on it
being writable.

The prefix and suffix remain two independently complete reports from two
different Genesis scenes and builds. Prefix checkpoints and suffix checkpoints
must never be copied, concatenated, or stitched into a synthetic report or a
single-scene claim.

No combined claim is supported until an independent verifier has revalidated
both complete reports. If and only if both independently verify, their only
combined topology claim is:

> The fixed 30-seed archived challenge was replayed across exactly two Genesis
> scene shards, comprising a cumulative 90 distinct non-fixed robot
> instantiations, with at most 60 robots co-resident in either scene.

This is never a claim that 90 robots were co-resident. The first shard contains
60 robots for seeds `102500` through `102519`; the second contains 30 newly
instantiated robots for seeds `102520` through `102529`.

## Frozen V1 identity

Except for selecting the predeclared 10-seed suffix, retaining original layout
indices `20` through `29`, and adding partial checkpoint observability, the
within-seed scientific design is V1. The reference V1 implementation at
protocol freeze is
`scripts/run_v8_additive_decision_dynamics_bridge.py`, SHA256
`6d885b8b004c816e663c5e346e2bf740e75440c24f97457931f237a824331b8c`.

The 30-body suffix implementation must retain the V1:

- decision parser and oracle boundary;
- `trial_layout(case, index)` coordinates at original indices `20` through
  `29`, including the three-column grid, active/passive replica separation,
  starts, side viewpoints, corridor waypoints, outer detour, and blocker boxes;
- carrier and scout URDFs, wheel geometry, start heights, velocity gains, force
  limits, and wheel-only actuation;
- `DifferentialDriveControlLaw` and all controller gains and velocity limits;
- contact, path-length, tilt, drift, and goal-error measurement procedures;
- acceptance thresholds and aggregate path-reduction floor.

The fixed execution parameters are `dt=0.02 s`, `settle_steps=80`,
`maximum_steps_per_waypoint=1800`, `goal_tolerance=0.14 m`, `drive_sign=-1.0`,
and `record_stride=50`. The exact implementation, verifier, this protocol,
helper, controller, scenario source, immutable decision input, both URDF byte
identities, and prior-prefix evidence digest must be recorded in a pre-run
`SOURCE_BINDING.json` and remain unchanged for an attempt.

## One-scene topology and serial execution

The runner initializes Genesis once and constructs exactly one new scene.
Before the single `scene.build()` call, it instantiates all 10 isolated suffix
trial cells at their original V1 layout indices `20` through `29`. Each cell
contains:

1. one active non-fixed loaded carrier;
2. one active non-fixed scout;
3. one passive non-fixed loaded carrier;
4. fixed blocker boxes matching the archived seed's initial corridor truth in
   both the active and passive replicas.

The suffix scene therefore contains exactly 30 non-fixed robot bodies at the
same time: 10 scouts, 10 active carriers, and 10 passive carriers. All 30 are
co-resident in this one Genesis scene and share its solver. They are new entity
instantiations and are not reused from the completed prefix process or scene.
The V1 spatial offsets isolate cells by design, but cross-seed scene sharing is
still present and must not be rewritten as 10 independent scenes.

After the one build and the fixed 80-step settle, trials advance serially in
seed order. For each seed:

1. drive only its active scout to the fixed side viewpoint while its active
   carrier is explicitly held at zero wheel target;
2. stop the scout, then drive only its active loaded carrier through the
   archived selected direct corridor;
3. drive only its passive loaded carrier through the fixed outer detour;
4. assess the complete three-body trial and atomically seal its checkpoint;
5. continue to the next seed without rebuilding or replacing the scene.

All other bodies retain zero wheel targets while a body is active. Every
`scene.step()` advances the complete 30-body scene. The phases are sequential;
the topology is not evidence of simultaneous cooperative-policy control.

After `scene.build()`, the runner may not call `set_pos`, `set_quat`, or
`set_qpos`. It configures the wheel controllers with `set_dofs_kp`,
`set_dofs_kv`, and `set_dofs_force_range`; after that configuration, the only
API used to produce robot motion is `control_dofs_velocity` on wheel DOFs.

## Atomic checkpoints and the no-resume rule

A per-trial checkpoint may be published only after all three bodies for that
seed have completed their phases. Before publication, the complete in-memory
checkpoint must pass schema, recomputed-assessment, trial-hash, content-hash,
attempt/process/scene identity, seed ordinal, original V1 layout-index,
source-binding, and prefix-chain validation. It is then written to a
same-directory temporary file opened with exclusive creation, flushed, and
file-`fsync`ed. The runner uses exclusive, no-overwrite atomic publication for
`TRIALS/<seed>.json` and `fsync`s the containing directory. If either the
temporary name or final target already exists, publication fails closed. After
publication, the runner must read back the sealed bytes and repeat the full
validation before advancing or updating progress. Each checkpoint must bind at
least the suffix attempt ID, suffix scene ID, process identity, seed ordinal,
original V1 layout index, source-binding hash, previous-prefix hash, and its own
content hash.

Every checkpoint is explicitly **partial evidence**. It may support progress
monitoring and diagnosis, but it is not a formal pass. `PROGRESS.json` may
expose only the sealed ordered suffix prefix and checkpoint identities and must
never state or imply a complete-run pass.

There is no checkpoint resume mode. Checkpoints from different processes,
attempts, scene builds, output directories, commits, or source bindings must
never be concatenated, copied, or stitched into a complete suffix result. They
also must never be stitched to prefix checkpoints to imply one persistent scene
or 90 co-resident bodies.

If an attempt is interrupted before the complete suffix report is atomically
sealed, that attempt remains incomplete and all of its checkpoints remain
labelled partial. An infrastructure restart must use a new attempt directory,
initialize a new scene, and start again at seed `102520`; it may not skip a
retained checkpoint. All incomplete attempts must be preserved. The first
attempt that reaches a complete 10-seed report is authoritative. A complete
failed attempt is authoritative and must not be replaced by any rerun under
this protocol.

The runner writes `REPORT.json` atomically only after all 10 trials from the
same suffix process and scene have been assessed. Absence of that report means
there is no complete suffix result. A report with fewer than 10 trials, or with
any cross-attempt checkpoint, is invalid rather than failed or passed.

## Fixed acceptance bar

The complete suffix report passes only if every condition below is true:

- the report and all checkpoints bind to one suffix attempt, one process, one
  Genesis initialization, one scene build, and one source binding;
- exactly 10 trials appear in order `102520` through `102529` and preserve
  original V1 layout indices `20` through `29`;
- all 10 archived decisions are direct decisions using their archived selected
  corridors;
- exactly 10 scouts, 10 active carriers, and 10 passive carriers were
  instantiated together in the suffix scene and all 30 reach their final
  waypoints within `0.14 m`;
- all 30 bodies receive non-zero wheel targets;
- every scout path is at least `0.50 m`, and every active and passive carrier
  path is at least `3.50 m`;
- every one of the 10 active carriers saves at least `0.50 m` of measured
  simulated rigid-body path relative to its paired passive carrier;
- paired mean active loaded-carrier path is at least 15% shorter than paired
  mean passive loaded-carrier path;
- maximum parked-partner drift is at most `0.08 m`;
- maximum body tilt is at most 20 degrees;
- blocker-contact rows and active carrier/scout pair-contact rows are both zero;
- script-level entity pose writes after build are zero;
- every pose is finite and every per-trial, checkpoint, source-binding,
  single-scene-topology, and aggregate check passes.

There is no early-success stop, individual-seed retry, result-based retry,
threshold tuning, decision change, or seed replacement. If a trial fails but
the process remains healthy, the unchanged suffix scene continues through the
full denominator and the complete report is retained as a failure.

## Fixed command shape

Formal execution must use the suffix runner with the AMDGPU backend and a new,
empty attempt directory. The runner and verifier filenames and their exact byte
identities are frozen in `SOURCE_BINDING.json` before execution. There is
intentionally no `--resume` command. After an incomplete infrastructure
attempt, a new empty directory must restart at seed `102520`.

The verifier must reject a report unless all 10 trials and all 30 co-resident
bodies belong to the same bound suffix attempt and single suffix scene. Any
cross-reference to the completed prefix is evidence metadata only and cannot
satisfy a missing suffix trial, checkpoint, body, check, or acceptance
condition.

## Interpretation boundary

A full 10/10 suffix pass supports only this standalone statement:

> In one Genesis/ROCm scene containing 30 co-resident non-fixed robot bodies,
> the fixed 10-seed archived-decision suffix completed the V1 serial
> wheel-actuation bar: all bodies reached and all 10 direct active carriers
> retained the predeclared paired path advantage without counted blocker or
> active-pair contact.

Only after an independent verifier revalidates both this complete suffix report
and the completed 20-seed prefix report does their combination support the
cumulative two-shard statement declared above: 30 fixed seeds, cumulative 90
distinct robot instantiations, exactly two Genesis scenes/builds, and a maximum
of 60 robots co-resident in either scene. Until then, the combined claim remains
conditional. Even after both reports verify, they do **not** support “90 robots
co-resident,” “one 90-body scene,” checkpoint resume across scenes, or a
synthetic combined single-scene report.

This suffix result is additive, non-locked, and simulation-only. It does not
replace the V8 29/30 primary endpoint or the separate V2 30/30 archived-decision
replay. It does not rerun the live frozen perception-policy loop, demonstrate
simultaneous cooperative control or dynamic-obstacle response, validate a
physical robot, establish sim-to-real transfer, measure energy or throughput,
or provide safety certification.
