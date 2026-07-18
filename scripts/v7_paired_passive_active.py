#!/usr/bin/env python3
"""Paired passive vs purify-active-vision eval on a fixed seed list.

Uses the real look_twice_v7 closed-loop entry (synthetic by default for CI;
pass --runtime genesis --device cuda:0 on GPU).

With --repair-required (default on for genesis), both policies share a contract
that denies until an independent scout/side-view vision clear root exists —
so Active can prove deny→repair→direct while Passive stays fail-closed detour.
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
    repair_required: bool,
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
    if repair_required:
        cmd.append("--repair-required")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("PYOPENGL_PLATFORM", "egl")
    log = out.with_suffix(".log")
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run(
            cmd, cwd=str(ROOT), env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
        )
    return json.loads(out.read_text(encoding="utf-8"))


def _episode_flags(d: dict) -> dict:
    m = d.get("metrics") or {}
    env = d.get("environment") or {}
    conf = d.get("configuration") or {}
    vision_sources = m.get("vision_sources") or []
    if not vision_sources:
        vision_sources = sorted(
            {
                str(a.get("vision_source"))
                for a in (d.get("vision_audits") or d.get("rgbd_observation_audits") or [])
                if a.get("kind") == "vision_proposal_v7" and a.get("vision_source")
            }
        )
    return {
        "mission": bool(m.get("mission_success")),
        "unsafe": bool(m.get("unsafe_crossing")),
        "repair_attempted": bool(m.get("repair_attempted")),
        "repair_success": bool(m.get("repair_success")),
        "route_mode": m.get("route_mode"),
        "initial_gate_denied": bool(m.get("initial_gate_denied")),
        "scout_viewpoint_changed": bool(m.get("scout_viewpoint_changed")),
        "new_capture_root_added": bool(m.get("new_capture_root_added")),
        "repair_chain_complete": bool(m.get("repair_chain_complete")),
        "vision_sources": list(vision_sources),
        "device": m.get("device") or conf.get("device") or env.get("device"),
        "runtime": env.get("runtime"),
        "formal_result_eligible": env.get("formal_result_eligible"),
        "observation_count": m.get("observation_count"),
        "vision_claim_count": m.get("vision_claim_count"),
    }


def active_gpu_success(flags: dict, *, require_genesis_rgb: bool, require_cuda: bool) -> bool:
    if not (
        flags["initial_gate_denied"]
        and flags["repair_attempted"]
        and flags["scout_viewpoint_changed"]
        and flags["new_capture_root_added"]
        and flags["repair_success"]
        and flags["route_mode"] == "direct"
        and not flags["unsafe"]
    ):
        return False
    if require_genesis_rgb and "genesis_rgb" not in (flags.get("vision_sources") or []):
        return False
    if require_cuda and not str(flags.get("device") or "").startswith("cuda"):
        return False
    return True


def passive_ok(flags: dict) -> bool:
    return (
        flags["initial_gate_denied"]
        and not flags["repair_attempted"]
        and flags["route_mode"] == "detour"
        and not flags["unsafe"]
    )


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
    parser.add_argument(
        "--repair-required",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Force side-view vision contract for both policies (default: on for genesis).",
    )
    parser.add_argument(
        "--strict-genesis",
        action="store_true",
        help="Apply GPU-validated repair gates (genesis_rgb + cuda + chain fields).",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    repair_required = args.repair_required
    if repair_required is None:
        repair_required = args.runtime == "genesis" or args.strict_genesis

    require_genesis_rgb = bool(args.strict_genesis or args.runtime == "genesis")
    require_cuda = bool(args.strict_genesis or args.runtime == "genesis")

    rows = []
    label_hist: Counter[str] = Counter()
    by = defaultdict(
        lambda: {
            "n": 0,
            "mission": 0,
            "unsafe": 0,
            "repair_success": 0,
            "direct": 0,
            "detour": 0,
            "initial_gate_denied": 0,
            "repair_attempted": 0,
            "scout_viewpoint_changed": 0,
            "new_capture_root_added": 0,
            "repair_chain_complete": 0,
            "gpu_repair_success": 0,
            "passive_contract_ok": 0,
        }
    )
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
                    repair_required=bool(repair_required),
                )
                m = d["metrics"]
                flags = _episode_flags(d)
                b = by[policy]
                b["n"] += 1
                b["mission"] += int(flags["mission"])
                b["unsafe"] += int(flags["unsafe"])
                b["repair_success"] += int(flags["repair_success"])
                if flags["route_mode"] == "direct":
                    b["direct"] += 1
                if flags["route_mode"] == "detour" or m.get("used_detour"):
                    b["detour"] += 1
                b["initial_gate_denied"] += int(flags["initial_gate_denied"])
                b["repair_attempted"] += int(flags["repair_attempted"])
                b["scout_viewpoint_changed"] += int(flags["scout_viewpoint_changed"])
                b["new_capture_root_added"] += int(flags["new_capture_root_added"])
                b["repair_chain_complete"] += int(flags["repair_chain_complete"])
                if policy == "purify-active-vision":
                    b["gpu_repair_success"] += int(
                        active_gpu_success(
                            flags,
                            require_genesis_rgb=require_genesis_rgb,
                            require_cuda=require_cuda,
                        )
                    )
                else:
                    b["passive_contract_ok"] += int(passive_ok(flags))
                for a in d.get("rgbd_observation_audits") or []:
                    if a.get("kind") == "vision_proposal_v7":
                        label_hist[str(a.get("value") or "?")] += 1
                rows.append(
                    {
                        "policy": policy,
                        "profile": profile,
                        "seed": seed,
                        **flags,
                    }
                )
                print(
                    f"{stem} mission={flags['mission']} unsafe={flags['unsafe']} "
                    f"repair={flags['repair_success']} route={flags['route_mode']} "
                    f"init_deny={flags['initial_gate_denied']} "
                    f"chain={flags['repair_chain_complete']} "
                    f"src={flags['vision_sources']} device={flags['device']}",
                    flush=True,
                )

    passive = by["purify-passive"]
    active = by["purify-active-vision"]
    n_pairs = max(1, len(args.profiles) * len(args.seeds))
    active_rate = active["gpu_repair_success"] / n_pairs
    passive_repair_rate = passive["repair_success"] / n_pairs
    improves = (
        active["unsafe"] == 0
        and passive["unsafe"] == 0
        and (
            active["repair_success"] > passive["repair_success"]
            or active["direct"] > passive["direct"]
            or active["gpu_repair_success"] > 0
        )
    )
    # Strict Genesis upgrade gate (user-specified).
    genesis_upgrade = (
        require_genesis_rgb
        and active["unsafe"] == 0
        and passive["unsafe"] == 0
        and active_rate >= 0.70
        and passive_repair_rate == 0.0
        and passive["direct"] == 0
        and active["gpu_repair_success"] >= int(0.70 * n_pairs)
        and passive["passive_contract_ok"] >= int(0.70 * n_pairs)
    )
    total_lab = sum(label_hist.values()) or 1
    dominant = max(label_hist.values()) / total_lab if label_hist else 1.0
    summary = {
        "schema_version": "look-twice.v7-paired-passive-active/v2",
        "runtime": args.runtime,
        "device": args.device,
        "vision_backend": args.vision_backend,
        "repair_required": bool(repair_required),
        "strict_genesis": bool(args.strict_genesis or args.runtime == "genesis"),
        "n_pairs": n_pairs,
        "profiles": list(args.profiles),
        "seeds": list(args.seeds),
        "by_policy": dict(by),
        "active_gpu_repair_rate": active_rate,
        "passive_repair_rate": passive_repair_rate,
        "improves_active_over_passive": improves,
        "genesis_upgrade_ready": genesis_upgrade,
        "thresholds": {
            "active_gpu_repair_rate_min": 0.70,
            "passive_repair_rate_max": 0.0,
            "unsafe_max": 0,
        },
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
    if args.runtime == "genesis" or args.strict_genesis:
        return 0 if genesis_upgrade else 2
    return 0 if improves and summary["vision_non_degenerate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
