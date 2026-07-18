# V7 GPU archive STATUS (honest)

Local mirror of remote `/workspace/look-twice-v6/outputs/v7/`  
Pulled: ~121 MB, 1013 files → `results/v7-gpu-archive/`

## Grade

| Item | Status |
| --- | --- |
| Code on branch `v7-vision-evidence-contracts` | done |
| AMD Genesis matrices (smoke / formal / torch) | done, fail=0 |
| Vision from real RGB (`genesis_rgb`) | done |
| Purify gated unsafe=0 | done |
| Formal archive on laptop | **done (this tree)** |
| Active > Passive (repair→direct) | **not achieved** |
| Torch head task-valid | **not achieved** (domain shift → all blocked) |
| Contest “upgrade over V6” | **not yet** |

## Formal 3×6×20 (heuristic vision) — regenerated summary

`n_episodes=360` (summarizer no longer counts `LAUNCH.json`)

| policy | n | mission | unsafe | direct | detour | repair_success | modality_conflict_events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 120 | 50 | 36 | 50 | 0 | 0 | 5 |
| purify-passive | 120 | 120 | 0 | 0 | 120 | 0 | 5 |
| purify-active-vision | 120 | 120 | 0 | 0 | 120 | 0 | 159 |

## Torch 3×3×10

Train: `vision-head/train_summary.json` acc=1.0 on **synthetic** labels.  
Eval: vision proposals almost always `blocked` on Genesis RGB → detour only.

See [DIAGNOSIS.md](DIAGNOSIS.md).

## Claimable sentence

> Models propose claims from Genesis RGB; Purify decides whether the robot may act. Naive can go unsafe; Purify keeps unsafe=0. Active vision does not yet recover direct routes after deny.

## Next (capability, not more scale)

1. Train vision on Genesis-like crops / match dark_frac distribution  
2. Closed-loop: conflict → side view → clear vision root → direct  
3. Paired Passive vs Active metrics (wrong detour, repair rate, observation cost)
