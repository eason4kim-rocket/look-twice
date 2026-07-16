# Look Twice v4 reproduction

This document separates reproducible CPU verification, non-formal synthetic
orchestration, and **archived AMD W7900D** runs under `results/v4-gpu/`.

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

## 3. Formal calibration artifact (W7900D, partial split)

Collect on W7900D with Genesis kinematic motion (not synthetic):

```bash
/opt/venv/bin/python scripts/collect_v4_calibration.py \
  --mode formal --runtime genesis --motion kinematic --device cuda:0 \
  --output-dir outputs/v4-calibration-formal \
  --purify-bin purify_robotics/bin/purify-robotics-core
```

Build JSONL from rows, then fit:

```bash
# Prefer the standard split when all 350 rows exist.
/opt/venv/bin/python scripts/build_v4_calibration.py \
  --input outputs/v4-calibration-formal/calibration.jsonl \
  --output outputs/v4-calibration-formal/calibration_artifact.json \
  --alpha 0.05
```

**Archived contest state:** collection retained **336/350** seeds after retries;
missing seeds are documented in
[`results/v4-gpu/calibration/PARTIAL_SPLIT.txt`](../results/v4-gpu/calibration/PARTIAL_SPLIT.txt).
The fitted artifact used for smoke/formal is

```text
results/v4-gpu/calibration/calibration_artifact.json
```

It was produced with `--allow-nonstandard-split` **only because the split is
honestly incomplete**, not to hide missing data. Re-collection can resume over
existing good rows; do not invent synthetic calibration lines.

## 4. W7900D Genesis integration (frozen kinematic path)

On the competition cloud image (`/opt/venv`, Genesis 1.1.2, ROCm 7.2):

```bash
cd /workspace/look-twice
export PATH=/opt/venv/bin:$PATH PYTHONPATH=src PYOPENGL_PLATFORM=egl
# pin commit: echo "$(git rev-parse HEAD)" > .git_commit   # or copy from Mac

/opt/venv/bin/python - <<'PY'
import genesis as gs, torch
print("Genesis", gs.__version__)
print("PyTorch", torch.__version__)
print("ROCm", torch.version.hip)
print("GPU", torch.cuda.get_device_name(0))
PY

/opt/venv/bin/python src/look_twice_v4.py \
  --runtime genesis \
  --motion-backend kinematic \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --device cuda:0 \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --json-output outputs/v4/evidence-echo-seed-50000.json
```

Acceptance inspection (also true of archived smoke JSON):

```bash
/opt/venv/bin/python - <<'PY'
import json
p = json.load(open("results/v4-gpu/smoke-genesis/raw/purify-active__evidence-echo__seed-50000.json"))
e = p["environment"]
assert e["runtime"] == "genesis-amd"
assert e["genesis_backend"] == "gs.amdgpu"
assert e["gpu"] == "AMD Radeon PRO W7900D"
assert p["configuration"]["smoke_calibration"] is False
assert p["claims"] and p["gate_receipts"]
assert p["motion_segments"]
print(e)
print(p["metrics"])
PY
```

Skid-steer remains implemented for demos/probes but **failed** 10×4 acceptance;
do not claim skid formal physics. Use kinematic for matrices.

## 5. Experiment matrices

```bash
# Smoke 96 — COMPLETE (archived under results/v4-gpu/smoke-genesis/)
/opt/venv/bin/python scripts/run_v4_experiments.py \
  --mode smoke --runtime genesis --motion kinematic \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --device cuda:0 --output-dir outputs/v4-smoke-genesis

# Formal 960 — IN PROGRESS on live GPU; resume-safe
/opt/venv/bin/python scripts/run_v4_experiments.py \
  --mode formal --runtime genesis --motion kinematic \
  --calibration results/v4-gpu/calibration/calibration_artifact.json \
  --device cuda:0 --output-dir outputs/v4-formal-genesis
```

## 6. Summarise completed episodes

```bash
python scripts/summarize_v4_experiments.py \
  --input results/v4-gpu/smoke-genesis \
  --output-dir results/v4-gpu/smoke-genesis/summary

python scripts/summarize_v4_experiments.py \
  --input results/v4-gpu/formal-genesis \
  --output-dir results/v4-gpu/formal-genesis/summary
```

Outputs: `runs.csv`, `aggregate.csv`, `paired_comparisons.csv`. Failed and
unresolved episodes remain. Current formal package N is incomplete until the
GPU runner finishes all 960.

## 7. Figures / evidence DAG

```bash
python scripts/build_v4_evidence_dag.py \
  results/v4-gpu/smoke-genesis/raw/purify-active__evidence-echo__seed-50000.json \
  -o results/v4-gpu/figures/evidence_dag_purify-active_evidence-echo_seed-50000.dot
```

See [`results/v4-gpu/figures/`](../results/v4-gpu/figures/).

## 8. Backup before releasing the instance

Archive and copy to Mac/GitHub:

```text
results/v4-gpu/calibration/*
results/v4-gpu/smoke-genesis/**
results/v4-gpu/formal-genesis/**
results/v4-gpu/bench/*
results/v4-gpu/figures/*
results/v4-gpu/SHA256SUMS
```

The cloud instance is disposable for code, but **leave it running** while formal
960 is unfinished if that is the operator policy.

## Reproduction status

| Tier | Status |
| --- | --- |
| CPU tests and Go core | **Done** (local + cloud) |
| Synthetic Go-gated episode | **Done**; non-formal |
| Formal calibration collection | **Partial** 336/350 on W7900D; artifact archived |
| Genesis RGB-D v4 episode | **Done** (many archived smoke/formal episodes) |
| Skid-steer seed acceptance | **Failed** → kinematic demotion |
| Smoke matrix 96 | **Complete** (`results/v4-gpu/smoke-genesis/`) |
| Formal matrix 960 | **Archived 956 completed + 4 errors** under `results/v4-gpu/formal-genesis/` |
| Physical skid 60 | **Not run** (blocked by acceptance) |
| GPU evidence benchmark | **Done** (`results/v4-gpu/bench/`) |
| Video | Pending presentation |
| Evidence DAG / comparison figure | **Done** (`results/v4-gpu/figures/`) |
