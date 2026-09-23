from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from threading import Lock, Thread
from time import monotonic, sleep

from .bedrock_bridge import BedrockBridge
from .policy import valid_actions
from .telemetry import Event, EventType
from .vision import VisionRecorder
from .visual_model import create_fused_policy, image_tensor


class LiveFusedRuntime:
    """Synchronizes a real frame to a Bedrock state revision and returns one safe objective."""

    def __init__(
        self,
        bridge: BedrockBridge,
        recorder: VisionRecorder,
        checkpoint: Path,
        token: str,
        frame_timeout: float = 3.5,
    ) -> None:
        import torch

        self.torch = torch
        self.bridge = bridge
        self.recorder = recorder
        self.token = token
        self.frame_timeout = frame_timeout
        self.model = create_fused_policy()
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()
        self._lock = Lock()

    def consume(self, event: Event) -> None:
        if event.event_type is not EventType.POLICY_DECISION_REQUESTED:
            return
        Thread(target=self._answer, args=(dict(event.payload),), daemon=True, name="archie-fused-policy").start()

    def _matching_frame(self, episode: str, built: list[float]):
        expected = {index for index, value in enumerate(built) if value}
        deadline = monotonic() + self.frame_timeout
        while monotonic() < deadline:
            frame = self.recorder.latest_snapshot()
            if frame is not None:
                labels = frame.labels
                observed = set((labels.world or {}).get("built_actions") or [])
                if str((labels.world or {}).get("episode")) == episode and observed == expected:
                    return frame
            sleep(0.05)
        return None

    def _answer(self, payload: dict) -> None:
        from PIL import Image

        episode = str(payload.get("episode"))
        revision = payload.get("revision")
        blueprint = list(payload.get("blueprint") or [])
        built = list(payload.get("built") or [])
        if not isinstance(revision, int) or len(blueprint) != 25 or len(built) != 25:
            return
        frame = self._matching_frame(episode, built)
        if frame is None:
            return
        features = tuple(float(value) for value in blueprint + built)
        with self._lock, self.torch.no_grad():
            image = Image.open(BytesIO(frame.image))
            pixels = image_tensor(image).unsqueeze(0)
            state = self.torch.tensor([features], dtype=self.torch.float32)
            logits = self.model(pixels, state)["logits"][0]
            allowed = valid_actions(features)
            action = max(allowed, key=lambda candidate: float(logits[candidate]))
        message = json.dumps({
            "token": self.token,
            "episode": episode,
            "revision": revision,
            "action": action,
            "source": "vision-fused-policy-v1",
        }, separators=(",", ":"))
        try:
            self.bridge.send_script_event("archie:policy_action", message)
        except ConnectionError:
            # Bedrock's bounded timeout owns fallback behavior.
            return
