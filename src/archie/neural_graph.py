from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from threading import Event

from .policy import create_objective_selector, select_action, valid_actions
from .policy_data import COMPLETE_ACTION, MAX_WIDTH, masks


class ObsidianNeuralGraph:
    """A human-scale, live view of the real objective-selector computation."""

    def __init__(self, vault: Path, checkpoint: Path) -> None:
        import torch

        self.torch = torch
        self.vault = vault
        self.root = vault / "Archie" / "Brain"
        self.model = create_objective_selector()
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()
        self.activations: dict[str, list[float]] = {}
        self.model[1].register_forward_hook(self._capture("features_1"))
        self.model[3].register_forward_hook(self._capture("features_2"))

    def _capture(self, layer: str):
        def hook(_module, _inputs, output) -> None:
            self.activations[layer] = [float(value) for value in output[0].detach().tolist()]

        return hook

    def _note(self, name: str, role: str, links: list[str], body: str, current: bool = False) -> None:
        tags = ["archie-brain", f"brain-{role}"]
        if current:
            tags.append("brain-current")
        content = (
            "---\n"
            f"tags: [{', '.join(tags)}]\n"
            "---\n"
            f"# {name}\n\n{body}\n\n"
            + " ".join(f"[[{link}]]" for link in links)
            + "\n"
        )
        (self.root / f"{name}.md").write_text(content, encoding="utf-8")

    def materialize(self) -> None:
        old_root = self.vault / "Archie" / "Neural Network"
        if old_root.exists():
            shutil.rmtree(old_root)
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self._note("Objective - build 3x3 wall", "objective", [], "The construction objective Archie is pursuing.")
        self._configure_graph()

    def _configure_graph(self) -> None:
        graph_path = self.vault / ".obsidian" / "graph.json"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "collapse-filter": False,
            "search": 'path:"Archie/Brain"',
            "showTags": False,
            "showAttachments": False,
            "hideUnresolved": True,
            "showOrphans": True,
            "collapse-color-groups": False,
            "colorGroups": [
                {"query": "tag:#brain-current", "color": {"a": 1, "rgb": 16766720}},
                {"query": "tag:#brain-objective", "color": {"a": 1, "rgb": 2293759}},
                {"query": "tag:#brain-input", "color": {"a": 1, "rgb": 2948863}},
                {"query": "tag:#brain-state", "color": {"a": 1, "rgb": 3464089}},
                {"query": "tag:#brain-model", "color": {"a": 1, "rgb": 9133302}},
                {"query": "tag:#brain-decision", "color": {"a": 1, "rgb": 15485081}},
                {"query": "tag:#brain-action", "color": {"a": 1, "rgb": 16420412}},
                {"query": "tag:#brain-complete", "color": {"a": 1, "rgb": 2278750}},
            ],
            "collapse-display": False,
            "showArrow": True,
            "textFadeMultiplier": -3,
            "nodeSizeMultiplier": 1.15,
            "lineSizeMultiplier": 0.8,
            "collapse-forces": False,
            "centerStrength": 0.5,
            "repelStrength": 16,
            "linkStrength": 1,
            "linkDistance": 180,
            "scale": 0.75,
            "close": True,
        }
        graph_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def _clear_live_notes(self) -> None:
        for path in self.root.glob("*.md"):
            if not path.name.startswith("Objective -"):
                path.unlink()

    @staticmethod
    def _summary(values: list[float]) -> str:
        active = sum(value > 0 for value in values)
        peak = max(values, default=0.0)
        return f"{active} active features; strongest activation {peak:.3f}."

    def step(self, column_heights: list[int]) -> int:
        blueprint, built = masks(3, 3, tuple(column_heights))
        features = tuple(blueprint + built)
        action = select_action(self.model, features)
        with self.torch.no_grad():
            logits = self.model(self.torch.tensor([features], dtype=self.torch.float32))[0]
        choices = valid_actions(features)
        built_count = int(sum(built))

        self._clear_live_notes()
        objective = "Objective - build 3x3 wall"
        blueprint_name = "Blueprint - 9 stone blocks"
        state_name = f"Observed build - {built_count} of 9 complete"
        feature_1 = "Learned visual-spatial features"
        feature_2 = "Learned construction features"
        valid_name = f"Valid placements - {len(choices)} choices"

        self._note(blueprint_name, "input", [objective], "The 5x5 blueprint mask supplied to the model.")
        self._note(state_name, "state", [blueprint_name], "Privileged V0 observation of blocks already placed.")
        self._note(feature_1, "model", [state_name], self._summary(self.activations["features_1"]))
        self._note(feature_2, "model", [feature_1], self._summary(self.activations["features_2"]))
        valid_body = "Candidate cells allowed by blueprint, occupancy, and support constraints: " + ", ".join(
            "complete" if item == COMPLETE_ACTION else f"({item % MAX_WIDTH}, {item // MAX_WIDTH})"
            for item in choices
        )
        self._note(valid_name, "decision", [feature_2], valid_body)

        if action == COMPLETE_ACTION:
            self._note("Decision - structure complete", "complete", [valid_name], "The policy selected COMPLETE.", True)
        else:
            x, y = action % MAX_WIDTH, action // MAX_WIDTH
            score = float(logits[action].item())
            target_name = f"Decision - place stone at x{x} y{y}"
            self._note(target_name, "decision", [valid_name], f"Selected policy logit: {score:.3f}.", True)
            self._note("Action - place block", "action", [target_name], "Dispatch the selected placement to Minecraft.")
        return action

    def run_demo(self, stop: Event) -> None:
        heights = [0, 0, 0]
        while not stop.is_set():
            action = self.step(heights)
            if action == COMPLETE_ACTION:
                stop.wait(2.5)
                heights = [0, 0, 0]
                continue
            x, y = action % MAX_WIDTH, action // MAX_WIDTH
            if x < 3 and y == heights[x]:
                heights[x] += 1
            stop.wait(1.5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive Archie's model through Obsidian Graph View")
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/objective-selector-v0.pt"))
    args = parser.parse_args()
    graph = ObsidianNeuralGraph(args.vault, args.checkpoint)
    graph.materialize()
    print(f"Obsidian brain graph: {graph.root}")
    print("Open Obsidian Graph View. Press Ctrl+C to stop live updates.")
    stop = Event()
    try:
        graph.run_demo(stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
