#!/usr/bin/env python3
"""Roll up v6 GPU multi-policy episode matrices."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    by_pol: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "n": 0,
            "mission": 0,
            "unsafe": 0,
            "repair_attempted": 0,
            "repair_success": 0,
            "direct": 0,
            "detour": 0,
            "rgbd": 0,
        }
    )
    for path in sorted(args.input_dir.glob("*__*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        m = d.get("metrics") or {}
        parts = path.stem.split("__")
        if len(parts) < 3:
            continue
        pol, profile, seed_s = parts[0], parts[1], parts[2]
        row = {
            "file": path.name,
            "policy": pol,
            "profile": profile,
            "seed": int(seed_s),
            "claims_mode": m.get("claims_mode"),
            "device": m.get("device"),
            "mission": bool(m.get("mission_success")),
            "unsafe": bool(m.get("unsafe_crossing")),
            "carrier_reached_goal": bool(m.get("carrier_reached_goal")),
            "payload_delivered": bool(m.get("payload_delivered")),
            "route_mode": m.get("route_mode"),
            "repair_attempted": bool(m.get("repair_attempted")),
            "repair_success": bool(m.get("repair_success")),
            "observation_count": m.get("observation_count"),
            "n_evidence_requests": len(d.get("evidence_request_receipts") or []),
            "n_rgbd_audits": len(d.get("rgbd_observation_audits") or []),
        }
        rows.append(row)
        b = by_pol[pol]
        b["n"] += 1
        b["mission"] += int(row["mission"])
        b["unsafe"] += int(row["unsafe"])
        b["repair_attempted"] += int(row["repair_attempted"])
        b["repair_success"] += int(row["repair_success"])
        b["direct"] += int(row["route_mode"] == "direct")
        b["detour"] += int(row["route_mode"] == "detour")
        b["rgbd"] += int(
            str(row["claims_mode"] or "").startswith("genesis_rgbd")
        )

    modes = sorted({r["claims_mode"] for r in rows if r["claims_mode"]})
    purify_unsafe = sum(
        r["unsafe"] for r in rows if r["policy"] in ("purify-passive", "purify-active")
    )
    rollup = {
        "schema_version": "look-twice.v6-gpu-rollup/v1",
        "n": len(rows),
        "claims_modes": modes,
        "by_policy": {k: dict(v) for k, v in sorted(by_pol.items())},
        "purify_unsafe_total": purify_unsafe,
        "purify_unsafe_zero": purify_unsafe == 0,
        "all_rgbd": all(
            str(r["claims_mode"] or "").startswith("genesis_rgbd") for r in rows
        ),
        "rows": rows,
    }
    out = args.output or (args.input_dir / "rollup.json")
    out.write_text(json.dumps(rollup, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: rollup[k] for k in rollup if k != "rows"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
