from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path
from threading import Event, Thread
from time import sleep

from .bedrock_bridge import BedrockBridge, ContentLogBridge
from .collector import TrajectoryWriter, default_content_log_directory, default_output
from .policy import create_objective_selector, select_action, valid_actions
from .policy_data import COMPLETE_ACTION, MAX_WIDTH, masks
from .live_fused_runtime import LiveFusedRuntime
from .preview_vision import LiveFrameLabels, capture_preview
from .telemetry import Event as TelemetryEvent
from .telemetry import EventType, Telemetry
from .vision import RecordingPolicy, VisionRecorder


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
        self.built_actions: set[int] = set()
        self.current_action: int | None = None
        self.current_target_note: str | None = None
        self.placement_note: str | None = None
        self.last_policy = "unknown"
        self.applied_decisions = 0
        self.fallback_decisions = 0
        self.rejected_decisions = 0
        self.blueprint_name = "3x3-wall"
        self.total_blocks = 9
        self.spatial_episode = False
        self.model[1].register_forward_hook(self._capture("features_1"))
        self.model[3].register_forward_hook(self._capture("features_2"))

    def _capture(self, layer: str):
        def hook(_module, _inputs, output) -> None:
            self.activations[layer] = [float(value) for value in output[0].detach().tolist()]

        return hook

    def _note(self, name: str, role: str, links: list[str], body: str, current: bool = False) -> None:
        if current:
            self._clear_current_tags()
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

    def _clear_current_tags(self) -> None:
        """Keep exactly one graph node illuminated as execution advances."""
        for path in self.root.glob("*.md"):
            if not self._is_generated(path):
                continue
            content = path.read_text(encoding="utf-8")
            if "brain-current" not in content:
                continue
            content = content.replace(", brain-current", "").replace("brain-current, ", "")
            path.write_text(content, encoding="utf-8")

    def materialize(self) -> None:
        old_root = self.vault / "Archie" / "Neural Network"
        if old_root.exists():
            for path in old_root.glob("*.md"):
                if self._is_generated(path):
                    path.unlink()
        self.root.mkdir(parents=True, exist_ok=True)
        for path in self.root.glob("*.md"):
            if self._is_generated(path):
                path.unlink()
        self._note("Objective - build 3x3 wall", "objective", [], "The construction objective Archie is pursuing.")
        self._note(
            "Architecture - objective selector",
            "model",
            ["Objective - build 3x3 wall"],
            "Chooses the next supported blueprint cell from blueprint and privileged built-state masks.",
        )
        self._note(
            "Architecture - placement controller",
            "model",
            ["Architecture - objective selector"],
            "Executes each objective through approach, place, verify, reposition, retry, advance, or abort.",
        )
        self._note(
            "Architecture - spatial blueprint planner",
            "model",
            ["Objective - build 3x3 wall", "Architecture - placement controller"],
            "Orders imported 3D cells into supported floor, lane, and far-to-near placement rays.",
        )
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
            if self._is_generated(path) and not path.name.startswith(("Objective -", "Architecture -")):
                path.unlink()

    @staticmethod
    def _is_generated(path: Path) -> bool:
        try:
            return "archie-brain" in path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False

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
        feature_1 = "Learned privileged-state features"
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
            self.current_target_note = target_name
            self.placement_note = target_name
            self._note(target_name, "decision", [valid_name], f"Selected policy logit: {score:.3f}.", True)
            self._note("Action - place block", "action", [target_name], "Dispatch the selected placement to Minecraft.")
        return action

    def consume(self, event: TelemetryEvent) -> None:
        """Update the graph from a real Minecraft Preview telemetry event."""
        if event.event_type is EventType.EPISODE_STARTED:
            self.built_actions.clear()
            self.current_action = None
            self.last_policy = "unknown"
            self.applied_decisions = 0
            self.fallback_decisions = 0
            self.rejected_decisions = 0
            self.blueprint_name = str(event.payload.get("blueprint", "unknown-blueprint"))
            self.total_blocks = int(event.payload.get("total_blocks", 0) or 0)
            self.spatial_episode = event.payload.get("policy") == "spatial-blueprint-planner-v0"
            if self.spatial_episode:
                self._clear_live_notes()
                for path in self.root.glob("Objective - *.md"):
                    if self._is_generated(path):
                        path.unlink()
                objective = f"Objective - build {self.blueprint_name}"
                blueprint = f"Blueprint - {self.blueprint_name} ({self.total_blocks} blocks)"
                self._note(objective, "objective", [], "The imported spatial construction objective.")
                self._note(
                    blueprint,
                    "input",
                    [objective, "Architecture - spatial blueprint planner"],
                    "Validated cells and palette decoded from the Bedrock .mcstructure input.",
                    True,
                )
            else:
                self._note("Objective - build 3x3 wall", "objective", [], "The construction objective Archie is pursuing.")
                self.step([0, 0, 0])
            return
        if event.event_type is EventType.POLICY_DECISION_APPLIED:
            self.applied_decisions += 1
            return
        if event.event_type is EventType.POLICY_FALLBACK_USED:
            self.fallback_decisions += 1
            return
        if event.event_type is EventType.POLICY_DECISION_REJECTED:
            self.rejected_decisions += 1
            return
        if event.event_type is EventType.OBJECTIVE_SELECTED:
            raw_action = event.payload.get("policy_action")
            if isinstance(raw_action, int):
                self.current_action = raw_action
            policy = str(event.payload.get("policy", "unknown"))
            self.last_policy = policy
            if self.spatial_episode:
                target = event.payload.get("target")
                note = f"Spatial objective - action {self.current_action}"
                self._note(
                    note,
                    "decision",
                    ["Architecture - spatial blueprint planner"],
                    f"Selected the next supported cell at {target} in the active placement ray.",
                    True,
                )
                self.current_target_note = note
                self.placement_note = note
                return
            heights = [0, 0, 0]
            for action in self.built_actions:
                x, y = action % MAX_WIDTH, action // MAX_WIDTH
                if x < len(heights):
                    heights[x] = max(heights[x], y + 1)
            predicted = self.step(heights)
            source_note = f"Policy source - {policy}"
            self._note(
                source_note,
                "model",
                [self.current_target_note or "Architecture - objective selector"],
                "The policy source that selected the live objective for this state revision.",
                True,
            )
            self.placement_note = source_note
            if self.current_action is not None and predicted != self.current_action:
                title = "Vision changed objective" if policy == "vision-fused-policy-v1" else "Warning - policy mismatch"
                self._note(
                    title,
                    "action",
                    [source_note],
                    f"Privileged selector proposed {predicted}; live policy selected {self.current_action}.",
                    True,
                )
            return
        if event.event_type is EventType.PLACEMENT_DECISION:
            decision = str(event.payload.get("decision", "UNKNOWN")).lower()
            reason = str(event.payload.get("reason", "No reason reported."))
            target = event.payload.get("target")
            note = f"Placement controller - {decision}"
            parent = self.placement_note or self.current_target_note or "Architecture - placement controller"
            self._note(
                note,
                "action",
                [parent, "Architecture - placement controller"],
                f"Target: {target}. Reason: {reason}",
                True,
            )
            self.placement_note = note
            return
        if event.event_type is EventType.BLOCK_PLACEMENT_SUCCEEDED and self.current_action is not None:
            self.built_actions.add(self.current_action)
            if self.spatial_episode:
                progress = f"Observed build - {len(self.built_actions)} of {self.total_blocks} complete"
                self._note(
                    progress,
                    "state",
                    [self.placement_note or "Architecture - placement controller"],
                    "Minecraft confirmed the intended block at the selected spatial target.",
                    True,
                )
                self.placement_note = progress
                return
            heights = [0, 0, 0]
            for action in self.built_actions:
                x, y = action % MAX_WIDTH, action // MAX_WIDTH
                if x < len(heights):
                    heights[x] = max(heights[x], y + 1)
            self.step(heights)
            return
        if event.event_type is EventType.EPISODE_COMPLETED:
            if not self.spatial_episode:
                self.step([3, 3, 3])
            self._note(
                f"Episode policy - {self.last_policy}",
                "complete",
                [self.placement_note or "Architecture - placement controller"],
                f"Completed {len(self.built_actions)} of {self.total_blocks} blocks. "
                f"Applied external decisions: {self.applied_decisions}. Fallbacks: {self.fallback_decisions}. "
                f"Rejections: {self.rejected_decisions}.",
                True,
            )
            return
        if event.event_type is EventType.EPISODE_FAILED:
            self._note("Build failed", "action", ["Learned construction features"], str(event.payload), True)

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
    parser.add_argument("--source", choices=("live", "demo"), default="live")
    parser.add_argument("--content-log-directory", type=Path, default=None)
    parser.add_argument("--trajectory-output", type=Path, default=None)
    parser.add_argument("--capture-vision", action="store_true")
    parser.add_argument("--vision-fps", type=float, default=2.0)
    parser.add_argument("--vision-max-frames", type=int, default=300)
    parser.add_argument("--vision-warmup", type=float, default=6.0)
    parser.add_argument("--vision-output", type=Path, default=Path("data/generated/vision/preview"))
    parser.add_argument("--live-fused", action="store_true")
    parser.add_argument("--fused-checkpoint", type=Path, default=Path("checkpoints/vision-fused-policy-v1.pt"))
    parser.add_argument("--external-token", default=None)
    args = parser.parse_args()
    graph = ObsidianNeuralGraph(args.vault, args.checkpoint)
    graph.materialize()
    print(f"Obsidian brain graph: {graph.root}")
    print("Open Obsidian Graph View. Press Ctrl+C to stop live updates.")
    stop = Event()
    try:
        if args.source == "demo":
            graph.run_demo(stop)
        else:
            output = args.trajectory_output or default_output()
            writer = TrajectoryWriter(output)
            live_labels = LiveFrameLabels()
            fused_runtime: LiveFusedRuntime | None = None

            def sink(event: TelemetryEvent) -> None:
                writer(event)
                graph.consume(event)
                live_labels.consume(event)
                if fused_runtime:
                    fused_runtime.consume(event)

            telemetry = Telemetry(sink=sink)
            directory = args.content_log_directory or default_content_log_directory()
            content_bridge = ContentLogBridge(telemetry, directory)
            content_bridge.start()
            recorder = None
            if args.capture_vision:
                recorder = VisionRecorder(
                    RecordingPolicy(True, sample_every=1, max_frames=args.vision_max_frames, persist_images=True),
                    args.vision_output,
                )
                Thread(
                    target=capture_preview,
                    args=(recorder, live_labels, stop, args.vision_fps, args.vision_warmup),
                    daemon=True,
                    name="archie-preview-vision",
                ).start()
            command_bridge = None
            if args.live_fused:
                if recorder is None:
                    raise SystemExit("--live-fused requires --capture-vision")
                token = args.external_token or secrets.token_hex(16)
                if len(token) < 16:
                    raise SystemExit("--external-token must contain at least 16 characters")
                command_bridge = BedrockBridge(Telemetry())
                command_bridge.start()
                fused_runtime = LiveFusedRuntime(
                    command_bridge,
                    recorder,
                    args.fused_checkpoint,
                    token,
                )
                print("Live fused policy waiting for Minecraft /connect localhost:19131")
                print(f"Then arm it with: /scriptevent archie:external_on {token}")
            print(f"Following live Preview telemetry: {directory}")
            print(f"Recording trajectory: {output}")
            if args.capture_vision:
                print(f"Recording bounded first-person frames: {args.vision_output}")
            while True:
                sleep(1)
    except KeyboardInterrupt:
        stop.set()
        if args.source == "live":
            content_bridge.stop()
            if command_bridge:
                command_bridge.stop()


if __name__ == "__main__":
    main()
