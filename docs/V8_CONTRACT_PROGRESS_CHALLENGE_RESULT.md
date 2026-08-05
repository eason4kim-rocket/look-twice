# V8 Compound Contract-Progress Challenge Result

Status: **independently verified `promotion_pass=true`**

This is an additive result for the frozen V8 system. It does not replace the
permanent locked result or the preregistered 30-world active-versus-passive
primary endpoint.

## Public-before-run binding

- Commit A: [`6c7b46dc3ac5044c7ed0c422fc30dee1d5b1ba1e`](https://github.com/eason4kim-rocket/look-twice/commit/6c7b46dc3ac5044c7ed0c422fc30dee1d5b1ba1e)
- Commit B: [`427f2f729ce653df91a20db56c9fdbd16911a014`](https://github.com/eason4kim-rocket/look-twice/commit/427f2f729ce653df91a20db56c9fdbd16911a014)
- Population: seeds `102530–102549`, 20 worlds, 40 paired policy cells
- Attempts: one per seed-policy cell, fixed order, no retry, resume,
  substitution, early stopping, threshold change, or retuning

Commit A fixed the candidate source, shared frozen-model inference path,
contract-progress selector, runner, verifier, protocol, and preregistration
placeholders. Commit B changed only the preregistration file to bind those
identities. The formal runner verified the exact public remote head before the
first episode and repeated the immutable binding after the last episode.

## Preregistered result

| Endpoint | Frozen V8 baseline | Compound candidate | Paired result |
| --- | ---: | ---: | ---: |
| Full-chain direct | 20 / 20 | 20 / 20 | no direct regression |
| Mean scout path | 2.9229 m | 1.7462 m | **−40.2563%** |
| Mean team path | 7.8326 m | 6.6553 m | **−15.0306%** |
| Physical captures | 69 total | 50 total | **−27.5362%** |

Deterministic paired-bootstrap 95% intervals were:

- scout relative reduction: **36.0505–45.0271%**;
- team relative reduction: **12.2563–17.6227%**;
- physical-capture relative reduction: **15.6250–37.8378%**.

All three preregistered capability gates passed. The improvement was also
directionally consistent: candidate-minus-baseline scout and team path deltas
were negative in **20/20** paired worlds. Physical captures fell from 69 to 50;
one shared initial RGB-D capture legitimately produced two corridor-scoped ROI
proposals while retaining one physical capture/device root.

## Safety, execution, and audit closure

- mission success: **40/40**;
- unsafe crossing, false clear, fallback, and collision: **0**;
- full-chain direct: **20/20 baseline and 20/20 candidate**;
- candidate native contract-progress decisions: **30**;
- delegated candidate decisions: **0**;
- exact path set, checksums, pre/post source bindings, public-remote binding,
  attempt reconstruction, frozen-Go authentication, and telemetry: **valid**;
- telemetry: 554 two-second samples, 2.2324-second maximum observed gap, full
  challenge-window coverage, and no sampler errors.

The result is attributed to the complete additive compound intervention:

```text
one initial physical RGB-D capture
-> one shared frozen seg-v3 backbone forward
-> two corridor-scoped ROI proposals
-> geometry/vision physical-root unification
-> contract debt -> online Go p_blocked -> travel NBV
```

It is not evidence for new model weights, a new conformal calibration, a gate
or threshold change, or a single-component causal effect.

## Evidence boundary

Every record retains `formal_result_eligible=false`. The population is
same-generator, non-locked, and not OOD. Execution used Genesis on AMD ROCm
with the kinematic motion backend. It is not a physical-robot, sim-to-real,
energy, throughput, control-loop latency, or safety-certification result.

The compact entry point is
[`RESULT_README.md`](../release/v8-derived/contract_progress_challenge_102530_102549/RESULT_README.md).
The complete local evidence remains under
`release/v8-derived/contract_progress_challenge_102530_102549/formal_run/`;
the official submission package carries a compact summary and cryptographic
index rather than duplicating the roughly 15 MB raw episode tree.
