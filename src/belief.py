"""Look Twice 的最小证据结算与行动准入逻辑。"""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Observation:
    """记录机器人在某个观察点获得的一条证据。"""

    viewpoint: str
    result: str
    confidence: float
    step: int


class BeliefStatus(str, Enum):
    UNKNOWN = "unknown"
    PROVISIONAL_CLEAR = "provisional_clear"
    PROVISIONAL_BLOCKED = "provisional_blocked"
    UNCERTAIN = "uncertain"
    CONFIRMED_CLEAR = "confirmed_clear"
    CONFIRMED_BLOCKED = "confirmed_blocked"


class RegionBelief:
    """根据最近观察结算区域状态，并为高风险动作把关。"""

    def __init__(self, confirmation_threshold: float = 0.8) -> None:
        self.confirmation_threshold = confirmation_threshold
        self.evidence: list[Observation] = []
        self.status = BeliefStatus.UNKNOWN
        self.history: list[BeliefStatus] = [self.status]

    def add_observation(self, observation: Observation) -> BeliefStatus:
        if observation.result not in {"clear", "blocked"}:
            raise ValueError(f"Unsupported observation result: {observation.result}")
        if not 0.0 <= observation.confidence <= 1.0:
            raise ValueError("Observation confidence must be between 0 and 1")

        self.evidence.append(observation)
        new_status = self.resolve_state()
        if new_status != self.status:
            self.status = new_status
            self.history.append(new_status)
        return self.status

    def resolve_state(self) -> BeliefStatus:
        if not self.evidence:
            return BeliefStatus.UNKNOWN

        latest = self.evidence[-1]
        if len(self.evidence) == 1:
            if latest.result == "clear":
                return BeliefStatus.PROVISIONAL_CLEAR
            return BeliefStatus.PROVISIONAL_BLOCKED

        previous = self.evidence[-2]
        if latest.result != previous.result:
            return BeliefStatus.UNCERTAIN

        mean_confidence = (latest.confidence + previous.confidence) / 2.0
        if mean_confidence < self.confirmation_threshold:
            return BeliefStatus.UNCERTAIN

        if latest.result == "clear":
            return BeliefStatus.CONFIRMED_CLEAR
        return BeliefStatus.CONFIRMED_BLOCKED

    def is_action_allowed(self, action: str) -> bool:
        if action == "go_to_goal":
            return self.status == BeliefStatus.CONFIRMED_CLEAR
        if action == "go_to_detour":
            return self.status == BeliefStatus.CONFIRMED_BLOCKED
        raise ValueError(f"Unsupported action: {action}")
