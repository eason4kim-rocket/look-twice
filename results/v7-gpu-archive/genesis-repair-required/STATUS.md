# V7 Genesis Repair-Required — STATUS (honest)

**Branch tip:** `f315a02` on `v7-vision-evidence-contracts`  
**Host:** `root@36.150.116.206:31128` · `/workspace/look-twice-v6`  
**Phase lock:** world homology **closed**. Next = **Genesis RGB vision calibration only**  
(no further motion / obstacle rewrites; no relaxing blocked-claim thresholds).

## Freeze policy (do not overwrite)

| Archive | Meaning | Touch? |
| --- | --- | --- |
| `r1/` | Pre-homology side-view contract; **45% full chain** | **FROZEN** |
| `r3/` + `r3-episodes/` | Gate repair 90% but world mismatch; **20% direct** | **FROZEN** |
| `homology-physics8/` | Oracle==physics collision check 8/8 | keep |
| `homology-smoke-3x2/` | Post-homology 12-ep capability smoke | keep |
| `homology-paired-3x20/` | Full 120 after homology (when complete) | write only here |

**r3 is not an upgrade candidate.** It exposed Gate admit → wrong physics.

## Root cause (fixed in `67cb253`)

V6 Genesis was:

```python
v4_scenario = sample_v4_scenario(physics_profile, scenario.seed)
# independent V4 obstacle_xy RNG — not V6 oracle
```

V6 oracle / synthetic used `(1.0, ±0.3)` while Genesis used a random V4 base-world obstacle.  
`set_obstacle()` only appended to a Python list — **no Genesis entity move**.

### Fix

- `v6_aligned_v4_scenario()` forces obstacle anchors from V6 oracle  
- Primary + secondary Genesis boxes at A/B anchors (created before `scene.build`)  
- Real `set_obstacle()` → `entity.set_pos`  
- `world_alignment_audit()` → `world_alignment_passed`, `obstacle_pose_error`  
- Corridor **approach → entry → mid → exit** centerline path  

## Physics validation (8 force-corridor)

`homology-physics8/physics_alignment_summary.json`

| Check | Result |
| --- | --- |
| n | 8 |
| world_alignment_passed | **8/8** |
| physics_ok (contact iff blocked) | **8/8** |
| all_passed | **true** |

Seeds: A-only `95001,95003`; B-only `95002,95004`.

## Capability smoke (12 = 2 pol × 3 prof × 2 seeds)

`homology-smoke-3x2/`

| Gate | Target | Result |
| --- | --- | --- |
| world_alignment_passed | 12/12 | **12/12** |
| Passive deny → detour | 6/6 | **6/6** |
| Active init_deny + scout + new root | 6/6 | **6/6** |
| clear admitted collision | 0 | **0** |
| unsafe | 0 | **0** |
| Active full chain | ≥4/6 | **4/6** |

Active: repair_success 5/6, direct/chain **4/6 (67%)**, rate slightly under formal 70% threshold on this tiny n.

## Pre-homology baselines (frozen numbers)

### r1

| policy | repair_success | direct / chain | unsafe |
| --- | ---: | ---: | ---: |
| Passive | 0/60 | 0 | 0 |
| Active | 30/60 | **27/60 (45%)** | 0 |

### r3

| policy | repair_success | direct / chain | unsafe |
| --- | ---: | ---: | ---: |
| Passive | 0/60 | 0 | 0 |
| Active | 54/60 (90% gate) | **12/60 (20%)** | 0 |

## Full 120 matrix (homology) — COMPLETE

Local: `homology-paired-3x20/` · GPU: `outputs/v7/genesis-repair-required-paired-3x20-homology`

| Metric | Target | Result | Pass |
| --- | --- | ---: | --- |
| Active initial deny | 60/60 | **60/60** | ✅ |
| Scout viewpoint changed | 60/60 | **60/60** | ✅ |
| New independent root | 60/60 | **60/60** | ✅ |
| Gate repair | ≥48/60 | **57/60 (95%)** | ✅ |
| **Full repair→direct chain** | **≥42/60** | **32/60 (53%)** | ❌ |
| Unsafe | 0 | **0** | ✅ |
| Clear admitted collision | 0 | **0** | ✅ |
| World alignment | 60/60 (×2 pol) | **120/120** | ✅ |
| Passive repair | 0 | **0** | ✅ |
| Passive safe detour | 60/60 | **60/60** | ✅ |

`genesis_upgrade_ready = false` (chain 53% < 70%)

### vs frozen baselines

| Run | World | Gate repair | Full chain | clear_admitted_collision |
| --- | --- | ---: | ---: | ---: |
| r1 | mismatched | 50% | **45%** | n/a |
| r3 | mismatched | 90% | **20%** | high admit-then-fail |
| **homology** | **aligned** | **95%** | **53%** | **0** |

Homology fixed the physics bug: **no admit-then-contact / clear_admitted_collision**.  
Remaining misses are mostly **false gate admits of oracle-blocked corridors** (heuristic vision nearly always `clear`) → fail-closed detour via truth check, mission still complete, unsafe=0.

## Vision (separate issue — do not mix)

Heuristic labels still nearly all `clear` on Genesis RGB (`clear=203`). Even with world homology, this drives false admits. Next workstream (not mixed into this fix): Genesis RGB dataset + non-degenerate vision calibration.

## Claimable now

> V6/V7 oracle corridor obstacles are the same entities used for Genesis collision and rendering (`world_alignment_passed` 120/120). Force-corridor physics checks pass 8/8. On the 120-episode repair-required paired matrix, Active completes gate-level evidence repair on 57/60 pairs and full deny→scout→repair→direct on **32/60 (53%)**, with unsafe=0, clear-admitted collision=0, and Passive always fail-closed detour.

## Not claimable yet

> GPU-validated active visual evidence repair at ≥70% (42/60) full chain.

Next (separate): reduce false clear admits of blocked corridors — vision/geometry calibration, not more world rewiring.
