from __future__ import annotations

from abc import ABC, abstractmethod

from .blueprint import BlockSpec, Position
from .state import AgentState, SurvivalState


class Environment(ABC):
    """Boundary between Archie and Minecraft Bedrock implementation details."""

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def get_agent_state(self) -> AgentState: ...

    @abstractmethod
    def get_blocks(self) -> dict[Position, BlockSpec]: ...

    @abstractmethod
    def move_to(self, position: Position) -> bool: ...

    @abstractmethod
    def select_block(self, block_type: str) -> bool: ...

    @abstractmethod
    def place_block(self, position: Position, block: BlockSpec) -> bool: ...

    @abstractmethod
    def observe_block(self, position: Position) -> BlockSpec | None: ...


class SimulatedEnvironment(Environment):
    """Deterministic embodied test double: move, select, act, then observe."""

    def __init__(self, start: Position = Position(0, 0, -2)) -> None:
        self._start = start
        self._agent = start
        self._selected: str | None = None
        self._blocks: dict[Position, BlockSpec] = {}
        self.distance_traveled = 0

    def reset(self) -> None:
        self._agent = self._start
        self._selected = None
        self._blocks.clear()
        self.distance_traveled = 0

    def get_agent_state(self) -> AgentState:
        return AgentState(
            position=self._agent,
            selected_block=self._selected,
            inventory={"minecraft:stone": 64},
            survival=SurvivalState(health=20.0, hunger=20.0),
        )

    def get_blocks(self) -> dict[Position, BlockSpec]:
        return dict(self._blocks)

    def move_to(self, position: Position) -> bool:
        self.distance_traveled += self._agent.distance(position)
        self._agent = position
        return True

    def select_block(self, block_type: str) -> bool:
        self._selected = block_type
        return True

    def place_block(self, position: Position, block: BlockSpec) -> bool:
        if self._selected != block.block_type or self._agent.distance(position) > 4:
            return False
        self._blocks[position] = block
        return True

    def observe_block(self, position: Position) -> BlockSpec | None:
        return self._blocks.get(position)

