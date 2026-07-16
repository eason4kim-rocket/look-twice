# v5 repair-required mini-eval **r2** (W7900D) — INVALIDATED

> **Superseded by r3.** This archive is kept for audit only.
> Bugs: (1) safe detour scored as `nav_success=False` / mission fail;
> (2) zero-distance `side_view` revisits (`path_length=0`).
> **Valid mini-eval:** [`../capability-v5-repair-required-r3/STATUS.md`](../capability-v5-repair-required-r3/STATUS.md)

## Decision (historical — do not cite)

| Question | Answer |
| --- | --- |
| Strategy differentiation shown? | claimed YES under **buggy** metrics (invalid) |
| GO for paired 90 (eligibility)? | **superseded** — use r3 |
| Paired 90 auto-started? | **NO** |
| New contest tag / Gate B claim? | **NO** |

## Why this set exists

RGB-D smoke (24 eps) already showed Purify safer than naive, but **passive = active**
on mission (both 7/8, 0 unsafe). Expanding to 90 there would mainly re-prove “Gate
works,” not “active evidence repair has value.”

This mini-eval forces **initial evidence insufficiency**:

```text
initial_viewpoint_budget = 1   # single measurement root
passive → fail-closed deny → no gated nav → mission incomplete, unsafe=0
active  → side_view repair → second independent root → safe mission (clear world)
naive   → may ungated-cross → unsafe on blocked seed
```

## Matrix

- **Host:** AMD Radeon PRO W7900D, `device=cuda:0`
- **Claims:** `genesis_rgbd_depth_semantic` on all 9 episodes
- **Motion:** kinematic
- **Profile:** `repair-required` only
- **Policies × seeds:** 3 × {50000, 50001, 50002} = **9**, workers=2, **9/9 OK**
- **Wall:** ~131 s
- **Clear seeds:** even (50000, 50002); **blocked:** odd (50001)
- **Output dir (cloud):** `outputs/v5-repair-required-eval-r2`
- **Local archive:** `results/capability-v5-repair-required/`

## Results (mission = nav ∧ pick ∧ ¬unsafe)

| policy | N | mission | nav | pick | unsafe | repair_attempted | repair_success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 3 | 2 | 2 | 3 | **1** | 0 | 0 |
| purify-passive | 3 | **0** | 0 | 3 | **0** | 0 | 0 |
| purify-active | 3 | **2** | 2 | 3 | **0** | 3 | **2** |

### Clear-world contrast (seeds 50000, 50002)

| | passive | active |
| --- | ---: | ---: |
| mission | **0** | **2** |
| nav | 0 | 2 |
| repair_attempted | 0 | 2 |
| repair_success | 0 | **2** |
| unsafe | 0 | 0 |

### Blocked contrast (seed 50001)

- naive: **unsafe=1**, mission=0
- passive: mission=0, unsafe=0 (fail-closed)
- active: mission=0, repair_attempted=1, repair_success=0, unsafe=0  
  (correctly refuses to force a blocked corridor after failed repair)

### Per-episode

| policy | seed | mission | nav | unsafe | init_gate | repair_ok | outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| naive | 50000 | 1 | 1 | 0 | 0 | 0 | mission_complete |
| naive | 50001 | 0 | 0 | **1** | 0 | 0 | pick_ok |
| naive | 50002 | 1 | 1 | 0 | 0 | 0 | mission_complete |
| purify-passive | 50000 | 0 | 0 | 0 | 0 | 0 | pick_only_not_mission |
| purify-passive | 50001 | 0 | 0 | 0 | 0 | 0 | pick_only_not_mission |
| purify-passive | 50002 | 0 | 0 | 0 | 0 | 0 | pick_only_not_mission |
| purify-active | 50000 | **1** | 1 | 0 | 0 | **1** | mission_complete |
| purify-active | 50001 | 0 | 0 | 0 | 0 | 0 | pick_only_not_mission |
| purify-active | 50002 | **1** | 1 | 0 | 0 | **1** | mission_complete |

## Criteria

| ID | Statement | Result |
| --- | --- | --- |
| C1 | clear: passive mission=0, active mission≥1, active repair_success≥1 | **PASS** |
| C2 | purify unsafe=0 | **PASS** |
| C3 | naive unsafe≥1 on blocked | **PASS** |
| C4 | all claims_mode = genesis_rgbd_depth_semantic | **PASS** |

**GO_for_paired_90 = true** (C1 ∧ C2 ∧ C4). Still **do not** launch 90 without an
explicit decision — this only unlocks the *eligibility* to spend that GPU budget
on a design where active ≫ passive is the hypothesis under test.

## Mechanism (what made active win)

1. `repair-required` sets `initial_viewpoint_budget=1` → one root → gate deny
   (`shared_root` / `insufficient_roots`).
2. Active BeliefGap planner issues `side_view` → second independent root → admit
   (`repair_success`).
3. Boundary invalidation recheck **keeps** those repair roots on non-dynamic
   profiles (does not replace them with a single same_view boundary capture).
4. Re-eval after invalidation is allowed to stay admitted; the boundary repair
   loop only runs if still denied.
5. Passive never repairs → no gated cross → pick-only, not mission.
6. Detour remains available for chassis safety but **does not** grant `nav_success`.

### Provenance note (r1 → r2)

First GPU cut (`outputs/v5-repair-required-eval`) had active `repair_success=2`
but `mission=0`: boundary path wiped / polluted claim roots after a successful
repair, then forced a failing re-repair loop. r2 ships the boundary control-flow
fix; raw r1 JSON is left on the cloud host for audit, local archive is **r2 only**.

## Code surface (uncommitted at archive time)

Local branch `v5-embodied-evidence` tip was `f10cef2` (RGB-D smoke archive) with
**uncommitted** repair-required work:

- `src/v5_scenario.py` — profile `repair-required`, budget=1
- `src/v5_episode.py` — budget, repair metrics, detour no-nav-credit, boundary keep-roots
- `src/v5_genesis_runtime.py` — map repair-required → shared-occlusion evidence class
- `tests/test_v5_repair_required.py` — synthetic passive-deny / active-repair
- `tests/test_v5_core.py` — profile registration

Executable MD5 of `src/v5_episode.py` on W7900D matched local:
`4b99ceb169681e18fe35c1b70d2016bd`.

Unit: `tests/test_v5_repair_required.py` + `tests/test_v5_core.py` → **12 passed**.

## Recommended next (not executed)

1. **Commit + push** repair-required profile + boundary fix + this archive.
2. Only then design the **paired 90** around repair-required (or a mix that still
   stresses second-root acquisition), not a re-run of the undifferentiated 24-smoke
   profile mix.
3. Keep contest packaging frozen until the 90 (if run) is summarized honestly.
