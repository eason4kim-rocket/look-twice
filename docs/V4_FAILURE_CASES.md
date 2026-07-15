# Look Twice v4 failure-case record

Updated from archived **W7900D Genesis** JSON under `results/v4-gpu/`.
Synthetic Mac episodes are not used as formal failure evidence.

## Reporting rule

Never delete a run because it is unsafe, unresolved, slow, malformed, or fails
a promotion gate. Keep it in `runs.csv` and record:

```text
profile / policy / seed / commit / runtime / motion backend
calibration artifact ID and SHA256
world truth (evaluation-only)
Claims and lineage roots used/discounted
GateReceipt and BeliefGap
repair ranking and selected action
PlanInvalidationReceipt
trajectory, controls, contacts, and evidence artifacts
observed failure and root-cause hypothesis
whether a code fix changed the frozen protocol
```

If a fix changes policy logic, contracts, profiles, calibration, or utility,
rerun the affected calibration/validation process and do not reuse the locked
test as development data.

## Representative W7900D cases (smoke matrix, fitted calibration, kinematic)

### Case A — Fail-closed unresolved (wrong detour, no unsafe entry)

| Field | Value |
| --- | --- |
| Path | [`results/v4-gpu/smoke-genesis/raw/purify-active__independent-noise__seed-50000.json`](../results/v4-gpu/smoke-genesis/raw/purify-active__independent-noise__seed-50000.json) |
| Policy / profile / seed | `purify-active` / `independent-noise` / `50000` |
| GPU / backend | AMD Radeon PRO W7900D / `kinematic` / `gs.amdgpu` |
| Commit | `07f852e5c0f2ef1abb0ac53a576b2c1ce6d73da8` |
| Truth (oracle only) | `clear` |
| Outcome | `safe_fallback` / `resolved_value=unresolved` / reason `pre_detour_gate_unreachable` |
| Metrics | `unsafe_crossing=false`, `safe_success=false`, `wrong_detour=true`, `observation_count=2`, `collision_count=2` |
| Gate | First receipt `admitted=false`, prediction set `{clear, blocked}`, BeliefGaps include `stale`, `shared_root`, `insufficient_roots`, `low_coverage` |

**Hypothesis:** Contract never admitted `cross_region`. The robot attempted a
detour approach, contacted geometry before the pre-detour gate, and aborted.
This is a **conservative fail-closed** path with false abstention cost, not an
unsafe risk-region entry.

**Retained as limitation:** motion reachability of detour waypoints under
kinematic contact; not fixed by relaxing the Action Contract.

### Case B — Mission completed via labelled safe fallback (repair budget exhausted)

| Field | Value |
| --- | --- |
| Path | [`results/v4-gpu/smoke-genesis/raw/purify-active__shared-occlusion__seed-50000.json`](../results/v4-gpu/smoke-genesis/raw/purify-active__shared-occlusion__seed-50000.json) |
| Policy / profile / seed | `purify-active` / `shared-occlusion` / `50000` |
| GPU / backend | AMD Radeon PRO W7900D / `kinematic` / `gs.amdgpu` |
| Commit | `07f852e5c0f2ef1abb0ac53a576b2c1ce6d73da8` |
| Truth (oracle only) | `clear` |
| Outcome | `safe_fallback` / `unresolved` / reason `repair_budget_exhausted` |
| Metrics | `unsafe_crossing=false`, `safe_success=true`, `wrong_detour=true`, `observation_count=4`, `collision_count=0` |
| Gate | Denied singleton `{clear}`; active repair consumed the observation budget |

**Hypothesis:** Shared occlusion kept prediction sets multi-valued; BeliefGap
repair used four observations without admitting `cross_region`. The episode
still reached the goal on the labelled detour, so task success is true while
`wrong_detour` correctly flags a clear world.

**Retained as limitation:** active repair does not guarantee contract repair
within budget; promotion threshold (80% repair) is **not** claimed from smoke N.

### Case C — Evidence echo lineage discount (auditable DAG)

