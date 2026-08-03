# V8 frozen challenge protocol

## Purpose and evidence boundary

This is an additive challenge of the already frozen V8 runtime. It is not a
new model-selection, calibration, or tuning stage. The challenge uses seeds
`102500-102529`, a 30-world subset of the previously untouched reserved range
`102500-102699`. That range comes from the same generator family as the prior
V8 data. A result here must not be called OOD evidence or a population-level
generalization result.

Each world is executed once with each frozen policy, producing 30 pairs and 60
raw episodes. The declared scope is the complete Look Twice
perception -> evidence -> Python/Go gate -> planning pipeline with live Genesis
RGB-D on AMD ROCm. Robot motion uses the declared **kinematic** backend. This is
not rigid-body contact validation and not a physical-robot test.

The carrier and scout are separate **logical roles** with distinct role poses,
viewpoints, and capture roots, realized on one shared Genesis chassis. They are
not two physical devices and are not simultaneous dual-body dynamics. Any path
comparison is therefore labeled logical-role kinematic burden.

The machine-readable source of truth is
`release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json`.

## Binding sequence before execution

The following sequence is mandatory:

1. Finalize `scripts/run_v8_frozen_challenge.py` without inspecting any result
   from seeds `102500-102529`.
2. Compute the runner's SHA-256 and replace the preregistration's explicit
   `TO_BE_BOUND_AFTER_RUNNER_FINALIZATION` value. Also finalize this independent
   validator, compute its SHA-256, and replace
   `TO_BE_BOUND_AFTER_VALIDATOR_FINALIZATION`. No challenge episode may run
   while either placeholder remains.
3. Publish Commit A containing the finalized runner, validator, protocol, and
   preregistration with both executable SHAs bound while
   `public_binding.runner_protocol_commit` is still the explicit placeholder.
4. Create Commit B by changing only that field to Commit A's 40-hex hash, then
   publish Commit B. Commit B is the final public preregistration commit.
5. Compute the SHA-256 of the Commit-B preregistration bytes. Before execution,
   pass Commit B to the runner; `RUN_MANIFEST.json` records the byte SHA,
   `runner_protocol_commit` = Commit A, and `preregistration_public_commit` =
   Commit B. It also records the frozen validator SHA. The two commit hashes
   must be valid and different. This two-commit construction resolves the
   unavoidable self-reference boundary.
6. The runner preflight re-hashes all 13 `critical_source_files` from the V8
   identity freeze manifest. It proceeds only when every digest matches and
   records every expected and observed digest, zero mismatches, and the frozen
   source-tree fingerprint
   `983d7d373a3eedc6f6204e91d2d63b95a7e563506add24d37ee5a30c95aa71a9`.
7. After the challenge subprocess starts, neither the runner, preregistration,
   runtime source, checkpoint, conformal artifacts, Go binary, seeds, order,
   thresholds, nor result schema may change.

The exact frozen identities are:

| Component | SHA-256 |
|---|---|
| vision checkpoint | `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783` |
| vision conformal artifact identity | `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f` |
| Go conformal artifact identity | `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97` |
| Purify Go binary | `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00` |

### Additive runtime-source packaging repair

An import canary found that the earlier minimized frozen source copy omitted
transitive runtime dependencies such as `v6_scenario`. This was a packaging
defect, not a model or policy change. A second canary found the locally
referenced skid-steer URDF was also absent. The additive runtime-dependency
manifest now binds 29 Python files plus that one static asset:

- manifest file SHA-256:
  `018f064f0361e59371e6694d7909da8639960f41f2ef158687c8e65e24d45c2f`;
- runtime-dependency-tree fingerprint:
  `abc1b6810aed6dc19a127069b9b5d5f044def24f35c9a13602f7f5096742b1be`;
- exact file count: 30 (29 Python files and one required URDF).

The nine source files already present in the earlier frozen package remain
byte-identical. The repair adds missing dependencies only: no checkpoint,
model, conformal calibration, threshold, policy, or runtime-logic byte changes.
Runner preflight must verify the exact file set and record this identity in both
the prestart binding and final run manifest.

## Fixed execution plan

Seeds run strictly in ascending order from `102500` through `102529`. Policy
order is balanced deterministically before seeing outcomes:

- even seed: `purify-passive`, then `purify-active-vision`;
- odd seed: `purify-active-vision`, then `purify-passive`.

There is exactly one attempt per seed-policy cell. Retries, seed substitution,
early stopping, and outcome-dependent reordering are prohibited. A poor,
failed, or crashed attempt remains the attempt. The run continues to later
cells when technically possible. If the challenge cannot continue, all partial
artifacts remain preserved and the final validation is incomplete/failed; no
replacement run may be presented under this preregistration.

Each episode subprocess has a fixed 300-second timeout. On timeout the runner
signals the entire process group with `SIGTERM`, waits 10 seconds, then sends
`SIGKILL` if anything remains. The timeout, logs, and partial/error artifacts
are preserved; collection continues to the next fixed cell and never retries.
Every subprocess prepends `/opt/venv/bin` to `PATH` and fixes
`MIOPEN_FIND_MODE=FAST`.

The raw filenames are fixed:

```text
episodes/active__independent-noise__<seed>.json
episodes/passive__independent-noise__<seed>.json
```

All 60 expected files, good or bad, are required for a complete report.

## Endpoints fixed before execution

The primary endpoint is the paired difference in **full-chain direct** rates:

```text
active full-chain direct rate - passive full-chain direct rate
```

An episode is full-chain direct only when all five conditions hold:

1. the mission succeeds (mission, carrier-goal, payload-delivery, deadline, and
   outcome fields agree);
