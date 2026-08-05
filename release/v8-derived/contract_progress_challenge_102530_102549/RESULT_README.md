# Contract-Progress Challenge Evidence

Independent verification reports `promotion_pass=true` for the publicly
preregistered 20-world, 40-cell paired challenge on seeds `102530–102549`.

## Result at a glance

| Check | Result |
| --- | ---: |
| Mission success | 40 / 40 |
| Full-chain direct | baseline 20 / 20; candidate 20 / 20 |
| Scout path reduction | 40.2563% (bootstrap 95%: 36.0505–45.0271%) |
| Team path reduction | 15.0306% (bootstrap 95%: 12.2563–17.6227%) |
| Physical-capture reduction | 27.5362% (bootstrap 95%: 15.6250–37.8378%) |
| Physical captures | baseline 69; candidate 50 |
| Negative scout/team paired deltas | 20 / 20; 20 / 20 |
| Unsafe / false clear / fallback / collision | 0 / 0 / 0 / 0 |
| Candidate native / delegated decisions | 30 / 0 |

Public source binding: Commit A
`6c7b46dc3ac5044c7ed0c422fc30dee1d5b1ba1e`; Commit B
`427f2f729ce653df91a20db56c9fdbd16911a014`.

## Evidence map

- `PREREGISTRATION.json`: public-before-run design and immutable identities.
- `formal_run/REPORT.json`: per-seed rows, burden statistics, bootstrap
  intervals, mandatory gates, capability gates, and promotion decision.
- `formal_run/VERIFICATION.json`: independent structural, checksum, frozen-Go,
  telemetry, and pre/post binding verification.
- `formal_run/ROCM_TELEMETRY.json`: compact full-window ROCm summary.
- `formal_run/RUN_MANIFEST.json`: all 40 fixed attempts and source/runtime
  bindings.
- `formal_run/SHA256SUMS`: exact formal output path-set checksum index.
- `EVIDENCE_INDEX.json`: compact artifact identities for submission handoff.

Two report digests intentionally describe different byte representations. The
`REPORT.json` file-byte SHA256 recorded by `SHA256SUMS` and `EVIDENCE_INDEX` is
`8dc2d5026f697312bd39ddf6be7a65aa3ee08ac0e2799d0ca24cf4348c439a44`;
`VERIFICATION.json.report_sha256` is the verifier's canonical-JSON digest of
the same parsed report object,
`ac498eaef1e6013acfb761f009478ce387e6b76ab08318f9a6a18ca22d4dd5cd`.
They are not expected to match byte-for-byte.

The `formal_run/raw/`, baseline, and candidate episode trees are intentionally
not duplicated into the official submission directory. The compact package
points back here by path and SHA256.

## Scope

This is additive compound-system evidence: frozen shared seg-v3 inference,
physical-root unification, and contract-progress NBV are evaluated together.
It is not a new-weight or single-component causal claim and does not overwrite
the frozen primary result. All records retain `formal_result_eligible=false`.
The run is same-generator, non-locked, not OOD, kinematic simulation on AMD
ROCm—not physical-robot or sim-to-real validation.
