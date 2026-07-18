"""CommunicationQueue received_step semantics (network arrival, not poll time)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import SENSOR_VERSION_V6, build_robot_claim_v2
from v6_communication import CommunicationQueue
from v6_contracts import CorridorContract, evaluate_corridor_contract


def _claim(*, observed: int, capture: str = "cap", salt: str = "s") -> object:
    return build_robot_claim_v2(
        fact_id="region:corridor_a",
        predicate="carrier_traversable",
        value="clear",
        confidence=0.9,
        observed_step=observed,
        valid_until_step=observed + 2000,
        modality="vision_semantic_v7",
        device_root_id="rgb-scout-01",
        capture_root_id=capture,
        calibration_id=SENSOR_VERSION_V6,
        pose_version="base-link-v7",
        model_id="look-twice-v7-vision/test/1",
        artifact_sha256=canonical_sha256({"c": capture, "s": salt}),
        observer_agent_id="scout",
        intended_actor_id="carrier",
        received_step=observed,
        communication_root_id=capture,
        quality=0.85,
        visibility=0.85,
        scope=ClaimScope("carrier", "payload_loaded", "corridor_a"),
    )


class ReceivedStepSemanticsTests(unittest.TestCase):
    def test_publish_100_delay_5_poll_500_received_105(self) -> None:
        q = CommunicationQueue(delay_steps=5, seed=0)
        q.publish(_claim(observed=100, capture="c1", salt="a"), current_step=100)
        self.assertEqual(q.poll(104), [])
        got = q.poll(500)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].received_step, 105)
        self.assertEqual(got[0].observed_step, 100)

    def test_poll_before_deliver_at_empty(self) -> None:
        q = CommunicationQueue(delay_steps=5, seed=0)
        q.publish(_claim(observed=100, capture="c2", salt="b"), current_step=100)
        self.assertEqual(q.poll(104), [])
        self.assertEqual(len(q._pending), 1)

    def test_echo_same_physical_root(self) -> None:
        q = CommunicationQueue(delay_steps=5, echo_fanout=4, seed=3)
        q.publish(_claim(observed=20, capture="same", salt="e"), current_step=20)
        got = q.poll(25)
        self.assertEqual(len(got), 4)
        self.assertEqual({c.capture_root_id for c in got}, {"same"})
        self.assertEqual({c.communication_root_id for c in got}, {"same"})
        self.assertTrue(all(c.received_step == 25 for c in got))

    def test_late_poll_clear_claim_survives_contract_delay_limit(self) -> None:
        """Bug class of smoke 99001: late poll must not create communication_delay."""
        q = CommunicationQueue(delay_steps=5, seed=0)
        # Two independent clear side roots observed early.
        q.publish(_claim(observed=100, capture="side-a", salt="a"), current_step=100)
        q.publish(_claim(observed=110, capture="side-b", salt="b"), current_step=110)
        # Consumer only polls after long motion.
        got = q.poll(278)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0].received_step, 105)
        self.assertEqual(got[1].received_step, 115)
        contract = CorridorContract(
            corridor_id="corridor_a",
            communication_delay_limit=40,
            min_distinct_capture_roots=2,
            evidence_age_limit=2000,
        )
        # Age measured from observed; at step 120 both still fresh.
        dec = evaluate_corridor_contract(list(got), contract, current_step=120)
        self.assertNotIn("communication_delay", dec.reasons)
        # If we had stamped poll time 278, delay would be 178 > 40 and both filtered.
        for c in got:
            self.assertLessEqual(c.received_step - c.observed_step, 40)


if __name__ == "__main__":
    unittest.main()
