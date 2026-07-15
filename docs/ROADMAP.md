# Look Twice competition roadmap

## Final scope freeze

**Look Twice v4 — Active Evidence Assurance** is the final feature direction
for this hackathon. From August onward, only integration fixes, experiments,
visualisation, reproduction, and submission work are allowed.

Positioning:

> A Purify-powered, lineage-aware action qualification and active evidence
> repair system for Physical AI on AMD GPU.

中文定位：机器人不仅判断世界状态，还验证证据是否新鲜、独立、校准有效；动作
合同不满足时，机器人主动执行能够修复证据缺口的观察。

## V4 status — 2026-07-15

Legend:

- **Implemented**: code and interfaces exist;
- **Local verified**: CPU/unit or synthetic CI checks passed;
- **Pending W7900D**: no v4 GPU/formal result is claimed yet.

| Workstream | Implemented | Local verified | Remaining acceptance |
| --- | :---: | :---: | --- |
| Public Robot Claim and receipt Schemas | Yes | Yes | Include in clean-clone CI |
| Standalone Go reference core | Yes | Yes | Linux binary/checksum in release |
| Persistent Python/Go NDJSON bridge | Yes | Yes | Verify inside cloud image |
| Root-aware fusion and Action Contract | Yes | Yes | Genesis episode integration |
| Split-conformal artifact builder | Yes | Yes | Collect 350 W7900D calibration records |
| Six policy baselines | Yes | Yes | Run paired matrices |
| Eight stress profiles and oracle boundary | Yes | Yes | Render representative failures |
| BeliefGap repair planner | Yes | Yes | W7900D closed-loop validation |
| Kinematic controller/backend | Yes | Yes | Genesis batch acceptance |
| Skid-steer URDF/wheel controller | Yes | Unit only | 10-seed waypoint and 60-episode tests |
| V4 Genesis RGB-D runtime | Yes | Static/local only | Execute on Genesis 1.1.2/W7900D |
| Atomic metrics/calibration tooling | Yes | Yes | Formal data ingestion |
| `n_envs=8` feasibility | No | No | One-day go/no-go test |
| 96 smoke / 960 formal / 60 physical runs | No | No | Pending |
| V4 demo, report, upstream PR | No | No | Pending; no PR claimed |

Synthetic v4 smoke episodes validate orchestration only and carry
`formal_result_eligible=false`. They cannot satisfy a W7900D milestone.

## Milestones

### M1 — Public evidence contract and independent modalities

Status: **implemented and locally verified**.

- immutable Depth, Semantic, and Static Map Claims;
- capture/device/artifact/parent lineage;
- explicit Depth ROI independent of segmentation;
- clean simulator truth excluded from online Claims;
- JSON Schemas and deterministic IDs/hashes.

Cloud acceptance:

- capture Genesis RGB-D/entity segmentation;
- confirm Depth and Semantic Claims can disagree without oracle leakage;
- archive raw/corrupted evidence and hashes.

### M2 — Purify Robotics Reference Core

Status: **implemented and locally verified**.

- Go 1.23 standard-library module, independent of private Purify;
- `evaluate_action` and `invalidate_plan`;
- conservative lineage collapse and root-aware fusion;
- Action Contract clauses, BeliefGaps, GateReceipt and
  PlanInvalidationReceipt;
- persistent fail-closed NDJSON bridge.

Cloud acceptance: build/run the static binary in the competition image and
verify an admitted receipt followed by a real invalidation.

### M3 — Calibration and action qualification

Status: **logic/tooling implemented; formal artifact pending**.

- class-conditional split conformal, `alpha=0.05`;
- applicability by profile, intensity, and sensor version;
- strict builder for 7 ID profiles × seeds `30000–30049`;
- OOD and version mismatch fail closed.

Acceptance:

- collect the frozen 350-record calibration split on W7900D;
- freeze artifact ID, SHA256, source commit, and sensor version;
- do not tune from validation or locked test results;
- report empirical coverage, miscoverage, Wilson 95% CI, Brier and ECE.

### M4 — Active contract repair

Status: **implemented and locally verified; GPU closed loop pending**.

- seven finite BeliefGap reasons;
- same-view recapture, wait, and four side-view actions;
- fixed utility and no oracle/future/noise-realisation inputs;
- four-observation/two-replan budget;
- explicit safe fallback after unresolved evidence.

Acceptance: videos and JSON must demonstrate
`shared root/conflict → denied → physical observation → new root → revised
receipt → action`.

