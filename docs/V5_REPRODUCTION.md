# Look Twice v5 reproduction

## CPU

```bash
python -m unittest discover -s tests -v
python src/look_twice_v5.py --runtime synthetic --policy purify-active \
  --profile independent-noise --seed 50000 \
  --purify-bin purify_robotics/bin/purify-robotics-core
```

## W7900D Genesis

```bash
export PATH=/opt/venv/bin:$PATH PYTHONPATH=src PYOPENGL_PLATFORM=egl
python src/look_twice_v5.py --runtime genesis --motion-backend kinematic \
  --policy purify-active --profile independent-noise --seed 50000 \
  --allow-smoke-calibration \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/v5-episode.json
```

Skid acceptance: `python scripts/v5_motion_accept.py` (currently failing; demoted).

Archived smoke: `results/v5-gpu/`.
