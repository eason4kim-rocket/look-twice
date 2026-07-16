# Look Twice v5 status (honest)

## Positioning

**Embodied Evidence Assurance** — contract-gated mobile navigation + proxy
manipulation under lineage-aware evidence on AMD W7900D.

Branch: `v5-embodied-evidence`  
v4 (`v4.0-hackathon-final`) frozen.

## Motion demotion

Skid-steer 5-seed × 4-viewpoint acceptance **failed** (12 failures, mostly
`obstacle_contact`). See `motion/v5-motion-accept-5.json`.

**v5 demo/matrix default: `kinematic`** (bounded velocity + chassis camera).
URDF/skid code retained; not claimed as skid-physics formal acceptance.

## GPU results archived

| Artifact | N / note |
| --- | --- |
| Cloud unit tests | 131 OK |
| Synthetic v5 episode | OK |
| Genesis single episode | `genesis-smoke/` W7900D `gs.amdgpu` |
| Smoke matrix | **18** = 3 policies × 6 profiles × seed 50000 |
| Unsafe crossings (smoke) | **0** |
| Dual contracts in JSON | `cross_region` + `pick_proxy` |
| Invalidation fields | present (counts vary by episode) |
| Claims mode on GPU | `synthetic_modality_proxies_on_gpu_motion` (honest) |

## Smoke rollup (seed 50000)

See `smoke-matrix/summary.csv`. Mission success rates are modest; safety-side
fail-closed (unsafe=0) is the primary formal-quality claim for this scaffold.

## Not claimed

- Skid-steer 10×4 acceptance
- Full formal large-N v5 matrix
- Real RGB-D Claims on GPU (still synthetic modality proxies for gate)
- Upstream Genesis PR
- Real-robot / sim-to-real

## GPU policy

Instance left running unless operator shuts down.
