#!/usr/bin/env python3
"""Look Twice v4 — Active Evidence Assurance episode entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from purify_bridge import PurifyBridge
from v4_conformal import CalibrationArtifact
from v4_episode import ABLATIONS, EpisodeConfig, run_v4_episode, smoke_calibration_artifact
from v4_policies import POLICIES, get_policy_descriptor
from v4_runtime import SyntheticEpisodeRuntime
from v4_scenario import PROFILES, sample_v4_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="independent-noise")
    parser.add_argument("--policy", choices=POLICIES, default="purify-active")
    parser.add_argument("--seed", type=int, default=50000)
    parser.add_argument("--runtime", choices=("genesis", "synthetic"), default="genesis")
    parser.add_argument(
        "--motion-backend", choices=("skid-steer", "kinematic"), default="skid-steer"
    )
    parser.add_argument("--device")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--allow-smoke-calibration", action="store_true")
    parser.add_argument("--purify-bin", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--video-stride", type=int, default=4)
    parser.add_argument("--max-observations", type=int, default=4)
    parser.add_argument("--max-replans", type=int, default=2)
    parser.add_argument("--belief-ttl", type=int, default=60)
    parser.add_argument("--ablation", choices=ABLATIONS, default="none")
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    if args.video_stride < 1 or args.max_observations < 1 or args.belief_ttl < 1:
        parser.error("video stride, max observations, and TTL must be positive")
    if args.max_replans < 0:
        parser.error("--max-replans must be non-negative")
    if args.runtime == "synthetic" and args.motion_backend != "skid-steer":
        # The synthetic adapter is already an explicit kinematic CI fixture;
        # this flag is relevant only to Genesis and should not imply physics.
        parser.error("--motion-backend applies only to --runtime genesis")
    if args.runtime == "genesis" and args.calibration is None and not args.allow_smoke_calibration:
        parser.error(
            "Genesis/formal runs require --calibration; use --allow-smoke-calibration "
            "only for GPU integration debugging"
        )
    if args.ablation != "none" and args.policy != "purify-active":
        parser.error("component ablations require --policy purify-active")
    return args


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    args = parse_args()
    scenario = sample_v4_scenario(args.profile, args.seed)
    calibration = (
        CalibrationArtifact.load(args.calibration)
        if args.calibration is not None
        else smoke_calibration_artifact()
    )
    device = args.device or ("cpu" if args.runtime == "synthetic" else "cuda:0")
    if args.runtime == "synthetic" and device != "cpu":
        raise SystemExit("synthetic CI runtime supports --device cpu only")

    if args.runtime == "genesis":
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        from v4_genesis_runtime import GenesisEpisodeRuntime

        runtime = GenesisEpisodeRuntime(
            scenario,
            motion_backend=args.motion_backend,
            video_output=args.video_output,
            video_stride=args.video_stride,
        )
    else:
        runtime = SyntheticEpisodeRuntime(scenario)

    config = EpisodeConfig(
        policy=args.policy,
        device=device,
        max_observations=args.max_observations,
        max_replans=args.max_replans,
        ttl_steps=args.belief_ttl,
        evidence_dir=args.evidence_dir,
        ablation=args.ablation,
    )
    descriptor = get_policy_descriptor(args.policy)
    bridge = None
    try:
        if descriptor.requires_go_gate:
            command = (args.purify_bin,) if args.purify_bin is not None else None
            bridge = PurifyBridge(command=command)
            bridge.start()
        result = run_v4_episode(
            scenario=scenario,
            runtime=runtime,
            calibration=calibration,
            config=config,
            bridge=bridge,
        )
    finally:
        if bridge is not None:
            bridge.close()
        runtime.close()

    result["configuration"].update(
        {
            "runtime": args.runtime,
            "motion_backend": (
                args.motion_backend if args.runtime == "genesis" else "kinematic-ci"
            ),
            "calibration_path": str(args.calibration) if args.calibration else None,
            "smoke_calibration": args.calibration is None,
            "video_output": str(args.video_output) if args.video_output else None,
        }
    )
    output = args.json_output or Path(
        f"outputs/v4-{args.runtime}-{args.policy}-{args.profile}-{args.seed}.json"
    )
    _atomic_json(output, result)
    metrics = result["metrics"]
    print(
        "v4 finished",
        f"policy={args.policy}",
        f"profile={args.profile}",
        f"seed={args.seed}",
        f"safe={metrics['safe_success']}",
        f"unsafe={metrics['unsafe_crossing']}",
        f"observations={metrics['observation_count']}",
        f"output={output}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
