# Look Twice V8 Reproducibility Guide

This guide separates five reproducibility levels:

1. CPU evidence audit - verifies submitted bundles, source identities, and the
   frozen V8 boundary.
2. Preregistered challenge audit - independently recomputes the additive
   30-world same-generator result from all 60 raw episodes.
3. Local Evidence Console - rebuilds the exact judge-facing replay site.
4. Radeon runtime replay - executes a new non-locked episode using the frozen
   model and calibration artifacts.
5. Additive dynamics audit - verifies the earlier 20/20 component bar, the
   separate 30/30 archived-decision V2 package, and the independently sealed
   20/20 60-body plus 10/10 30-body solver-scale shards without rerunning them.

The locked result itself is permanent and is not rerun. A new execution must be
reported as a reproduction or smoke, never as a second locked test.

## 1. Clone the competition branch

```bash
git clone --branch v8-competition-release --single-branch \
  https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
```

## 2. CPU evidence audit

Requirements:

- Python 3.11 or newer;
- no third-party Python package for the replay verifier;
- no GPU, Genesis, ROCm, or private Purify service.

Run:

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
python3 scripts/derive_v8_task_utility.py
```

Expected final verifier fields:

```json
{
  "passed": true,
  "guarded_file_count": 21,
  "replay_count": 2,
  "v8_runtime_frozen": true,
  "locked_test_runs": 1,
  "public_replay_gpu_dependency": false,
  "errors": []
}
```

The first command regenerates public replay bundles deterministically. If any
guarded runtime file, result, receipt, calibration artifact, episode, or bundle
has changed, verification fails. The final command derives paired task utility
and a confirmatory cost ledger from already archived evidence; it does not run
V8, reopen the locked split, or change model thresholds.

### 2.1 Verify the input-only locked archive

The archive is too large for the Git repository. Its stable identity, content
counts, and evidence boundaries are recorded in
`docs/V8_LOCKED_INPUT_EVIDENCE.md` and
`release/v8-frozen/results/V8_LOCKED_INPUT_PACK_MANIFEST.json`.

After obtaining the archive and sidecar, run:

```bash
python3 scripts/verify_v8_locked_input_pack.py \
  --archive /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.tar.gz \
  --sidecar /path/to/v8-spatial-dataset-v1__locked_test__400seeds__20260720T120737Z.sidecar.json \
  --check-only
```

The verifier first checks the archive SHA256, then streams metadata and table
entries without extracting arrays. It runs no model inference, does not reopen
the locked split, and does not recompute the locked aggregate. This is
input-only verification: the pack lacks the original 3,200 one-shot
predictions and the 24 raw live full-chain episodes. Report summaries cannot
reconstruct those missing outputs.

### 2.2 Verify the preregistered challenge from all raw episodes

This is a separate **same-generator non-locked supplement**, not a rerun or
replacement of the permanent 12-pair locked result. Seeds `102500-102529` were
publicly preregistered and each policy was attempted once per seed. Seeds
`102530-102549` were separately attempted once per policy cell under the
public-before-run compound contract-progress protocol; seeds
`102550-102699` remain unevaluated. Neither result is OOD or physical-robot
evidence.

Download, authenticate, extract, and independently recompute it:

```bash
curl -LO https://github.com/eason4kim-rocket/look-twice/releases/download/v8-competition-candidate/v8-frozen-challenge-102500-102529.raw.tar.gz
shasum -a 256 v8-frozen-challenge-102500-102529.raw.tar.gz
tar -xzf v8-frozen-challenge-102500-102529.raw.tar.gz
python3 scripts/verify_v8_frozen_challenge.py \
  --results-dir v8-frozen-challenge-102500-102529 \
  --preregistration release/v8-frozen/results/V8_FROZEN_CHALLENGE_PREREGISTRATION.json \
  --repo-root . \
  --output v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
