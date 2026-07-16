#!/usr/bin/env python3
"""Roll up a v5 paired capability matrix (e.g. 3×6×5 = 90).

Honest metrics only — does not claim active is shorter/faster.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_rows(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("*__*.json")):
        if path.name in {"parallel_summary.json", "rollup.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        metrics = payload.get("metrics") or {}
        parts = path.stem.split("__")
        if len(parts) < 3:
            continue
        policy, profile, seed_s = parts[0], parts[1], parts[2]
        try:
            seed = int(seed_s)
        except ValueError:
            continue
        side_views = [
            {
                "previous": d.get("previous_viewpoint"),
                "selected": d.get("selected_viewpoint"),
                "actual_distance": d.get("actual_distance"),
                "viewpoint_changed": d.get("viewpoint_changed"),
            }
            for d in (payload.get("repair_decisions") or [])
            if d.get("action_kind_executed") == "side_view"
            and bool(d.get("viewpoint_changed"))
            and float(d.get("actual_distance") or 0.0) > 0.10
        ]
        rows.append(
            {
                "file": path.name,
                "policy": policy,
                "profile": profile,
                "seed": seed,
                "claims_mode": metrics.get("claims_mode"),
                "mission": bool(metrics.get("mission_success")),
                "nav": bool(metrics.get("nav_success")),
                "pick": bool(metrics.get("pick_success")),
                "unsafe": bool(metrics.get("unsafe_crossing")),
                "route_mode": metrics.get("route_mode") or "none",
                "direct_cross_success": bool(metrics.get("direct_cross_success")),
                "detour_success": bool(metrics.get("detour_success")),
                "wrong_detour": bool(metrics.get("wrong_detour")),
                "repair_attempted": bool(metrics.get("repair_attempted")),
                "repair_success": bool(metrics.get("repair_success")),
                "real_side_view_count": int(metrics.get("real_side_view_count") or 0),
                "path_length_total": float(metrics.get("path_length_total") or 0.0),
                "simulation_steps": int(metrics.get("simulation_steps") or 0),
                "initial_gate_admitted": bool(metrics.get("initial_gate_admitted")),
                "outcome": metrics.get("outcome"),
                "side_views": side_views,
            }
        )
    return rows


def _agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "n": 0,
            "mission": 0,
            "nav": 0,
            "pick": 0,
            "unsafe": 0,
            "wrong_detour": 0,
            "repair_attempted": 0,
            "repair_success": 0,
            "direct": 0,
            "detour": 0,
            "real_side_view": 0,
            "path_sum": 0.0,
            "steps_sum": 0,
        }
    )
    for row in rows:
        b = buckets[row["policy"]]
        b["n"] += 1
        for key in (
            "mission",
            "nav",
            "pick",
            "unsafe",
            "wrong_detour",
            "repair_attempted",
            "repair_success",
        ):
            b[key] += int(row[key])
        b["direct"] += int(row["route_mode"] == "direct")
        b["detour"] += int(row["route_mode"] == "detour")
        b["real_side_view"] += int(row["real_side_view_count"])
        b["path_sum"] += float(row["path_length_total"])
        b["steps_sum"] += int(row["simulation_steps"])
    out: dict[str, Any] = {}
    for policy, b in sorted(buckets.items()):
        n = max(1, b["n"])
        out[policy] = {
            **{k: b[k] for k in b if k not in {"path_sum", "steps_sum"}},
            "mean_path_length": b["path_sum"] / n,
            "mean_simulation_steps": b["steps_sum"] / n,
        }
    return out


def _by_profile_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    nested: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "n": 0,
                "mission": 0,
                "unsafe": 0,
                "wrong_detour": 0,
                "repair_success": 0,
                "direct": 0,
                "detour": 0,
            }
        )
    )
    for row in rows:
        cell = nested[row["profile"]][row["policy"]]
        cell["n"] += 1
        cell["mission"] += int(row["mission"])
        cell["unsafe"] += int(row["unsafe"])
        cell["wrong_detour"] += int(row["wrong_detour"])
        cell["repair_success"] += int(row["repair_success"])
        cell["direct"] += int(row["route_mode"] == "direct")
        cell["detour"] += int(row["route_mode"] == "detour")
    return {p: dict(pols) for p, pols in sorted(nested.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    rows = _load_rows(args.input_dir)
    claims = sorted({r["claims_mode"] for r in rows if r["claims_mode"]})
    rollup = {
        "schema_version": "look-twice.paired-capability-rollup/v1",
        "kind": "paired_capability_evaluation",
        "calibration": "smoke",
        "formal_gate_b": False,
        "n": len(rows),
        "claims_modes": claims,
        "by_policy": _agg(rows),
        "by_profile_policy": _by_profile_policy(rows),
        "narrative_constraint": (
            "Active trades extra observation cost for evidence repair and "
            "correct direct routing that removes wrong detours on clear worlds. "
            "Do not claim active is shorter or faster when path/steps are higher."
        ),
        "rows": rows,
    }
    text = json.dumps(rollup, indent=2) + "\n"
    out = args.output or (args.input_dir / "rollup.json")
    out.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "n": rollup["n"],
                "claims_modes": rollup["claims_modes"],
                "by_policy": rollup["by_policy"],
                "formal_gate_b": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
