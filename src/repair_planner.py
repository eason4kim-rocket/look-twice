"""BeliefGap-driven active evidence repair for Look Twice v4.

This planner is deliberately one-step, deterministic, and auditable.  It is
allowed to use current belief gaps, known static geometry, predicted sensor
quality, travel cost, visit history, and route-risk estimates.  It never
accepts world truth, future events, or realised noise parameters.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from v4_scenario import assert_public_context_safe


BELIEF_GAP_REASONS = (
    "stale",
    "shared_root",
    "insufficient_roots",
    "modality_conflict",
    "time_skew",
    "low_coverage",
    "calibration_not_applicable",
)

# The signed coefficients are the approved v4 utility exactly.  Keep the
# component values separate in RepairFeatureVector so every score is auditable.
UTILITY_WEIGHTS: dict[str, float] = {
    "expected_contract_repair": 0.45,
    "new_measurement_root_gain": 0.25,
    "conflict_discrimination": 0.20,
    "predicted_coverage": 0.10,
    "normalized_travel_cost": -0.25,
    "revisit_penalty": -0.20,
    "predicted_degradation": -0.30,
    "physical_risk": -0.50,
}

ACTION_SAME_VIEW = "same_view_sync_recapture"
ACTION_WAIT = "wait_then_recapture"
SIDE_VIEW_NAMES = ("left_near", "left_far", "right_near", "right_far")


# Expected ability of each action kind to repair each declared contract gap.
# These are policy priors, not realised outcomes or oracle labels.
_REPAIR_EFFECTIVENESS: dict[str, dict[str, float]] = {
    "stale": {"same_view": 0.95, "wait": 0.90, "side_view": 0.85},
    # Shared capture roots are not broken by same-view recapture under
    # shared-occlusion style faults (strip dropout persists). Side views are
    # the intended repair; same_view/wait stay weak so utility prefers them.
    "shared_root": {"same_view": 0.18, "wait": 0.12, "side_view": 1.00},
    "insufficient_roots": {
        "same_view": 0.55,
        "wait": 0.40,
        "side_view": 1.00,
    },
    "modality_conflict": {
        "same_view": 0.85,
        "wait": 0.60,
        "side_view": 1.00,
    },
    "time_skew": {"same_view": 1.00, "wait": 0.80, "side_view": 0.75},
    "low_coverage": {"same_view": 0.20, "wait": 0.18, "side_view": 0.90},
    "calibration_not_applicable": {
        "same_view": 0.05,
        "wait": 0.05,
        "side_view": 0.52,
    },
}

_CONFLICT_DISCRIMINATION: dict[str, dict[str, float]] = {
    "stale": {"same_view": 0.25, "wait": 0.35, "side_view": 0.40},
    "shared_root": {"same_view": 0.20, "wait": 0.15, "side_view": 1.00},
    "insufficient_roots": {
        "same_view": 0.35,
        "wait": 0.25,
        "side_view": 0.95,
    },
    "modality_conflict": {
        "same_view": 0.90,
        "wait": 0.60,
        "side_view": 1.00,
    },
    "time_skew": {"same_view": 1.00, "wait": 0.80, "side_view": 0.72},
    "low_coverage": {"same_view": 0.20, "wait": 0.18, "side_view": 0.75},
    "calibration_not_applicable": {
        "same_view": 0.10,
        "wait": 0.10,
        "side_view": 0.70,
    },
}

_NEW_ROOT_GAIN = {"same_view": 0.98, "wait": 0.92, "side_view": 1.00}


def _unit_interval(name: str, value: float) -> float:
    converted = float(value)
    if not math.isfinite(converted) or not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return converted


@dataclass(frozen=True)
class BeliefGap:
    """Finite, explainable reasons why the current Action Contract failed."""

    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        canonical = tuple(dict.fromkeys(self.reasons))
        invalid = sorted(set(canonical) - set(BELIEF_GAP_REASONS))
        if invalid:
            raise ValueError(f"unsupported BeliefGap reasons: {invalid}")
        object.__setattr__(
            self,
            "reasons",
            tuple(reason for reason in BELIEF_GAP_REASONS if reason in canonical),
        )

    @classmethod
    def from_reasons(cls, reasons: Iterable[str]) -> "BeliefGap":
        return cls(tuple(reasons))


@dataclass(frozen=True)
class PublicViewpoint:
    name: str
    xy: tuple[float, float]
    reachable: bool
    predicted_coverage: float
    predicted_degradation: float
    physical_risk: float


@dataclass(frozen=True)
class RepairPlanningContext:
    """Typed planner input containing no oracle or future state."""

    paired_world_id: str
    current_step: int
    current_xy: tuple[float, float]
    current_viewpoint_name: str
    current_predicted_coverage: float
    current_predicted_degradation: float
    current_physical_risk: float
    side_viewpoints: tuple[PublicViewpoint, ...]
    visited_actions: frozenset[str]
    observations_taken: int
    replans_taken: int


@dataclass(frozen=True)
class RepairAction:
    name: str
    kind: str
    target_xy: tuple[float, float]
    wait_steps: int
    synchronous_modalities: bool


@dataclass(frozen=True)
class RepairFeatureVector:
    expected_contract_repair: float
    new_measurement_root_gain: float
    conflict_discrimination: float
    predicted_coverage: float
    normalized_travel_cost: float
    revisit_penalty: float
    predicted_degradation: float
    physical_risk: float


@dataclass(frozen=True)
class RepairScore:
    action: RepairAction
    features: RepairFeatureVector
    utility: float
    reachable: bool
    eligible: bool
    gap_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairDecision:
    status: str
    reason: str
    selected_action: RepairAction | None
    ranking: tuple[RepairScore, ...]

    @property
    def should_safe_fallback(self) -> bool:
        return self.selected_action is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _xy(raw: Any, field_name: str) -> tuple[float, float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"{field_name} must contain exactly two coordinates")
    result = (float(raw[0]), float(raw[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{field_name} coordinates must be finite")
    return result


def build_planning_context(
    *,
    public_context: Mapping[str, Any],
    current_step: int,
    current_xy: tuple[float, float],
    current_viewpoint_name: str,
    current_predicted_coverage: float = 0.50,
    current_predicted_degradation: float = 0.35,
    current_physical_risk: float = 0.02,
    visited_actions: Iterable[str] = (),
    observations_taken: int = 0,
    replans_taken: int = 0,
) -> RepairPlanningContext:
    """Sanitise a public scenario view into the planner's typed input."""
    assert_public_context_safe(public_context)
    allowed_top_level = {
        "schema_version",
        "paired_world_id",
        "region_id",
        "known_static_map",
        "candidate_viewpoints",
        "sensor_model",
    }
    unexpected = set(public_context) - allowed_top_level
    if unexpected:
        raise ValueError(f"unsupported public planner context keys: {sorted(unexpected)}")
    if current_step < 0 or observations_taken < 0 or replans_taken < 0:
        raise ValueError("step and counters must be non-negative")

    raw_candidates = public_context.get("candidate_viewpoints")
    if not isinstance(raw_candidates, list):
        raise ValueError("public_context.candidate_viewpoints must be a list")
    viewpoints: list[PublicViewpoint] = []
    names: set[str] = set()
    allowed_candidate_keys = {
        "name",
        "xy",
        "reachable",
        "predicted_coverage",
        "predicted_degradation",
        "physical_risk",
    }
    for raw in raw_candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("each candidate_viewpoint must be an object")
        extra = set(raw) - allowed_candidate_keys
        if extra:
            raise ValueError(f"unsupported candidate keys: {sorted(extra)}")
        name = str(raw.get("name", ""))
        if name not in SIDE_VIEW_NAMES or name in names:
            raise ValueError(f"invalid or duplicate side viewpoint: {name!r}")
        names.add(name)
        viewpoints.append(
            PublicViewpoint(
                name=name,
                xy=_xy(raw.get("xy"), f"{name}.xy"),
                reachable=bool(raw.get("reachable")),
                predicted_coverage=_unit_interval(
                    f"{name}.predicted_coverage", raw.get("predicted_coverage")
                ),
                predicted_degradation=_unit_interval(
                    f"{name}.predicted_degradation",
                    raw.get("predicted_degradation"),
                ),
                physical_risk=_unit_interval(
                    f"{name}.physical_risk", raw.get("physical_risk")
                ),
            )
        )
    if names != set(SIDE_VIEW_NAMES):
        missing = sorted(set(SIDE_VIEW_NAMES) - names)
        raise ValueError(f"public context is missing side viewpoints: {missing}")

    return RepairPlanningContext(
        paired_world_id=str(public_context.get("paired_world_id", "unknown")),
        current_step=current_step,
        current_xy=_xy(current_xy, "current_xy"),
        current_viewpoint_name=str(current_viewpoint_name),
        current_predicted_coverage=_unit_interval(
            "current_predicted_coverage", current_predicted_coverage
        ),
        current_predicted_degradation=_unit_interval(
            "current_predicted_degradation", current_predicted_degradation
        ),
        current_physical_risk=_unit_interval(
            "current_physical_risk", current_physical_risk
        ),
        side_viewpoints=tuple(sorted(viewpoints, key=lambda item: item.name)),
        visited_actions=frozenset(str(item) for item in visited_actions),
        observations_taken=observations_taken,
        replans_taken=replans_taken,
    )


