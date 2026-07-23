from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from competition_replay import (  # noqa: E402
    EPISODE_BUNDLE_SCHEMA,
    adapt_v8_episode,
    assert_public_bundle,
)


class CompetitionReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen = ROOT / "release" / "v8-frozen"
        identity_manifest = json.loads(
            (
                cls.frozen
                / "results"
                / "V8_IDENTITY_FREEZE_MANIFEST.json"
            ).read_text()
        )
        frozen = identity_manifest["V8_RUNTIME_FROZEN"]
        cls.identity = {
            "vision_checkpoint": frozen["checkpoint_sha256"],
            "vision_conformal": frozen["vision_conformal_sha256"],
            "go_conformal": frozen["go_fusion_v3_sha256"],
            "purify_binary": identity_manifest["frozen_assets"]["purify_binary"]["file_sha256"],
        }

    def adapt(self, name: str, replay_id: str) -> dict:
        return adapt_v8_episode(
            self.frozen / "episodes" / name,
            replay_id=replay_id,
            frozen_identity=self.identity,
        )

    def test_active_bundle_is_version_neutral_and_complete(self) -> None:
        bundle = self.adapt(
            "active__independent-noise__105400.json", "v8-active-repair-direct"
        )
        self.assertEqual(bundle["schema_version"], EPISODE_BUNDLE_SCHEMA)
        self.assertTrue(bundle["outcome"]["repair_success"])
        self.assertEqual(bundle["outcome"]["route_mode"], "direct")
        self.assertTrue(any(g["effective_admit"] for g in bundle["gate_receipts"]))
        self.assertGreaterEqual(len(bundle["measurement_roots"]), 2)
        self.assertEqual(
            bundle["episode_meta"]["agent_geometry"]["carrier"],
            {
                "collision_width_m": 0.55,
                "source": "scenario.public_context.carrier_width",
            },
        )
        self.assertEqual(
            bundle["episode_meta"]["agent_geometry"]["scout"],
            {
                "collision_width_m": 0.32,
                "source": "scenario.public_context.scout_width",
            },
        )
        assert_public_bundle(bundle)

    def test_passive_bundle_denies_and_detours(self) -> None:
        bundle = self.adapt(
            "passive__independent-noise__105400.json", "v8-passive-safe-detour"
        )
        self.assertFalse(bundle["outcome"]["repair_attempted"])
        self.assertEqual(bundle["outcome"]["route_mode"], "detour")
        self.assertFalse(any(g["effective_admit"] for g in bundle["gate_receipts"]))
        assert_public_bundle(bundle)

    def test_public_bundle_has_no_machine_paths_or_oracle(self) -> None:
        bundle = self.adapt(
            "active__independent-noise__105400.json", "v8-active-repair-direct"
        )
        text = json.dumps(bundle, sort_keys=True)
        for token in ("/workspace/", "/Users/", "root@", "oracle_context"):
            self.assertNotIn(token, text)

    def test_events_are_monotonic(self) -> None:
        bundle = self.adapt(
            "active__independent-noise__105400.json", "v8-active-repair-direct"
        )
        steps = [event["step"] for event in bundle["events"]]
        self.assertEqual(steps, sorted(steps))

    def test_gate_occurrences_are_unique_and_event_statuses_match(self) -> None:
        bundle = self.adapt(
            "active__independent-noise__105400.json", "v8-active-repair-direct"
        )
        gates = bundle["gate_receipts"]
        gate_ids = [gate["gate_id"] for gate in gates]
        self.assertEqual(len(gate_ids), len(set(gate_ids)))
        # The frozen runtime legitimately reused one source receipt hash. The
        # public occurrence identity must remain unique despite that fact.
        source_hashes = [gate["source_receipt_sha256"] for gate in gates]
        self.assertLess(len(set(source_hashes)), len(source_hashes))
        by_id = {gate["gate_id"]: gate for gate in gates}
        for event in bundle["events"]:
            if event["ref_kind"] != "gate_receipt":
                continue
            receipt = by_id[event["ref_id"]]
            expected = "admitted" if receipt["effective_admit"] else "denied"
            self.assertEqual(event["status"], expected)

    def test_active_and_passive_motion_are_public_and_traceable(self) -> None:
        active = self.adapt(
            "active__independent-noise__105400.json", "v8-active-repair-direct"
        )
        passive = self.adapt(
            "passive__independent-noise__105400.json", "v8-passive-safe-detour"
        )
        self.assertTrue(
            any(
                motion["purpose"] == "scout_repair"
                and motion["trajectory_sample"]
                for motion in active["motion_segments"]
            )
        )
        self.assertTrue(
            any(
                motion["purpose"] == "direct_cross"
                for motion in active["motion_segments"]
            )
        )
        self.assertTrue(
            any(
                motion["purpose"] == "safe_detour"
                for motion in passive["motion_segments"]
            )
        )
        for bundle in (active, passive):
            motion_ids = {
                motion["motion_id"] for motion in bundle["motion_segments"]
            }
            for event in bundle["events"]:
                if event["ref_kind"] == "motion_segment":
                    self.assertIn(event["ref_id"], motion_ids)


if __name__ == "__main__":
    unittest.main()
