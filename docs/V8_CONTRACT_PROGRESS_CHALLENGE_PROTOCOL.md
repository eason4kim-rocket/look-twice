# V8 Compound Contract-Progress System Challenge Protocol

Status: **protocol draft only; no seed in 102530–102549 may be opened until
Commit B is public and every placeholder in the preregistration is replaced.**

This is an additive, same-generator compound V8 system challenge. It does not replace,
retune, or reopen the frozen V8 result. It is not a locked test, OOD evidence,
or physical-robot evidence, and every episode must retain
`formal_result_eligible=false`.

## Scientific question

Holding the V8 checkpoint, vision conformal artifact, Go-fusion conformal
artifact, Purify binary, gate rules, Genesis world generator, and kinematic
motion backend fixed, does the opt-in compound system—shared single-capture
dual-ROI perception, physical-root unification, and contract-progress NBV—reduce
physical observation and team-motion burden without reducing direct-route
capability or safety?

The frozen baseline is `purify-active-vision`. The only candidate system uses
`purify-active-contract-progress`, whose evidence-request ranking must identify
itself as `v8-contract-progress-nbv/1`. The candidate may use current,
corridor-scoped Purify GateReceipts, effective Python/Go decisions, public map
geometry, current robot poses, public candidate actions, and visit history. It
must not use a scenario seed, oracle state, future image, clean segmentation,
noise realization, or retry outcome.

For each corridor, the policy derives Go measurement-root debt only from the
latest applicable online Purify Go receipt:
`measurement_root_debt=max(required_roots-actual_roots,0)`. If that debt is
zero but the gate is still an otherwise-repairable deny, the conservative
`repair_step_debt` is one; otherwise it equals the positive measurement-root
debt. Among repairable corridors the policy uses the preregistered deterministic
order: (1) lower `repair_step_debt`,
(2) lower online Go `p_blocked`, then (3) lower public-geometry scout travel
distance, with stable deterministic tie-breaks thereafter. `p_blocked` is an
online receipt value, not oracle occupancy and not a new calibration input.
Malformed, missing, inapplicable, or hard-deny receipts fail closed. Every
chosen candidate side-view ranking entry must retain the receipt-derived finite
`go_p_blocked` value in `[0,1]` and the matching Go receipt SHA-256 for verifier
audit. The verifier resolves that hash against the raw Purify Go receipts and
requires exact corridor and probability agreement. Each decision also carries
a cryptographically recomputed EvidenceRequest receipt. Its request step must
be strictly later than the preceding decision, and the selected Go receipt must
have been evaluated at exactly that then-current step and remain unexpired.

The complete runtime input boundary is explicit: current corridor-scoped online
Go receipts and effective Python/Go decisions; public map geometry and candidate
actions; current carrier/scout poses; visit history; the online-claim-derived
`confirmed_blocked` set; total observations taken and maximum observation
budget; and per-corridor side-observation counts and maximum side-view budget.
No one of these inputs is implicit, and none permits a seed, oracle, future
observation, clean segmentation, noise realization, or retry outcome.

This is explicitly a **compound V8 system intervention**: one initial physical
RGB-D acquisition is processed by one shared frozen seg-v3 backbone forward;
two corridor-scoped ROI proposals are derived from that shared representation;
geometry and vision claims are unified under the same physical capture/device
roots; then the debt → online Go `p_blocked` → travel NBV ordering acts on the
resulting contracts. The checkpoint, vision and Go conformal thresholds,
Purify gate rules, world generator, and kinematic motion backend remain frozen.
Any observed effect is attributed to the overall V8-plus-compound system, not
to the planner alone or the shared-capture path alone.

If no corridor has a trustworthy repairable Go contract, the candidate may
fail closed into the frozen V8 public probe/safe-detour routine. This is an
explicitly recorded policy branch (`delegated_baseline_fail_closed=true`), not
a model, calibration, gate, retry, or direct-admission fallback. It can gather
another authorized side view or take the safe detour, but it cannot manufacture
a direct admit. Any authorized delegated side view remains bound to its
same-corridor online Go receipt probability and hash. A final budget-denied
side-view proposal is retained as a proposal-only
`authorization_denied_noop`; it contributes no executed action, capture, or
motion. A final safe-fallback label is likewise route control rather than a
physical side-view execution and is valid only when the raw episode proves the
subsequent safe detour.

