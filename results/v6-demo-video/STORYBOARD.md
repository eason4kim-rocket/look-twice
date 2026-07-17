# Look Twice v6 — contest demo storyboard

Source: real GPU Genesis RGB-D episode JSON (not synthetic fill).

## Clip 1: purify-active · shared-occlusion
- claims_mode: `genesis_rgbd_multi_agent_v6` device=`cuda:0`
- mission=True unsafe=False
- route=direct repair_success=True
- observations=3 replans=2
- gate receipts=10
- evidence requests=2
- RGB-D audits=3

## Clip 2: purify-passive · shared-occlusion
- claims_mode: `genesis_rgbd_multi_agent_v6` device=`cuda:0`
- mission=True unsafe=False
- route=detour repair_success=False
- observations=1 replans=0
- gate receipts=2
- evidence requests=0
- RGB-D audits=1

## Clip 3: naive · shared-occlusion
- claims_mode: `genesis_rgbd_multi_agent_v6` device=`cuda:0`
- mission=True unsafe=False
- route=direct repair_success=False
- observations=1 replans=0
- gate receipts=2
- evidence requests=0
- RGB-D audits=1

## Narrative beats (canonical)
1. Cold start: carrier front view is insufficient / shared-root risk.
2. Purify denies corridor cross (BeliefGaps residual not empty).
3. Active repair: scout side views authorized via EvidenceRequestReceipt.
4. Two independent clear capture roots then Gate admitted.
5. Carrier takes gated direct when repaired; else safe detour.
6. Passive always detours when denied; naive may go unsafe.

## Non-claims
- Not real-robot Gate B product.
- Not claiming learned beats heuristic unless promotion matrix says so.
- Physics video path is kinematic/skid-steer unless waypoint bar is shown.
