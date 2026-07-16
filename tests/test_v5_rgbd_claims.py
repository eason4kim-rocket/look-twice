"""Unit tests for v5 RGB-D → Claim path (shipped perception helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v4_perception import ImageROI
from v5_rgbd_claims import (
    CLAIMS_MODE_GENESIS_RGBD,
    CLAIMS_MODE_SYNTHETIC,
    V4_SENSOR_VERSION,
    claims_from_depth_and_segmentation,
    process_genesis_observation,
    runtime_supports_rgbd_claims,
)
from v4_evidence import RawEvidenceFrame, SyntheticEvidenceSource
from v4_scenario import sample_v4_scenario


class V5RgbdClaimsTests(unittest.TestCase):
    def test_claims_from_depth_segmentation_clear_blocked(self) -> None:
        h, w = 48, 64
        roi = ImageROI(10, 10, 50, 40)
        depth_clear = np.full((h, w), 3.0, dtype=np.float32)
        seg_clear = np.zeros((h, w), dtype=np.int32)
        seg_clear[12:38, 12:48] = 7  # target pixels
        d_claim, s_claim, audit = claims_from_depth_and_segmentation(
            depth=depth_clear,
            segmentation=seg_clear,
            risk_roi=roi,
            expected_clear_depth=3.0,
            obstacle_segmentation_idx=6,
            target_segmentation_idx=7,
            target_reference_pixels=roi.pixels,
            observed_step=10,
            valid_until_step=2010,
            capture_root_id="cap-unit-clear",
            device="cpu",
        )
        self.assertEqual(d_claim.modality, "depth_geometry")
        self.assertEqual(s_claim.modality, "simulated_semantic_sensor")
        self.assertEqual(d_claim.value, "clear")
        self.assertEqual(audit["claims_mode"], CLAIMS_MODE_GENESIS_RGBD)
        self.assertEqual(d_claim.calibration_id, V4_SENSOR_VERSION)

        depth_blocked = depth_clear.copy()
        depth_blocked[15:30, 20:40] = 1.2
        seg_blocked = seg_clear.copy()
        seg_blocked[15:30, 20:40] = 6
        d2, s2, _ = claims_from_depth_and_segmentation(
            depth=depth_blocked,
            segmentation=seg_blocked,
            risk_roi=roi,
            expected_clear_depth=3.0,
            obstacle_segmentation_idx=6,
            target_segmentation_idx=7,
            target_reference_pixels=roi.pixels,
            observed_step=20,
            valid_until_step=2020,
            capture_root_id="cap-unit-blocked",
            device="cpu",
        )
        self.assertEqual(d2.value, "blocked")
        self.assertEqual(s2.value, "blocked")

    def test_process_genesis_observation_uses_shipped_pipeline(self) -> None:
        scenario = sample_v4_scenario("independent-noise", 50000)
        source = SyntheticEvidenceSource()
        frame = source.raw_frame(
            scenario=scenario,
            viewpoint="unit",
            viewpoint_xy=(-0.4, 1.1),
            predicted_coverage=0.8,
            capture_step=100,
        )
        claims, audit = process_genesis_observation(
            frame,
            scenario,
            observation_index=0,
            repair_action_kind="initial",
            device="cpu",
            ttl_steps=2000,
        )
        self.assertGreaterEqual(len(claims), 2)
        modalities = {c.modality for c in claims}
        self.assertIn("depth_geometry", modalities)
        self.assertIn("simulated_semantic_sensor", modalities)
        self.assertEqual(audit["claims_mode"], CLAIMS_MODE_GENESIS_RGBD)
        self.assertNotEqual(audit["claims_mode"], CLAIMS_MODE_SYNTHETIC)
        self.assertTrue(all(c.is_physical_measurement for c in claims))

    def test_runtime_supports_rgbd_detection(self) -> None:
        class Fake:
            evidence_scenario = object()

            def capture_raw(self, **kwargs):
                return None

        self.assertTrue(runtime_supports_rgbd_claims(Fake()))
        self.assertFalse(runtime_supports_rgbd_claims(object()))

    def test_synthetic_episode_still_marks_synthetic_mode(self) -> None:
        from look_twice_v5 import _V5SyntheticRuntime
        from v5_episode import V5EpisodeConfig, run_v5_episode, smoke_calibration_artifact
        from v5_scenario import sample_v5_scenario

        scenario = sample_v5_scenario("independent-noise", 50000)
        runtime = _V5SyntheticRuntime(scenario)
        try:
            result = run_v5_episode(
                scenario=scenario,
                runtime=runtime,
                calibration=smoke_calibration_artifact("a" * 40),
                config=V5EpisodeConfig(policy="naive"),
                bridge=None,
            )
        finally:
            runtime.close()
        self.assertEqual(result["metrics"]["claims_mode"], CLAIMS_MODE_SYNTHETIC)
        self.assertEqual(
            result["configuration"]["claims_mode"], CLAIMS_MODE_SYNTHETIC
        )
        self.assertEqual(
            result["environment"]["claims_mode"], CLAIMS_MODE_SYNTHETIC
        )


if __name__ == "__main__":
    unittest.main()
