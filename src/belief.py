"""Look Twice 的离散与概率证据结算、行动准入逻辑。"""

import math
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


class ProbabilisticRegionBelief:
    """v3 概率 belief：用加权 log-odds 累积证据并显式记录熵。"""

    def __init__(
        self,
        *,
        confirmation_probability: float = 0.82,
        maximum_confirmation_entropy: float = 0.70,
        max_age_steps: Optional[int] = 60,
    ) -> None:
        if not 0.5 < confirmation_probability < 1.0:
            raise ValueError("confirmation_probability must be between 0.5 and 1")
        self.confirmation_probability = confirmation_probability
        self.maximum_confirmation_entropy = maximum_confirmation_entropy
        self.max_age_steps = max_age_steps
        self.log_odds = 0.0
        self.evidence: list[Observation] = []
        self.status = BeliefStatus.UNKNOWN
        self.history: list[BeliefStatus] = [self.status]
        self.confirmed_step: Optional[int] = None
        self.epoch_start = 0
        self.calibration_trace: list[dict[str, Any]] = []

    @property
    def p_blocked(self) -> float:
        return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, self.log_odds))))

    @property
    def entropy(self) -> float:
        probability = min(1.0 - 1e-12, max(1e-12, self.p_blocked))
        return -probability * math.log2(probability) - (1.0 - probability) * math.log2(
            1.0 - probability
        )

    def add_observation(
        self,
        observation: Observation,
        *,
        evidence_weight: float = 1.0,
    ) -> BeliefStatus:
        if observation.result not in {"clear", "blocked", "inconclusive"}:
            raise ValueError(f"Unsupported observation result: {observation.result}")
        if not 0.0 <= observation.confidence <= 1.0:
            raise ValueError("Observation confidence must be between 0 and 1")
        if not 0.0 <= evidence_weight <= 1.0:
            raise ValueError("evidence_weight must be between 0 and 1")

        self.evidence.append(observation)
        if observation.result == "inconclusive":
            # 无结论证据不伪造方向，只让既有结论轻微回归未知。
            self.log_odds *= 0.90
        else:
            reliability = min(0.995, max(0.505, observation.confidence))
            contribution = math.log(reliability / (1.0 - reliability))
            contribution *= evidence_weight
            self.log_odds += contribution if observation.result == "blocked" else -contribution

        new_status = self.resolve_state(observation.result)
        if new_status != self.status:
            self.status = new_status
            self.history.append(new_status)
        if self.status in {
            BeliefStatus.CONFIRMED_CLEAR,
            BeliefStatus.CONFIRMED_BLOCKED,
        }:
            self.confirmed_step = observation.step
        self.calibration_trace.append(
            {
                "step": observation.step,
                "result": observation.result,
                "confidence": observation.confidence,
                "evidence_weight": evidence_weight,
                "p_blocked": self.p_blocked,
                "entropy": self.entropy,
                "status": self.status.value,
            }
        )
        return self.status

    def resolve_state(self, latest_result: Optional[str] = None) -> BeliefStatus:
        active = self.evidence[self.epoch_start :]
        if not active:
            return BeliefStatus.UNKNOWN
        if latest_result == "inconclusive":
            return BeliefStatus.UNCERTAIN
        if len(active) == 1:
            return (
                BeliefStatus.PROVISIONAL_BLOCKED
                if self.p_blocked >= 0.5
                else BeliefStatus.PROVISIONAL_CLEAR
            )
        if (
            self.p_blocked >= self.confirmation_probability
            and self.entropy <= self.maximum_confirmation_entropy
        ):
            return BeliefStatus.CONFIRMED_BLOCKED
        if (
            self.p_blocked <= 1.0 - self.confirmation_probability
            and self.entropy <= self.maximum_confirmation_entropy
        ):
            return BeliefStatus.CONFIRMED_CLEAR
        return BeliefStatus.UNCERTAIN

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
            self.log_odds = 0.0
            self.calibration_trace.append(
                {
                    "step": current_step,
                    "result": "stale",
                    "confidence": 0.0,
                    "evidence_weight": 0.0,
                    "p_blocked": self.p_blocked,
                    "entropy": self.entropy,
                    "status": self.status.value,
                }
            )
        return self.status

    def is_action_allowed(self, action: str, current_step: Optional[int] = None) -> bool:
        if current_step is not None:
            self.refresh_status(current_step)
        if action == "go_to_goal":
            return self.status == BeliefStatus.CONFIRMED_CLEAR
        if action == "go_to_detour":
            return self.status == BeliefStatus.CONFIRMED_BLOCKED
        raise ValueError(f"Unsupported action: {action}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "p_blocked": self.p_blocked,
            "entropy": self.entropy,
            "log_odds": self.log_odds,
            "evidence_count": len(self.evidence),
        }
