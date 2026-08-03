from __future__ import annotations

import math
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_v8_additive_dual_body_dynamics import (  # noqa: E402
    ROBOT_SPECS,
    assess_trial,
    parse_seeds,
    quaternion_tilt_degrees,
    summarize_trials,
    trial_layout,
)
from scripts.verify_v8_additive_dual_body_dynamics import (  # noqa: E402
    EXPECTED_SEEDS,
    SCHEMA_VERSION,
    validate_report,
)


def _motion_result(*, path: float, drift: float = 0.01) -> dict:
    return {
        "reached": True,
        "final_goal_error_m": 0.10,
        "max_abs_wheel_target_rad_s": 2.0,
        "path_length_m": path,
        "stationary_partner_drift_m": drift,
        "max_tilt_deg": 5.0,
        "obstacle_contact_rows": 0,
        "robot_contact_rows": 0,
    }


def _passing_trial(seed: int = 160800) -> dict:
    trial = {
        "seed": seed,
        "script_entity_set_pos_calls_after_build": 0,
        "scout": _motion_result(path=0.9),
        "carrier": _motion_result(path=4.7),
    }
    trial["assessment"] = assess_trial(trial)
    return trial


class AdditiveDualBodyDynamicsTests(unittest.TestCase):
    def test_seed_parser_is_sorted_unique_and_half_open(self) -> None:
        self.assertEqual(
            parse_seeds("160804,160800:160803,160801"),
            (160800, 160801, 160802, 160804),
        )
        with self.assertRaises(ValueError):
            parse_seeds("5:5")

    def test_layout_separates_worlds_and_blocks_opposite_lane(self) -> None:
        even = trial_layout(160800, 0)
        odd = trial_layout(160801, 1)
        self.assertLess(even["clear_lane_y"], 0.0)
        self.assertGreater(even["blocked_lane_y"], 0.0)
        self.assertGreater(odd["clear_lane_y"], 0.0)
        self.assertLess(odd["blocked_lane_y"], 0.0)
        self.assertGreaterEqual(abs(odd["offset"][0] - even["offset"][0]), 12.0)

    def test_quaternion_tilt_ignores_yaw(self) -> None:
        yaw_90 = (math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))
        roll_90 = (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0)
        self.assertAlmostEqual(quaternion_tilt_degrees(yaw_90), 0.0, places=8)
        self.assertAlmostEqual(quaternion_tilt_degrees(roll_90), 90.0, places=8)

    def test_assessment_is_fail_closed_on_contact_or_teleport(self) -> None:
        trial = _passing_trial()
        self.assertTrue(trial["assessment"]["passed"])

        trial["carrier"]["obstacle_contact_rows"] = 1
        trial["script_entity_set_pos_calls_after_build"] = 1
        assessment = assess_trial(trial)
        self.assertFalse(assessment["passed"])
        self.assertFalse(assessment["checks"]["no_blocker_contact"])
        self.assertFalse(assessment["checks"]["no_script_pose_teleport_after_build"])

    def test_summary_rolls_up_both_physical_bodies(self) -> None:
        trials = [_passing_trial(160800), _passing_trial(160801)]
        summary = summarize_trials(trials)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["distinct_non_fixed_robot_entities"], 4)
        self.assertEqual(summary["total_obstacle_contact_rows"], 0)
        self.assertEqual(summary["total_pair_robot_contact_rows"], 0)
        self.assertAlmostEqual(summary["mean_carrier_path_m"], 4.7)

    def test_all_urdf_inertials_have_explicit_origins(self) -> None:
        for spec in ROBOT_SPECS.values():
            root = ET.parse(spec.urdf).getroot()
            inertials = root.findall("./link/inertial")
            self.assertGreater(len(inertials), 0)
            self.assertTrue(all(node.find("origin") is not None for node in inertials))

    def test_report_verifier_enforces_boundary_and_rollups(self) -> None:
        trials = [_passing_trial(seed) for seed in EXPECTED_SEEDS]
        report = {
            "schema_version": SCHEMA_VERSION,
            "boundary": {
                "additive_non_locked": True,
                "formal_result_eligible": False,
                "changes_frozen_v8_endpoint": False,
            },
            "protocol": {
                "seeds": EXPECTED_SEEDS,
                "carrier_and_scout_are_distinct_non_fixed_entities": True,
                "post_build_actuation_api": "control_dofs_velocity only",
            },
            "environment": {
                "backend_requested": "amdgpu",
                "torch_hip": "7.2",
                "gpu": "AMD Radeon Graphics",
            },
            "source": {"git_status_porcelain": ""},
            "summary": summarize_trials(trials),
            "trials": trials,
        }
        self.assertEqual(validate_report(report, verify_source=False), [])

        report["boundary"]["changes_frozen_v8_endpoint"] = True
        errors = validate_report(report, verify_source=False)
        self.assertIn("frozen endpoint changed", errors)


if __name__ == "__main__":
    unittest.main()
