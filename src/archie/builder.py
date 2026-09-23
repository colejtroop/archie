from __future__ import annotations

from dataclasses import asdict, dataclass
from time import monotonic

from .blueprint import Blueprint, Position
from .environment import Environment
from .placement_controller import PlacementAction, PlacementController
from .state import BuildComparison, compare_build
from .telemetry import EventType, Telemetry


@dataclass
class BuildMetrics:
    total_actions: int = 0
    failed_placements: int = 0
    repair_attempts: int = 0
    repair_successes: int = 0
    distance_traveled: int = 0
    build_time_seconds: float = 0.0
    correct_blocks: int = 0
    incorrect_blocks: int = 0
    missing_blocks: int = 0
    extra_blocks: int = 0
    completion: float = 0.0
    exact_completion: bool = False


@dataclass(frozen=True)
class BuildResult:
    comparison: BuildComparison
    metrics: BuildMetrics


class DeterministicBuilder:
    def __init__(self, environment: Environment, telemetry: Telemetry, max_attempts: int = 3) -> None:
        self.environment = environment
        self.telemetry = telemetry
        self.max_attempts = max_attempts
        self.placement_controller = PlacementController(max_attempts=max_attempts)

    def build(self, blueprint: Blueprint, origin: Position = Position(0, 0, 0)) -> BuildResult:
        started = monotonic()
        metrics = BuildMetrics()
        target = blueprint.at_origin(origin)
        self.environment.reset()
        self.telemetry.publish(EventType.EPISODE_STARTED, blueprint=blueprint.name)
        self.telemetry.publish(EventType.BLUEPRINT_LOADED, name=blueprint.name, blocks=len(target))

        for position, block in sorted(target.items(), key=lambda item: (item[0].y, item[0].x, item[0].z)):
            self.telemetry.publish(EventType.OBJECTIVE_SELECTED, target=asdict(position), block=block.block_type)
            work_position = Position(position.x, max(0, position.y - 1), position.z - 1)
            self.telemetry.publish(EventType.MOVEMENT_STARTED, destination=asdict(work_position))
            before = self.environment.get_agent_state().position
            self.environment.move_to(work_position)
            metrics.distance_traveled += before.distance(work_position)
            self.environment.select_block(block.block_type)

            self.telemetry.publish(
                EventType.PLACEMENT_DECISION,
                decision=PlacementAction.PLACE.value,
                reason="target is within simulated interaction reach",
                target=asdict(position),
            )

            for attempt in range(1, self.max_attempts + 1):
                metrics.total_actions += 1
                self.telemetry.publish(
                    EventType.BLOCK_PLACEMENT_ATTEMPTED,
                    target=asdict(position), block=block.block_type, attempt=attempt,
                )
                self.environment.place_block(position, block)
                observed = self.environment.observe_block(position)
                decision = self.placement_controller.after_observation(observed == block, attempt)
                self.telemetry.publish(
                    EventType.PLACEMENT_DECISION,
                    decision=decision.action.value,
                    reason=decision.reason,
                    target=asdict(position),
                    attempt=attempt,
                )
                if decision.action is PlacementAction.ADVANCE:
                    self.telemetry.publish(EventType.BLOCK_PLACEMENT_SUCCEEDED, target=asdict(position))
                    if attempt > 1:
                        metrics.repair_successes += 1
                    break
                metrics.failed_placements += 1
                self.telemetry.publish(
                    EventType.BLOCK_PLACEMENT_FAILED,
                    target=asdict(position), observed=observed.block_type if observed else None,
                )
                if decision.action is PlacementAction.RETRY:
                    metrics.repair_attempts += 1
                    self.telemetry.publish(EventType.FAULT_DETECTED, target=asdict(position), action="retry")

            comparison = compare_build(target, self.environment.get_blocks())
            state = self.environment.get_agent_state()
            self.telemetry.publish(
                EventType.STATE_UPDATED,
                completion=comparison.completion,
                correct=len(comparison.correct),
                missing=len(comparison.missing),
                position=asdict(state.position),
                health=state.survival.health,
                hunger=state.survival.hunger,
            )

        comparison = compare_build(target, self.environment.get_blocks())
        metrics.build_time_seconds = monotonic() - started
        metrics.correct_blocks = len(comparison.correct)
        metrics.incorrect_blocks = len(comparison.incorrect)
        metrics.missing_blocks = len(comparison.missing)
        metrics.extra_blocks = len(comparison.extra)
        metrics.completion = comparison.completion
        metrics.exact_completion = comparison.exact
        self.telemetry.publish(EventType.EPISODE_COMPLETED, **asdict(metrics))
        return BuildResult(comparison, metrics)

