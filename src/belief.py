"""Look Twice 的最小证据结算与行动准入逻辑。"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


@dataclass(frozen=True)
class Observation:
    """记录机器人在某个观察点获得的一条证据。"""

    viewpoint: str
    result: str
    confidence: float
    step: int
    source: str = "geometry"
    artifact: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class BeliefStatus(str, Enum):
    UNKNOWN = "unknown"
    PROVISIONAL_CLEAR = "provisional_clear"
    PROVISIONAL_BLOCKED = "provisional_blocked"
    UNCERTAIN = "uncertain"
    CONFIRMED_CLEAR = "confirmed_clear"
    CONFIRMED_BLOCKED = "confirmed_blocked"
    STALE = "stale"


class RegionBelief:
    """根据最近观察结算区域状态，并为高风险动作把关。"""

    def __init__(
        self,
        confirmation_threshold: float = 0.8,
        max_age_steps: Optional[int] = None,
    ) -> None:
        self.confirmation_threshold = confirmation_threshold
        self.max_age_steps = max_age_steps
        self.evidence: list[Observation] = []
        self.status = BeliefStatus.UNKNOWN
        self.history: list[BeliefStatus] = [self.status]
        self.confirmed_step: Optional[int] = None
        self.epoch_start = 0

    def add_observation(self, observation: Observation) -> BeliefStatus:
        if observation.result not in {"clear", "blocked", "inconclusive"}:
            raise ValueError(f"Unsupported observation result: {observation.result}")
        if not 0.0 <= observation.confidence <= 1.0:
            raise ValueError("Observation confidence must be between 0 and 1")

        self.evidence.append(observation)
        new_status = self.resolve_state()
        if new_status != self.status:
            self.status = new_status
            self.history.append(new_status)
        if self.status in {
            BeliefStatus.CONFIRMED_CLEAR,
            BeliefStatus.CONFIRMED_BLOCKED,
        }:
            self.confirmed_step = observation.step
        return self.status

    def resolve_state(self) -> BeliefStatus:
        active_evidence = self.evidence[self.epoch_start :]
        if not active_evidence:
            return BeliefStatus.UNKNOWN

        latest = active_evidence[-1]
        if latest.result == "inconclusive":
            return BeliefStatus.UNCERTAIN
        if len(active_evidence) == 1:
            if latest.result == "clear":
                return BeliefStatus.PROVISIONAL_CLEAR
            return BeliefStatus.PROVISIONAL_BLOCKED

        previous = active_evidence[-2]
        if previous.result == "inconclusive":
            return BeliefStatus.UNCERTAIN
        if latest.result != previous.result:
            return BeliefStatus.UNCERTAIN

        mean_confidence = (latest.confidence + previous.confidence) / 2.0
        if mean_confidence < self.confirmation_threshold:
            return BeliefStatus.UNCERTAIN

        if latest.result == "clear":
            return BeliefStatus.CONFIRMED_CLEAR
        return BeliefStatus.CONFIRMED_BLOCKED

    def refresh_status(self, current_step: int) -> BeliefStatus:
        if (
            self.max_age_steps is not None
            and self.confirmed_step is not None
            and self.status
            in {BeliefStatus.CONFIRMED_CLEAR, BeliefStatus.CONFIRMED_BLOCKED}
            and current_step - self.confirmed_step > self.max_age_steps
        ):
            self.status = BeliefStatus.STALE
            self.history.append(self.status)
            self.epoch_start = len(self.evidence)
        return self.status

    def is_action_allowed(
        self,
        action: str,
        current_step: Optional[int] = None,
    ) -> bool:
        if current_step is not None:
            self.refresh_status(current_step)
        if action == "go_to_goal":
            return self.status == BeliefStatus.CONFIRMED_CLEAR
        if action == "go_to_detour":
            return self.status == BeliefStatus.CONFIRMED_BLOCKED
        raise ValueError(f"Unsupported action: {action}")
