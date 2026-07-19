# Look Twice V8 — Spatially Grounded RGB-D Evidence Model

**Role:** Independent Challenger. Does **not** overwrite frozen V7.  
**Decision window:** 5 days (promote by 2026-07-24/25 or keep V7 as primary).  
**Parent baseline:** [V7_BASELINE_FREEZE.md](V7_BASELINE_FREEZE.md)

## Problem statement

V7 residual failures are not primarily “too few parameters.” They are:

> The model does not fully condition on **which corridor is under judgment**, so the other lane’s obstacle contaminates the claim.

V8 must answer:

> From this viewpoint, does **specified corridor C** have enough reliable evidence to support traverse?

Not:

> Is there an obstacle somewhere in the image?

## Architecture

```text
RGB ────────────── RGB Encoder ─────┐
Depth ─────────── Depth Encoder ────┤
Corridor Mask ── Spatial Encoder ───┼→ Fusion → multi-task heads
Pose/Viewpoint ─ Geometry MLP ──────┘
        ↓
obstacle segmentation | p_blocked | visibility | quality | uncertainty
        ↓
spatial_rgbd_claim → Purify (root/TTL/conformal/conflict) → direct/scout/detour
```

### Primary backbone (Day 1–4 mainline)

- **DeepLabV3 + ResNet50** (torchvision) RGB stream
- Lightweight depth conv encoder (1→32→64→128)
- Corridor mask as extra channel(s) fused early or mid
- Geometry MLP: camera xyz, yaw, corridor id one-hot, range-to-entry
- Heads:
  - Obstacle segmentation (1 channel logit)
  - Traversability logit → sigmoid `p_blocked`
  - Visibility / quality scalars
  - Uncertainty scalar (optional ensemble later)

### Optional high-difficulty Challenger

- DINOv2 ViT-S/14 only if ROCm 1h feasibility passes
- Freeze most backbone; train last blocks + heads
- Must not block DeepLabV3 mainline

## Genesis honesty boundary

| Source | Use |
|--------|-----|
| Genesis RGB | Runtime + train input |
| Genesis depth (+ noise) | Runtime + train input |
| Clean entity segmentation | **Train labels / offline eval only** |
| Clean depth | Label / audit only |
| Oracle obstacle flags | Offline labels only |
| Purify / NBV | **Never** reads oracle or clean seg |

RGB+Depth from one capture = **one** measurement root (no fake independence).

## Seed isolation (V8 only)

```text
Train       100000–101499   1500 worlds
Validation  101500–101799    300 worlds
Calibration 101800–102099    300 worlds
Locked V8   102100–102499    400 worlds   # open once after freeze
OOD Test    102500–102699    200 worlds
```

**Forbidden:** any V7 train/val/cal/locked/smoke/matrix seeds (96000–98300, 95000–95019, 99000–99003, 99200–99203, 99300–99319).

## Sample payload (schema `look-twice.v8-spatial-rgbd/v1`)

Per viewpoint × target corridor:

- `rgb.npy`, `depth_noisy.npy`
- `depth_clean.npy` (label-only)
- `seg_entity.npy` (label-only; obstacle/background)
- `corridor_mask.npy` (target corridor projected occupancy in image)
- `meta.json`: pose, K/extrinsics, viewpoint, corridor_id, offline_label,
  obstacle specs, world seed, git_commit, sha256s, train_eligible

## Losses (fixed)

```text
total =
  0.40 × (Dice + BCE) segmentation
+ 0.30 × Focal BCE traversability
+ 0.15 × SmoothL1 visibility
+ 0.10 × depth-validity / quality
+ 0.05 × calibration regularizer
```

Then **split conformal** on calibration only → prediction sets  
`{clear} | {blocked} | {clear,blocked}→inconclusive`.

## Promotion gates (must all pass to replace V7)

### Offline (Locked V8 once)

- blocked recall ≥ 0.95  
- false-clear rate ≤ 0.01  
- conformal coverage ≥ 0.95  
- obstacle IoU ≥ 0.80  
- no silent fallback; SHA match  

### Online (fresh worlds, V7 vs V8 paired)

- unsafe = 0; alignment = 100%  
- V8 full-chain ≥ 48/60 **or** +8 vs same-seed V7  
- false-blocked detour ≤ V7 − 30%  
- no increase in false-clear admits  
- unresolved → safe detour  
- p95 single-frame inference &lt; 50 ms on W7900D  
- Purify Gate / TTL / root collapse semantics **unchanged**  

If not met: V7 remains submission; V8 appendix only.

## 5-day schedule

| Day | Deliverable |
|-----|-------------|
| 1 | Schema, 50-world preflight, ROCm DeepLab feasibility, this doc |
| 2 | Full collect + audit + manifest |
| 3 | DeepLab RGB-D multi-task train |
| 4 | Val + conformal + non-locked smoke; freeze artifacts |
| 5 | One locked V8 + V7/V8 paired closed-loop; promote or demote |

Then stop development → AMD benchmark, video, README, PR.

## Non-goals

- Do not re-open V7 locked test  
- Do not lower safety thresholds to promote V8  
- Do not give Purify oracle access  
- Do not treat DINOv2 as required for Day-5 decision  
