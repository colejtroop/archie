import json
import unittest

from archie.blueprint import Position, wall
from archie.builder import DeterministicBuilder
from archie.environment import SimulatedEnvironment
from archie.telemetry import EventType, Telemetry


class BuilderTests(unittest.TestCase):
    def test_builder_completes_and_verifies_wall(self) -> None:
        telemetry = Telemetry()
        result = DeterministicBuilder(SimulatedEnvironment(), telemetry).build(wall(3, 3), Position(2, 0, 2))
        self.assertTrue(result.comparison.exact)
        self.assertEqual(result.metrics.correct_blocks, 9)
        self.assertEqual(result.metrics.failed_placements, 0)
        self.assertEqual(telemetry.events[-1].event_type, EventType.EPISODE_COMPLETED)

    def test_telemetry_is_json_serializable(self) -> None:
        telemetry = Telemetry()
        DeterministicBuilder(SimulatedEnvironment(), telemetry).build(wall(1, 1))
        json.dumps([event.to_dict() for event in telemetry.events])

    def test_builder_observes_failure_then_retries(self) -> None:
        class FailOnceEnvironment(SimulatedEnvironment):
            failed = False

            def place_block(self, position, block):
                if not self.failed:
                    self.failed = True
                    return False
                return super().place_block(position, block)

        result = DeterministicBuilder(FailOnceEnvironment(), Telemetry()).build(wall(1, 1))
        self.assertTrue(result.comparison.exact)
        self.assertEqual(result.metrics.failed_placements, 1)
        self.assertEqual(result.metrics.repair_attempts, 1)
        self.assertEqual(result.metrics.repair_successes, 1)


if __name__ == "__main__":
    unittest.main()
