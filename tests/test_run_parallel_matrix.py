from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_parallel_matrix import Job, _build_command


class ParallelMatrixCommandTests(unittest.TestCase):
    def test_v5_learned_command_uses_formal_artifacts(self) -> None:
        command = _build_command(
            Job("v5", "purify-active", "independent-noise", 50000),
            python="python",
            output=Path("out.json"),
            calibration=Path("outer.json"),
            purify_bin=Path("purify"),
            motion="kinematic",
            device="cuda:0",
            log=Path("run.log"),
            learned_rgbd_model=Path("model.pt"),
            learned_rgbd_calibration=Path("learned.json"),
        )
        self.assertIn("--calibration", command)
        self.assertNotIn("--allow-smoke-calibration", command)
        self.assertIn("--learned-rgbd-model", command)
        self.assertIn("--learned-rgbd-calibration", command)

    def test_v5_without_formal_artifact_keeps_smoke_compatibility(self) -> None:
        command = _build_command(
            Job("v5", "naive", "independent-noise", 50000),
            python="python",
            output=Path("out.json"),
            calibration=None,
            purify_bin=Path("purify"),
            motion="kinematic",
            device="cuda:0",
            log=Path("run.log"),
        )
        self.assertIn("--allow-smoke-calibration", command)


if __name__ == "__main__":
    unittest.main()
