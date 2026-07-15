# Look Twice v4 W7900D status (honest)

## Completed on AMD Radeon PRO W7900D (Genesis 1.1.2, ROCm 7.2)

1. CPU/Go contracts verified on cloud image and Mac.
2. Single-env Genesis closed-loop episodes with GateReceipts (`gs.amdgpu`).
3. 8-profile × seed `50000` Genesis smoke (purify-active) under `profile-smoke/`.
4. Skid-steer motion acceptance **failed** (14/40 viewpoint trials; SIGSEGV on
   multi-scene teardown). Formal path demoted to **`motion_backend=kinematic`**.
5. Formal calibration collection: **336/350** seeds retained after multi-viewpoint
   retry; partial split fitted with `--allow-nonstandard-split` and flagged in
   `calibration/PARTIAL_SPLIT.txt`. Artifact:
   `calibration/calibration_artifact.json`.
6. GPU evidence benchmark: `bench/evidence_benchmark.json` (batches 1/8/32/128,
   warmup 20 / timed 100, CPU vs ROCm separated).
7. **Genesis smoke matrix 6×8×2 = 96 completed** with fitted calibration;
   summaries under `smoke-genesis/summary/`; SHA256 in `SHA256SUMS`.
8. **Formal closed-loop 6×8×20 = 960 in progress** on the live instance
   (`/workspace/look-twice/outputs/v4-formal-genesis`). Mac/GitHub package holds
   the current incomplete subset under `formal-genesis/` (see counts below).
9. Figures: evidence DAG + smoke comparison SVG under `figures/`.

## Packaged counts (this repository snapshot)

| Artifact | N / note |
| --- | --- |
| Smoke completed episodes | **96** (0 runner failures) |
| Formal completed raw JSON | **40** (plus **2** error JSON; incomplete vs 960) |
| Formal design size | **960** |
| Unsafe crossings (smoke 96) | **0** |
| Unsafe crossings (packaged formal subset) | **0** (N incomplete) |

## Not claimed

- Full **960** formal completion until the cloud matrix finishes and is re-synced.
- Skid-steer formal physics validation (explicitly demoted).
- Full promotion-threshold certification on locked test N=960 (smoke N and
  partial formal N are too small for CI/promotion claims).
- Complete calibration split of exactly 350 rows (partial, documented).

## GPU policy

Instance left **running** for formal matrix continuation (operator objective:
do not shut down at this packaging step).
