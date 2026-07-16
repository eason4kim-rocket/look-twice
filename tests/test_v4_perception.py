import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_claims import ClaimScope, summarize_lineage
from v4_perception import (
    ClaimProvenance,
    ImageROI,
    analyze_depth_geometry,
    analyze_semantic_proxy,
    build_static_map_claim,
    depth_result_to_claim,
    semantic_result_to_claim,
)


def provenance(capture="capture-001"):
    return ClaimProvenance(
        fact_id="region-01",
        predicate="traversable",
        observed_step=10,
        valid_until_step=70,
        device_root_id="camera-front",
        capture_root_id=capture,
        calibration_id="cal-v1",
        pose_version="pose-v10",
        scope=ClaimScope("amr-01", "empty", "region-01"),
    )


class V4PerceptionTests(unittest.TestCase):
    def test_depth_clear_uses_only_explicit_roi(self) -> None:
        depth = np.full((8, 10), 2.0, dtype=np.float32)
        depth[:, :2] = 0.5  # ROI 外的近物体不得影响证据。
        result = analyze_depth_geometry(
            depth=depth,
            roi=ImageROI(2, 1, 9, 7),
            expected_clear_depth=2.0,
        )
        self.assertEqual(result.result, "clear")
        self.assertEqual(result.near_pixels, 0)

    def test_depth_detects_near_geometry_and_dropout_is_inconclusive(self) -> None:
        blocked = np.full((10, 10), 2.0, dtype=np.float32)
        blocked[3:7, 3:7] = 1.0
        result = analyze_depth_geometry(
            depth=blocked,
            roi=ImageROI(2, 2, 8, 8),
            expected_clear_depth=2.0,
            minimum_near_pixels=8,
        )
        self.assertEqual(result.result, "blocked")

        dropout = np.full((10, 10), np.nan, dtype=np.float32)
        dropout[2:4, 2:4] = 2.0
        result = analyze_depth_geometry(
            depth=dropout,
            roi=ImageROI(1, 1, 9, 9),
            expected_clear_depth=2.0,
        )
        self.assertEqual(result.result, "inconclusive")

    def test_depth_clear_despite_sparse_near_clutter(self) -> None:
        """Median-free ROI must not hard-block on a few near pixels (v4 formal bug)."""
        depth = np.full((20, 20), 5.0, dtype=np.float32)
        depth[8:10, 8:10] = 0.5  # sparse clutter << 28% near fraction
        result = analyze_depth_geometry(
            depth=depth,
            roi=ImageROI(2, 2, 18, 18),
            expected_clear_depth=2.0,
            minimum_near_pixels=4,
        )
        self.assertEqual(result.result, "clear")
        self.assertLess(result.near_fraction, 0.24)

    def test_semantic_is_independent_and_can_conflict_with_depth(self) -> None:
        depth = np.full((20, 20), 2.0, dtype=np.float32)
        segmentation = np.full((20, 20), 2, dtype=np.int64)
        segmentation[5:12, 5:12] = 9
        depth_result = analyze_depth_geometry(
            depth=depth,
            roi=ImageROI(2, 2, 18, 18),
            expected_clear_depth=2.0,
        )
        semantic_result = analyze_semantic_proxy(
            segmentation=segmentation,
            obstacle_segmentation_idx=9,
            target_segmentation_idx=2,
            target_reference_pixels=400,
        )
        self.assertEqual(depth_result.result, "clear")
        self.assertEqual(semantic_result.result, "blocked")

        depth_claim = depth_result_to_claim(depth_result, provenance())
        semantic_claim = semantic_result_to_claim(semantic_result, provenance())
        self.assertEqual(summarize_lineage((depth_claim, semantic_claim)).distinct_measurement_roots, 1)

    def test_static_map_never_counts_as_physical_measurement(self) -> None:
        claim = build_static_map_claim(
            map_record={"region": "region-01", "traversable": True},
            value="clear",
            confidence=0.85,
            provenance=provenance("map-source"),
            map_version="warehouse-v4",
        )
        self.assertEqual(claim.modality, "static_map")
        self.assertEqual(summarize_lineage((claim,)).distinct_measurement_roots, 0)


if __name__ == "__main__":
    unittest.main()
