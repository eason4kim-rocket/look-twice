# Look Twice V8 Reproducibility Guide

This guide separates three reproducibility levels:

1. CPU evidence audit - verifies submitted bundles, source identities, and the
   frozen V8 boundary.
2. Local Evidence Console - rebuilds the exact judge-facing replay site.
3. Radeon runtime replay - executes a new non-locked episode using the frozen
   model and calibration artifacts.

The locked result itself is permanent and is not rerun. A new execution must be
reported as a reproduction or smoke, never as a second locked test.

## 1. Clone the competition branch

```bash
git clone --branch v8-competition-release --single-branch \
  https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
```

Until the release branch is pushed, use the provided source archive or the
local release worktree. The final submission must not publish these commands
until the public branch resolves from a logged-out browser.

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

The command regenerates public replay bundles deterministically. If any
guarded runtime file, result, receipt, calibration artifact, episode, or bundle
has changed, verification fails.

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

The checkpoint is preserved outside normal Git because it exceeds GitHub's
100 MB blob limit. Before final submission, publish it as a GitHub release
asset or model-hosting artifact and verify the download hash.

## 8. Run a new non-locked Radeon episode

After placing the checkpoint at `$V8_CHECKPOINT`, run:

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

## 9. Verify artifact identities

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

## 10. Reproducibility limits

- The full train/validation/locked datasets are not committed to Git.
- The frozen model requires a separately hosted 159 MB checkpoint.
- The exact locked run is permanent and should not be regenerated.
- A new execution can differ in wall-clock timing because the public replay
  does not pin the cloud scheduler or all system packages.
- Statistical claims apply only to the declared simulated split.
- The evidence website verifies recorded results; it does not run Genesis or
  infer new robot actions.
