"""Unit tests for the isolated V8+ contract-progress NBV policy."""

from __future__ import annotations

import copy
import hashlib
import inspect
import math
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from v4_motion import Pose2D
from v6_episode import V6EpisodeConfig, run_v6_episode
from v6_motion import MultiAgentKinematicRuntime
from v6_repair import EvidenceAction
from v6_scenario import CARRIER_ID, SCOUT_ID, sample_v6_scenario
from v7_vision_claims import VisionProposal
from v8_corridor_projection import corridor_mask_from_geometry
from v8_contract_progress_nbv import (
    POLICY_ARTIFACT_ID,
    choose_contract_progress_action,
)


def _receipt(
    corridor: str,
    *,
    actual: int,
    required: int = 2,
    labels=None,
    p_blocked: float = 0.5,
):
    labels = list(labels or ["clear", "blocked"])
    receipt_sha256 = ("a" if corridor == "corridor_a" else "b") * 64
    return {
        "schema_version": "purify.robotics.gate-receipt/v1",
        "receipt_sha256": receipt_sha256,
        "admitted": actual >= required and labels == ["clear"],
        "decision": "denied",
        "p_blocked": p_blocked,
        "scope": {
            "robot_id": "carrier",
            "payload_id": "payload_loaded",
            "region_id": corridor,
        },
        "prediction_set": labels,
        "calibration_applicable": True,
        "clauses": [
            {
                "clause": "prediction_set",
                "required": ["clear"],
                "actual": labels,
                "passed": labels == ["clear"],
            },
            {
                "clause": "evidence_age",
                "required": 80,
                "actual": 0,
                "passed": True,
            },
            {
                "clause": "distinct_measurement_roots",
                "required": required,
                "actual": actual,
                "passed": actual >= required,
            },
            {
                "clause": "modality_skew",
                "required": 40,
                "actual": 0,
                "passed": True,
            },
            {
                "clause": "unresolved_conflicts",
                "required": 0,
                "actual": 0,
                "passed": True,
            },
            {
                "clause": "calibration_applicable",
                "required": True,
                "actual": True,
                "passed": True,
            },
            {
                "clause": "scope_match",
                "required": True,
                "actual": True,
                "passed": True,
            },
        ],
        "_purify_invoked": True,
    }


def _decision(corridor: str, **extra):
    value = {
        "corridor_id": corridor,
        "admitted": False,
        "effective_admit": False,
        "reasons": ["purify_go_denied"],
    }
    value.update(extra)
    return value


def _action(name: str, corridor: str, viewpoint: str, xy, *, coverage=0.75, risk=0.05):
    return EvidenceAction(
        name=name,
        kind="side_view",
        observer="scout",
        corridor_id=corridor,
        viewpoint=viewpoint,
        target_xy=tuple(xy),
        predicted_coverage=coverage,
        predicted_degradation=0.2,
        physical_risk=risk,
        reachable=True,
        travel_cost=0.0,
    )


def _fallback():
    return EvidenceAction(
        name="safe_fallback",
        kind="safe_fallback",
        observer="carrier",
        corridor_id="",
        viewpoint="safe_fallback",
        target_xy=(0.0, 0.0),
        predicted_coverage=0.0,
        predicted_degradation=1.0,
        physical_risk=0.0,
        reachable=True,
        travel_cost=0.0,
    )


