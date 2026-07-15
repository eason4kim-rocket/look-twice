# Look Twice v4: Active Evidence Assurance

## Frozen positioning

Look Twice v4 is a Purify-powered, lineage-aware action qualification and
active evidence repair system for Physical AI. It is not a new navigation
algorithm and it does not claim to be a production robot safety certificate.

The contest repository contains only a standalone Purify Robotics Reference
Core, public robotics evidence contracts, the Genesis demonstration, and its
reproducible benchmark. It contains no code or runtime dependency from the
private Purify product repository.

## Closed loop

```text
Depth / semantic / map claims
-> lineage-aware root fusion
-> class-conditional conformal prediction set
-> action contract and GateReceipt
-> BeliefGap-driven physical observation
-> revised world fact and PlanInvalidationReceipt
-> cross, detour, or fail closed
```

## Safety boundary

Only a fresh singleton `{clear}` prediction set with two distinct physical
measurement roots, acceptable modality skew, matching scope, valid calibration,
and no unresolved conflict may qualify `cross_region`. All other outcomes deny
the high-risk action. A collision-checked detour remains an explicitly labelled
safe fallback and never masquerades as a confirmed blocked fact.

Conformal results are reported only for the simulated in-distribution test
population covered by the versioned calibration artifact. OOD or incompatible
sensor configurations fail closed and carry no statistical-coverage claim.
