# Look Twice demo script

## V2 opening sequence

Show `assets/demo/v2/dynamic-active-annotated.mp4` while explaining:

> The robot first confirms the passage is clear. A dynamic obstacle then
> appears. When the robot approaches the passage, the old evidence has expired,
> so the Action Gate refuses entry. The robot moves to a new viewpoint, obtains
> fresh RGB-D evidence on the AMD GPU, confirms blockage, and takes the detour.

Briefly show the RGB, depth, and segmentation evidence triplets beside the
top-down route. State explicitly that segmentation is a Genesis simulated
sensor, not a trained perception model.

Target length: 60–90 seconds.

## 0–12 seconds — Problem

Show an occluded route and the robot at the start.

> A single uncertain observation should not authorize a risky crossing. But a
> robot that always stops is not useful either.

## 12–30 seconds — Evidence gate

Show the clear run. Display the first observation as provisional and the direct
action as denied. Display the second consistent observation as confirmed and
the direct route as allowed.

> Look Twice separates observations from belief. One clear observation remains
> provisional. Consistent evidence is required before direct passage.

## 30–52 seconds — Active reinspection

Show the first-flip conflict run. Highlight the conflicting evidence and the
physical move from the left inspection point to the right inspection point.

> When evidence conflicts, Purify does not guess. It makes the robot move to a
> new viewpoint and collect the evidence needed to resolve the decision.

## 52–68 seconds — Safe fallback

Briefly show the alternating-noise run.

> If uncertainty remains after reinspection, the action gate still refuses
> direct passage and selects the safe detour without pretending the region was
> confirmed blocked.

## 68–82 seconds — Measured result

Show the policy comparison chart.

> Single Shot is cheap but unsafe under observation noise. Majority Vote is
> robust but always pays for three observations. Look Twice adapts its sensing
> cost to the quality and consistency of evidence.

## 82–90 seconds — AMD

Show the environment summary and repository.

> The physics simulation and experiment matrix run on an AMD Radeon PRO W7900D
> using ROCm, PyTorch, Genesis 1.1.2, and the `gs.amdgpu` backend.
