# Formal policy comparison

This experiment contains **480 AMD GPU simulation episodes**:

```text
3 policies x 2 scenarios x 4 noise rates x 20 seeds = 480 runs
```

All runs were generated from Git commit
`3da503e33a39405893f0d62913798e89c7392e00` on an AMD Radeon PRO W7900D
with Genesis 1.1.2 and the `gs.amdgpu` backend.

## Main result

| Noise | Policy | Safe success | Unsafe crossing | Wrong detour | Avg. observations |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0.0 | Single Shot | 100.0% | 0.0% | 0.0% | 1.00 |
| 0.0 | Majority Vote | 100.0% | 0.0% | 0.0% | 3.00 |
| 0.0 | Purify | 100.0% | 0.0% | 0.0% | 2.00 |
| 0.1 | Single Shot | 100.0% | 0.0% | 0.0% | 1.00 |
| 0.1 | Majority Vote | 100.0% | 0.0% | 0.0% | 3.00 |
| 0.1 | Purify | 100.0% | 0.0% | 2.5% | 2.05 |
| 0.2 | Single Shot | 92.5% | 7.5% | 7.5% | 1.00 |
| 0.2 | Majority Vote | 100.0% | 0.0% | 0.0% | 3.00 |
| 0.2 | Purify | 100.0% | 0.0% | 7.5% | 2.30 |
| 0.3 | Single Shot | 82.5% | 17.5% | 17.5% | 1.00 |
| 0.3 | Majority Vote | 95.0% | 5.0% | 5.0% | 3.00 |
| 0.3 | Purify | **97.5%** | **2.5%** | 10.0% | **2.40** |

At the highest tested noise level, Purify improves safe success by 15
percentage points over Single Shot and 2.5 points over Majority Vote, while
using 20% fewer observations than Majority Vote. The trade-off is additional
travel for active reinspection and a higher conservative-detour rate in clear
scenarios.

## Files

- `runs.csv` — one row per episode
- `aggregate.csv` — 12 policy/noise groups
- `policy-comparison.png` — safety and observation-cost chart
- `trajectory-clear.png` — confirmed-clear direct route
- `trajectory-blocked.png` — confirmed-blocked detour
- `trajectory-conflict.png` — conflict-driven second viewpoint
- `raw-sha256.txt` — checksums for all 480 raw JSON records

The raw JSON directory is retained on the Mac working backup because it is much
larger than the summary artifacts. Each raw record includes evidence, belief
lifecycle, action decisions, state transitions, full trajectory, environment,
and metrics. `raw-sha256.txt` verifies that backup without committing the full
raw directory to the normal Git history.

## Reproduce

```bash
/opt/venv/bin/python scripts/run_experiments.py \
  --output-dir outputs/experiment-formal \
  --seed-count 20 \
  --workers 4 \
  --python /opt/venv/bin/python

python scripts/summarize_experiments.py \
  --runs outputs/experiment-formal/runs.csv \
  --output outputs/experiment-formal/aggregate.csv
```