shasum -a 256 v8-frozen-challenge-102500-102529.LOCAL-VERIFICATION.json
```

Expected archive SHA256:

```text
171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2
```

Expected independent verification SHA256:

```text
942f1624e6903033335e5ffbcdbc12afed4a0e8eed4e0d33ffa657f5e147a940
```

The extracted directory has 195 regular files. Its internal `SHA256SUMS`
binds every other file (194/194); validator output must remain outside that
directory. The validator checks the public preregistration and frozen
identities, exact seed/policy schedule, all raw episodes, Python/Go receipts,
full-wall telemetry, recursive hashes, and recomputes the complete report.

Expected headline recomputation:

```text
passed: true; errors: 0
active full-chain direct: 29/30
passive full-chain direct: 0/30
mission success: 60/60
unsafe: 0/60
fallback: 0/60
comparable Python/Go receipt agreement: 250/268 (93.3%)
```

The preregistered primary endpoint remains active 29/30 versus passive 0/30,
with exact two-sided McNemar `p=3.73e-9`. To reproduce the separate post-hoc
descriptive offline oracle-feasibility audit without extracting or rerunning
episodes:

```bash
python3 scripts/audit_v8_challenge_feasibility.py \
  v8-frozen-challenge-102500-102529.raw.tar.gz \
  --output v8-frozen-challenge-102500-102529.LOCAL-FEASIBILITY-AUDIT.json
```

The derived result is 29/29 active worlds with at least one oracle-clear
corridor routed direct and selected an oracle-clear corridor; the sole
dual-blocked world, seed `102515`, completed by safe detour. Thus 30/30 active
route outcomes matched offline feasibility, with unsafe false, collision count
zero, and fallback false across the active records. Oracle labels were never
available to the controller. This audit is not a preregistered endpoint and
does not change the formal 29/30 direct result.

All 18 receipt disagreements are Python-admit/Go-deny with
`effective_admit=false`; no disagreement opens the gate. Carrier and scout are
two logical roles with distinct poses/viewpoints on one shared Genesis
chassis, not two physical devices or simultaneous dual-body dynamics.

A post-hoc descriptive raw-archive audit localizes all 18 disagreements to
active-policy corridor-B evaluations for which Go had one qualifying root and
the conformal prediction set `{clear, blocked}`. Four corridors were not
ultimately selected; the other 14 temporary evaluations were followed by a
separate joint Python+Go admit before the selected direct crossing. No selected
crossing was authorized by a mismatch. This localization changes no run,
preregistered endpoint, calibration, or threshold.

## 3. Inspect the authoritative result

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("release/v8-frozen/results/LOCKED_TEST_REPORT.json")
r = json.loads(p.read_text())
print("passed", r["passed"])
print("offline", r["offline"]["metrics"])
print("live", r["live_fullchain"]["gates"])
PY
```

Verify the archived report file hash:

```bash
shasum -a 256 release/v8-frozen/results/LOCKED_TEST_REPORT.json
```

Expected:

```text
5b88d5e7683f853380f1e23123f830c6966824e3afee055af5c4fb6604f672cb
```

Linux users may use `sha256sum` instead of `shasum -a 256`.

## 4. Run the public Purify Go core

Requirements: Go 1.23+.

```bash
cd purify_robotics
go test ./...
go build ./cmd/purify-robotics-core
cd ..
```

The Go tests cover canonical serialization, action-contract evaluation, receipt
hashing, and fail-closed schema behavior.

## 5. Build the Evidence Console

### Docker path

Requirements: Docker Engine with Compose.

```bash
docker compose up --build
```

Open http://localhost:3000 and inspect:

- `/` - project and 30-second evidence reel;
- `/console` - active and passive evidence replay;
- `/results` - frozen metrics and artifact identities;
- `/reproduce` - judge-facing reproduction summary.

Stop with `Ctrl-C`.

### Node path

Requirements: Node.js 22.13+.

```bash
cd showcase
npm ci
npm test
npm run dev
```

The test suite rebuilds the site and checks replay timing, language consistency,
rendered HTML, and evidence snapshots.

## 6. Trace a displayed decision to raw evidence

The public replay manifest is:

```text
showcase/public/data/manifest.json
```

It points to:

```text
showcase/public/data/replays/v8-active-repair-direct.json
showcase/public/data/replays/v8-passive-safe-detour.json
```

Each EpisodeBundle contains:

- source episode SHA256;
- Claim and measurement-root summaries;
- initial and final GateReceipts;
- repair requests and plan invalidation;
- route and safety outcomes;
- AMD GPU evidence metadata;
- its own bundle SHA256.

