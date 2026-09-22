from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .blueprint import BlockSpec, Position


class BlockRole(str, Enum):
    PERMANENT = "permanent"
    SCAFFOLD = "scaffold"


@dataclass(frozen=True)
class SurvivalState:
    health: float | None = None
    hunger: float | None = None
    nearby_hostiles: tuple[str, ...] = ()
    dead: bool = False
    time_of_day: int | None = None


@dataclass(frozen=True)
class AgentState:
    position: Position
    yaw: float = 0.0
    pitch: float = 0.0
    selected_block: str | None = None
    inventory: Mapping[str, int] = field(default_factory=dict)
    survival: SurvivalState = field(default_factory=SurvivalState)


@dataclass(frozen=True)
class BuildComparison:
    correct: Mapping[Position, BlockSpec]
    missing: Mapping[Position, BlockSpec]
    incorrect: Mapping[Position, tuple[BlockSpec, BlockSpec]]
    extra: Mapping[Position, BlockSpec]

    @property
    def exact(self) -> bool:
        return not self.missing and not self.incorrect and not self.extra

    @property
    def completion(self) -> float:
        total = len(self.correct) + len(self.missing) + len(self.incorrect)
        return len(self.correct) / total if total else 1.0


def compare_build(
    target: Mapping[Position, BlockSpec], current: Mapping[Position, BlockSpec]
) -> BuildComparison:
    correct: dict[Position, BlockSpec] = {}
    missing: dict[Position, BlockSpec] = {}
    incorrect: dict[Position, tuple[BlockSpec, BlockSpec]] = {}
    for position, desired in target.items():
        observed = current.get(position)
        if observed is None:
            missing[position] = desired
        elif observed == desired:
            correct[position] = desired
        else:
            incorrect[position] = (desired, observed)
    extra = {position: block for position, block in current.items() if position not in target}
    return BuildComparison(correct, missing, incorrect, extra)

