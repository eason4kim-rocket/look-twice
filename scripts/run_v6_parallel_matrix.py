#!/usr/bin/env python3
"""Process-isolated v6 multi-policy matrix runner (remote GPU)."""

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
    return "episode/v6" in str(payload.get("schema_version") or "") and isinstance(
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
        str(ROOT / "src" / "look_twice_v6.py"),
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
        "--json-output",
        str(output),
    ]
    if payload.get("learned_checkpoint"):
        cmd.extend(["--learned-checkpoint", str(payload["learned_checkpoint"])])
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
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--policies",
        nargs="+",
        default=["naive", "purify-passive", "purify-active"],
    )
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
        "--seeds",
        type=int,
        nargs="+",
        default=list(range(90000, 90005)),
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--runtime", default="genesis", choices=("genesis", "synthetic"))
    parser.add_argument("--motion", default="kinematic")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--learned-checkpoint",
        default="",
        help="Optional checkpoint path for learned/dagger policies",
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
                        "learned_checkpoint": args.learned_checkpoint or "",
                        "output": str(out / f"{stem}.json"),
                        "log": str(log_dir / f"{stem}.log"),
                    }
                )

    print(
        f"v6 parallel matrix jobs={len(work)} workers={args.workers} "
        f"runtime={args.runtime} device={args.device}",
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
        "schema_version": "look-twice.v6-parallel-matrix/v1",
        "workers": args.workers,
        "jobs": len(work),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "wall_seconds": time.perf_counter() - started,
        "runtime": args.runtime,
        "device": args.device,
        "results": sorted(results, key=lambda r: r["stem"]),
    }
    (out / "parallel_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, indent=2))
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
