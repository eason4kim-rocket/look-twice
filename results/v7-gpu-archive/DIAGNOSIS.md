# V7 diagnosis (post formal/torch matrices)

## Accurate status

Engineering + AMD matrices complete; Purify safety holds.  
**Not** yet a capability upgrade over V6 for “active fixes deny → direct”.

## What works

- Vision claims from Genesis RGB (`vision_source=genesis_rgb`)
- Purify remains authorizer; gated policies `unsafe=0` on formal 360
- Naive remains unsafe as control
- Fail-closed on geometry↔vision conflict is observable (active-vision high conflict counts)

## Capability gap

| Policy | direct | detour | repair_success |
| --- | ---: | ---: | ---: |
| purify-passive | 0 | 120 | 0 |
| purify-active-vision | 0 | 120 | 0 |

Active-vision == passive on task outcome: more observations/claims, no recovered direct.

## Torch head: why all blocked

Training:

- Synthetic RGB labels only (`synthetic_rgb_for_label`)
- `final_acc=1.0` on that distribution

Deployment:

- Real Genesis frames: formal active-vision audits show **mean_luma median ≈ 0.21**, **dark_frac median ≈ 0.80**
- Torch on formal/torch matrices: **vision value blocked almost always** (torch matrix audits: blocked=180)
- Same head on synthetic clear/blocked: perfect class separation

Conclusion: **domain shift** (train on cartoon synthetic RGB, eval on dark Genesis renders), not “Purify broken”. High train acc is not task value.

## Heuristic on real RGB

Formal active-vision proposal values (audits): mostly **inconclusive** + **blocked**, rare **clear** (7).  
With `require_vision_clear_root` and modality conflict, gate stays denied → detour.

## Summarizer bug (fixed)

`by_policy_summary` counted non-episode JSON (`LAUNCH.json`) → `n_episodes=361` and policy `"?"`.  
Fix: require `schema_version` contains `episode/` and `metrics` dict. Regenerated summaries: **n_episodes=360**.

## Next capability work (not more matrix scale)

1. Train vision on Genesis crops (or domain-randomize synthetic to match mean_luma/dark_frac)
2. Soften / stage `require_vision_clear_root` so clear-geometry can admit when vision is inconclusive (product decision)
3. Closed-loop target: conflict → side_view → independent clear vision root → **direct**
4. Paired Passive vs Active: wrong_detour / repair_success / observation cost

## Update: repair→direct proven (synthetic closed-loop entry)

After viewpoint-staged vision cues + depth-preferring heuristic + repair ranking:

- `look_twice_v7.py` seed 95000: deny → repair_success + direct, unsafe=0
- Paired 30 seeds: active repair_success=25/direct=25 vs passive 0/0, both unsafe=0
- Vision hist non-degenerate (clear+inconclusive)

Artifacts: `results/v7-repair-capability/`
