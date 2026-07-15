# Track 3, Look Twice — submission draft

## Project

**Look Twice: Evidence-gated active perception under noisy, dynamic and
view-dependent observations.**

Look Twice is a simulated indoor navigation robot that refuses to enter a
high-risk region when its evidence is insufficient or stale. Instead, it moves
to a viewpoint expected to reduce uncertainty, collects another noisy RGB-D
observation, updates a probabilistic belief, and then proceeds or detours.

## Problem

A single apparently clear observation can be wrong because of occlusion,
depth failure, segmentation loss or an obstacle that appears after the robot
looked. A safe robot should neither trust that observation blindly nor stop
forever. It needs an explicit mechanism for deciding when to trust evidence
and where to look next.

## Method

The closed loop is:

```text
Genesis RGB-D and entity-segmentation sensor proxy
-> view-dependent corruption on AMD ROCm tensors
-> weighted log-odds belief and entropy
-> temporal Action Gate
-> fixed, random, heuristic information-gain, or learned NBV
-> proceed, reinspect, or safely detour
```

Clean Genesis segmentation is retained only as simulator ground truth and an
evaluation label. The belief and planner receive corrupted evidence. The
planner is prohibited from reading unknown obstacle truth, future observations
or clean segmentation.

## AMD GPU use

- Genesis 1.1.2 simulation uses `gs.amdgpu` on an AMD Radeon PRO W7900D.
- RGB, depth and segmentation corruption runs in PyTorch ROCm on `cuda:0`.
- Candidate evidence and the Learned NBV MLP are evaluated and trained on the
  same AMD GPU.
- The benchmark uses 20 warm-ups and 100 timed iterations, separating kernel,
  transfer and end-to-end time.
- At batch 128 the evidence kernel reached 99,166 observations/s, 148.0x the
  measured CPU kernel throughput; end-to-end speedup was 15.0x.

## Evaluation

The core experiment contains 500 paired episodes:

```text
5 policies x 5 randomized profiles x 20 held-out seeds
```

All policies share the same scene and noise seed. The profiles cover mixed
static scenes, view-dependent occlusion, segmentation degradation, depth
degradation and dynamic change. Every episode writes an auditable schema-v3
JSON trace.

In the dynamic-change profile, Single Shot and Fixed Multi-View each had a 50%
unsafe-crossing rate. Purify Fixed, Random and Information-Gain all achieved
100% safe success and zero unsafe crossings. Information-Gain reduced path
length by 1.74–2.27 units relative to Random across all profiles, with paired
95% bootstrap intervals excluding zero.

The optional Learned NBV used 200 train, 50 validation and 100 isolated test
scenes. It reduced held-out oracle regret from 0.0669 to 0.0421 and retained
100% safe success over a separate 100-episode closed-loop evaluation. It did
not beat the heuristic on every path-efficiency metric, and that limitation is
reported explicitly.

## Demo

The dynamic demo shows this sequence:

```text
confirmed clear
-> obstacle appears
-> evidence becomes stale
-> Action Gate denies route commitment
-> Learned NBV selects new viewpoints
-> confirmed blocked
-> Action Gate permits a detour
-> goal reached safely
```

## Reproducibility and limitations

Code, seeds, result tables, representative raw JSON, dataset hashes, trained
model, sensor evidence and demo assets are versioned in the repository. The
robot is intentionally a simplified box moved with `set_pos()`; this project
does not claim wheel dynamics, a trained segmentation model, sim-to-real, or a
physical robot deployment. Its contribution is the auditable active-perception
and evidence-gating loop.

## Links

- Source: https://github.com/eason4kim-rocket/look-twice
- Core results: `results/2026-07-15_v3-formal/`
- Learned NBV: `results/2026-07-15_v3-learned/`
- Annotated demo: `assets/demo/v3/look-twice-v3-demo.mp4`