2. `metrics.route_mode == "direct"`;
3. `metrics.used_detour == false`;
4. `metrics.selected_corridor` is a non-empty string; and
5. at least one comparable gate receipt records
   `python_admitted == purify_go_admitted == effective_admit == true`,
   `action == "cross_corridor"`, and a `corridor_id` exactly equal to
   `metrics.selected_corridor`.

This matches the earlier locked-test `active_full_chain_direct` meaning and
prevents route labeling or an admission for a different corridor from
satisfying the primary endpoint. Route-only
direct remains a descriptive secondary endpoint. The report gives a two-sided
95% Wilson score interval for each policy rate and a two-sided exact McNemar
p-value over the 30 paired outcomes. There is no preregistered success cutoff,
promotion gate, or minimum effect. The observed value is reported as-is.

Secondary endpoints are descriptive:

- mission success;
- unsafe episode (unsafe crossing, collision, admit-then-contact, or
  clear-admitted collision);
- any fallback;
- Python/Go admission agreement across every gate receipt;
- initial gate denial;
- repair attempted;
- Purify invocation;
- exact episode-environment contract validity;
- route-only direct, kept descriptive and never substituted for the primary
  full-chain event;
- the full-pipeline denominator: all 60 episodes, Genesis live RGB-D,
  frozen-checkpoint-loaded, Purify Go invocation/receipt, and world-alignment
  counts, plus raw RGB-D observation and vision-proposal totals/means and the
  total Purify invocation count;
- logical-role kinematic operational burden derived only by summing
  `motion_segments[].path_length` by `agent_id`.

The operational-burden table reports active/passive loaded-carrier mean and
median path length and their 30 paired active-minus-passive deltas, active scout
mean/median path length, and active/passive total-team mean/median plus paired
deltas. These are same-generator **logical-role kinematic motion-burden**
measurements only. Distinct carrier/scout capture roots and viewpoints do not
imply two physical devices or simultaneous dual-body dynamics. They do not
estimate energy, throughput, wall-clock latency, or a physical robot's duty
cycle.

No secondary endpoint is promoted to primary after the run, and no
multiplicity-adjusted confirmatory claim is made from them.

## Full-wall ROCm telemetry

`ROCM_TELEMETRY.json` samples at the fixed 2.0-second interval and covers the
entire challenge subprocess wall, not only
model forwards. Sampling starts and produces a sample before or at subprocess
start, remains continuous, and produces a sample after or at subprocess end.
The artifact records monotonic sampler/subprocess bounds, every sample's
monotonic timestamp, the configured interval, preflight state, sampler errors,
and the subprocess exit code.

Validation requires:

- no other KFD process at preflight and a zero challenge-subprocess exit code;
- sampler start <= subprocess start < subprocess end <= sampler end;
- first sample <= subprocess start and last sample >= subprocess end;
- strictly increasing timestamps and no gap greater than
  5.5 seconds (the allowance includes the `rocm-smi` command's five-second
  timeout);
- zero sampler errors and an interval no greater than five seconds.

The telemetry supports an AMD/ROCm full-pipeline execution claim within the
kinematic scope. It does not turn the run into rigid-body or physical-robot
evidence.

The report recomputes a `full_wall_rocm_telemetry` section directly from every
sample, including 0% idle samples. It reports the measured challenge wall,
sample count and timestamp range, GPU-use mean/median/nearest-rank p95/min/max,
VRAM mean/median/p95/max, package-power mean/median/p95/min/max, and the sample
rate at or above the preregistered 1% GPU-busy threshold.

`RUN_MANIFEST.json:execution.attempts` also records all 60 episode subprocesses
in fixed order with seed, policy, monotonic start/end, positive wall seconds,
and exit code. The report recomputes active, passive, and all-attempt
mean/median/p95/min/max wall summaries. Each duration covers the complete
Python + Genesis + checkpoint + episode subprocess wall; it must not be called
control-loop latency.

## Independent validation and publication

The output directory contains:

```text
RUN_MANIFEST.json
ROCM_TELEMETRY.json
CHALLENGE_REPORT.json
SHA256SUMS
episodes/  # exactly 60 JSON files
raw/PRESTART_BINDING.json
logs/ and errors/  # when emitted
```

`SHA256SUMS` binds **every regular file recursively under the results
directory except itself**. The fixed minimum is the 60 raw episodes, the three
top-level JSON artifacts, and `raw/PRESTART_BINDING.json`; every emitted raw
preflight record, stdout/stderr log, and preserved error is bound as well. The
validator requires exact equality between the checksum path set and the actual
regular-file path set, then verifies every digest.

`scripts/verify_v8_frozen_challenge.py` independently checks the
preregistration and runner digests, the 13-file source preflight, all expected
filenames, seeds, policies, frozen identities, environment, raw flags,
Python/Go receipts, telemetry coverage, and checksums. It then recomputes the
complete endpoint table from raw episodes and requires exact agreement with
`CHALLENGE_REPORT.json`.

Run it from the repository root after copying the challenge output into place:

```bash
python scripts/verify_v8_frozen_challenge.py \
  --results-dir /path/to/v8-frozen-challenge-102500-102529 \
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \
  --output /path/to/v8-frozen-challenge-102500-102529.VERIFICATION.json
```

The validator does not repair, rerun, select, or delete outcomes. A validation
failure is published as a failure or kept as an explicitly incomplete run; it
is never overwritten by a more favorable attempt.

The result directory is immutable after `SHA256SUMS` is written. Validator
output must be a sibling or otherwise outside that directory; the CLI rejects
an in-directory `--output`. Do not open or copy the package in a way that adds
`.DS_Store`, editor metadata, or any other unchecksummed file before validation.
