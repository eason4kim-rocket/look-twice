# Look Twice v6 — capability completion STATUS

Branch: `v6-collaborative-evidence-repair`  
Remote: `root@36.150.116.206:31128` `/workspace/look-twice-v6`  
GPU: AMD Radeon · `cuda:0` · Genesis 1.1.2 · `gs.amdgpu`

## Delivered

### 1. GPU active `repair_success` + clear `direct`
- Gate fix: usable-set-only deny reasons; `evidence_age_limit=2000`.
- Repair-fix matrix **75/75**: active mission 25/25, unsafe 0, **repair_success=6**, **direct=5**.
- Proof episode: `purify-active__shared-occlusion__90000` — repair=True, route=direct, genesis RGB-D.

### 2. Learned repair + DAgger ×3 + promotion
| Stage | Path | Result |
| --- | --- | --- |
| Pilot BC | `results/v6-learned-pilot/` | 256 worlds, 40 ep, `best.pt` |
| DAgger ×3 | `results/v6-learned-dagger/` | BC 256 + 3×96 rollouts → **1120** aggregate samples |
| Teacher agree | dagger probe | **85.4%** top-1 vs heuristic |
| Synthetic promote | `results/v6-promotion-synthetic/` | n=120: H repair **26** / L **46**; unsafe 0/0; **promote=true** |

**Online primary after synthetic promotion:** `purify-active-dagger` (checkpoint `outputs/v6/learned-dagger/best.pt`).  
Genesis paired promotion matrix is running/queued on GPU for confirmation; fail-closed rule remains if GPU pair worsens unsafe.

Policies now supported: `naive`, `purify-passive`, `purify-active`, `purify-active-learned`, `purify-active-dagger`, `purify-random`.

### 3. Physics diff-drive URDF acceptance
Path: `results/v6-physics-urdf/smoke.json` (GPU mirror `outputs/v6/physics-urdf/smoke.json`)

| Check | Status |
| --- | --- |
| URDF parse + continuous wheels | **pass** (carrier + scout) |
| Genesis load+build (AMD) | **pass** |
| 20-seed waypoint PD bar | **pass 20/20** (skid-steer PD proxy, URDF track width) |

Honest note: waypoint bar certifies **URDF geometry + diff-drive kinematics**, not full rigid-body wheel-torque dynamics in Genesis.

### 4. Contest video
Path: `results/v6-demo-video/`
- `demo.mp4` (real GPU episode trajectories)
- `STORYBOARD.md`, `beats.json`, `trajectory_panel.png`
- Source includes active repair_success direct + passive + naive clips

### 5. Upstream Genesis PR material
- `docs/genesis-amd-multi-agent-rgbd.md` (technical note)
- `docs/genesis-upstream-pr.md` (PR title/body + file path suggestion)
- Not auto-filed (needs maintainer `gh` auth on Genesis fork)

### 6. Formal / OOD / physics-180 matrices (GPU, resume-safe)

| Matrix | Design | Status |
| --- | --- | --- |
| Formal locked | 3×6×100 = **1800** | **Running** (`outputs/v6/formal-locked-3x6x100`, workers=4, resume-safe) |
| Formal learned | 3×6×100 = **1800** | **Running** (`purify-active-learned/dagger/random`, workers=2) |
| Formal total toward 4800 | 6 policies × 6 locked profiles × 100 = 3600; + 6×2 OOD×100 = **4800** design | locked+learned=3600 in flight; OOD profile fill follows |
| OOD | 3×2×500 = **3000** | **Running** (`heavy-occlusion`, `multi-fault`, seeds 200000–200499) |
| Physics-180 | 3×6×10 = **180** | **Running** (genesis kinematic; URDF acceptance separate) |

Profiles (8): locked 6 + OOD `heavy-occlusion`, `multi-fault`.

## Formal narrative

> On AMD GPU Genesis RGB-D, active pays observation cost to collect independent scout views; when two clear roots admit, carrier takes a **gated direct** corridor; otherwise Purify fail-closes to safe detour. Passive always detours when denied. Naive can go unsafe. Learned/DAgger ranker improves repair_success on synthetic promotion (46 vs 26 /120) with unsafe=0.

## Non-claims
- Not real-robot / Gate B product.
- Not full rigid-body wheel torque certification (waypoint = PD proxy).
- Mega-matrices still **in progress** on GPU (resume-safe); do not claim 4800/3000/180 complete until `parallel_summary.json` exists for each.
- Genesis upstream PR is content-ready, not necessarily merged.

## Key commits (this completion push)
- Learned/DAgger policies + promotion eval
- Physics waypoint acceptance
- Demo MP4 + Genesis PR draft
- OOD profiles + formal/OOD/physics matrix launches
