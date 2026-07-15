# Look Twice v3 dynamic-change demo

This reproducible demo was generated on the AMD Radeon PRO W7900D from source
commit `d6d487731eec601a082b8f9c5027a5ad5f8deab1`.

```text
initial noisy observations -> confirmed_clear
dynamic obstacle appears -> old evidence becomes stale
Action Gate denies route commitment
Learned NBV selects new views
new RGB-D evidence -> confirmed_blocked
Action Gate allows safe detour -> goal
```

The episode uses profile `dynamic-change`, policy `purify-learned`, seed
`20000`, PyTorch ROCm device `cuda:0`, and the promoted model from
`results/2026-07-15_v3-learned/nbv-model.pt`.

## Files

- `look-twice-v3-demo.mp4` — annotated 13.8-second closed-loop demo;
- `raw.mp4` — original Genesis top-down recording;
- `evidence-before.png` — raw/corrupted RGB-D-segmentation before the event;
- `evidence-after.png` — raw/corrupted evidence after obstacle appearance;
- `trajectory.png` — route, scene geometry, viewpoints, probability and entropy;
- `result.json` — complete schema-v3 evidence, belief and action audit trail;
- `evidence/` — all raw and corrupted sensor frames;
- `SHA256SUMS` — hashes for the five primary demo artifacts.

## Reproduce

```bash
/opt/venv/bin/python src/look_twice_v3.py \
  --profile dynamic-change \
  --policy purify-learned \
  --seed 20000 \
  --learned-model results/2026-07-15_v3-learned/nbv-model.pt \
  --device cuda:0 \
  --video-stride 2 \
  --video-output outputs/v3-demo/raw.mp4 \
  --evidence-dir outputs/v3-demo/evidence \
  --json-output outputs/v3-demo/result.json

/opt/venv/bin/python scripts/annotate_v3_video.py \
  --video outputs/v3-demo/raw.mp4 \
  --result outputs/v3-demo/result.json \
  --video-stride 2 \
  --output outputs/v3-demo/look-twice-v3-demo.mp4
```
