# V8 additive decision-to-dynamics bridge protocol

**Protocol fixed:** 2026-08-04, after excluded engineering smoke and before
the fixed 30-pair Radeon run

**Scope:** submission-time, additive, non-locked validation

**Formal-result eligible:** no

## Question

Do the route outcomes already sealed in the V8 30-world challenge report retain
their operational meaning when replayed through separate, non-fixed scout and
carrier bodies using wheel-joint dynamics?

This protocol tests the missing decision-to-actuation boundary. It does not
rerun perception, change an archived route outcome, reopen the frozen model,
or create a new locked-policy result.

## Immutable decision input

The only formal decision input is:

`release/v8-frozen/results/challenge_102500_102529/CHALLENGE_REPORT.json`

SHA256:
`59b5d464954e6e03ee4b65f689e93fd4e4ba836a6512509e98df0b7a94d186b0`

The fixed seed order is `102500` through `102529`. The report contains 29
active direct outcomes with a selected corridor and one dual-blocked safe
detour at seed `102515`. No decision may be edited, replaced, or resampled.

The scenario oracle is used only to reconstruct the initially blocked physical
corridors and audit that an archived direct selection is clear. It is not
provided to the wheel controller. The active controller receives only the
archived selected corridor or archived safe-detour outcome.

## Excluded engineering smoke

Three synthetic seeds outside the formal denominator cover corridor A direct,
corridor B direct, and dual-blocked detour:

- `170800`, `170801`, `170802`.

Smoke attempt 1 passed two of three. The dual-blocked carrier crossed the
parked scout's side and produced 1,155 pair-contact rows. Its report SHA256 is
`ea91f18c610cd2d6c63f4de377dfcf3f68a5c256d8f81a629688f0712050fd4d`.

Before fixing this protocol, the detour case's parked scout viewpoint was moved
to the opposite side of the outer detour. A symmetric parked-scout drift check
was added. Smoke attempt 2 then passed 3/3 with zero blocker and pair contacts,
maximum tilt 10.5062 degrees, maximum parked-partner drift 0.020645 m, and
report SHA256
`4cc40b147255996d6d001db040daa027c46fba521de2f3bc0d709f17587c88b5`.

The three-case smoke has a diagnostic 10% aggregate path-reduction floor
because its direct:detour mix is 2:1. The formal 30-pair floor below remains
15% for the fixed 29:1 mix. Smoke outcomes are excluded from every formal
count and claim.

## Physical design

Each of the 30 trial cells contains two isolated replicas:

1. an active non-fixed loaded carrier;
2. an active non-fixed scout;
3. a passive non-fixed loaded carrier;
4. fixed blocker boxes matching the initial corridor truth in each replica.

The formal scene therefore contains 90 distinct non-fixed robot entities. In
the active replica, the scout first reaches a side viewpoint while the carrier
is parked. The loaded carrier then follows the archived selected corridor or,
for the single dual-blocked outcome, the fixed outer detour. In the passive
replica, the loaded carrier always follows the same fixed outer-detour rule.

After `scene.build()`, the script makes no `set_pos`, `set_quat`, or `set_qpos`
calls. Its only actuation API is `control_dofs_velocity` on the wheel DOFs.

## Fixed acceptance bar

The complete formal run passes only if every condition below is true:

- exactly 30 trials in seed order `102500`–`102529`;
- exactly 29 archived direct decisions and one archived safe detour;
- all 30 scouts, 30 active carriers, and 30 passive carriers reach their final
  waypoints within 0.14 m;
- all 90 bodies receive non-zero wheel targets;
- every scout path is at least 0.50 m and every carrier path at least 3.50 m;
- all 29 direct active carriers save at least 0.50 m of measured physical path
  relative to their paired passive carrier;
- paired mean active loaded-carrier physical path is at least 15% shorter than
  paired mean passive loaded-carrier physical path;
- the dual-blocked active outcome completes the safe outer detour;
- maximum parked-partner drift is at most 0.08 m;
- maximum body tilt is at most 20 degrees;
- zero blocker-contact rows and zero active carrier/scout pair-contact rows;
- zero script-level entity pose writes after build;
- every per-trial and aggregate check passes.

There is no early stopping, retry, seed substitution, or replacement rule. The
complete report is retained whether the bar passes or fails.

## Fixed command

```bash
python scripts/run_v8_additive_decision_dynamics_bridge.py \
  --backend amdgpu \
  --output release/v8-derived/decision_dynamics_bridge_102500_102529/REPORT.json
```

Verification:

```bash
python scripts/verify_v8_additive_decision_dynamics_bridge.py \
  release/v8-derived/decision_dynamics_bridge_102500_102529/REPORT.json
```

## Interpretation boundary

A full pass supports only this statement:

> The 30 archived V8 route outcomes were bound to 90 distinct non-fixed robot
> bodies; the paired active loaded carriers retained a predeclared physical
> path advantage over passive detours while every body reached its goal without
> blocker or active-pair contact under the fixed Genesis/ROCm bar.

It remains an archived-decision replay in simulation. It is not a live rerun of
the frozen perception-policy loop, simultaneous cooperative motion, dynamic
obstacle response, physical-robot validation, sim-to-real evidence, energy
savings, or safety certification.
