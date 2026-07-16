# v5 paired capability evaluation — 90 episodes

## Framing

| Field | Value |
| --- | --- |
| Kind | **paired capability evaluation** |
| Calibration | **smoke** (`--allow-smoke-calibration`) |
| Formal Gate B | **NO** |
| Device | AMD Radeon PRO W7900D · `cuda:0` · `gs.amdgpu` |
| Claims | `genesis_rgbd_depth_semantic` on **90/90** |
| Motion | kinematic |
| Code semantics | post-r3 (`ce8ae3b` detour/side_view) |
| Workers | 2 |
| Wall | ~1296 s (~21.6 min) |
| Completion | **90 ok · 0 fail · 0 skipped** |

## Provenance

- **Executable source commit:** `ce8ae3b` (`Fix repair-required detour nav credit and real side_view moves`).
- The temporary cloud snapshot had no `.git` directory and retained the stale
  `.git_commit` marker `d7ab2f7`. Raw episode JSON preserves that value; it must
  not be interpreted as the executable source revision.
- SHA256 hashes of `src/repair_planner.py`, `src/v5_episode.py`,
  `src/v5_genesis_runtime.py`, and `src/v5_scenario.py` matched byte-for-byte
  between the W7900D instance and commit `ce8ae3b` at archive verification time.
- Raw JSON remains unchanged. `rollup.json` was independently regenerated from
  all 90 episode files and matched the archived rollup byte-for-byte.

## Formal narrative (required)

> Active 以额外观察成本换取证据修复和正确直接通行，消除了 clear 场景的错误绕行。

**禁止**宣称 active 路径更短或更快：本矩阵 mean path / steps 均为
active (10.22 m / 1739) **>** passive (8.54 m / 1456) **>** naive (7.38 m / 1136)。

## Matrix

```text
3 policies × 6 profiles × 5 paired seeds (50000–50004) = 90
```

Profiles: `independent-noise`, `shared-occlusion`, `evidence-echo`, `time-skew`,
`dynamic-change`, `repair-required`.

## Headline by policy (N=30 each)

| policy | mission | nav | unsafe | wrong_detour | repair_success | direct | detour | real_side_view | mean path | mean steps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 18 | 20 | **10** | 3 | 0 | 17 | 3 | 0 | 7.38 | 1136 |
| purify-passive | **27** | 30 | **0** | **9** | 0 | 9 | 21 | 0 | 8.54 | 1456 |
| purify-active | **27** | 30 | **0** | **4** | **5** | **14** | 16 | **31** | **10.22** | **1739** |

### Active vs passive (honest)

| signal | passive | active | reading |
| --- | ---: | ---: | --- |
| unsafe | 0 | 0 | both fail-closed vs naive |
| mission | 27 | 27 | **parity** on this cut |
| wrong_detour | 9 | **4** | active fewer wrong detours |
| direct routes | 9 | **14** | active more gated direct |
| repair_success | 0 | **5** | only active repairs |
| real side_views | 0 | **31** | real relocates |
| mean path / steps | lower | **higher** | observation cost |

## Profile highlights

- **repair-required** (the r3 story at N=5):
  passive 5/5 detour, wrong_detour=3 (clear seeds);
  active 5/5 mission, wrong_detour=**0**, repair_success=3, direct=3 on clear, real_side_view=12.
- **shared-occlusion**: both purify safer than naive; mission still hard (2/5); active has repair_success=2, fewer wrong_detour than passive (1 vs 3).
- **dynamic-change**: all policies mission 5/5 unsafe 0; active/passive both detour-heavy (world flip).
- **independent-noise / evidence-echo / time-skew**: purify mission 5/5 unsafe 0; naive ~3/5 with unsafe on blocked.

## Artifacts

- Local: `results/capability-v5-paired-90/` (90 JSON + logs + `rollup.json` + `parallel_summary.json`)
- Cloud: `outputs/v5-paired-capability-90`
- Rollup tool: `scripts/summarize_v5_paired_capability.py`

## Non-claims

- Not formal Gate B / Full Purify promotion.
- Smoke calibration only.
- Does not claim active is shorter or faster.
