#!/usr/bin/env python3
"""Look Twice v7 — Vision-Grounded Evidence Contracts entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_scenario import PROFILES, sample_v6_scenario
from v7_episode import V7_POLICIES, V7EpisodeConfig, run_v7_episode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=V7_POLICIES, default="purify-active-vision")
    parser.add_argument("--profile", choices=PROFILES, default="independent-noise")
    parser.add_argument("--seed", type=int, default=90000)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--runtime", choices=("synthetic", "genesis"), default="synthetic")
    parser.add_argument("--motion-backend", choices=("kinematic", "skid-steer"), default="kinematic")
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--vision-backend",
        choices=("heuristic_rgb_proxy", "torch_corridor_head"),
        default="heuristic_rgb_proxy",
    )
    parser.add_argument("--vision-checkpoint", type=Path, default=None)
    parser.add_argument(
        "--vision-conformal-artifact",
        type=Path,
        default=None,
        help="Path to conformal_artifact.json (required for torch_corridor_head).",
    )
    parser.add_argument("--no-rgbd-claims", action="store_true")
    parser.add_argument(
        "--repair-required",
        action="store_true",
        help=(
            "Capability mode: require independent scout/side-view vision clear "
            "root so initial carrier front alone cannot admit (both active and "
            "passive). Default on for purify-active-vision; use this flag to "
            "apply the same contract to purify-passive for paired matrices."
        ),
    )
    args = parser.parse_args(argv)

    scenario = sample_v6_scenario(args.profile, args.seed)
    device = args.device or ("cuda:0" if args.runtime == "genesis" else "cpu")
    if args.vision_backend == "torch_corridor_head":
        if not args.vision_checkpoint:
            raise SystemExit(
                "torch_corridor_head requires --vision-checkpoint (fail-closed)"
            )
        if not args.vision_conformal_artifact:
            raise SystemExit(
                "torch_corridor_head requires --vision-conformal-artifact (fail-closed)"
            )
    config = V7EpisodeConfig(
        policy=args.policy,
        device=device,
        prefer_rgbd_claims=not args.no_rgbd_claims,
        vision_backend=args.vision_backend,
        vision_checkpoint=str(args.vision_checkpoint) if args.vision_checkpoint else None,
        vision_conformal_artifact=(
            str(args.vision_conformal_artifact)
            if args.vision_conformal_artifact
            else None
        ),
        repair_required=bool(args.repair_required),
    )

    if args.runtime == "synthetic":
        result = run_v7_episode(scenario=scenario, config=config, runtime=None)
    else:
        import genesis as gs

        gs.init(backend=gs.amdgpu, logging_level="warning")
        from v6_genesis_runtime import V6GenesisRuntime

        runtime = V6GenesisRuntime(
            scenario, motion_backend=args.motion_backend, device=device
        )
        try:
            result = run_v7_episode(
                scenario=scenario, config=config, runtime=runtime
            )
        finally:
            runtime.close()

    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.json_output.with_name(args.json_output.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, args.json_output)

    m = result["metrics"]
    print(
        f"v7 finished policy={args.policy} profile={args.profile} seed={args.seed} "
        f"mission={m['mission_success']} unsafe={m['unsafe_crossing']} "
        f"route={m.get('route_mode')} repair_ok={m.get('repair_success')} "
        f"init_deny={m.get('initial_gate_denied')} chain={m.get('repair_chain_complete')} "
        f"vision={m.get('vision_backend')} v_clear={m.get('vision_clear_proposals')} "
        f"v_blocked={m.get('vision_blocked_proposals')} "
        f"ckpt_loaded={m.get('checkpoint_loaded')} fallback={m.get('fallback_used')} "
        f"device={m.get('tensor_device') or m.get('device')} "
        f"tension={m.get('modality_tension_hint')} "
        + (f"output={args.json_output}" if args.json_output else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
