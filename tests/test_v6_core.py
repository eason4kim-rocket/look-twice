"""v6 unit tests: claims, scope, echo, freshness, planner oracle-free, episode path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v4_claims import ClaimScope, canonical_sha256
from v6_claims import (
    SENSOR_VERSION_V6,
    build_robot_claim_v2,
    collapse_echo_claims,
    distinct_capture_roots,
)
from v6_communication import CommunicationQueue
from v6_contracts import (
    CorridorContract,
    authorize_evidence_request,
    evaluate_corridor_contract,
)
from v6_episode import V6EpisodeConfig, run_v6_episode
from v6_repair import (
    FORBIDDEN_PLANNER_KEYS,
    assert_public_planner_context,
    choose_evidence_action,
)
from v6_scenario import sample_v6_scenario


def _claim(
    *,
    value: str = "clear",
    observer: str = "scout",
    actor: str = "carrier",
    corridor: str = "corridor_a",
    capture_root: str = "cap-1",
    comm_root: str | None = None,
    observed: int = 10,
    received: int | None = None,
    artifact_salt: str = "a",
    visibility: float = 0.8,
    quality: float = 0.8,
    predicate: str = "carrier_traversable",
    robot_scope: str | None = None,
) -> object:
    return build_robot_claim_v2(
        fact_id=f"region:{corridor}",
        predicate=predicate,
        value=value,
        confidence=0.8,
        observed_step=observed,
        valid_until_step=observed + 200,
        modality="depth_geometry",
        device_root_id=f"rgbd-{observer}-01",
        capture_root_id=capture_root,
        calibration_id=SENSOR_VERSION_V6,
        pose_version="base-link-v6",
        model_id="test",
        artifact_sha256=canonical_sha256({"s": artifact_salt, "c": capture_root}),
        observer_agent_id=observer,
        intended_actor_id=actor,
        received_step=received if received is not None else observed,
        communication_root_id=comm_root or capture_root,
        quality=quality,
        visibility=visibility,
        scope=ClaimScope(robot_scope or actor, "payload_loaded", corridor),
    )


class V6ClaimContractTests(unittest.TestCase):
    def test_scout_scope_cannot_satisfy_carrier_contract(self) -> None:
        contract = CorridorContract(corridor_id="corridor_a")
        # Two independent roots but scoped to scout.
        claims = [
            _claim(
                capture_root="c1",
                robot_scope="scout",
                actor="scout",
                observer="scout",
                artifact_salt="1",
            ),
            _claim(
                capture_root="c2",
                robot_scope="scout",
                actor="scout",
                observer="scout",
                artifact_salt="2",
            ),
        ]
        dec = evaluate_corridor_contract(claims, contract, current_step=20)
        self.assertFalse(dec.admitted)
        self.assertIn("scope_mismatch", dec.reasons)

    def test_echo_multiplicity_does_not_inflate_roots(self) -> None:
        base = _claim(capture_root="same-cap", comm_root="same-comm", artifact_salt="x")
        # 100 echoes same roots
        echoes = [
            _claim(
                capture_root="same-cap",
                comm_root="same-comm",
                artifact_salt="x",
                observed=10,
                received=10 + i,
            )
            for i in range(100)
        ]
        collapsed = collapse_echo_claims([base, *echoes])
        self.assertEqual(len(distinct_capture_roots(collapsed)), 1)
        contract = CorridorContract(corridor_id="corridor_a")
        # Need second independent root for admit — echoes alone fail.
        dec = evaluate_corridor_contract(collapsed, contract, current_step=50)
        self.assertFalse(dec.admitted)
        self.assertLess(dec.distinct_capture_roots, 2)

    def test_freshness_uses_observed_not_received(self) -> None:
        # Observed long ago; received "now" must still be stale if valid_until passed.
        claim = _claim(
            capture_root="c1",
            observed=0,
            received=500,
            artifact_salt="old",
        )
        # Rebuild with short validity
        claim = build_robot_claim_v2(
            fact_id=claim.fact_id,
            predicate=claim.predicate,
            value="clear",
            confidence=0.8,
            observed_step=0,
            valid_until_step=50,
            modality="depth_geometry",
            device_root_id=claim.device_root_id,
            capture_root_id="c1",
            calibration_id=SENSOR_VERSION_V6,
            pose_version="base-link-v6",
            model_id="test",
            artifact_sha256=canonical_sha256({"old": True}),
            observer_agent_id="scout",
            intended_actor_id="carrier",
            received_step=500,
            communication_root_id="c1",
            scope=ClaimScope("carrier", "payload_loaded", "corridor_a"),
        )
        self.assertFalse(claim.is_fresh_at(100))
        contract = CorridorContract(corridor_id="corridor_a")
        dec = evaluate_corridor_contract([claim], contract, current_step=100)
        self.assertFalse(dec.admitted)
        self.assertTrue(
            any(r in dec.reasons for r in ("stale", "evidence_age", "insufficient_roots"))
        )

    def test_two_independent_clear_roots_can_admit(self) -> None:
        claims = [
            _claim(capture_root="r1", artifact_salt="1", visibility=0.9),
            _claim(capture_root="r2", artifact_salt="2", visibility=0.9),
        ]
        contract = CorridorContract(corridor_id="corridor_a")
        dec = evaluate_corridor_contract(claims, contract, current_step=20)
        self.assertTrue(dec.admitted)
        self.assertEqual(dec.distinct_capture_roots, 2)


class V6CommAndPlannerTests(unittest.TestCase):
    def test_echo_fanout_preserves_communication_root(self) -> None:
        q = CommunicationQueue(delay_steps=0, echo_fanout=100, drop_rate=0.0, seed=1)
        claim = _claim(capture_root="capZ", comm_root="commZ", artifact_salt="z")
        n = q.publish(claim, current_step=0)
        self.assertEqual(n, 100)
        delivered = q.poll(0)
        self.assertEqual(len(delivered), 100)
        roots = {c.capture_root_id for c in delivered}
        comm = {c.communication_root_id for c in delivered}
        self.assertEqual(roots, {"capZ"})
        self.assertEqual(comm, {"commZ"})
        collapsed = collapse_echo_claims(delivered)
        self.assertEqual(len(distinct_capture_roots(collapsed)), 1)

    def test_planner_rejects_oracle_fields(self) -> None:
        with self.assertRaises(ValueError):
            assert_public_planner_context({"oracle": {"blocked": True}})
        with self.assertRaises(ValueError):
            assert_public_planner_context(
                {"known_static_map": {"truth": 1, "map_version": "x"}}
            )

    def test_candidates_from_fixed_action_set(self) -> None:
        sc = sample_v6_scenario("independent-noise", 90000)
        selected, ranking = choose_evidence_action(
            sc.public_context,
            gap_reasons=["insufficient_roots", "low_coverage"],
            carrier_xy=(-2.0, 0.0),
            scout_xy=(-1.6, 1.2),
            visited=set(),
            observations_taken=0,
            max_observations=6,
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        from v6_contracts import ALLOWED_EVIDENCE_ACTIONS

        self.assertIn(selected.name, ALLOWED_EVIDENCE_ACTIONS)
        for item in ranking:
            self.assertIn(item["action"]["name"], ALLOWED_EVIDENCE_ACTIONS)

    def test_authorize_rejects_unknown_action(self) -> None:
        receipt = authorize_evidence_request(
            belief_gaps=["insufficient_roots"],
            selected_action={
                "name": "hack_the_gate",
                "kind": "side_view",
                "observer": "scout",
                "physical_risk": 0.01,
                "reachable": True,
            },
            current_step=10,
            observations_taken=0,
            replans_taken=0,
        )
        self.assertFalse(receipt.authorized)
        self.assertIn("unknown_action", receipt.reasons)

    def test_safe_fallback_not_confirmed_blocked(self) -> None:
        sc = sample_v6_scenario("shared-occlusion", 90001)
        result = run_v6_episode(
            scenario=sc,
            config=V6EpisodeConfig(policy="purify-passive"),
        )
        label = result["outcome"]["label"]
        self.assertNotEqual(label, "confirmed_blocked")
        if result["metrics"]["used_detour"]:
            self.assertIn(
                result["metrics"]["route_mode"],
                ("detour", "none", "direct"),
            )


class V6EpisodePathTests(unittest.TestCase):
    def test_mission_fields_without_pick_proxy(self) -> None:
        sc = sample_v6_scenario("independent-noise", 90000)
        result = run_v6_episode(
            scenario=sc, config=V6EpisodeConfig(policy="purify-active")
        )
        m = result["metrics"]
        for key in (
            "mission_success",
            "carrier_reached_goal",
            "payload_delivered",
            "unsafe_crossing",
            "collision_count",
            "elapsed_steps",
            "within_deadline",
        ):
            self.assertIn(key, m)
        self.assertNotIn("pick_success", m)
        self.assertEqual(
            m["mission_success"],
            bool(
                m["carrier_reached_goal"]
                and m["payload_delivered"]
                and not m["unsafe_crossing"]
                and m["collision_count"] == 0
                and m["within_deadline"]
            ),
        )

    def test_active_repair_path_records_request(self) -> None:
        sc = sample_v6_scenario("shared-occlusion", 90000)
        result = run_v6_episode(
            scenario=sc, config=V6EpisodeConfig(policy="purify-active")
        )
        m = result["metrics"]
        self.assertTrue(m["repair_attempted"])
        self.assertGreaterEqual(len(result["evidence_request_receipts"]), 1)
        # Gated policy must not be unsafe on this synthetic path.
        self.assertFalse(m["unsafe_crossing"])

    def test_naive_can_be_unsafe_on_blocked(self) -> None:
        # Odd seeds bias corridor_a blocked.
        sc = sample_v6_scenario("independent-noise", 90001)
        result = run_v6_episode(
            scenario=sc, config=V6EpisodeConfig(policy="naive")
        )
        m = result["metrics"]
        self.assertTrue(m["unsafe_crossing"] or not m["mission_success"])

    def test_passive_never_crosses_without_admit_or_detour(self) -> None:
        sc = sample_v6_scenario("shared-occlusion", 90002)
        result = run_v6_episode(
            scenario=sc, config=V6EpisodeConfig(policy="purify-passive")
        )
        m = result["metrics"]
        self.assertFalse(m["unsafe_crossing"])
        if m["route_mode"] == "direct":
            # Direct only if some gate admitted.
            admits = [g for g in result["gate_receipts"] if g.get("admitted")]
            self.assertGreaterEqual(len(admits), 1)

    def test_scenario_deterministic(self) -> None:
        a = sample_v6_scenario("comm-fault", 90123).to_dict()
        b = sample_v6_scenario("comm-fault", 90123).to_dict()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
