from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from random import Random


MAX_WIDTH = 5
MAX_HEIGHT = 5
CELL_COUNT = MAX_WIDTH * MAX_HEIGHT
COMPLETE_ACTION = CELL_COUNT


@dataclass(frozen=True)
class PolicySample:
    features: tuple[float, ...]
    target: int
    width: int
    height: int
    built_count: int


def cell_index(x: int, y: int) -> int:
    return y * MAX_WIDTH + x


def masks(width: int, height: int, column_heights: tuple[int, ...]) -> tuple[list[float], list[float]]:
    blueprint = [0.0] * CELL_COUNT
    built = [0.0] * CELL_COUNT
    for x in range(width):
        for y in range(height):
            blueprint[cell_index(x, y)] = 1.0
            if y < column_heights[x]:
                built[cell_index(x, y)] = 1.0
    return blueprint, built


def expert_action(width: int, height: int, column_heights: tuple[int, ...]) -> int:
    candidates = [
        (column_heights[x], x)
        for x in range(width)
        if column_heights[x] < height
    ]
    if not candidates:
        return COMPLETE_ACTION
    y, x = min(candidates)
    return cell_index(x, y)


def generate_expert_samples(states_per_shape: int | None = 128, seed: int = 7) -> list[PolicySample]:
    random = Random(seed)
    samples: list[PolicySample] = []
    for width in range(1, MAX_WIDTH + 1):
        for height in range(1, MAX_HEIGHT + 1):
            states = {(0,) * width, (height,) * width}
            canonical = [0] * width
            for _ in range(width * height):
                action = expert_action(width, height, tuple(canonical))
                x, y = action % MAX_WIDTH, action // MAX_WIDTH
                canonical[x] = y + 1
                states.add(tuple(canonical))
            if states_per_shape is None:
                states.update(product(range(height + 1), repeat=width))
            else:
                target_states = min(states_per_shape, (height + 1) ** width)
                while len(states) < target_states:
                    states.add(tuple(random.randint(0, height) for _ in range(width)))
            for column_heights in sorted(states):
                blueprint, built = masks(width, height, column_heights)
                samples.append(
                    PolicySample(
                        features=tuple(blueprint + built),
                        target=expert_action(width, height, column_heights),
                        width=width,
                        height=height,
                        built_count=sum(column_heights),
                    )
                )
    random.shuffle(samples)
    return samples


def split_samples(samples: list[PolicySample], validation_fraction: float = 0.2) -> tuple[list[PolicySample], list[PolicySample]]:
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between zero and one")
    split = max(1, round(len(samples) * (1 - validation_fraction)))
    return samples[:split], samples[split:]
