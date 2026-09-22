from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable


class EventType(str, Enum):
    EPISODE_STARTED = "EPISODE_STARTED"
    BLUEPRINT_LOADED = "BLUEPRINT_LOADED"
    STATE_UPDATED = "STATE_UPDATED"
    OBJECTIVE_SELECTED = "OBJECTIVE_SELECTED"
    MOVEMENT_STARTED = "MOVEMENT_STARTED"
    BLOCK_PLACEMENT_ATTEMPTED = "BLOCK_PLACEMENT_ATTEMPTED"
    BLOCK_PLACEMENT_SUCCEEDED = "BLOCK_PLACEMENT_SUCCEEDED"
    BLOCK_PLACEMENT_FAILED = "BLOCK_PLACEMENT_FAILED"
    FAULT_DETECTED = "FAULT_DETECTED"
    EPISODE_COMPLETED = "EPISODE_COMPLETED"


@dataclass(frozen=True)
class Event:
    event_type: EventType
    payload: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["event_type"] = self.event_type.value
        return value


class Telemetry:
    def __init__(self, sink: Callable[[Event], None] | None = None) -> None:
        self.events: list[Event] = []
        self._sink = sink
        self._lock = Lock()

    def publish(self, event_type: EventType, **payload: Any) -> Event:
        event = Event(event_type, payload, datetime.now(timezone.utc).isoformat())
        with self._lock:
            self.events.append(event)
        if self._sink:
            self._sink(event)
        return event

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(event.to_dict(), separators=(",", ":")) + "\n" for event in self.events),
            encoding="utf-8",
        )

