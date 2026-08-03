# V8 additive dual-body rigid-dynamics protocol

**Protocol fixed:** 2026-08-03, before the confirmatory seed run

**Scope:** submission-time, additive, non-locked validation

**Formal-result eligible:** no

## Question

Can the two roles disclosed in frozen V8 as logical poses on one kinematic
chassis also be instantiated as two separate, non-fixed Genesis rigid bodies
and execute bounded warehouse motion using wheel-joint velocity control only?

This protocol tests that narrow actuation boundary. It does not rerun the V8
perception comparison, alter its 29/30 primary result, validate a real robot, or
claim that the full V8 policy has been converted to simultaneous multi-robot
dynamics.

## Engineering smoke excluded from confirmation

Seeds `160800`–`160802` were used only to establish wheel-axis sign, start
height, stable control limits, acceptance thresholds, and the need for explicit
URDF inertial origins. Those three observed layouts are excluded from the
confirmatory set.

The confirmatory set is the disjoint, fixed half-open range
`160820:160840` (20 geometry seeds). No seed is resampled or replaced. The
complete report is retained whether the bar passes or fails.

## Physical scene

Each seed contributes three entities to one Genesis scene:

1. `diff_drive_carrier.urdf`, `fixed=False`, including a 4 kg payload;
2. `diff_drive_scout.urdf`, `fixed=False`;
3. one fixed 0.45 m × 0.45 m × 0.50 m blocker in the opposite corridor.

The 20 trial worlds are placed on a 12 m × 6 m grid so their bodies cannot
interact. Every articulated robot has two continuous wheel DOFs. Wheel position
stiffness is zero; velocity gain and bounded force targets are applied after
`scene.build()`.

The script does not call `set_pos`, `set_quat`, or `set_qpos` after build. Its
only post-build actuation API is `control_dofs_velocity` on the two wheel DOFs.
Ground contact is expected and is not counted as a failure.

## Per-seed sequence

1. Settle the full scene for 80 steps at `dt=0.02 s` with zero wheel targets.
2. Drive the scout from `(-1.6, 1.2)` to a deterministic side viewpoint while
   holding the carrier wheel targets at zero.
3. Stop the scout.
4. Drive the loaded carrier through three waypoints in the clear corridor and
   back to the goal centerline while holding the scout wheel targets at zero.
5. Record poses, wheel targets, path lengths, tilt, partner drift, trial-blocker
   contacts, and carrier/scout pair contacts.

Even seeds use the lower clear corridor and odd seeds use the upper clear
corridor. Seeded sub-5 cm lateral jitter prevents all trials from being exact
duplicates.

## Fixed pass criteria

Every one of the 20 seeds must satisfy all checks:

- scout reaches its final waypoint within 0.14 m;
- carrier reaches its final waypoint within 0.14 m;
- both roles receive a non-zero wheel velocity target;
- scout path is at least 0.50 m and carrier path at least 3.50 m;
- the inactive partner drifts no more than 0.08 m during either phase;
- maximum carrier/scout body tilt is no more than 20°;
- zero contact rows with the trial's blocking obstacle;
- zero contact rows between that seed's carrier and scout;
- zero script-level entity pose writes after `scene.build()`;
- all poses remain finite.

There is no retry rule. Any failed check makes that seed fail; any failed seed
makes the 20-seed bar fail.

## Fixed command

```bash
python scripts/run_v8_additive_dual_body_dynamics.py \
  --seeds 160820:160840 \
  --backend amdgpu \
  --output release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

Verification:

```bash
python scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

## Interpretation boundary

A full pass supports only this statement:

> On the disclosed Genesis/ROCm environment, separate non-fixed carrier and
> scout URDF bodies completed a bounded 20-seed wheel-actuated corridor-motion
> bar without trial-blocker or pair contact and without post-build pose writes.

It does not establish real-robot transfer, energy or throughput improvement,
dynamic-obstacle response, contact-rich manipulation, or a replacement for the
frozen kinematic V8 evidence.
