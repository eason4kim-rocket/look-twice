"""v7 episode: v6 loop + vision claims + v7 contract options."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from v6_episode import (
    ACTIVE_REPAIR_POLICIES,
    GATED_POLICIES,
    POLICIES as V6_POLICIES,
    V6EpisodeConfig,
    run_v6_episode,
)
from v6_scenario import V6ScenarioSample
from v7_contracts import CorridorContractV7
from v7_vision_claims import (
    propose_vision,
    synthetic_rgb_for_label,
    vision_proposal_to_claim_v2,
)

EPISODE_SCHEMA_V7 = "look-twice.episode/v7"
V7_POLICIES = V6_POLICIES + ("purify-active-vision",)


@dataclass
class V7EpisodeConfig(V6EpisodeConfig):
    policy: str = "purify-active-vision"
    vision_backend: str = "heuristic_rgb_proxy"
    vision_checkpoint: str | None = None
    vision_conformal_artifact: str | None = None
    require_vision_clear_root: bool = False
    require_side_view_vision_root: bool = False
    enforce_modality_conflict: bool = True
    inject_vision: bool = True
    # Capability mode: initial carrier front alone cannot admit; scout side
    # vision required. Enable for both active and passive in paired matrices.
    repair_required: bool = False

    def __post_init__(self) -> None:
        # Allow v7 policy before parent check.
        if self.policy == "purify-active-vision":
            self.require_vision_clear_root = True
            self.require_side_view_vision_root = True
            # Temporarily map to purify-active for v6 runner fields.
            object.__setattr__(self, "_v6_policy", "purify-active")
        else:
            object.__setattr__(self, "_v6_policy", self.policy)
        if self.repair_required:
            self.require_vision_clear_root = True
            self.require_side_view_vision_root = True
            self.inject_vision = True
        if self.policy not in V7_POLICIES:
            raise ValueError(f"unsupported v7 policy: {self.policy}")


def _synthetic_vision_label(scenario: V6ScenarioSample, corridor_id: str) -> str:
    """Oracle-free public proxy: use profile noise + corridor parity, not blocked flag."""
    # Do not read oracle blocked flags for online claims.
    # Use seed parity + profile as public-looking pseudo signal.
    seed = scenario.seed
    if scenario.profile in ("heavy-occlusion", "shared-occlusion"):
        return "blocked" if seed % 3 == 0 else "inconclusive" if seed % 3 == 1 else "clear"
    if corridor_id.endswith("a"):
        return "clear" if seed % 2 == 0 else "inconclusive"
    return "clear" if seed % 2 == 1 else "blocked"


def attach_synthetic_vision_claims(
    claims: list[Any],
    *,
    scenario: V6ScenarioSample,
    agent_id: str,
    corridor_id: str,
    step: int,
    config: V7EpisodeConfig,
) -> tuple[list[Any], dict[str, Any]]:
    label = _synthetic_vision_label(scenario, corridor_id)
    rgb = synthetic_rgb_for_label(label, seed=scenario.seed + step + hash(corridor_id) % 97)
    prop = propose_vision(
        rgb,
        backend=config.vision_backend,
        checkpoint=config.vision_checkpoint,
        conformal_artifact=config.vision_conformal_artifact,
        device=config.device if str(config.device).startswith("cuda") else "cpu",
        allow_heuristic_fallback=False,
        meta={"corridor_id": corridor_id, "agent_id": agent_id, "step": step},
    )
    claim = vision_proposal_to_claim_v2(
        prop,
        agent_id=agent_id,
        corridor_id=corridor_id,
        step=step,
        ttl=config.ttl_steps,
    )
    return claims + [claim], prop.to_dict()


def run_v7_episode(
    *,
    scenario: V6ScenarioSample,
    config: V7EpisodeConfig | None = None,
    runtime: Any | None = None,
) -> dict[str, Any]:
    """Run closed-loop episode with vision claims + v7 contract hooks enabled."""
    config = config or V7EpisodeConfig()
    v6_policy = "purify-active" if config.policy == "purify-active-vision" else config.policy
    require_vis = config.require_vision_clear_root or (
        config.policy == "purify-active-vision"
    ) or bool(config.repair_required)
    require_side = config.require_side_view_vision_root or (
        config.policy == "purify-active-vision"
    ) or bool(config.repair_required)
    inject = config.inject_vision or bool(config.repair_required)
    v6_cfg = V6EpisodeConfig(
        policy=v6_policy,
        ttl_steps=config.ttl_steps,
        max_observations=config.max_observations,
        max_replans=config.max_replans,
        device=config.device,
        prefer_rgbd_claims=config.prefer_rgbd_claims,
        learned_checkpoint=config.learned_checkpoint,
        vision_enabled=inject,
        vision_backend=config.vision_backend,
        vision_checkpoint=config.vision_checkpoint,
        vision_conformal_artifact=config.vision_conformal_artifact,
        require_vision_clear_root=require_vis,
        require_side_view_vision_root=require_side,
        enforce_modality_conflict=config.enforce_modality_conflict,
        use_v7_contract=True,
    )
    result = run_v6_episode(scenario=scenario, config=v6_cfg, runtime=runtime)

    vision_audits = [
        a
        for a in (result.get("rgbd_observation_audits") or [])
        if a.get("kind") == "vision_proposal_v7"
    ]
    result["schema_version"] = EPISODE_SCHEMA_V7
    # Episode JSON must never self-declare formal eligibility (matrix-only).
    env = dict(result.get("environment") or {})
    if "artifact_inputs_eligible" not in env:
        env["artifact_inputs_eligible"] = bool(
            (result.get("metrics") or {}).get("world_alignment_passed")
            or (result.get("world_alignment") or {}).get("world_alignment_passed")
        )
    env["formal_result_eligible"] = False
    result["environment"] = env
    result["configuration"] = {
        **result.get("configuration", {}),
        "policy": config.policy,
        "vision_backend": config.vision_backend,
        "vision_checkpoint": config.vision_checkpoint,
        "vision_conformal_artifact": config.vision_conformal_artifact,
        "require_vision_clear_root": require_vis,
        "require_side_view_vision_root": require_side,
        "repair_required": bool(config.repair_required),
        "enforce_modality_conflict": config.enforce_modality_conflict,
        "use_v7_contract": True,
    }
    result["vision_audits"] = vision_audits
    m = result["metrics"]
    m["policy"] = config.policy
    m["vision_backend"] = config.vision_backend
    m["repair_required"] = bool(config.repair_required or require_side)
    m["vision_claim_count"] = len(vision_audits)
    m["vision_blocked_proposals"] = sum(
        1 for v in vision_audits if v.get("value") == "blocked"
    )
    m["vision_clear_proposals"] = sum(
        1 for v in vision_audits if v.get("value") == "clear"
    )
    # Surface model/calibration provenance for runtime-integration gates.
    ckpt_shas = sorted(
        {str(v.get("checkpoint_sha256")) for v in vision_audits if v.get("checkpoint_sha256")}
    )
    conf_shas = sorted(
        {
            str(v.get("conformal_artifact_sha256"))
            for v in vision_audits
            if v.get("conformal_artifact_sha256")
        }
    )
    m["checkpoint_sha256"] = ckpt_shas[0] if len(ckpt_shas) == 1 else (ckpt_shas or None)
    m["conformal_artifact_sha256"] = (
        conf_shas[0] if len(conf_shas) == 1 else (conf_shas or None)
    )
    m["fallback_used"] = any(bool(v.get("fallback_used")) for v in vision_audits)
    m["checkpoint_loaded"] = (
        all(bool(v.get("checkpoint_loaded")) for v in vision_audits)
        if vision_audits and config.vision_backend == "torch_corridor_head"
        else False
    )
    m["tensor_device"] = next(
        (v.get("tensor_device") for v in vision_audits if v.get("tensor_device")),
        config.device,
    )
    m["preprocessing_version"] = next(
        (
            v.get("preprocessing_version")
            for v in vision_audits
            if v.get("preprocessing_version")
        ),
        None,
    )
    m["vision_side_clear_proposals"] = sum(
        1
        for v in vision_audits
        if v.get("value") == "clear" and v.get("vision_root_kind") == "side"
    )
    m["modality_conflict_events"] = sum(
        1
        for g in (result.get("gate_receipts") or [])
        if "modality_conflict" in (g.get("reasons") or [])
    )
    m["modality_tension_hint"] = bool(
        m.get("route_mode") == "direct" and m["vision_blocked_proposals"] > 0
    )
    # Capability chain flag: deny → viewpoint change → new root → repair → direct.
    m["repair_chain_complete"] = bool(
        m.get("initial_gate_denied")
        and m.get("repair_attempted")
        and m.get("scout_viewpoint_changed")
        and m.get("new_capture_root_added")
        and m.get("repair_success")
        and m.get("route_mode") == "direct"
        and not m.get("unsafe_crossing")
    )
    return result


__all__ = (
    "EPISODE_SCHEMA_V7",
    "V7_POLICIES",
    "V7EpisodeConfig",
    "attach_synthetic_vision_claims",
    "run_v7_episode",
)
