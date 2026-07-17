#!/usr/bin/env python3
"""Paired promotion eval: heuristic active vs learned/dagger on locked seeds.

Fail-closed: promote only if learned matches/exceeds heuristic on
mission_success and repair_success with unsafe==0, and never worse on unsafe.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_one(
    *,
    python: str,
    policy: str,
    profile: str,
    seed: int,
    runtime: str,
    device: str,
    out: Path,
    checkpoint: str | None,
) -> dict:
    if out.is_file() and out.stat().st_size > 64:
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    cmd = [
        python,
        str(ROOT / "src" / "look_twice_v6.py"),
        "--policy",
        policy,
        "--profile",
        profile,
        "--seed",
        str(seed),
        "--runtime",
        runtime,
        "--device",
        device,
        "--json-output",
        str(out),
    ]
    if checkpoint:
        cmd.extend(["--learned-checkpoint", checkpoint])
    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "PYTHONPATH": str(ROOT / "src"),
        "PYOPENGL_PLATFORM": "egl",
    }
    log = out.with_suffix(".log")
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--runtime", default="synthetic", choices=("synthetic", "genesis"))
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(90000, 90020)))
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=[
            "independent-noise",
            "shared-occlusion",
            "evidence-echo",
            "time-skew",
            "dynamic-change",
            "comm-fault",
        ],
    )
    parser.add_argument(
        "--learned-policy",
        default="purify-active-dagger",
        choices=("purify-active-learned", "purify-active-dagger"),
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for profile in args.profiles:
        for seed in args.seeds:
            h_path = args.out_dir / f"heuristic__{profile}__{seed}.json"
            l_path = args.out_dir / f"learned__{profile}__{seed}.json"
            h = run_one(
                python=args.python,
                policy="purify-active",
                profile=profile,
                seed=seed,
                runtime=args.runtime,
                device=args.device,
                out=h_path,
                checkpoint=None,
            )
            l = run_one(
                python=args.python,
                policy=args.learned_policy,
                profile=profile,
                seed=seed,
                runtime=args.runtime,
                device=args.device,
                out=l_path,
                checkpoint=str(args.checkpoint),
            )
            hm, lm = h["metrics"], l["metrics"]
            rows.append(
                {
                    "profile": profile,
                    "seed": seed,
                    "h_mission": hm["mission_success"],
                    "l_mission": lm["mission_success"],
                    "h_unsafe": hm["unsafe_crossing"],
                    "l_unsafe": lm["unsafe_crossing"],
                    "h_repair": hm.get("repair_success"),
                    "l_repair": lm.get("repair_success"),
                    "h_route": hm.get("route_mode"),
                    "l_route": lm.get("route_mode"),
                }
            )
            print(
                f"{profile}:{seed} H m={hm['mission_success']} r={hm.get('repair_success')} "
                f"L m={lm['mission_success']} r={lm.get('repair_success')}",
                flush=True,
            )

    n = len(rows)
    h_mission = sum(1 for r in rows if r["h_mission"])
    l_mission = sum(1 for r in rows if r["l_mission"])
    h_unsafe = sum(1 for r in rows if r["h_unsafe"])
    l_unsafe = sum(1 for r in rows if r["l_unsafe"])
    h_repair = sum(1 for r in rows if r["h_repair"])
    l_repair = sum(1 for r in rows if r["l_repair"])
    h_direct = sum(1 for r in rows if r["h_route"] == "direct")
    l_direct = sum(1 for r in rows if r["l_route"] == "direct")

    promote = (
        l_unsafe == 0
        and l_mission >= h_mission
        and l_repair >= h_repair
        and (l_mission > h_mission or l_repair > h_repair or l_direct >= h_direct)
    )
    summary = {
        "n": n,
        "heuristic": {
            "mission": h_mission,
            "unsafe": h_unsafe,
            "repair_success": h_repair,
            "direct": h_direct,
        },
        "learned": {
            "mission": l_mission,
            "unsafe": l_unsafe,
            "repair_success": l_repair,
            "direct": l_direct,
            "policy": args.learned_policy,
            "checkpoint": str(args.checkpoint),
        },
        "promote": promote,
        "primary_remains": "purify-active" if not promote else args.learned_policy,
        "rule": "l_unsafe==0 and mission/repair not worse; improve mission or repair or direct",
        "rows": rows,
    }
    (args.out_dir / "promotion_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
