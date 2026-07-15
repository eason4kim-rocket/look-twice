import hashlib
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_claims import ClaimScope, RobotClaim, build_robot_claim, summarize_lineage


ARTIFACT_A = hashlib.sha256(b"capture-a").hexdigest()
ARTIFACT_B = hashlib.sha256(b"capture-b").hexdigest()


def make_claim(**overrides):
    values = {
        "fact_id": "region-01",
        "predicate": "traversable",
        "value": "clear",
        "confidence": 0.9,
        "observed_step": 10,
        "valid_until_step": 70,
        "modality": "depth_geometry",
        "device_root_id": "camera-front",
        "capture_root_id": "capture-a",
        "calibration_id": "depth-v1",
        "pose_version": "pose-10",
        "model_id": "geometry-v1",
        "artifact_sha256": ARTIFACT_A,
        "scope": ClaimScope("amr-01", "empty", "risk-region-01"),
    }
    values.update(overrides)
    return build_robot_claim(**values)


class RobotClaimTests(unittest.TestCase):
    def test_wire_round_trip_and_immutability(self) -> None:
        claim = make_claim(parent_claim_ids=("raw-01",))
        self.assertEqual(RobotClaim.from_wire(claim.to_wire()), claim)
        with self.assertRaises(FrozenInstanceError):
            claim.value = "blocked"  # type: ignore[misc]

    def test_stable_id_and_no_oracle_field(self) -> None:
        first = make_claim()
        second = make_claim()
        self.assertEqual(first.claim_id, second.claim_id)
        payload = first.to_wire()
        payload["oracle"] = "blocked"
        with self.assertRaisesRegex(ValueError, "oracle"):
            RobotClaim.from_wire(payload)

    def test_same_capture_modalities_count_as_one_root(self) -> None:
        depth = make_claim()
        semantic = make_claim(
            modality="simulated_semantic_sensor",
            model_id="semantic-proxy-v1",
            artifact_sha256=ARTIFACT_B,
            value="blocked",
        )
        summary = summarize_lineage((depth, semantic))
        self.assertEqual(summary.distinct_measurement_roots, 1)
        self.assertEqual(summary.measurement_root_ids, ("capture-a",))

    def test_duplicate_artifact_and_unknown_root_do_not_add_roots(self) -> None:
        strong = make_claim(quality=0.9)
        echo = make_claim(
            modality="simulated_semantic_sensor",
            model_id="echo-v1",
            quality=0.5,
        )
        unknown = make_claim(
            artifact_sha256=ARTIFACT_B,
            capture_root_id="unknown",
            observed_step=11,
            valid_until_step=71,
        )
        summary = summarize_lineage((strong, echo, unknown))
        self.assertEqual(summary.distinct_measurement_roots, 1)
        self.assertIn(echo.claim_id, summary.discounted_claim_ids)
        self.assertEqual(summary.unknown_root_claim_ids, (unknown.claim_id,))

    def test_static_map_is_not_a_measurement_root(self) -> None:
        static_map = make_claim(
            modality="static_map",
            device_root_id="map-server",
            capture_root_id="map-version-4",
            model_id="warehouse-map-v4",
        )
        self.assertEqual(summarize_lineage((static_map,)).distinct_measurement_roots, 0)


if __name__ == "__main__":
    unittest.main()
