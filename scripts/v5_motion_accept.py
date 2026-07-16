#!/usr/bin/env python3
"""Skid-steer motion acceptance for v5 (run on W7900D with Genesis).

Exit 0 only if all seeds reach four side viewpoints within 0.10 m.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

# Usage on cloud:
#   gs.init(backend=gs.amdgpu) then import GenesisEpisodeRuntime with motion skid-steer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/v5-motion-accept.json"))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(50000, 50010)))
    args = parser.parse_args()

    try:
        import genesis as gs
    except ImportError:
        print("Genesis not installed; motion acceptance is cloud-only.", file=sys.stderr)
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    gs.init(backend=gs.amdgpu, logging_level="warning")
    from v4_genesis_runtime import GenesisEpisodeRuntime
    from v4_scenario import sample_v4_scenario

    viewpoints = (
        ("left_near", (-0.4, 1.1)),
        ("left_far", (-1.2, 1.6)),
        ("right_near", (-0.4, -1.1)),
        ("right_far", (-1.2, -1.6)),
    )
    failures = []
    results = []
    t0 = time.time()
    for seed in args.seeds:
        scenario = sample_v4_scenario("independent-noise", seed)
        rt = GenesisEpisodeRuntime(scenario, motion_backend="skid-steer")
        seed_rows = []
        try:
            for name, xy in viewpoints:
                mr = rt.move_to(xy)
                pose = rt.current_pose
                err = math.hypot(pose.x - xy[0], pose.y - xy[1])
                row = {
                    "seed": seed,
                    "viewpoint": name,
                    "error_m": err,
                    "reached": mr.reached,
                    "reason": mr.reason,
                }
                seed_rows.append(row)
                if (not mr.reached) or err >= 0.10:
                    failures.append(row)
        finally:
            rt.close()
        results.append({"seed": seed, "viewpoints": seed_rows})
        print(
            f"seed {seed} max_err={max(r['error_m'] for r in seed_rows):.4f} "
            f"fails={sum(1 for r in seed_rows if r['error_m'] >= 0.10 or not r['reached'])}",
            flush=True,
        )

    payload = {
        "schema": "look-twice.motion-acceptance/v5",
        "backend": "skid-steer",
        "threshold_m": 0.10,
        "elapsed_seconds": time.time() - t0,
        "n_failures": len(failures),
        "passed": len(failures) == 0,
        "failures": failures,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print("MOTION_ACCEPT_PASSED" if payload["passed"] else "MOTION_ACCEPT_FAILED", payload["n_failures"])
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
