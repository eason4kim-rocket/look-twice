# Look Twice v2 design

Look Twice v2 demonstrates a temporal active-perception loop rather than a
static navigation classifier.

```text
Genesis RGB-D + entity segmentation
→ contiguous camera arrays
→ ROCm PyTorch tensors on cuda:0
→ clear / blocked / inconclusive evidence
→ RegionBelief with evidence epochs
→ Next-Best-View or Action Gate
→ passage, detour, or reinspection
```

The segmentation image contains Genesis compact segmentation indices. These
are resolved through `scene.visualizer.segmentation_idx_dict`; they are not the
same values as `Entity.idx`. The detector never depends on object color.

Clear requires at least 65% of the calibrated target patch to be visible.
Obstacle support of at least 30 pixels produces blocked evidence. Anything
else is inconclusive and cannot authorize passage.

Confirmed evidence expires after 60 simulation steps by default. Expiry starts
a new evidence epoch, so old and fresh observations cannot be combined to
manufacture confirmation.

The robot remains a fixed box moved with `set_pos()`. This isolates the project
claim: evidence quality and temporal validity change embodied navigation
behavior. Wheel dynamics are deliberately outside the hackathon version.
