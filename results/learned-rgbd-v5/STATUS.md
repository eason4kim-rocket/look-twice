# Learned RGB-D navigation status

Date: 2026-07-17  
Branch: `v5-learned-rgbd`  
Final episode commit: `f015ed01a1b5f542e44634be8341ea073764a962`

## Decision

- **Learned RGB-D navigation: promoted.**
- **Full v5 mission: not promoted.** The proxy pick action has no independent
  formal calibration and partly uses simulator-oracle occlusion semantics, so
  it remains fail-closed in the formal learned matrix.

## Training and calibration

- 390 paired Genesis worlds produced 1,505 view samples.
- Frozen samples: train 772, validation 154, locked test 386; the remaining
  193 samples fit the learned-sensor conformal thresholds.
- Training ran on ROCm `cuda:0` and stopped after 39 epochs.
- Validation and locked-test balanced accuracy: `1.0`.
- Locked-test Brier score: `0.0011838`.
- Locked-test conformal coverage: `0.99482`; singleton rate: `0.99482`.
- Clean Genesis segmentation was used only as an offline label/hash and was
  never a model input. Online input is RGB, corrupted depth, and depth-validity.

The combined Depth + learned-semantic Go Gate was separately calibrated on
six profiles × seeds `31000–31049` = 300 independent worlds. Each world
contributes its worst true-class prefix across cumulative independent views.
The resulting class quantiles are:

- clear: `0.0113802`
- blocked: `0.4845153`

The earlier `30000–30049` Gate data is development/audit only. It revealed
that accumulating Claims across an exogenous fact change made dynamic-change
accuracy collapse to 12%. Calibration now resets the Claim epoch at an
oracle-labelled exogenous boundary, matching online plan invalidation; the
fresh dynamic-change calibration slice reached 100% accuracy. Oracle values
do not enter runtime Claims or planner features.

## Final closed-loop matrix

`purify-active × 6 profiles × 4 locked seeds = 24` Genesis episodes, eight
isolated workers, Genesis `gs.amdgpu`, PyTorch ROCm `cuda:0`.

| Metric | Result |
| --- | ---: |
| Episode process success | 24 / 24 |
| Formal-result eligible | 24 / 24 |
| Learned Claims mode | 24 / 24 |
| Unsafe crossing | 0 / 24 |
| Navigation success | 24 / 24 |
| Evidence repair success | 2 / 24 |
| Wrong detour | 8 / 24 |
| Full mission / proxy pick | 0 / 24 |
| Calibration-version mismatch discounts | 0 |

The learned system is conservative: it safely detours in many unresolved
cases. The result supports a safety–efficiency claim, not universal superiority
or real-world generalization.

## Important failure retained

The first learned matrix is invalidated. Learned Claims carried a learned
artifact identifier while the Go Gate expected the v4 sensor version, so the
Gate discounted learned semantic evidence. One shared-occlusion episode then
crossed unsafely using Depth alone. The fix assigns Depth and learned semantic
to `look-twice-rgbd-learned-v5/1`, fits a new combined Gate artifact, and the
final matrix has no version-mismatch discounts and no unsafe crossing.

## Reproduction

```bash
PYTHONPATH=src /opt/venv/bin/python src/look_twice_v5.py \
  --runtime genesis \
  --motion-backend kinematic \
  --policy purify-active \
  --profile repair-required \
  --seed 50002 \
  --calibration results/learned-rgbd-v5/artifacts/gate_calibration_artifact.json \
  --learned-rgbd-model results/learned-rgbd-v5/artifacts/model.pt \
  --learned-rgbd-calibration results/learned-rgbd-v5/artifacts/learned_conformal_artifact.json \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/learned-rgbd-reproduction.json
```

## Boundaries

- Genesis simulation and kinematic motion, not a real robot or stable
  skid-steer claim.
- Small CNN and simulated distribution; perfect classification metrics do not
  imply real-world RGB-D generalization.
- Entity segmentation remains offline oracle labelling only.
- Final learned matrix has 24 episodes; broader comparative baselines and video
  presentation remain future competition-delivery work.
- Proxy manipulation is explicitly excluded from learned navigation promotion.

