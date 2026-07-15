# Look Twice

**Evidence-gated active perception for safe navigation.**

Look Twice is a Physical AI project for the AMD AI DevMaster Hackathon. It
addresses a simple safety problem: when a robot cannot confirm whether an
occluded area is safe, it should neither rush through nor stop forever. It
should move to a better viewpoint, collect evidence, and act only when the
evidence is reliable enough.

中文简介：Look Twice 是一个通过证据结算与行动准入实现安全导航的主动感知系统。
机器人面对未知区域时会主动换观察位置；证据确认安全后直行，确认阻挡后绕行，证据冲突时继续观察。

## Why it is different

```text
scene truth
-> noisy observations
-> Purify belief resolution
-> action gate
-> proceed, detour, or actively reinspect
```

The action gate never treats one `clear` observation as sufficient evidence.
The first observation is provisional. Two consistent, confident observations
are required for confirmation. Conflicting observations make the robot move to
a second inspection viewpoint. If uncertainty remains, direct passage is
denied and a safe detour is selected.

## Current capabilities

- Scene-driven `clear` and `blocked` outcomes in Genesis
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
- `tests/test_belief.py` — deterministic belief unit tests
- `scripts/run_experiments.py` — resumable comparison matrix
- `scripts/summarize_experiments.py` — aggregate metrics
- `scripts/plot_trajectory.py` — top-down evidence and route plot
- `scripts/plot_comparison.py` — safety and observation-cost comparison
- `scripts/annotate_video.py` — state, belief, and Action Gate video overlays
- `docs/ARCHITECTURE.md` — system design and state flow
- `docs/ROADMAP.md` — implementation and submission roadmap
- `results/` — versioned, reproducible experiment samples

## Results and demos

- [Formal 480-run experiment](results/2026-07-15_formal-experiment/README.md)
- [Clear demo](assets/demo/clear.mp4)
- [Blocked demo](assets/demo/blocked.mp4)
- [Conflict-driven reinspection demo](assets/demo/conflict.mp4)

At observation noise `0.3`, Purify achieved 97.5% safe success with an average
of 2.4 observations. Majority Vote achieved 95.0% with a fixed cost of 3
observations, while Single Shot achieved 82.5% with 1 observation.

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
- Geometry-based observations stand in for a future camera/depth sensor.
- Noise is controlled and synthetic so policy behavior remains reproducible.
- Safe navigation is demonstrated in simulation; no real-robot claim is made.
