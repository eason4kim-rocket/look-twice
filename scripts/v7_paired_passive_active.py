#!/usr/bin/env python3
"""Paired passive vs purify-active-vision eval on a fixed seed list.

Uses the real look_twice_v7 closed-loop entry (synthetic by default for CI;
pass --runtime genesis on GPU). Writes by-policy rollup + vision label hist.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
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
    vision_backend: str,
    vision_checkpoint: str,
    out: Path,
) -> dict:
    if out.is_file() and out.stat().st_size > 64:
        try:
            d = json.loads(out.read_text(encoding="utf-8"))
            if "episode/v7" in str(d.get("schema_version") or ""):
                return d
        except json.JSONDecodeError:
            pass
    cmd = [
        python,
        str(ROOT / "src" / "look_twice_v7.py"),
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
        "--vision-backend",
        vision_backend,
        "--json-output",
        str(out),
    ]
    if vision_checkpoint:
        cmd.extend(["--vision-checkpoint", vision_checkpoint])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("PYOPENGL_PLATFORM", "egl")
    log = out.with_suffix(".log")
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run(
            cmd, cwd=str(ROOT), env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
        )
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--runtime", default="synthetic", choices=("synthetic", "genesis"))
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--vision-backend",
        default="heuristic_rgb_proxy",
        choices=("heuristic_rgb_proxy", "torch_corridor_head"),
    )
    parser.add_argument("--vision-checkpoint", default="")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["independent-noise", "shared-occlusion", "evidence-echo"],
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=list(range(95000, 95010)),
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    label_hist: Counter[str] = Counter()
    by = defaultdict(lambda: {
        "n": 0,
        "mission": 0,
        "unsafe": 0,
        "repair_success": 0,
        "direct": 0,
        "detour": 0,
    })
    for profile in args.profiles:
        for seed in args.seeds:
            for policy in ("purify-passive", "purify-active-vision"):
                stem = f"{policy}__{profile}__{seed}"
                out = args.out_dir / f"{stem}.json"
                d = run_one(
                    python=args.python,
                    policy=policy,
                    profile=profile,
                    seed=seed,
                    runtime=args.runtime,
                    device=args.device,
                    vision_backend=args.vision_backend,
                    vision_checkpoint=args.vision_checkpoint,
                    out=out,
                )
                m = d["metrics"]
                b = by[policy]
                b["n"] += 1
                b["mission"] += int(bool(m.get("mission_success")))
                b["unsafe"] += int(bool(m.get("unsafe_crossing")))
                b["repair_success"] += int(bool(m.get("repair_success")))
                if m.get("route_mode") == "direct":
                    b["direct"] += 1
                if m.get("route_mode") == "detour" or m.get("used_detour"):
                    b["detour"] += 1
                for a in d.get("rgbd_observation_audits") or []:
                    if a.get("kind") == "vision_proposal_v7":
                        label_hist[str(a.get("value") or "?")] += 1
                rows.append(
                    {
                        "policy": policy,
                        "profile": profile,
                        "seed": seed,
                        "mission": m.get("mission_success"),
                        "unsafe": m.get("unsafe_crossing"),
                        "repair_success": m.get("repair_success"),
                        "route_mode": m.get("route_mode"),
                        "vision_claim_count": m.get("vision_claim_count"),
                    }
                )
                print(
                    f"{stem} mission={m.get('mission_success')} unsafe={m.get('unsafe_crossing')} "
                    f"repair={m.get('repair_success')} route={m.get('route_mode')}",
                    flush=True,
                )

    passive = by["purify-passive"]
    active = by["purify-active-vision"]
    improves = (
        active["unsafe"] == 0
        and passive["unsafe"] == 0
        and (
            active["repair_success"] > passive["repair_success"]
            or active["direct"] > passive["direct"]
        )
    )
    total_lab = sum(label_hist.values()) or 1
    dominant = max(label_hist.values()) / total_lab if label_hist else 1.0
    summary = {
        "schema_version": "look-twice.v7-paired-passive-active/v1",
        "runtime": args.runtime,
        "vision_backend": args.vision_backend,
        "n_pairs": len(args.profiles) * len(args.seeds),
        "by_policy": dict(by),
        "improves_active_over_passive": improves,
        "vision_label_hist": dict(label_hist),
        "vision_dominant_frac": dominant,
        "vision_non_degenerate": dominant < 0.95 and len(label_hist) >= 2,
        "rows": rows,
    }
    (args.out_dir / "paired_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "vision_label_hist.json").write_text(
        json.dumps(
            {
                "hist": dict(label_hist),
                "dominant_frac": dominant,
                "non_degenerate": summary["vision_non_degenerate"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    return 0 if improves and summary["vision_non_degenerate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
