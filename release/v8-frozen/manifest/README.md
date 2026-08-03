# V8 Frozen Evidence Manifest

The V8 runtime was copied into this evidence directory before the one-shot
locked evaluation. Hostnames, local paths, and transfer-only records are not
part of the public submission surface.

## Core identities

| Asset | SHA256 |
| --- | --- |
| Vision checkpoint | `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783` |
| Vision conformal artifact | `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f` |
| Go-fusion conformal artifact | `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97` |
| Purify Linux binary | `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00` |

## Public evidence policy

- The authoritative locked result is `LOCKED_RESULT.md` plus the immutable
  JSON report referenced there.
- Recompute identities with `python3 scripts/verify_frozen_foundation.py`.
- Do not retune thresholds, refit calibration, retrain vision, or overwrite the
  archived one-shot result.
- Absolute paths embedded in immutable source artifacts are historical
  provenance strings; the judge-facing replay data is separately sanitized.
