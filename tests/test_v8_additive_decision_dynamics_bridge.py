from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.run_v8_additive_decision_dynamics_bridge import (
    FORMAL_SEEDS,
    assess_trial,
    engineering_smoke_cases,
    load_formal_cases,
    summarize_trials,
    trial_layout,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "release"
    / "v8-frozen"
    / "results"
    / "challenge_102500_102529"
    / "CHALLENGE_REPORT.json"
)


def motion(path: float, *, scout: bool = False) -> dict[str, object]:
    return {
        "reached": True,
        "final_goal_error_m": 0.10,
        "path_length_m": path,
        "max_tilt_deg": 4.0,
        "stationary_partner_drift_m": 0.01 if scout else 0.0,
        "obstacle_contact_rows": 0,
        "stationary_obstacle_contact_rows": 0,
        "partner_contact_rows": 0,
        "max_abs_wheel_target_rad_s": 2.0,
    }


def trial(seed: int, *, direct: bool = True) -> dict[str, object]:
    row: dict[str, object] = {
        "seed": seed,
        "decision": {
            "full_chain_direct": direct,
            "selected_corridor_clear": direct,
            "both_corridors_blocked": not direct,
        },
        "script_entity_pose_writes_after_build": 0,
        "active_scout": motion(1.0, scout=True),
        "active_carrier": motion(4.8 if direct else 6.2),
        "passive_carrier": motion(6.2),
    }
    row["assessment"] = assess_trial(row)
    return row


class DecisionDynamicsBridgeTests(unittest.TestCase):
    def test_immutable_report_yields_fixed_30_cases(self) -> None:
        cases = load_formal_cases(REPORT)
        self.assertEqual([case.seed for case in cases], list(FORMAL_SEEDS))
        self.assertEqual(sum(case.full_chain_direct for case in cases), 29)
        self.assertEqual(sum(case.both_corridors_blocked for case in cases), 1)
        self.assertTrue(
            all(
                case.selected_corridor_clear for case in cases if case.full_chain_direct
            )
        )

    def test_smoke_covers_a_b_and_dual_blocked(self) -> None:
        cases = engineering_smoke_cases()
        self.assertEqual(
            [case.selected_corridor for case in cases],
            ["corridor_a", "corridor_b", None],
        )
        self.assertTrue(cases[-1].both_corridors_blocked)

    def test_layout_keeps_active_and_passive_replicas_separate(self) -> None:
        layout = trial_layout(engineering_smoke_cases()[0], 0)
        self.assertEqual(layout["passive_offset"][0] - layout["active_offset"][0], 8.0)
        self.assertEqual(len(layout["active_blocker_positions"]), 1)
        self.assertEqual(len(layout["passive_blocker_positions"]), 1)

    def test_dual_blocked_scout_parks_opposite_detour(self) -> None:
        case = engineering_smoke_cases()[-1]
        layout = trial_layout(case, 2)
        scout_y = layout["active_scout_waypoints"][0][1] - layout["active_offset"][1]
        carrier_y = (
            layout["active_carrier_waypoints"][0][1] - layout["active_offset"][1]
        )
        self.assertLess(scout_y * carrier_y, 0.0)

    def test_good_direct_trial_passes(self) -> None:
        row = trial(102500)
        self.assertTrue(row["assessment"]["passed"])

    def test_contact_tamper_fails(self) -> None:
        row = trial(102500)
        row["active_carrier"]["obstacle_contact_rows"] = 1  # type: ignore[index]
        self.assertFalse(assess_trial(row)["passed"])

    def test_formal_summary_requires_all_30_and_15_percent(self) -> None:
        rows = [trial(seed, direct=seed != 102515) for seed in FORMAL_SEEDS]
        summary = summarize_trials(rows, "formal")
        self.assertTrue(summary["all_passed"])
        self.assertEqual(summary["distinct_non_fixed_robot_entities"], 90)
        self.assertGreaterEqual(summary["paired_mean_path_reduction_fraction"], 0.15)

    def test_path_saving_tamper_fails(self) -> None:
        row = trial(102500)
        bad = copy.deepcopy(row)
        bad["active_carrier"]["path_length_m"] = 6.0  # type: ignore[index]
        self.assertFalse(assess_trial(bad)["passed"])


if __name__ == "__main__":
    unittest.main()
