# v5 repair-required mini-eval **r3** (W7900D)

## Decision

| Question | Answer |
| --- | --- |
| r2 valid? | **NO** — invalidated (see below) |
| r3 valid mini-eval? | **YES** (`acceptance_all=true`) |
| Paired 90 run? | **NO** |
| Contest Gate B claim? | **NO** |
| Calibration | smoke (`--allow-smoke-calibration`) |

## Why r2 was invalidated

`results/capability-v5-repair-required/` (r2) is **preserved** for audit but **not** the
capability claim, for two semantic bugs:

1. **Detour scored as nav failure** — safe detour set `nav_success=False` /
   `mission_success=False`, so passive mission looked 0 even after safe arrival.
2. **Zero-distance “side_view”** — active repair reselected the current
   viewpoint (`left_near → left_near`, `path_length=0`), which is same-pose
   recapture, not viewpoint change.

r3 fixes both in shipped episode/planner code and re-runs the 9-episode matrix.

## Forcing condition

Profile `repair-required`: `initial_viewpoint_budget=1` (single initial root).

```text
passive → Gate deny → safe detour → nav+mission; clear ⇒ wrong_detour
active  → real unvisited side_view(s) → repair_success → direct (clear)
naive   → ungated corridor; blocked ⇒ unsafe
```

Mission remains: **nav ∧ pick ∧ ¬unsafe**. Safe detour **is** nav success.
`wrong_detour = detour_success ∧ oracle_clear`.

## Matrix

- Host: AMD Radeon PRO W7900D, `device=cuda:0`, `genesis_backend=gs.amdgpu`
- claims_mode: **genesis_rgbd_depth_semantic** on all 9
- 3 policies × seeds {50000, 50001, 50002} = **9/9 OK**
- Cloud: `outputs/v5-repair-required-eval-r3`
- Local: `results/capability-v5-repair-required-r3/`
- r2 archive: **untouched** at `results/capability-v5-repair-required/`

## Results

| policy | N | mission | nav | unsafe | direct | detour | repair_success | wrong_detour | real_side_views |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 3 | 2 | 2 | **1** | 2 | 0 | 0 | 0 | 0 |
| purify-passive | 3 | **3** | 3 | **0** | 0 | **3** | 0 | **2** | 0 |
| purify-active | 3 | **3** | 3 | **0** | **2** | 1 | **2** | **0** | **7** |

### Clear seeds (50000, 50002)

| | naive | passive | active |
| --- | --- | --- | --- |
| mission | True | True | True |
| unsafe | False | False | False |
| route_mode | direct | **detour** | **direct** |
| wrong_detour | False | **True** | **False** |
| repair_success | — | False | **True** |
| real side_view | 0 | 0 | **2 each** (≥0.90 m then ≥2.6 m) |

### Blocked seed (50001)

| | naive | passive | active |
| --- | --- | --- | --- |
| unsafe | **True** | False | False |
| mission | False | True | True |
| route | none (unsafe push) | detour | detour |
| wrong_detour | False | False | False |

### Active vs passive advantage (clear)

Not “mission 2 vs 0” (both complete via different routes). Differentiating signals:

| signal | passive | active |
| --- | ---: | ---: |
| wrong_detour (clear n=2) | **2** | **0** |
| route_mode | detour | **direct** |
| repair_success | 0 | **2** |
| real side_view moves | 0 | **4** total |
| mean path length | 5.92 m | 8.94 m (repair travel) |
| mean sim steps | 1187 | 1500 (repair travel) |

Active pays travel cost for second/third independent views; the win is **correct
direct routing under evidence**, not shorter chassis path on this cut.

## Acceptance checks

All **true** (see `rollup.json`):

- naive clear mission + direct
- passive clear detour + wrong_detour + mission
- active clear real side_view + repair_success + direct + mission
- naive blocked unsafe
- passive/active blocked safe detour, not wrong_detour

## Code surface

Uncommitted base was `f10cef2` + repair-required work; r3 also includes:

- detour → `nav_success` + `route_mode` / `wrong_detour` metrics
- planner: visited / too-close side_view **ineligible**
- episode: force unvisited side_view when roots insufficient; decision fields
  `previous_viewpoint`, `selected_viewpoint`, `planned_distance`,
  `actual_distance`, `viewpoint_changed`, `action_kind_executed`

Local↔cloud SHA256 of critical sources **matched** at archive time.

## Non-claims

- No paired 90.
- No Gate B / Full Purify promotion.
- Smoke calibration only.
- r2 numbers must not be cited as the repair-value proof.
