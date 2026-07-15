# Look Twice

Physical AI project for the AMD AI DevMaster Hackathon.

## Core idea

When a robot cannot determine whether an area is safe, it actively moves
to a better viewpoint, observes again, and then decides whether to proceed
or take a detour.

## Current progress

- Genesis 1.1.2 runs on AMD Radeon PRO W7900D
- AMD backend: `gs.amdgpu`
- GPU physics simulation verified
- Simple object movement from point A to point B verified
- Initial active-perception state machine verified

## Scripts

- `src/hello_genesis_gpu.py` — verifies Genesis on AMD GPU
- `src/hello_genesis_cpu.py` — CPU comparison
- `src/move_a_to_b.py` — moves a simplified robot from A to B
- `src/look_twice_v0.py` — visits an inspection viewpoint before continuing

## Current limitation

The inspection result is currently hard-coded as `clear`.
The next milestone is to support both `clear` and `blocked` outcomes.
