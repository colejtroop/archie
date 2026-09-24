from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccessMethod(StrEnum):
    GROUND = "ground"
    JUMP = "jump"
    EXISTING_SUPPORT = "existing_support"
    SCAFFOLD = "scaffold"


@dataclass(frozen=True)
class BuildSite:
    """Temporary privileged geometry used to label construction-strategy choices."""

    width: int
    height: int
    depth: int
    block_count: int
    existing_vertical_support: frozenset[str] = frozenset()
    scaffold_available: int = 64


@dataclass(frozen=True)
class StrategyCandidate:
    approach: str
    access: AccessMethod
    rotations: int
    scaffold_blocks: int
    estimated_steps: int
    camera_turns: int
    trapped_risk: float
    score: float

    def features(self) -> tuple[float, ...]:
        """Stable input vector for the future learned strategy ranker."""
        return (
            float(self.rotations),
            float(self.scaffold_blocks),
            float(self.estimated_steps),
            float(self.camera_turns),
            self.trapped_risk,
            float(self.access is AccessMethod.GROUND),
            float(self.access is AccessMethod.JUMP),
            float(self.access is AccessMethod.EXISTING_SUPPORT),
            float(self.access is AccessMethod.SCAFFOLD),
        )


APPROACHES = ("north", "east", "south", "west")


def enumerate_strategies(site: BuildSite) -> tuple[StrategyCandidate, ...]:
    if min(site.width, site.height, site.depth, site.block_count) < 1:
        raise ValueError("build-site dimensions and block count must be positive")

    candidates: list[StrategyCandidate] = []
    for rotations, approach in enumerate(APPROACHES):
        face_width = site.width if rotations % 2 == 0 else site.depth
        travel = site.block_count + face_width * 2
        turns = max(1, face_width - 1) + rotations
        support = approach in site.existing_vertical_support

        if support:
            access = AccessMethod.EXISTING_SUPPORT
            scaffolds = 0
            risk = 0.05
        elif site.height <= 3:
            access = AccessMethod.GROUND
            scaffolds = 0
            risk = 0.08
        elif site.height == 4:
            access = AccessMethod.JUMP
            scaffolds = 0
            travel += face_width
            risk = 0.18
        else:
            access = AccessMethod.SCAFFOLD
            # One reusable stair/tower per two blocks of face width. The planner
            # accounts for cleanup even though V1 lends these temporary blocks.
            levels = max(1, site.height - 3)
            scaffolds = levels * max(1, (face_width + 1) // 2)
            travel += scaffolds * 3
            risk = 0.12 + 0.02 * levels

        if scaffolds > site.scaffold_available:
            continue
        score = travel + turns * 0.75 + scaffolds * 4.0 + risk * 20.0
        candidates.append(
            StrategyCandidate(
                approach=approach,
                access=access,
                rotations=rotations,
                scaffold_blocks=scaffolds,
                estimated_steps=travel,
                camera_turns=turns,
                trapped_risk=risk,
                score=score,
            )
        )
    return tuple(candidates)


def choose_strategy(site: BuildSite) -> StrategyCandidate:
    candidates = enumerate_strategies(site)
    if not candidates:
        raise ValueError("no executable strategy fits the available scaffold budget")
    return min(candidates, key=lambda candidate: (candidate.score, candidate.rotations))