class ContractProgressNBVTests(unittest.TestCase):
    def setUp(self) -> None:
        self.public = {
            "corridors": [
                {"id": "corridor_a", "region": [0.0, 2.0, -0.5, 0.0]},
                {"id": "corridor_b", "region": [0.0, 2.0, 0.0, 0.5]},
            ],
            "candidate_viewpoints": [
                {
                    "name": "corridor_a/left_near",
                    "corridor_id": "corridor_a",
                    "xy": [1.0, 0.0],
                    "reachable": True,
                    "predicted_coverage": 0.75,
                    "predicted_degradation": 0.2,
                    "physical_risk": 0.05,
                },
                {
                    "name": "corridor_a/left_far",
                    "corridor_id": "corridor_a",
                    "xy": [4.0, 0.0],
                    "reachable": True,
                    "predicted_coverage": 0.75,
                    "predicted_degradation": 0.2,
                    "physical_risk": 0.05,
                },
                {
                    "name": "corridor_b/left_near",
                    "corridor_id": "corridor_b",
                    "xy": [0.5, 1.0],
                    "reachable": True,
                    "predicted_coverage": 0.75,
                    "predicted_degradation": 0.2,
                    "physical_risk": 0.05,
                },
                {
                    "name": "corridor_b/left_far",
                    "corridor_id": "corridor_b",
                    "xy": [0.5, 2.0],
                    "reachable": True,
                    "predicted_coverage": 0.75,
                    "predicted_degradation": 0.2,
                    "physical_risk": 0.05,
                },
            ],
        }
        self.candidates = [
            _action(
                "scout_a_left_far",
                "corridor_a",
                "corridor_a/left_far",
                (4.0, 0.0),
            ),
            _action(
                "scout_b_left_far",
                "corridor_b",
                "corridor_b/left_far",
                (0.5, 2.0),
            ),
            _action(
                "scout_a_left_near",
                "corridor_a",
                "corridor_a/left_near",
                (1.0, 0.0),
            ),
            _action(
                "scout_b_left_near",
                "corridor_b",
                "corridor_b/left_near",
                (0.5, 1.0),
            ),
            _fallback(),
        ]
        self.decisions = {
            "corridor_a": _decision("corridor_a"),
            "corridor_b": _decision("corridor_b"),
        }

    def choose(self, receipts, **overrides):
        kwargs = {
            "latest_go_receipts": receipts,
            "decisions": self.decisions,
            "confirmed_blocked": set(),
            "side_obs_per_corridor": {"corridor_a": 0, "corridor_b": 0},
            "public": self.public,
            "carrier_xy": (0.0, 0.0),
            "scout_xy": (0.0, 0.0),
            "candidates": self.candidates,
            "observations_taken": 1,
            "max_observations": 6,
        }
        kwargs.update(overrides)
        return choose_contract_progress_action(**kwargs)

    def test_a_owing_one_go_root_beats_b_owing_two(self) -> None:
        selected, ranking = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=1),
                "corridor_b": _receipt("corridor_b", actual=0),
            }
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.corridor_id, "corridor_a")
        self.assertEqual(selected.name, "scout_a_left_near")
        self.assertEqual(ranking[0]["go_measurement_root_debt"], 1)
        self.assertEqual(ranking[0]["repair_step_debt"], 1)
        self.assertEqual(ranking[0]["estimated_contract_completion_debt"], 1)
        self.assertEqual(ranking[0]["policy_artifact_id"], POLICY_ARTIFACT_ID)

    def test_zero_root_debt_repairable_deny_has_one_repair_step_debt(self) -> None:
        selected, ranking = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=2),
                "corridor_b": _receipt("corridor_b", actual=1, labels=["blocked"]),
            }
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.corridor_id, "corridor_a")
        self.assertEqual(ranking[0]["go_measurement_root_debt"], 0)
        self.assertEqual(ranking[0]["repair_step_debt"], 1)
        self.assertEqual(ranking[0]["estimated_contract_completion_debt"], 1)

    def test_hard_blocked_a_fails_closed_and_selects_b(self) -> None:
        selected, _ = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=1, labels=["blocked"]),
                "corridor_b": _receipt("corridor_b", actual=1),
            }
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.corridor_id, "corridor_b")

    def test_equal_debt_prefers_lower_go_p_even_when_farther(self) -> None:
        selected, ranking = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=1, p_blocked=0.02),
                "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.82),
            },
            # B-near is at the current scout pose; A still wins on lower
            # calibrated Go p_blocked because completion debt is tied.
            scout_xy=(0.5, 1.0),
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.corridor_id, "corridor_a")
        self.assertEqual(ranking[0]["go_p_blocked"], 0.02)
        self.assertIn("then_go_p_then_travel", ranking[0]["selection_reason"])

    def test_missing_nan_or_out_of_range_go_p_fails_closed(self) -> None:
        malformed_values = {
            "missing": None,
            "nan": float("nan"),
            "negative": -0.01,
            "above_one": 1.01,
            "string": "0.02",
            "boolean": False,
        }
        for label, bad_value in malformed_values.items():
            with self.subTest(label=label):
                bad_a = _receipt("corridor_a", actual=1, p_blocked=0.02)
                if label == "missing":
                    bad_a.pop("p_blocked")
                else:
                    bad_a["p_blocked"] = bad_value
                selected, ranking = self.choose(
                    {
                        "corridor_a": bad_a,
                        "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
                    }
                )
                self.assertIsNotNone(selected)
                self.assertEqual(selected.corridor_id, "corridor_b")
                a_audits = [
                    item
                    for item in ranking
                    if item["action"]["corridor_id"] == "corridor_a"
                ]
                self.assertTrue(a_audits)
                self.assertTrue(all(not item["eligible"] for item in a_audits))
                self.assertTrue(all(item["go_p_blocked"] is None for item in a_audits))

    def test_every_required_go_clause_must_be_present(self) -> None:
        required_clauses = {
            "prediction_set",
            "evidence_age",
            "distinct_measurement_roots",
            "modality_skew",
            "unresolved_conflicts",
            "calibration_applicable",
            "scope_match",
        }
        for missing_clause in sorted(required_clauses):
            with self.subTest(missing_clause=missing_clause):
                bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
                bad_a["clauses"] = [
                    clause
                    for clause in bad_a["clauses"]
                    if clause["clause"] != missing_clause
                ]
                selected, ranking = self.choose(
                    {
                        "corridor_a": bad_a,
                        "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
                    }
                )
                self.assertEqual(selected.corridor_id, "corridor_b")
                a_reasons = [
                    item["selection_reason"]
                    for item in ranking
                    if item["action"]["corridor_id"] == "corridor_a"
                ]
                self.assertTrue(a_reasons)
                self.assertTrue(
                    all(
                        f"missing_go_clause:{missing_clause}" in reason
                        for reason in a_reasons
                    )
                )

    def test_hard_go_clause_failures_are_not_repairable(self) -> None:
        for failed_clause in (
            "evidence_age",
            "modality_skew",
            "unresolved_conflicts",
            "calibration_applicable",
            "scope_match",
        ):
            with self.subTest(failed_clause=failed_clause):
                bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
                clause = next(
                    item for item in bad_a["clauses"] if item["clause"] == failed_clause
                )
                clause["actual"] = False
                clause["passed"] = False
                selected, ranking = self.choose(
                    {
                        "corridor_a": bad_a,
                        "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
                    }
                )
                self.assertEqual(selected.corridor_id, "corridor_b")
                self.assertTrue(
                    all(
                        f"go_clause_failed:{failed_clause}" in item["selection_reason"]
                        for item in ranking
                        if item["action"]["corridor_id"] == "corridor_a"
                    )
                )

    def test_top_level_calibration_false_fails_closed(self) -> None:
        bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
        bad_a["calibration_applicable"] = False
        selected, ranking = self.choose(
            {
                "corridor_a": bad_a,
                "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
            }
        )
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertTrue(
            all(
                "top_level_calibration_not_applicable" in item["selection_reason"]
                for item in ranking
                if item["action"]["corridor_id"] == "corridor_a"
            )
        )

    def test_empty_prediction_clause_actual_fails_closed(self) -> None:
        bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
        prediction_clause = next(
            item for item in bad_a["clauses"] if item["clause"] == "prediction_set"
        )
        prediction_clause["actual"] = []
        selected, ranking = self.choose(
            {
                "corridor_a": bad_a,
                "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
            }
        )
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertTrue(
            all(
                "go_prediction_clause_mismatch" in item["selection_reason"]
                for item in ranking
                if item["action"]["corridor_id"] == "corridor_a"
            )
        )

    def test_candidate_selector_never_receives_oracle_invalidation_set(self) -> None:
        source = inspect.getsource(run_v6_episode)
        self.assertNotIn("set(confirmed_blocked) | set(invalidated_corridors)", source)

    def test_duplicate_required_clause_fails_closed(self) -> None:
        bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
        scope_clause = next(
            item for item in bad_a["clauses"] if item["clause"] == "scope_match"
        )
        bad_a["clauses"].append(copy.deepcopy(scope_clause))
        selected, ranking = self.choose(
            {
                "corridor_a": bad_a,
                "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
            }
        )
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertTrue(
            all(
                "duplicate_go_clause:scope_match" in item["selection_reason"]
                for item in ranking
                if item["action"]["corridor_id"] == "corridor_a"
            )
        )

    def test_missing_receipt_sha256_fails_closed(self) -> None:
        bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
        del bad_a["receipt_sha256"]
        selected, ranking = self.choose(
            {
                "corridor_a": bad_a,
                "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
            }
        )
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertTrue(
            all(
                "missing_or_malformed_go_receipt_sha256" in item["selection_reason"]
                for item in ranking
                if item["action"]["corridor_id"] == "corridor_a"
            )
        )

    def test_receipt_identity_and_exact_scope_are_required(self) -> None:
        cases = {
            "schema": lambda receipt: receipt.update(
                schema_version="purify.robotics.gate-receipt/v0"
            ),
            "invocation": lambda receipt: receipt.update(_purify_invoked=False),
            "robot": lambda receipt: receipt["scope"].update(robot_id=None),
            "payload": lambda receipt: receipt["scope"].update(payload_id=None),
            "region": lambda receipt: receipt["scope"].update(region_id="corridor_b"),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                bad_a = _receipt("corridor_a", actual=1, p_blocked=0.01)
                mutate(bad_a)
                selected, ranking = self.choose(
                    {
                        "corridor_a": bad_a,
                        "corridor_b": _receipt("corridor_b", actual=1, p_blocked=0.9),
                    }
                )
                self.assertEqual(selected.corridor_id, "corridor_b")
                self.assertTrue(
                    all(
                        item["selection_reason"].startswith("fail_closed:")
                        for item in ranking
                        if item["action"]["corridor_id"] == "corridor_a"
                    )
                )

    def test_go_roots_override_python_multimodality_fake_roots(self) -> None:
        decisions = {
            "corridor_a": _decision("corridor_a", distinct_capture_roots=99),
            "corridor_b": _decision("corridor_b", distinct_capture_roots=0),
        }
        selected, ranking = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=0),
                "corridor_b": _receipt("corridor_b", actual=1),
            },
            decisions=decisions,
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.corridor_id, "corridor_b")
        self.assertEqual(ranking[0]["go_distinct_roots_actual"], 1)

    def test_safe_coverage_candidates_are_ordered_by_shortest_path(self) -> None:
        receipts = {
            "corridor_a": _receipt("corridor_a", actual=1),
            "corridor_b": _receipt("corridor_b", actual=1, labels=["blocked"]),
        }
        selected_a, ranking_a = self.choose(receipts)
        selected_b, ranking_b = self.choose(
            receipts, candidates=list(reversed(self.candidates))
        )
        self.assertEqual(selected_a.name, "scout_a_left_near")
        self.assertEqual(selected_b.name, selected_a.name)
        self.assertEqual(
            [r["action"]["name"] for r in ranking_a],
            [r["action"]["name"] for r in ranking_b],
        )

    def test_two_root_debt_uses_two_view_sequence_lookahead(self) -> None:
        selected, ranking = self.choose(
            {
                "corridor_a": _receipt("corridor_a", actual=0),
                "corridor_b": _receipt("corridor_b", actual=0, labels=["blocked"]),
            }
        )
        self.assertEqual(selected.name, "scout_a_left_near")
        self.assertEqual(
            ranking[0]["projected_sequence"],
            ["scout_a_left_near", "scout_a_left_far"],
        )

    def test_missing_receipt_fails_closed_to_safe_fallback(self) -> None:
        selected, ranking = self.choose({})
        self.assertIsNotNone(selected)
        self.assertEqual(selected.name, "safe_fallback")
        self.assertEqual(
            ranking[0]["selection_reason"],
            "fail_closed_no_repairable_go_contract",
        )

    def test_forbidden_runtime_key_is_rejected_recursively(self) -> None:
        public = copy.deepcopy(self.public)
        public["known_static_map"] = {"nested": {"seed": 102530}}
        with self.assertRaisesRegex(ValueError, "forbidden contract-progress input"):
            self.choose(
                {
                    "corridor_a": _receipt("corridor_a", actual=1),
                    "corridor_b": _receipt("corridor_b", actual=0),
                },
                public=public,
            )

    def test_protocol_forbidden_aliases_are_rejected(self) -> None:
        receipts = {
            "corridor_a": _receipt("corridor_a", actual=1),
            "corridor_b": _receipt("corridor_b", actual=0),
        }
        for alias in (
            "scenario_seed",
            "oracle_state",
            "oracle_context",
            "future_image",
            "true_noise_realization",
            "retry_outcome",
        ):
            with self.subTest(alias=alias):
                public = copy.deepcopy(self.public)
                public["nested"] = {alias: "forbidden"}
                with self.assertRaisesRegex(
                    ValueError, "forbidden contract-progress input"
                ):
                    self.choose(receipts, public=public)

    def test_online_state_corridor_domains_are_strict(self) -> None:
        receipts = {
            "corridor_a": _receipt("corridor_a", actual=1),
            "corridor_b": _receipt("corridor_b", actual=0),
        }
        with self.assertRaisesRegex(ValueError, "unknown contract-progress corridor"):
            self.choose(receipts, confirmed_blocked={"corridor_c"})
        with self.assertRaisesRegex(ValueError, "unknown contract-progress corridor"):
            self.choose(receipts, side_obs_per_corridor={"corridor_c": 0})
        with self.assertRaisesRegex(ValueError, "unknown contract-progress corridor"):
            self.choose({**receipts, "corridor_c": receipts["corridor_a"]})


