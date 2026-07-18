"""Tests for one-shot locked vision evaluator (NO locked_test access).

Uses a temporary synthetic fixture dataset and frozen-threshold helpers.
Never touches the real locked_test split.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from v7_evaluate_locked_vision import (  # noqa: E402
    EXPECTED_CONFORMAL_SHA,
    EXPECTED_DATASET_SHA,
    EXPECTED_MODEL_SHA,
    apply_frozen_sets,
    evaluate_gates,
    metrics_from_sets,
)
from v7_vision_model import GenesisCorridorHead  # noqa: E402


def _write_fixture(root: Path, split: str, n: int = 12) -> None:
    split_dir = root / split
    split_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for i in range(n):
        label = "blocked" if i % 2 == 0 else "clear"
        arr = rng.random((96, 96, 3), dtype=np.float32)
        if label == "blocked":
            arr *= 0.2
        else:
            arr = 0.4 + 0.4 * arr
        rel = f"{split}/img_{i:03d}.npy"
        np.save(root / rel, arr)
        meta = {
            "offline_label": label,
            "world_alignment_passed": True,
            "train_eligible": True,
            "image_path": rel,
        }
        (split_dir / f"sample_{i:03d}.json").write_text(
            json.dumps(meta) + "\n", encoding="utf-8"
        )
    (root / "dataset_sha256.json").write_text(
        json.dumps({"manifest_all_sha256": EXPECTED_DATASET_SHA}) + "\n",
        encoding="utf-8",
    )


def _save_tiny_ckpt(path: Path) -> str:
    import hashlib

    model = GenesisCorridorHead()
    torch.save(
        {
            "state_dict": model.state_dict(),
            "model": "GenesisCorridorHead",
            "best_val_balanced_accuracy": 0.99,
        },
        path,
    )
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h


def _save_conformal(path: Path) -> str:
    import hashlib

    payload = {
        "schema_version": "look-twice.v7-vision-conformal/v1",
        "thresholds": {
            "coverage_target": 0.95,
            "include_blocked_if_p_blocked_ge": 0.8950414955615998,
            "include_clear_if_p_blocked_le": 0.2635742992162704,
        },
        "runtime_rule": {
            "include_blocked_if_p_blocked_ge": 0.8950414955615998,
            "include_clear_if_p_blocked_le": 0.2635742992162704,
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FrozenSetAndGateTests(unittest.TestCase):
    def test_apply_frozen_sets_boundaries(self) -> None:
        p = np.array([0.0, 0.2635742992162704, 0.5, 0.8950414955615998, 1.0])
        pred = apply_frozen_sets(
            p,
            include_blocked_if_p_blocked_ge=0.8950414955615998,
            include_clear_if_p_blocked_le=0.2635742992162704,
        )
        self.assertEqual(pred[0], "clear")
        self.assertEqual(pred[1], "clear")
        self.assertEqual(pred[2], "inconclusive")
        self.assertEqual(pred[3], "blocked")
        self.assertEqual(pred[4], "blocked")

    def test_metrics_histogram_and_confusion(self) -> None:
        y = np.array([1.0, 1.0, 0.0, 0.0, 1.0])
        pred = ["blocked", "clear", "clear", "inconclusive", "inconclusive"]
        m = metrics_from_sets(y, pred)
        self.assertEqual(m["n"], 5)
        self.assertEqual(m["prediction_histogram"]["blocked"], 1)
        self.assertEqual(m["prediction_histogram"]["clear"], 2)
        self.assertEqual(m["prediction_histogram"]["inconclusive"], 2)
        self.assertIn("tp", m["confusion_decisive"])
        self.assertEqual(m["abstention"]["n"], 2)

    def test_gate_requires_sha_and_no_recompute(self) -> None:
        m = {
            "n": 2283,
            "balanced_accuracy_decisive": 0.99,
            "blocked_recall": 0.95,
            "false_clear_rate": 0.01,
            "coverage": 0.99,
            "frac_clear": 0.4,
            "frac_blocked": 0.4,
        }
        g = evaluate_gates(
            m,
            model_sha=EXPECTED_MODEL_SHA,
            conformal_sha=EXPECTED_CONFORMAL_SHA,
            dataset_sha=EXPECTED_DATASET_SHA,
            thresholds_recomputed=False,
            locked_test_runs=1,
            enforce_n=True,
        )
        self.assertTrue(g["passed"])
        g2 = evaluate_gates(
            m,
            model_sha=EXPECTED_MODEL_SHA,
            conformal_sha=EXPECTED_CONFORMAL_SHA,
            dataset_sha=EXPECTED_DATASET_SHA,
            thresholds_recomputed=True,
            locked_test_runs=1,
            enforce_n=True,
        )
        self.assertFalse(g2["passed"])


class EvaluatorPathTests(unittest.TestCase):
    def test_validation_dry_run_no_locked_open(self) -> None:
        """Exercise CLI on synthetic validation split; never opens locked_test."""
        import v7_evaluate_locked_vision as ev

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data"
            out = root / "out_val"
            _write_fixture(data, "validation", n=16)
            ckpt = root / "best.pt"
            conf = root / "conformal_artifact.json"
            real_model_sha = _save_tiny_ckpt(ckpt)
            real_conf_sha = _save_conformal(conf)

            # Patch expected SHAs to the fixture digests so path runs.
            with mock.patch.object(ev, "EXPECTED_MODEL_SHA", real_model_sha), mock.patch.object(
                ev, "EXPECTED_CONFORMAL_SHA", real_conf_sha
            ):
                rc = ev.main(
                    [
                        "--data-dir",
                        str(data),
                        "--checkpoint",
                        str(ckpt),
                        "--conformal-artifact",
                        str(conf),
                        "--output-dir",
                        str(out),
                        "--device",
                        "cpu",
                        "--split",
                        "validation",
                        "--expected-dataset-sha",
                        EXPECTED_DATASET_SHA,
                        "--expected-model-sha",
                        real_model_sha,
                        "--expected-conformal-sha",
                        real_conf_sha,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertFalse((out / "LOCKED_TEST_OPENED.json").exists())
            self.assertTrue((out / "validation_dry_run_report.json").is_file())
            rep = json.loads((out / "validation_dry_run_report.json").read_text())
            self.assertFalse(rep["is_formal_locked_run"])
            self.assertFalse(rep["thresholds_recomputed"])
            self.assertEqual(rep["locked_test_runs"], 0)
            self.assertEqual(rep["n_samples"], 16)

    def test_refuse_second_open_when_seal_exists(self) -> None:
        import v7_evaluate_locked_vision as ev

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data"
            out = root / "out_locked"
            out.mkdir()
            (out / "LOCKED_TEST_OPENED.json").write_text("{}", encoding="utf-8")
            _write_fixture(data, "locked_test", n=4)
            ckpt = root / "best.pt"
            conf = root / "conformal_artifact.json"
            real_model_sha = _save_tiny_ckpt(ckpt)
            real_conf_sha = _save_conformal(conf)
            rc = ev.main(
                [
                    "--data-dir",
                    str(data),
                    "--checkpoint",
                    str(ckpt),
                    "--conformal-artifact",
                    str(conf),
                    "--output-dir",
                    str(out),
                    "--device",
                    "cpu",
                    "--split",
                    "locked_test",
                    "--expected-dataset-sha",
                    EXPECTED_DATASET_SHA,
                    "--expected-model-sha",
                    real_model_sha,
                    "--expected-conformal-sha",
                    real_conf_sha,
                ]
            )
            self.assertEqual(rc, 3)

    def test_no_force_flag(self) -> None:
        import v7_evaluate_locked_vision as ev

        with self.assertRaises(SystemExit):
            # argparse rejects unknown --force
            ev.main(["--force", "--data-dir", "x", "--checkpoint", "y",
                     "--conformal-artifact", "z", "--output-dir", "o"])


if __name__ == "__main__":
    unittest.main()
