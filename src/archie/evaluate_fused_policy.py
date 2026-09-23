from __future__ import annotations

import argparse
import json
from pathlib import Path

from .policy import valid_actions
from .train_fused_policy import FusedSampleDataset
from .visual_model import create_fused_policy, load_episode_records


def masked_prediction(logits, features) -> int:
    allowed = valid_actions(tuple(float(value) for value in features.tolist()))
    return max(allowed, key=lambda action: float(logits[action]))


def main() -> None:
    import torch
    from torch.utils.data import DataLoader

    parser = argparse.ArgumentParser(description="Evaluate Archie's fused policy on held-out episodes")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    held_out = set(str(value) for value in checkpoint.get("validation_episodes", []))
    episodes = load_episode_records(args.samples)
    records = [record for episode in sorted(held_out) for record in episodes.get(episode, [])]
    if not records:
        raise SystemExit("Checkpoint validation episodes were not found in the sample set")

    model = create_fused_policy()
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    counts = {"labeled": 0, "fused_correct": 0, "privileged_correct": 0, "zero_image_correct": 0}
    residuals: list[float] = []
    sensitivities: list[float] = []
    with torch.no_grad():
        for images, features, targets in DataLoader(
            FusedSampleDataset(args.samples, records), batch_size=args.batch_size
        ):
            fused = model(images, features)["logits"]
            privileged = model.privileged(features)
            zero_image = model(torch.zeros_like(images), features)["logits"]
            residuals.append(float((fused - privileged).abs().mean().item()))
            sensitivities.append(float((fused - zero_image).abs().mean().item()))
            for row, target in enumerate(targets.tolist()):
                if target < 0:
                    continue
                counts["labeled"] += 1
                counts["fused_correct"] += masked_prediction(fused[row], features[row]) == target
                counts["privileged_correct"] += masked_prediction(privileged[row], features[row]) == target
                counts["zero_image_correct"] += masked_prediction(zero_image[row], features[row]) == target

    labeled = counts["labeled"]
    metrics = {
        "model": "vision-fused-policy-v1",
        "held_out_episodes": sorted(held_out),
        "held_out_frames": len(records),
        "labeled_actions": labeled,
        "fused_masked_accuracy": counts["fused_correct"] / labeled,
        "privileged_masked_accuracy": counts["privileged_correct"] / labeled,
        "zero_image_masked_accuracy": counts["zero_image_correct"] / labeled,
        "mean_abs_visual_residual": sum(residuals) / len(residuals),
        "mean_abs_real_vs_zero_image": sum(sensitivities) / len(sensitivities),
        "visual_scale": float(model.visual_scale.item()),
    }
    rendered = json.dumps(metrics, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
