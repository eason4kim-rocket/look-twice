# Look Twice — version map (for reviewers)

Each major step lives on its own branch (and usually a tag).  
`main` currently points at the **v2** publish commit; later work is on version branches, not fast-forwarded into `main`.

| Version | Branch | Tag | Tip (summary) |
| --- | --- | --- | --- |
| v1 | *(no long-lived branch; history under early main)* | `v1.0-hackathon` | Initial hackathon demo packaging |
| v2 | `main`, `feature/active-perception-v2` | `v2.0-active-perception` | Active perception results/demo publish |
| v3 | `v3-noisy-active-perception` | `v3.0-noisy-active-perception` | Noisy active perception package |
| v4 | `v4-active-evidence-assurance` | `v4.0-hackathon-final` | Formal 960 + W7900D archive |
| v5 | `v5-embodied-evidence` | `v5.0-hackathon` | Embodied evidence + GPU smoke path |
| v5-learned | `v5-learned-rgbd` | `v5.1-learned-rgbd` | Learned RGB-D gate / navigation archive |
| v6 | `v6-collaborative-evidence-repair` | `v6.0-collaborative-evidence-repair` | Multi-agent repair; full formal/learned/OOD/physics matrices |
| v7 (scaffold) | `v7-vision-evidence-contracts` | `v7.0-vision-scaffold` | Vision-grounded contracts (in progress) |

## How to scan iteration

```bash
git clone https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
git branch -a
git tag -l 'v*'

# Example: open v6 archive status
git switch v6-collaborative-evidence-repair
# see results/v6-final-capability/STATUS.md
```

## Notes

- Per-version experiment status files live under `results/` on that branch.
- Large per-episode GPU JSON dumps are not all in git; matrix `parallel_summary.json` and STATUS files are.
- Official AMD contest submission (fork + PR to `AMD-DEV-CONTEST/Radeon-hackathon-2026-07`) is separate from this repo’s version branches.
