# Look Twice v4 failure-case record

This file is the required home for negative and unresolved formal results. It
must be updated from archived W7900D JSON; no formal v4 failure case has been
measured yet.

## Reporting rule

Never delete a run because it is unsafe, unresolved, slow, malformed, or fails
a promotion gate. Keep it in `runs.csv` and record:

```text
profile / policy / seed / commit / runtime / motion backend
calibration artifact ID and SHA256
world truth (evaluation-only)
Claims and lineage roots used/discounted
GateReceipt and BeliefGap
repair ranking and selected action
PlanInvalidationReceipt
trajectory, controls, contacts, and evidence artifacts
observed failure and root-cause hypothesis
whether a code fix changed the frozen protocol
```

If a fix changes policy logic, contracts, profiles, calibration, or utility,
rerun the affected calibration/validation process and do not reuse the locked
test as development data.

## Failure categories to audit

| Category | Required evidence | Formal status |
| --- | --- | --- |
| Unsafe crossing | risk entry, truth, gate, trajectory/contact | Pending |
| False abstention/wrong detour | decisive evidence and denied contract clause | Pending |
| Echo accepted as independent | Claim DAG, artifact/capture/device roots | Pending |
| Miscoverage | prediction set, true label, artifact/domain | Pending |
| OOD incorrectly admitted | applicability clause and runtime context | Pending |
| Repair budget exhausted | all rankings, visited actions, observations | Pending |
| Wrong/missed plan invalidation | old/new receipts and triggering Claims | Pending |
| Skid-steer timeout/contact | controls, wheel targets, trajectory, contacts | Pending |
| Sensor artifact failure | raw/corrupted file hashes and exception | Pending |
| Process/protocol failure | NDJSON request ID, error, timeout, stderr tail | Pending |

## Known engineering limitations, not measured failures

- Entity segmentation is a simulated semantic proxy, not a trained model.
- The kinematic Genesis batch backend uses `set_pos()`/`set_quat()` after
  integrating bounded velocity commands.
- Skid-steer W7900D acceptance is pending.
- No real robot or sim-to-real result exists.
- Conformal coverage applies only to the declared simulated ID distribution.
- The public Go core is a contest reference slice, not the private Purify
  product or a certified controller.

## Development-only observations

Local synthetic episodes have exercised Go-gated admission, evidence echo,
repair, and invalidation. They carry `formal_result_eligible=false` and cannot
populate the formal failure table above.

## Final submission checklist for this file

- [ ] Add at least one representative safe resolution and one unresolved or
  failed episode from W7900D artifacts.
- [ ] Link raw JSON and evidence images by relative path.
- [ ] Explain whether failure arose from perception, lineage, calibration,
  planning, motion, protocol, or experimental infrastructure.
- [ ] State whether the final system fixed it or retains it as a limitation.
- [ ] Ensure aggregate counts still include every documented case.