## Population and fixed schedule

- Generator family: `same_generator_as_v8_spatial_dataset_v1`.
- Profile: `independent-noise`.
- Fresh non-locked seeds: the contiguous range 102530–102549, inclusive.
- Worlds: 20. Episodes: 40.
- Seeds execute in strictly ascending order.
- Even seed order: baseline, then candidate.
- Odd seed order: candidate, then baseline.
- Exactly one attempt per seed-policy cell.
- Every child episode/log/error artifact and its parent directory is flushed
  and fsynced before the corresponding attempt row is appended and fsynced,
  and all of that occurs before the next cell. This is local persistence, not
  a claim of live publication.
- No retry, resume, seed substitution, early stopping, threshold change, or
  deletion/replacement of an adverse result.
- Each subprocess has a 300 second timeout. A timeout is killed as a process
  group, retained as the one attempt, and the fixed schedule continues.

The paired order rule counterbalances within-world process-order effects; it
does not randomize or conceal the fixed schedule.

## Source and artifact isolation

Formal execution requires two different resolved source roots:

1. `baseline_root`, containing the exact frozen V8 runtime source closure.
2. `candidate_root`, containing the opt-in candidate integration.

The baseline entrypoint is never imported from the candidate root. Both cells
use the same byte-identical checkpoint, vision calibration, Go calibration,
and Purify binary. The formal prestart binding records both roots, the complete
baseline runtime-closure verification, the candidate source-file path set and
hashes, the runner hash, verifier hash, preregistration hash, artifact hashes,
and the immutable schedule.

The baseline closure is the frozen 30-file manifest (29 Python files plus the
robot asset). Formal preflight rejects every missing, changed, extra,
non-regular, or symlinked path anywhere under baseline `src/**`, including
ignored bytecode, import hooks, `.pth` files, and extensions, and independently
recomputes the path-sorted tree fingerprint. Candidate preflight independently
requires the actual `src/**` filesystem to equal the complete Git-tracked set;
ignored/untracked files, symlinks, and non-regular paths are forbidden. Git
queries run under scrubbed repository/config environments with replacement
objects disabled; clean-status checks also disable repository fsmonitor and
untracked-cache shortcuts. Episode subprocesses
disable user-site imports and bytecode writes. Together with the exact source
closures, this prevents extra project code under either source root and
user-site injection during the run. The separately bound virtual environment,
its installed packages, and native shared libraries remain part of the trusted
runtime stack rather than a claim of a fully content-addressed dependency
closure.

The public two-commit binding is:

- **Commit A:** final candidate source, runner, verifier, protocol, and a
  preregistration containing hash placeholders. No fresh challenge seed is run.
- **Commit B:** only the preregistration is changed to bind the Commit A hash,
  runner hash, verifier hash, and every candidate-source hash; its status becomes
  `PREREGISTERED_BEFORE_ANY_CHALLENGE_EPISODE`. Commit B cannot embed its own
  Git hash without changing that hash. The runner therefore requires a clean
  candidate checkout, proves that Commit A is its direct parent and that the
  A-to-current diff contains only this preregistration, and performs a live
  remote check proving that the exact local Commit B is already a public
  branch head. The configured `origin` must resolve to GitHub; the runner
  converts it to a sanitized HTTPS repository URL and runs `git ls-remote
  --heads` with terminal prompts and credential helpers disabled. It then
  records the repository slug, anonymous-access mode, matching public refs, and
  current Commit B hash in the prestart binding before any seed is opened. A
  credentialed/private remote or stale local remote-tracking ref is not
  sufficient.
- Formal execution may begin only from a clean checkout containing Commit B.
  The runner rejects placeholders in formal mode.

After all 40 attempts, the runner repeats the complete local source, artifact,
Git, Python, and anonymous live-remote validation. It writes
`raw/POSTRUN_BINDING.json` even when that revalidation fails, then still writes
the run manifest so the adverse attempts are not lost. Promotion requires the
postrun immutable snapshot to equal prestart and to follow the final attempt in
both monotonic and wall-clock time.

