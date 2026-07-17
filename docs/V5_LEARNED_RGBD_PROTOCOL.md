# V5 learned RGB-D sensor protocol

## Purpose

Replace the runtime semantic segmentation proxy with a small learned sensor
that predicts `p_blocked` from RGB and depth. Clean Genesis segmentation is an
offline label/audit source only and is never a model input.

## Input and model

- projected risk-region crop;
- RGB, normalized depth, and depth-validity mask (`5×64×64`);
- three convolution blocks and one scalar logit (~100 KB checkpoint);
- training and augmentation run in PyTorch on ROCm `cuda:0`.

Depth geometry remains a separate deterministic Claim. Both learned semantic
and depth Claims derived from one camera capture retain the same measurement
root, so Purify cannot count them as independent physical observations.

## Frozen split

| Split | World seeds | Worlds | Purpose |
| --- | --- | ---: | --- |
| Train | `10000–10199` | 200 | fit model weights |
| Calibration | `30000–30049` | 50 | fit conformal thresholds only |
| Validation | `40000–40039` | 40 | architecture/early stopping |
| Locked test | `50000–50099` | 100 | one final evaluation |

Each consecutive even/odd seed pair uses the same profile, preventing profile
identity from becoming a clear/blocked shortcut. Profiles rotate across
`independent-noise`, `shared-occlusion`, `evidence-echo`, `time-skew`,
`dynamic-change`, and `repair-required`. Every reachable side viewpoint is
captured; unreachable viewpoints are recorded as absent, not fabricated.

The collector applies the same deterministic ROCm corruption function used by
the deployed evidence pipeline before preprocessing. Manifests include sample,
input, raw-frame, corrupted-frame, and oracle-segmentation hashes.

## Promotion gates

The learned sensor enters the final Look Twice demo only if all are true:

1. validation and locked-test balanced accuracy are at least `0.85`;
2. locked-test Brier score is at most `0.15`;
3. class-conditional conformal coverage satisfies the declared alpha tolerance;
4. no locked-test seed is used to change architecture, thresholds, or planner;
5. closed-loop Purify unsafe crossing remains zero on the selected evaluation;
6. the online model receives no clean segmentation or oracle world state.

Before opening the locked test results, the conformal tolerance is frozen at
coverage `>= 0.92` (`1 - alpha - 0.03`) for overall, clear, and blocked
coverage. To prevent a vacuous predictor from passing by always returning both
labels, locked-test singleton rate must be at least `0.50` and singleton
accuracy at least `0.85`. Passing these offline gates creates only a model
candidate; final online promotion still requires a closed-loop safety run.

Failure is reported honestly. The existing segmentation-proxy path remains the
stable baseline and is not overwritten.
