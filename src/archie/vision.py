from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from time import time_ns
from typing import Any


@dataclass(frozen=True)
class FrameLabels:
    """Privileged state synchronized to a frame for supervision/debugging."""

    player: dict[str, Any]
    blueprint: dict[str, Any]
    world: dict[str, Any]
    survival: dict[str, Any]
    current_target: dict[str, Any] | None
    current_action: str | None
    placement_result: str | None


@dataclass(frozen=True)
class VisionFrame:
    sequence: int
    captured_at_ns: int
    media_type: str
    image: bytes
    labels: FrameLabels


@dataclass(frozen=True)
class RecordingPolicy:
    enabled: bool = False
    sample_every: int = 1
    max_frames: int = 1_000
    persist_images: bool = False

    def __post_init__(self) -> None:
        if self.sample_every < 1 or self.max_frames < 1:
            raise ValueError("sample_every and max_frames must be positive")


class VisionRecorder:
    """Keeps a bounded live frame and optionally writes sampled training records."""

    def __init__(self, policy: RecordingPolicy = RecordingPolicy(), output: Path = Path("data/generated/vision")) -> None:
        self.policy = policy
        self.output = output
        self.latest: VisionFrame | None = None
        self.recorded = 0
        self.received = 0
        self._lock = Lock()

    def receive(self, image: bytes, labels: FrameLabels, media_type: str = "image/jpeg") -> VisionFrame:
        if media_type not in {"image/jpeg", "image/png"}:
            raise ValueError("frames must be JPEG or PNG")
        with self._lock:
            self.received += 1
            frame = VisionFrame(self.received, time_ns(), media_type, image, labels)
            self.latest = frame
            should_record = (
                self.policy.enabled
                and self.received % self.policy.sample_every == 0
                and self.recorded < self.policy.max_frames
            )
            if should_record:
                self._persist(frame)
                self.recorded += 1
            return frame

    def _persist(self, frame: VisionFrame) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        stem = f"frame-{frame.sequence:08d}-{frame.captured_at_ns}"
        record = {
            "sequence": frame.sequence,
            "captured_at_ns": frame.captured_at_ns,
            "media_type": frame.media_type,
            "image": f"{stem}.{'jpg' if frame.media_type == 'image/jpeg' else 'png'}" if self.policy.persist_images else None,
            "labels": asdict(frame.labels),
        }
        with (self.output / "samples.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
        if self.policy.persist_images:
            (self.output / record["image"]).write_bytes(frame.image)

