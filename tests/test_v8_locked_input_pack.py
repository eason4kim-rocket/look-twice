from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_v8_locked_input_pack import (  # noqa: E402
    PackExpectations,
    canonical_sha256,
    file_sha256,
    verify_input_pack,
)


ARRAY_KEYS = (
    "rgb",
    "depth_noisy",
    "depth_clean",
    "seg_entity",
    "obstacle_mask",
    "corridor_mask",
)


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o444
    archive.addfile(info, io.BytesIO(payload))


def _add_directory(archive: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name.rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.mode = 0o555
    archive.addfile(info)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _build_fixture(
    root: Path,
    *,
    locked_opened: bool = False,
    omit_array: bool = False,
    unsafe_member: bool = False,
) -> tuple[Path, Path, PackExpectations]:
    archive_path = root / "fixture-locked.tar.gz"
    split = "locked_test"
    seed_lo, seed_hi = 10, 11
    samples_per_seed = 2
    label_counts = {"blocked": 2, "clear": 2}
    with tarfile.open(archive_path, "w:gz") as archive:
        _add_directory(archive, split)
        for seed in range(seed_lo, seed_hi + 1):
            seed_dir = f"{split}/seed_{seed}"
            _add_directory(archive, seed_dir)
            complete_rows = []
            for index, label in enumerate(("clear", "blocked")):
                stem = f"corridor_{index}__corridor_{index}__left_near"
                paths = {}
                for key in ARRAY_KEYS:
                    relative = f"{seed_dir}/{stem}__{key}.npy"
                    payload = f"{seed}:{index}:{key}".encode("utf-8")
                    paths[key] = relative
                    paths[f"{key}_sha256"] = hashlib.sha256(payload).hexdigest()
                    if not (
                        omit_array and seed == seed_lo and index == 0 and key == "rgb"
                    ):
                        _add_bytes(archive, relative, payload)
                meta_path = f"{seed_dir}/{stem}__meta.json"
                meta = {
                    "schema_version": "look-twice.v8-spatial-rgbd/v1",
                    "profile": "independent-noise",
                    "split": split,
                    "seed": seed,
                    "viewpoint": f"corridor_{index}/left_near",
                    "corridor_id": f"corridor_{index}",
                    "offline_label": label,
                    "offline_blocked": label == "blocked",
                    "train_eligible": True,
                    "paths": paths,
                    "image_path": paths["rgb"],
                    "git_commit": "1" * 40,
                    "generation_config": {
                        "profile": "independent-noise",
                        "split": split,
                        "seed": seed,
                    },
                    "world_alignment_passed": True,
                }
                _add_bytes(archive, meta_path, _json_bytes(meta))
                complete_rows.append(
                    {
                        "meta": meta_path,
                        "offline_label": label,
                        "corridor_id": meta["corridor_id"],
                        "viewpoint": meta["viewpoint"],
                    }
                )
            complete = {
                "seed": seed,
                "split": split,
                "profile": "independent-noise",
                "n_samples": samples_per_seed,
                "samples": complete_rows,
            }
            _add_bytes(
                archive,
                f"{split}/_COMPLETE__{seed}.json",
                _json_bytes(complete),
            )
        if unsafe_member:
            _add_bytes(archive, "../escape.txt", b"forbidden")

    archive_sha = file_sha256(archive_path)
    sidecar_path = root / "fixture-locked.sidecar.json"
    sidecar = {
        "schema_version": "look-twice.v8-eval-evidence-pack/v1",
        "split": split,
        "n_seeds": seed_hi - seed_lo + 1,
        "source_path": "outputs/v8/fixture/locked_test",
        "archive": archive_path.name,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": archive_sha,
        "compressor": "gzip",
        "created_utc": "20260720T120737Z",
        "locked_opened": locked_opened,
        "locked_analyzed": False,
        "do_not": ["open_for_selection", "use_in_conformal_fit"],
    }
    sidecar_path.write_text(_json_bytes(sidecar).decode("utf-8"), encoding="utf-8")
    expected = PackExpectations(
        archive_name=archive_path.name,
        archive_sha256=archive_sha,
        archive_bytes=archive_path.stat().st_size,
        sidecar_name=sidecar_path.name,
        sidecar_sha256=file_sha256(sidecar_path),
        sidecar_bytes=sidecar_path.stat().st_size,
        created_utc="20260720T120737Z",
        split=split,
        profile="independent-noise",
        seed_lo=seed_lo,
        seed_hi=seed_hi,
        samples_per_seed=samples_per_seed,
        label_counts=label_counts,
    )
    return archive_path, sidecar_path, expected


class LockedInputPackVerifierTests(unittest.TestCase):
    def test_valid_fixture_passes_without_extraction_or_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive, sidecar, expected = _build_fixture(Path(temporary))
            manifest = verify_input_pack(archive, sidecar, expected)
        self.assertTrue(manifest["passed"], manifest["errors"])
        self.assertEqual(manifest["contents"]["seeds"], 2)
        self.assertEqual(manifest["contents"]["metadata_records"], 4)
        self.assertFalse(manifest["path_hygiene"]["archive_extracted"])
        self.assertFalse(manifest["evidence_boundary"]["runs_model_inference"])
        self.assertFalse(
            manifest["evidence_boundary"][
                "contains_original_one_shot_per_sample_predictions"
            ]
        )
        self.assertNotIn(str(Path(temporary)), json.dumps(manifest, sort_keys=True))

    def test_manifest_self_hash_is_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive, sidecar, expected = _build_fixture(Path(temporary))
            manifest = verify_input_pack(archive, sidecar, expected)
        claimed = manifest.pop("manifest_sha256")
        self.assertEqual(claimed, canonical_sha256(manifest))

    def test_refuses_sidecar_that_says_locked_was_opened(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive, sidecar, expected = _build_fixture(
                Path(temporary), locked_opened=True
            )
            manifest = verify_input_pack(archive, sidecar, expected)
        self.assertFalse(manifest["passed"])
        self.assertIn("sidecar_locked_opened_false", manifest["errors"])

    def test_refuses_path_traversal_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive, sidecar, expected = _build_fixture(
                Path(temporary), unsafe_member=True
            )
            manifest = verify_input_pack(archive, sidecar, expected)
        self.assertFalse(manifest["passed"])
        self.assertTrue(
            any(error.startswith("unsafe_member_path:") for error in manifest["errors"])
        )

    def test_refuses_missing_required_array(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive, sidecar, expected = _build_fixture(
                Path(temporary), omit_array=True
            )
            manifest = verify_input_pack(archive, sidecar, expected)
        self.assertFalse(manifest["passed"])
        self.assertTrue(
            any(
                error.startswith("required_array_missing:")
                for error in manifest["errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
