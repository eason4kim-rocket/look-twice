#!/usr/bin/env python3
"""Look Twice v6 — Collaborative Evidence Repair entrypoint.

Does not alter v5 CLI behavior. Synthetic multi-agent closed loop by default;
Genesis RGB-D backends can be added on the cloud path later.
"""

from __future__ import annotations

import argparse
import json
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
        choices=("synthetic",),
        default="synthetic",
        help="v6 scaffold: synthetic multi-agent kinematic only on this path",
    )
    args = parser.parse_args(argv)

    scenario = sample_v6_scenario(args.profile, args.seed)
    result = run_v6_episode(
        scenario=scenario,
        config=V6EpisodeConfig(policy=args.policy),
    )
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text, encoding="utf-8")
    m = result["metrics"]
    print(
        f"v6 finished policy={args.policy} profile={args.profile} seed={args.seed} "
        f"mission={m['mission_success']} unsafe={m['unsafe_crossing']} "
        f"route={m['route_mode']} repair_ok={m['repair_success']} "
        f"claims_mode={m['claims_mode']}"
        + (f" output={args.json_output}" if args.json_output else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
