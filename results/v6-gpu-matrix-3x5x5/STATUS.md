# Look Twice v6 — GPU full verification (Genesis RGB-D multi-agent)

## Framing

| Field | Value |
| --- | --- |
| Branch | `v6-collaborative-evidence-repair` |
| Host | `root@36.150.116.206:31128` · `/workspace/look-twice-v6` |
| GPU | AMD Radeon Graphics (`cuda:0`, ROCm / PyTorch 2.9.1) |
| Genesis | 1.1.2 · backend `gs.amdgpu` |
| Runtime | **genesis** dual-agent RGB-D (not synthetic-only) |
| Claims mode | **`genesis_rgbd_multi_agent_v6`** on **75/75** |
| Calibration | smoke path (no formal Gate calibration artifact) |
| Formal Gate B | **NO** |
| Real robot | **NO** |
| Primary active policy | **purify-active heuristic** (learned not trained) |

## Matrix

```text
3 policies × 5 profiles × 5 seeds = 75 episodes
workers=2, process-isolated, resume-by-valid-file
wall ≈ 900 s
ok=75 fail=0 skipped=0
```

Profiles: `independent-noise`, `shared-occlusion`, `evidence-echo`, `time-skew`, `dynamic-change`.  
Seeds: `90000`–`90004`.

Remote dir: `outputs/v6/gpu-matrix-3x5x5`  
Local archive: `results/v6-gpu-matrix-3x5x5/`  
Single proof: `gpu-single/purify-active__shared-occlusion__90000.json`

## Headline results

| policy | N | mission | unsafe | repair_attempted | repair_success | direct | detour |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 25 | 12 | **7** | 0 | 0 | 12 | 0 |
| purify-passive | 25 | **25** | **0** | 0 | 0 | 0 | 25 |
| purify-active | 25 | **25** | **0** | **25** | 0 | 0 | 25 |

### Safety

- Purify gated policies: **unsafe_crossing = 0** on full matrix.
- Naive shows unsafe on blocked-style seeds (7/25) — contrast holds.
- All episodes include mission fields: `carrier_reached_goal`, `payload_delivered`, `unsafe_crossing`, collisions, deadline.

### RGB-D path

- Single-episode proof: `claims_mode=genesis_rgbd_multi_agent_v6`, `device=cuda:0`, `n_rgbd_audits=4`, evidence requests present when denied.
- Matrix: **75/75** genesis RGB-D multi-agent claims (no synthetic-only substitution).

### Honest active vs passive (this cut)

- Mission parity (both 25/25 via **safe detour**).
- Active **always** attempted repair (`repair_attempted=25`) but **did not** achieve contract repair success under smoke-cal RGB-D (`repair_success=0`) — so route stayed detour, not direct.
- **Do not claim** active is shorter/faster or that active already wins wrong-detour/direct on this GPU cut; observation cost was paid without admit under current RGB-D+smoke-cal regime.
- Narrative for this archive: Purify keeps the team **safe**; active **attempts** cross-agent evidence repair on GPU RGB-D; promotion of learned policy and higher admit rates remain future work.

## Code surface

- `src/v6_genesis_runtime.py` — dual-agent Genesis adapter
- `src/look_twice_v6.py` — `--runtime genesis --device cuda:0`
- `src/v6_episode.py` — RGB-D observe → Claim v2 → gate / evidence request
- `scripts/run_v6_parallel_matrix.py` — process-isolated matrix

## Non-claims

- Not formal 4800 locked / Gate B / real-robot.
- Not learned-policy superiority.
- Not “active always direct” on GPU RGB-D smoke cal.
