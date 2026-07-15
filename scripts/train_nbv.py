"""在 ROCm PyTorch 上训练共享候选点效用 MLP，并评估独立 test split。"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dataset_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ranking_metrics(records: list[dict], predictions: list[float]) -> dict[str, float]:
    groups: dict[str, list[tuple[dict, float]]] = defaultdict(list)
    for record, prediction in zip(records, predictions):
        groups[record["decision_id"]].append((record, prediction))
    learned_regret = heuristic_regret = top1 = 0.0
    for group in groups.values():
        oracle_best = max(record["label"] for record, _ in group)
        learned_choice = max(group, key=lambda item: item[1])[0]
        heuristic_choice = max(group, key=lambda item: item[0]["heuristic_utility"])[0]
        learned_regret += oracle_best - learned_choice["label"]
        heuristic_regret += oracle_best - heuristic_choice["label"]
        top1 += float(learned_choice["label"] == oracle_best)
    count = max(1, len(groups))
    return {
        "decision_count": float(len(groups)),
        "learned_oracle_regret": learned_regret / count,
        "heuristic_oracle_regret": heuristic_regret / count,
        "learned_top1_accuracy": top1 / count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import torch
    from learned_nbv import FEATURE_NAMES, build_model

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    train, validation, test = map(load_records, (args.train, args.validation, args.test))
    if not train or not validation or not test:
        raise SystemExit("All three dataset splits must contain records")

    def tensors(records: list[dict]):
        features = torch.tensor([row["features"] for row in records], dtype=torch.float32)
        labels = torch.tensor([row["label"] for row in records], dtype=torch.float32)[:, None]
        return features, labels

    train_x, train_y = tensors(train)
    val_x, val_y = tensors(validation)
    test_x, test_y = tensors(test)
    mean = train_x.mean(dim=0)
    std = train_x.std(dim=0).clamp_min(1e-6)
    train_x = ((train_x - mean) / std).to(args.device)
    train_y = train_y.to(args.device)
    val_x = ((val_x - mean) / std).to(args.device)
    val_y = val_y.to(args.device)
    test_x = ((test_x - mean) / std).to(args.device)
    test_y = test_y.to(args.device)

    model = build_model(torch).to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_function = torch.nn.MSELoss()
    best_state = None
    best_validation = float("inf")
    for epoch in range(args.epochs):
        permutation = torch.randperm(len(train_x), device=args.device)
        model.train()
        for start in range(0, len(train_x), args.batch_size):
            indices = permutation[start : start + args.batch_size]
            loss = loss_function(model(train_x[indices]), train_y[indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(loss_function(model(val_x), val_y).item())
        if validation_loss < best_validation:
            best_validation = validation_loss
            best_state = {name: value.detach().cpu() for name, value in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        test_predictions = model(test_x).squeeze(1).cpu().tolist()
        test_mse = float(loss_function(model(test_x), test_y).item())
    ranking = ranking_metrics(test, test_predictions)
    passed_gate = ranking["learned_oracle_regret"] < ranking["heuristic_oracle_regret"]
    digest = dataset_sha256([args.train, args.validation, args.test])
    checkpoint = {
        "state_dict": best_state,
        "feature_names": list(FEATURE_NAMES),
        "feature_mean": mean.tolist(),
        "feature_std": std.tolist(),
        "training_data_sha256": digest,
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.model_output)
    metrics = {
        "validation_mse": best_validation,
        "test_mse": test_mse,
        **ranking,
        "passed_promotion_gate": passed_gate,
        "dataset_sha256": digest,
        "device": args.device,
        "epochs": args.epochs,
    }
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
