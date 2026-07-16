# Formal matrix promotion snapshot (honest)

Source: `results/v4-gpu/formal-genesis/summary/aggregate.csv`
Raw completed JSON: **956**. Error JSON: **4**. Design size: 960.

Calibration used for these episodes is the **partial** ID split artifact
(`results/v4-gpu/calibration/PARTIAL_SPLIT.txt`). Coverage claims are limited
to that simulated ID population; OOD rows carry no coverage claim.

## Per-policy rollup (completed episodes only)

| policy | N | unsafe | safe_success | wrong_detour | repair ok/att | echo ok/att | ID conf cov |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| conformal-only | 160 | 0 | 64 | 80 | n/a | n/a | 116/120 (0.967; misc=0.033) |
| lineage-only | 160 | 0 | 64 | 80 | n/a | n/a | 117/120 (0.975; misc=0.025) |
| naive-majority | 156 | 0 | 60 | 76 | n/a | n/a | n/a |
| purify-active | 160 | 0 | 64 | 80 | 109/160 | 20/20 | 83/140 (0.593; misc=0.407) |
| purify-passive | 160 | 0 | 64 | 80 | n/a | 20/20 | 136/140 (0.971; misc=0.029) |
| v3-logodds | 160 | 0 | 64 | 80 | n/a | n/a | 117/120 (0.975; misc=0.025) |

## Gate checklist (Full Purify targets)

| Criterion | Target | Observed (purify-active unless noted) | Verdict |
| --- | --- | --- | --- |
| Unsafe risk-region entry (all policies) | 0 | total unsafe=0 over completed N=956 | PASS |
| Evidence-echo rejection | high / no root inflation | 20/20 | PASS |
| ID miscoverage ≤ 0.05+0.03=0.08 | ≤0.08 | miscoverage≈0.4071 (cov 83/140) | FAIL |
| Paired unsafe ≤ v3-logodds | active≤v3 | active=0.0000, v3=0.0000 | PASS |
| Safe success ≥ purify-passive | active≥passive | active=0.4000, passive=0.4000 | PASS |
| Contract repair success ≥ 80% | ≥0.80 | 0.6813 (109/160) | FAIL |

## Notes

- Matrix holes: 4 error JSON files (typically seed 50018 viewpoint contact);
  multi-try viewpoint fallback is in tree for resume.
- No rule retuning after reading these aggregates.
- Do not claim skid-steer physics; formal backend is kinematic.

