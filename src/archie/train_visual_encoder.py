from __future__ import annotations

import argparse
from pathlib import Path

from .visual_model import (
    VisionSampleDataset,
    create_visual_encoder,
    load_episode_records,
    masked_multitask_loss,
)


def main() -> None:
    import torch
    from torch.utils.data import DataLoader

    parser = argparse.ArgumentParser(description="Train Archie's first visual encoder")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("checkpoints/visual-encoder-v0.pt"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--allow-single-episode-smoke",
        action="store_true",
        help="Permit pipeline smoke-training without a valid held-out episode",
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    episodes = load_episode_records(args.samples)
    if len(episodes) < 2 and not args.allow_single_episode_smoke:
        raise SystemExit("At least two labeled episodes are required for episode-held-out validation")
    all_records = [record for records in episodes.values() for record in records]
    dataset = VisionSampleDataset(args.samples, records=all_records)
    if len(dataset) < 10:
        raise SystemExit("At least 10 retained vision samples are required")
    episode_ids = sorted(episodes)
    if len(episode_ids) >= 2:
        validation_ids = set(episode_ids[-max(1, round(len(episode_ids) * 0.2)):])
        train_records = [record for episode in episode_ids if episode not in validation_ids for record in episodes[episode]]
        validation_records = [record for episode in episode_ids if episode in validation_ids for record in episodes[episode]]
    else:
        split = max(1, round(len(all_records) * 0.8))
        train_records, validation_records = all_records[:split], all_records[split:]
        validation_ids = set()
    train = VisionSampleDataset(args.samples, records=train_records)
    validation = VisionSampleDataset(args.samples, records=validation_records)
    train_size, validation_size = len(train), len(validation)
    model = create_visual_encoder()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    for epoch in range(args.epochs):
        model.train()
        total = 0.0
        for images, targets in DataLoader(train, batch_size=args.batch_size, shuffle=True):
            optimizer.zero_grad()
            loss = masked_multitask_loss(model(images), targets)
            loss.backward()
            optimizer.step()
            total += float(loss.item()) * len(images)
        print(f"epoch={epoch + 1:03d} train_loss={total / train_size:.5f}")

    model.eval()
    validation_loss = 0.0
    with torch.no_grad():
        for images, targets in DataLoader(validation, batch_size=args.batch_size):
            validation_loss += float(masked_multitask_loss(model(images), targets).item()) * len(images)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": "visual-encoder-v0",
        "state_dict": model.state_dict(),
        "embedding_size": 128,
        "samples": len(dataset),
        "training_episodes": sorted(set(episode_ids) - validation_ids),
        "validation_episodes": sorted(validation_ids),
        "split": "episode-held-out" if validation_ids else "single-episode-smoke",
        "validation_loss": validation_loss / validation_size,
    }, args.output)
    print(f"saved={args.output} validation_loss={validation_loss / validation_size:.5f}")


if __name__ == "__main__":
    main()