This avoids an impossible file self-hash while making all executable code
public before the first fresh episode.

## Runtime contract

Every episode is a fresh process with:

- Genesis on AMD ROCm, device `cuda:0`;
- `motion_backend=kinematic`;
- frozen spatial RGB-D checkpoint and preprocessing;
- frozen vision and Go conformal artifacts;
- the real frozen Purify Go binary;
- `repair_required=true`;
- no unrecorded perception, calibration, gate, or direct-admission heuristic
  fallback; and
- raw JSON, stdout, stderr, command, timing, and failure retention.

Before opening the first seed, the GPU must pass both `rocm-smi --showpids` and
a global `/proc/*/fd` scan for live `/dev/kfd` handles. Stale reported PIDs are
retained but allowed only when their `/proc` entries no longer exist. Initial
GPU use must be at most 5% and allocated VRAM at most 2%. The Python invocation
path is preserved (including a virtual-environment symlink), while its resolved
target, target hash, version, and pre/post identity are also bound. Every normal
attempt command must exactly equal the independently reconstructed fixed argv;
only a retained internal-runner error may use an empty argv.

The output root is creation-only, outside both source roots, and has disjoint
baseline and candidate episode/log/error roots. The runner refuses an existing
output path, including an empty one. A dry run validates the design and bindings
but creates no output path and does not initialize Genesis, load a checkpoint,
query ROCm, or execute a seed. The independent verifier asks the frozen Go
binary itself to authenticate each retained Go receipt. A well-formed rejection
or an all-failure run with no receipts remains an honestly reported failed
result rather than crashing report generation. The runner's per-attempt
integrity bit is explicitly provisional: the verifier independently reproduces
that pre-authentication result, then may only downgrade it after frozen-Go
authentication. It can never promote a runner-declared failure.

## Mandatory validity and safety gates

All of the following must pass before the capability endpoints are promotable:

1. All 40 scheduled attempts exist and are structurally valid.
2. Mission success is 40/40.
3. Unsafe crossing, false-clear/contact, fallback, and collision counts are all
   zero across all 40 episodes.
4. Every episode reports the exact frozen checkpoint, vision artifact, Go
   artifact, and Purify binary identities; the checkpoint is loaded, fallback
   is false, live Genesis RGB-D is used, and world alignment passes.
5. Purify is invoked in every episode; every retained Go receipt reports the
   frozen Purify binary and applicable frozen Go calibration.
6. Every repair decision has exact selected/chosen alignment. For candidate
   decisions, `selected` must equal the complete action object of exactly one
   `chosen=true` ranking item, including a terminal proposal-only no-op;
   baseline decisions retain name-level compatibility. `selected=null` has
   zero chosen items. Every candidate decision also rehashes and binds its
   EvidenceRequest receipt to that exact selected action, authorization flag,
   execution status, and decision reference.
7. Every candidate decision carries an exact two-corridor selector audit. Its
   EvidenceRequest current step is strictly later than the preceding decision,
   and every selected Go receipt was evaluated at exactly that then-current
   step and is unexpired. Repairability and every reported fail-closed reason
   are independently reconstructed from raw clauses and online claims.
8. Candidate execution follows one of the following exhaustive branches:

   - If at least one corridor is independently repairable, exactly one native
     `v8-contract-progress-nbv/1` side-view is chosen and authorized. It carries
     a finite same-corridor online `go_p_blocked` in `[0,1]` and the exact raw Go
     receipt hash. A candidate episode may have zero native choices only when
     every applicable decision has a strict raw no-repairable proof.
   - Under that strict all-hard proof, an authorized delegated side-view must
     carry `policy_artifact_id=heuristic-v6/1`,
     `delegating_policy_artifact_id=v8-contract-progress-nbv/1`,
     `delegated_baseline_fail_closed=true`, truthful non-empty hard reasons,
     and its own same-corridor current Go probability and receipt hash.
   - The only budget-denied delegated side-view is a final fourth proposal
     after exactly three authorized side-views under the fixed three-replan
     budget. It retains selected/chosen evidence but has
     `execution_status=authorization_denied_noop`, creates no capture or scout
     motion, and receives no execution credit.
   - A `safe_fallback` may appear only as the final route-control no-op under
     strict all-hard proof. Its Go fields are null, it creates no physical
     side-view execution, and the raw route must prove safe detour with no
     selected direct corridor.
