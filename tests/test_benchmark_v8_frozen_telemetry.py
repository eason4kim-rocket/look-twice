import json
import unittest

from scripts.benchmark_v8_frozen_telemetry import (
    confirms_no_kfd_processes,
    parse_rocm_smi_json,
    summarize_samples,
)


class FrozenTelemetryHelpersTest(unittest.TestCase):
    def test_parser_allow_lists_metrics_and_drops_identity(self) -> None:
        raw = json.dumps(
            {
                "card0": {
                    "Unique ID": "secret-device-id",
                    "GPU use (%)": "97",
                    "GPU Memory Allocated (VRAM%)": "4",
                    "GPU Memory Read/Write Activity (%)": "12",
                    "Average Graphics Package Power (W)": "123.5",
                    "Temperature (Sensor edge) (C)": "41.0",
                    "Temperature (Sensor junction) (C)": "52.0",
                    "Temperature (Sensor memory) (C)": "44.0",
                }
            }
        )
        row = parse_rocm_smi_json(raw)
        self.assertEqual(row["device"], "card0")
        self.assertEqual(row["gpu_use_percent"], 97.0)
        self.assertEqual(row["graphics_package_power_w"], 123.5)
        self.assertNotIn("Unique ID", row)
        self.assertNotIn("secret-device-id", json.dumps(row))

    def test_summary_ignores_unavailable_values(self) -> None:
        summary = summarize_samples(
            [
                {"gpu_use_percent": 50.0},
                {"gpu_use_percent": 100.0},
                {"gpu_use_percent": None},
            ]
        )
        self.assertEqual(summary["sample_count"], 3)
        self.assertEqual(summary["gpu_use_percent"]["mean"], 75.0)
        self.assertEqual(summary["gpu_use_percent"]["samples"], 2)

    def test_clean_process_preflight_requires_explicit_rocm_smi_message(self) -> None:
        self.assertTrue(confirms_no_kfd_processes("No KFD PIDs currently running"))
        self.assertFalse(confirms_no_kfd_processes("PID 1234 is running"))


if __name__ == "__main__":
    unittest.main()
