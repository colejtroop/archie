from __future__ import annotations

import argparse
import json
from pathlib import Path

from .policy import create_objective_selector, select_action
from .policy_data import generate_expert_samples, split_samples


def accuracy(model, features, targets) -> float:
    import torch

    with torch.no_grad():
        predictions = model(features).argmax(dim=1)
        return float((predictions == targets).float().mean().item())


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Archie's first expert-inherited objective selector")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("checkpoints/objective-selector-v0.pt"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    import torch
    import torch.nn.functional as functional

    torch.manual_seed(args.seed)
    training, validation = split_samples(generate_expert_samples(states_per_shape=None, seed=args.seed))

    def tensors(samples):
        return (
            torch.tensor([sample.features for sample in samples], dtype=torch.float32),
            torch.tensor([sample.target for sample in samples], dtype=torch.long),
        )

    train_x, train_y = tensors(training)
    validation_x, validation_y = tensors(validation)
    model = create_objective_selector()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)

    for _ in range(args.epochs):
        optimizer.zero_grad()
        loss = functional.cross_entropy(model(train_x), train_y)
        loss.backward()
        optimizer.step()

    metrics = {
        "model": "objective-selector-v0",
        "training_samples": len(training),
        "validation_samples": len(validation),
        "training_accuracy": accuracy(model, train_x, train_y),
        "validation_accuracy": accuracy(model, validation_x, validation_y),
        "validation_masked_accuracy": sum(
            select_action(model, sample.features) == sample.target for sample in validation
        ) / len(validation),
        "epochs": args.epochs,
        "seed": args.seed,
        "inputs": "blueprint mask + privileged built-state mask",
        "output": "next supported target cell or complete",
        "vision_features": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "metrics": metrics}, args.output)
    metrics_path = args.output.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