class _RGBDKinematicRuntime(MultiAgentKinematicRuntime):
    def __init__(self, scenario) -> None:
        public = scenario.public_context
        super().__init__(
            poses={
                CARRIER_ID: Pose2D(*map(float, public["carrier_start_xy"]), 0.0),
                SCOUT_ID: Pose2D(*map(float, public["scout_start_xy"]), 0.0),
            },
            risk_regions=[tuple(c["region"]) for c in public["corridors"]],
        )
        self.evidence_scenario = object()
        self.capture_count = 0
        self.raw_corridor_mask = np.zeros((16, 24), dtype=np.float32)
        self.raw_corridor_mask[3:11, 5:19] = 1.0

    def capture_raw(self, **_kwargs):
        self.capture_count += 1
        return SimpleNamespace(
            rgb=np.zeros((16, 24, 3), dtype=np.uint8),
            depth=np.ones((16, 24), dtype=np.float32),
            corridor_mask=self.raw_corridor_mask.copy(),
        )


class _FakePurifyBridge:
    """In-process Go-receipt stand-in for delegation provenance tests."""

    P_BY_CORRIDOR = {"corridor_a": 0.91, "corridor_b": 0.87}

    def __init__(self, **_kwargs) -> None:
        pass

    def start(self) -> None:
        pass

    def close(self) -> None:
        pass

    def evaluate_action(self, *, contract, current_step, claims=(), **_kwargs):
        corridor = str(contract["scope"]["region_id"])
        p_blocked = self.P_BY_CORRIDOR[corridor]
        measurement_roots = {
            (
                str(claim.get("capture_root_id") or ""),
                str(claim.get("device_root_id") or ""),
            )
            for claim in claims
            if isinstance(claim, dict)
            and claim.get("capture_root_id")
            and claim.get("device_root_id")
        }
        roots_actual = len(measurement_roots)
        prediction_set = ["blocked"] if roots_actual >= 2 else ["clear", "blocked"]
        receipt_sha256 = hashlib.sha256(
            (
                f"{corridor}:{current_step}:{roots_actual}:{p_blocked}:{prediction_set}"
            ).encode("utf-8")
        ).hexdigest()
        return {
            "schema_version": "purify.robotics.gate-receipt/v1",
            "receipt_id": f"gate-test-{corridor}-{current_step}",
            "receipt_sha256": receipt_sha256,
            "contract_id": contract["contract_id"],
            "scope": dict(contract["scope"]),
            "admitted": False,
            "decision": "denied",
            "p_blocked": p_blocked,
            "prediction_set": prediction_set,
            "calibration_applicable": True,
            "clauses": [
                {
                    "clause": "prediction_set",
                    "required": ["clear"],
                    "actual": prediction_set,
                    "passed": False,
                },
                {
                    "clause": "evidence_age",
                    "required": 80,
                    "actual": 0,
                    "passed": True,
                },
                {
                    "clause": "distinct_measurement_roots",
                    "required": 2,
                    "actual": roots_actual,
                    "passed": roots_actual >= 2,
                },
                {
                    "clause": "modality_skew",
                    "required": 40,
                    "actual": 0,
                    "passed": True,
                },
                {
                    "clause": "unresolved_conflicts",
                    "required": 0,
                    "actual": 0,
                    "passed": True,
                },
                {
                    "clause": "calibration_applicable",
                    "required": True,
                    "actual": True,
                    "passed": True,
                },
                {
                    "clause": "scope_match",
                    "required": True,
                    "actual": True,
                    "passed": True,
                },
            ],
            "belief_gaps": [
                {
                    "reason": (
                        "prediction_blocked"
                        if prediction_set == ["blocked"]
                        else "insufficient_roots"
                    )
                }
            ],
            "_purify_invoked": True,
        }


