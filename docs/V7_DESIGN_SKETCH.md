# Look Twice v7 — Design Sketch (pre-planning, quality-preserving)

Status: **superseded for engineering by `docs/V7_DESIGN.md`** (kept as history).  
Depends on: v6 multi-agent path (mega-matrices may still be running in parallel).

## One-liner

Vision-Grounded Evidence Contracts: a vision model **proposes** corridor claims from RGB-D; Purify still **authorizes** via lineage / age / scope / conflict. Models cannot bypass the gate.

## Non-goals (keep v6 quality bar)

- No end-to-end VLA replacing Purify
- No dropping genesis formal matrices or shrinking seeds for a fake win
- No claiming real-robot Gate B
- Arm (if any) is optional gated place after admit — not the hero

## Minimal slice (award-oriented)

1. Lightweight vision head OR open VLM constrained JSON:
   - output: `{clear|blocked|uncertain, confidence}`
2. Map to Claim v2 with `model_id`, `artifact_sha256`, capture root
3. Contract extras:
   - require ≥1 vision clear root **and** existing multi-root geometry discipline where applicable
   - **vision vs geometry conflict → deny** (demo killer feature)
4. Active repair: Scout prioritizes high visual uncertainty viewpoints
5. Eval: small paired matrix + one adversarial false-clear injection case

## Repo touchpoints (when implementing)

- `src/v7_vision_claims.py` — RGB → structured claim
- `src/v6_contracts.py` or v7 contract wrapper — conflict rules
- `src/v6_episode.py` / `look_twice_v7.py` — wire observe path
- `docs/V7_DESIGN.md` — full design after sketch review
- `tests/test_v7_vision_gate.py` — conflict deny unit tests

## Success metrics

- Purify unsafe remains 0 on gated policies
- At least one world where geometry alone would be weak and vision repair helps **or** conflict correctly blocks
- AMD ROCm path documented for vision inference

## Handoff trigger

When `outputs/v6/V6_COMPLETE_HANDOFF.json` exists on GPU:

1. Pull finals → `results/v6-final-capability/`
2. Update STATUS with matrix tables
3. Expand this sketch → `V7_DESIGN.md`
4. Implement minimal vision claim adapter + tests
5. Do **not** open contest PR unless user asks
