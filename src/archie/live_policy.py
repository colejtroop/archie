from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .policy import valid_actions


class PolicySource(str, Enum):
    FUSED_V1 = "vision-fused-policy-v1"
    PRIVILEGED_FALLBACK = "objective-selector-v0-fallback"


@dataclass(frozen=True)
class LivePolicyDecision:
    episode: str
    state_revision: int
    action: int
    source: PolicySource

    def validate(self, features: tuple[float, ...]) -> None:
        if self.action not in valid_actions(features):
            raise ValueError(f"action {self.action} is invalid for state revision {self.state_revision}")


class DecisionGate:
    """Rejects stale/unsafe external decisions before Bedrock can execute them."""

    def __init__(self) -> None:
        self.episode: str | None = None
        self.state_revision = -1

    def begin(self, episode: str) -> None:
        self.episode = episode
        self.state_revision = 0

    def advance(self) -> None:
        if self.episode is None:
            raise RuntimeError("no live episode")
        self.state_revision += 1

    def accept(self, decision: LivePolicyDecision, features: tuple[float, ...]) -> bool:
        if decision.episode != self.episode or decision.state_revision != self.state_revision:
            return False
        decision.validate(features)
        return True
