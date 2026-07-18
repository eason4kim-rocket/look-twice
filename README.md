# Look Twice

Version index for reviewers: **[VERSIONS.md](VERSIONS.md)**  
(Branches/tags `v1`–`v6` (+ v5-learned, v7 scaffold). `main` tip is still the v2 publish; use the version branches for later work.)

---

# Look Twice

**Temporal evidence-gated next-best-view navigation on AMD GPU.**

Look Twice is a Physical AI project for the AMD AI DevMaster Hackathon. It
addresses a simple safety problem: when a robot cannot confirm whether an
occluded area is safe, it should neither rush through nor stop forever. It
should move to a better viewpoint, collect evidence, and act only when the
evidence is reliable enough.

中文简介：Look Twice 是一个通过证据结算与行动准入实现安全导航的主动感知系统。
机器人面对未知区域时会主动换观察位置；证据确认安全后直行，确认阻挡后绕行，证据冲突时继续观察。

## Why it is different

```text
Genesis RGB + depth + instance segmentation
-> AMD GPU evidence computation
-> Purify belief resolution
-> action gate
-> proceed, detour, actively reinspect, or reject stale evidence
```

The action gate never treats one `clear` observation as sufficient evidence.
The first observation is provisional. Two consistent, confident observations
are required for confirmation. Conflicting observations make the robot move to
a second inspection viewpoint. If uncertainty remains, direct passage is
denied and a safe detour is selected.

## Current capabilities

- Scene-driven `clear` and `blocked` outcomes in Genesis
- Optional Genesis RGB camera perception with saved evidence frames
- RGB-D and entity-segmentation evidence computed by ROCm PyTorch on `cuda:0`
- Deterministic Next-Best-View selection from four candidate viewpoints
- Temporal belief expiry and mandatory verification before passage entry
- Dynamic obstacle appearance, clearance, and shifted-occluder scenarios
- Evidence lifecycle: unknown, provisional, uncertain, and confirmed
- Conflict-driven movement to a second inspection viewpoint
- Safe fallback when evidence remains unresolved
- Reproducible noise profiles and random seeds
- Single Shot, Majority Vote, and Purify policy comparison
- Versioned JSON results with evidence, decisions, transitions, and trajectory
- Batch experiment runner with resume support
- Trajectory and policy-comparison plots
- AMD GPU simulation through `gs.amdgpu`

## Quick start

The competition cloud image provides the tested environment at
`/opt/venv/bin/python`.

```bash
# Confirmed clear: inspect, then go directly to the goal
/opt/venv/bin/python src/look_twice_v0.py \
  --policy purify \
  --scenario clear \
  --noise-profile none

# Conflicting evidence: move to the second viewpoint, then resolve
/opt/venv/bin/python src/look_twice_v0.py \
  --policy purify \
  --scenario blocked \
  --noise-profile first-flip \
  --seed 0

# Save a reproducible structured result
/opt/venv/bin/python src/look_twice_v0.py \
  --policy purify \
  --scenario blocked \
  --noise-profile first-flip \
  --seed 0 \
  --json-output outputs/blocked-first-flip.json

# Use rendered camera pixels instead of reading entity coordinates
/opt/venv/bin/python src/look_twice_v0.py \
  --policy purify \
  --scenario blocked \
  --sensor-mode camera \
  --noise-profile first-flip \
  --evidence-dir outputs/camera-evidence \
  --json-output outputs/camera-result.json

# Look Twice v2: GPU RGB-D + Next-Best-View + temporal Action Gate
/opt/venv/bin/python src/look_twice_v0.py \
  --policy purify-active \
  --scenario dynamic-appears \
  --sensor-mode camera-rgbd \
  --viewpoint-policy next-best \
  --belief-ttl 60 \
  --evidence-dir outputs/v2-evidence \
  --json-output outputs/v2-dynamic.json
```

Run the standard-library belief tests:

```bash
python -m unittest discover -s tests -v
```

Run the complete 480-episode comparison matrix:

```bash
/opt/venv/bin/python scripts/run_experiments.py \
  --output-dir outputs/experiment-formal \
  --seed-count 20 \
  --python /opt/venv/bin/python

python scripts/summarize_experiments.py \
  --runs outputs/experiment-formal/runs.csv \
  --output outputs/experiment-formal/aggregate.csv
```

## Repository

- `src/look_twice_v0.py` — Genesis scene, mission state machine, policies, and results
- `src/belief.py` — Purify evidence resolution and action gate
- `src/perception.py` — ROCm RGB-D/segmentation evidence computation
- `src/viewpoint.py` — deterministic visibility scoring and Next-Best-View
- `tests/test_belief.py` — deterministic belief unit tests
- `scripts/run_experiments.py` — resumable comparison matrix
- `scripts/summarize_experiments.py` — aggregate metrics
- `scripts/plot_trajectory.py` — top-down evidence and route plot
- `scripts/plot_comparison.py` — safety and observation-cost comparison
- `scripts/run_v2_experiments.py` — resumable 120-episode v2 matrix
- `scripts/summarize_v2_experiments.py` — v2 aggregate metrics
- `scripts/annotate_video.py` — state, belief, and Action Gate video overlays
- `docs/ARCHITECTURE.md` — system design and state flow
- `docs/ROADMAP.md` — implementation and submission roadmap
- `results/` — versioned, reproducible experiment samples

## Results and demos

- [Formal 480-run experiment](results/2026-07-15_formal-experiment/README.md)
- [Rendered-camera perception validation](results/2026-07-15_camera-perception/README.md)
- [Look Twice v2 formal 120-run experiment](results/2026-07-15_v2-formal/README.md)
- [Clear demo](assets/demo/clear.mp4)
- [Blocked demo](assets/demo/blocked.mp4)
- [Conflict-driven reinspection demo](assets/demo/conflict.mp4)
- [Approximately 60-second submission video draft](assets/demo/look-twice-demo.mp4)

At observation noise `0.3`, Purify achieved 97.5% safe success with an average
of 2.4 observations. Majority Vote achieved 95.0% with a fixed cost of 3
observations, while Single Shot achieved 82.5% with 1 observation.

In the v2 `dynamic-appears` experiment, Single Shot, Majority Vote, and fixed
Purify all produced a 100% unsafe-crossing rate. Active Purify detected stale
evidence, moved to a new viewpoint, and achieved 100% safe success across six
seeds. This safety gain required 4 observations, 1 replan, and a longer path.

## Tested AMD environment

- GPU: AMD Radeon PRO W7900D
- Backend: `gs.amdgpu`
- ROCm: 7.2
- PyTorch: 2.9.1 ROCm build
- Genesis: 1.1.2
- Python: 3.12

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for environment and persistence
notes.

## Known limitations

- The robot is currently a fixed box moved with `set_pos()`, not a wheel model.
- Legacy `camera` mode uses a color rule. V2 `camera-rgbd` uses Genesis entity
  segmentation as a transparent simulated sensor proxy, not a trained model.
- Reported GPU perception latency includes first-use ROCm warm-up and is not an
  optimized throughput benchmark.
- Noise is controlled and synthetic so policy behavior remains reproducible.
- Safe navigation is demonstrated in simulation; no real-robot claim is made.
