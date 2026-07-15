# Look Twice

**Evidence-gated active perception under noisy, dynamic observations on AMD GPU.**

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
- View-dependent RGB-D/segmentation corruption executed on ROCm tensors
- Probabilistic `p_blocked`, belief entropy, calibration trace, and TTL decay
- Information-Gain and optional Learned Next-Best-View policies
- Continuously randomized, paired scene distributions with balanced truth seeds

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

# Look Twice v3: noisy evidence + probabilistic belief + information gain
/opt/venv/bin/python src/look_twice_v3.py \
  --profile dynamic-change \
  --policy purify-information-gain \
  --seed 20000 \
  --evidence-dir outputs/v3-evidence \
  --json-output outputs/v3-dynamic.json
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
- `src/look_twice_v3.py` — v3 randomized noisy active-perception episode
- `src/belief.py` — Purify evidence resolution and action gate
- `src/perception.py` — ROCm RGB-D/segmentation evidence computation
- `src/viewpoint.py` — deterministic visibility scoring and Next-Best-View
- `src/sensor_noise.py` — view-dependent PyTorch sensor corruption
- `src/scenario.py` — reproducible continuous scene distribution
- `tests/test_belief.py` — deterministic belief unit tests
- `scripts/run_experiments.py` — resumable comparison matrix
- `scripts/summarize_experiments.py` — aggregate metrics
- `scripts/plot_trajectory.py` — top-down evidence and route plot
- `scripts/plot_comparison.py` — safety and observation-cost comparison
- `scripts/run_v2_experiments.py` — resumable 120-episode v2 matrix
- `scripts/summarize_v2_experiments.py` — v2 aggregate metrics
- `scripts/annotate_video.py` — state, belief, and Action Gate video overlays
- `scripts/run_v3_experiments.py` — resumable 500-episode paired matrix
- `scripts/benchmark_perception.py` — warmed CPU/ROCm batch benchmark
- `scripts/collect_nbv_dataset.py` and `scripts/train_nbv.py` — optional Learned NBV
- `docs/ARCHITECTURE.md` — system design and state flow
- `docs/ROADMAP.md` — implementation and submission roadmap
- `docs/V3_DESIGN.md` — v3 data isolation, noise, belief, NBV, and reproduction
- `docs/SUBMISSION_CHECKLIST.md` — verified deadline, judging criteria, and final actions
- `docs/SUBMISSION_DRAFT.md` — ready-to-adapt English competition description
- `results/` — versioned, reproducible experiment samples

## Results and demos

- [Formal 480-run experiment](results/2026-07-15_formal-experiment/README.md)
- [Rendered-camera perception validation](results/2026-07-15_camera-perception/README.md)
- [Look Twice v2 formal 120-run experiment](results/2026-07-15_v2-formal/README.md)
- [Look Twice v3 formal 500-run experiment](results/2026-07-15_v3-formal/README.md)
- [Look Twice v3 Learned NBV training and 100-run evaluation](results/2026-07-15_v3-learned/README.md)
- [Clear demo](assets/demo/clear.mp4)
- [Blocked demo](assets/demo/blocked.mp4)
- [Conflict-driven reinspection demo](assets/demo/conflict.mp4)
- [Approximately 60-second submission video draft](assets/demo/look-twice-demo.mp4)
- [V3 dynamic-change Learned NBV demo](assets/demo/v3/look-twice-v3-demo.mp4)
- [V3 raw/corrupted evidence panels and trajectory](assets/demo/v3/README.md)

At observation noise `0.3`, Purify achieved 97.5% safe success with an average
of 2.4 observations. Majority Vote achieved 95.0% with a fixed cost of 3
observations, while Single Shot achieved 82.5% with 1 observation.

In the v2 `dynamic-appears` experiment, Single Shot, Majority Vote, and fixed
Purify all produced a 100% unsafe-crossing rate. Active Purify detected stale
evidence, moved to a new viewpoint, and achieved 100% safe success across six
seeds. This safety gain required 4 observations, 1 replan, and a longer path.

In v3, the five-policy core matrix contains 500 paired episodes. Learned NBV
was trained on 200 randomized scenes and evaluated on disjoint 50-scene
validation and 100-scene test splits. It reduced held-out oracle regret from
0.0669 to 0.0421 and retained 100% safe success in a separate 100-episode
closed-loop evaluation. It did not beat the heuristic on every path-efficiency
metric; this limitation is reported with the result rather than hidden.

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
