import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_evidence import SENSOR_VERSION, SyntheticEvidenceSource, process_evidence_frame
from v4_scenario import sample_v4_scenario


class V4EvidenceTests(unittest.TestCase):
    def capture(self, profile: str, seed: int, *, index: int = 0, action: str = "initial"):
        scenario = sample_v4_scenario(profile, seed)
        source = SyntheticEvidenceSource()
        candidate = scenario.public_context["candidate_viewpoints"][0]
        frame = source.raw_frame(
            scenario=scenario,
            viewpoint=candidate["name"],
            viewpoint_xy=tuple(candidate["xy"]),
            predicted_coverage=candidate["predicted_coverage"],
            capture_step=100 + index * 20,
        )
        return scenario, process_evidence_frame(
            frame,
            scenario,
            observation_index=index,
            repair_action_kind=action,
        )

    def test_capture_is_deterministic_and_has_independent_modalities(self) -> None:
        _, first = self.capture("independent-noise", 50000)
        _, second = self.capture("independent-noise", 50000)
        self.assertEqual(
            [claim.to_wire() for claim in first.claims],
            [claim.to_wire() for claim in second.claims],
        )
        self.assertEqual(
            first.corrupted_artifact_sha256, second.corrupted_artifact_sha256
        )
        self.assertEqual(first.corruption.derived_seed, second.corruption.derived_seed)
        self.assertEqual(
            {claim.modality for claim in first.claims},
            {"depth_geometry", "simulated_semantic_sensor"},
        )
        self.assertEqual(len({claim.capture_root_id for claim in first.claims}), 1)

    def test_online_record_contains_no_oracle_truth(self) -> None:
        _, capture = self.capture("dynamic-change", 50001)
        serialized = str(capture.online_record()).lower()
        self.assertNotIn("oracle", serialized)
        self.assertNotIn("truth_blocked", serialized)

    def test_evidence_echo_keeps_artifact_and_declares_parent(self) -> None:
        scenario, capture = self.capture("evidence-echo", 50000)
        self.assertEqual(
            len(capture.claims),
            2 + scenario.fault_realization.evidence_echo_count,
        )
        semantic = capture.claims[1]
        for echo in capture.claims[2:]:
            self.assertEqual(echo.artifact_sha256, semantic.artifact_sha256)
            self.assertEqual(echo.parent_claim_ids, (semantic.claim_id,))

    def test_time_skew_is_repaired_by_synchronous_recapture(self) -> None:
        _, initial = self.capture("time-skew", 50000)
        _, repaired = self.capture("time-skew", 50000, index=1, action="same_view")
        self.assertGreater(initial.claims[1].temporal_skew, 2)
        self.assertEqual(repaired.claims[1].temporal_skew, 0)

    def test_pose_drift_changes_declared_version_only_on_first_capture(self) -> None:
        _, initial = self.capture("pose-calibration-drift", 50000)
        _, repaired = self.capture(
            "pose-calibration-drift", 50000, index=1, action="side_view"
        )
        self.assertNotEqual(initial.corruption.sensor_version, SENSOR_VERSION)
        self.assertEqual(repaired.corruption.sensor_version, SENSOR_VERSION)

    def test_structured_dropout_is_visible_in_audit(self) -> None:
        _, capture = self.capture("structured-depth-dropout", 50000)
        self.assertGreater(capture.corruption.structured_dropout_fraction, 0.0)
        self.assertEqual(capture.depth_result["result"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
