from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True, order=True)
class Position:
    x: int
    y: int
    z: int

    def offset(self, origin: "Position") -> "Position":
        return Position(self.x + origin.x, self.y + origin.y, self.z + origin.z)

    def distance(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)


@dataclass(frozen=True)
class BlockSpec:
    block_type: str
    states: Mapping[str, str | int | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.block_type:
            raise ValueError("block_type cannot be empty")


@dataclass(frozen=True)
class Blueprint:
    name: str
    blocks: Mapping[Position, BlockSpec]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("blueprint name cannot be empty")
        if not self.blocks:
            raise ValueError("blueprint must contain at least one block")

    def at_origin(self, origin: Position) -> dict[Position, BlockSpec]:
        return {relative.offset(origin): block for relative, block in self.blocks.items()}


def wall(width: int = 3, height: int = 3, block_type: str = "minecraft:stone") -> Blueprint:
    if width < 1 or height < 1:
        raise ValueError("wall dimensions must be positive")
    blocks = {
        Position(x, y, 0): BlockSpec(block_type)
        for y in range(height)
        for x in range(width)
    }
    return Blueprint(name=f"{width}x{height}-wall", blocks=blocks)

