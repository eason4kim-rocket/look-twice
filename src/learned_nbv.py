"""学习型 NBV 的固定特征接口和轻量 PyTorch 推理封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


FEATURE_NAMES = (
    "p_blocked",
    "belief_entropy",
    "expected_visibility",
    "predicted_degradation",
    "travel_cost",
    "revisit_penalty",
    "reachable",
    "observation_count",
)


def feature_vector(*, p_blocked: float, entropy: float, observation_count: int, score) -> list[float]:
    return [
        p_blocked,
        entropy,
        score.expected_visibility,
        score.predicted_degradation,
        score.travel_cost,
        score.revisit_penalty,
        float(score.reachable),
        min(1.0, observation_count / 4.0),
    ]


def build_model(torch):
    return torch.nn.Sequential(
        torch.nn.Linear(len(FEATURE_NAMES), 64),
        torch.nn.ReLU(),
        torch.nn.Linear(64, 32),
        torch.nn.ReLU(),
        torch.nn.Linear(32, 1),
    )


class LearnedNBVScorer:
    def __init__(self, model_path: Path, device: str) -> None:
        import torch

        checkpoint: dict[str, Any] = torch.load(model_path, map_location=device)
        if tuple(checkpoint["feature_names"]) != FEATURE_NAMES:
            raise ValueError("Learned NBV feature schema does not match this code")
        self.torch = torch
        self.device = device
        self.model = build_model(torch).to(device)
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()
        self.mean = torch.tensor(checkpoint["feature_mean"], device=device)
        self.std = torch.tensor(checkpoint["feature_std"], device=device)
        self.model_sha256 = checkpoint["training_data_sha256"]

    def score(self, features: list[float]) -> float:
        tensor = self.torch.tensor(features, device=self.device, dtype=self.torch.float32)
        normalized = (tensor - self.mean) / self.std
        with self.torch.no_grad():
            return float(self.model(normalized).item())
