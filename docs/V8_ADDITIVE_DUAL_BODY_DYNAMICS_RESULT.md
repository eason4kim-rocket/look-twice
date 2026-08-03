# V8 additive dual-body rigid-dynamics result

**Status:** passed and independently verified

**Classification:** submission-time, additive, non-locked

**Formal-result eligible:** no

**Generated:** 2026-08-03 18:15:49 UTC

## Result

The fixed confirmatory range `160820:160840` passed **20/20** under the
predeclared bar. One Genesis scene contained 40 distinct non-fixed robot
entities: one loaded carrier and one scout for each seed. The scout and carrier
were actuated in separate phases using wheel-DOF velocity targets only.

| Check | Observed | Fixed bar |
| --- | ---: | ---: |
| Passing seeds | 20 / 20 | 20 / 20 required |
| Distinct non-fixed robot entities | 40 | 40 expected |
| Carrier / scout reached | 20 / 20; 20 / 20 | all required |
| Trial-blocker contact rows | 0 | 0 required |
| Carrier/scout pair contact rows | 0 | 0 required |
| Script pose writes after build | 0 | 0 required |
| Maximum body tilt | 10.750 degrees | no more than 20 degrees |
| Maximum parked-partner drift | 0.018061 m | no more than 0.08 m |
| Minimum scout path | 0.940847 m | at least 0.50 m |
| Minimum carrier path | 4.746561 m | at least 3.50 m |
| Maximum scout goal error | 0.139779 m | no more than 0.14 m |
| Maximum carrier goal error | 0.139922 m | no more than 0.14 m |

The goal-error maximum is close to the fixed tolerance because the controller
stops when it first enters the 0.14 m goal region. It should not be interpreted
as a large goal-margin result. Stability, parked-body drift, path-length, and
contact checks retained materially wider margins.

## Execution recovery disclosure

Attempt 1 was ended by an external 3,600-second watchdog before the script's
single end-of-run report write. It exited 124, produced no report, and exposed
no per-seed pass/fail outcome. The complete process was restarted once with
only the external watchdog increased to 10,800 seconds. Commit, script and URDF
bytes, fixed seeds, protocol parameters, and thresholds were unchanged. No
seed was retried individually, resampled, or replaced.

The recovery run exited 0 after 4,299.992 seconds. Both the Radeon host and the
local source tree independently accepted the same report:

```text
PASS: additive dual-body dynamics 20/20
report_sha256=8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110
```

Verify the sealed directory without Genesis or a GPU:

```bash
cd release/v8-derived/dual_body_dynamics_160820_160839
shasum -a 256 -c SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

## Evidence identities

| Artifact | SHA256 |
| --- | --- |
| Complete report | `8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110` |
| Attempt-1 timeout audit | `711547fb5f0ab928ae5cc8b6195f4e0e964a98f6df44dfa2955c67e624705d55` |
| Recovery execution audit | `6c3ddfa0ec2b482c1ab01a160572d01451f0bb1b495137e09a18a96018f23e6e` |
| Bound source commit | `c17c3a17904af34ba514d68e6e5ad8d1d96a353b` |

## Interpretation boundary

This closes one narrow implementation gap: the disclosed logical carrier and
scout roles can also be instantiated as two separate, non-fixed Genesis rigid
bodies and execute bounded wheel-actuated warehouse motion on AMD ROCm.

It does **not** rerun the frozen V8 active-versus-passive policy, replace the
29/30 preregistered primary result, establish simultaneous cooperative policy
control, validate a physical robot, or demonstrate sim-to-real transfer,
dynamic-obstacle response, energy savings, or safety certification.
