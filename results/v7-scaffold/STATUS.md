# v7 status (code branch pointer)

Full GPU artifacts live on the evaluation host under  
`/workspace/look-twice-v6/outputs/v7/` (not mirrored here).

## Completed on AMD Genesis
- Unit tests: `tests/test_v7_vision_gate.py` + v6 core
- formal-genesis-3x6x20: 360 jobs, fail=0, workers 16–24
- torch-genesis-3x3x10: 90 jobs, fail=0, torch_corridor_head
- vision-head/best.pt trained on cuda:0
- Gated policies unsafe=0; genesis_rgb vision_source confirmed

See branch code: `docs/V7_DESIGN.md`, `src/v7_*.py`, `src/look_twice_v7.py`.
