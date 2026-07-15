# Look Twice v2 formal experiment

This directory records the 120-episode v2 comparison generated from commit
`f7a4e32467b984ef236eadbd767a99001c64113e` on the AMD Radeon PRO W7900D.

## Matrix

```text
4 policies × 5 scenario profiles × 6 seeds = 120 episodes
```

Policies: Single Shot, Majority Vote, Purify Fixed, and Purify Active.
Profiles: static clear, static blocked, high occlusion, dynamic appearance,
and shifted occluder.

## Key result

| Policy | Dynamic safe success | Unsafe crossing | Observations | Replans | Path length |
| --- | ---: | ---: | ---: | ---: | ---: |
| Single Shot | 0% | 100% | 1.0 | 0.0 | 5.74 |
| Majority Vote | 0% | 100% | 3.0 | 0.0 | 5.74 |
| Purify Fixed | 0% | 100% | 2.0 | 0.0 | 4.80 |
| Purify Active | **100%** | **0%** | 4.0 | 1.0 | 9.22 |

The result is intentionally not presented as a free improvement. Temporal
verification adds observation and path cost. Its benefit is preventing every
unsafe crossing in the dynamic-appearance profile.

In high occlusion, Active Purify required 2 observations versus 3 observations
and 2 replans for fixed Purify, demonstrating the Next-Best-View benefit.

## Files

- `aggregate.csv` — 20 policy/profile aggregate rows;
- `runs.csv` — metrics and configuration for all 120 episodes;
- `SHA256SUMS` — hashes for all raw JSON files stored in the Mac backup;
- `representative/` — selected traceable raw JSON examples;
- `v2-comparison.png` — core result figure.

All 120 raw JSON files are backed up under the ignored local
`outputs/v2-formal-f7a4e32/raw/` directory. Each JSON uses schema v2 and records
Git commit, ROCm/PyTorch/Genesis versions, evidence metadata, viewpoint scores,
dynamic events, Action Gate decisions, trajectory, and GPU device.

## Reproduce

```bash
/opt/venv/bin/python scripts/run_v2_experiments.py \
  --output-dir outputs/v2-formal-f7a4e32 \
  --seed-count 6 \
  --workers 1 \
  --python /opt/venv/bin/python

/opt/venv/bin/python scripts/summarize_v2_experiments.py \
  --runs outputs/v2-formal-f7a4e32/runs.csv \
  --output outputs/v2-formal-f7a4e32/aggregate.csv
```

Genesis instance segmentation is used transparently as a simulated sensor; no
claim is made that a learned vision model produced these masks. GPU timing
includes first-use ROCm warm-up.
