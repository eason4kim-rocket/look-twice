#!/usr/bin/env python3
"""Fail fast unless the live interpreter matches the recorded V8 ROCm core."""

from __future__ import annotations

import json
import platform
from importlib.metadata import PackageNotFoundError, version


EXPECTED = {
    "genesis": "1.1.2",
    "torch": "2.9.1+gitff65f5b",
    "hip": "7.2.53211-e1a6bc5663",
    "gcn_arch_name": "gfx1100",
}


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main() -> int:
    errors: list[str] = []
    try:
        import torch
    except ImportError as exc:
        raise SystemExit(f"PyTorch import failed: {exc}") from exc

    try:
        import genesis as gs
    except ImportError as exc:
        raise SystemExit(f"Genesis import failed: {exc}") from exc

    torch_version = torch.__version__
    hip_version = getattr(torch.version, "hip", None)
    genesis_version = getattr(gs, "__version__", None) or package_version("genesis-world")
    cuda_available = bool(torch.cuda.is_available())
    device_name = torch.cuda.get_device_name(0) if cuda_available else None
    properties = torch.cuda.get_device_properties(0) if cuda_available else None
    gcn_arch_name = getattr(properties, "gcnArchName", None) if properties else None
    torchvision_version = package_version("torchvision")

    observed = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch_version,
        "torchvision": torchvision_version,
        "hip": hip_version,
        "genesis": genesis_version,
        "cuda_api_available": cuda_available,
        "device_name": device_name,
        "gcn_arch_name": gcn_arch_name,
        "device_total_memory_bytes": int(properties.total_memory) if properties else None,
    }
    for key in ("torch", "hip", "genesis", "gcn_arch_name"):
        if observed[key] != EXPECTED[key]:
            errors.append(
                f"{key}: expected {EXPECTED[key]!r}, observed {observed[key]!r}"
            )
    if not cuda_available:
        errors.append("torch.cuda.is_available() is false for the ROCm device API")

    report = {
        "schema_version": "look-twice.v8-rocm-environment-check/v1",
        "passed": not errors,
        "expected": EXPECTED,
        "observed": observed,
        "errors": errors,
        "note": "PyTorch uses the cuda device namespace on ROCm.",
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