### M5 — Motion and Genesis integration

Status: **two backends implemented; W7900D acceptance pending**.

- fast kinematic backend integrates bounded linear/angular commands and applies
  poses with `set_pos()` inside Genesis;
- skid-steer backend commands four wheel DOFs and records contacts;
- sensor camera pose is derived from the chassis at every capture.

Go/no-go rule: allow at most two development days for skid-steer acceptance.
If unstable, retain the explicitly labelled velocity-controlled dynamic-rigid-
body fallback; do not weaken evidence correctness or mislabel kinematic output
as wheel physics.

Skid-steer acceptance:

- four viewpoints reached over 10 consecutive seeds within 0.10 m;
- clear route has no collision;
- blocked route reaches the detour;
- controls, contacts, chassis-mounted camera pose, and trajectory appear in JSON.

### M6 — Formal experiments

Status: **protocol/tooling frozen; runs pending**.

1. 96-episode smoke matrix;
2. 960-episode paired closed-loop matrix;
3. 60 skid-steer physical-backend episodes;
4. CPU/ROCm benchmark at batches 1, 8, 32, 128 after 20 warm-ups and 100 timed
   iterations;
5. all results atomically written, immediately copied from cloud, hashed, and
   summarised.

Promotion gates:

- unresolved/stale/conflict/OOD direct entries: zero;
- evidence echo adds no false independent root;
- ID miscoverage ≤ `alpha + 0.03`, with Wilson 95% CI reported;
- unsafe crossing no worse than v3 baseline on paired seeds;
- active safe-task success no worse than passive Purify;
- contract-repair success ≥ 80%;
- every conclusion traceable to Claims, receipts, artifacts, and raw JSON.

Failure cases remain in `runs.csv` and receive a written explanation; no 100%
versus 0% result is manufactured.

### M7 — Presentation and submission

Status: **pending**.

- 3–5 minute English video;
- raw/corrupted RGB-D/semantic evidence, root graph, contract clauses,
  BeliefGap, repair motion, revised receipt, and AMD results on screen;
- technical report, architecture, result tables, failure cases, reproduction;
- fresh-clone CPU and W7900D reproduction;
- optional genuine Genesis AMD example/documentation PR after reproduction;
- official Track 3 PR and `v4.0-hackathon-final` tag.

No upstream contribution is claimed until a public PR URL exists.

## Frozen experiment splits

| Split | Profiles | Seeds | Episodes/scenes | Use |
| --- | ---: | --- | ---: | --- |
| Calibration | 7 ID | `30000–30049` | 350 | Fit quantiles only |
| Validation | 7 ID | `40000–40019` | 140 | Integration/threshold checks |
| Locked test pool | 8 | `50000–50099` | 800 | Held-out evaluation |
| Formal closed loop | 6 policies × 8 | first 20 locked seeds | 960 | Main comparison |
| Physical backend | 3 policies × 4 | 5 locked seeds | 60 | Motion validation |

`ood-severity` is excluded from calibration and included only for fail-closed
evaluation.

## Schedule

| Date | Deliverable |
| --- | --- |
| July 16–20 | M1–M2 integration; skid-steer two-day gate |
| July 21–24 | Formal calibration artifact and Action Contract acceptance |
| July 25–28 | Stress profiles, active repair, AMD benchmark |
| July 29–31 | 96/960/60 runs, immediate backup and summaries |
| August 1–3 | Ablations, failure cases, figures, video, English report |
| August 4 | Fresh-clone reproduction and official submission |
| August 5–6 | Buffer only; no new features |

## Purify/IP boundary

The contest entry includes only the standalone public reference core, robotics
contracts, adapter, benchmark, and reproduction artifacts. It excludes the
private Purify repository, unfinished product engine, product history,
production connectors, databases, commercial code, and internal APIs. Review
the governing competition rules again before final submission.

## Explicitly out of scope

- complete Purify product integration;
- VLA, reinforcement learning, ROS, or a large visual model;
- learned NBV optimisation;
- multi-robot scout;
- open-ended causal/fault discovery or complex POMDP planning;
- real-robot or sim-to-real claim;
- universal formal-safety or certification claim.

## Preserved baselines

V3 remains frozen at `v3.0-noisy-active-perception`; its 500 core episodes,
Learned NBV data, 100-episode learned evaluation, demo, and reported limitations
remain unchanged. V2 remains frozen at `v2.0-active-perception`. V4 may compare
against them but must not overwrite or reinterpret their published artifacts.
