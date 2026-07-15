# Look Twice v4 — Active Evidence Assurance

**A Purify-powered, lineage-aware action qualification and active evidence
repair system for Physical AI on AMD GPU.**

Look Twice asks a stricter question than ordinary obstacle detection: when
depth, semantic perception, and a static map disagree, is the world changing,
is a sensor failing, or are several apparent observations merely copies of the
same physical measurement? The robot may cross a high-risk region only when a
versioned evidence contract is satisfied. Otherwise it actively acquires the
specific evidence needed to repair that contract, invalidates stale plans, or
uses an explicitly labelled safe fallback.

中文简介：Look Twice v4 不只是判断前方 `clear / blocked`。它检查证据是否
新鲜、独立、同源、冲突以及是否仍在校准适用范围内；证据不足时，机器人会选择
能够修复证据缺口的观察动作，而不是盲目前进或永久停止。

## Closed loop

```text
Depth Claim + Semantic Claim + Static Map Claim
→ lineage-aware root fusion
→ class-conditional conformal prediction set
→ Action Contract
→ GateReceipt
→ BeliefGap-driven physical observation
→ revised facts + PlanInvalidationReceipt
→ cross, detour, or fail closed
```

The online path never receives clean simulator truth. Genesis entity
segmentation is used as a transparent **simulated semantic sensor proxy** after
controlled corruption; clean segmentation and world state remain in a separate
oracle/evaluation channel.

## What is implemented now

Status is intentionally split so local CI results cannot be confused with AMD
GPU evidence. Packaged W7900D artifacts live under
[`results/v4-gpu/`](results/v4-gpu/STATUS.md).

| Capability | Implemented | Locally verified | W7900D / formal status |
| --- | :---: | :---: | --- |
| Immutable Robot Claim v1 and JSON Schemas | Yes | Yes | GPU-independent |
| Capture/artifact/parent-lineage collapse | Yes | Yes | Verified on W7900D smoke (echo discounts) |
| Standalone Go 1.23 Purify Robotics Reference Core | Yes | Yes | Linux amd64 binary on cloud |
| Persistent Python ↔ Go NDJSON bridge | Yes | Yes | Used in all Genesis episodes |
| Root-aware fusion, Action Contract and hashed receipts | Yes | Yes | GateReceipts in archived JSON |
| Class-conditional split-conformal artifact | Yes | Yes | Fitted partial cal in `results/v4-gpu/calibration/` |
| BeliefGap-driven repair planner | Yes | Yes | Exercised on W7900D smoke |
| Six comparison policies and eight stress profiles | Yes | Yes | **96 smoke complete**; **960 formal in progress** |
| Deterministic synthetic runtime | Yes | Yes | **Never a formal GPU result** |
| Kinematic motion backend | Yes | Yes | **Formal/smoke default after skid demotion** |
| Four-wheel skid-steer URDF and wheel controller | Yes | Unit tests | **Acceptance failed** → demoted (see STATUS) |
| Genesis RGB-D/entity-segmentation v4 runtime | Yes | Yes | **W7900D `gs.amdgpu` episodes archived** |
| AMD multi-environment `n_envs=8` feasibility | Planned | No | Not blocking; single-env used |
| 60 physical skid-steer validation episodes | No | — | Blocked by skid acceptance failure |
| Upstream Genesis contribution | Planned | No | No PR claimed yet |

**Completed on W7900D (archived):** Genesis smoke matrix 6×8×2=96 with fitted
calibration; 8-profile single-seed smokes; ROCm evidence benchmark; partial
calibration artifact; representative figures/DAG. **Incomplete:** locked-test
formal closed-loop 6×8×20=960 (runner still on GPU; packaged subset only).

## Purify IP boundary

This repository does **not** contain or depend on the private Purify product or
its unfinished assimilation engine. It contains only a clean, standalone
contest implementation:

- Purify Robotics Reference Core v0.1;
- public Robot Evidence Contracts and JSON Schemas;
- the Look Twice robotics adapter and benchmark;
- code and small artifacts required to reproduce the submission.

