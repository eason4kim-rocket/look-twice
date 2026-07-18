# V7 repair capability (deny → observe → direct)

## Claim (now proven on closed-loop entry)

> Active vision can turn an initial gate **deny** into **repair_success + route=direct** with **unsafe=0**, while passive on the same seeds stays detour-only.

Models still only **propose** claims; Purify still **authorizes**.

## Locked case (real entry `look_twice_v7.py`)

- profile=`independent-noise` seed=`95000`
- policy=`purify-active-vision`
- Initial gate reasons include `missing_vision_root` / `insufficient_roots`
- After scout side views: `repair_success=true`, `route_mode=direct`, `unsafe_crossing=false`
- Artifact: `active-vision__independent-noise__95000.json`

## Paired passive vs active (synthetic, 3×10 seeds)

| policy | n | mission | unsafe | repair_success | direct | detour |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| purify-passive | 30 | 30 | **0** | **0** | **0** | 30 |
| purify-active-vision | 30 | 30 | **0** | **25** | **25** | 5 |

Vision label hist (non-degenerate): clear=87, inconclusive=34 (dominant≈72% < 95%).

## What changed (capability, not matrix scale)

1. Viewpoint-staged synthetic vision cues: initial weak → side_view clear  
2. Heuristic prefers free-space depth; darkness alone ≠ blocked  
3. Repair ranking boosts side_view on `missing_vision_root` / `modality_conflict`  
4. Domain-randomized dark clear/blocked synthetic RGB for train/eval alignment  

## Still honest limits

- Primary proof path is **synthetic closed-loop** through the real v7 entry (Genesis still supported; warehouse RGB domain remains harder).
- Not a foundation VLM.
- Fail-closed conflict unit tests remain green.

See also `results/v7-gpu-archive/DIAGNOSIS.md` for the prior “always detour” baseline.
