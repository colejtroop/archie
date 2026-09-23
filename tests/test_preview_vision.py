import unittest

from archie.preview_vision import LiveFrameLabels
from archie.telemetry import Event, EventType


class LiveFrameLabelsTests(unittest.TestCase):
    def test_synchronizes_privileged_labels_across_episode(self) -> None:
        labels = LiveFrameLabels()
        labels.consume(Event(EventType.EPISODE_STARTED, {
            "blueprint": "3x3-wall",
            "block": "minecraft:stone",
            "total_blocks": 9,
            "origin": {"x": 1, "y": 2, "z": 3},
            "vision_capture": True,
        }, "now"))
        labels.consume(Event(EventType.STATE_UPDATED, {
            "player": {"x": 0, "y": 2, "z": 3},
            "health": 20,
            "hunger": 20,
            "completion": 0,
            "correct": 0,
            "missing": 9,
            "built_actions": [0, 1],
        }, "now"))
        labels.consume(Event(EventType.OBJECTIVE_SELECTED, {
            "target": {"x": 4, "y": 2, "z": 3},
            "policy_action": 0,
        }, "now"))
        active, episode, snapshot = labels.snapshot()
        self.assertTrue(active)
        self.assertEqual(episode, 1)
        self.assertEqual(snapshot.blueprint["name"], "3x3-wall")
        self.assertEqual(snapshot.survival, {"health": 20, "hunger": 20})
        self.assertEqual(snapshot.current_action, "POLICY_ACTION_0")
        self.assertEqual(snapshot.current_target["x"], 4)
        self.assertEqual(snapshot.world["built_actions"], [0, 1])
        self.assertTrue(snapshot.world["episode"].endswith(":unknown"))
        labels.consume(Event(EventType.EPISODE_COMPLETED, {}, "now"))
        self.assertFalse(labels.snapshot()[0])

    def test_does_not_capture_unarmed_episode(self) -> None:
        labels = LiveFrameLabels()
        labels.consume(Event(EventType.EPISODE_STARTED, {"vision_capture": False}, "now"))
        self.assertFalse(labels.snapshot()[0])
        self.assertEqual(labels.snapshot()[1], 1)


if __name__ == "__main__":
    unittest.main()
