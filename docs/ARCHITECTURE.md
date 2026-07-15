# Look Twice architecture

## Data flow

```mermaid
flowchart LR
    S["Genesis scene"] --> O["Geometry or rendered RGB sensor"]
    O --> E["Observation evidence"]
    E --> B["Purify RegionBelief"]
    B --> G["Action Gate"]
    G -->|"confirmed_clear"| D["Go directly to goal"]
    G -->|"confirmed_blocked"| T["Take detour"]
    G -->|"uncertain"| R["Move to second viewpoint"]
    R --> O
    G -->|"still uncertain"| F["Safe detour fallback"]
```

The implementation deliberately separates:

- **scenario** — what is actually present in the world;
- **observation** — what one noisy sensing event reports;
- **belief** — what can be concluded from recent evidence;
- **action** — what the reliability gate permits the robot to do.

In `--sensor-mode camera`, the observation comes from a 320×240 Genesis RGB
camera placed at the robot's current inspection viewpoint. A small,
deterministic red-pixel detector produces `clear` or `blocked`; visible pixel
support determines confidence, and the raw frame can be saved as an evidence
artifact. The controller never reads the obstacle entity position in this
mode.

## Belief lifecycle

```mermaid
stateDiagram-v2
    [*] --> unknown
    unknown --> provisional_clear: first clear
    unknown --> provisional_blocked: first blocked
    provisional_clear --> confirmed_clear: consistent clear
    provisional_blocked --> confirmed_blocked: consistent blocked
    provisional_clear --> uncertain: conflict or low confidence
    provisional_blocked --> uncertain: conflict or low confidence
    uncertain --> confirmed_clear: latest evidence agrees on clear
    uncertain --> confirmed_blocked: latest evidence agrees on blocked
```

Only `confirmed_clear` grants direct-passage permission. Confirmed blockage
selects the planned detour. Unresolved uncertainty never becomes a fabricated
blocked belief; the belief remains `uncertain` while the controller selects a
conservative detour.

## Mission state flow

```mermaid
flowchart TD
    A["GO_TO_INSPECTION"] --> B["INSPECT"]
    B -->|"provisional"| B
    B -->|"confirmed_clear"| G["GO_TO_GOAL"]
    B -->|"confirmed_blocked"| D["GO_TO_DETOUR"]
    B -->|"uncertain"| R["GO_TO_SECOND_INSPECTION"]
    R --> B
    B -->|"unresolved at second viewpoint"| D
    D --> G
    G --> F["FINISHED"]
```

## Policy comparison

All three policies receive observations from the same scene and noise model:

| Policy | Rule | Expected trade-off |
| --- | --- | --- |
| Single Shot | Act on the first observation | Lowest cost, highest error risk |
| Majority Vote | Always take three observations | Robust but fixed observation cost |
| Purify | Confirm consistent evidence; reinspect conflicts | Adaptive safety/cost balance |

The batch experiment varies scenario, observation noise, policy, and seed while
recording raw evidence and decisions for every episode.
