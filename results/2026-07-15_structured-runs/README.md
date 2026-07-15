# Structured run samples

These three AMD GPU runs verify the versioned JSON result format introduced
in Git commit `e52e7a6`.

| File | Scenario | Noise | Belief | Observations | Path length | Result |
| --- | --- | --- | --- | ---: | ---: | --- |
| `clear-none.json` | clear | none | confirmed_clear | 2 | 4.6400 | success |
| `blocked-none.json` | blocked | none | confirmed_blocked | 2 | 5.1360 | success |
| `blocked-first-flip.json` | blocked | first-flip | confirmed_blocked | 3 | 8.9600 | success |

Each JSON file includes the configuration, environment, evidence, belief
lifecycle, action-gate decisions, state transitions, complete trajectory, and
final metrics. The first-flip run demonstrates conflict-driven movement to the
second inspection viewpoint.

Reproduce on the configured AMD cloud image with:

```bash
/opt/venv/bin/python src/look_twice_v0.py \
  --scenario blocked \
  --noise-profile first-flip \
  --seed 0 \
  --json-output outputs/blocked-first-flip.json
```
