import hashlib
import inspect
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v4_claims import build_robot_claim
from v4_conformal import CalibrationArtifact, SeedRange
from v4_policies import (
    POLICIES,
    POLICY_CONFORMAL_ONLY,
    POLICY_DESCRIPTORS,
    POLICY_LINEAGE_ONLY,
    POLICY_NAIVE_MAJORITY,
    POLICY_PURIFY_ACTIVE,
    POLICY_PURIFY_PASSIVE,
    POLICY_V3_LOGODDS,
    PolicyDecision,
    decision_from_gate_receipt,
    evaluate_policy,
)


def artifact_hash(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()


def calibration() -> CalibrationArtifact:
    return CalibrationArtifact(
        artifact_id="cal-v4",
        alpha=0.05,
        class_quantiles={"clear": 0.10, "blocked": 0.10},
        applicable_profiles=("independent-noise",),
        min_noise_intensity=0.0,
        max_noise_intensity=0.75,
        sensor_versions=("sensor-v4",),
        git_commit="test-commit",
        dataset_sha256=artifact_hash("calibration-dataset"),
        seed_ranges=(SeedRange(30000, 30049),),
    )


def claim(
    value="clear",
    confidence=0.9,
    *,
    artifact="capture-a",
    root="root-a",
    device="camera-front",
    modality="depth_geometry",
    model="depth-v4",
    observed_step=10,
    valid_until_step=70,
    calibration_id="sensor-v4",
):
    return build_robot_claim(
        fact_id="risk-region-01",
        predicate="traversable",
        value=value,
        confidence=confidence,
        observed_step=observed_step,
        valid_until_step=valid_until_step,
        modality=modality,
        device_root_id=device,
        capture_root_id=root,
        calibration_id=calibration_id,
        pose_version="pose-v4",
        model_id=model,
        artifact_sha256=artifact_hash(artifact),
    )


class V4PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calibration = calibration()

    def decide(self, policy, claims, step=20) -> PolicyDecision:
        return evaluate_policy(
            policy,
            claims=claims,
            calibration=self.calibration,
            current_step=step,
        )

    def test_frozen_policy_matrix_and_purify_descriptors(self) -> None:
        self.assertEqual(
            POLICIES,
            (
                "naive-majority",
                "v3-logodds",
                "conformal-only",
                "lineage-only",
                "purify-passive",
                "purify-active",
            ),
        )
        passive = POLICY_DESCRIPTORS[POLICY_PURIFY_PASSIVE]
        active = POLICY_DESCRIPTORS[POLICY_PURIFY_ACTIVE]
        self.assertTrue(passive.requires_go_gate)
        self.assertTrue(active.requires_go_gate)
        self.assertFalse(passive.allows_repair)
        self.assertTrue(active.allows_repair)

    def test_python_evaluation_accepts_only_claims_artifact_and_current_step(self) -> None:
        parameters = set(inspect.signature(evaluate_policy).parameters)
        self.assertEqual(
            parameters, {"policy", "claims", "calibration", "current_step"}
        )
        with self.assertRaises(TypeError):
            self.decide(POLICY_NAIVE_MAJORITY, [{"oracle": "clear"}])

    def test_evidence_echo_fools_naive_but_not_lineage_policy(self) -> None:
        clear_echoes = [
            claim(
                "clear",
                0.70,
                artifact="one-physical-capture",
                root="root-clear",
                model=f"echo-{index}",
            )
            for index in range(4)
        ]
        strong_blocked = claim(
            "blocked",
            0.98,
            artifact="independent-blocked",
            root="root-blocked",
            model="semantic-v4",
            modality="simulated_semantic_sensor",
        )
        claims = (*clear_echoes, strong_blocked)
        naive = self.decide(POLICY_NAIVE_MAJORITY, claims)
        lineage = self.decide(POLICY_LINEAGE_ONLY, claims)

        self.assertEqual(naive.action, "cross_region")
        self.assertEqual(naive.diagnostics["votes"], {"clear": 4, "blocked": 1})
        self.assertEqual(lineage.resolved_value, "blocked")
        self.assertEqual(lineage.action, "safe_fallback")
        self.assertEqual(lineage.diagnostics["distinct_measurement_roots"], 2)
        self.assertEqual(
            len(lineage.diagnostics["artifact_duplicate_claim_ids"]), 3
        )

    def test_v3_logodds_accumulates_echoes_without_lineage_collapse(self) -> None:
        one = claim("clear", 0.75, model="one")
        echoed = [
            claim("clear", 0.75, model=f"echo-{index}") for index in range(3)
        ]
        single = self.decide(POLICY_V3_LOGODDS, (one,))
        repeated = self.decide(POLICY_V3_LOGODDS, (*echoed,))
        self.assertGreater(
            repeated.diagnostics["p_clear"], single.diagnostics["p_clear"]
        )
        self.assertFalse(repeated.diagnostics["lineage_collapsed"])

    def test_conformal_only_does_not_collapse_repeated_artifact(self) -> None:
        blocked = claim(
            "blocked",
            0.98,
            artifact="blocked",
            root="root-blocked",
            modality="simulated_semantic_sensor",
        )
        echoes = tuple(
            claim(
                "clear",
                0.70,
                artifact="shared-clear-artifact",
                root="root-clear",
                model=f"echo-{index}",
            )
            for index in range(8)
        )
        decision = self.decide(POLICY_CONFORMAL_ONLY, (*echoes, blocked))
        self.assertEqual(decision.action, "cross_region")
        self.assertEqual(decision.prediction_set, ("clear",))
        self.assertFalse(decision.diagnostics["lineage_collapsed"])

    def test_balanced_modal_conflict_is_unresolved_and_never_crosses(self) -> None:
        clear = claim("clear", 0.90, artifact="clear", root="root-clear")
        blocked = claim(
            "blocked",
            0.90,
            artifact="blocked",
            root="root-blocked",
            modality="simulated_semantic_sensor",
        )
        for policy in (
            POLICY_NAIVE_MAJORITY,
            POLICY_V3_LOGODDS,
            POLICY_CONFORMAL_ONLY,
            POLICY_LINEAGE_ONLY,
        ):
            with self.subTest(policy=policy):
                decision = self.decide(policy, (clear, blocked))
                self.assertNotEqual(decision.action, "cross_region")
                self.assertEqual(decision.resolved_value, "unresolved")

    def test_stale_evidence_fails_closed_for_every_python_baseline(self) -> None:
        stale_clear = claim("clear", 0.99, valid_until_step=15)
        for policy in (
            POLICY_NAIVE_MAJORITY,
            POLICY_V3_LOGODDS,
            POLICY_CONFORMAL_ONLY,
            POLICY_LINEAGE_ONLY,
        ):
            with self.subTest(policy=policy):
                decision = self.decide(policy, (stale_clear,), step=20)
                self.assertEqual(decision.action, "safe_fallback")
                self.assertEqual(decision.reason, "stale_evidence")

    def test_unrecognised_sensor_version_is_ood_and_fails_closed(self) -> None:
        ood_clear = claim("clear", 0.999, calibration_id="sensor-v5-ood")
        for policy in (
            POLICY_NAIVE_MAJORITY,
            POLICY_V3_LOGODDS,
            POLICY_CONFORMAL_ONLY,
            POLICY_LINEAGE_ONLY,
        ):
            with self.subTest(policy=policy):
                decision = self.decide(policy, (ood_clear,))
                self.assertEqual(decision.action, "safe_fallback")
                self.assertEqual(decision.reason, "calibration_not_applicable")

    def test_static_map_is_prior_but_never_a_physical_root(self) -> None:
        static_clear = claim(
            "clear",
            0.999,
            modality="static_map",
            root="map-v4",
            device="map-server",
            calibration_id="map-v4",
        )
        for policy in (
            POLICY_NAIVE_MAJORITY,
            POLICY_V3_LOGODDS,
            POLICY_CONFORMAL_ONLY,
            POLICY_LINEAGE_ONLY,
        ):
            with self.subTest(policy=policy):
                self.assertNotEqual(
                    self.decide(policy, (static_clear,)).action, "cross_region"
                )

    def test_purify_policy_without_go_receipt_fails_closed(self) -> None:
        for policy in (POLICY_PURIFY_PASSIVE, POLICY_PURIFY_ACTIVE):
            decision = self.decide(policy, (claim(),))
            self.assertEqual(decision.action, "safe_fallback")
            self.assertEqual(decision.reason, "go_gate_receipt_required")

    def test_go_denial_allows_only_active_policy_to_observe(self) -> None:
        receipt = self.gate_receipt(admitted=False)
        passive = decision_from_gate_receipt(
            POLICY_PURIFY_PASSIVE, gate_receipt=receipt, current_step=20
        )
        active = decision_from_gate_receipt(
            POLICY_PURIFY_ACTIVE, gate_receipt=receipt, current_step=20
        )
        self.assertEqual(passive.action, "safe_fallback")
        self.assertEqual(active.action, "observe")

    def test_only_fresh_applicable_clear_go_receipt_can_cross(self) -> None:
        admitted = decision_from_gate_receipt(
            POLICY_PURIFY_ACTIVE,
            gate_receipt=self.gate_receipt(admitted=True, prediction_set=["clear"]),
            current_step=20,
        )
        self.assertEqual(admitted.action, "cross_region")

        stale = decision_from_gate_receipt(
            POLICY_PURIFY_ACTIVE,
            gate_receipt=self.gate_receipt(
                admitted=True, prediction_set=["clear"], valid_until_step=19
            ),
            current_step=20,
        )
        self.assertEqual(stale.action, "safe_fallback")
        self.assertEqual(stale.reason, "gate_receipt_stale")

        ood = decision_from_gate_receipt(
            POLICY_PURIFY_ACTIVE,
            gate_receipt=self.gate_receipt(
                admitted=False, calibration_applicable=False
            ),
            current_step=20,
        )
        self.assertNotEqual(ood.action, "cross_region")
        self.assertEqual(ood.reason, "calibration_not_applicable")

    def test_gate_receipt_with_oracle_data_is_rejected(self) -> None:
        receipt = self.gate_receipt(admitted=False)
        receipt["oracle"] = {"truth": "clear"}
        with self.assertRaises(ValueError):
            decision_from_gate_receipt(
                POLICY_PURIFY_ACTIVE, gate_receipt=receipt, current_step=20
            )

    @staticmethod
    def gate_receipt(
        *,
        admitted=False,
        prediction_set=None,
        valid_until_step=70,
        calibration_applicable=True,
    ):
        return {
            "receipt_id": "gate-test",
            "receipt_sha256": "0" * 64,
            "admitted": admitted,
            "prediction_set": prediction_set or ["clear", "blocked"],
            "calibration_applicable": calibration_applicable,
            "valid_until_step": valid_until_step,
            "belief_gaps": [{"reason": "modality_conflict"}],
            "measurement_root_ids": ["root-a"],
        }


if __name__ == "__main__":
    unittest.main()
