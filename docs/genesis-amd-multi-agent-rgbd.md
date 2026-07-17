# Genesis on AMD ROCm: multi-agent RGB-D notes (Look Twice v6)

This note is intended as an upstream-friendly summary of practices that made
multi-robot RGB-D capture workable on AMD GPUs with Genesis 1.1.x + ROCm/PyTorch.

## Environment

- Backend: `gs.amdgpu` via `gs.init(backend=gs.amdgpu)`
- Device string for perception tensors: `cuda:0` (PyTorch ROCm)
- Prefer **process-isolated** episode workers over multi-context Genesis in one process

## Capture pipeline

1. Mount or pose a visualization/sensor camera from the chassis pose each capture.
2. Call `camera.render(rgb=True, depth=True, segmentation=True, force_render=True)`.
3. Immediately convert buffers with `np.ascontiguousarray(...)` before any stride-sensitive ops.
4. Project risk-region ROI with a pinhole model for claim quality metrics.

## Multi-agent pattern used here

- One physical chassis for RGB-D capture.
- Logical poses for **carrier** and **scout**.
- When an agent acts, snap/move the chassis to that agent, capture, then continue.
- Claims are labeled with `observer_agent_id` and `intended_actor_id` (Claim v2).

This is not a claim of full dual-URDF physics completeness; it is a reproducible
RGB-D evidence path for action-gated multi-robot evaluation on AMD hardware.

## Throughput

- Use process-per-episode isolation for matrix runs.
- Keep `OMP_NUM_THREADS` modest per worker when many Genesis processes run.
- Resume matrices by validating existing episode JSON files.

## What not to claim

- That Genesis segmentation is a real vision model input without labeling it as sim proxy.
- That wheel dynamics are “true” when kinematic motion is used.
- That GPU utilization alone implies algorithmic superiority.