class _MalformedPurifyBridge(_FakePurifyBridge):
    P_BY_CORRIDOR = {"corridor_a": "0.91", "corridor_b": "0.87"}


def _fake_process_genesis(_frame, _scenario, *, observation_index, **_kwargs):
    capture_root = f"physical-capture-{observation_index}"
    claim = SimpleNamespace(
        modality="depth_geometry",
        value="inconclusive" if observation_index == 0 else "clear",
        confidence=0.5 if observation_index == 0 else 0.9,
        observed_step=observation_index,
        valid_until_step=2000,
        capture_root_id=capture_root,
        model_id="fake-rgbd",
        artifact_sha256="e" * 64,
        quality=0.8,
        visibility=0.8,
    )
    return [claim], {"capture_root_id": capture_root, "claims_mode": "test"}


def _proposal(corridor: str, *, shared: bool, value: str = "clear") -> VisionProposal:
    blocked = value == "blocked"
    return VisionProposal(
        value=value,
        confidence=0.95,
        quality=0.9,
        visibility=0.9,
        model_id=f"shared-test-{corridor}",
        input_sha256=("a" if corridor == "corridor_a" else "b") * 64,
        backend="torch_spatial_rgbd",
        features={"shared_rgbd_backbone": 1.0 if shared else 0.0},
        tensor_device="cpu",
        checkpoint_sha256="c" * 64,
        conformal_artifact_sha256="d" * 64,
        preprocessing_version="test-preprocess",
        fallback_used=False,
        p_blocked=0.99 if blocked else 0.01,
        prediction_set=("blocked",) if blocked else ("clear",),
        checkpoint_loaded=True,
        shared_rgbd_backbone=shared,
    )


