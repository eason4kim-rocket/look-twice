# Look Twice v6 — final capability STATUS

Branch: `v6-collaborative-evidence-repair`  
GPU archive: AMD Genesis RGB-D (`genesis_rgbd_multi_agent_v6`), resume-safe matrices  
Completed: 2026-07-18 (handoff `V6_COMPLETE_HANDOFF.json`)

## What v6 is

Multi-agent collaborative evidence repair: carrier does not cross without Purify admit; scout collects independent views; gated direct when clear roots admit, else fail-closed detour.

## Matrices (all `fail=0`)

| Matrix | Jobs | parallel_summary |
| --- | ---: | --- |
| physics-180 | 180 | ok=160 skipped=20 |
| formal-locked-3x6x100 | 1800 | ok=1041 skipped=759 |
| formal-learned-3x6x100 | 1800 | ok=1604 skipped=196 |
| ood-3x2x500 | 3000 | ok=2662 skipped=338 |

`skipped` = valid episode JSON already present on resume (not failures).

### formal-locked (3 policies × 6 profiles × 100)

| policy | n | mission | unsafe | repair_success | direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 600 | 250 | 198 | 0 | 250 |
| purify-passive | 600 | 600 | 0 | 0 | 0 |
| purify-active | 600 | 600 | 0 | 100 | 94 |

### formal-learned

| policy | n | mission | unsafe | repair_success | direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| purify-active-learned | 600 | 600 | 0 | 100 | 100 |
| purify-active-dagger | 600 | 600 | 0 | 100 | 100 |
| purify-random | 600 | 470 | 0 | 68 | 51 |

### OOD (heavy-occlusion, multi-fault × 500 seeds)

| policy | n | mission | unsafe | repair_success | direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 1000 | 250 | 425 | 0 | 250 |
| purify-passive | 1000 | 1000 | 0 | 0 | 0 |
| purify-active | 1000 | 1000 | 0 | 250 | 250 |

### physics-180

| policy | n | mission | unsafe | repair_success | direct |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 60 | 25 | 15 | 0 | 25 |
| purify-passive | 60 | 60 | 0 | 0 | 0 |
| purify-active | 60 | 60 | 0 | 10 | 9 |

## Other delivered pieces

- Gate fix: usable-set deny reasons; `evidence_age_limit=2000` (repair_success + clear direct non-zero)
- DAgger×3 + synthetic promotion summary under `results/v6-learned-dagger/`, `results/v6-promotion-synthetic/`
- Diff-drive URDF + Genesis load + 20-seed waypoint bar: `results/v6-physics-urdf/`
- Demo assets: `results/v6-demo-video/`
- Genesis AMD note: `docs/genesis-amd-multi-agent-rgbd.md`

## Artifacts in this archive (repo)

- `V6_COMPLETE_HANDOFF.json`, `MATRIX_FINAL.json`, `V6_MATRIX_FINAL_STATUS.md`
- Per-matrix `*/parallel_summary.json`
- Full per-episode JSON is large; kept on the evaluation machine / local emergency mirror, not all committed

## Non-claims

- Not real-robot Gate B
- Not full rigid-body wheel-torque dynamics
- Not end-to-end VLA control

## Next

- v7: vision-grounded evidence contracts (separate branch `v7-vision-evidence-contracts`)