It excludes Purify product history, private APIs, production connectors,
databases, commercial modules, and unreleased internal designs. `NOTICE`
records this boundary. The contest reference API is not a compatibility promise
for a future Purify product.

中文说明：本仓库只公开比赛所需的最小机器人参考实现，不会把完整 Purify 产品、
私有同化引擎或未来商业接口纳入参赛 Entry。

## Fresh-clone local verification

Requirements: Python 3.11+ and Go 1.23+. CPU tests install only NumPy and Pillow;
Genesis and ROCm are required only for the cloud integration tier.

```bash
git clone https://github.com/eason4kim-rocket/look-twice.git
cd look-twice

python -m pip install numpy pillow
python -m unittest discover -s tests -v

./scripts/build_purify_robotics.sh
```

Run a deterministic CI smoke episode through the real Go gate:

```bash
python src/look_twice_v4.py \
  --runtime synthetic \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --allow-smoke-calibration \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/v4-synthetic-smoke.json
```

This command validates orchestration only. Its result contains:

```text
runtime = synthetic-ci
formal_result_eligible = false
```

It must not be quoted as a Genesis, ROCm, W7900D, physics, or formal experiment
result.

## AMD W7900D integration command

The competition image uses `/opt/venv/bin/python`. Formal Genesis runs require a
fitted calibration artifact; `--allow-smoke-calibration` is integration-debug
only. After skid-steer acceptance failure, **formal and smoke matrices use
`--motion-backend kinematic`**.

Cross-compile the Go core on a Go host (or use CI), copy the Linux amd64 binary
to the instance, pin the Git commit, then:

```bash
# On the AMD instance (Genesis + ROCm image)
export PATH=/opt/venv/bin:$PATH
export PYTHONPATH=src
export PYOPENGL_PLATFORM=egl
# echo <40-hex-commit> > .git_commit

# Single episode (fitted calibration from results/v4-gpu/calibration/)
/opt/venv/bin/python src/look_twice_v4.py \
  --runtime genesis \
  --motion-backend kinematic \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --device cuda:0 \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/v4/episode.json

# Smoke matrix (96) then formal (960, resume-safe)
/opt/venv/bin/python scripts/run_v4_experiments.py \
  --mode smoke --runtime genesis --motion kinematic \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --device cuda:0 --output-dir outputs/v4-smoke-genesis

/opt/venv/bin/python scripts/run_v4_experiments.py \
  --mode formal --runtime genesis --motion kinematic \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --device cuda:0 --output-dir outputs/v4-formal-genesis
```

Archived smoke results and honest formal partial counts:
[`results/v4-gpu/STATUS.md`](results/v4-gpu/STATUS.md). Full reproduction order:
[V4 reproduction](docs/V4_REPRODUCTION.md).

## V4 experiment design

Stress profiles:

```text
independent-noise          shared-occlusion
evidence-echo              time-skew
pose-calibration-drift     structured-depth-dropout
dynamic-change             ood-severity
```

Policies:

```text
naive-majority             v3-logodds
conformal-only             lineage-only
purify-passive             purify-active
```

Frozen data splits and matrices:

- calibration: 7 in-distribution profiles × seeds `30000–30049` = 350;
- validation: 7 profiles × seeds `40000–40019` = 140;
- locked test pool: 8 profiles × seeds `50000–50099` = 800;
- smoke matrix: 6 policies × 8 profiles × 2 seeds = 96 — **complete on W7900D**
  (`results/v4-gpu/smoke-genesis/`);
- formal closed loop: 6 × 8 × 20 = 960 — **in progress** on the live GPU; Mac
  package holds the current incomplete N under `results/v4-gpu/formal-genesis/`;
- skid-steer validation: 3 × 4 × 5 = 60 — **not run** (motion acceptance failed;
  kinematic demotion).

Do not treat synthetic CI episodes as GPU formal results. See the
[experiment protocol](docs/V4_EXPERIMENT_PROTOCOL.md) and
[`results/v4-gpu/STATUS.md`](results/v4-gpu/STATUS.md).

## Repository map

