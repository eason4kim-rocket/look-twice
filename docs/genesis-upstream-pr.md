# Archived Genesis upstream draft - not submitted

> Historical V6-era draft for Genesis 1.1.x. It is not part of the V8
> competition claim, has not been filed upstream, and should not be opened as
> written. The current Genesis project and documentation structure have moved
> on, and several recommendations below require a new reproducer, benchmark,
> and maintainer issue before they could become an honest contribution.

**Target repo:** [Genesis-Embodied-AI/Genesis](https://github.com/Genesis-Embodied-AI/Genesis)  
**Suggested path:** `docs/examples/amd_multi_agent_rgbd.md` or `examples/rigid/amd_multi_agent_rgbd.py`  
**Status:** Archived historical proposal; no upstream PR exists.

## PR title

```
docs: AMD ROCm multi-agent RGB-D capture notes (process isolation)
```

## PR body

### Summary

Documents practices that made multi-robot RGB-D capture workable on AMD GPUs with Genesis 1.1.x + ROCm/PyTorch for the Look Twice collaborative evidence-repair evaluation.

### Motivation

Genesis docs cover single-camera RGB-D well, but multi-agent evaluation on AMD often hits:

- multi-context / multi-process camera contention
- non-contiguous render buffers breaking stride-sensitive ops
- confusion between kinematic chassis snap vs dual-URDF physics

### What we document

1. `gs.init(backend=gs.amdgpu)` with PyTorch device `cuda:0`
2. Process-isolated episode workers for matrix runs
3. Chassis snap → `camera.render(rgb=True, depth=True, segmentation=True, force_render=True)` → `np.ascontiguousarray`
4. Claim labeling with `observer_agent_id` / `intended_actor_id` (application-level)

### Non-claims

- Not a dual-URDF full dynamics completeness claim
- Segmentation treated as sim proxy, not a vision model

### Checklist

- [ ] Example runs on ROCm CI or documented as AMD-only
- [ ] No dependency on Look Twice-private packages
- [ ] Minimal self-contained snippet

### Reference implementation note

See `docs/genesis-amd-multi-agent-rgbd.md` in the Look Twice tree for the full note mirrored here.

---

## Minimal example sketch (for upstream)

```python
import numpy as np
import genesis as gs

gs.init(backend=gs.amdgpu, logging_level="warning")
scene = gs.Scene(show_viewer=False)
# add warehouse + chassis + camera ...
scene.build()
# logical multi-agent: move chassis to agent pose, capture, continue
rgb, depth, seg = cam.render(rgb=True, depth=True, segmentation=True, force_render=True)
rgb = np.ascontiguousarray(rgb)
depth = np.ascontiguousarray(depth)
```

## Historical filing sketch - do not run as written

```bash
# from a Genesis fork
gh pr create --title "docs: AMD ROCm multi-agent RGB-D capture notes" \
  --body-file docs/genesis-upstream-pr.md
```

If `gh` auth is unavailable on the contest machine, attach this markdown to the submission package and file from a maintainer workstation.
