import unittest

from archie.visual_model import UNKNOWN_ACTION, UNKNOWN_PLACEMENT, target_from_labels


class VisualTargetTests(unittest.TestCase):
    def test_extracts_available_supervision(self) -> None:
        target = target_from_labels({
            "world": {"completion": 0.5},
            "current_action": "POLICY_ACTION_7",
            "placement_result": "SUCCEEDED",
        })
        self.assertEqual(target.progress, 0.5)
        self.assertEqual(target.action, 7)
        self.assertEqual(target.placement, 0)

    def test_marks_unavailable_supervision(self) -> None:
        target = target_from_labels({"world": {}, "current_action": "MOVE", "placement_result": None})
        self.assertEqual(target.progress, -1.0)
        self.assertEqual(target.action, UNKNOWN_ACTION)
        self.assertEqual(target.placement, UNKNOWN_PLACEMENT)


if __name__ == "__main__":
    unittest.main()