- `src/look_twice_v4.py` — v4 single-episode entrypoint
- `src/v4_episode.py` — Claim → gate → repair → action closed loop
- `src/v4_claims.py`, `schemas/` — public evidence wire contracts
- `purify_robotics/` — standalone Go reference core and NDJSON service
- `src/purify_bridge.py` — persistent deterministic Python client
- `src/v4_perception.py`, `src/v4_evidence.py` — independent modality Claims
- `src/v4_conformal.py` — calibration artifact and prediction sets
- `src/repair_planner.py` — contract-repair observation selection
- `src/v4_policies.py` — six frozen comparison policies
- `src/v4_scenario.py` — paired stress scenarios and oracle boundary
- `src/v4_motion.py`, `src/v4_genesis_motion.py` — two motion backends
- `src/v4_genesis_runtime.py` — AMD Genesis camera/physics adapter
- `src/v4_metrics.py` — Wilson CI, Brier, ECE and conformal metrics
- `scripts/build_v4_calibration.py` — strict calibration artifact builder
- `scripts/summarize_v4_experiments.py` — deterministic, atomic summaries

## Preserved v3 baseline

V3 remains frozen at tag `v3.0-noisy-active-perception`; v4 does not rewrite
its data or conclusions.

- [Formal 500-run v3 experiment](results/2026-07-15_v3-formal/README.md)
- [Learned NBV training and 100-run evaluation](results/2026-07-15_v3-learned/README.md)
- [V3 evidence and demo package](assets/demo/v3/README.md)

The verified v3 five-policy matrix contains 500 paired episodes. Learned NBV
was trained on 200 randomized scenes and evaluated on isolated 50-scene
validation and 100-scene test splits. It reduced held-out oracle regret from
0.0669 to 0.0421 and retained 100% safe success in its separate 100-episode
closed-loop evaluation. It did not outperform the heuristic on every
path-efficiency metric; that limitation remains reported.

Earlier preserved results:

- [Formal 480-run v1 experiment](results/2026-07-15_formal-experiment/README.md)
- [Rendered-camera validation](results/2026-07-15_camera-perception/README.md)
- [Formal 120-run v2 experiment](results/2026-07-15_v2-formal/README.md)

## AMD role

The verified v3 environment used:

```text
GPU: AMD Radeon PRO W7900D
Backend: gs.amdgpu
ROCm: 7.2
PyTorch: 2.9.1 ROCm build
Genesis: 1.1.2
Python: 3.12 (/opt/venv/bin/python)
```

V4 uses that GPU for Genesis physics, RGB-D/entity-segmentation rendering,
ROCm tensor corruption/evidence processing, and experiment throughput. The Go
admission core intentionally runs on CPU as a low-latency governance layer.
**Archived W7900D work** (see [`results/v4-gpu/STATUS.md`](results/v4-gpu/STATUS.md)):
smoke matrix 96, partial calibration, ROCm evidence benchmark, and a growing
formal closed-loop subset. Formal **960** is still running on the live instance.
Timing reports separate simulation, rendering, tensor kernels, transfer, gate,
and end-to-end stages where measured (`results/v4-gpu/bench/`).

## Known limitations

- V4 has no real-robot or sim-to-real result.
- Genesis entity segmentation is a disclosed simulated semantic sensor proxy,
  not a trained segmentation model.
- The fast `kinematic` Genesis backend still applies integrated poses with
  `set_pos()` and is intended for batch experiments, not the physical-motion
  claim.
- The skid-steer URDF and controller failed the 10×4 W7900D acceptance gate;
  formal matrices use the kinematic backend (see STATUS).
- The calibration guarantee applies only to the declared simulated
  in-distribution population; OOD configurations fail closed and receive no
  coverage claim. The archived calibration split is **partial** (336/350).
- The Purify reference core is a contest slice, not the complete Purify product
  or a certified robot-safety system.
- Claimed when archived: smoke **96**, GPU evidence **benchmark**, partial
  formal subset under `results/v4-gpu/formal-genesis/`. **Not** claimed complete:
  formal **960**, skid-steer physical **60**, contest video, upstream Genesis PR.

See [environment notes](docs/ENVIRONMENT.md), [architecture](docs/ARCHITECTURE.md),
and the [submission checklist](docs/SUBMISSION_CHECKLIST.md).
