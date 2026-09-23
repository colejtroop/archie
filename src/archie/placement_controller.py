from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlacementAction(str, Enum):
    APPROACH = "APPROACH"
    PLACE = "PLACE"
    VERIFY = "VERIFY"
    REPOSITION = "REPOSITION"
    RETRY = "RETRY"
    ADVANCE = "ADVANCE"
    ABORT = "ABORT"


@dataclass(frozen=True)
class PlacementDecision:
    action: PlacementAction
    reason: str


class PlacementController:
    """Low-level branch policy beneath the construction objective selector."""

    def __init__(self, reach: float = 2.25, max_attempts: int = 3) -> None:
        self.reach = reach
        self.max_attempts = max_attempts

    def before_placement(self, distance: float, reposition_attempts: int = 0) -> PlacementDecision:
        if distance <= self.reach:
            return PlacementDecision(PlacementAction.PLACE, "target is within interaction reach")
        if reposition_attempts < self.max_attempts:
            return PlacementDecision(PlacementAction.REPOSITION, "target is outside interaction reach")
        return PlacementDecision(PlacementAction.ABORT, "target remained unreachable after repositioning")

    def after_observation(self, succeeded: bool, attempt: int) -> PlacementDecision:
        if succeeded:
            return PlacementDecision(PlacementAction.ADVANCE, "intended block was observed")
        if attempt < self.max_attempts:
            return PlacementDecision(PlacementAction.RETRY, "placement was not observed")
        return PlacementDecision(PlacementAction.ABORT, "placement retry budget was exhausted")
