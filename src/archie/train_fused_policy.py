from __future__ import annotations

import argparse
from pathlib import Path

from .policy import valid_actions
from .visual_model import (
    VisionSampleDataset,
    create_fused_policy,
    load_episode_records,
    privileged_features_from_labels,
)


class FusedSampleDataset:
    def __init__(self, samples: Path, records: list[dict]) -> None:
        self.vision = VisionSampleDataset(samples, records=records)
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        import torch

        image, targets = self.vision[index]
        features = privileged_features_from_labels(self.records[index].get("labels", {}))
        return image, torch.tensor(features, dtype=torch.float32), targets["action"]


def masked_action_loss(logits, features, targets):
    import torch
    import torch.nn.functional as functional

    keep = targets >= 0
    if not bool(keep.any()):
        return logits.sum() * 0
    selected_logits = logits[keep].clone()
    selected_features = features[keep]
    for row, feature in enumerate(selected_features):
        allowed = valid_actions(tuple(float(value) for value in feature.tolist()))
        mask = torch.full_like(selected_logits[row], float("-inf"))
        mask[allowed] = 0
        selected_logits[row] += mask
    return functional.cross_entropy(selected_logits, targets[keep])


def main() -> None:
    import torch
    from torch.utils.data import DataLoader

    parser = argparse.ArgumentParser(description="Train Archie's vision-fused residual policy")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--objective-checkpoint", type=Path, required=True)
    parser.add_argument("--visual-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("checkpoints/vision-fused-policy-v1.pt"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    episodes = load_episode_records(args.samples)
    if len(episodes) < 3:
        raise SystemExit("At least three clean episodes are required to train and hold out the fused policy")
    episode_ids = sorted(episodes)
    validation_id = episode_ids[-1]
    train_records = [record for episode in episode_ids[:-1] for record in episodes[episode]]
    validation_records = list(episodes[validation_id])
    model = create_fused_policy()
    model.privileged.load_state_dict(torch.load(args.objective_checkpoint, map_location="cpu")["state_dict"])
    model.visual.load_state_dict(torch.load(args.visual_checkpoint, map_location="cpu")["state_dict"])
    for parameter in model.privileged.parameters():
        parameter.requires_grad = False

    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=3e-4)
    train = FusedSampleDataset(args.samples, train_records)
    validation = FusedSampleDataset(args.samples, validation_records)
    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        labeled = 0
        for images, features, targets in DataLoader(train, batch_size=args.batch_size, shuffle=True):
            optimizer.zero_grad()
            loss = masked_action_loss(model(images, features)["logits"], features, targets)
            loss.backward()
            optimizer.step()
            count = int((targets >= 0).sum().item())
            total += float(loss.item()) * count
            labeled += count
        print(f"epoch={epoch + 1:03d} train_loss={total / max(labeled, 1):.5f} visual_scale={model.visual_scale.item():.5f}")

    model.eval()
    validation_loss = 0.0
    labeled = 0
    with torch.no_grad():
        for images, features, targets in DataLoader(validation, batch_size=args.batch_size):
            loss = masked_action_loss(model(images, features)["logits"], features, targets)
            count = int((targets >= 0).sum().item())
            validation_loss += float(loss.item()) * count
            labeled += count
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": "vision-fused-policy-v1",
        "state_dict": model.state_dict(),
        "training_episodes": episode_ids[:-1],
        "validation_episodes": [validation_id],
        "validation_loss": validation_loss / max(labeled, 1),
    }, args.output)
    print(f"saved={args.output} validation_loss={validation_loss / max(labeled, 1):.5f}")


if __name__ == "__main__":
    main()
