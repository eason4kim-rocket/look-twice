# Purify Robotics Reference Core v0.1

This directory is a contest-only, standard-library Go reference implementation
of the Robot Evidence Contract used by Look Twice v4. It is intentionally
independent of the private Purify product and does not claim API compatibility
with future Purify releases.

## Build and run

```bash
cd purify_robotics
go test ./...
mkdir -p bin
CGO_ENABLED=0 go build -trimpath \
  -o bin/purify-robotics-core ./cmd/purify-robotics-core
./bin/purify-robotics-core
```

The process reads one command per stdin line and writes exactly one response
per stdout line. It remains alive after a malformed or rejected command.

```json
{"schema_version":"purify.robotics.command.v1","request_id":"req-1","op":"evaluate_action","payload":{"claims":[],"contract":{},"calibration":{},"context":{}}}
{"schema_version":"purify.robotics.response.v1","request_id":"req-1","ok":false,"result":null,"error":{"code":"invalid_request","message":"..."}}
```

Supported operations:

- `evaluate_action`: payload keys are `claims`, `contract`, `calibration`, and
  `context`. Its result is a `GateReceipt`.
- `invalidate_plan`: payload keys are `previous_receipt`, `current_step`, and
  `triggering_claims`. Its result is a `PlanInvalidationReceipt`.

The complete wire definitions are in `../schemas/`.

## Safety and lineage assumptions

- A physical measurement root counts only when both `capture_root_id` and
  `device_root_id` are known. Empty, `unknown`, `unavailable`, and `none` are
  unknown-root sentinels.
- Claims connected by the same capture, exact artifact SHA-256, or declared
  parent lineage form one conservative evidence component.
- A declared parent missing from the request makes that component non-independent.
- `static_map` contributes prior evidence but never a physical measurement root.
- Root-level evidence is quality-and-visibility-weighted; independent roots are
  accumulated in log-odds space.
- A calibration scope mismatch, stale evidence, insufficient roots, excessive
  skew, unresolved conflict, or scope mismatch denies the action.
- An empty conformal set is normalized to `{clear, blocked}` and remains denied.
- Receipt hashes use lexicographically key-sorted, compact UTF-8 JSON with the
  `receipt_sha256` field cleared. Hashes detect mutation; they are not signatures.
