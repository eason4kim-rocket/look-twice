# Paired capability evaluation — 90 episodes

## Framing (mandatory)

- **Kind:** paired capability evaluation
- **Calibration:** smoke (`--allow-smoke-calibration`)
- **Not** formal Gate B / Full Purify promotion
- **Device:** AMD Radeon PRO W7900D, `cuda:0`, `gs.amdgpu`
- **Claims:** `genesis_rgbd_depth_semantic`
- **Motion:** kinematic
- **Code base:** post-r3 (`ce8ae3b`+) on `v5-embodied-evidence`

## Formal narrative (active vs passive)

> Active 以额外观察成本换取证据修复和正确直接通行，消除了 clear 场景的错误绕行。

**Do not claim** active is shorter or faster when path/steps are higher
(as on repair-required r3 clear cells).

## Matrix

```text
3 policies × 6 profiles × 5 paired seeds = 90 episodes
```

| Axis | Values |
| --- | --- |
| policies | `naive`, `purify-passive`, `purify-active` |
| profiles | `independent-noise`, `shared-occlusion`, `evidence-echo`, `time-skew`, `dynamic-change`, `repair-required` |
| seeds | `50000` … `50004` (paired: even≈clear-ish, odd≈blocked by scenario convention) |

**Not included:** `manipulation-occlusion` (user matrix omits it).

## Primary metrics

- unsafe crossing
- mission success (`nav ∧ pick ∧ ¬unsafe`)
- wrong detour
- repair success
- direct / detour route (`route_mode`)
- real side-view count and distances
- total path length and simulation steps

## Output paths

- Cloud: `outputs/v5-paired-capability-90`
- Local archive: `results/capability-v5-paired-90/`
