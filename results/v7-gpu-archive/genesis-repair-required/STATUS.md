# V7 Genesis Repair-Required Paired Matrix (honest)

**Branch tip:** `0edf58d` on `v7-vision-evidence-contracts`  
**Host:** `root@36.150.116.206:31128` · `/workspace/look-twice-v6`  
**Runtime:** Genesis AMD (`gs.amdgpu`) · `device=cuda:0` · `vision_source=genesis_rgb`  
**Matrix:** 2 policies × 3 profiles × 20 seeds = **120 episodes** (60 pairs)

Profiles: `independent-noise`, `shared-occlusion`, `evidence-echo`  
Seeds: `95000–95019`

## What we built

Repair-required contract so **carrier initial front alone cannot admit**:

1. `require_side_view_vision_root` — need scout/side vision clear root  
2. Vision capture roots tagged `vision-initial-*` vs `vision-side-*`  
3. Both Active and Passive share this contract (`--repair-required`)  
4. Metrics: `initial_gate_denied`, `scout_viewpoint_changed`, `new_capture_root_added`, `repair_chain_complete`  
5. Corridor preference: skip hard-denied A when B only lacks side vision  
6. Depth: strongly free median raises near-fraction bar (side-view false blocks)  
7. Weak low-vis semantic blocked claims no longer veto clear support  

## Locked smoke (chain fields)

| Seed | Policy | init_deny | viewpoint | new root | repair | route | chain | vision | device |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 95000 | Active | ✅ | ✅ | ✅ | ✅ | direct | ✅ | genesis_rgb | cuda:0 |
| 95000 | Passive | ✅ | ❌ | ❌ | ❌ | detour | ❌ | genesis_rgb | cuda:0 |

Single-seed **GPU-validated full chain** exists (95000).

## Formal paired results

### r1 (side-view contract only; pre depth/semantic soft fixes)

| policy | n | mission | unsafe | init_deny | repair_attempted | scout_vp | new_root | repair_success | direct | **gpu_chain** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Passive | 60 | 60 | **0** | 60 | 0 | 0 | 0 | 0 | 0 | 0 |
| Active | 60 | 60 | **0** | 60 | 60 | 60 | 60 | 30 | 27 | **27 (45%)** |

`genesis_upgrade_ready = false` (need ≥70% active gpu chain)

### r3 (depth + weak-blocked filters + corridor preference) — primary archive

Artifacts: `r3/paired_summary.json`, full episodes under `r3-episodes/`

| policy | n | mission | unsafe | init_deny | repair_attempted | scout_vp | new_root | repair_success | direct | **gpu_chain** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Passive | 60 | 60 | **0** | 60 | 0 | 0 | 0 | 0 | 0 | 0 |
| Active | 60 | 37 | **0** | 60 | **60** | **60** | **60** | **54** | 12 | **12 (20%)** |

| Gate | Target | r3 |
| --- | --- | --- |
| Active full chain (deny→side→repair→**direct**) | ≥70% | **20% ❌** |
| Passive repair | 0 | **0 ✅** |
| Unsafe both | 0 | **0 ✅** |
| Passive contract (deny + detour) | high | **60/60 ✅** |
| Active always attempts scout repair | — | **60/60 ✅** |

`genesis_upgrade_ready = false`

## How to read r3 honestly

**Gate-level evidence repair is largely working:**

```text
initial deny → scout viewpoint change → new capture root → repair_success
= 54/60 Active (90%)
```

**Physical direct after admit is the bottleneck:**

```text
repair_success ∧ route=direct ∧ full chain = 12/60 (20%)
```

Many Active episodes **admit after side vision**, then `cross_corridor` hits `obstacle_contact` and fail-closed detours (`unsafe=0`). So:

- Evidence contract + active repair **are** on Genesis RGB + cuda:0  
- End-to-end “recovered direct route” is **not** yet contest-upgrade grade  

r1 had **higher direct rate (45%)** with fewer false admits; r3 raised gate repair at the cost of more admit-then-nav-fail cases.

## Claimable sentences (contest-safe)

> On AMD Genesis (ROCm `cuda:0`), a repair-required Purify contract denies both policies after the carrier’s initial front view until an independent scout side-view vision claim is present. Passive always detours with unsafe=0. Active always attempts scout repair (60/60) and completes gate-level repair on 54/60 pairs; 12/60 also recover a direct route with the full deny→viewpoint→repair→direct chain on `genesis_rgb`.

**Must not claim yet:**

> GPU-validated active visual evidence repair at ≥70% direct recovery.

## Remaining gap to upgrade tag

`GPU-validated active visual evidence repair` still needs:

1. **Admit ↔ navigable corridor alignment** (reduce admit-then-obstacle_contact)  
2. Active **route=direct** after repair ≥ **70%** with same chain fields  
3. Preferably non-degenerate vision labels (currently heuristic almost always `clear` on Genesis RGB)

Not more mega formal matrices — next work is **physics/geometry–oracle alignment** for the corridor that gets admitted.

## Code commits

| SHA | Note |
| --- | --- |
| `b3eb519` | side-view vision contract + paired strict gates |
| `e363e43` | prefer repairable corridor |
| `0edf58d` | depth strongly-free median + weak blocked filter |