def _mean(values: Iterable[float]) -> float:
    materialised = tuple(values)
    return sum(materialised) / len(materialised) if materialised else 0.0


def _feature_utility(features: RepairFeatureVector) -> float:
    return sum(
        UTILITY_WEIGHTS[name] * getattr(features, name) for name in UTILITY_WEIGHTS
    )


class RepairPlanner:
    """Rank diagnostic observation actions that can repair an Action Contract."""

    def __init__(self, *, max_observations: int = 4, max_replans: int = 2) -> None:
        if max_observations < 1 or max_replans < 0:
            raise ValueError("max_observations must be positive and max_replans non-negative")
        self.max_observations = max_observations
        self.max_replans = max_replans

    @staticmethod
    def _actions(context: RepairPlanningContext) -> tuple[tuple[RepairAction, PublicViewpoint | None], ...]:
        same = RepairAction(
            name=ACTION_SAME_VIEW,
            kind="same_view",
            target_xy=context.current_xy,
            wait_steps=0,
            synchronous_modalities=True,
        )
        wait = RepairAction(
            name=ACTION_WAIT,
            kind="wait",
            target_xy=context.current_xy,
            wait_steps=20,
            synchronous_modalities=True,
        )
        side = tuple(
            (
                RepairAction(
                    name=viewpoint.name,
                    kind="side_view",
                    target_xy=viewpoint.xy,
                    wait_steps=0,
                    synchronous_modalities=True,
                ),
                viewpoint,
            )
            for viewpoint in context.side_viewpoints
        )
        return ((same, None), (wait, None), *side)

    @staticmethod
    def _score_action(
        action: RepairAction,
        viewpoint: PublicViewpoint | None,
        gap: BeliefGap,
        context: RepairPlanningContext,
    ) -> RepairScore:
        kind = action.kind
        coverage = (
            context.current_predicted_coverage
            if viewpoint is None
            else viewpoint.predicted_coverage
        )
        degradation = (
            context.current_predicted_degradation
            if viewpoint is None
            else viewpoint.predicted_degradation
        )
        physical_risk = (
            0.0
            if kind == "wait"
            else (
                context.current_physical_risk
                if viewpoint is None
                else viewpoint.physical_risk
            )
        )
        repair_values = [
            _REPAIR_EFFECTIVENESS[reason][kind] for reason in gap.reasons
        ]
        discrimination_values = [
            _CONFLICT_DISCRIMINATION[reason][kind] for reason in gap.reasons
        ]
        expected_repair = _mean(repair_values)
        discrimination = _mean(discrimination_values)
        travel_cost = min(1.0, math.dist(context.current_xy, action.target_xy) / 4.0)

        # A low-coverage repair can only work to the extent that the public
        # geometry model predicts better coverage.  Likewise, an out-of-domain
        # repair is less promising when predicted degradation remains high.
        if "low_coverage" in gap.reasons:
            expected_repair *= 0.5 + 0.5 * coverage
        if "calibration_not_applicable" in gap.reasons:
            expected_repair *= 1.0 - 0.5 * degradation
        if "insufficient_roots" in gap.reasons and kind == "side_view":
            # A second root only repairs the contract if the existing fresh
            # root survives the trip.  Travel is a public, causal predictor;
            # this does not inspect a future observation or scene truth.
            expected_repair *= max(0.20, 1.0 - 2.0 * travel_cost)

        revisit_penalty = 1.0 if action.name in context.visited_actions else 0.0
        features = RepairFeatureVector(
            expected_contract_repair=expected_repair,
            new_measurement_root_gain=_NEW_ROOT_GAIN[kind],
            conflict_discrimination=discrimination,
            predicted_coverage=coverage,
            normalized_travel_cost=travel_cost,
            revisit_penalty=revisit_penalty,
            predicted_degradation=degradation,
            physical_risk=physical_risk,
        )
        reachable = viewpoint is None or viewpoint.reachable
        eligible = reachable
        return RepairScore(
            action=action,
            features=features,
            utility=_feature_utility(features),
            reachable=reachable,
            eligible=eligible,
            gap_reasons=gap.reasons,
        )

    def rank(
        self,
        gap: BeliefGap | Iterable[str],
        context: RepairPlanningContext,
    ) -> list[RepairScore]:
        if not isinstance(gap, BeliefGap):
            gap = BeliefGap.from_reasons(gap)
        if not gap.reasons:
            return []
        scores = [
            self._score_action(action, viewpoint, gap, context)
            for action, viewpoint in self._actions(context)
        ]
        return sorted(
            scores,
            key=lambda item: (
                not item.eligible,
                -item.utility,
                item.action.name,
            ),
        )

    def choose(
        self,
        gap: BeliefGap | Iterable[str],
        context: RepairPlanningContext,
    ) -> RepairDecision:
        if not isinstance(gap, BeliefGap):
            gap = BeliefGap.from_reasons(gap)
        if not gap.reasons:
            return RepairDecision("safe_fallback", "no_belief_gap", None, ())
        if context.observations_taken >= self.max_observations:
            return RepairDecision(
                "safe_fallback", "max_observations_reached", None, ()
            )
        ranking = tuple(self.rank(gap, context))
        selected = next(
            (
                score
                for score in ranking
                if score.eligible
                and score.utility > 0.0
                and not (
                    score.action.kind == "side_view"
                    and context.replans_taken >= self.max_replans
                )
            ),
            None,
        )
        if selected is None:
            if context.replans_taken >= self.max_replans and any(
                score.eligible
                and score.utility > 0.0
                and score.action.kind == "side_view"
                for score in ranking
            ):
                return RepairDecision(
                    "safe_fallback", "max_replans_reached", None, ranking
                )
            return RepairDecision(
                "safe_fallback", "no_positive_utility", None, ranking
            )
        return RepairDecision(
            "selected", "highest_positive_utility", selected.action, ranking
        )
