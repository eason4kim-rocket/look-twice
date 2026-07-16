# Analysis: repair-required r3

## Cell list

| profile | seed | world | intended contrast |
| --- | ---: | --- | --- |
| repair-required | 50000 | clear | active direct after real side_view; passive detour+wrong |
| repair-required | 50001 | blocked | naive unsafe; purify safe detour |
| repair-required | 50002 | clear | replicate clear contrast |

## Quoted episode metrics (raw JSON, unedited)

### purify-passive / 50000 (clear) — safe detour, wrong_detour

- `initial_gate_admitted=false`, `repair_attempted=false`
- `route_mode=detour`, `nav_success=true`, `mission_success=true`
- `wrong_detour=true`, `unsafe_crossing=false`
- path ≈ 5.92 m, steps 1187

### purify-active / 50000 (clear) — real side_view → direct

- `repair_attempted=true`, `repair_success=true`
- side_view: `left_near → left_far` actual_distance ≈ **0.906 m**, viewpoint_changed
- side_view: `left_far → right_near` actual_distance ≈ **2.635 m**, viewpoint_changed
- `route_mode=direct`, `wrong_detour=false`, mission complete
- path ≈ 8.94 m, steps 1500 (longer because of repair travel)

### naive / 50001 (blocked) — unsafe

- `unsafe_crossing=true`, `mission_success=false`

## Active ≫ passive (honest)

| metric (clear) | passive | active | better for active? |
| --- | ---: | ---: | --- |
| wrong_detour | 2/2 | 0/2 | **yes** |
| route_mode direct | 0/2 | 2/2 | **yes** |
| repair_success | 0 | 2 | **yes** |
| real side_view count | 0 | 4 | **yes** |
| mean path | 5.92 | 8.94 | no (repair cost) |
| mean steps | 1187 | 1500 | no (repair cost) |

The contest-relevant claim is **evidence repair enables gated direct clearance
without wrong detour**, not that active is always shorter.

## r2 vs r3

| issue | r2 | r3 |
| --- | --- | --- |
| detour → nav | false (mission 0 for passive) | true |
| side_view distance | 0.0 m revisit labeled side_view | ≥0.90 m real moves |
| active clear route | often detour after broken repair | direct after repair_success |

## No paired 90

This package does not run or archive a 90-episode matrix.
