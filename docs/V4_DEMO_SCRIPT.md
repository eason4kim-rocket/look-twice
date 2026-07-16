# Look Twice v4 demo / video script (3–5 minutes)

English narration outline for the contest video. Shoot on W7900D Genesis
episodes already archived under `results/v4-gpu/`.

## Shot list

1. **Title (5s)**  
   Look Twice v4 — Active Evidence Assurance  
   Purify-powered, lineage-aware action qualification on AMD Radeon PRO W7900D.

2. **Many claims, false confidence (20–30s)**  
   Show evidence-echo episode UI/JSON: several Claims appear independent.  
   Cut to GateReceipt: `artifact_duplicate_of` discounts; measurement roots do
   not inflate.  
   Reference: `smoke-genesis/raw/purify-active__evidence-echo__seed-50000.json`  
   DAG: `figures/evidence_dag_purify-active_evidence-echo_seed-50000.dot`

3. **Action Gate rejects (20s)**  
   Prediction set unresolved / not singleton `{clear}`.  
   Contract clauses fail (roots, skew, or calibration).  
   Caption: unresolved/stale/conflict/OOD never enter the risk region.

4. **BeliefGap and repair (40–50s)**  
   List gap reasons (e.g. shared_root, insufficient_roots).  
   Robot moves to a diagnostic viewpoint (kinematic chassis + mounted camera).  
   New independent capture; prediction set updates.

5. **Plan invalidation and safe detour (30–40s)**  
   Stale GateReceipt invalidated; route replan.  
   Label **safe_fallback** detour — never masquerades as confirmed blocked when
   unresolved.

6. **AMD results (40–50s)**  
   Slide: smoke 96 complete; formal **956 completed + 4 errors** archived.  
   Safety: **0 unsafe** on completed formal episodes.  
   Honest failures: repair ~68% (&lt;80%); active conformal coverage not promoted.  
   Motion: skid acceptance failed → kinematic formal path.

7. **Close (10s)**  
   Code: github.com/eason4kim-rocket/look-twice  
   Branch: `v4-active-evidence-assurance`  
   Reference core is contest-only, not the Purify product.

## On-screen text rules

- Always show `gs.amdgpu` / W7900D when claiming GPU results.  
- Never present synthetic CI as formal.  
- Prefer numbers from `results/v4-gpu/STATUS.md` and `PROMOTION_SNAPSHOT.md`.
