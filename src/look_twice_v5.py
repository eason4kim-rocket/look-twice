#!/usr/bin/env python3
"""Look Twice v5 — Embodied Evidence Assurance entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from purify_bridge import PurifyBridge
from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact
from v5_policies import POLICIES, get_policy_descriptor
from v5_scenario import PROFILES, sample_v5_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="independent-noise")
    parser.add_argument("--policy", choices=POLICIES, default="purify-active")
    parser.add_argument("--seed", type=int, default=50000)
    parser.add_argument(
        "--runtime", choices=("synthetic", "genesis"), default="synthetic"
    )
    parser.add_argument(
        "--motion-backend",
        choices=("skid-steer", "kinematic"),
        default="skid-steer",
        help="Genesis only; synthetic is always kinematic CI",
    )
    parser.add_argument("--purify-bin", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--allow-smoke-calibration", action="store_true")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument(
        "--device",
        default=None,
        help="Perception device for RGB-D Claims (default: cuda:0 on genesis, cpu on synthetic)",
    )
    parser.add_argument(
        "--no-rgbd-claims",
        action="store_true",
        help="Force synthetic modality proxies even on Genesis",
    )
    parser.add_argument(
        "--learned-rgbd-model",
        type=Path,
        help="Optional promoted learned RGB-D model checkpoint (Genesis only)",
    )
    parser.add_argument(
        "--learned-rgbd-calibration",
        type=Path,
        help="Clustered conformal artifact paired with --learned-rgbd-model",
    )
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("seed must be non-negative")
    if args.runtime == "genesis" and not args.calibration and not args.allow_smoke_calibration:
        parser.error("Genesis requires --calibration or --allow-smoke-calibration")
    if bool(args.learned_rgbd_model) != bool(args.learned_rgbd_calibration):
        parser.error(
            "--learned-rgbd-model and --learned-rgbd-calibration must be used together"
        )
    if args.learned_rgbd_model is not None and args.runtime != "genesis":
        parser.error("learned RGB-D Claims require --runtime genesis")
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
    scenario = sample_v5_scenario(args.profile, args.seed)
    if args.calibration is not None:
        from v4_conformal import CalibrationArtifact

        calibration = CalibrationArtifact.load(args.calibration)
    else:
        calibration = smoke_calibration_artifact()

    if args.runtime == "synthetic":
        runtime = _V5SyntheticRuntime(scenario)
    else:
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        from v5_genesis_runtime import V5GenesisRuntime

        runtime = V5GenesisRuntime(
            scenario, motion_backend=args.motion_backend
        )

    descriptor = get_policy_descriptor(args.policy)
    bridge = None
    try:
        if descriptor.requires_go_gate:
            command = (args.purify_bin,) if args.purify_bin is not None else None
            bridge = PurifyBridge(command=command)
            bridge.start()
        device = args.device
        if device is None:
            device = "cuda:0" if args.runtime == "genesis" else "cpu"
        result = run_v5_episode(
            scenario=scenario,
            runtime=runtime,
            calibration=calibration,
            config=V5EpisodeConfig(
                policy=args.policy,
                device=device,
                prefer_rgbd_claims=not args.no_rgbd_claims,
                learned_rgbd_model=(
                    str(args.learned_rgbd_model)
                    if args.learned_rgbd_model is not None
                    else None
                ),
                learned_rgbd_calibration=(
                    str(args.learned_rgbd_calibration)
                    if args.learned_rgbd_calibration is not None
                    else None
                ),
            ),
            bridge=bridge,
        )
    finally:
        if bridge is not None:
            bridge.close()
        runtime.close()

    result["configuration"]["runtime"] = args.runtime
    result["configuration"]["motion_backend"] = (
        "kinematic-ci" if args.runtime == "synthetic" else args.motion_backend
    )
    result["configuration"]["smoke_calibration"] = args.calibration is None
    # Smoke calibration must never be formal-eligible.
    if args.calibration is None and isinstance(result.get("environment"), dict):
        result["environment"]["formal_result_eligible"] = False
    out = args.json_output or Path(
        f"outputs/v5-{args.runtime}-{args.policy}-{args.profile}-{args.seed}.json"
    )
    _atomic_json(out, result)
    m = result["metrics"]
    print(
        "v5 finished",
        f"policy={args.policy}",
        f"profile={args.profile}",
        f"seed={args.seed}",
        f"mission={m['mission_success']}",
        f"unsafe={m['unsafe_crossing']}",
        f"nav={m['nav_success']}",
        f"pick={m['pick_success']}",
        f"claims_mode={m.get('claims_mode') or result.get('configuration', {}).get('claims_mode')}",
        f"output={out}",
    )
    return 0


class _V5SyntheticRuntime:
    """Thin wrapper so v5 scenarios drive the v4 kinematic CI runtime."""

    def __init__(self, scenario) -> None:
        import math
        from types import SimpleNamespace

        from v4_motion import Pose2D
        from v4_runtime import SyntheticEpisodeRuntime
        from v5_scenario import NAV_REGION, START_XY

        # Minimal duck-type for SyntheticEvidenceSource / motion only.
        fake = SimpleNamespace(
            public_context=scenario.public_context,
            oracle_context=scenario.oracle_context,
            profile=scenario.profile,
            seed=scenario.seed,
            fault_realization=SimpleNamespace(
                depth_realization_seed=scenario.seed,
                semantic_realization_seed=scenario.seed + 1,
                rgb_realization_seed=scenario.seed + 2,
            ),
            truth_blocked_at=scenario.truth_nav_blocked_at,
        )
        def heading_provider(target):
            tx, ty = float(target[0]), float(target[1])
            if abs(ty) > 0.55 or tx <= 0.45:
                return math.atan2(-ty, 0.8 - tx)
            return 0.0

        self._inner = SyntheticEpisodeRuntime(
            fake,  # type: ignore[arg-type]
            start_pose=Pose2D(START_XY[0], START_XY[1], 0.0),
            final_heading_provider=heading_provider,
            risk_region=NAV_REGION,
        )
        self.scenario = scenario

    @property
    def current_step(self):
        return self._inner.current_step

    @property
    def current_pose(self):
        return self._inner.current_pose

    @property
    def collision_count(self):
        return self._inner.collision_count

    @property
    def environment(self):
        env = dict(self._inner.environment)
        env["v5"] = True
        env["formal_result_eligible"] = False
        return env

    def move_to(self, target_xy):
        return self._inner.move_to(target_xy)

    def wait_steps(self, count):
        return self._inner.wait_steps(count)

    def capture_raw(self, **kwargs):
        return self._inner.capture_raw(**kwargs)

    def close(self):
        return self._inner.close()


if __name__ == "__main__":
    sys.exit(main())