class ContractProgressEpisodeIntegrationTests(unittest.TestCase):
    def assert_selected_matches_unique_chosen(self, result) -> None:
        for decision in result["repair_decisions"]:
            chosen = [
                item
                for item in decision.get("ranking_head", [])
                if item.get("chosen") is True
            ]
            selected = decision.get("selected")
            if selected is None:
                self.assertEqual(chosen, [])
                self.assertFalse(decision["authorized"])
                continue
            self.assertEqual(len(chosen), 1, decision)
            self.assertEqual(
                selected.get("name"),
                chosen[0].get("action", {}).get("name"),
            )

    def test_candidate_initial_capture_emits_shared_rooted_a_b_claims(self) -> None:
        scenario = sample_v6_scenario("shared-occlusion", 90000)
        runtime = _RGBDKinematicRuntime(scenario)
        with (
            patch(
                "v5_rgbd_claims.process_genesis_observation",
                side_effect=_fake_process_genesis,
            ),
            patch(
                "v7_vision_claims.propose_vision_spatial_rgbd_ab_shared",
                return_value=(
                    _proposal("corridor_a", shared=True),
                    _proposal("corridor_b", shared=True),
                ),
            ) as shared_propose,
            patch(
                "v7_vision_claims.propose_vision",
                return_value=_proposal("corridor_a", shared=False),
            ),
        ):
            result = run_v6_episode(
                scenario=scenario,
                runtime=runtime,
                config=V6EpisodeConfig(
                    policy="purify-active-contract-progress",
                    vision_enabled=True,
                    vision_backend="torch_spatial_rgbd",
                    require_vision_clear_root=True,
                    require_side_view_vision_root=True,
                    use_v7_contract=True,
                ),
            )

        shared_propose.assert_called_once()
        self.assert_selected_matches_unique_chosen(result)
        shared_kwargs = shared_propose.call_args.kwargs
        np.testing.assert_array_equal(
            shared_kwargs["corridor_mask_a"], runtime.raw_corridor_mask
        )
        expected_b_mask = corridor_mask_from_geometry(
            16,
            24,
            corridor_id="corridor_b",
            public=scenario.public_context,
        )
        np.testing.assert_array_equal(shared_kwargs["corridor_mask_b"], expected_b_mask)
        self.assertFalse(
            np.array_equal(
                shared_kwargs["corridor_mask_a"],
                shared_kwargs["corridor_mask_b"],
            )
        )
        self.assertEqual(shared_kwargs["meta_a"]["corridor_id"], "corridor_a")
        self.assertEqual(shared_kwargs["meta_b"]["corridor_id"], "corridor_b")
        self.assertNotIn("pose", shared_kwargs["meta_a"])
        self.assertNotIn("pose", shared_kwargs["meta_b"])
        self.assertNotIn("shared_physical_capture_root_id", shared_kwargs["meta_a"])
        initial_shared = [
            claim
            for claim in result["claims"]
            if claim.get("model_id", "").startswith("shared-test-")
            and claim.get("capture_root_id") == "physical-capture-0"
        ]
        self.assertEqual(
            {claim["scope"]["region_id"] for claim in initial_shared},
            {"corridor_a", "corridor_b"},
        )
        self.assertEqual(
            {claim["capture_root_id"] for claim in initial_shared},
            {"physical-capture-0"},
        )
        self.assertEqual(len({claim["device_root_id"] for claim in initial_shared}), 1)
        shared_audits = [
            audit
            for audit in result["rgbd_observation_audits"]
            if audit.get("shared_initial_ab_capture")
        ]
        self.assertEqual(len(shared_audits), 2)
        self.assertTrue(all(audit["shared_rgbd_backbone"] for audit in shared_audits))
        self.assertTrue(
            all(
                audit["shared_geometry_pose_semantics"] == "legacy_default_empty"
                for audit in shared_audits
            )
        )
        self.assertTrue(
            all(
                audit["shared_initial_a_mask_source"] == "raw_frame.corridor_mask"
                for audit in shared_audits
            )
        )
        self.assertTrue(result["metrics"]["contract_progress_nbv_enabled"])
        self.assertEqual(
            result["metrics"]["contract_progress_nbv_policy_artifact_id"],
            POLICY_ARTIFACT_ID,
        )
        self.assertEqual(result["metrics"]["observation_count"], runtime.capture_count)
        self.assertEqual(
            result["metrics"]["observation_count"],
            len(result["metrics"]["viewpoints_sequence"]),
        )
        vision_audit_count = sum(
            1
            for audit in result["rgbd_observation_audits"]
            if audit.get("kind") == "vision_proposal_v7"
        )
        self.assertEqual(result["metrics"]["vision_proposal_count"], vision_audit_count)
        self.assertGreater(
            result["metrics"]["vision_proposal_count"],
            result["metrics"]["observation_count"],
        )
        self.assertGreater(
            len(result["rgbd_observation_audits"]),
            result["metrics"]["observation_count"],
        )
        self.assertTrue(
            result["metrics"]["contract_progress_shared_initial_ab_capture"]
        )
        self.assertEqual(
            result["metrics"]["contract_progress_shared_initial_ab_proposal_count"],
            2,
        )
        self.assertEqual(
            result["metrics"]["contract_progress_shared_initial_ab_corridors"],
            ["corridor_a", "corridor_b"],
        )
        self.assertTrue(
            result["metrics"]["contract_progress_all_rgbd_geometry_vision_roots_bound"]
        )
        self.assertEqual(
            result["metrics"]["contract_progress_shared_initial_capture_root_ids"],
            ["physical-capture-0"],
        )
        self.assertEqual(
            len(result["metrics"]["contract_progress_shared_initial_device_root_ids"]),
            1,
        )
        geometry_root_devices = {
            (claim["capture_root_id"], claim["device_root_id"])
            for claim in result["claims"]
            if claim.get("modality") != "vision_semantic_v7"
        }
        candidate_vision_claims = [
            claim
            for claim in result["claims"]
            if claim.get("modality") == "vision_semantic_v7"
        ]
        self.assertTrue(candidate_vision_claims)
        genesis_vision_audits = [
            audit
            for audit in result["rgbd_observation_audits"]
            if audit.get("kind") == "vision_proposal_v7"
            and audit.get("vision_source") == "genesis_rgb"
        ]
        for audit in genesis_vision_audits:
            matching_claims = [
                claim
                for claim in candidate_vision_claims
                if claim.get("observer_agent_id") == audit.get("observer_agent_id")
                and claim.get("scope", {}).get("region_id") == audit.get("corridor_id")
                and claim.get("model_id") == audit.get("model_id")
                and claim.get("artifact_sha256") == audit.get("input_sha256")
                and claim.get("capture_root_id")
                == audit.get("physical_capture_root_id")
                and claim.get("device_root_id") == audit.get("physical_device_root_id")
            ]
            self.assertEqual(len(matching_claims), 1, audit)
            vision_claim = matching_claims[0]
            same_scope_geometry = [
                claim
                for claim in result["claims"]
                if claim.get("modality") != "vision_semantic_v7"
                and claim.get("observer_agent_id") == audit.get("observer_agent_id")
                and claim.get("scope") == vision_claim.get("scope")
            ]
            self.assertTrue(
                all(
                    claim.get("capture_root_id") == vision_claim.get("capture_root_id")
                    and claim.get("device_root_id")
                    == vision_claim.get("device_root_id")
                    for claim in same_scope_geometry
                )
            )
        self.assertTrue(
            all(
                (claim["capture_root_id"], claim["device_root_id"])
                in geometry_root_devices
                for claim in candidate_vision_claims
            )
        )
        self.assertTrue(
            all(
                receipt["policy_artifact_id"] == POLICY_ARTIFACT_ID
                for receipt in result["evidence_request_receipts"]
            )
        )
        missing_go_delegations = [
            decision
            for decision in result["repair_decisions"]
            if decision.get("delegated_baseline_fail_closed")
        ]
        self.assertTrue(missing_go_delegations)
        self.assertTrue(
            all(
                decision["contract_progress_selector_invoked"]
                and decision["contract_progress_no_repairable_contract"]
                and decision["contract_progress_selector_selection_reason"]
                == "fail_closed_no_repairable_go_contract"
                for decision in missing_go_delegations
            )
        )
        missing_go_chosen_sides = [
            (decision, item)
            for decision in missing_go_delegations
            for item in decision["ranking_head"]
            if item.get("chosen") and item.get("action", {}).get("kind") == "side_view"
        ]
        self.assertTrue(missing_go_chosen_sides)
        for decision, item in missing_go_chosen_sides:
            self.assertEqual(item["policy_artifact_id"], "heuristic-v6/1")
            self.assertEqual(item["delegating_policy_artifact_id"], POLICY_ARTIFACT_ID)
            self.assertIsNone(item["go_p_blocked"])
            self.assertFalse(item["go_p_blocked_valid"])
            self.assertEqual(
                item["go_p_blocked_source_corridor"],
                item["action"]["corridor_id"],
            )
            self.assertEqual(
                item["go_p_blocked_binding_reason"],
                "missing_latest_go_receipt",
            )
            self.assertTrue(decision["delegated_go_p_fail_closed"])
            self.assertFalse(decision["authorized"])

    def test_frozen_active_policy_never_uses_shared_a_b_helper(self) -> None:
        scenario = sample_v6_scenario("shared-occlusion", 90000)
        runtime = _RGBDKinematicRuntime(scenario)
        with (
            patch(
                "v5_rgbd_claims.process_genesis_observation",
                side_effect=_fake_process_genesis,
            ),
            patch(
                "v7_vision_claims.propose_vision_spatial_rgbd_ab_shared"
            ) as shared_propose,
            patch(
                "v7_vision_claims.propose_vision",
                return_value=_proposal("corridor_a", shared=False),
            ),
        ):
            result = run_v6_episode(
                scenario=scenario,
                runtime=runtime,
                config=V6EpisodeConfig(
                    policy="purify-active",
                    vision_enabled=True,
                    vision_backend="torch_spatial_rgbd",
                    require_vision_clear_root=True,
                    require_side_view_vision_root=True,
                    use_v7_contract=True,
                ),
            )

        shared_propose.assert_not_called()
        self.assertFalse(
            any(key.startswith("contract_progress_") for key in result["metrics"])
        )
        baseline_vision_claims = [
            claim
            for claim in result["claims"]
            if claim.get("model_id") == "shared-test-corridor_a"
        ]
        self.assertTrue(baseline_vision_claims)
        self.assertTrue(
            all(
                claim["capture_root_id"] != "physical-capture-0"
                for claim in baseline_vision_claims
            )
        )
        self.assertTrue(
            all(
                receipt["policy_artifact_id"] == "heuristic-v6/1"
                for receipt in result["evidence_request_receipts"]
            )
        )

    def test_dual_blocked_delegates_to_frozen_probe_then_safe_detour(self) -> None:
        scenario = sample_v6_scenario("shared-occlusion", 90000)
        runtime = _RGBDKinematicRuntime(scenario)
        with tempfile.NamedTemporaryFile() as fake_binary:
            fake_binary.write(b"fake-purify-binary")
            fake_binary.flush()
            with (
                patch("purify_bridge.PurifyBridge", _FakePurifyBridge),
                patch(
                    "v5_rgbd_claims.process_genesis_observation",
                    side_effect=_fake_process_genesis,
                ),
                patch(
                    "v7_vision_claims.propose_vision_spatial_rgbd_ab_shared",
                    return_value=(
                        _proposal("corridor_a", shared=True),
                        _proposal("corridor_b", shared=True),
                    ),
                ),
                patch(
                    "v7_vision_claims.propose_vision",
                    return_value=_proposal("corridor_a", shared=False, value="blocked"),
                ),
            ):
                result = run_v6_episode(
                    scenario=scenario,
                    runtime=runtime,
                    config=V6EpisodeConfig(
                        policy="purify-active-contract-progress",
                        vision_enabled=True,
                        vision_backend="torch_spatial_rgbd",
                        require_vision_clear_root=True,
                        require_side_view_vision_root=True,
                        use_v7_contract=True,
                        use_purify_go_gate=True,
                        purify_binary=fake_binary.name,
                    ),
                )

        self.assert_selected_matches_unique_chosen(result)
        metrics = result["metrics"]
        self.assertEqual(
            metrics["confirmed_blocked_corridors"],
            ["corridor_a", "corridor_b"],
        )
        self.assertGreaterEqual(metrics["contract_progress_nbv_delegation_count"], 1)
        first_decision = result["repair_decisions"][0]
        self.assertTrue(first_decision["contract_progress_selector_invoked"])
        self.assertFalse(first_decision["delegated_baseline_fail_closed"])
        first_chosen = [
            item
            for item in first_decision["ranking_head"]
            if item.get("chosen") is True
        ]
        self.assertEqual(len(first_chosen), 1)
        self.assertEqual(first_chosen[0]["policy_artifact_id"], POLICY_ARTIFACT_ID)
        self.assertNotIn("delegating_policy_artifact_id", first_chosen[0])
        delegated_decisions = [
            decision
            for decision in result["repair_decisions"]
            if decision.get("delegated_baseline_fail_closed")
        ]
        self.assertTrue(delegated_decisions)
        self.assertTrue(
            all(
                decision["contract_progress_selector_invoked"]
                and decision["contract_progress_no_repairable_contract"]
                and decision["contract_progress_selector_selection_reason"]
                == "fail_closed_no_repairable_go_contract"
                and isinstance(
                    decision["contract_progress_corridor_fail_closed_reasons"],
                    dict,
                )
                and set(decision["contract_progress_selector_corridor_audit"])
                == {"corridor_a", "corridor_b"}
                and all(
                    decision["contract_progress_selector_corridor_audit"][cid][
                        "fail_closed_reasons"
                    ]
                    for cid in ("corridor_a", "corridor_b")
                )
                for decision in delegated_decisions
            )
        )
        delegated_chosen = [
            item
            for decision in delegated_decisions
            for item in decision["ranking_head"]
            if item.get("chosen") is True
        ]
        self.assertTrue(delegated_chosen)
        self.assertTrue(
            all(
                item["policy_artifact_id"] == "heuristic-v6/1"
                and item["delegating_policy_artifact_id"] == POLICY_ARTIFACT_ID
                and item["delegated_baseline_fail_closed"] is True
                for item in delegated_chosen
            )
        )
        delegated_chosen_sides = [
            (decision, item)
            for decision in delegated_decisions
            for item in decision["ranking_head"]
            if item.get("chosen") and item.get("action", {}).get("kind") == "side_view"
        ]
        self.assertTrue(delegated_chosen_sides)
        raw_receipts = result["purify_go_receipts"]
        for decision in delegated_decisions:
            for corridor_id, audit in decision[
                "contract_progress_selector_corridor_audit"
            ].items():
                matching_receipt = next(
                    receipt
                    for receipt in raw_receipts
                    if receipt.get("receipt_sha256") == audit["go_receipt_sha256"]
                    and receipt.get("scope", {}).get("region_id") == corridor_id
                    and receipt.get("p_blocked") == audit["go_p_blocked"]
                )
                root_clause = next(
                    clause
                    for clause in matching_receipt["clauses"]
                    if clause["clause"] == "distinct_measurement_roots"
                )
                expected_root_debt = max(
                    root_clause["required"] - root_clause["actual"], 0
                )
                self.assertEqual(audit["roots_actual"], root_clause["actual"])
                self.assertEqual(audit["roots_required"], root_clause["required"])
                self.assertEqual(audit["go_measurement_root_debt"], expected_root_debt)
                self.assertEqual(audit["repair_step_debt"], max(expected_root_debt, 1))
        all_chosen_sides = [
            item
            for decision in result["repair_decisions"]
            for item in decision["ranking_head"]
            if item.get("chosen") is True
            and item.get("action", {}).get("kind") == "side_view"
        ]
        self.assertTrue(all_chosen_sides)
        for item in all_chosen_sides:
            corridor_id = item["action"]["corridor_id"]
            self.assertTrue(
                any(
                    receipt.get("receipt_sha256") == item.get("go_receipt_sha256")
                    and receipt.get("scope", {}).get("region_id") == corridor_id
                    and receipt.get("p_blocked") == item.get("go_p_blocked")
                    for receipt in raw_receipts
                )
            )
        for decision, item in delegated_chosen_sides:
            corridor_id = item["action"]["corridor_id"]
            go_p_blocked = item["go_p_blocked"]
            self.assertFalse(decision["delegated_go_p_fail_closed"])
            self.assertIsInstance(go_p_blocked, float)
            self.assertTrue(math.isfinite(go_p_blocked))
            self.assertGreaterEqual(go_p_blocked, 0.0)
            self.assertLessEqual(go_p_blocked, 1.0)
            self.assertTrue(item["go_p_blocked_valid"])
            self.assertEqual(item["go_p_blocked_source_corridor"], corridor_id)
            self.assertEqual(
                go_p_blocked,
                _FakePurifyBridge.P_BY_CORRIDOR[corridor_id],
            )
            self.assertEqual(
                len(item["go_receipt_sha256"]),
                64,
            )
            self.assertEqual(
                item["go_p_blocked_receipt_sha256"],
                item["go_receipt_sha256"],
            )
            self.assertTrue(item["go_receipt_sha256_valid"])
            self.assertEqual(item["go_measurement_root_debt"], 0)
            self.assertEqual(item["repair_step_debt"], 1)
            self.assertEqual(item["estimated_contract_completion_debt"], 1)
            matching_raw_receipts = [
                receipt
                for receipt in raw_receipts
                if receipt.get("receipt_sha256") == item["go_receipt_sha256"]
                and receipt.get("scope", {}).get("region_id") == corridor_id
                and receipt.get("p_blocked") == go_p_blocked
            ]
            self.assertTrue(matching_raw_receipts)
            self.assertEqual(
                item["go_p_blocked_binding_reason"],
                "latest_same_corridor_go_receipt",
            )
        self.assertFalse(metrics["unsafe_crossing"])
        self.assertEqual(metrics["route_mode"], "detour")
        self.assertFalse(result["outcome"]["safe_fallback"])

    def test_delegated_malformed_go_probability_is_not_authorized(self) -> None:
        scenario = sample_v6_scenario("shared-occlusion", 90000)
        runtime = _RGBDKinematicRuntime(scenario)
        with tempfile.NamedTemporaryFile() as fake_binary:
            fake_binary.write(b"fake-purify-binary")
            fake_binary.flush()
            with (
                patch("purify_bridge.PurifyBridge", _MalformedPurifyBridge),
                patch(
                    "v5_rgbd_claims.process_genesis_observation",
                    side_effect=_fake_process_genesis,
                ),
                patch(
                    "v7_vision_claims.propose_vision_spatial_rgbd_ab_shared",
                    return_value=(
                        _proposal("corridor_a", shared=True, value="blocked"),
                        _proposal("corridor_b", shared=True, value="blocked"),
                    ),
                ),
                patch(
                    "v7_vision_claims.propose_vision",
                    return_value=_proposal("corridor_a", shared=False, value="blocked"),
                ),
            ):
                result = run_v6_episode(
                    scenario=scenario,
                    runtime=runtime,
                    config=V6EpisodeConfig(
                        policy="purify-active-contract-progress",
                        vision_enabled=True,
                        vision_backend="torch_spatial_rgbd",
                        require_vision_clear_root=True,
                        require_side_view_vision_root=True,
                        use_v7_contract=True,
                        use_purify_go_gate=True,
                        purify_binary=fake_binary.name,
                    ),
                )

        self.assert_selected_matches_unique_chosen(result)
        malformed_chosen_sides = [
            (decision, item)
            for decision in result["repair_decisions"]
            if decision.get("delegated_baseline_fail_closed")
            for item in decision["ranking_head"]
            if item.get("chosen") and item.get("action", {}).get("kind") == "side_view"
        ]
        self.assertTrue(malformed_chosen_sides)
        for decision, item in malformed_chosen_sides:
            self.assertEqual(item["policy_artifact_id"], "heuristic-v6/1")
            self.assertEqual(item["delegating_policy_artifact_id"], POLICY_ARTIFACT_ID)
            self.assertIsNone(item["go_p_blocked"])
            self.assertFalse(item["go_p_blocked_valid"])
            self.assertEqual(
                item["go_p_blocked_source_corridor"],
                item["action"]["corridor_id"],
            )
            self.assertEqual(
                item["go_p_blocked_binding_reason"],
                "missing_or_malformed_go_p_blocked",
            )
            self.assertTrue(decision["delegated_go_p_fail_closed"])
            self.assertFalse(decision["authorized"])


if __name__ == "__main__":
    unittest.main()
