#!/usr/bin/env python3
"""Minimal Genesis physics validation: oracle truth == geometry == collision.

8 deterministic force-corridor episodes (no vision policy):

  A blocked × force A → must contact / unsafe-ish fail
  A blocked × force B → must no contact
  B blocked × force B → must contact
  B blocked × force A → must no contact

Each class uses 2 seeds. Exit 0 only if all pass world_alignment and
contact expectations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _pick_seeds() -> dict[str, list[int]]:
    """Find seeds with exclusive A or B block from independent-noise."""
    from v6_scenario import sample_v6_scenario

    a_only: list[int] = []
    b_only: list[int] = []
    for seed in range(95000, 95200):
        o = sample_v6_scenario("independent-noise", seed).oracle_context
        a = bool(o["corridor_a_blocked_initial"])
        b = bool(o["corridor_b_blocked_initial"])
        if a and not b:
            a_only.append(seed)
        elif b and not a:
            b_only.append(seed)
        if len(a_only) >= 2 and len(b_only) >= 2:
            break
    return {"a_only": a_only[:2], "b_only": b_only[:2]}


def _worker_payload(seed: int, force_corridor: str, device: str, out: str) -> int:
    """One-process worker (fresh Genesis init)."""
    from v6_scenario import sample_v6_scenario

    scenario = sample_v6_scenario("independent-noise", seed)
    import genesis as gs

    gs.init(backend=gs.amdgpu, logging_level="warning")
    from v6_genesis_runtime import V6GenesisRuntime

    runtime = V6GenesisRuntime(scenario, motion_backend="kinematic", device=device)
    try:
        audit = runtime.world_alignment_audit()
        region = next(
            c["region"]
            for c in scenario.public_context["corridors"]
            if c["id"] == force_corridor
        )
        cy = 0.5 * (float(region[2]) + float(region[3]))
        waypoints = [
            (-0.55, cy),
            (float(region[0]) - 0.05, cy),
            (0.5 * (float(region[0]) + float(region[1])), cy),
            (float(region[1]) + 0.1, cy),
        ]
        contacts = 0
        reached_all = True
        segments = []
        for wp in waypoints:
            res = runtime.move_agent_to(
                "carrier",
                wp,
                risk_gated=False,
                allow_without_admit=True,
                admitted=True,
            )
            segments.append(res.to_dict())
            contacts += int(res.collision_count)
            if not res.reached:
                reached_all = False
                break
        oracle = scenario.oracle_context
        truth_blocked = bool(
            oracle["corridor_a_blocked_initial"]
            if force_corridor == "corridor_a"
            else oracle["corridor_b_blocked_initial"]
        )
        expect_contact = truth_blocked
        had_contact = contacts > 0 or any(
            "obstacle" in str(s.get("reason") or "") for s in segments
        )
        if expect_contact:
            physics_ok = bool(had_contact or not reached_all)
        else:
            physics_ok = bool((not had_contact) and reached_all)
        result = {
            "seed": seed,
            "force_corridor": force_corridor,
            "truth_blocked": truth_blocked,
            "expect_contact": expect_contact,
            "had_contact": had_contact,
            "contacts": contacts,
            "reached_all": reached_all,
            "physics_ok": physics_ok,
            "world_alignment": audit,
            "world_alignment_passed": bool(audit.get("world_alignment_passed")),
            "segments": segments,
            "oracle": {
                "a": oracle["corridor_a_blocked_initial"],
                "b": oracle["corridor_b_blocked_initial"],
                "obstacles": oracle.get("true_obstacle_xy_list"),
            },
        }
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(
            f"align={result['world_alignment_passed']} physics_ok={physics_ok} "
            f"contact={had_contact} truth_blocked={truth_blocked}",
            flush=True,
        )
        return 0 if result["world_alignment_passed"] and physics_ok else 1
    finally:
        runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--worker-seed", type=int, default=None)
    parser.add_argument("--worker-corridor", default=None)
    parser.add_argument("--worker-out", type=Path, default=None)
    args = parser.parse_args()

    # Subprocess worker entry.
    if args.worker_seed is not None:
        assert args.worker_corridor and args.worker_out
        return _worker_payload(
            args.worker_seed, args.worker_corridor, args.device, str(args.worker_out)
        )

    import subprocess

    args.out_dir.mkdir(parents=True, exist_ok=True)
    seeds = _pick_seeds()
    cases = []
    for seed in seeds["a_only"]:
        cases.append((seed, "corridor_a", "A_blocked_force_A"))
        cases.append((seed, "corridor_b", "A_blocked_force_B"))
    for seed in seeds["b_only"]:
        cases.append((seed, "corridor_b", "B_blocked_force_B"))
        cases.append((seed, "corridor_a", "B_blocked_force_A"))

    rows = []
    for seed, corridor, label in cases[:8]:
        out = args.out_dir / f"{label}__{seed}.json"
        print(f"RUN {label} seed={seed} force={corridor}", flush=True)
        cmd = [
            args.python,
            str(Path(__file__).resolve()),
            "--out-dir",
            str(args.out_dir),
            "--device",
            args.device,
            "--worker-seed",
            str(seed),
            "--worker-corridor",
            corridor,
            "--worker-out",
            str(out),
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env.setdefault("PYOPENGL_PLATFORM", "egl")
        log = out.with_suffix(".log")
        with log.open("w", encoding="utf-8") as handle:
            subprocess.run(
                cmd, cwd=str(ROOT), env=env, stdout=handle, stderr=subprocess.STDOUT, check=False
            )
        if not out.is_file():
            rows.append(
                {
                    "label": label,
                    "seed": seed,
                    "force_corridor": corridor,
                    "world_alignment_passed": False,
                    "physics_ok": False,
                    "error": "no_output",
                }
            )
            continue
        r = json.loads(out.read_text(encoding="utf-8"))
        rows.append({"label": label, **{k: r[k] for k in r if k != "segments"}})
        print(
            f"  align={r['world_alignment_passed']} physics_ok={r['physics_ok']} "
            f"contact={r['had_contact']} truth_blocked={r['truth_blocked']}",
            flush=True,
        )

    n = len(rows)
    n_align = sum(1 for r in rows if r.get("world_alignment_passed"))
    n_phys = sum(1 for r in rows if r.get("physics_ok"))
    summary = {
        "schema_version": "look-twice.v7-physics-world-alignment/v1",
        "n": n,
        "world_alignment_passed": n_align,
        "physics_ok": n_phys,
        "all_passed": n_align == n and n_phys == n and n >= 8,
        "seeds": seeds,
        "rows": rows,
    }
    (args.out_dir / "physics_alignment_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    return 0 if summary["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
