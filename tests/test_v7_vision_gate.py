"""v7 vision contract: modality conflict, vision root, proxy determinism."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import SENSOR_VERSION_V6, build_robot_claim_v2
from v7_contracts import CorridorContractV7, evaluate_corridor_contract_v7
from v7_vision_claims import (
    VISION_MODALITY,
    propose_vision,
    synthetic_rgb_for_label,
    vision_proposal_to_claim_v2,
)


def _geo(
    *,
    value: str = "clear",
    capture: str = "geo-1",
    observer: str = "scout",
    corridor: str = "corridor_a",
    step: int = 10,
) -> object:
    return build_robot_claim_v2(
        fact_id=f"region:{corridor}",
        predicate="carrier_traversable",
        value=value,
        confidence=0.85,
        observed_step=step,
        valid_until_step=step + 500,
        modality="depth_geometry",
        device_root_id=f"rgbd-{observer}-01",
        capture_root_id=capture,
        calibration_id=SENSOR_VERSION_V6,
        pose_version="base-link-v6",
        model_id="geo-test",
        artifact_sha256=canonical_sha256({"c": capture, "v": value}),
        observer_agent_id=observer,
        intended_actor_id="carrier",
        received_step=step,
        quality=0.85,
        visibility=0.85,
        scope=ClaimScope("carrier", "payload_loaded", corridor),
    )


def _vis(
    *,
    value: str = "clear",
    capture: str = "vis-1",
    observer: str = "scout",
    corridor: str = "corridor_a",
    step: int = 10,
) -> object:
    return build_robot_claim_v2(
        fact_id=f"region:{corridor}",
        predicate="carrier_traversable",
        value=value,
        confidence=0.8,
        observed_step=step,
        valid_until_step=step + 500,
        modality=VISION_MODALITY,
        device_root_id=f"rgb-{observer}-01",
        capture_root_id=capture,
        calibration_id=SENSOR_VERSION_V6,
        pose_version="base-link-v7",
        model_id="look-twice-v7-vision/test/1",
        artifact_sha256=canonical_sha256({"c": capture, "v": value, "m": "vis"}),
        observer_agent_id=observer,
        intended_actor_id="carrier",
        received_step=step,
        quality=0.8,
        visibility=0.8,
        scope=ClaimScope("carrier", "payload_loaded", corridor),
    )


class V7VisionGateTests(unittest.TestCase):
    def test_modality_conflict_denies(self) -> None:
        contract = CorridorContractV7(
            corridor_id="corridor_a",
            evidence_age_limit=2000,
            min_distinct_capture_roots=2,
            enforce_modality_conflict=True,
        )
        claims = [
            _geo(value="clear", capture="g1"),
            _geo(value="clear", capture="g2"),
            _vis(value="blocked", capture="v1"),
        ]
        dec = evaluate_corridor_contract_v7(claims, contract, current_step=20)
        self.assertFalse(dec.admitted)
        self.assertIn("modality_conflict", dec.reasons)

    def test_dual_modality_clear_can_admit(self) -> None:
        contract = CorridorContractV7(
            corridor_id="corridor_a",
            evidence_age_limit=2000,
            min_distinct_capture_roots=2,
            require_vision_clear_root=True,
            enforce_modality_conflict=True,
        )
        claims = [
            _geo(value="clear", capture="g1"),
            _geo(value="clear", capture="g2"),
            _vis(value="clear", capture="v1"),
            _vis(value="clear", capture="v2"),
        ]
        dec = evaluate_corridor_contract_v7(claims, contract, current_step=20)
        self.assertTrue(dec.admitted)
        self.assertEqual(dec.reasons, ())

    def test_missing_vision_root_when_required(self) -> None:
        contract = CorridorContractV7(
            corridor_id="corridor_a",
            evidence_age_limit=2000,
            min_distinct_capture_roots=2,
            require_vision_clear_root=True,
        )
        claims = [
            _geo(value="clear", capture="g1"),
            _geo(value="clear", capture="g2"),
        ]
        dec = evaluate_corridor_contract_v7(claims, contract, current_step=20)
        self.assertFalse(dec.admitted)
        self.assertIn("missing_vision_root", dec.reasons)

    def test_proxy_deterministic(self) -> None:
        rgb = synthetic_rgb_for_label("blocked", seed=7)
        a = propose_vision(rgb, backend="heuristic_rgb_proxy")
        b = propose_vision(rgb, backend="heuristic_rgb_proxy")
        self.assertEqual(a.value, b.value)
        self.assertEqual(a.input_sha256, b.input_sha256)
        self.assertEqual(a.backend, "heuristic_rgb_proxy")

    def test_proposal_to_claim_modality(self) -> None:
        rgb = synthetic_rgb_for_label("clear", seed=1)
        prop = propose_vision(rgb)
        claim = vision_proposal_to_claim_v2(
            prop, agent_id="scout", corridor_id="corridor_a", step=5
        )
        self.assertEqual(claim.modality, VISION_MODALITY)
        self.assertEqual(claim.intended_actor_id, "carrier")


if __name__ == "__main__":
    unittest.main()
