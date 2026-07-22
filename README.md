# Look Twice — Active Evidence Assurance for Physical AI

Look Twice qualifies whether robot evidence is reliable enough to support a
physical action, and actively repairs missing evidence when it is not.

```text
RGB-D observations
→ calibrated, lineage-aware Claims
→ action contract
→ Purify authorization
→ active evidence repair when denied
→ direct action, safe detour, or fail closed
```

The competition release is candidate-neutral. The product website reads only
`ReleaseProfile v1` and `EpisodeBundle v1`; V8 and a possible V9 connect through
small adapters without candidate-specific UI code.

## Replay the evidence console

No AMD GPU, Genesis, ROCm, or live Purify process is required:

```bash
docker compose up --build
# open http://localhost:3000
```

The two foundation replays are recorded non-locked confirmatory episodes:

- Active: initial denial → new capture root → Python ∧ Purify Go admit → direct;
- Passive: initial denial → safe detour.

Every bundle retains its source episode SHA and frozen artifact identities. The
public data is scrubbed of local paths, SSH details, and oracle fields.

## Verify the frozen boundary

```bash
python3 scripts/build_competition_replays.py
python3 -m unittest tests.test_competition_replay -v
python3 scripts/verify_frozen_foundation.py
```

The guard covers the imported V8 runtime, both calibration artifacts, Purify
binary, locked report, and the two replay sources. V9 may add an adapter; it may
not change any guarded V8 file.

## Repository map

- `showcase/` — bilingual, replay-first Evidence Console;
- `src/competition_replay.py` — candidate adapter and public schemas;
- `release/V8_FROZEN_IMPORT_MANIFEST.json` — frozen SHA boundary;
- `release/v8-frozen/` — compact V8 evidence import;
- `scripts/build_competition_replays.py` — deterministic Replay Pack builder;
- `release/FOUNDATION_SOURCE_READY.json` — source-layer acceptance stamp.

## Honest boundary

This is a simulation demonstration and research prototype, not a real-robot or
certified-safety claim. The standalone Purify Robotics Core included for the
contest is a minimal reference implementation, not the private Purify product
or a promise of future API compatibility.

Apache-2.0. See `NOTICE` for the Purify IP boundary.
