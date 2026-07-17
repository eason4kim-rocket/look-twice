#!/usr/bin/env python3
"""Physics diff-drive URDF acceptance smoke (Genesis).

Loads carrier/scout URDFs, checks continuous wheel joints exist, and attempts
a short Genesis scene load when available. Full 20-seed waypoint bar is logged
as pass/fail honestly.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_urdf(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    joints = []
    for j in root.findall("joint"):
        joints.append({"name": j.get("name"), "type": j.get("type")})
    continuous = [j for j in joints if j["type"] == "continuous"]
    return {
        "path": str(path),
        "n_joints": len(joints),
        "continuous_wheels": continuous,
        "ok": len(continuous) >= 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--try-genesis", action="store_true")
    args = parser.parse_args()
    robots = list((ROOT / "assets" / "robots").glob("diff_drive_*.urdf"))
    reports = [inspect_urdf(p) for p in sorted(robots)]
    genesis = {"attempted": False}
    if args.try_genesis:
        genesis["attempted"] = True
        try:
            import genesis as gs
            import numpy as np

            gs.init(backend=gs.amdgpu, logging_level="warning")
            scene = gs.Scene(show_viewer=False)
            loaded = []
            for p in sorted(robots):
                try:
                    ent = scene.add_entity(gs.morphs.URDF(file=str(p), pos=(0, 0, 0.15)))
                    loaded.append({"file": p.name, "loaded": True})
                except Exception as exc:
                    loaded.append({"file": p.name, "loaded": False, "error": str(exc)})
            try:
                scene.build()
                genesis["build"] = True
            except Exception as exc:
                genesis["build"] = False
                genesis["build_error"] = str(exc)
            genesis["entities"] = loaded
        except Exception as exc:
            genesis["error"] = str(exc)

    # Waypoint bar: not claiming pass without real wheel control loop.
    waypoint = {
        "criterion": "20 seeds reach all viewpoints, err<0.10m, yaw<8deg, zero collision on clear",
        "status": "not_run_full_bar",
        "note": (
            "URDFs and continuous wheel joints are present. Full differential-drive "
            "PD control acceptance requires a dedicated physics backend integration; "
            "large-scale matrices continue on batched kinematic and must not claim "
            "true wheel dynamics in video."
        ),
    }
    out = {
        "urdfs": reports,
        "all_urdf_ok": all(r["ok"] for r in reports),
        "genesis": genesis,
        "waypoint_acceptance": waypoint,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["all_urdf_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
