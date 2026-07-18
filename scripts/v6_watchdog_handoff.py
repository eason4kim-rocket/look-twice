#!/usr/bin/env python3
"""Watch v6 mega-matrices; on completion write finals + handoff flag for v7.

Designed to run under nohup on the GPU machine. Does NOT reduce quality:
only observes existing genesis outputs and aggregates metrics.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("LOOK_TWICE_ROOT", "/workspace/look-twice-v6"))
OUT = ROOT / "outputs" / "v6"
HANDOFF = OUT / "V6_COMPLETE_HANDOFF.json"
FINAL = OUT / "MATRIX_FINAL.json"
STATUS_MD = OUT / "V6_MATRIX_FINAL_STATUS.md"

TARGETS = {
    "physics-180": 180,
    "formal-locked-3x6x100": 1800,
    "formal-learned-3x6x100": 1800,
    "ood-3x2x500": 3000,
}


def count_json(name: str) -> int:
    d = OUT / name
    if not d.exists():
        return 0
    return len([p for p in d.glob("*.json") if "parallel" not in p.name])


def has_summary(name: str) -> bool:
    return (OUT / name / "parallel_summary.json").exists()


def matrix_done(name: str, target: int) -> bool:
    if has_summary(name):
        return True
    # complete counts with no live workers for this matrix
    if count_json(name) < target:
        return False
    # if target reached, treat as done even if summary lagging
    return True


def all_done() -> bool:
    return all(matrix_done(n, t) for n, t in TARGETS.items())


def summarize_dir(name: str) -> dict:
    d = OUT / name
    by = defaultdict(lambda: {
        "n": 0,
        "mission": 0,
        "unsafe": 0,
        "repair_success": 0,
        "direct": 0,
        "detour": 0,
    })
    claims_modes = defaultdict(int)
    n = 0
    bad = 0
    for p in d.glob("*.json"):
        if "parallel" in p.name:
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            m = payload.get("metrics") or {}
        except Exception:
            bad += 1
            continue
        n += 1
        pol = str(m.get("policy") or "?")
        b = by[pol]
        b["n"] += 1
        b["mission"] += int(bool(m.get("mission_success")))
        b["unsafe"] += int(bool(m.get("unsafe_crossing")))
        b["repair_success"] += int(bool(m.get("repair_success")))
        route = m.get("route_mode")
        if route == "direct":
            b["direct"] += 1
        if route == "detour" or m.get("used_detour"):
            b["detour"] += 1
        claims_modes[str(m.get("claims_mode") or "?")] += 1
    summary_path = d / "parallel_summary.json"
    parallel = None
    if summary_path.exists():
        try:
            parallel = json.loads(summary_path.read_text(encoding="utf-8"))
            parallel = {k: parallel[k] for k in parallel if k != "results"}
        except Exception as exc:
            parallel = {"error": str(exc)}
    return {
        "n_episodes": n,
        "bad_json": bad,
        "target": TARGETS.get(name),
        "by_policy": dict(by),
        "claims_modes": dict(claims_modes),
        "parallel_summary": parallel,
    }


def write_finals() -> dict:
    matrices = {name: summarize_dir(name) for name in TARGETS}
    handoff = {
        "schema_version": "look-twice.v6-complete-handoff/v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "quality_lock": {
            "runtime": "genesis",
            "no_seed_cut": True,
            "no_synthetic_downgrade": True,
        },
        "matrices": matrices,
        "next": {
            "v7_theme": "Vision-Grounded Evidence Contracts",
            "v7_priority": [
                "RGB/VLM or lightweight vision head -> Claim v2",
                "geometry vs vision conflict => fail-closed deny",
                "Scout repair targets high visual uncertainty",
                "Keep Purify gate as authorizer; model is proposer only",
                "Do NOT replace v6 gate with end-to-end VLA",
            ],
            "agent_instructions": (
                "Archive GPU finals to results/; update STATUS.md; "
                "scaffold docs/V7_DESIGN.md + minimal vision claim adapter; "
                "do not open contest PR yet."
            ),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    FINAL.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    HANDOFF.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# v6 matrix final status (auto)",
        "",
        f"- completed_at: `{handoff['completed_at']}`",
        "- quality: genesis RGB-D, no seed cut",
        "",
        "| matrix | n | target |",
        "| --- | ---: | ---: |",
    ]
    for name, block in matrices.items():
        lines.append(f"| {name} | {block['n_episodes']} | {block['target']} |")
    lines.extend(["", "## by_policy (each matrix)", ""])
    for name, block in matrices.items():
        lines.append(f"### {name}")
        lines.append("```json")
        lines.append(json.dumps(block["by_policy"], indent=2))
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## v7 handoff",
            "- Theme: Vision-Grounded Evidence Contracts",
            "- Model proposes claims; Purify still authorizes",
            "- Next agent: archive + V7_DESIGN scaffold",
            "",
        ]
    )
    STATUS_MD.write_text("\n".join(lines), encoding="utf-8")
    return handoff


def main() -> int:
    poll = int(os.environ.get("V6_WATCH_POLL_SEC", "180"))
    print(f"v6 watchdog start root={ROOT} poll={poll}s", flush=True)
    while True:
        status = {
            name: {
                "n": count_json(name),
                "target": tgt,
                "summary": has_summary(name),
                "done": matrix_done(name, tgt),
            }
            for name, tgt in TARGETS.items()
        }
        (OUT / "WATCHDOG_PROGRESS.json").write_text(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "status": status,
                    "all_done": all_done(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        parts = [
            f"{n}:{status[n]['n']}/{status[n]['target']}"
            + ("*" if status[n]["done"] else "")
            for n in TARGETS
        ]
        print("WATCH " + " ".join(parts), flush=True)
        if all_done():
            handoff = write_finals()
            print("V6_COMPLETE", handoff["completed_at"], flush=True)
            return 0
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())
