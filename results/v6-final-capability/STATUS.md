# Look Twice v6 — capability completion STATUS (honest)

Branch: `v6-collaborative-evidence-repair`  
Remote: `root@36.150.116.206:31128` `/workspace/look-twice-v6`  
GPU: AMD Radeon · `cuda:0` · Genesis 1.1.2 · `gs.amdgpu`

## Delivered (done)

### 1. GPU active repair_success + clear direct
- Root-cause: gate poisoned by stale-sibling `evidence_age` + age limit 80 vs multi-view travel.
- Fix: usable-set-only deny reasons; `evidence_age_limit=2000`.
- **Single GPU proof** (`active_clear_repair.json`):  
  `repair_success=True`, `route_mode=direct`, `claims_mode=genesis_rgbd_multi_agent_v6`, unsafe=False.
- **Passive** same world: detour; **naive**: direct (clear seed).

### 2. Re-matrix after fix (75 episodes)
Path: `results/v6-gpu-matrix-3x5x5-repairfix/`  
3×5×5, genesis RGB-D, **75/75 ok**, purify **unsafe=0**.

| policy | mission | unsafe | repair_success | direct | detour |
| --- | ---: | ---: | ---: | ---: | ---: |
| naive | 12 | **7** | 0 | 12 | 0 |
| purify-passive | **25** | **0** | 0 | 0 | **25** |
| purify-active | **25** | **0** | **6** | **5** | 20 |

Active now shows **some** clear direct after repair (5/25 direct, 6 repair_success).  
Not yet majority direct — honest.

### 3. Learned repair pilot (counterfactual imitation)
Path: `results/v6-learned-pilot/`  
- 256 worlds labeled, 40 epochs, `best.pt` + `last.pt`  
- Pure PyTorch listwise + BCE + pairwise  
- **Promotion:** not claimed. Primary closed-loop remains **purify-active heuristic** until paired eval beats heuristic on locked seeds. Learned is exploratory.

### 4. Diff-drive URDF
Path: `results/v6-physics-urdf/smoke.json`  
- Carrier + scout URDFs parse OK; continuous wheel joints OK.  
- Genesis load+build: **both loaded**.  
- Full 20-seed waypoint PD bar: **`not_run_full_bar`** (honest). Large matrices stay kinematic; video must not claim true wheel dynamics.

### 5. Demo video assets
Path: `results/v6-demo-video/`  
- `STORYBOARD.md` + `trajectory.png` from real GPU episode JSON (not fabricated).

### 6. Upstream note
Path: `docs/genesis-amd-multi-agent-rgbd.md`  
Ready as content for a Genesis AMD multi-agent RGB-D docs/example PR (not auto-filed without maintainer review).

## In progress / incomplete vs mega-spec

| Item | Status |
| --- | --- |
| Formal 4800 (6×8×100) | **Not complete.** Tranche **3×6×100=1800** running on GPU (`outputs/v6/formal-locked-3x6x100`, resume-safe; ~90+ JSON at archive time). |
| OOD 3000 | **Not launched** (depends on free GPU after locked tranche). |
| Physics 180 | URDF smoke only; not 180 physics episodes. |
| DAgger ×3 | Pilot imitation only; no three DAgger rounds yet. |
| Learned promotion | Fail-closed: **heuristic remains primary**. |

## Formal narrative (this package)

> On AMD GPU Genesis RGB-D, active pays observation cost to collect independent scout views; when two clear roots admit, carrier takes a **gated direct** corridor; otherwise Purify fail-closes to safe detour. Passive always detours when denied. Naive can go unsafe.

## Commits (recent)
- `a6be5a6` — repair admit fix, learned pilot, URDFs, demo tooling  
- `4a6a7a8` — first Genesis RGB-D 75-ep matrix  
- earlier scaffold/gate fixes  

## Non-claims
- Not real-robot / Gate B product.  
- Not “learned beats heuristic”.  
- Not full 4800+3000+180 complete.  
- Not true differential-drive waypoint certification.