The active source episode is:

```text
release/v8-frozen/episodes/active__independent-noise__105400.json
```

The replay is non-locked confirmatory evidence. The locked aggregate remains
the report in Section 3.

## 7. Frozen Radeon runtime requirements

The captured environment was:

```text
Linux 6.8.0-79 x86_64
Python 3.12.3
Genesis 1.1.2
PyTorch 2.9.1 ROCm build
HIP 7.2.53211-e1a6bc5663
AMD Radeon gfx1100, approximately 48 GiB VRAM
```

The GPU path needs:

- the competition Genesis/ROCm image;
- the frozen checkpoint;
- the vision conformal artifact;
- the Go-fusion conformal artifact;
- the Purify Linux binary;
- the frozen V8 runtime source.

Checkpoint identity:

```text
filename: v8_seg_v3_selected_ep22_7b158726f9c0.pt
bytes:    159592901
sha256:   7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783
```

The checkpoint is distributed as a GitHub release asset because it exceeds
GitHub's 100 MB blob limit. Download it with the Python standard library:

```bash
python3 - <<'PY'
from urllib.request import urlretrieve

url = (
    "https://github.com/eason4kim-rocket/look-twice/releases/download/"
    "v8-competition-candidate/v8_seg_v3_selected_ep22_7b158726f9c0.pt"
)
urlretrieve(url, "v8_seg_v3_selected_ep22_7b158726f9c0.pt")
PY

shasum -a 256 v8_seg_v3_selected_ep22_7b158726f9c0.pt
```

The result must be exactly the SHA256 above before loading the file.

### 7.1 Dependency and environment contract

The exact GPU path uses the AMD competition image. Install the recorded direct
Genesis pin and retain the image's ABI-matched ROCm PyTorch packages:

```bash
/opt/venv/bin/python -m pip install -r requirements-rocm-v8.txt
/opt/venv/bin/python scripts/verify_v8_rocm_environment.py
```

The preflight requires Genesis 1.1.2, PyTorch 2.9.1+gitff65f5b, HIP
7.2.53211-e1a6bc5663, and `gfx1100`. `torchvision` must remain the build paired
with that competition-image PyTorch package. A generic PyPI PyTorch wheel is
not an exact reproduction of the frozen runtime.

### 7.2 Inspect the frozen ROCm telemetry

The submission-time telemetry report is
`release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json`. Verify its bytes:

```bash
shasum -a 256 release/v8-frozen/results/V8_FROZEN_ROCM_TELEMETRY.json
```

Expected:

```text
0ec12a92ac4e88a97d9068e40a06f72f9dd5ecaa16503c45e2d965d4d876dde9
```

It records a clean-GPU preflight followed by a 60.182-second synthetic,
preloaded-tensor, FP32 frozen-model forward run at batch 8: 47 forwards, 376
images, 61/61 GPU-use samples at 100%, 135.33 W mean graphics-package power,
and 156 W p95 power.

These are workload-specific telemetry measurements, not an accuracy test or
end-to-end robot benchmark. The run excludes RGB-D preprocessing, Genesis
simulation and rendering, Go fusion, I/O, and actuation. It did not open the
locked split or change model weights, calibration, or thresholds.

### 7.3 Inspect the challenge full-wall ROCm telemetry

The challenge telemetry is a second, broader execution record, not an
extension of the synthetic model-forward measurement above:

```bash
shasum -a 256 \
  release/v8-frozen/results/challenge_102500_102529/ROCM_TELEMETRY.json
```

Expected:

```text
463add74afa2c905cb7e63e7450f8761f3c6c3cd56ee9789633c7df0272860c0
```

It retains 844 two-second samples across the complete 1,685.5-second
challenge subprocess wall, including idle, for all 60 episode subprocesses.
GPU-use mean/median/p95/max is 19.4/0/95/100%; VRAM p95/max is 2/2%; graphics
package power mean/p95/max is 35.7/81/109 W. The denominator includes Python,
Genesis live RGB-D, the frozen checkpoint, and Purify Go execution.

The recorded per-episode wall durations cover the complete subprocess, not
control-loop latency. These values are not mission energy, physical duty
cycle, rigid-body contact evidence, or a real-robot benchmark.

