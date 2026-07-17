# Look Twice v7 — Vision-Grounded Evidence Contracts

**Branch intent:** `v7-vision-evidence-contracts`  
**Status:** Implementation design (supersedes sketch for engineering)  
**Depends on:** v6 multi-agent Purify path (geometry RGB-D claims, scout repair)

## 1. One-liner

A vision model **proposes** structured corridor claims from RGB(-D); **Purify still authorizes** corridor cross via lineage, age, scope, multi-root clear support, and **geometry ↔ vision modality conflict**. Models cannot bypass the gate.

## 2. Motivation (Track 3 / award)

v6 proved multi-robot active evidence repair with geometry/depth claims on AMD Genesis. The weakest honesty point was “semantic” quality of evidence. v7 upgrades the **evidence source** without abandoning fail-closed contracts — the narrative judges can repeat:

> Scout sees; the model proposes; Purify decides.

## 3. Non-goals

- End-to-end VLA driving the carrier
- Real-robot Gate B product claim
- Shrinking v6 formal matrices to “finish” v7
- Vision mAP SOTA claims
- Arm as the hero (optional gated place is P2 only)

## 4. Architecture

```
capture RGB-D
  ├─ geometry/depth claims (v5→v2 path, unchanged)
  └─ vision proposer → modality=vision_semantic_v7 Claim v2
           │
           ▼
    claim pool + echo collapse
           │
           ▼
  evaluate_corridor_contract_v7
    = v6 rules
    + modality_conflict (geometry clear vs vision blocked, etc.)
    + optional require_vision_clear_root
           │
           ▼
  admit → gated direct | deny → safe detour
```

## 5. Vision proposer

**Module:** `src/v7_vision_claims.py`

| Backend | When | Notes |
| --- | --- | --- |
| `heuristic_rgb_proxy` | CI / default | Deterministic ROI features; labeled proxy, not a fake VLM |
| `torch_corridor_head` | GPU optional | Tiny CNN/MLP on downscaled RGB; ROCm `cuda:0` |

Output fields: `value ∈ {clear,blocked,inconclusive}`, `confidence`, `quality`, `visibility`, `model_id`, `input_sha256`.

**Calibration:** use shared bundle id `look-twice-rgbd-multi-agent-v7/1` for both geometry and vision claims so v6 exact-calibration filter does not false-deny; distinguish sources via **modality** and **model_id**.

## 6. Contract v7

**Module:** `src/v7_contracts.py`

Wraps `evaluate_corridor_contract` after adding modality-conflict gaps:

- Among **usable** claims, if geometry-class modalities support `clear` roots and vision supports `blocked` (or reverse) → `modality_conflict` deny.
- If `require_vision_clear_root=True` and no vision `clear` capture root → `missing_vision_root` deny.

Geometry-class modalities: `depth_geometry`, `simulated_semantic_sensor`, `learned_rgbd_semantic`.  
Vision-class: `vision_semantic_v7`.

## 7. Policies

| Policy | Behavior |
| --- | --- |
| `naive` | No gate (v6 semantics) |
| `purify-passive` | Gate, no active repair |
| `purify-active` | Gate + repair (geometry+vision claims if enabled) |
| `purify-active-vision` | Active + `require_vision_clear_root` |

## 8. Episode schema

- `look-twice.episode/v7`
- Metrics inherit v6 fields; add `vision_claim_count`, `vision_backend`, `modality_conflict_events`

## 9. Evaluation

- Unit tests: conflict deny, dual-clear admit, proxy determinism
- Synthetic closed-loop smoke
- Optional GPU smoke 3×3×5 (does not replace v6 mega-matrices)

## 10. Optional P2 — gated place

After goal reach **and** last corridor admit, emit `gated_place_receipt` placeholder. Not required for v7 gate story.

## 11. AMD ROCm note

Vision torch backend loads on `cuda:0` under ROCm PyTorch. Prefer process-isolated episodes consistent with v6 Genesis practice.

## 12. Success criteria

- Gated policies: unsafe=0 on unit + smoke
- Reproducible **modality_conflict → deny** fixture
- v6 unit tests remain green
- Honest docs: proxy vs torch backends
