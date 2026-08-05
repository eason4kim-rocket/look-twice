# Genesis PR #3184 bounded validation record

This is a post-report, post-package validation note for the focused Genesis
URDF inertial-origin fix published in
[issue #3183](https://github.com/Genesis-Embodied-AI/genesis-world/issues/3183)
and open, non-draft
[PR #3184](https://github.com/Genesis-Embodied-AI/genesis-world/pull/3184).
It is not part of the sealed competition result.

## Exact identity

- PR head: `0fa0f4ae5c83e964282fea1d6ad44aa333ee1850`
- `genesis/utils/urdf.py` SHA256:
  `3c23b78917209c80cf30ca7ccba67af181f9d1efbcd7e9b6478efbd2d9f5f584`
- `tests/rigid/test_asset_loading.py` SHA256:
  `e061e7f29229dcc7c93a1fcab413b41f05a4fdd93eff389143417e7e00cf189e`
- retained raw execution-log SHA256:
  `188c8231612a3a57fc87e0e87ed0d04c55444525aca2b83bc41fc93ef522b3da`

## Bounded serial CPU regression

The run used Python 3.12.3, pytest 9.0.2, Quadrants 1.0.2, serial execution
(`-n 0`), and `--backend cpu`. CUDA and AMDGPU backend discovery and device
visibility were explicitly disabled. A 1,200-second hard timeout was present
and did not trigger.

Selected nodes:

1. `test_depth_first_link_ordering[depth_first_tree_urdf]`
2. `test_urdf_parsing_undefined_inertia[undefined_inertia]`
3. `test_align_mixed_mass_raises`

Result:

```text
collected 3 items
tests/rigid/test_asset_loading.py ...                                    [100%]
3 passed in 56.08s
wrapper wall: 62.099s
exit code: 0
```

The run started at `2026-08-05T12:47:57Z` and ended at
`2026-08-05T12:49:00Z` (63 seconds by epoch timestamps).

## Boundary

This record supports only the three named regression nodes at the exact PR
head. It is not a full-suite result, GPU result, competition score, maintainer
review, merge, acceptance, or upstream-release claim. At the time of this
record, the PR's official workflows were awaiting first-time-fork maintainer
approval and had launched no jobs; that state is not described as a test
failure.

The first runner invocation was retained separately but exited before pytest
because the environment did not provide `/usr/bin/time`. The successful run
used the shell's timing facility. That setup error was not a code-test failure
and did not overwrite the successful record above.
