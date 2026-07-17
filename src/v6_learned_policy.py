"""Lightweight pure-PyTorch cross-agent evidence repair ranker.

Does not authorize corridor cross — only ranks observation candidates.
Oracle fields never enter online scoring features.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

from v6_contracts import ALLOWED_EVIDENCE_ACTIONS
from v6_repair import EvidenceAction, build_candidate_actions, score_action


MODEL_VERSION = "look-twice-v6-learned-repair/1"


def _gap_onehot(reasons: Sequence[str]) -> list[float]:
    keys = [
        "insufficient_roots",
        "shared_root",
        "low_coverage",
        "evidence_conflict",
        "stale",
        "scope_mismatch",
        "prediction_not_clear",
        "other",
    ]
    s = set(reasons)
    vec = [1.0 if k in s else 0.0 for k in keys[:-1]]
    vec.append(1.0 if (s - set(keys[:-1])) else 0.0)
    return vec


def action_feature_vector(
    action: EvidenceAction | Mapping[str, Any],
    *,
    gap_reasons: Sequence[str],
    observations_taken: int,
    max_observations: int,
) -> list[float]:
    if isinstance(action, EvidenceAction):
        d = action.to_dict()
    else:
        d = dict(action)
    name = str(d.get("name") or "")
    name_oh = [1.0 if name == a else 0.0 for a in sorted(ALLOWED_EVIDENCE_ACTIONS)]
    kind = str(d.get("kind") or "")
    kind_oh = [
        1.0 if kind == k else 0.0
        for k in ("side_view", "same_view", "wait", "safe_fallback")
    ]
    observer_oh = [
        1.0 if d.get("observer") == o else 0.0 for o in ("carrier", "scout")
    ]
    feats = [
        float(d.get("predicted_coverage") or 0.0),
        float(d.get("predicted_degradation") or 0.0),
        float(d.get("physical_risk") or 0.0),
        float(d.get("travel_cost") or 0.0),
        1.0 if d.get("reachable") else 0.0,
        observations_taken / max(1, max_observations),
    ]
    feats.extend(kind_oh)
    feats.extend(observer_oh)
    feats.extend(_gap_onehot(gap_reasons))
    feats.extend(name_oh)
    return feats


class RepairRanker(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Linear(hidden, 1),
        )
        self.repair_head = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [B, A, F] or [A, F]
        squeeze = False
        if x.dim() == 2:
            x = x.unsqueeze(0)
            squeeze = True
        util = self.net(x).squeeze(-1)
        repair = torch.sigmoid(self.repair_head(x).squeeze(-1))
        if squeeze:
            util = util.squeeze(0)
            repair = repair.squeeze(0)
        return util, repair


@dataclass
class LearnedPolicyArtifact:
    path: Path
    in_dim: int
    model_version: str = MODEL_VERSION

    def load(self, device: str = "cpu") -> RepairRanker:
        payload = torch.load(self.path, map_location=device, weights_only=False)
        model = RepairRanker(int(payload["in_dim"]))
        model.load_state_dict(payload["state_dict"])
        model.eval()
        return model


def rank_with_learned(
    model: RepairRanker,
    actions: Sequence[EvidenceAction],
    *,
    gap_reasons: Sequence[str],
    observations_taken: int,
    max_observations: int,
    device: str = "cpu",
) -> tuple[EvidenceAction | None, list[dict[str, Any]]]:
    if not actions:
        return None, []
    feats = [
        action_feature_vector(
            a,
            gap_reasons=gap_reasons,
            observations_taken=observations_taken,
            max_observations=max_observations,
        )
        for a in actions
    ]
    x = torch.tensor(feats, dtype=torch.float32, device=device)
    with torch.no_grad():
        util, repair_p = model(x)
    util_l = util.detach().cpu().tolist()
    rep_l = repair_p.detach().cpu().tolist()
    ranked: list[dict[str, Any]] = []
    for a, u, rp in zip(actions, util_l, rep_l):
        ranked.append(
            {
                "action": a.to_dict(),
                "utility": float(u),
                "repair_prob": float(rp),
                "eligible": bool(a.reachable or a.kind == "safe_fallback"),
            }
        )
    ranked.sort(
        key=lambda r: (not r["eligible"], -float(r["utility"]), r["action"]["name"])
    )
    for item in ranked:
        if item["eligible"]:
            ad = item["action"]
            selected = EvidenceAction(
                name=ad["name"],
                kind=ad["kind"],
                observer=ad["observer"],
                corridor_id=ad["corridor_id"],
                viewpoint=ad["viewpoint"],
                target_xy=tuple(ad["target_xy"]),
                predicted_coverage=ad["predicted_coverage"],
                predicted_degradation=ad["predicted_degradation"],
                physical_risk=ad["physical_risk"],
                reachable=ad["reachable"],
                travel_cost=ad["travel_cost"],
            )
            return selected, ranked
    return None, ranked


def heuristic_teacher_utility(
    action: EvidenceAction,
    *,
    gap_reasons: Sequence[str],
    contract_repaired: bool,
    new_root: bool,
) -> float:
    """Offline teacher; may use repair outcome labels, not online oracle world."""
    base = score_action(action, gap_reasons=gap_reasons, visited=set())
    if contract_repaired:
        base += 1.0
    if new_root:
        base += 0.3
    return float(base)


def save_checkpoint(model: RepairRanker, path: Path, in_dim: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "in_dim": in_dim,
            "model_version": MODEL_VERSION,
        },
        path,
    )


def train_listwise(
    samples: list[dict[str, Any]],
    *,
    epochs: int = 20,
    lr: float = 1e-3,
    device: str = "cpu",
) -> tuple[RepairRanker, dict[str, Any]]:
    if not samples:
        raise ValueError("empty training samples")
    in_dim = len(samples[0]["features"][0])
    model = RepairRanker(in_dim).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    history: list[float] = []
    for _ in range(epochs):
        total = 0.0
        n = 0
        for sample in samples:
            feats = torch.tensor(sample["features"], dtype=torch.float32, device=device)
            utilities = torch.tensor(
                sample["utilities"], dtype=torch.float32, device=device
            )
            repair = torch.tensor(
                sample["repair_labels"], dtype=torch.float32, device=device
            )
            # Softmax listwise CE against teacher softmax.
            teacher = F.softmax(utilities, dim=0)
            pred_u, pred_r = model(feats)
            log_p = F.log_softmax(pred_u, dim=0)
            loss_list = -(teacher * log_p).sum()
            loss_bce = F.binary_cross_entropy(pred_r, repair)
            # Pairwise: best vs second
            order = torch.argsort(utilities, descending=True)
            if len(order) >= 2:
                i, j = int(order[0]), int(order[1])
                margin = 0.1
                loss_pair = F.relu(margin - (pred_u[i] - pred_u[j]))
            else:
                loss_pair = pred_u.sum() * 0.0
            loss = loss_list + 0.5 * loss_bce + 0.1 * loss_pair
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
            n += 1
        history.append(total / max(1, n))
    return model, {"epochs": epochs, "loss_history": history, "in_dim": in_dim}


__all__ = (
    "MODEL_VERSION",
    "RepairRanker",
    "LearnedPolicyArtifact",
    "action_feature_vector",
    "rank_with_learned",
    "heuristic_teacher_utility",
    "save_checkpoint",
    "train_listwise",
    "build_candidate_actions",
)
