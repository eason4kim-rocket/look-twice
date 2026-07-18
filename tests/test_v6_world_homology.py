"""V6 oracle → V4/Genesis world homology (no Genesis import required)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v6_genesis_runtime import (
    V6_OBSTACLE_A_XY,
    V6_OBSTACLE_B_XY,
    v6_aligned_v4_scenario,
    v6_oracle_obstacle_specs,
)
from v6_scenario import sample_v6_scenario


class V6WorldHomologyTests(unittest.TestCase):
    def test_a_blocked_maps_to_a_anchor(self) -> None:
        # seed odd → a_blocked True typically
        sc = sample_v6_scenario("independent-noise", 95001)
        self.assertTrue(sc.oracle_context["corridor_a_blocked_initial"])
        self.assertFalse(sc.oracle_context["corridor_b_blocked_initial"])
        specs = v6_oracle_obstacle_specs(sc)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["corridor_id"], "corridor_a")
        self.assertEqual(tuple(specs[0]["xy"]), V6_OBSTACLE_A_XY)
        v4 = v6_aligned_v4_scenario(sc)
        self.assertTrue(v4.initial_blocked)
        self.assertEqual(v4.obstacle_xy, V6_OBSTACLE_A_XY)

    def test_b_blocked_maps_to_b_anchor(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95000)
        self.assertFalse(sc.oracle_context["corridor_a_blocked_initial"])
        # 95000 may have b clear or blocked depending on seed%5; find exclusive B
        found = None
        for seed in range(95000, 95100):
            sc = sample_v6_scenario("independent-noise", seed)
            a = sc.oracle_context["corridor_a_blocked_initial"]
            b = sc.oracle_context["corridor_b_blocked_initial"]
            if b and not a:
                found = sc
                break
        self.assertIsNotNone(found)
        specs = v6_oracle_obstacle_specs(found)
        self.assertEqual(len(specs), 1)
        self.assertEqual(tuple(specs[0]["xy"]), V6_OBSTACLE_B_XY)
        v4 = v6_aligned_v4_scenario(found)
        self.assertEqual(v4.obstacle_xy, V6_OBSTACLE_B_XY)

    def test_v4_random_obstacle_not_kept_when_clear(self) -> None:
        # Both clear is rare; when neither blocked, initial_blocked False.
        for seed in range(90000, 90200):
            sc = sample_v6_scenario("independent-noise", seed)
            a = sc.oracle_context["corridor_a_blocked_initial"]
            b = sc.oracle_context["corridor_b_blocked_initial"]
            if not a and not b:
                v4 = v6_aligned_v4_scenario(sc)
                self.assertFalse(v4.initial_blocked)
                specs = v6_oracle_obstacle_specs(sc)
                self.assertEqual(specs, [])
                return
        self.skipTest("no both-clear seed in range")

    def test_oracle_obstacle_list_matches_flags(self) -> None:
        sc = sample_v6_scenario("independent-noise", 95001)
        lst = sc.oracle_context.get("true_obstacle_xy_list") or []
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0], [1.0, -0.3])


if __name__ == "__main__":
    unittest.main()
