import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from perception import resolve_multimodal_evidence


class PerceptionTests(unittest.TestCase):
    def test_obstacle_support_is_blocked(self) -> None:
        result = resolve_multimodal_evidence(
            support_pixels=100,
            target_pixels=50,
            target_reference_pixels=1000,
            depth_support=1.2,
        )
        self.assertEqual(result.result, "blocked")

    def test_visible_target_is_clear(self) -> None:
        result = resolve_multimodal_evidence(
            support_pixels=0,
            target_pixels=700,
            target_reference_pixels=1000,
            depth_support=2.0,
        )
        self.assertEqual(result.result, "clear")

    def test_low_visibility_is_inconclusive(self) -> None:
        result = resolve_multimodal_evidence(
            support_pixels=0,
            target_pixels=200,
            target_reference_pixels=1000,
            depth_support=2.0,
        )
        self.assertEqual(result.result, "inconclusive")
