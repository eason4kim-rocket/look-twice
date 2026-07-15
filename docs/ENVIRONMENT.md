# Environment and reproducibility

## Verified AMD environment from v3

The following cloud stack was used for the preserved v3 results:

```text
GPU:         AMD Radeon PRO W7900D
Backend:     gs.amdgpu
ROCm:        7.2
PyTorch:     2.9.1+rocm7.2.0
Genesis:     1.1.2 (genesis-world)
Python:      3.12
Interpreter: /opt/venv/bin/python
```

The base image may expose `/usr/bin/python`, but that interpreter does not
contain Genesis. Use `/opt/venv/bin/python` for every cloud GPU command.

V4 targets the same environment. Its CPU contracts and synthetic closed loop
are locally verified, but v4 Genesis/skid-steer/formal-matrix acceptance on the
W7900D is still pending. The v3 environment record is not itself proof that a
new v4 path has run.

中文说明：v3 已在 W7900D 上验证；v4 当前本地逻辑已通过，但必须重新在云端运行
Genesis、轮式控制、正式校准和实验矩阵，不能直接沿用 v3 的 GPU 结果。

## Fresh-clone CPU tier

Requirements:

- Python 3.11 or newer;
- Go 1.23 or newer;
- NumPy and Pillow for the CPU test suite.

```bash
git clone https://github.com/eason4kim-rocket/look-twice.git
cd look-twice

python -m pip install numpy pillow
python -m unittest discover -s tests -v
(cd purify_robotics && go test ./...)
./scripts/build_purify_robotics.sh
```

The build output is:

```text
purify_robotics/bin/purify-robotics-core
purify_robotics/bin/purify-robotics-core.sha256
```

The binary uses `CGO_ENABLED=0`; CI also cross-builds Linux AMD64.

## Synthetic orchestration tier

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

This tier verifies deterministic scenario generation, motion integration,
Claim creation, the persistent Go gate, repair decisions, invalidation, and
result serialization without Genesis or PyTorch.

Every such episode states:

```text
environment.runtime = synthetic-ci
environment.formal_result_eligible = false
configuration.smoke_calibration = true
```

Synthetic output is never eligible for v4 GPU, physics, camera, formal
calibration, benchmark, or competition-result claims.

## Formal calibration artifact

The builder consumes one JSON object per line with exactly these required
fields:

```json
{"seed":30000,"profile":"independent-noise","noise_intensity":0.2,"sensor_version":"look-twice-v4-rgbd-semantic-v1","true_label":"clear","p_clear":0.91}
```

Default mode requires exactly seven in-distribution profiles across every seed
from `30000` through `30049` (350 records), rejects duplicate profile/seed pairs,
and excludes `ood-severity`.

```bash
/opt/venv/bin/python scripts/build_v4_calibration.py \
  --input outputs/v4/calibration-records.jsonl \
  --output outputs/v4/calibration.json \
  --git-commit "$(git rev-parse HEAD)"
```

`--allow-nonstandard-split` exists only for unit/integration fixtures. Artifacts
built with it are not formal.

The W7900D calibration record collection step is pending; therefore no formal
v4 calibration artifact is currently claimed.

## W7900D Genesis integration tier

After copying a fitted artifact and building the Go core:

```bash
cd /workspace/look-twice
./scripts/build_purify_robotics.sh

/opt/venv/bin/python src/look_twice_v4.py \
  --runtime genesis \
  --motion-backend skid-steer \
  --policy purify-active \
  --profile evidence-echo \
  --seed 50000 \
  --device cuda:0 \
  --calibration outputs/v4/calibration.json \
  --purify-bin purify_robotics/bin/purify-robotics-core \
  --evidence-dir outputs/v4/evidence \
  --json-output outputs/v4/evidence-echo-seed-50000.json \
  --video-output outputs/v4/evidence-echo-seed-50000.mp4
```

Required acceptance checks before calling the result formal:

- `environment.runtime == genesis-amd`;
- `environment.genesis_backend == gs.amdgpu`;
- GPU name identifies the W7900D and ROCm is non-null;
- `formal_result_eligible == true`;
- `configuration.smoke_calibration == false`;
- the calibration artifact ID/SHA and Git commit are archived;
- raw/corrupted evidence, Claims, receipts, motion controls, contacts, and
  trajectory are present;
- the output JSON is copied off the ephemeral instance immediately.

The documented command is pending execution/acceptance for v4.

## Motion backends

`--motion-backend skid-steer` drives four wheel DOFs in Genesis and is the
required demo/physical-behaviour path.

`--motion-backend kinematic` integrates bounded linear/angular commands, then
uses `set_pos()`/`set_quat()` to apply the pose in Genesis. It is permitted for
fast paired batch experiments but cannot support a wheel-physics claim.

The standalone synthetic runtime is also kinematic, but it is a CPU CI fixture
and not a Genesis batch result.

## AMD workload accounting

V4 assigns work as follows:

| Component | Device | Status |
| --- | --- | --- |
| Genesis physics | W7900D through `gs.amdgpu` | Pending v4 run |
| RGB-D/entity-segmentation rendering | Genesis graphics path | Pending v4 run |
| Sensor corruption and evidence tensors | PyTorch ROCm `cuda:0` | Pending v4 run |
| Batched candidate/evidence evaluation | PyTorch ROCm | Pending benchmark |
| Root fusion and Action Contract | CPU Go core | Locally verified |
| NDJSON, orchestration, JSON/CSV | CPU | Locally verified |

The project does not claim that every operation belongs on the GPU. Formal
timing will report simulation, rendering, tensor kernel, host/device transfer,
Go gate, and end-to-end time separately. Benchmark protocol: 20 warm-ups, 100
timed iterations, batches 1/8/32/128, median, p95, and observations/second.

The optional Genesis `n_envs=8` path is a one-day feasibility test. If Genesis
1.1.2 multi-environment RGB-D is unstable, v4 will retain single-environment
rendering plus batched ROCm evidence processing without upgrading Genesis or
blocking submission.

## Persistence model

The Radeon instance is ephemeral compute:

- GitHub stores source, schemas, documentation, and small representative data;
- the Mac clone is the working backup and large-artifact destination;
- every calibration/experiment group is written atomically and downloaded as
  soon as it completes;
- JSON/JSONL/CSV/PNG, model/artifact files, SHA256 manifests, and environment
  logs are copied before the instance stops;
- videos and large raw evidence stay out of ordinary Git history unless
  intentionally packaged as small representative assets.

The formal summarizer reads JSON, JSONL, or directories and atomically writes:

```text
runs.csv
aggregate.csv
paired_comparisons.csv
```

Malformed and failed episodes remain in `runs.csv`; they are never silently
dropped.

## V4 reproduction metadata

Each formal episode must preserve:

- Git commit, policy, profile, seed, runtime, motion backend, and device;
- scenario public configuration plus evaluation-only oracle record;
- raw/corrupted evidence artifact hashes;
- every Claim and lineage root;
- Calibration Artifact ID and applicability;
- GateReceipts, BeliefGaps, repair rankings, and invalidation receipts;
- motion controls, trajectory, path length, collisions, and step count;
- unsafe/safe/wrong-detour/repair/invalidation/echo metrics;
- GPU, ROCm, PyTorch, Genesis, and backend versions.

See [V4 reproduction](V4_REPRODUCTION.md) and
[experiment protocol](V4_EXPERIMENT_PROTOCOL.md).
