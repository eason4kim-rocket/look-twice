# Look Twice v6 — Collaborative Evidence Repair (scaffold smoke)

## Framing

| Field | Value |
| --- | --- |
| Branch | `v6-collaborative-evidence-repair` |
| Baseline | `v5-learned-rgbd` @ `e2a2a72` |
| Kind | **scaffold / dual-agent synthetic smoke** |
| Real robot | **NO** |
| Formal Gate B | **NO** |
| Learned policy | **not trained yet** — primary active path is **purify-active heuristic** |
| Runtime | synthetic multi-agent kinematic (`batched-kinematic` interface) |
| Claims mode | `synthetic_multi_agent_v6` |

## What shipped

New entry: `src/look_twice_v6.py` (v5 CLI unchanged).

Modules:

- `v6_scenario.py` — dual corridor warehouse (carrier + scout)
- `v6_claims.py` — Claim v2 (observer / intended actor / received_step / communication_root)
- `v6_communication.py` — delay / drop / echo queue
- `v6_contracts.py` — carrier corridor gate + `authorize_evidence_request`
- `v6_motion.py` — `move_agent_to` multi-agent kinematic
- `v6_repair.py` — oracle-free heuristic evidence ranking
- `v6_episode.py` — deny → authorize request → observe → re-eval → deliver

Mission (no pick_proxy):

```text
carrier_reached_goal ∧ payload_delivered ∧ ¬unsafe ∧ collisions==0 ∧ within_deadline
```

## Smoke matrix (local synthetic)

3 policies × `shared-occlusion` × seeds {90000, 90001} = **6 episodes**.

| policy | seed | mission | unsafe | route | repair |
| --- | ---: | ---: | ---: | --- | --- |
| naive | 90000 | True | False | direct | — |
| naive | 90001 | False | **True** | none | — |
| purify-passive | 90000 | True | False | **detour** | no |
| purify-passive | 90001 | True | False | detour | no |
| purify-active | 90000 | True | False | **direct** | **success** |
| purify-active | 90001 | True | False | detour | attempted |

Formal narrative alignment (scaffold):

> Active spends observation budget to repair evidence and take a gated direct
> route on the clear world; passive fail-closes to detour; naive may cross unsafe.

## Unit tests

`tests/test_v6_core.py` — 14 passed:

- scout scope cannot satisfy carrier contract
- 100× echo → one capture root
- freshness by `observed_step` not receive time
- planner rejects oracle keys
- fixed evidence action set
- safe_fallback ≠ confirmed_blocked
- mission fields without pick_proxy
- active records EvidenceRequestReceipt

## Not yet done (later phases)

- Genesis dual RGB-D on AMD GPU
- physics-diff-drive URDF
- counterfactual dataset + learned ranker + DAgger
- formal 4800/3000 matrices / contest video
- Go-core `authorize_evidence_request` (Python gate used for scaffold)

## Cloud

Target: `root@36.150.116.206 -p 31128` → `/workspace/look-twice-v6` (sync after push).
