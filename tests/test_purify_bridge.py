import json
import sys
import textwrap
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from purify_bridge import PurifyBridge, PurifyBridgeTimeout, PurifyCoreError


FAKE_CORE = textwrap.dedent(
    r"""
    import json, os, sys, time
    for line in sys.stdin:
        command = json.loads(line)
        payload = command["payload"]
        if payload.get("mode") == "sleep":
            time.sleep(2)
        if payload.get("mode") == "error":
            response = {
                "schema_version": "purify.robotics.response.v1",
                "request_id": command["request_id"],
                "ok": False,
                "result": None,
                "error": {"code": "contract_invalid", "message": "test error"},
            }
        else:
            response = {
                "schema_version": "purify.robotics.response.v1",
                "request_id": command["request_id"],
                "ok": True,
                "result": {"pid": os.getpid(), "op": command["op"], "payload": payload},
                "error": None,
            }
        print(json.dumps(response, sort_keys=True, separators=(",", ":")), flush=True)
    """
)


class PurifyBridgeTests(unittest.TestCase):
    def command(self):
        return (sys.executable, "-u", "-c", FAKE_CORE)

    def test_process_is_persistent_and_request_ids_are_internal(self) -> None:
        with PurifyBridge(self.command()) as bridge:
            first = bridge.request("evaluate_action", {"value": 1})
            second = bridge.request("invalidate_plan", {"value": 2})
            self.assertEqual(first["pid"], second["pid"])
            self.assertEqual(first["op"], "evaluate_action")
            self.assertEqual(second["payload"], {"value": 2})

    def test_core_error_is_deterministic(self) -> None:
        with PurifyBridge(self.command()) as bridge:
            with self.assertRaises(PurifyCoreError) as caught:
                bridge.request("evaluate_action", {"mode": "error"})
        self.assertEqual(caught.exception.request_id, "py-00000001")
        self.assertEqual(caught.exception.error["code"], "contract_invalid")

    def test_timeout_terminates_bridge_fail_closed(self) -> None:
        bridge = PurifyBridge(self.command(), timeout_seconds=0.05)
        try:
            with self.assertRaisesRegex(PurifyBridgeTimeout, "py-00000001"):
                bridge.request("evaluate_action", {"mode": "sleep"})
            with self.assertRaisesRegex(Exception, "exited"):
                bridge.request("evaluate_action", {})
        finally:
            bridge.close()

    def test_high_level_evaluate_action_shape(self) -> None:
        with PurifyBridge(self.command()) as bridge:
            result = bridge.evaluate_action(
                claims=(),
                contract={"contract_id": "cross-region-v1"},
                calibration={"artifact_id": "cal-v1"},
                current_step=10,
                profile="independent-noise",
                noise_intensity=0.2,
                sensor_version="sensor-v4",
            )
        self.assertEqual(result["payload"]["context"]["current_step"], 10)
        self.assertEqual(result["payload"]["claims"], [])


if __name__ == "__main__":
    unittest.main()
