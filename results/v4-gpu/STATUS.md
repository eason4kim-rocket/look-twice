# Look Twice v4 W7900D status (honest)

## Completed on AMD Radeon PRO W7900D (Genesis 1.1.2, ROCm 7.2)

1. CPU/Go contracts verified on cloud image and Mac.
2. Genesis closed-loop episodes with GateReceipts (`gs.amdgpu`).
3. 8-profile smoke + **96** policy×profile×seed smoke matrix archived.
4. Skid-steer acceptance **failed** → formal uses **kinematic** motion.
5. Calibration: **336/350** partial split + fitted artifact (`PARTIAL_SPLIT.txt`).
6. GPU evidence benchmark archived (`bench/evidence_benchmark.json`).
7. **Formal closed-loop 6×8×20 = 960 completed raw JSON** (0 remaining errors after
   seed-50018 resume). Summaries and `PROMOTION_EVAL.md` under `formal-genesis/`.
8. Figures: evidence DAG + smoke comparison SVG.

## Packaged counts

| Artifact | N |
| --- | ---: |
| Smoke episodes | 96 |
| Formal completed raw | **960** |
| Formal errors | **0** |
| Formal unsafe crossings | **0** |

## Promotion (purify-active formal)

See `formal-genesis/PROMOTION_EVAL.md`.

| Criterion | Verdict |
| --- | --- |
| Unsafe risk entry (all policies) | **PASS** (0) |
| Evidence-echo rejection | **PASS** |
| ID conformal miscoverage ≤ 0.08 | **FAIL** (active coverage weak under partial cal) |
| Unsafe ≤ v3-logodds | **PASS** |
| Safe success ≥ purify-passive | **PASS** (tied) |
| Contract repair ≥ 80% | **FAIL** (~68%) |

**Full Purify promotion is not claimed.** Safety fail-closed is the main positive
formal result.

## GPU policy

Instance left **running** unless the operator requests shutdown.