## 8. Run a new non-locked Radeon episode

After placing the verified checkpoint at `$V8_CHECKPOINT`, run:

```bash
export PYTHONPATH=src
export PYOPENGL_PLATFORM=egl
export V8_CHECKPOINT=/absolute/path/v8_seg_v3_selected_ep22_7b158726f9c0.pt

/opt/venv/bin/python src/look_twice_v7.py \
  --runtime genesis \
  --motion-backend kinematic \
  --policy purify-active-vision \
  --profile independent-noise \
  --seed 105400 \
  --device cuda:0 \
  --vision-backend torch_spatial_rgbd \
  --vision-checkpoint "$V8_CHECKPOINT" \
  --vision-conformal-artifact \
    release/v8-frozen/results/calibration_vision/conformal_artifact.json \
  --go-conformal-artifact \
    release/v8-frozen/results/calibration_go_fusion_v3/conformal_artifact.json \
  --use-purify-go-gate \
  --purify-binary release/v8-frozen/artifacts/purify-robotics-core-linux \
  --json-output outputs/reproduction/v8-active-105400.json
```

This is a reproduction episode. It must not overwrite the archived episode or
locked report.

## 9. Verify the additive dual-body dynamics supplement

The complete report can be audited without Genesis or a GPU:

```bash
cd release/v8-derived/dual_body_dynamics_160820_160839
shasum -a 256 -c SHA256SUMS
cd ../../..
python3 scripts/verify_v8_additive_dual_body_dynamics.py \
  release/v8-derived/dual_body_dynamics_160820_160839/REPORT.json
```

Expected output:

```text
PASS: additive dual-body dynamics 20/20 report_sha256=8a883163ff544bdf7aa9410b4b4d364e88dcee15dce15edcbd791a1d4b4fd110
```

The report is submission-time, additive, and non-locked. It binds the fixed
seeds `160820-160839`, source commit, runner and URDF hashes, Radeon/ROCm
environment, all per-seed checks, and aggregate rollups. Its first whole-run
attempt hit only an external 3,600-second watchdog before any report or seed
outcome was observed. The recovery audit verifies that attempt 2 changed only
the watchdog to 10,800 seconds; code, seeds, protocol, and thresholds did not
change.

The original Radeon command is in
`docs/V8_ADDITIVE_DUAL_BODY_DYNAMICS_PROTOCOL.md`. Running it again creates a
new non-locked reproduction and must not overwrite the sealed report.

## 10. Verify the additive decision-bound dynamics replay

This is separate from both the frozen primary and the earlier 20-seed
component bar. It consumes the immutable archived challenge outcomes--29
direct decisions and the safe detour at dual-blocked seed `102515`--without
rerunning the perception-policy loop. Each seed used one fresh serial
Genesis/ROCm scene containing an active scout, active loaded carrier, and
passive loaded carrier. The 90 non-fixed bodies are totals across 30 scenes,
not one simultaneous 90-body execution.

First authenticate the 79-entry package checksum index, then verify every
retained file and run the fail-closed report/checkpoint verifier:

```bash
V2=release/v8-derived/decision_dynamics_recovery_v2_102500_102529
PACKAGE_SHA=24d3538365d2818f5e5b64c5f06ecee94bdeae1e4d3df2ab320178248bf71540

printf '%s  %s\n' "$PACKAGE_SHA" "$V2/PACKAGE_SHA256SUMS" | \
  shasum -a 256 -c -
(cd "$V2" && shasum -a 256 -c PACKAGE_SHA256SUMS)
python3 scripts/verify_v8_additive_decision_dynamics_recovery_v2.py \
  "$V2/REPORT.json"
```

Expected final verifier line:

```text
PASS: additive decision-to-dynamics recovery V2 30/30 report_sha256=1501e31bdc1bc353d56224f76f0a0f58de574e6c436980bc9c22a7c33104bd99
```

Expected result summary:

```text
decisions: 29 direct + 1 safe detour (seed 102515)
sealed checkpoints / passed trials: 30/30 / 30/30
scout / active carrier / passive carrier reached: 30/30 / 30/30 / 30/30
mean active / passive loaded-carrier path: 4.943529 m / 6.243270 m
paired mean path reduction: 20.8183%
blocker / active-pair contact rows: 0 / 0
maximum tilt / parked-partner drift: 10.579607 deg / 0.022329 m
```

