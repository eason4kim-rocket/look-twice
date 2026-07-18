# V7 Genesis RGB Vision Calibration (phase lock)

**Status:** world homology closed (`f315a02` / STATUS homology 120).  
**This phase only:** train + calibrate non-degenerate visual Claims on **homology-aligned** Genesis RGB.

Do **not**:

- rewrite motion / obstacle placement
- relax blocked-claim gate thresholds
- use `synthetic_rgb_for_label()` for formal vision training

## Why

Homology 120 matrix:

| Metric | Result |
| --- | ---: |
| World alignment | 120/120 |
| Gate repair | 57/60 |
| Full chain→direct | 32/60 (53%) |
| Vision labels | ~all `clear` |

Purify + active scout + physics are online. Remaining misses are **false-clear** admits of oracle-blocked corridors.

## Dataset (world-seed isolated splits)

| Split | Seeds | Worlds | Images (≈10/world) |
| --- | --- | ---: | ---: |
| train | 96000–96999 | 1000 | 10_000 |
| validation | 97000–97199 | 200 | 2_000 |
| calibration | 97200–97499 | 300 | 3_000 |
| locked test | 98000–98299 | 300 | 3_000 |

Per world (profile fixed to `independent-noise` for collection baseline; optional multi-profile later):

```text
2 corridors × (carrier front + 4 scout side views) = 10 RGB samples
```

Offline labels **only** from:

```text
oracle corridor_a/b_blocked_initial → clear | blocked
```

Forbidden online features: oracle flags, obstacle pose, clean segmentation, seed-derived features.

Keep only samples with `world_alignment_passed=true`.

## Model

```text
RGB ROI 96×96
→ Conv32 → Conv64 → Conv128 → GAP → Linear64 → blocked logit (or 3-way)
```

Train on ROCm `cuda:0`. Early stop on validation **balanced accuracy**.  
Save `best.pt`, curves, dataset manifest SHA256.

## Conformal calibration (calibration split only)

Runtime prediction sets:

```text
{clear} | {blocked} | {clear, blocked}→inconclusive
```

Gates:

- Balanced accuracy ≥ 85%
- Blocked recall ≥ 90%
- False-clear rate ≤ 5%
- Conformal coverage ≥ 95%
- ≥20% clear and ≥20% blocked outputs on locked test
- Locked test **not** used for tuning

## Active corridor switch (policy, not gate rewrite)

```text
A confirmed blocked → observe B side views → Gate B → direct B
max 2 corridors × 2 side obs; else safe detour
```

## Smoke then 120

1. 2×3×4 = 24 ep capability smoke (full chain ≥9/12 Active)
2. Same 120 structure as homology; upgrade needs full chain ≥42/60 + false-clear admit ≤3/60
3. Only then set `formal_result_eligible=true` with calibration artifact

## Scripts

| Script | Role |
| --- | --- |
| `scripts/v7_collect_genesis_vision_dataset.py` | Homology RGB collection |
| `scripts/v7_train_genesis_vision_head.py` | Real-RGB torch head |
| `scripts/v7_calibrate_vision_conformal.py` | Class-conditional conformal |
| `scripts/v7_paired_passive_active.py` | Capability matrices (unchanged entry) |
