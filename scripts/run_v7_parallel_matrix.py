#!/usr/bin/env python3
"""Process-isolated v7 matrix runner (intended for remote GPU)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 64:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return "episode/v7" in str(payload.get("schema_version") or "") and isinstance(
        payload.get("metrics"), dict
    )


def _run_one(payload: dict[str, Any]) -> dict[str, Any]:
    stem = payload["stem"]
    output = Path(payload["output"])
    log = Path(payload["log"])
    if _valid(output):
        return {"stem": stem, "status": "skipped", "seconds": 0.0, "returncode": 0}
    cmd = [
        payload["python"],
        str(ROOT / "src" / "look_twice_v7.py"),
        "--runtime",
        payload["runtime"],
        "--motion-backend",
        payload["motion"],
        "--policy",
        payload["policy"],
        "--profile",
        payload["profile"],
        "--seed",
        str(payload["seed"]),
        "--device",
        payload["device"],
        "--vision-backend",
        payload["vision_backend"],
        "--json-output",
        str(output),
    ]
    if payload.get("vision_checkpoint"):
        cmd.extend(["--vision-checkpoint", str(payload["vision_checkpoint"])])
    if payload.get("vision_conformal_artifact"):
        cmd.extend(
            ["--vision-conformal-artifact", str(payload["vision_conformal_artifact"])]
        )
    if payload.get("repair_required"):
        cmd.append("--repair-required")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("PYOPENGL_PLATFORM", "egl")
    env.setdefault("PATH", "/opt/venv/bin:" + env.get("PATH", ""))
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter() - started
    ok = proc.returncode == 0 and _valid(output)
    return {
        "stem": stem,
        "status": "ok" if ok else "fail",
        "seconds": elapsed,
        "returncode": proc.returncode,
        "log": str(log),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--policies",
        nargs="+",
        default=["naive", "purify-passive", "purify-active-vision"],
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["independent-noise", "shared-occlusion", "evidence-echo"],
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(90000, 90005)))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--runtime", default="genesis", choices=("genesis", "synthetic"))
    parser.add_argument("--motion", default="kinematic")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--vision-backend",
        default="heuristic_rgb_proxy",
        choices=("heuristic_rgb_proxy", "torch_corridor_head"),
    )
    parser.add_argument("--vision-checkpoint", default="")
    parser.add_argument(
        "--vision-conformal-artifact",
        default="",
        help="conformal_artifact.json (required for torch_corridor_head)",
    )
    parser.add_argument(
        "--repair-required",
        action="store_true",
        help="Pass --repair-required to look_twice_v7 (paired passive contract).",
    )
    args = parser.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    log_dir = out / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    work: list[dict[str, Any]] = []
    for policy in args.policies:
        for profile in args.profiles:
            for seed in args.seeds:
                stem = f"{policy}__{profile}__{seed}"
                work.append(
                    {
                        "stem": stem,
                        "policy": policy,
                        "profile": profile,
                        "seed": seed,
                        "python": args.python,
                        "runtime": args.runtime,
                        "motion": args.motion,
                        "device": args.device,
                        "vision_backend": args.vision_backend,
                        "vision_checkpoint": args.vision_checkpoint or "",
                        "vision_conformal_artifact": args.vision_conformal_artifact or "",
                        "repair_required": bool(args.repair_required),
                        "output": str(out / f"{stem}.json"),
                        "log": str(log_dir / f"{stem}.log"),
                    }
                )

    print(
        f"v7 parallel matrix jobs={len(work)} workers={args.workers} "
        f"runtime={args.runtime} vision={args.vision_backend} device={args.device}",
        flush=True,
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(_run_one, item) for item in work]
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            print(
                f"[{result['status']}] {result['stem']} "
                f"{result['seconds']:.1f}s rc={result['returncode']}",
                flush=True,
            )
    summary = {
        "schema_version": "look-twice.v7-parallel-matrix/v1",
        "workers": args.workers,
        "jobs": len(work),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "wall_seconds": time.perf_counter() - started,
        "runtime": args.runtime,
        "device": args.device,
        "vision_backend": args.vision_backend,
        "vision_checkpoint": args.vision_checkpoint or None,
        "vision_conformal_artifact": args.vision_conformal_artifact or None,
        "repair_required": bool(args.repair_required),
        "results": sorted(results, key=lambda r: r["stem"]),
    }
    (out / "parallel_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, indent=2))
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