| Field | Value |
| --- | --- |
| Path | [`results/v4-gpu/smoke-genesis/raw/purify-active__evidence-echo__seed-50000.json`](../results/v4-gpu/smoke-genesis/raw/purify-active__evidence-echo__seed-50000.json) |
| DAG | [`results/v4-gpu/figures/evidence_dag_purify-active_evidence-echo_seed-50000.dot`](../results/v4-gpu/figures/evidence_dag_purify-active_evidence-echo_seed-50000.dot) |
| Metric | `echo_rejection_success=true` |
| Gate discounts | repeated `artifact_duplicate_of:…` reasons on discounted Claims |

**Hypothesis:** Multiple Claims shared artifact hashes; Go core collapsed them
so echo copies did not inflate independent measurement roots.

## Failure categories to audit

| Category | Required evidence | Formal status |
| --- | --- | --- |
| Unsafe crossing | risk entry, truth, gate, trajectory/contact | **0** in archived smoke 96; formal partial N=40 raw also **0** unsafe (incomplete matrix) |
| False abstention/wrong detour | decisive evidence and denied contract clause | **Measured** — Case A/B |
| Echo accepted as independent | Claim DAG, artifact/capture/device roots | **Counter-example measured** — Case C rejects echoes |
| Miscoverage | prediction set, true label, artifact/domain | Smoke CIs only; formal incomplete |
| OOD incorrectly admitted | applicability clause and runtime context | Smoke OOD rows present; fail-closed expected |
| Repair budget exhausted | all rankings, visited actions, observations | **Measured** — Case B |
| Wrong/missed plan invalidation | old/new receipts and triggering Claims | Present in JSON when triggered; no counterfeit claim |
| Skid-steer timeout/contact | controls, wheel targets, trajectory, contacts | **Acceptance failed** — see below |
| Sensor artifact failure | raw/corrupted file hashes and exception | None in smoke 96 |
| Process/protocol failure | NDJSON request ID, error, timeout, stderr tail | Formal partial: `results/v4-gpu/formal-genesis/errors/naive-majority__independent-noise__seed-50018.error.json` |

## Known engineering limitations, not measured failures

- Entity segmentation is a simulated semantic proxy, not a trained model.
- The kinematic Genesis batch backend uses `set_pos()`/`set_quat()` after
  integrating bounded velocity commands.
- Skid-steer W7900D acceptance **failed** (2026-07-15): 10 seeds × 4
  viewpoints produced 14 failures with position errors above 0.10 m; multi-scene
  teardown also hit SIGSEGV. Formal matrices demote to the kinematic motion
  backend per plan. Artifact on GPU: `outputs/v4-motion-accept/skid_10x4.json`
  (summary copied under implementer scratch / STATUS).
- No real robot or sim-to-real result exists.
- Conformal coverage applies only to the declared simulated ID distribution.
- Calibration split is **partial** (336/350): `results/v4-gpu/calibration/PARTIAL_SPLIT.txt`.
- The public Go core is a contest reference slice, not the private Purify
  product or a certified controller.

## Formal matrix honesty (in progress)

| Item | Value |
| --- | --- |
| Design size | 6 × 8 × 20 = **960** |
| Packaged on Mac/GitHub (this sync) | **40** completed raw + **2** error JSON |
| GPU runner | still writing `/workspace/look-twice/outputs/v4-formal-genesis` |
| Unsafe in packaged formal subset | **0** (N too small for promotion certification) |

## Final submission checklist for this file

- [x] Add at least one representative safe resolution and one unresolved or
  failed episode from W7900D artifacts.
- [x] Link raw JSON and evidence DAG by relative path.
- [x] Explain whether failure arose from perception, lineage, calibration,
  planning, motion, protocol, or experimental infrastructure.
- [x] State whether the final system fixed it or retains it as a limitation.
- [x] Ensure aggregate counts still include every documented case
  (`results/v4-gpu/smoke-genesis/summary/runs.csv`).
