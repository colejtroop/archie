import tempfile
import unittest
from pathlib import Path

from archie.neural_graph import ObsidianNeuralGraph
from archie.telemetry import Event, EventType


class ObsidianNeuralGraphTests(unittest.TestCase):
    def test_materializes_real_live_activation_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            graph = ObsidianNeuralGraph(
                Path(directory),
                Path("checkpoints/objective-selector-v0.pt"),
                "V0.5.9",
            )
            graph.materialize()
            graph.consume(Event(EventType.EPISODE_STARTED, {
                "blueprint": "neural-3x3",
                "total_blocks": 9,
                "policy": "objective-selector-v0",
            }, "now"))
            graph.consume(Event(EventType.MODEL_INFERENCE, {
                "blueprint_on": 9,
                "built_on": 2,
                "hidden_1": {"active": 61, "peak": 1.25, "top": [[17, 1.25]]},
                "hidden_2": {"active": 29, "peak": 0.75, "top": [[4, 0.75]]},
                "valid_actions": [2, 3],
                "selected_action": 2,
                "selected_logit": 0.5,
            }, "now"))

            root = Path(directory) / "Archie" / "Brain"
            self.assertIn("Activation 1.2500", (root / "H1 17.md").read_text(encoding="utf-8"))
            self.assertIn("[[H1]]", (root / "H1 17.md").read_text(encoding="utf-8"))
            self.assertIn("brain-current", (root / "Choice.md").read_text(encoding="utf-8"))
            self.assertIn("[[Choice]]", (root / "Live.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
