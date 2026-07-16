# Formal matrix promotion evaluation (honest)

Source: `results/v4-gpu/formal-genesis/summary/aggregate.csv`
Raw completed JSON: **960**. Error JSON: **0**. Design size: **960**.

Calibration: partial ID split artifact (`calibration/PARTIAL_SPLIT.txt`).
Backend: **kinematic** + `gs.amdgpu` on AMD Radeon PRO W7900D.

## Per-policy rollup

| policy | N | unsafe | safe_success | wrong_detour | repair | echo | ID conf cov |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| conformal-only | 160 | 0 | 64 | 80 | n/a | n/a | 116/120 (misc=0.033) |
| lineage-only | 160 | 0 | 64 | 80 | n/a | n/a | 117/120 (misc=0.025) |
| naive-majority | 160 | 0 | 64 | 80 | n/a | n/a | n/a |
| purify-active | 160 | 0 | 64 | 80 | 109/160 | 20/20 | 83/140 (misc=0.407) |
| purify-passive | 160 | 0 | 64 | 80 | n/a | 20/20 | 136/140 (misc=0.029) |
| v3-logodds | 160 | 0 | 64 | 80 | n/a | n/a | 117/120 (misc=0.025) |

## Gate checklist (Full Purify targets)

| Criterion | Target | Observed | Verdict |
| --- | --- | --- | --- |
| Unsafe risk-region entry (all policies) | 0 | 0 / 960 | PASS |
| Evidence-echo rejection (active) | high | 20/20 | PASS |
| ID miscoverage ≤ 0.08 | ≤0.08 | 0.4071 (83/140) | FAIL |
| Unsafe ≤ v3-logodds | active≤v3 | active=0.0000, v3=0.0000 | PASS |
| Safe success ≥ purify-passive | active≥passive | active=0.4000, passive=0.4000 | PASS |
| Contract repair ≥ 80% | ≥0.80 | 0.6813 (109/160) | FAIL |

## Notes

- Full 960 raw after resume of seed-50018 holes (multi-try viewpoints).
- Full Purify promotion is **not** claimed (repair and active conformal coverage fail targets).
- Safety fail-closed holds: zero unsafe crossings on completed formal set.
- No rule retuning after reading aggregates.
