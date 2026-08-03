from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_v8_challenge_feasibility import (  # noqa: E402
    ACTIVE_POLICY,
    EXPECTED_SEEDS,
    SCHEMA_VERSION,
    classify_episode,
)


ARTIFACT = (
    ROOT
    / "release/v8-derived/V8_FROZEN_CHALLENGE_FEASIBILITY_AUDIT.json"
)
EXPECTED_ARCHIVE_SHA256 = (
    "171c9bab73554e1a3654c24872ade011b8423d3aca0df8eca38625a90b0854d2"
)


def _episode(
    *,
    seed: int = 102500,
    corridor_a_blocked: bool = False,
    corridor_b_blocked: bool = True,
    selected_corridor: str | None = "corridor_a",
    route_mode: str = "direct",
    used_detour: bool = False,
    mission_success: bool = True,
    unsafe_crossing: bool = False,
    collision_count: int = 0,
    fallback_used: bool = False,
) -> dict:
    return {
        "schema_version": "look-twice.episode/v7",
        "configuration": {"policy": ACTIVE_POLICY},
        "scenario": {
            "seed": seed,
            "profile": "independent-noise",
            "oracle_context": {
                "corridor_a_blocked_initial": corridor_a_blocked,
                "corridor_b_blocked_initial": corridor_b_blocked,
                "external_event": None,
            },
        },
        "metrics": {
            "policy": ACTIVE_POLICY,
            "selected_corridor": selected_corridor,
            "selected_corridor_oracle_blocked": (
                None
                if selected_corridor is None
                else (
                    corridor_a_blocked
                    if selected_corridor == "corridor_a"
                    else corridor_b_blocked
                )
            ),
            "route_mode": route_mode,
            "used_detour": used_detour,
            "mission_success": mission_success,
            "unsafe_crossing": unsafe_crossing,
            "collision_count": collision_count,
            "fallback_used": fallback_used,
        },
    }


class FeasibilityClassificationTests(unittest.TestCase):
    def test_oracle_clear_direct_selected_clear_is_consistent(self) -> None:
        row = classify_episode(_episode())
        self.assertTrue(row["oracle_clear_direct_and_selected_clear"])
        self.assertTrue(row["offline_feasibility_consistent_route_outcome"])
        self.assertEqual(
            row["classification"], "oracle_clear_direct_selected_clear"
        )

    def test_direct_selection_of_oracle_blocked_corridor_is_inconsistent(self) -> None:
        row = classify_episode(_episode(selected_corridor="corridor_b"))
        self.assertTrue(row["direct_route_primary_observation"])
        self.assertFalse(row["oracle_clear_direct_and_selected_clear"])
        self.assertFalse(row["offline_feasibility_consistent_route_outcome"])

    def test_both_blocked_safe_detour_is_consistent_not_direct(self) -> None:
        row = classify_episode(
            _episode(
                seed=102515,
                corridor_a_blocked=True,
                corridor_b_blocked=True,
                selected_corridor=None,
                route_mode="detour",
                used_detour=True,
            )
        )
        self.assertFalse(row["direct_route_primary_observation"])
        self.assertTrue(row["both_blocked_safe_detour"])
        self.assertTrue(row["offline_feasibility_consistent_route_outcome"])
        self.assertEqual(row["classification"], "both_blocked_safe_detour")

    def test_both_blocked_direct_route_is_inconsistent(self) -> None:
        row = classify_episode(
            _episode(corridor_a_blocked=True, corridor_b_blocked=True)
        )
        self.assertFalse(row["both_blocked_safe_detour"])
        self.assertFalse(row["offline_feasibility_consistent_route_outcome"])

    def test_collision_prevents_feasibility_consistent_outcome(self) -> None:
        row = classify_episode(_episode(collision_count=1))
        self.assertTrue(row["oracle_clear_direct_and_selected_clear"])
        self.assertFalse(row["safe_mission_outcome"])
        self.assertFalse(row["offline_feasibility_consistent_route_outcome"])

    def test_fallback_prevents_feasibility_consistent_outcome(self) -> None:
        row = classify_episode(_episode(fallback_used=True))
        self.assertTrue(row["oracle_clear_direct_and_selected_clear"])
        self.assertFalse(row["safe_mission_outcome"])
        self.assertFalse(row["offline_feasibility_consistent_route_outcome"])


class FeasibilityArtifactContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_artifact_identity_and_scope(self) -> None:
        report = self.report
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["source"]["archive_sha256"], EXPECTED_ARCHIVE_SHA256
        )
        self.assertEqual(report["source"]["archive_read_mode"], "streaming tar r|gz")
        self.assertFalse(report["source"]["archive_extracted"])
        self.assertFalse(report["source"]["model_inference_run"])
        self.assertFalse(report["source"]["episode_rerun"])
        self.assertEqual(report["scope"]["observed_seeds"], list(EXPECTED_SEEDS))

    def test_primary_29_of_30_is_preserved(self) -> None:
        primary = self.report["summary"][
            "preregistered_primary_active_direct_route"
        ]
        self.assertEqual((primary["count"], primary["denominator"]), (29, 30))
        self.assertTrue(primary["unchanged"])
        boundary = self.report["evidence_boundary"]
        self.assertTrue(boundary["does_not_replace_preregistered_primary_endpoint"])
        self.assertTrue(boundary["does_not_relabel_detour_as_direct"])
        self.assertIn("29/30 direct", boundary["preregistered_primary_result_must_remain"])

    def test_secondary_feasibility_contract_is_29_plus_1(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(
            (
                summary["oracle_clear_direct_and_selected_oracle_clear"]["count"],
                summary["oracle_clear_direct_and_selected_oracle_clear"][
                    "denominator"
                ],
            ),
            (29, 29),
        )
        self.assertEqual(
            (
                summary["both_blocked_safe_detour"]["count"],
                summary["both_blocked_safe_detour"]["denominator"],
            ),
            (1, 1),
        )
        self.assertEqual(
            (
                summary["offline_feasibility_consistent_route_outcomes"]["count"],
                summary["offline_feasibility_consistent_route_outcomes"][
                    "denominator"
                ],
            ),
            (30, 30),
        )
        seed_102515 = next(
            row for row in self.report["episodes"] if row["seed"] == 102515
        )
        self.assertEqual(seed_102515["classification"], "both_blocked_safe_detour")

    def test_safety_and_post_hoc_disclosure_are_explicit(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(summary["unsafe_crossing"]["count"], 0)
        self.assertEqual(summary["collision_episodes"]["count"], 0)
        self.assertEqual(summary["collision_events"], 0)
        self.assertEqual(summary["fallback_used"]["count"], 0)
        self.assertEqual(summary["external_event_present"]["count"], 0)
        boundary = self.report["evidence_boundary"]
        self.assertTrue(boundary["post_hoc"])
        self.assertTrue(boundary["descriptive_only"])
        self.assertTrue(boundary["secondary_not_preregistered_endpoint"])
        self.assertTrue(
            boundary["oracle_used_by_this_artifact_only_for_offline_classification"]
        )
        self.assertIn("not a 30/30 direct-route score", boundary["prohibited_interpretation"])


if __name__ == "__main__":
    unittest.main()