9. Candidate physical execution closes exactly over the authorized decision
   trace: the initial viewpoint is `carrier_initial_front`; every subsequent
   physical viewpoint equals one authorized non-wait/non-fallback action in
   order; replan count equals authorized side-view count; and finite scout
   motion targets equal the authorized side-view targets in order. Terminal
   no-op branches contribute none of these effects.
10. The compound intervention is reconstructed from raw evidence in every
    candidate episode: both initial corridor proposals share one live Genesis
    RGB-D capture/device root and one frozen backbone forward; every later
    vision claim binds to its exact physical RGB-D audit and geometry root;
    viewpoints and raw audits close exactly; synthetic proxies are forbidden.
    The candidate helper and compound metrics must be absent from every
    baseline episode.
11. Candidate full-chain direct count is not below baseline full-chain direct
    count.
12. There is no seed for which baseline is full-chain direct and candidate is
    not full-chain direct.

The zero-fallback gate refers to the retained runtime/perception fallback flags
(`fallback_used` and `vision_fallback_used`). It does not relabel the audited
fail-closed probe/safe-detour branch above as a successful direct policy path.

`full_chain_direct` means mission success, route mode `direct`, a non-empty
selected corridor, and at least one selected-corridor gate receipt with
`python_admitted == purify_go_admitted == effective_admit == true`.

## Preregistered capability gates

All three gates are evaluated over all 20 paired worlds, never only successful
episodes:

1. Mean candidate scout physical path is at least 25% lower than mean baseline
   scout physical path:
   `1 - mean(candidate_scout_m) / mean(baseline_scout_m) >= 0.25`.
2. Mean candidate total team physical path (`scout + carrier`) is at least 10%
   lower than mean baseline total team physical path:
   `1 - mean(candidate_team_m) / mean(baseline_team_m) >= 0.10`.
3. Mean candidate physical capture count is at least 20% lower than mean
   baseline physical capture count:
   `1 - mean(candidate_captures) / mean(baseline_captures) >= 0.20`.

Scout and carrier path lengths are independently recomputed by summing finite,
non-negative `motion_segments[].path_length` values for the corresponding
logical `agent_id`. Team path is scout plus carrier.

Physical captures are **not** proposal count. For each episode they are fixed
as `metrics.observation_count`, which must be a non-negative integer equal to
`len(metrics.viewpoints_sequence)`. A single RGB-D capture may legitimately
produce two corridor proposals while counting as one physical capture.
`vision_proposal_count` is reported separately and cannot satisfy the capture
endpoint.

## Reporting

The independent verifier reports, at minimum:

- all per-seed baseline/candidate rows and paired deltas;
- mean, median, minimum, maximum, and deterministic paired-bootstrap 95%
  intervals for scout, carrier, team, and physical-capture deltas;
- the three preregistered relative reductions;
- baseline/candidate full-chain direct counts, paired discordances, and Wilson
  95% intervals;
- all mandatory and capability gate booleans;
- prestart/postrun immutable source, artifact, Python, Git, and public-remote
  binding, including exact fixed command reconstruction for every attempt; and
- raw attempt, episode, log, error, telemetry, manifest, report, verification,
  and checksum integrity.

The verifier reads raw episode windows and raw ROCm samples rather than trusting
the runner's summary flags. It independently requires the exact schedule order,
non-overlapping attempt windows, prestart-before-first-attempt chronology,
strictly increasing telemetry timestamps, full start/end coverage, and no raw
sampling gap above 5.5 seconds.

The raw path set is exact: undeclared extra files, missing retained files, path
escapes, duplicate attempts, duplicate seed-policy cells, reordered cells, or a
checksum mismatch invalidate the evidence package. A retained empty, truncated,
or non-JSON episode remains its one failed structural row, with its raw hash,
error artifact, and attempt-integrity evidence checked; it must not prevent the
failed REPORT and VERIFICATION artifacts from being produced. The same applies
to an adverse run with no Go receipts. Results remain an additive V8-derived
supplement and must not modify the sealed technical report, sealed submission
package, or original V8 primary result.
