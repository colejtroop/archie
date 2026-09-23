from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from threading import Event
from time import sleep

from .policy import create_objective_selector, select_action
from .policy_data import COMPLETE_ACTION, MAX_WIDTH, masks


ACTIVATION_PATTERN = re.compile(r"activation-(?:cold|active|warm|hot)")


def note_name(layer: str, index: int) -> str:
    return f"{layer}-{index:03d}"


def classify(values: list[float], index: int) -> str:
    magnitude = abs(values[index])
    nonzero = sorted(abs(value) for value in values if value)
    if not nonzero or magnitude == 0:
        return "cold"
    warm = nonzero[max(0, int(len(nonzero) * 0.70) - 1)]
    hot = nonzero[max(0, int(len(nonzero) * 0.92) - 1)]
    if magnitude >= hot:
        return "hot"
    if magnitude >= warm:
        return "warm"
    return "active"


class ObsidianNeuralGraph:
    def __init__(self, vault: Path, checkpoint: Path, top_links: int = 4) -> None:
        import torch

        self.torch = torch
        self.vault = vault
        self.root = vault / "Archie" / "Neural Network"
        self.top_links = top_links
        self.model = create_objective_selector()
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()
        self.activations: dict[str, list[float]] = {}
        for module_index, layer in ((0, "h1"), (2, "h2"), (4, "output")):
            self.model[module_index].register_forward_hook(self._capture(layer))

    def _capture(self, layer: str):
        def hook(_module, _inputs, output) -> None:
            self.activations[layer] = [float(value) for value in output[0].detach().tolist()]
        return hook

    def _write_note(self, layer: str, index: int, links: list[str]) -> None:
        folder = self.root / layer
        folder.mkdir(parents=True, exist_ok=True)
        name = note_name(layer, index)
        content = (
            "---\n"
            f"layer: {layer}\nindex: {index}\n"
            f"tags: [archie-neural, layer-{layer}, activation-cold]\n"
            "---\n"
            f"# {name}\n\n"
            + (" ".join(f"[[{link}]]" for link in links) if links else "Input neuron")
            + "\n"
        )
        (folder / f"{name}.md").write_text(content, encoding="utf-8")

    def materialize(self) -> None:
        input_names = [note_name("blueprint", index) for index in range(25)] + [
            note_name("built", index) for index in range(25)
        ]
        for index in range(25):
            self._write_note("blueprint", index, [])
            self._write_note("built", index, [])

        previous = input_names
        for module_index, layer in ((0, "h1"), (2, "h2"), (4, "output")):
            weights = self.model[module_index].weight.detach()
            current = []
            for index, row in enumerate(weights):
                strongest = self.torch.topk(row.abs(), min(self.top_links, row.numel())).indices.tolist()
                self._write_note(layer, index, [previous[source] for source in strongest])
                current.append(note_name(layer, index))
            previous = current
        self._configure_graph()

    def _configure_graph(self) -> None:
        graph_path = self.vault / ".obsidian" / "graph.json"
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        if graph_path.exists() and not graph_path.with_suffix(".json.archie-backup").exists():
            graph_path.with_suffix(".json.archie-backup").write_bytes(graph_path.read_bytes())
        config = {
            "collapse-filter": False,
            "search": 'path:"Archie/Neural Network"',
            "showTags": False,
            "showAttachments": False,
            "hideUnresolved": True,
            "showOrphans": True,
            "collapse-color-groups": False,
            "colorGroups": [
                {"query": "tag:#activation-hot", "color": {"a": 1, "rgb": 16744272}},
                {"query": "tag:#activation-warm", "color": {"a": 1, "rgb": 10855845}},
                {"query": "tag:#activation-active", "color": {"a": 1, "rgb": 4505434}},
                {"query": "tag:#activation-cold", "color": {"a": 1, "rgb": 6316128}},
            ],
            "collapse-display": False,
            "showArrow": True,
            "textFadeMultiplier": -1.5,
            "nodeSizeMultiplier": 0.75,
            "lineSizeMultiplier": 0.55,
            "collapse-forces": False,
            "centerStrength": 0.45,
            "repelStrength": 12,
            "linkStrength": 0.8,
            "linkDistance": 70,
            "scale": 0.32,
            "close": True,
        }
        graph_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def _set_activation(self, layer: str, values: list[float]) -> None:
        folder = self.root / layer
        for index in range(len(values)):
            path = folder / f"{note_name(layer, index)}.md"
            old = path.read_text(encoding="utf-8")
            new = ACTIVATION_PATTERN.sub(f"activation-{classify(values, index)}", old, count=1)
            if new != old:
                path.write_text(new, encoding="utf-8")

    def step(self, column_heights: list[int]) -> int:
        blueprint, built = masks(3, 3, tuple(column_heights))
        features = tuple(blueprint + built)
        action = select_action(self.model, features)
        self.model(self.torch.tensor([features], dtype=self.torch.float32))
        self._set_activation("blueprint", blueprint)
        self._set_activation("built", built)
        self._set_activation("h1", self.activations["h1"])
        self._set_activation("h2", self.activations["h2"])
        output = self.activations["output"]
        self._set_activation("output", output)
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
    parser.add_argument("--top-links", type=int, default=4)
    args = parser.parse_args()
    graph = ObsidianNeuralGraph(args.vault, args.checkpoint, args.top_links)
    graph.materialize()
    print(f"Obsidian neural graph: {graph.root}")
    print("Open Obsidian Graph View. Press Ctrl+C to stop live activation updates.")
    stop = Event()
    try:
        graph.run_demo(stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
