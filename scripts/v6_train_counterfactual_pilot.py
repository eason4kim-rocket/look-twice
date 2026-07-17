#!/usr/bin/env python3
"""Counterfactual pilot + imitation train for v6 evidence ranker (GPU-friendly).

Uses synthetic multi-agent loop for fast label generation (paired worlds).
Labels store oracle utilities only under sample['oracle'].
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_contracts import CorridorContract, evaluate_corridor_contract
from v6_episode import V6EpisodeConfig, run_v6_episode, _synthetic_observation
from v6_learned_policy import (
    action_feature_vector,
    save_checkpoint,
    train_listwise,
)
from v6_repair import build_candidate_actions, score_action
from v6_scenario import sample_v6_scenario
from v6_motion import build_runtime_from_scenario


def build_sample(profile: str, seed: int) -> dict:
    scenario = sample_v6_scenario(profile, seed)
    public = scenario.public_context
    runtime = build_runtime_from_scenario(scenario)
    # Initial low-quality capture
    claims = _synthetic_observation(
        scenario=scenario,
        agent_id="carrier",
        corridor_id="corridor_a",
        step=runtime.current_step,
        capture_index=0,
        viewpoint_name="carrier_initial_front",
        predicted_coverage=0.5,
        ttl=2000,
    )
    contract = CorridorContract(
        corridor_id="corridor_a",
        evidence_age_limit=int(public["evidence_age_limit"]),
        min_distinct_capture_roots=int(public["min_distinct_capture_roots"]),
    )
    before = evaluate_corridor_contract(
        claims, contract, current_step=runtime.current_step
    )
    gaps = [g.get("reason", "insufficient_roots") for g in before.belief_gaps] or list(
        before.reasons
    ) or ["insufficient_roots"]
    carrier_xy = (runtime.pose_of("carrier").x, runtime.pose_of("carrier").y)
    scout_xy = (runtime.pose_of("scout").x, runtime.pose_of("scout").y)
    actions = build_candidate_actions(
        public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=set()
    )
    features = []
    utilities = []
    repair_labels = []
    oracle_rows = []
    for idx, action in enumerate(actions):
        # Counterfactual: apply one synthetic observation if side/same view.
        trial_claims = list(claims)
        repaired = False
        new_root = False
        if action.kind in ("side_view", "same_view") and action.corridor_id:
            extra = _synthetic_observation(
                scenario=scenario,
                agent_id=action.observer,
                corridor_id=action.corridor_id,
                step=runtime.current_step + 10 + idx,
                capture_index=1 + idx,
                viewpoint_name=action.viewpoint,
                predicted_coverage=action.predicted_coverage,
                ttl=2000,
            )
            # second capture for clear-world often needs two roots — add twin root
            extra2 = _synthetic_observation(
                scenario=scenario,
                agent_id=action.observer,
                corridor_id=action.corridor_id,
                step=runtime.current_step + 20 + idx,
                capture_index=50 + idx,
                viewpoint_name=action.viewpoint + ":b",
                predicted_coverage=action.predicted_coverage,
                ttl=2000,
            )
            trial_claims = trial_claims + extra + extra2
            new_root = True
            after = evaluate_corridor_contract(
                trial_claims, contract, current_step=runtime.current_step + 30 + idx
            )
            repaired = bool(after.admitted and not before.admitted)
        util = score_action(action, gap_reasons=gaps, visited=set())
        if repaired:
            util += 1.0
        if new_root:
            util += 0.3
        features.append(
            action_feature_vector(
                action,
                gap_reasons=gaps,
                observations_taken=1,
                max_observations=6,
            )
        )
        utilities.append(float(util))
        repair_labels.append(1.0 if repaired else 0.0)
        oracle_rows.append(
            {
                "action": action.name,
                "contract_repaired": repaired,
                "new_root": new_root,
                "utility": float(util),
            }
        )
    runtime.close()
    return {
        "profile": profile,
        "seed": seed,
        "features": features,
        "utilities": utilities,
        "repair_labels": repair_labels,
        "oracle": {"ranking": oracle_rows, "gaps": gaps},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--start-seed", type=int, default=90000)
    parser.add_argument("--n-worlds", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--device", default="cpu")
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
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for i in range(args.n_worlds):
        profile = args.profiles[i % len(args.profiles)]
        seed = args.start_seed + i
        samples.append(build_sample(profile, seed))
        if (i + 1) % 32 == 0:
            print(f"labeled {i+1}/{args.n_worlds}", flush=True)
    data_path = args.out_dir / "counterfactual_pilot.jsonl"
    with data_path.open("w", encoding="utf-8") as handle:
        for s in samples:
            handle.write(json.dumps(s) + "\n")
    model, hist = train_listwise(samples, epochs=args.epochs, device=args.device)
    ckpt = args.out_dir / "best.pt"
    save_checkpoint(model, ckpt, hist["in_dim"])
    save_checkpoint(model, args.out_dir / "last.pt", hist["in_dim"])
    meta = {
        "n_worlds": args.n_worlds,
        "epochs": args.epochs,
        "in_dim": hist["in_dim"],
        "final_loss": hist["loss_history"][-1] if hist["loss_history"] else None,
        "checkpoint": str(ckpt),
        "data": str(data_path),
    }
    (args.out_dir / "train_summary.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
