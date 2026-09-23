import unittest
from importlib.util import find_spec

from archie.visual_model import (
    UNKNOWN_ACTION,
    UNKNOWN_PLACEMENT,
    privileged_features_from_labels,
    target_from_labels,
)


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

    def test_builds_privileged_masks_from_frame_labels(self) -> None:
        features = privileged_features_from_labels({"world": {"built_actions": [0, 5]}})
        self.assertEqual(len(features), 50)
        self.assertEqual(sum(features[:25]), 9)
        self.assertEqual(sum(features[25:]), 2)
        self.assertEqual(features[25], 1)
        self.assertEqual(features[30], 1)

    @unittest.skipIf(find_spec("torch") is None, "PyTorch is an optional dependency")
    def test_fused_policy_starts_exactly_at_privileged_behavior(self) -> None:
        import torch

        from archie.visual_model import create_fused_policy

        model = create_fused_policy()
        images = torch.rand(2, 3, 90, 160)
        features = torch.rand(2, 50)
        privileged = model.privileged(features)
        fused = model(images, features)["logits"]
        self.assertTrue(torch.equal(privileged, fused))
        fused.sum().backward()
        self.assertIsNotNone(model.visual_scale.grad)
        self.assertNotEqual(float(model.visual_scale.grad), 0.0)


if __name__ == "__main__":
    unittest.main()
