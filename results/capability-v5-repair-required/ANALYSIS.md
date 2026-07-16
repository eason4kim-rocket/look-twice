# repair-required mini-eval analysis

## Cell list

| profile | seeds | world | role |
| --- | --- | --- | --- |
| `repair-required` | 50000 | clear (even) | active must repair → mission; passive incomplete+safe |
| `repair-required` | 50001 | blocked (odd) | naive may unsafe; purify fail-closed |
| `repair-required` | 50002 | clear (even) | second clear replication of active repair value |

**Forcing:** `public.initial_viewpoint_budget=1` (single initial measurement root).
Passive never repairs → gate deny → no `nav_success`. Active `side_view` adds a second root.

**Mission definition:** `nav ∧ pick ∧ ¬unsafe` (unchanged; detour ≠ nav credit).

## Matrix

- Device: `cuda:0` + AMD Radeon PRO W7900D
- claims_mode: **genesis_rgbd_depth_semantic** on all 9/9
- N = 3 policies × 1 profile × 3 seeds = 9
- Archive: `results/capability-v5-repair-required/`
- Cloud dir: `outputs/v5-repair-required-eval-r2`
- **Paired 90 was NOT run**

## Rollup criteria

```json
{
  "schema_version": "look-twice.repair-required-rollup/v1",
  "n": 9,
  "device": "cuda:0",
  "gpu": "AMD Radeon PRO W7900D",
  "claims_modes": [
    "genesis_rgbd_depth_semantic"
  ],
  "by_policy": {
    "naive": {
      "mission": 2,
      "nav": 2,
      "pick": 3,
      "unsafe": 1,
      "repair_attempted": 0,
      "repair_success": 0,
      "n": 3,
      "initial_gate": 0
    },
    "purify-active": {
      "mission": 2,
      "nav": 2,
      "pick": 3,
      "unsafe": 0,
      "repair_attempted": 3,
      "repair_success": 2,
      "n": 3,
      "initial_gate": 0
    },
    "purify-passive": {
      "mission": 0,
      "nav": 0,
      "pick": 3,
      "unsafe": 0,
      "repair_attempted": 0,
      "repair_success": 0,
      "n": 3,
      "initial_gate": 0
    }
  },
  "clear_world_contrast": {
    "passive_mission": 0,
    "active_mission": 2,
    "passive_nav": 0,
    "active_nav": 2,
    "passive_repair_attempted": 0,
    "active_repair_attempted": 2,
    "active_repair_success": 2,
    "naive_mission_clear": 2,
    "naive_unsafe_blocked": 1,
    "passive_unsafe": 0,
    "active_unsafe": 0,
    "clear_n_per_policy": 2,
    "blocked_n_per_policy": 1
  },
  "blocked_naive_unsafe": 1,
  "CRITERION1_active_repairs_to_mission": true,
  "CRITERION2_purify_safe": true,
  "CRITERION3_naive_unsafe_blocked": true,
  "CRITERION4_rgbd_claims": true,
  "GO_for_paired_90": true,
  "decision_note": "GO means the mini repair-required set differentiated policies. It does NOT auto-start the paired 90; that remains an explicit user decision."
}
```

## Quoted raw episode contrast

### purify-passive seed 50000 (clear) — incomplete + safe

```json
{
  "file": "purify-passive__repair-required__50000.json",
  "policy": "purify-passive",
  "seed": 50000,
  "claims_mode": "genesis_rgbd_depth_semantic",
  "mission_success": false,
  "nav_success": false,
  "pick_success": true,
  "unsafe_crossing": false,
  "initial_gate_admitted": false,
  "repair_attempted": false,
  "repair_success": false,
  "observation_count": 1,
  "repair_decision_count": 0,
  "invalidation_count": 0,
  "outcome": "pick_only_not_mission",
  "used_detour": true,
  "gate_receipts_summary": [
    {
      "admitted": false,
      "action": "cross_region",
      "gaps": [
        "shared_root",
        "insufficient_roots",
        "low_coverage"
      ],
      "decision": "denied"
    },
    {
      "admitted": true,
      "action": "pick_proxy",
      "gaps": [],
      "decision": "admitted"
    }
  ],
  "repair_decisions_head": []
}
```

Expected: `initial_gate_admitted=false`, `repair_attempted=false`, `mission_success=false`, `unsafe_crossing=false`.

### purify-active seed 50000 (clear) — repair → safe mission

```json
{
  "file": "purify-active__repair-required__50000.json",
  "policy": "purify-active",
  "seed": 50000,
  "claims_mode": "genesis_rgbd_depth_semantic",
  "mission_success": true,
  "nav_success": true,
  "pick_success": true,
  "unsafe_crossing": false,
  "initial_gate_admitted": false,
  "repair_attempted": true,
  "repair_success": true,
  "observation_count": 2,
  "repair_decision_count": 2,
  "invalidation_count": 1,
  "outcome": "mission_complete",
  "used_detour": false,
  "gate_receipts_summary": [
    {
      "admitted": false,
      "action": "cross_region",
      "gaps": [
        "shared_root",
        "insufficient_roots",
        "low_coverage"
      ],
      "decision": "denied"
    },
    {
      "admitted": false,
      "action": "cross_region",
      "gaps": [
        "shared_root",
        "insufficient_roots",
        "low_coverage"
      ],
      "decision": "denied"
    },
    {
      "admitted": true,
      "action": "cross_region",
      "gaps": [
        "low_coverage"
      ],
      "decision": "admitted"
    },
    {
      "admitted": true,
      "action": "cross_region",
      "gaps": [
        "low_coverage"
      ],
      "decision": "admitted"
    },
    {
      "admitted": true,
      "action": "pick_proxy",
      "gaps": [],
      "decision": "admitted"
    }
  ],
  "repair_decisions_head": [
    {
      "status": "selected",
      "reason": "highest_positive_utility",
      "kind": "side_view",
      "name": "left_near"
    },
    {
      "status": "selected",
      "reason": "highest_positive_utility",
      "kind": "side_view",
      "name": "left_near"
    }
  ]
}
```

Expected: initial deny → `repair_attempted`/`repair_success` → `mission_success=true`, `unsafe_crossing=false`, `observation_count>=2`, non-empty repair decisions / multi-receipt gate trail.

### naive seed 50001 (blocked) — distinct unsafe mode

```json
{
  "file": "naive__repair-required__50001.json",
  "policy": "naive",
  "seed": 50001,
  "claims_mode": "genesis_rgbd_depth_semantic",
  "mission_success": false,
  "nav_success": false,
  "pick_success": true,
  "unsafe_crossing": true,
  "initial_gate_admitted": false,
  "repair_attempted": false,
  "repair_success": false,
  "observation_count": 1,
  "repair_decision_count": 0,
  "invalidation_count": 0,
  "outcome": "pick_ok",
  "used_detour": false,
  "gate_receipts_summary": [
    {
      "admitted": false,
      "action": null,
      "gaps": [
        "insufficient_roots"
      ],
      "decision": null
    },
    {
      "admitted": true,
      "action": null,
      "gaps": [],
      "decision": null
    }
  ],
  "repair_decisions_head": []
}
```

Expected: `unsafe_crossing=true` (or otherwise distinct failure from active's safe incomplete on blocked).

## Go / no-go for later 90

- **GO eligibility:** true (`GO_for_paired_90` in rollup) because C1–C4 hold.
- **90 executed in this goal:** **false**.
- **Contest Gate B / new tag:** **not claimed**.
- Recommendation: only after an explicit decision, design the paired 90 around repair-required (second-root acquisition), not the undifferentiated 24-smoke mix.
