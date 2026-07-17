# v7 scaffold STATUS

Branch: `v7-vision-evidence-contracts`

## Done
- Full design: `docs/V7_DESIGN.md`
- Vision proposer: `src/v7_vision_claims.py` (heuristic proxy + torch head scaffold)
- Contract v7: `src/v7_contracts.py` (modality_conflict, missing_vision_root)
- Episode hooks in `v6_episode.py` (vision_enabled / use_v7_contract; default off for v6 matrices)
- CLI: `src/look_twice_v7.py`
- Tests: `tests/test_v7_vision_gate.py` (5) + v6 regression (20) green

## Narrative
Vision **proposes** claims (`vision_semantic_v7`); Purify **authorizes**; geometry↔vision conflict fail-closes.

## Next
- GPU Genesis RGB → vision claim (pixels from capture_raw)
- Optional train torch head
- Small v7 smoke matrix when GPU free
- Demo beats with modality_conflict
