# Look Twice v4 experiment protocol

## Objective

Measure whether lineage-aware, calibrated Action Contracts and active evidence
repair reduce unsafe action without hiding the observation, movement, or
abstention cost.

No v4 formal result is recorded in this document yet. Synthetic CI output is
excluded from every formal table.

## Frozen policies

| Policy | Lineage | Conformal | Active repair |
| --- | :---: | :---: | :---: |
| `naive-majority` | No | No | No |
| `v3-logodds` | No | No | No |
| `conformal-only` | No | Yes | No |
| `lineage-only` | Yes | No | No |
| `purify-passive` | Yes | Yes | No |
| `purify-active` | Yes | Yes | Yes |

## Frozen profiles

1. `independent-noise`
2. `shared-occlusion`
3. `evidence-echo`
4. `time-skew`
5. `pose-calibration-drift`
6. `structured-depth-dropout`
7. `dynamic-change`
8. `ood-severity`

Unknown world state and realised faults exist only in the evaluator. Policies
share the same profile/seed world and absolute-time event; they receive no
future observation or clean segmentation.

## Data isolation

| Split | Profiles | Seeds | Size | Permitted use |
| --- | ---: | --- | ---: | --- |
| Calibration | 7 ID | `30000–30049` | 350 | Fit class quantiles |
| Validation | 7 ID | `40000–40019` | 140 | Integration and frozen promotion checks |
| Locked test | all 8 | `50000–50099` | 800 | Final evaluation only |

`ood-severity` is absent from calibration. Rules, utility weights, contracts,
noise profiles, and sensor versions must freeze before reading locked-test
aggregates.

## Execution matrices

- smoke: 6 policies × 8 profiles × seeds `50000–50001` = 96;
- formal: 6 × 8 × seeds `50000–50019` = 960;
- skid-steer: 3 representative policies × 4 key profiles × 5 locked seeds = 60;
- benchmark: batches 1/8/32/128, 20 warm-ups, 100 timed iterations.

Run order:

1. CPU and Go tests;
2. one Genesis episode for every profile;
3. 96 smoke episodes;
4. freeze/check artifacts and commands;
5. 960 kinematic-Genesis paired episodes;
6. 60 skid-steer episodes;
7. benchmark and videos;
8. deterministic summarisation and hash manifest.

Every episode writes atomically so interruption can resume without replacing a
valid prior result.

## Metrics

Primary safety/task metrics:

- unsafe crossing and collision;
- safe task success;
- wrong detour/false abstention;
- OOD fail-closed rate;
- unresolved/stale/conflict risk entry count.

Evidence/governance metrics:

- Claim count versus distinct measurement/device roots;
- echo rejection;
- contract repair attempted/success;
- plan invalidation expected/correct;
- prediction set, empirical coverage/miscoverage, Wilson score 95% CI;
- Brier score and 10-bin ECE.

Cost/performance metrics:

- observations, replans, path length, and simulation steps;
- simulation, rendering, corruption/evidence kernel, transfer, Go gate, and
  end-to-end latency separately;
- median, p95, and observations/second.

Event-specific rates use event-specific denominators: a run with no expected
plan invalidation does not count as a correct invalidation.

## Promotion gates

- unresolved/stale/conflict/OOD direct risk entries = 0;
- evidence echo adds no independent root or false confidence;
- ID miscoverage ≤ `0.05 + 0.03`, with Wilson interval;
- paired unsafe crossing no worse than v3 baseline;
- Purify Active safe-task success no worse than Purify Passive;
- contract-repair success ≥ 80%;
- every result traces to raw evidence, Claims, receipts, artifact, commit, and
  environment.

A missed gate is reported as a result, not tuned away.

## Ablations

Run after the main system is frozen:

```text
No TTL
No lineage collapse
No conformal calibration
No conflict gate
No active repair
No plan invalidation
```

Each ablation changes only its named capability and uses the same locked paired
scenes.

## Formal-result eligibility

Eligible v4 results require Genesis/AMD environment metadata,
`formal_result_eligible=true`, a non-smoke fitted artifact, frozen test seeds,
and archived raw JSON. `runtime=synthetic-ci`, smoke calibration, missing GPU
metadata, manually edited output, or unpaired seeds are excluded and retained
as development records.

## Current status

Protocol, schemas, metrics, summarizer, policies, and local smoke orchestration
are implemented. Calibration collection, 96/960/60 runs, GPU benchmark, and
formal W7900D result tables are pending.
