# Runtime Integration Gate — PASSED (single Genesis sample)

**Date:** 2026-07-18  
**Episode:** `purify-active-vision` / `independent-noise` / seed `99000`  
**Host:** GPU `cuda:0` (AMD / ROCm)

## Required fields

| Check | Result |
|-------|--------|
| `checkpoint_loaded` | `true` |
| `fallback_used` | `false` |
| `tensor_device` / `device` | `cuda:0` |
| `vision_source` | `genesis_rgb` |
| `vision_backend` | `torch_corridor_head` |
| `prediction_set` | from conformal artifact (`['clear']` on both audits) |
| `checkpoint_sha256` | `385aa7b78197909e…bcc9` |
| `conformal_artifact_sha256` | `44f564633b6e2a30…7333` |
| `p_blocked` present | yes (0.000458, 0.051065) |
| `preprocessing_version` | `v7-genesis-roi-side-0.30-0.75-0.28-0.72-resize96-v1` |

## Episode outcome (smoke, not formal)

- mission success, unsafe=false
- initial_gate_denied → repair → direct (`repair_chain_complete=true`)
- world_alignment_passed=true

## Fail-closed

- CLI without `--vision-conformal-artifact` exits with clear error (no silent heuristic).

## Unit tests

- `tests/test_v7_runtime_integration.py` + `test_v7_vision_gate.py`: **19 passed**

## Next (not yet run)

Non-locked 24: 2 policies × 3 profiles × seeds 99000–99003.  
Do **not** open locked_test until 24 passes and runtime commit is frozen.