The package index covers the report, source binding, all 30 checkpoints,
attempt and progress ledgers, worker and execution logs, the recovery audit,
and the post-run provenance review. `REPORT.json` remains
`formal_result_eligible=false`. Running the protocol command again would create
a new non-locked reproduction and must use a new output directory; it must not
overwrite or append to this sealed package.

### 10.1 Proof-scope disclosure

The package preserves two limitations that a verifier should not silently
upgrade into stronger claims:

- The inner V2-run `SHA256SUMS` contains 32 entries--`SOURCE_BINDING.json`, 30
  checkpoints, and `REPORT.json`--but did not originally include
  `ATTEMPTS.jsonl`, `PROGRESS.json`, or worker logs. The retained ledger and
  logs show exactly 30 attempt-1 completions, all exit code zero, with no
  retry or replacement. The original inner checksum and V2 attempt
  verifier alone are not a cryptographic proof that an additional unsealed
  attempt never existed. `PACKAGE_SHA256SUMS` binds the currently retained
  complete package; it does not retroactively change the original proof scope.
- `SOURCE_BINDING.json` omitted the directly imported runtime dependency
  `src/v4_motion.py`. A clean 2,419-file post-run tree audit found no source
  difference or writable non-Git file, and both the worktree and commit
  `b0c4f0d` copy hash to
  `fd94a2d7b89cc3118e3ccf4ae2545f95c84e6596b48c7e79bf52f352935d0772`.
  This is corroborating evidence, not a signed continuous-attestation claim.

For the full interpretation and V1 watchdog history, inspect:

```text
docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_RESULT.md
docs/V8_ADDITIVE_DECISION_DYNAMICS_RECOVERY_V2_PROTOCOL.md
release/v8-derived/decision_dynamics_recovery_v2_102500_102529/PROVENANCE_REVIEW.json
release/v8-derived/decision_dynamics_recovery_v2_102500_102529/RECOVERY_EXECUTION_AUDIT.json
```

## 11. Verify the solver-scale two-shard complement

This evidence class replays the same immutable archived decisions in a
different solver topology. The first report covers seeds `102500-102519` in
one scene containing 60 co-resident non-fixed robots and passed 20/20. The
second report covers seeds `102520-102529` in a separate scene containing 30
co-resident robots and passed 10/10. Both used fixed-order serial wheel
actuation, one Genesis initialization and scene build per shard, and no resume.

Run both checksum suites and both dedicated verifiers independently:

```bash
P60=release/v8-derived/decision_dynamics_single_scene_60_102500_102519
S30=release/v8-derived/decision_dynamics_single_scene_30_suffix_102520_102529

(cd "$P60" && shasum -a 256 -c SHA256SUMS && \
  shasum -a 256 -c PACKAGE_SHA256SUMS)
(cd "$S30" && shasum -a 256 -c SHA256SUMS && \
  shasum -a 256 -c PACKAGE_SHA256SUMS)
python3 scripts/verify_v8_additive_decision_dynamics_60.py "$P60/REPORT.json"
python3 scripts/verify_v8_additive_decision_dynamics_30_suffix.py \
  "$S30/REPORT.json"
```

Expected final verifier lines:

```text
PASS: additive decision-to-dynamics single-scene 60-body 20/20 report_sha256=3cfcf19e60ba102772d052862f44bae29eb47d84717db3d0fbe7ed3b62b24450
PASS: additive decision-to-dynamics 30-body suffix 10/10 report_sha256=69dfd142175ea3d9f719dd5cd0dbb3126f3f7b77b74f4ad753b5f92193ce1a4e
```

Expected two-report summary:

```text
scenes: exactly 2 (one 60-body prefix + one 30-body suffix)
fixed decisions: 20/20 + 10/10 = 30/30
cumulative distinct robots: 90
maximum co-resident robots: 60
all 90 co-resident in one scene: false
scout / active carrier / passive carrier reached: 30/30 / 30/30 / 30/30
direct pairs saving at least 0.50 m: 29/29
safe detour: seed 102515
weighted active / passive path: 4.943605 m / 6.245385 m
weighted path reduction: 20.8439%
blocker / active-pair contact rows: 0 / 0
maximum tilt / parked-partner drift: 10.583984 deg / 0.021342 m
```

