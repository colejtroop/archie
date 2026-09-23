import unittest

from archie.placement_controller import PlacementAction, PlacementController


class PlacementControllerTests(unittest.TestCase):
    def test_places_when_target_is_reachable(self) -> None:
        decision = PlacementController().before_placement(1.5)
        self.assertEqual(decision.action, PlacementAction.PLACE)

    def test_repositions_then_aborts_when_unreachable(self) -> None:
        controller = PlacementController(max_attempts=2)
        self.assertEqual(controller.before_placement(4, 0).action, PlacementAction.REPOSITION)
        self.assertEqual(controller.before_placement(4, 2).action, PlacementAction.ABORT)

    def test_retries_failed_observation_then_advances(self) -> None:
        controller = PlacementController(max_attempts=3)
        self.assertEqual(controller.after_observation(False, 1).action, PlacementAction.RETRY)
        self.assertEqual(controller.after_observation(True, 2).action, PlacementAction.ADVANCE)
        self.assertEqual(controller.after_observation(False, 3).action, PlacementAction.ABORT)


if __name__ == "__main__":
    unittest.main()
