# Demo assets

These short annotated clips were generated on the AMD Radeon PRO W7900D from
Git commit `a62accb`.

| Clip | Behavior |
| --- | --- |
| `clear.mp4` | Two consistent clear observations authorize the direct route |
| `blocked.mp4` | Two consistent blocked observations select the detour |
| `conflict.mp4` | Conflicting evidence triggers movement to the second viewpoint |

Each MP4 has a matching JSON record containing its evidence, belief lifecycle,
Action Gate decisions, state transitions, trajectory, environment, and final
metrics. The overlays are generated with `scripts/annotate_video.py`; the raw
Genesis videos remain in the Mac backup under `outputs/final-demos/`.

`look-twice-demo.mp4` is a roughly 60-second silent submission draft assembled
from the three annotated clips, the formal policy-comparison chart, and AMD
runtime title cards. Rebuild it with `scripts/build_demo_video.sh`.
