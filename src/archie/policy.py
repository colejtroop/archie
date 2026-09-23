from __future__ import annotations

from .policy_data import CELL_COUNT, COMPLETE_ACTION, MAX_WIDTH


def create_objective_selector():
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(CELL_COUNT * 2, 128),
        nn.ReLU(),
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Linear(64, COMPLETE_ACTION + 1),
    )


def valid_actions(features: tuple[float, ...]) -> list[int]:
    blueprint = features[:CELL_COUNT]
    built = features[CELL_COUNT:]
    valid = [
        index
        for index in range(CELL_COUNT)
        if blueprint[index]
        and not built[index]
        and (index // MAX_WIDTH == 0 or built[index - MAX_WIDTH])
    ]
    return valid or [COMPLETE_ACTION]


def select_action(model, features: tuple[float, ...]) -> int:
    import torch

    with torch.no_grad():
        logits = model(torch.tensor([features], dtype=torch.float32))[0]
        mask = torch.full_like(logits, float("-inf"))
        mask[valid_actions(features)] = 0
        return int((logits + mask).argmax().item())
