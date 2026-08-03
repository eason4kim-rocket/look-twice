# V8 Competition Evidence Boundary

This document defines what may and may not appear as a Look Twice V8
competition claim. It is intended to prevent development, recovery, research,
and locked-test results from being blended together.

## Primary competition evidence

### Frozen candidate

- Candidate: `v8-frozen`
- Runtime tag: `V8_RUNTIME_FROZEN`
- Vision checkpoint SHA256:
  `7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783`
- Vision conformal identity:
  `ca4a7203eeeedbc0a155955237ffb884f7684a4431e894855f847ee69c5eed1f`
- Go fusion conformal identity:
  `d72439827186d744de9a97306ebe1b1e15515b3cefaaa36727d53ac1ed402f97`
- Purify binary SHA256:
  `31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00`

The imported file boundary is recorded in
`release/V8_FROZEN_IMPORT_MANIFEST.json`. The verifier recalculates every
guarded file hash.

### One-shot locked evaluation

The authoritative report is
`release/v8-frozen/results/locked_test_v8_once/LOCKED_TEST_REPORT.json`.

- Report file SHA256:
  `5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb`
- Open-seal SHA256:
  `7bfe13d0d7e117f76286cb094711322b810dc44d40ddbd149bf1304713baba14`
- Permanent: true
- No retune: true
- No refit: true
- No vision retrain: true
- Errors: none

These numbers may be used in the README, report, website, video, and PR body.

### Submission-time derivation

`release/v8-derived/V8_TASK_UTILITY_DERIVATION.json` reads only the permanent
locked report and the two guarded seed-105400 replay episodes. It reruns no V8
episode, does not reopen the locked split, and changes no model, calibration,
contract, or threshold. Its SHA256 is
`f85f6d647ea49f9bc148cf9fad6c38a34050cd8e9f8f690522b965c5ff23730b`.

Allowed locked derivations include:

- active 11/12 direct versus passive 0/12 direct;
- paired direct-route gain of 91.7 percentage points;
- 12/12 mission completion for each policy;
- zero unsafe crossings and fallbacks across 24 policy runs;
- 24/24 Python/Go decision agreement;
- 3,001/3,200 decisive predictions (93.78%), without relabeling the 199
  non-decisive samples as errors or forced classifications.

The exact paired test is descriptive only for the fixed seed suite. It must not
be generalized to real robots or an unspecified world population.

## Supporting evidence

The development and confirmatory smokes establish runtime wiring before the
locked open:

- Development smoke, seeds 105300-105311: 10/12 active direct chains.
- Confirmatory smoke, seeds 105400-105411: 9/12 active direct chains.
- Both smokes: 12/12 passive deny, 12/12 passive detour, zero unsafe, zero
  fallback.

They may be described as pre-locked checks, not locked results.

## Public replay status

The website uses the confirmatory seed 105400 active and passive episodes. The
replay is a deterministic presentation of recorded AMD GPU evidence and links
back to each source episode SHA.

It must be described as:

- recorded Genesis plus AMD GPU evidence;
- a non-locked confirmatory example;
- simulation only;
- replayable without a live GPU.

It must not be described as a new benchmark run, a locked-test episode, a live
cloud execution, or a real-robot recording.

Seed 105400 may also support the following explicitly non-locked cost ledger:
loaded-carrier travel 4.915 m active versus 6.404 m passive (-23.24%), scout
travel 3.046 m active, and total robot travel 7.961 m active versus 6.404 m
passive (+24.32%). This supports motion-burden shifting, not lower total
distance, latency, energy use, or locked-population path efficiency.

## Later research excluded from V8 claims

The following work remains scientifically useful but is not promoted into the
V8 competition result:

- V9 challenger experiments;
- Integrity Shield Research R1, whose one-shot calibration failed;
- Integrity Shield Research R2, whose protocol is explicitly
  `research_only` and `competition_promotion_forbidden`, and whose one-shot
  calibration failed;
- any shortcut-only pass that lacks its required terminal calibration pass;
- any failed or invalid implementation report.

The R1 recovery source result of 150/150 worlds, zero failed jobs, and one
recaptured seed establishes data completeness only. It does not change the R1
terminal calibration decision and does not alter V8.

Failed reports remain preserved. They are not overwritten, relabeled, or
silently omitted from the research archive.

## Honest limitations

- Simulation only; no real-robot or sim-to-real result.
- The public replay uses a kinematic Genesis motion backend.
- The public replay episode carries `formal_result_eligible=false`; it is a
  presentation artifact, not the locked aggregate.
- The locked result is an internal one-shot simulated evaluation, not a safety
  certification.
- The 159 MB frozen checkpoint is identified by SHA and distributed as a
  GitHub release asset because it exceeds GitHub's 100 MB file limit.
- No external upstream contribution is claimed.

## Claim approval rule

A number is submission-ready only when it has:

1. a named source file;
2. a stable SHA or frozen identity;
3. a declared split and population;
4. an honest label such as locked, confirmatory, replay, or research;
5. no conflict with this boundary.
