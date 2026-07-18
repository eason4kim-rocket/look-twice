#!/usr/bin/env python3
"""Summarize v7 episode JSON dir → by_policy metrics (run on GPU)."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    by = defaultdict(
        lambda: {
            "n": 0,
            "mission": 0,
            "unsafe": 0,
            "repair_success": 0,
            "direct": 0,
            "detour": 0,
            "vision_clear": 0,
            "vision_blocked": 0,
            "modality_conflict_events": 0,
            "vision_sources": defaultdict(int),
        }
    )
    n = 0
    for p in sorted(args.input_dir.glob("*.json")):
        if p.name.startswith("parallel") or p.name.endswith("summary.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            m = d.get("metrics") or {}
        except Exception:
            continue
        n += 1
        pol = str(m.get("policy") or "?")
        b = by[pol]
        b["n"] += 1
        b["mission"] += int(bool(m.get("mission_success")))
        b["unsafe"] += int(bool(m.get("unsafe_crossing")))
        b["repair_success"] += int(bool(m.get("repair_success")))
        if m.get("route_mode") == "direct":
            b["direct"] += 1
        if m.get("route_mode") == "detour" or m.get("used_detour"):
            b["detour"] += 1
        b["vision_clear"] += int(m.get("vision_clear_proposals") or 0)
        b["vision_blocked"] += int(m.get("vision_blocked_proposals") or 0)
        b["modality_conflict_events"] += int(m.get("modality_conflict_events") or 0)
        for a in d.get("vision_audits") or d.get("rgbd_observation_audits") or []:
            if a.get("kind") == "vision_proposal_v7":
                b["vision_sources"][str(a.get("vision_source") or "?")] += 1

    # jsonify nested defaultdict
    out_by = {}
    for k, v in by.items():
        vv = dict(v)
        vv["vision_sources"] = dict(v["vision_sources"])
        out_by[k] = vv
    payload = {
        "schema_version": "look-twice.v7-matrix-summary/v1",
        "n_episodes": n,
        "by_policy": out_by,
        "input_dir": str(args.input_dir),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
