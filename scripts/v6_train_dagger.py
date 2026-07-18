#!/usr/bin/env python3
"""DAgger × N for v6 evidence repair ranker (synthetic closed-loop + teacher).

Round 0: behavioral cloning on counterfactual pilot samples.
Rounds 1..N: roll student policy, query heuristic teacher utilities, aggregate, retrain.
Oracle world fields stay under sample['oracle'] only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_contracts import CorridorContract, evaluate_corridor_contract
from v6_episode import V6EpisodeConfig, _synthetic_observation
from v6_learned_policy import (
    action_feature_vector,
    rank_with_learned,
    save_checkpoint,
    train_listwise,
    LearnedPolicyArtifact,
)
from v6_motion import build_runtime_from_scenario
from v6_repair import build_candidate_actions, choose_evidence_action, score_action
from v6_scenario import sample_v6_scenario


PROFILES_DEFAULT = [
    "independent-noise",
    "shared-occlusion",
    "evidence-echo",
    "time-skew",
    "dynamic-change",
    "comm-fault",
]


def _label_state(
    *,
    profile: str,
    seed: int,
    claims,
    runtime,
    public,
    gaps,
    observations_taken: int,
    visited: set[str],
) -> dict:
    carrier_xy = (runtime.pose_of("carrier").x, runtime.pose_of("carrier").y)
    scout_xy = (runtime.pose_of("scout").x, runtime.pose_of("scout").y)
    actions = build_candidate_actions(
        public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=visited
    )
    contract = CorridorContract(
        corridor_id="corridor_a",
        evidence_age_limit=int(public["evidence_age_limit"]),
        min_distinct_capture_roots=int(public["min_distinct_capture_roots"]),
    )
    before = evaluate_corridor_contract(
        claims, contract, current_step=runtime.current_step
    )
    features = []
    utilities = []
    repair_labels = []
    oracle_rows = []
    for idx, action in enumerate(actions):
        trial_claims = list(claims)
        repaired = False
        new_root = False
        if action.kind in ("side_view", "same_view") and action.corridor_id:
            scenario = sample_v6_scenario(profile, seed)
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
        util, _audit = score_action(action, gap_reasons=gaps, visited=visited)
        if repaired:
            util += 1.0
        if new_root:
            util += 0.3
        features.append(
            action_feature_vector(
                action,
                gap_reasons=gaps,
                observations_taken=observations_taken,
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
    return {
        "profile": profile,
        "seed": seed,
        "features": features,
        "utilities": utilities,
        "repair_labels": repair_labels,
        "oracle": {"ranking": oracle_rows, "gaps": gaps},
    }


def collect_bc_samples(n_worlds: int, start_seed: int, profiles: list[str]) -> list[dict]:
    samples = []
    for i in range(n_worlds):
        profile = profiles[i % len(profiles)]
        seed = start_seed + i
        scenario = sample_v6_scenario(profile, seed)
        public = scenario.public_context
        runtime = build_runtime_from_scenario(scenario)
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
        samples.append(
            _label_state(
                profile=profile,
                seed=seed,
                claims=claims,
                runtime=runtime,
                public=public,
                gaps=gaps,
                observations_taken=1,
                visited=set(),
            )
        )
        runtime.close()
        if (i + 1) % 64 == 0:
            print(f"bc labeled {i+1}/{n_worlds}", flush=True)
    return samples


def dagger_rollout_samples(
    model,
    *,
    n_worlds: int,
    start_seed: int,
    profiles: list[str],
    device: str,
) -> list[dict]:
    """Roll student; at each denied state, label with teacher and append."""
    samples = []
    for i in range(n_worlds):
        profile = profiles[i % len(profiles)]
        seed = start_seed + i
        scenario = sample_v6_scenario(profile, seed)
        public = scenario.public_context
        runtime = build_runtime_from_scenario(scenario)
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
        visited: set[str] = set()
        observations = 1
        for _step in range(4):
            before = evaluate_corridor_contract(
                claims, contract, current_step=runtime.current_step
            )
            if before.admitted:
                break
            gaps = [g.get("reason", "insufficient_roots") for g in before.belief_gaps] or list(
                before.reasons
            ) or ["insufficient_roots"]
            samples.append(
                _label_state(
                    profile=profile,
                    seed=seed,
                    claims=claims,
                    runtime=runtime,
                    public=public,
                    gaps=gaps,
                    observations_taken=observations,
                    visited=set(visited),
                )
            )
            carrier_xy = (runtime.pose_of("carrier").x, runtime.pose_of("carrier").y)
            scout_xy = (runtime.pose_of("scout").x, runtime.pose_of("scout").y)
            candidates = build_candidate_actions(
                public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=visited
            )
            selected, _ = rank_with_learned(
                model,
                candidates,
                gap_reasons=gaps,
                observations_taken=observations,
                max_observations=6,
                device=device,
            )
            if selected is None or selected.kind == "safe_fallback":
                break
            if selected.kind == "wait":
                runtime.wait_steps(20)
                continue
            # Apply synthetic observation at student-chosen viewpoint.
            extra = _synthetic_observation(
                scenario=scenario,
                agent_id=selected.observer,
                corridor_id=selected.corridor_id or "corridor_a",
                step=runtime.current_step + 5,
                capture_index=observations,
                viewpoint_name=selected.viewpoint,
                predicted_coverage=selected.predicted_coverage,
                ttl=2000,
            )
            claims = claims + extra
            visited.add(selected.viewpoint)
            if selected.viewpoint.startswith("corridor_a/"):
                visited.add("scout_a_" + selected.viewpoint.split("/", 1)[1])
            elif selected.viewpoint.startswith("corridor_b/"):
                visited.add("scout_b_" + selected.viewpoint.split("/", 1)[1])
            observations += 1
            runtime.wait_steps(8)
        runtime.close()
        if (i + 1) % 32 == 0:
            print(f"dagger rollout labeled {i+1}/{n_worlds}", flush=True)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--bc-worlds", type=int, default=384)
    parser.add_argument("--dagger-worlds", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--start-seed", type=int, default=91000)
    parser.add_argument("--profiles", nargs="+", default=PROFILES_DEFAULT)
    parser.add_argument(
        "--init-checkpoint",
        type=Path,
        default=None,
        help="Optional warm-start from pilot best.pt",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    aggregate: list[dict] = collect_bc_samples(
        args.bc_worlds, args.start_seed, args.profiles
    )
    (args.out_dir / "bc.jsonl").write_text(
        "\n".join(json.dumps(s) for s in aggregate) + "\n", encoding="utf-8"
    )

    model, hist = train_listwise(aggregate, epochs=args.epochs, device=args.device)
    if args.init_checkpoint and args.init_checkpoint.is_file():
        # Warm-start after first BC if dims match.
        try:
            warm = LearnedPolicyArtifact(args.init_checkpoint, in_dim=0).load(
                device=args.device
            )
            if sum(p.numel() for p in warm.parameters()) == sum(
                p.numel() for p in model.parameters()
            ):
                model.load_state_dict(warm.state_dict())
                model, hist = train_listwise(
                    aggregate, epochs=max(5, args.epochs // 2), device=args.device
                )
        except Exception as exc:
            print(f"warm-start skipped: {exc}", flush=True)

    round_meta = []
    for r in range(1, args.rounds + 1):
        rdir = args.out_dir / f"round{r}"
        rdir.mkdir(parents=True, exist_ok=True)
        save_checkpoint(model, rdir / "student_before.pt", hist["in_dim"])
        new_samples = dagger_rollout_samples(
            model,
            n_worlds=args.dagger_worlds,
            start_seed=args.start_seed + 10000 * r,
            profiles=args.profiles,
            device=args.device,
        )
        (rdir / "dagger_new.jsonl").write_text(
            "\n".join(json.dumps(s) for s in new_samples) + "\n", encoding="utf-8"
        )
        aggregate.extend(new_samples)
        model, hist = train_listwise(aggregate, epochs=args.epochs, device=args.device)
        save_checkpoint(model, rdir / "best.pt", hist["in_dim"])
        save_checkpoint(model, args.out_dir / "best.pt", hist["in_dim"])
        meta = {
            "round": r,
            "aggregate_n": len(aggregate),
            "new_n": len(new_samples),
            "final_loss": hist["loss_history"][-1] if hist["loss_history"] else None,
            "in_dim": hist["in_dim"],
        }
        (rdir / "train_summary.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        round_meta.append(meta)
        print(json.dumps(meta), flush=True)

    # Teacher agreement probe on held-out seeds.
    probe = []
    for i in range(48):
        profile = args.profiles[i % len(args.profiles)]
        seed = 99000 + i
        scenario = sample_v6_scenario(profile, seed)
        public = scenario.public_context
        runtime = build_runtime_from_scenario(scenario)
        claims = _synthetic_observation(
            scenario=scenario,
            agent_id="carrier",
            corridor_id="corridor_a",
            step=0,
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
        before = evaluate_corridor_contract(claims, contract, current_step=0)
        gaps = [g.get("reason", "insufficient_roots") for g in before.belief_gaps] or [
            "insufficient_roots"
        ]
        carrier_xy = (runtime.pose_of("carrier").x, runtime.pose_of("carrier").y)
        scout_xy = (runtime.pose_of("scout").x, runtime.pose_of("scout").y)
        teacher, _ = choose_evidence_action(
            public,
            gap_reasons=gaps,
            carrier_xy=carrier_xy,
            scout_xy=scout_xy,
            visited=set(),
            observations_taken=1,
            max_observations=6,
        )
        student, _ = rank_with_learned(
            model,
            build_candidate_actions(
                public, carrier_xy=carrier_xy, scout_xy=scout_xy, visited=set()
            ),
            gap_reasons=gaps,
            observations_taken=1,
            max_observations=6,
            device=args.device,
        )
        agree = (
            teacher is not None
            and student is not None
            and teacher.name == student.name
        )
        probe.append(
            {
                "seed": seed,
                "teacher": None if teacher is None else teacher.name,
                "student": None if student is None else student.name,
                "agree": agree,
            }
        )
        runtime.close()
    agree_rate = sum(1 for p in probe if p["agree"]) / max(1, len(probe))
    # Soft promotion: teacher top-1 agreement ≥ 0.55 on probe (not online mission claim).
    promote = agree_rate >= 0.55
    summary = {
        "rounds": args.rounds,
        "bc_worlds": args.bc_worlds,
        "dagger_worlds_per_round": args.dagger_worlds,
        "aggregate_final": len(aggregate),
        "round_meta": round_meta,
        "teacher_top1_agree": agree_rate,
        "promote_candidate": promote,
        "promotion_rule": "teacher_top1_agree>=0.55 on 48 synthetic probe worlds",
        "checkpoint": str(args.out_dir / "best.pt"),
        "probe": probe,
        "note": (
            "Promotion here is teacher-agreement only. Online GPU mission promotion "
            "requires paired genesis matrix beating heuristic on locked seeds."
        ),
    }
    (args.out_dir / "dagger_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "probe"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
