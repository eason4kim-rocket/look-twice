#!/usr/bin/env python3
"""Collect one clustered calibration row for the learned RGB-D Gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from learned_rgbd import LearnedRGBDSensor
from purify_bridge import PurifyBridge
from v4_claims import canonical_sha256
from v4_conformal import CalibrationArtifact, SeedRange
from v5_episode import V5_ID_PROFILES, _gate_profile, cross_region_contract
from v5_rgbd_claims import (
    LEARNED_RGBD_SENSOR_VERSION,
    process_genesis_observation,
)
from v5_scenario import sample_v5_scenario


ROW_SCHEMA = "look-twice.learned-rgbd-gate-calibration-row/v1"


def placeholder_artifact() -> CalibrationArtifact:
    """Applicable wire object used only to expose uncalibrated p_blocked."""
    return CalibrationArtifact(
        artifact_id="learned-gate-collection-placeholder",
        alpha=0.05,
        class_quantiles={"clear": 1.0, "blocked": 1.0},
        applicable_profiles=tuple(V5_ID_PROFILES),
        min_noise_intensity=0.0,
        max_noise_intensity=1.0,
        sensor_versions=(LEARNED_RGBD_SENSOR_VERSION,),
        git_commit="collection-only",
        dataset_sha256=canonical_sha256({"purpose": "uncalibrated-score"}),
        seed_ranges=(SeedRange(31000, 31049),),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--learned-calibration", type=Path, required=True)
    parser.add_argument("--purify-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import genesis as gs
    from v5_genesis_runtime import V5GenesisRuntime

    scenario = sample_v5_scenario(args.profile, args.seed)
    gs.init(backend=gs.amdgpu, logging_level="warning")
    runtime = V5GenesisRuntime(scenario, motion_backend="kinematic")
    sensor = LearnedRGBDSensor(
        args.model, args.learned_calibration, device="cuda:0"
    )
    bridge = PurifyBridge(command=(args.purify_bin,))
    claims = []
    prefixes = []
    epoch_label: str | None = None
    epoch_observations = 0
    try:
        bridge.start()
        observation_index = 0
        for candidate in scenario.public_context["candidate_viewpoints"]:
            name = str(candidate["name"])
            if not name.startswith(("left_", "right_")) or not candidate["reachable"]:
                continue
            xy = (float(candidate["xy"][0]), float(candidate["xy"][1]))
            motion = runtime.move_to(xy)
            if not motion.reached:
                continue
            runtime.wait_steps(3)
            frame = runtime.capture_raw(
                viewpoint=name,
                viewpoint_xy=xy,
                predicted_coverage=float(candidate["predicted_coverage"]),
            )
            new_claims, audit = process_genesis_observation(
                frame,
                runtime.evidence_scenario,
                observation_index=observation_index,
                repair_action_kind=(
                    "initial" if observation_index == 0 else "side_view"
                ),
                device="cuda:0",
                ttl_steps=2000,
                learned_sensor=sensor,
            )
            label = (
                "blocked"
                if scenario.truth_nav_blocked_at(runtime.current_step)
                else "clear"
            )
            if epoch_label is not None and label != epoch_label:
                # Calibration oracle marks the exogenous fact boundary only.
                # Old physical Claims belong to the invalidated world epoch and
                # must not be fused with post-change observations.
                claims = []
                epoch_observations = 0
            epoch_label = label
            claims.extend(new_claims)
            observation_index += 1
            epoch_observations += 1
            if epoch_observations < 2:
                continue
            receipt = bridge.evaluate_action(
                claims=claims,
                contract=cross_region_contract(),
                calibration=placeholder_artifact(),
                current_step=runtime.current_step,
                profile=_gate_profile(args.profile),
                noise_intensity=float(
                    scenario.public_context["declared_noise_intensity"]
                ),
                sensor_version=LEARNED_RGBD_SENSOR_VERSION,
            )
            p_blocked = float(receipt["p_blocked"])
            p_true = p_blocked if label == "blocked" else 1.0 - p_blocked
            prefixes.append(
                {
                    "observation_count": epoch_observations,
                    "global_observation_index": observation_index,
                    "capture_step": runtime.current_step,
                    "viewpoint": name,
                    "true_label": label,
                    "p_clear": 1.0 - p_blocked,
                    "nonconformity": 1.0 - p_true,
                    "measurement_roots": list(
                        receipt.get("measurement_root_ids", [])
                    ),
                    "receipt_sha256": receipt.get("receipt_sha256"),
                    "claim_ids": list(audit["claim_ids"]),
                }
            )
    finally:
        bridge.close()
        runtime.close()

    if not prefixes:
        raise RuntimeError("fewer than two usable learned RGB-D observations")
    worst = max(
        prefixes,
        key=lambda item: (
            float(item["nonconformity"]),
            int(item["observation_count"]),
        ),
    )
    row = {
        "schema_version": ROW_SCHEMA,
        "seed": args.seed,
        "profile": _gate_profile(args.profile),
        "source_profile": args.profile,
        "noise_intensity": float(
            scenario.public_context["declared_noise_intensity"]
        ),
        "sensor_version": LEARNED_RGBD_SENSOR_VERSION,
        "true_label": worst["true_label"],
        "p_clear": worst["p_clear"],
        "cluster_method": "worst_true_class_prefix_per_world",
        "selected_prefix": worst,
        "prefixes": prefixes,
        "model_sha256": sensor.model_sha256,
        "learned_calibration_sha256": sensor.calibration_sha256,
        "gpu_environment": runtime.environment,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "selected": worst}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
