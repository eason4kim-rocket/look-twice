"""Multi-agent claim communication queue with delay/drop/echo faults."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from v6_claims import RobotClaimV2, build_robot_claim_v2


@dataclass
class PendingMessage:
    deliver_at_step: int
    claim: RobotClaimV2


@dataclass
class CommunicationQueue:
    """In-order or delayed delivery of claims to the carrier inbox."""

    delay_steps: int = 0
    drop_rate: float = 0.0
    echo_fanout: int = 1
    reorder: bool = False
    seed: int = 0
    _rng: random.Random = field(init=False, repr=False)
    _pending: list[PendingMessage] = field(default_factory=list)
    delivered: list[RobotClaimV2] = field(default_factory=list)
    dropped: int = 0
    echoed: int = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed ^ 0xC0FFEE)
        self.echo_fanout = max(1, int(self.echo_fanout))
        self.delay_steps = max(0, int(self.delay_steps))
        self.drop_rate = min(1.0, max(0.0, float(self.drop_rate)))

    def publish(self, claim: RobotClaimV2, current_step: int) -> int:
        """Enqueue claim (+ optional echoes). Returns number accepted into queue."""
        accepted = 0
        copies = self.echo_fanout
        for i in range(copies):
            if self._rng.random() < self.drop_rate:
                self.dropped += 1
                continue
            jitter = 0
            if self.reorder:
                jitter = self._rng.randint(0, max(1, self.delay_steps))
            deliver_at = current_step + self.delay_steps + jitter
            # Echoes keep the same communication_root_id and capture_root_id.
            if i == 0:
                msg_claim = claim
            else:
                self.echoed += 1
                msg_claim = build_robot_claim_v2(
                    fact_id=claim.fact_id,
                    predicate=claim.predicate,
                    value=claim.value,
                    confidence=claim.confidence,
                    observed_step=claim.observed_step,
                    valid_until_step=claim.valid_until_step,
                    modality=claim.modality,
                    device_root_id=claim.device_root_id,
                    capture_root_id=claim.capture_root_id,
                    calibration_id=claim.calibration_id,
                    pose_version=claim.pose_version,
                    model_id=claim.model_id,
                    artifact_sha256=claim.artifact_sha256,
                    observer_agent_id=claim.observer_agent_id,
                    intended_actor_id=claim.intended_actor_id,
                    received_step=claim.received_step,
                    communication_root_id=claim.communication_root_id,
                    parent_claim_ids=claim.parent_claim_ids,
                    communication_path=claim.communication_path + (f"echo:{i}",),
                    quality=claim.quality,
                    visibility=claim.visibility,
                    temporal_skew=claim.temporal_skew,
                    scope=claim.scope,
                )
            self._pending.append(PendingMessage(deliver_at, msg_claim))
            accepted += 1
        return accepted

    def poll(self, current_step: int) -> list[RobotClaimV2]:
        """Deliver due messages with received_step stamped at delivery."""
        due: list[PendingMessage] = []
        remain: list[PendingMessage] = []
        for item in self._pending:
            if item.deliver_at_step <= current_step:
                due.append(item)
            else:
                remain.append(item)
        self._pending = remain
        out: list[RobotClaimV2] = []
        for item in due:
            claim = item.claim
            # Stamp receive time without altering observed_step.
            # received_step cannot precede observed_step even if the queue is polled early.
            recv = max(int(current_step), int(claim.observed_step))
            delivered = build_robot_claim_v2(
                fact_id=claim.fact_id,
                predicate=claim.predicate,
                value=claim.value,
                confidence=claim.confidence,
                observed_step=claim.observed_step,
                valid_until_step=claim.valid_until_step,
                modality=claim.modality,
                device_root_id=claim.device_root_id,
                capture_root_id=claim.capture_root_id,
                calibration_id=claim.calibration_id,
                pose_version=claim.pose_version,
                model_id=claim.model_id,
                artifact_sha256=claim.artifact_sha256,
                observer_agent_id=claim.observer_agent_id,
                intended_actor_id=claim.intended_actor_id,
                received_step=recv,
                communication_root_id=claim.communication_root_id,
                parent_claim_ids=claim.parent_claim_ids,
                communication_path=claim.communication_path,
                quality=claim.quality,
                visibility=claim.visibility,
                temporal_skew=claim.temporal_skew,
                scope=claim.scope,
            )
            out.append(delivered)
            self.delivered.append(delivered)
        return out

    def stats(self) -> dict[str, Any]:
        return {
            "pending": len(self._pending),
            "delivered": len(self.delivered),
            "dropped": self.dropped,
            "echoed": self.echoed,
            "delay_steps": self.delay_steps,
            "drop_rate": self.drop_rate,
            "echo_fanout": self.echo_fanout,
        }


__all__ = ("CommunicationQueue", "PendingMessage")
