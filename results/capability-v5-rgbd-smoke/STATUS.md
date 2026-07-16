# v5 Genesis RGB-D Claims smoke (W7900D)

## Provenance

- **Executable source commit:** `6e36020` (`Wire Genesis RGB-D claims into v5`)
- The cloud snapshot had no `.git` directory. Its stale `.git_commit` marker was
  `d7ab2f7`, so raw episode JSON preserves that value and must not be interpreted
  as the executable source revision.
- Before committing, SHA256 hashes of the six changed runtime/test files on the
  W7900D instance were compared with the local files and matched byte-for-byte.
- Raw episode JSON is preserved unchanged; this note records the corrected
  provenance rather than rewriting experimental output.

## Claims path

Navigation Action Gate evidence is produced via Genesis camera RGB-D + entity
segmentation → v4 `process_evidence_frame` (corruption + depth/semantic Claims).

- **claims_mode:** `genesis_rgbd_depth_semantic` on all 24 smoke episodes
- **not** `synthetic_modality_proxies_on_gpu_motion` for this path
- CPU CI synthetic path remains available (`claims_mode=synthetic_modality_proxies`)

## Smoke matrix

3 policies × 4 profiles × 2 seeds (50000–50001) = **24**, workers=2, **24/24 OK**.

| policy | N | mission | nav | pick | unsafe |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 8 | 5 | 5 | 7 | **3** |
| purify-passive | 8 | 7 | 8 | 7 | **0** |
| purify-active | 8 | 7 | 8 | 7 | **0** |

Mission definition: **nav ∧ pick ∧ ¬unsafe** (no pick-only).
Invariant check: mission without nav = **0**.

## Differentiation (honest)

- Purify active/passive **fail-closed** (unsafe 0); naive shows **unsafe=3** on blocked seeds.
- Mission: purify 7/8 > naive 5/8 on this cut.
- **Active does not beat passive on this mix** (both 7/8 mission, 0 unsafe). Expanding
  this profile mix to 90 would mainly re-prove “Gate works,” not “active evidence
  repair has value.”
- Not a Full Purify promotion claim; small N; smoke cal allowed.

## Follow-on: repair-required mini-eval

Strategy differentiation is demonstrated on a separate forced set:

→ [`results/capability-v5-repair-required/STATUS.md`](../capability-v5-repair-required/STATUS.md)

There: clear worlds give passive mission=0 vs active mission=2 with `repair_success`,
all on `genesis_rgbd_depth_semantic` / W7900D. Paired 90 still **not** auto-started.

## Go/no-go for paired 90

- **On this 24-smoke mix alone:** do **not** spend 90 proving gate-only safety parity.
- **After repair-required mini-eval:** eligibility **GO** (`GO_for_paired_90=true` in
  that rollup). **90 still not run** here or there without an explicit decision.

## Contest Gate B

**No new contest Gate B pass.** Historical 90 remains provisional history only.

## Artifacts

- `single/` — single-episode RGB-D proof
- `matrix-3x4x2/` — 24 JSON + `rollup.json` + `parallel_summary.json`
