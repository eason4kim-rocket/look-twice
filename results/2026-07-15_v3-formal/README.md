# Look Twice v3 formal experiment

This directory records the 500-episode core v3 comparison generated on the
AMD Radeon PRO W7900D. Every raw episode reports source commit
`4d964182ec90d5eed2fdbf0382d2adc090091f95`, schema v3, ROCm device `cuda:0`,
and a reproducible scenario/noise seed.

## Matrix

```text
5 policies × 5 randomized profiles × 20 paired test seeds = 500 episodes
```

Even seeds start clear and odd seeds start blocked. Obstacle geometry,
occluder geometry, event delay, unreachable viewpoints and sensor severity
remain continuously randomized. All policies receive the same scene for a
given profile/seed.

## Dynamic-change result

| Policy | Safe success | Unsafe crossing | Wrong detour | Observations | Path |
| --- | ---: | ---: | ---: | ---: | ---: |
| Single Shot | 50% | 50% | 50% | 1.00 | 7.02 |
| Fixed Multi-View | 50% | 50% | 50% | 3.00 | 11.12 |
| Purify Fixed | **100%** | **0%** | **0%** | 4.00 | 10.16 |
| Purify Random | **100%** | **0%** | 35% | 3.80 | 12.50 |
| Purify Information-Gain | **100%** | **0%** | **0%** | 4.05 | 10.61 |

The temporal Action Gate, not repeated voting alone, prevents unsafe entry
after the world changes. This benefit costs additional evidence. Random
viewpoint changes remain safe but waste motion and sometimes retain an
unnecessary detour after the obstacle clears.

## Next-Best-View finding

Information-Gain NBV beats Random NBV in every profile:

- paired mean path reduction: 1.74–2.27 units;
- all five 95% bootstrap intervals exclude zero;
- information gain per movement improves by 0.19–0.23.

It does **not** consistently beat Purify Fixed. Across all profiles, mean path
is 10.24 for Information-Gain and 10.07 for Fixed. The project therefore does
not claim that the heuristic is universally optimal. This limitation motivates
the separately gated Learned NBV experiment.

## AMD GPU benchmark

The benchmark uses 20 warm-up iterations and 100 timed iterations at 320×240.

| Batch | CPU kernel obs/s | W7900D kernel obs/s | Kernel speedup | End-to-end speedup |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1,533 | 4,212 | 2.75× | 2.64× |
| 8 | 1,925 | 33,738 | 17.53× | 2.88× |
| 32 | 2,823 | 72,119 | 25.55× | 4.72× |
| 128 | 670 | 99,166 | 148.03× | 15.02× |

Kernel and end-to-end transfer timings are reported separately. Genesis
rendering and Python state-machine time are not presented as GPU kernel time.

## Files

- `runs.csv` — one row for every episode;
- `aggregate.csv` — 25 policy/profile aggregates with Wilson intervals;
- `calibration.csv` — 10-bin ECE from raw evidence traces;
- `paired_comparisons.csv` — paired 5,000-sample bootstrap comparisons;
- `benchmark.json` — warmed CPU/ROCm measurements;
- `v3-comparison.png` — core result figure;
- `representative/` — selected traceable JSON episodes;
- `SHA256SUMS` — hashes for all 500 raw JSON files backed up on the Mac.

The complete raw directory is stored under the ignored local path
`outputs/v3-formal-4d96418/raw/`. All 500 hashes were verified after download.

## Reproduce

```bash
/opt/venv/bin/python scripts/run_v3_experiments.py \
  --output-dir outputs/v3-formal-4d96418 \
  --seed-count 20 \
  --seed-offset 20000 \
  --workers 1 \
  --python /opt/venv/bin/python

/opt/venv/bin/python scripts/summarize_v3_experiments.py \
  --runs outputs/v3-formal-4d96418/runs.csv \
  --output outputs/v3-formal-4d96418/aggregate.csv

/opt/venv/bin/python scripts/analyze_v3_results.py \
  --raw-dir outputs/v3-formal-4d96418/raw \
  --output-dir outputs/v3-formal-4d96418
```
