# Look Twice v4 reproduction

This document separates reproducible CPU verification, non-formal synthetic
orchestration, and pending AMD W7900D acceptance.

## 1. Fresh clone and CPU contracts

```bash
git clone https://github.com/eason4kim-rocket/look-twice.git
cd look-twice
git rev-parse HEAD

python -m pip install numpy pillow
python -m unittest discover -s tests -v
(cd purify_robotics && go test ./...)
./scripts/build_purify_robotics.sh
shasum -a 256 purify_robotics/bin/purify-robotics-core
```

Expected scope: contracts, lineage, calibration, policy boundaries, repair,
motion-control logic, deterministic receipts, metrics, and CLI behavior. This
step uses no Genesis and proves no GPU behavior.

## 2. Synthetic CI smoke

```bash
python src/look_twice_v4.py \
  --runtime synthetic \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --allow-smoke-calibration \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/v4-synthetic-smoke.json
```

Verify:

```bash
python - <<'PY'
import json
p = json.load(open("outputs/v4-synthetic-smoke.json"))
assert p["environment"]["runtime"] == "synthetic-ci"
assert p["environment"]["formal_result_eligible"] is False
assert p["configuration"]["smoke_calibration"] is True
print(p["metrics"])
PY
```

This checks orchestration through the real Go subprocess. Do not publish its
rates as Genesis, ROCm, physics, W7900D, calibration, or formal results.

## 3. Build the formal calibration artifact

First collect exactly one W7900D calibration record per seven ID profile and
seed `30000–30049`. Each JSONL line requires:

```text
seed, profile, noise_intensity, sensor_version, true_label, p_clear
```

The frozen collector/matrix execution is still pending; do not manufacture
these records from synthetic smoke output.

```bash
/opt/venv/bin/python scripts/build_v4_calibration.py \
  --input outputs/v4/calibration-records.jsonl \
  --output outputs/v4/calibration.json \
  --git-commit "$(git rev-parse HEAD)"

shasum -a 256 \
  outputs/v4/calibration-records.jsonl \
  outputs/v4/calibration.json
```

Default validation rejects missing/extra seeds or profiles, duplicates, and
`ood-severity`. `--allow-nonstandard-split` is testing-only.

## 4. W7900D Genesis integration

On the competition cloud image:

```bash
cd /workspace/look-twice
./scripts/build_purify_robotics.sh

/opt/venv/bin/python - <<'PY'
import genesis as gs, torch
print("Genesis", gs.__version__)
print("PyTorch", torch.__version__)
print("ROCm", torch.version.hip)
print("GPU", torch.cuda.get_device_name(0))
PY

/opt/venv/bin/python src/look_twice_v4.py \
  --runtime genesis \
  --motion-backend skid-steer \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --device cuda:0 \
  --calibration outputs/v4/calibration.json \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --evidence-dir outputs/v4/evidence-echo-seed-50000 \
  --json-output outputs/v4/evidence-echo-seed-50000.json \
  --video-output outputs/v4/evidence-echo-seed-50000.mp4
```

Acceptance inspection:

```bash
/opt/venv/bin/python - <<'PY'
import json
p = json.load(open("outputs/v4/evidence-echo-seed-50000.json"))
e = p["environment"]
assert e["runtime"] == "genesis-amd"
assert e["genesis_backend"] == "gs.amdgpu"
assert e["formal_result_eligible"] is True
assert p["configuration"]["smoke_calibration"] is False
assert p["claims"] and p["gate_receipts"]
assert p["motion_segments"]
print(e)
print(p["metrics"])
PY
```

This v4 W7900D command is documented but not yet claimed as completed.

## 5. Fast Genesis batch backend

Use the same command with:

```text
--motion-backend kinematic
```

It retains Genesis sensing and `gs.amdgpu`, integrates bounded velocity
commands, and applies poses with `set_pos()`/`set_quat()`. It may be used for
the 960 paired evidence experiment but cannot be presented as skid-steer wheel
physics.

## 6. Summarise completed episodes

The summarizer accepts JSON, JSONL, directories, or repeated `--input`:

```bash
python scripts/summarize_v4_experiments.py \
  --input outputs/v4/formal/raw \
  --output-dir outputs/v4/formal/summary
```

Outputs:

```text
runs.csv
aggregate.csv
paired_comparisons.csv
```

Writes are atomic and deterministic. Failed, malformed, unsafe, and unresolved
episodes remain in `runs.csv` with source and raw JSON; rerunning the summarizer
does not silently discard them.

## 7. Backup before releasing the instance

Archive and immediately copy:

```text
calibration-records.jsonl and calibration.json
all raw episode JSON/JSONL
runs.csv, aggregate.csv, paired_comparisons.csv
raw/corrupted evidence images
videos and trajectories
environment log, Git commit, binary/artifact/data SHA256 manifests
```

The cloud instance is disposable. GitHub and the Mac copy are the permanent
stores.

## Reproduction status

| Tier | Status |
| --- | --- |
| CPU tests and Go core | Implemented/local verified |
| Synthetic Go-gated episode | Implemented/local verified; non-formal |
| Formal calibration collection | Pending W7900D |
| Genesis RGB-D v4 episode | Pending W7900D acceptance |
| Skid-steer seed test | Pending W7900D |
| 96/960/60 matrices | Pending |
| V4 benchmark/video | Pending |
