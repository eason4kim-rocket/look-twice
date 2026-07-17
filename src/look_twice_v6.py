#!/usr/bin/env python3
"""Look Twice v6 — Collaborative Evidence Repair entrypoint.

Synthetic path for CI; Genesis RGB-D multi-agent path for AMD GPU.
Does not alter v5 CLI behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_episode import POLICIES, V6EpisodeConfig, run_v6_episode
from v6_scenario import PROFILES, sample_v6_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, default="purify-active")
    parser.add_argument("--profile", choices=PROFILES, default="independent-noise")
    parser.add_argument("--seed", type=int, default=90000)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument(
        "--runtime",
        choices=("synthetic", "genesis"),
        default="synthetic",
    )
    parser.add_argument(
        "--motion-backend",
        choices=("kinematic", "skid-steer"),
        default="kinematic",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Perception device (default cuda:0 on genesis, cpu on synthetic)",
    )
    parser.add_argument(
        "--no-rgbd-claims",
        action="store_true",
        help="Force synthetic claims even on Genesis",
    )
    parser.add_argument(
        "--learned-checkpoint",
        type=Path,
        default=None,
        help="Checkpoint for purify-active-learned / purify-active-dagger",
    )
    args = parser.parse_args(argv)

    scenario = sample_v6_scenario(args.profile, args.seed)
    device = args.device or ("cuda:0" if args.runtime == "genesis" else "cpu")
    config = V6EpisodeConfig(
        policy=args.policy,
        device=device,
        prefer_rgbd_claims=not args.no_rgbd_claims,
        learned_checkpoint=str(args.learned_checkpoint)
        if args.learned_checkpoint
        else None,
    )

    if args.runtime == "synthetic":
        result = run_v6_episode(scenario=scenario, config=config, runtime=None)
    else:
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        from v6_genesis_runtime import V6GenesisRuntime

        runtime = V6GenesisRuntime(
            scenario,
            motion_backend=args.motion_backend,
            device=device,
        )
        try:
            result = run_v6_episode(
                scenario=scenario, config=config, runtime=runtime
            )
        finally:
            runtime.close()

    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.json_output.with_name(args.json_output.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, args.json_output)

    m = result["metrics"]
    env = result.get("environment") or {}
    print(
        f"v6 finished policy={args.policy} profile={args.profile} seed={args.seed} "
        f"mission={m['mission_success']} unsafe={m['unsafe_crossing']} "
        f"route={m.get('route_mode')} repair_ok={m.get('repair_success')} "
        f"claims_mode={m.get('claims_mode')} device={m.get('device')} "
        f"gpu={env.get('gpu') or env.get('gpu_name')}"
        + (f" output={args.json_output}" if args.json_output else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
