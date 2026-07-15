# Environment and reproducibility

## Tested cloud runtime

```text
GPU:       AMD Radeon PRO W7900D
Backend:   gs.amdgpu
ROCm:      7.2
PyTorch:   2.9.1+rocm7.2.0
Genesis:   1.1.2 (genesis-world)
Python:    3.12
Interpreter: /opt/venv/bin/python
```

The base image may expose `/usr/bin/python`, but that interpreter does not
contain Genesis. All GPU commands must use `/opt/venv/bin/python`.

## Persistence model

The Radeon cloud instance is treated as ephemeral compute:

- GitHub is the permanent source-code and small-result store.
- The Mac clone is the working backup and large-artifact destination.
- Important JSON/CSV/PNG results are downloaded immediately after experiments.
- Raw videos and large experiment directories are downloaded before the GPU
  instance is stopped.

## Reproduction metadata

Every JSON run records:

- Git commit;
- scenario, policy, seed, noise profile, and noise rate;
- AMD GPU and software versions;
- every observation and confidence;
- belief lifecycle and action-gate decisions;
- mission state transitions and trajectory;
- path length, observation count, simulation steps, and safety metrics.

Schema v2 additionally records RGB-D evidence support, target visibility,
occlusion, depth support, ROCm perception time, tensor device, Next-Best-View
rankings, dynamic events, stale counts, replans, and risk-gate entries.

The Genesis physics backend and PyTorch perception kernels use the AMD GPU.
Camera rasterization is a graphics-rendering path, while state-machine logic,
JSON, and experiment orchestration remain on CPU. The project does not claim
that every operation runs on ROCm.
