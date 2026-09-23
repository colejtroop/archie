from __future__ import annotations

import argparse
from pathlib import Path

from .visual_model import VisionSampleDataset, create_visual_encoder, masked_multitask_loss


def main() -> None:
    import torch
    from torch.utils.data import DataLoader, random_split

    parser = argparse.ArgumentParser(description="Train Archie's first visual encoder")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("checkpoints/visual-encoder-v0.pt"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    dataset = VisionSampleDataset(args.samples)
    if len(dataset) < 10:
        raise SystemExit("At least 10 retained vision samples are required")
    validation_size = max(1, round(len(dataset) * 0.2))
    train_size = len(dataset) - validation_size
    train, validation = random_split(dataset, [train_size, validation_size])
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
        "validation_loss": validation_loss / validation_size,
    }, args.output)
    print(f"saved={args.output} validation_loss={validation_loss / validation_size:.5f}")


if __name__ == "__main__":
    main()
