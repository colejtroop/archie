from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UNKNOWN_ACTION = -1
UNKNOWN_PLACEMENT = -1
PLACEMENT_CLASSES = {"SUCCEEDED": 0, "FAILED": 1}


@dataclass(frozen=True)
class VisualTarget:
    progress: float
    action: int
    placement: int


def target_from_labels(labels: dict[str, Any]) -> VisualTarget:
    world = labels.get("world") or {}
    raw_progress = world.get("completion")
    progress = float(raw_progress) if isinstance(raw_progress, (int, float)) else -1.0
    current_action = labels.get("current_action")
    action = UNKNOWN_ACTION
    if isinstance(current_action, str) and current_action.startswith("POLICY_ACTION_"):
        try:
            parsed = int(current_action.removeprefix("POLICY_ACTION_"))
            if 0 <= parsed <= 25:
                action = parsed
        except ValueError:
            pass
    placement = PLACEMENT_CLASSES.get(labels.get("placement_result"), UNKNOWN_PLACEMENT)
    return VisualTarget(progress, action, placement)


class VisionSampleDataset:
    def __init__(self, samples: Path, image_size: tuple[int, int] = (160, 90)) -> None:
        self.root = samples.parent
        self.image_size = image_size
        self.records = [
            record
            for line in samples.read_text(encoding="utf-8").splitlines()
            if (record := json.loads(line)).get("image")
        ]

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        import torch
        from PIL import Image

        record = self.records[index]
        image = Image.open(self.root / record["image"]).convert("RGB").resize(self.image_size)
        width, height = self.image_size
        tensor = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8)
        tensor = tensor.view(height, width, 3).permute(2, 0, 1).float().div_(255.0)
        target = target_from_labels(record["labels"])
        return tensor, {
            "progress": torch.tensor(target.progress, dtype=torch.float32),
            "action": torch.tensor(target.action, dtype=torch.long),
            "placement": torch.tensor(target.placement, dtype=torch.long),
        }


def create_visual_encoder(embedding_size: int = 128):
    import torch.nn as nn

    class VisualEncoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 24, 5, stride=2, padding=2),
                nn.ReLU(),
                nn.Conv2d(24, 48, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(48, 96, 3, stride=2, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1)),
                nn.Flatten(),
            )
            self.embedding = nn.Sequential(nn.Linear(96, embedding_size), nn.ReLU())
            self.progress_head = nn.Linear(embedding_size, 1)
            self.action_head = nn.Linear(embedding_size, 26)
            self.placement_head = nn.Linear(embedding_size, 2)

        def forward(self, images):
            embedding = self.embedding(self.features(images))
            return {
                "embedding": embedding,
                "progress": self.progress_head(embedding).squeeze(-1),
                "action": self.action_head(embedding),
                "placement": self.placement_head(embedding),
            }

    return VisualEncoder()


def masked_multitask_loss(outputs, targets):
    import torch
    import torch.nn.functional as functional

    losses = []
    progress_mask = targets["progress"] >= 0
    if progress_mask.any():
        losses.append(functional.mse_loss(outputs["progress"][progress_mask], targets["progress"][progress_mask]))
    action_mask = targets["action"] >= 0
    if action_mask.any():
        losses.append(functional.cross_entropy(outputs["action"][action_mask], targets["action"][action_mask]))
    placement_mask = targets["placement"] >= 0
    if placement_mask.any():
        losses.append(functional.cross_entropy(outputs["placement"][placement_mask], targets["placement"][placement_mask]))
    if not losses:
        return outputs["embedding"].sum() * 0
    return torch.stack(losses).sum()
