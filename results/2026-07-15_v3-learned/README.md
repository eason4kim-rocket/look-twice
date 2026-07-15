# Look Twice v3 Learned NBV

This directory records the optional Learned Next-Best-View experiment. The
model was trained and evaluated on the AMD Radeon PRO W7900D with PyTorch ROCm
on `cuda:0`.

## Data isolation

The dataset contains complete candidate-view probes from disjoint scene seeds:

| Split | Scenes | Seeds | Candidate rows | Decisions |
| --- | ---: | --- | ---: | ---: |
| Train | 200 | 0–199 | 2,787 | 763 |
| Validation | 50 | 10,000–10,049 | 734 | 199 |
| Test | 100 | 20,000–20,099 | 1,486 | 398 |

The label is the realized entropy reduction minus travel cost. Candidate
features exclude unknown obstacle truth, future observations and clean
segmentation. The three split decision IDs are disjoint. The combined dataset
SHA-256 is
`1f113e3383c92fe5e1551d6e42403e55a35ce81f9982485055a4fc0acd916370`.

## Offline test result

The shared MLP is `8 -> 64 -> 32 -> 1` and was trained for 200 epochs.

| Metric | Result |
| --- | ---: |
| Validation MSE | 0.02304 |
| Test MSE | 0.02398 |
| Test top-1 accuracy | 73.87% |
| Heuristic oracle regret | 0.06687 |
| Learned oracle regret | **0.04211** |

The configured promotion gate passed because Learned NBV reduced oracle regret
on the isolated test split.

## Online closed-loop result

The promoted model then ran 100 fresh closed-loop episodes:

```text
1 learned policy × 5 profiles × 20 paired test seeds = 100 episodes
```

All episodes completed on the W7900D, used schema v3, and reported:

- 100% safe success;
- 0 unsafe crossings;
- 0 unresolved Action Gate entries;
- 3.98 observations and 10.43 path units on average.

The comparison remains intentionally honest. Heuristic Information-Gain NBV
also achieved 100% safe success, with a shorter mean path (10.24) and higher
information gain per metre (0.373 versus 0.344). Learned NBV therefore passes
the predefined safety/regret gate, but it is not claimed to dominate the
heuristic in every online efficiency metric.

## Files

- `train.jsonl`, `validation.jsonl`, `test.jsonl` — reproducible candidate rows;
- `nbv-model.pt` — PyTorch state dict plus feature schema;
- `nbv-metrics.json` — isolated validation/test metrics;
- `runs.csv`, `aggregate.csv` — 100-episode online evaluation;
- `representative/` — one traceable dynamic episode;
- `DATASET_SHA256SUMS` — hashes of model, metrics and JSONL data;
- `EVALUATION_SHA256SUMS` — hashes of all 100 raw episodes backed up locally.

The full oracle-probe episodes and all 100 raw evaluation JSON files remain in
the ignored local `outputs/` tree. Their hashes were verified after transfer
from the cloud.

## Reproduce training and evaluation

```bash
/opt/venv/bin/python scripts/train_nbv.py \
  --train results/2026-07-15_v3-learned/train.jsonl \
  --validation results/2026-07-15_v3-learned/validation.jsonl \
  --test results/2026-07-15_v3-learned/test.jsonl \
  --model-output outputs/nbv-model.pt \
  --metrics-output outputs/nbv-metrics.json \
  --device cuda:0 \
  --epochs 200

/opt/venv/bin/python scripts/run_v3_experiments.py \
  --output-dir outputs/v3-learned-eval \
  --policies purify-learned \
  --learned-model outputs/nbv-model.pt \
  --seed-count 20 \
  --seed-offset 20000 \
  --python /opt/venv/bin/python
```
