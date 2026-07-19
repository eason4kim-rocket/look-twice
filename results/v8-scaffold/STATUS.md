# V8 Scaffold STATUS

**Started:** 2026-07-19  
**Role:** Independent Challenger — V7 remains frozen submission baseline  
**Branch tip at scaffold:** `87e54be` (+ V8 commits)

## Day 1 checklist

- [x] V7 freeze pointer (`docs/V7_BASELINE_FREEZE.md`)
- [x] V8 design lock (`docs/V8_DESIGN.md`)
- [x] `SpatialRGBDModel` DeepLabV3-R50 dual-stream skeleton
- [x] ROCm feasibility script
- [x] 50-world preflight collector (seeds 100000–100049)
- [x] Unit tests (CPU)
- [ ] ROCm feasibility report on W7900D
- [ ] 50-world preflight complete + summary

## Non-negotiables

- Do not re-open V7 locked test
- Do not lower safety thresholds
- V8 locked seeds only `102100–102499`, once, after freeze
- DINOv2 optional; must not block DeepLab mainline

## Promotion

Only if offline + online gates in `docs/V8_DESIGN.md` all pass → V8 becomes primary; else V7 ships and V8 is appendix.
