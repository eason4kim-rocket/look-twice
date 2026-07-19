# V8 Scaffold STATUS

**Started:** 2026-07-19  
**Role:** Independent Challenger — V7 remains frozen submission baseline  
**Scaffold commits:** `bdd93a0` (scaffold), `9f48acb` (ROCm feasibility fix)

## Day 1 checklist

- [x] V7 freeze pointer (`docs/V7_BASELINE_FREEZE.md`)
- [x] V8 design lock (`docs/V8_DESIGN.md`)
- [x] `SpatialRGBDModel` DeepLabV3-R50 multi-task skeleton
- [x] ROCm feasibility script
- [x] 50-world preflight collector (seeds 100000–100049)
- [x] Unit tests (CPU)
- [x] ROCm feasibility report (`results/v8-scaffold/feasibility_report.json`)
- [ ] 50-world preflight complete (GPU job running: `logs/v8-preflight50.pid`)

### ROCm feasibility notes

| Metric | Value |
|--------|------:|
| backend | deeplabv3_resnet50 |
| params | ~39.8M |
| train bs=8 | ~1.5 img/s |
| eval bs=1 p95 | ~195 ms |
| p95 &lt; 50 ms goal | **not yet** (smaller input / AMP export later) |

DeepLab forward+backward works on ROCm 7.2 / Torch 2.9. Train uses bs≥2 (ASPP BN).

## Non-negotiables

- Do not re-open V7 locked test
- Do not lower safety thresholds
- V8 locked seeds only `102100–102499`, once, after freeze
- DINOv2 optional; must not block DeepLab mainline

## Promotion

Only if offline + online gates in `docs/V8_DESIGN.md` all pass → V8 becomes primary; else V7 ships and V8 is appendix.
