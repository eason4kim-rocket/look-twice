# V7 Baseline Freeze (do not overwrite)

**Status:** frozen contest baseline. V8 is an independent Challenger.

## Frozen commits

| Role | SHA |
|------|-----|
| Runtime integration | `f68111f4f7f45a42376f0c9870d0fe1738f6589c` |
| Locked vision evaluator | `f8f73010ce05efb664773c67faa1544788bf079e` |
| NBV lateral planner | `87e54bea5555b74bbf1b98325ea76dffbb0dc9ae` |

## Frozen artifacts

| Artifact | SHA256 |
|----------|--------|
| Model `best.pt` | `385aa7b78197909e548cd39907bb21c3059987a4465c1d366ab221968636bcc9` |
| Conformal | `44f564633b6e2a303dd796380d8c300f41f0abce60124ee7f36f48feec0e7333` |
| Dataset manifest_all | `abfa99c309e03a009256da5fb1e6265a71eaf5508a6d3160fe5c3c1c87cb270e` |

## Frozen results (do not re-run)

| Result | Path / decision |
|--------|-----------------|
| Locked vision test | `outputs/v7/vision-locked-test-v1` — **passed=true, one-shot, archived** |
| Closed-loop 120 v1 | `vision-closedloop-matrix-120-v1` — **MATRIX_COMPLETE_NOT_FORMAL 35/60** |
| Closed-loop 120 NBV v2 | `vision-closedloop-matrix-120-nbv-v2` — **41/60 chain, formal=false** |
| Smoke24 NBV | seeds 99200–99203 — **9/12 chain, pass** |

## Rules

1. **Never re-open V7 locked_test.**
2. Do not retune V7 conformal thresholds for formal claims.
3. Do not lower V7 safety gates.
4. V8 uses **disjoint world seeds** (`100000+`) and its own locked split.
5. Only if V8 meets [V8_DESIGN.md](V8_DESIGN.md) promotion gates does it replace V7 as primary; otherwise V7 remains the submission baseline and V8 is an appendix.

## What V7 already proves

- Offline Genesis RGB head + conformal: excellent locked metrics once.
- Online Purify loop: unsafe=0, no silent fallback, world homology.
- Active vision recovers efficiency (35→41/60 full-chain after NBV alignment).
- Remaining misses are spatial-context contamination — the problem V8 targets.