The combined lines above are a deterministic summary of two disjoint fixed
denominators, not a third report. The suffix binds the exact prefix report SHA
but does not use prefix outcomes to determine its own scientific acceptance.
The combined topology may be stated only after both reports independently
verify. There is no cross-shard resume or stitching, and the 90 robots were
never all co-resident.

Both reports remain additive, non-locked, archived-decision, fixed-order
serial, simulation-only evidence with `formal_result_eligible=false`. They do
not rerun the live perception-policy loop, demonstrate simultaneous fleet
control or dynamic obstacles, validate a physical robot or sim-to-real
transfer, establish energy/throughput/latency, or certify safety. They do not
turn the failed V1 all-90-body attempt into a pass, and the preregistered
primary remains active 29/30 versus passive 0/30.

## 12. Verify artifact identities

```bash
shasum -a 256 "$V8_CHECKPOINT"
shasum -a 256 release/v8-frozen/artifacts/purify-robotics-core-linux
python3 scripts/verify_frozen_foundation.py
```

Expected checkpoint SHA:

```text
7b158726f9c00e01eec7f995674001727be03b84ff684a0cb43cba8682cd5783
```

Expected Purify binary SHA:

```text
31a405b6d7e494a6add120c14b8d27b1f9f168cedaaae2afd860ccfdbd385d00
```

## 13. Reproducibility limits

- The full train/validation/locked datasets are not committed to Git. The
  locked input archive is byte-identified and verifiable when supplied as a
  separate release asset, but it is input-only: it lacks the original
  predictions and raw locked live episodes.
- The frozen model is a separately hosted 159 MB release asset.
- The exact locked run is permanent and should not be regenerated.
- A new execution can differ in wall-clock timing because the public replay
  does not pin the cloud scheduler or all system packages.
- Statistical claims apply only to the declared simulated split.
- Seeds 102500-102529 were evaluated exactly once per preregistered policy in
  the additive same-generator non-locked challenge. Seeds 102530-102549 were
  separately evaluated once per policy cell in the public-before-run compound
  contract-progress challenge; seeds 102550-102699 remain unevaluated. No OOD,
  out-of-distribution, or population-generalization result is claimed.
- Challenge carrier/scout measurements are logical-role kinematic burden on
  one shared chassis, not simultaneous dual-body dynamics or two physical
  devices. The separate 20-seed dynamics supplement uses two non-fixed rigid
  bodies with sequential wheel actuation; it is not a rerun of the full frozen
  policy or a physical-robot result.
- The separate 30-seed decision-bound replay uses archived decisions in 30
  independent serial three-body scenes. It does not run the live frozen
  perception-policy loop, place 90 bodies in one simultaneous scene, or test
  simultaneous cooperation or dynamic obstacles. It is additive, non-locked,
  and `formal_result_eligible=false`.
- The solver-scale complement uses the same archived decisions in two separate,
  non-resumable, fixed-order serial scene shards: 20/20 in one 60-body scene
  and 10/10 in a second 30-body scene. The only combined topology claim is
  exactly two scenes, cumulative 90 distinct robots, maximum co-resident 60,
  and never all 90 co-resident. It is not a live full-policy rerun,
  simultaneous cooperative control, or completion of the failed V1 90-body
  attempt, and it does not alter the primary 29/30 endpoint.
- The decision-bound replay supports a paired physical-path result only. It is
  not real-robot, sim-to-real, energy, throughput, latency, or safety-
  certification evidence.
- The decision-bound package's inner attempt-verifier/checksum and source-
  binding proof scopes have the two explicit limitations in Section 10.1;
  post-run package and tree audits corroborate the retained evidence but do
  not provide signed continuous attestation.
- Challenge receipt-level Python/Go agreement is 250/268 (93.3%); all 18
  mismatches were Go vetoes with effective authorization kept fail-closed.
- Full-wall telemetry includes idle and covers complete episode subprocesses;
  it is not control-loop latency, mission energy, or physical duty cycle.
- The evidence website verifies recorded results; it does not run Genesis or
  infer new robot actions.
