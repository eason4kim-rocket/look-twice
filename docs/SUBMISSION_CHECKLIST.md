# AMD AI DevMaster Hackathon submission checklist

Verified on 2026-07-15 from the
[official event page](https://luma.com/amd-4dhi),
[official submission repository](https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07),
and linked Rules and Conditions. Recheck the governing rules immediately before
submission.

## Deadline and entry

- Deadline: **2026-08-06 23:59 UTC+8**.
- Track: **Track 3 — Physical AI**.
- Team size: one to three people.
- AMD AI Developer Program membership is required for prize eligibility.
- Submit materials and the official repository PR in English.
- PR title: `Track 3, <Team name>, Look Twice`.
- Recommended demo video length: **3–5 minutes**.

## Purify/IP review — mandatory

- [x] Contest code is a standalone reference implementation with no runtime or
  source dependency on the private Purify product repository.
- [x] `NOTICE` defines the public reference-core boundary.
- [ ] Re-read the current competition IP/license terms before final submission.
- [ ] Confirm that the Entry contains only the public robotics core, contracts,
  adapter, benchmark, and necessary reproduction artifacts.
- [ ] Search the final repository for private Purify paths, names, credentials,
  internal API shapes, history, databases, connectors, and commercial modules.
- [ ] Review every large artifact before upload.

Do not copy the unfinished private Purify assimilation engine into this entry.

## Physical AI score alignment

| Criterion | Points | V4 evidence | Current status |
| --- | ---: | --- | --- |
| Robot capability | 30 | deny, active repair, plan invalidation, cross/detour; two motion backends | Logic/unit implemented; skid-steer W7900D pending |
| AMD Radeon / ROCm | 20 | Genesis physics/rendering, ROCm corruption/evidence, paired throughput | V3 stack verified; v4 measurements pending |
| Innovation | 20 | lineage-aware evidence roots, scoped Action Contract, conformal admission, repair receipts | Implemented/local verified |
| Real-world value | 20 | avoid action from stale, echoed, conflicting, skewed, or OOD evidence | Formal paired evidence pending |
| Upstream open source | 10 | genuine Genesis AMD example/fix if reproduced | No PR currently claimed |

## Implemented and locally verified

- [x] Robot Claim, contract, calibration, gap, gate, and invalidation Schemas.
- [x] Standalone Go 1.23 core and deterministic receipt hashing.
- [x] Persistent fail-closed Python/Go NDJSON bridge.
- [x] Independent Depth/Semantic/Static Map Claims and lineage collapse.
- [x] Class-conditional split-conformal logic and strict artifact builder.
- [x] Six policy baselines and eight paired stress profiles.
- [x] BeliefGap-driven repair planner with oracle-input rejection.
- [x] Kinematic control, skid-steer URDF/controller, and motion audit schema.
- [x] Atomic episode summarizer; malformed/failed runs are retained.
- [x] Synthetic end-to-end smoke path clearly marked non-formal.

## W7900D acceptance — pending

- [ ] Build/run Go core in the cloud image and record checksum.
- [ ] Run v4 Genesis RGB-D/entity segmentation on `gs.amdgpu`/`cuda:0`.
- [ ] Verify independent Depth/Semantic conflicts without oracle leakage.
- [ ] Complete 10-seed skid-steer waypoint acceptance.
- [ ] Collect the 350-record calibration split and freeze its artifact/hash.
- [ ] Run the 96-episode smoke matrix.
- [ ] Run the 960-episode paired formal matrix.
- [ ] Run the 60-episode skid-steer physical-backend matrix.
- [ ] Run batch 1/8/32/128 benchmark with 20 warm-ups and 100 measurements.
- [ ] Perform the one-day `n_envs=8` feasibility test; record fallback honestly.
- [ ] Download every irreplaceable JSON/JSONL/CSV/PNG/video and SHA manifest.

No synthetic output may be copied into a formal W7900D result table.

## Result integrity

- [ ] Calibration uses only seven ID profiles and seeds `30000–30049`.
- [ ] Validation uses seeds `40000–40019`.
- [ ] Locked test uses seeds `50000–50099`; no rule tuning from test outcomes.
- [ ] `ood-severity` is absent from calibration.
- [ ] All policies share the same profile/seed world and absolute event clock.
- [ ] Unresolved/stale/conflict/OOD risk entries are zero or explicitly reported
  as a failed promotion gate.
- [ ] Evidence echo never increases independent-root count.
- [ ] Coverage/miscoverage includes correctly named Wilson 95% intervals.
- [ ] Brier and ECE use the frozen test population.
- [ ] Failed and malformed episodes remain in `runs.csv`.
- [ ] Every table traces to raw JSON, Claims, receipts, artifact ID, and commit.
- [ ] Failure cases are documented rather than deleted.

## Submission artifacts

- [ ] English technical report and project description.
- [ ] Main README with clean-clone commands.
- [ ] Architecture and trust-boundary diagram.
- [ ] V4 reproduction and experiment protocol.
- [ ] Formal result tables, core comparison figure, and failure cases.
- [ ] Representative raw/corrupted evidence and receipt DAG.
- [ ] 3–5 minute W7900D demo video.
- [ ] Linux AMD64 Go binary/checksum or reproducible build instructions.
- [ ] Dependency/environment lock and data hashes.
- [ ] `v4.0-hackathon-final` tag after clean-clone reproduction.

Current ready documents:

- [Submission draft](SUBMISSION_DRAFT.md)
- [Architecture](ARCHITECTURE.md)
- [Reproduction](V4_REPRODUCTION.md)
- [Experiment protocol](V4_EXPERIMENT_PROTOCOL.md)
- [Failure cases](V4_FAILURE_CASES.md)
- [Preserved v3 result](../results/2026-07-15_v3-formal/README.md)

## Human/external actions

- [ ] Confirm Luma registration approval.
- [ ] Confirm AMD AI Developer Program membership.
- [ ] Freeze team name and members.
- [ ] Review current Rules and Conditions and the Purify IP boundary.
- [ ] Fork the official submission repository.
- [ ] Verify public source/video links from a logged-out browser.
- [ ] If a genuine upstream contribution exists, record its real public status;
  otherwise state that none is claimed.
- [ ] Open the official English PR before the deadline.
