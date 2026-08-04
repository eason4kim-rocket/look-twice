# V8 additive decision-bound dynamics recovery V2 result

**Status:** passed and independently verified

**Classification:** submission-time, additive, non-locked

**Formal-result eligible:** no

**Generated:** 2026-08-04 16:48:14 UTC

## Result

The fixed seed range `102500:102530` passed **30/30** under the protocol fixed
before any formal V2 seed was opened. Each seed ran in a fresh Genesis 1.1.2
subprocess on AMD ROCm and retained its complete paired scene: one active
non-fixed scout, one active non-fixed loaded carrier, and one passive non-fixed
loaded carrier. Across 30 independent scenes, all **90/90** robot
instantiations were driven through wheel-DOF velocity targets and reached their
goals.

The replay consumed the immutable archived challenge decisions without
rerunning or changing the frozen V8 policy: 29 direct corridor decisions and
the single dual-blocked safe detour at seed `102515`.

| Check | Observed | Fixed bar |
| --- | ---: | ---: |
| Passing seeds | 30 / 30 | 30 / 30 required |
| Archived decision mix | 29 direct + 1 safe detour | exact mix required |
| Distinct non-fixed robot instantiations | 90 | 90 expected |
| Scout / active carrier / passive carrier reached | 30 / 30 / 30 | all required |
| Maximum goal error | 0.139930 m | no more than 0.14 m |
| Minimum scout path | 0.917551 m | at least 0.50 m |
| Minimum carrier path | 4.896027 m | at least 3.50 m |
| Direct pairs saving at least 0.50 m | 29 / 29 | all required |
| Minimum direct-pair carrier saving | 1.333621 m | at least 0.50 m |
| Mean active loaded-carrier path | 4.943529 m | paired comparison |
| Mean passive loaded-carrier path | 6.243270 m | paired comparison |
| Mean loaded-carrier path reduction | **20.8183%** | at least 15% |
| Blocker contact rows | 0 | 0 required |
| Active carrier/scout contact rows | 0 | 0 required |
| Script pose writes after build | 0 | 0 required |
| Maximum body tilt | 10.579607 degrees | no more than 20 degrees |
| Maximum parked-partner drift | 0.022329 m | no more than 0.08 m |

The maximum goal error is close to the fixed tolerance because the controller
stops on first entry into the 0.14 m goal region. The direct-pair saving,
stability, parked-body drift, path-length, and contact checks retained wider
margins. Carrier path reduction is a paired loaded-carrier result; it is not a
claim about total team travel, energy, task time, or throughput.

## Recovery integrity

V1 placed all 90 bodies in one scene, so every serial control step paid the
global solver cost for all 90. Its four-hour attempt and unchanged 12-hour
recovery both reached external watchdogs before the single final report write;
the latter exited `124`. A third unchanged recovery was stopped only after the
separate V2 protocol had been fixed and before V1 exposed a report or per-seed
outcome. Those unsuccessful attempts remain archived and are not relabeled as
V2 results.

V2 preserved the fixed seed cases, archived decisions, within-seed geometry,
wheel controller, and acceptance bar while separately versioning the global
solver, execution, and persistence topology. It exclusive-published one atomic
checkpoint after every fixed seed, in order, before starting the next. The
retained formal-run records show all 30 workers completed on attempt 1 with
exit code zero, no resume, no completed-checkpoint rerun, and no seed
replacement. It ran from `2026-08-04T16:29:53Z` to
`2026-08-04T16:48:14Z`; the 18-minute duration is an engineering fact, not a
throughput benchmark.

The successful formal run did not exercise resume. The mechanism validates and
skips an exact fixed-order checkpoint prefix, but this evidence does not claim
transactional recovery across every possible coordinator crash or host-power
loss boundary between checkpoint, ledger, report, and checksum publication.

Both the Radeon host and the local frozen source snapshot independently
accepted the byte-identical report:

```text
PASS: additive decision-to-dynamics recovery V2 30/30
report_sha256=1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99
```

The retained attempt ledger and worker logs show exactly 30 first-attempt
worker completions, all with exit code zero. A post-run provenance review also
records two proof-scope limits instead of overstating them: the formal checksum
index did not originally cover the attempt/progress/log files, and the formal
source manifest omitted the directly imported `src/v4_motion.py`. A clean
2,419-file post-run tree audit found no source difference, no writable non-Git
file, and byte identity between that dependency and commit `b0c4f0d`. This is
corroborating evidence, not a claim of signed continuous attestation. See
`PROVENANCE_REVIEW.json` in the sealed result directory.

Verify the sealed directory without Genesis or a GPU:

```bash
cd release/v8-derived/decision_dynamics_recovery_v2_102500_102529
shasum -a 256 -c SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  release/v8-derived/decision_dynamics_recovery_v2_102500_102529/REPORT.json
```

## Evidence identities

| Artifact | SHA256 |
| --- | --- |
| Complete report | `1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99` |
| Source binding | `c40f6ba74a39ad761e4926ddb66326f33a1a645fef3c96364f9c53b9d5d3eb5d` |
| Recovery execution audit | `344a948da49f89322f3486da2c025ee227dbf3454b33f7f8ab2f8acf6ea8eca4` |
| Post-run provenance review | `4667a9f817c882e7cbe6b358c207a2fb3cc6afec643e185e99fbd30ae0f959a7` |
| Complete 79-file package checksum index | `24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540` |
| Bound source commit | `b0c4f0d33b0a2d0c647dda0b2b3b7c03279a511a` |

## Interpretation boundary

This closes a narrow evidence gap: the 30 archived V8 route outcomes can be
bound to paired, wheel-actuated rigid-body execution across 30 fixed Genesis
scenes. Every body reached its goal; all 29 direct decisions retained a
physical loaded-carrier path advantage; and the single dual-blocked decision
executed its declared safe outer detour with zero recorded blocker-contact or
active-pair contact rows.

It remains an archived-decision replay in static simulation. The 90 bodies are
distinct instantiations across 30 scenes, not one simultaneous 90-body scene.
The result does **not** rerun the frozen perception-policy loop, demonstrate
simultaneous cooperative motion, validate dynamic-obstacle response, replace
the preregistered 29/30 primary endpoint, or establish a physical-robot,
sim-to-real, energy, throughput, or safety-certification result.
