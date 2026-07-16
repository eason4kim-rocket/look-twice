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
8. **Formal closed-loop 6×8×20 design = 960 attempted**: **956 completed raw JSON**
   + **4 error JSON** (seed-50018 viewpoint contact class). Archived under
   `formal-genesis/`. Cloud pipeline ended `2026-07-16 00:33 UTC`.
9. Figures: evidence DAG + smoke comparison SVG under `figures/`.
10. Promotion snapshot: `formal-genesis/PROMOTION_SNAPSHOT.md` (honest PASS/FAIL).

## Packaged counts (this repository snapshot)

| Artifact | N / note |
| --- | --- |
| Smoke completed episodes | **96** (0 runner failures) |
| Formal completed raw JSON | **956** |
| Formal error JSON | **4** (holes vs design 960) |
| Formal design size | **960** |
| Unsafe crossings (smoke 96) | **0** |
| Unsafe crossings (formal completed) | **0** |

## Promotion snapshot (purify-active, formal completed)

| Criterion | Verdict (see PROMOTION_SNAPSHOT.md) |
| --- | --- |
| Unsafe risk entry (all policies) | **PASS** (0/956) |
| Evidence-echo rejection | **PASS** (20/20) |
| ID conformal miscoverage ≤ 0.08 | **FAIL** (~0.41 on active ID samples) |
| Unsafe ≤ v3-logodds | **PASS** (both 0) |
| Safe success ≥ purify-passive | **PASS** (both 0.40) |
| Contract repair ≥ 80% | **FAIL** (~0.68 = 109/160) |

No rule retuning after reading aggregates. Partial calibration applies.

## Not claimed

- Perfect 960/960 without holes (4 errors remain until resume succeeds).
- Skid-steer formal physics validation (explicitly demoted).
- Full promotion certification for conformal coverage / 80% repair on purify-active.
- Complete calibration split of exactly 350 rows (partial, documented).

## GPU policy

Instance left **running** unless the operator requests shutdown. Formal runner has
finished; idle GPU still incurs credit cost.
