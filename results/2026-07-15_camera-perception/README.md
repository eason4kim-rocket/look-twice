# Rendered-camera perception validation

This result set validates the harder perception path added in commit
`6432093a5ce54eeda936f259dc70056f87c6df2d`. In `camera` mode the controller
does not read the blocking entity's coordinates. A Genesis camera renders the
occluded region from the current inspection viewpoint, and visible red pixels
produce the observation result and confidence supplied to `RegionBelief`.

## Validation results

| Scenario | Noise | Final belief | Route | Safe |
| --- | --- | --- | --- | --- |
| clear | none | confirmed_clear | left → goal | yes |
| blocked | none | confirmed_blocked | left → detour → goal | yes |
| clear | first-flip | confirmed_clear | left → right → goal | yes |
| blocked | first-flip | confirmed_blocked | left → right → detour → goal | yes |
| blocked | alternating | uncertain | left → right → detour → goal | yes |

The `blocked + first-flip` run is the key active-perception case. Its first
two reports conflict, so the robot moves to the second viewpoint. The third
camera frame provides a new `blocked` observation with confidence `0.905`,
which confirms blockage and opens only the detour action.

The alternating case deliberately remains unresolved. The Action Gate does
not fabricate a blocked belief; it keeps `uncertain` and chooses the safe
fallback route.

## Reproduce

Run on the documented AMD/Genesis environment:

```bash
/opt/venv/bin/python src/look_twice_v0.py \
  --scenario blocked \
  --policy purify \
  --sensor-mode camera \
  --noise-profile first-flip \
  --seed 0 \
  --evidence-dir outputs/camera-formal/blocked-first-flip/evidence \
  --json-output outputs/camera-formal/blocked-first-flip/result.json
```

Each case directory contains the raw rendered PNG evidence, terminal log, and
structured result JSON. All five JSON files record the same source commit and
the AMD Radeon PRO W7900D / ROCm / Genesis environment.

## What the images prove

The left and right evidence frames are visibly different. The central gray
occluder covers different parts of the red obstacle in each frame, so active
movement changes the visual evidence available to the decision system.

Current limitation: obstacle recognition is a deterministic color rule, not a
learned detector. This keeps the perception-to-belief-to-action chain easy to
audit while proving that decisions can originate from rendered sensor data.
