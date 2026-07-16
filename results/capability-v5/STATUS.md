# Capability v5 matrix — provisional assessment

## Formal judgment (2026-07-16 audit)

> **v5 is a valuable capability prototype. Gate B is only a *provisional pass*,
> not a contest final claim.**

The archived 90-run matrix (`parallel` workers=2, W7900D) remains useful for
engineering history, but **must not** be cited as official contest Gate B without
the semantic fixes below.

## Critical issues found (pre-fix)

1. **Action Gate bypass** — after receipt invalidation, `grasp_approach` could
   still drive through the risk slab; `unsafe` was only scored on the segment
   labelled `cross_region`.
2. **TTL vs motion** — contract / claim TTL was 80 steps while dual-viewpoint
   travel often spent ~600 steps → receipt expired before the boundary →
   `nav_success = 0/90`.
3. **Pick-only mission** — `mission_success = pick ∧ ¬unsafe` credited success
   with zero navigation; all three policies reported ~50% for that reason.
4. **Reproducibility** — matrix JSON commit pin did not match uncommitted code.

Also: nav Claims remain **synthetic modality proxies** on the Genesis path
(`v5_genesis_runtime.py`), not true RGB-D Claims.

## Provisional 90-run numbers (historical, pre-semantic-fix)

| policy | N | mission (old def) | pick | nav | unsafe (old metric) |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 30 | 15 (50%) | 15 | 0 | 0* |
| purify-passive | 30 | 15 (50%) | 15 | 0 | 0* |
| purify-active | 30 | 15 (50%) | 15 | 0 | 0* |

\* unsafe metric incomplete (risk motion outside `cross_region` not scored).

## Semantic fix (landed in source — re-run required)

In `src/v5_episode.py`:

| Fix | Change |
| --- | --- |
| TTL | default **2000** steps; contracts `max_evidence_age` match |
| Risk gate | any risk-slab motion requires live admitted nav receipt (purify) |
| Unsafe | trajectory ∩ risk slab while truth blocked → `unsafe` |
| Invalidation | **active** re-observes at boundary; **passive** fail-closed; **naive** may push and expose risk |
| Mission | **`nav ∧ pick ∧ ¬unsafe`** (no pick-only credit) |
| Approach | grasp base staged just **outside** risk max_x so pick does not sneak through the slab |

Local synthetic smoke (independent-noise / seed 50000) after fix:

```text
naive / passive / active → mission=True nav=True pick=True unsafe=False
```

Dynamic regression (profile `dynamic-change`, seed `50000`) after the complete
live-receipt fix:

| policy | mission | nav | pick | unsafe | detour | invalidation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| naive | 0 | 0 | 1 | **1** | 0 | 0 |
| purify-active | **1** | **1** | **1** | **0** | 1 | 1 |

This is a **local synthetic regression**, not a W7900D contest result.  It
proves the intended semantics: a new boundary Claim revokes the old plan,
invalidated/expired receipts are no longer considered live, and the active
policy can complete a physical safe fallback.  The paired GPU matrix remains
pending.

Full local regression at this checkpoint: **135 passed, 3 expected cloud-only
skips**; Go core `vet` and race tests pass.

## Next (do not expand N first)

```text
commit semantic fix → pin git commit in results
→ wire RGB-D Claims on Genesis path
→ run a small paired W7900D smoke
→ re-run paired 90 on W7900D with workers=2 only after smoke passes
→ only then re-evaluate Gate B for contest
```

## GPU

Instance was idle (0% util) after the last matrix; operator may shut down to
save credits until the re-run.

## RGB-D smoke follow-on

See `results/capability-v5-rgbd-smoke/STATUS.md` for Genesis RGB-D Claims smoke (24 eps). No contest Gate B claim.
