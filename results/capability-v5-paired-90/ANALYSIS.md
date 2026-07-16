# Analysis — paired capability 90

## Setup

3×6×5 on W7900D, `genesis_rgbd_depth_semantic`, smoke cal, post-r3 semantics.

## Main result

Purify (active and passive) is **safer** than naive (unsafe 0 vs 10).
Active and passive share **mission 27/30**. Differentiation is **not** mission count.

Differentiation that matches the formal claim:

1. **Fewer wrong detours** (4 vs 9)
2. **More direct gated crosses** (14 vs 9)
3. **Repair success only on active** (5), with **31 real side-views**
4. **Higher path and steps** — active pays observation cost

## repair-required slice (N=5, strongest active value)

| seed | world | naive | passive | active |
| ---: | --- | --- | --- | --- |
| 50000 | clear | direct mission | detour **wrong** | **direct + repair** |
| 50001 | blocked | unsafe | safe detour | safe detour (+3 side views) |
| 50002 | clear | direct mission | detour **wrong** | **direct + repair** |
| 50003 | blocked | unsafe | safe detour | safe detour |
| 50004 | clear | direct mission | detour **wrong** | **direct + repair** |

Active path on clear repair-required ≈ 8.94 m vs passive detour ≈ 5.92 m — **longer**, not shorter.

## Caveats

- Smoke calibration; not Gate B.
- Mission parity active=passive overall; claim must stay on routing quality + repair, not mission rate alone.
- On `dynamic-change`, active does not beat passive on wrong_detour (both 3) — flip dynamics dominate.
