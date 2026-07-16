#!/usr/bin/env python3
"""Safe multi-process episode matrix runner for AMD GPU throughput.

Each worker launches a **separate process** of look_twice_v4/v5 (not in-process
fork). That isolates Genesis/ROCm state and avoids multi-context corruption.

Completion is file-based resume: existing valid JSON is skipped.
Default workers=2 for genesis (conservative); raise with --workers after a smoke.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Job:
    kind: str  # v4 | v5
    policy: str
    profile: str
    seed: int

    @property
    def stem(self) -> str:
        return f"{self.policy}__{self.profile}__{self.seed}"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _valid_episode(path: Path, kind: str) -> bool:
    if not path.is_file() or path.stat().st_size < 64:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    schema = str(payload.get("schema_version") or "")
    if kind == "v4" and "episode/v4" not in schema:
        return False
    if kind == "v5" and "episode/v5" not in schema:
        return False
    return isinstance(payload.get("metrics"), dict)


def _build_command(
    job: Job,
    *,
    python: str,
    output: Path,
    calibration: Path | None,
    purify_bin: Path,
    motion: str,
    device: str,
    log: Path,
) -> list[str]:
    if job.kind == "v4":
        entry = ROOT / "src" / "look_twice_v4.py"
        cmd = [
            python,
            str(entry),
            "--runtime",
            "genesis",
            "--motion-backend",
            motion,
            "--policy",
            job.policy,
            "--profile",
            job.profile,
            "--seed",
            str(job.seed),
            "--purify-bin",
            str(purify_bin),
            "--device",
            device,
            "--json-output",
            str(output),
        ]
        if calibration is not None:
            cmd.extend(["--calibration", str(calibration)])
        else:
            cmd.append("--allow-smoke-calibration")
        return cmd
    if job.kind == "v5":
        entry = ROOT / "src" / "look_twice_v5.py"
        return [
            python,
            str(entry),
            "--runtime",
            "genesis",
            "--motion-backend",
            motion,
            "--policy",
            job.policy,
            "--profile",
            job.profile,
            "--seed",
            str(job.seed),
            "--purify-bin",
            str(purify_bin),
            "--allow-smoke-calibration",
            "--json-output",
            str(output),
        ]
    raise ValueError(f"unsupported kind: {job.kind}")


def _run_one(payload: dict[str, Any]) -> dict[str, Any]:
    """Worker entry (must be top-level for ProcessPool pickling)."""
    job = Job(
        kind=payload["kind"],
        policy=payload["policy"],
        profile=payload["profile"],
        seed=int(payload["seed"]),
    )
    output = Path(payload["output"])
    log = Path(payload["log"])
    if _valid_episode(output, job.kind):
        return {
            "stem": job.stem,
            "status": "skipped",
            "seconds": 0.0,
            "returncode": 0,
        }
    cmd = _build_command(
        job,
        python=payload["python"],
        output=output,
        calibration=Path(payload["calibration"]) if payload.get("calibration") else None,
        purify_bin=Path(payload["purify_bin"]),
        motion=payload["motion"],
        device=payload["device"],
        log=log,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("PYOPENGL_PLATFORM", "egl")
    env.setdefault("PATH", "/opt/venv/bin:" + env.get("PATH", ""))
    started = time.perf_counter()
    log.parent.mkdir(parents=True, exist_ok=True)
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
    ok = proc.returncode == 0 and _valid_episode(output, job.kind)
    return {
        "stem": job.stem,
        "status": "ok" if ok else "fail",
        "seconds": elapsed,
        "returncode": proc.returncode,
        "log": str(log),
    }


def expand_jobs(
    *,
    kind: str,
    policies: Iterable[str],
    profiles: Iterable[str],
    seeds: Iterable[int],
) -> list[Job]:
    return [
        Job(kind, policy, profile, seed)
        for policy in policies
        for profile in profiles
        for seed in seeds
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("v4", "v5"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--policies",
        nargs="+",
        default=None,
        help="Default depends on kind",
    )
    parser.add_argument("--profiles", nargs="+", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(50000, 50005)))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--purify-bin",
        type=Path,
        default=ROOT / "purify_robotics" / "bin" / "purify-robotics-core",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=ROOT / "results" / "v4-gpu" / "calibration" / "calibration_artifact.json",
    )
    parser.add_argument("--motion", default="kinematic", choices=("kinematic", "skid-steer"))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-jobs", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    if args.kind == "v4":
        policies = args.policies or [
            "naive-majority",
            "purify-passive",
            "purify-active",
        ]
        profiles = args.profiles or [
            "independent-noise",
            "shared-occlusion",
            "evidence-echo",
            "dynamic-change",
        ]
    else:
        policies = args.policies or ["naive", "purify-passive", "purify-active"]
        profiles = args.profiles or [
            "independent-noise",
            "shared-occlusion",
            "evidence-echo",
            "dynamic-change",
            "time-skew",
            "manipulation-occlusion",
        ]

    jobs = expand_jobs(
        kind=args.kind,
        policies=policies,
        profiles=profiles,
        seeds=args.seeds,
    )
    if args.max_jobs > 0:
        jobs = jobs[: args.max_jobs]

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    cal = args.calibration if args.calibration.is_file() else None
    work: list[dict[str, Any]] = []
    for job in jobs:
        work.append(
            {
                "kind": job.kind,
                "policy": job.policy,
                "profile": job.profile,
                "seed": job.seed,
                "python": args.python,
                "purify_bin": str(args.purify_bin),
                "calibration": str(cal) if cal else None,
                "motion": args.motion,
                "device": args.device,
                "output": str(out_dir / f"{job.stem}.json"),
                "log": str(log_dir / f"{job.stem}.log"),
            }
        )

    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    print(
        f"parallel matrix kind={args.kind} jobs={len(work)} workers={args.workers}",
        flush=True,
    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_run_one, item) for item in work]
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            print(
                f"[{result['status']}] {result['stem']} "
                f"{result['seconds']:.1f}s rc={result['returncode']}",
                flush=True,
            )

    elapsed = time.perf_counter() - started
    summary = {
        "schema_version": "look-twice.parallel-matrix/v1",
        "kind": args.kind,
        "workers": args.workers,
        "jobs": len(work),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "fail": sum(1 for r in results if r["status"] == "fail"),
        "wall_seconds": elapsed,
        "results": sorted(results, key=lambda r: r["stem"]),
    }
    _atomic_json(out_dir / "parallel_summary.json", summary)
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, indent=2))
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
