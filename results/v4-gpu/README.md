# Look Twice v4 GPU / W7900D artifacts

This directory holds **representative** AMD W7900D outputs synced from the
contest cloud instance. Full matrices may remain on `/workspace/look-twice/outputs`
on the GPU host until packaged.

## Integrity rules

- Synthetic Mac runs are **never** mixed into formal GPU claims.
- Episodes that used `--allow-smoke-calibration` are integration smoke only.
- Formal claims require a fitted calibration artifact from seeds `30000–30049`
  on ID profiles only, plus Genesis `gs.amdgpu` environment fields.

## Motion demotion

Skid-steer 10×4 viewpoint acceptance failed on 2026-07-15 (14 failures).
Formal experiment matrices use `motion_backend=kinematic`. See
`docs/V4_FAILURE_CASES.md` and the technical report.

## Layout

| Path | Meaning |
| --- | --- |
| `profile-smoke/` | One Genesis episode per stress profile (seed 50000) |
| `*.json` | Additional representative episodes |
| SHA256SUMS | Written when a formal packaging pass completes |
