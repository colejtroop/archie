from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import sleep
from typing import Any

from .bedrock_bridge import BedrockBridge, ContentLogBridge, parse_archie_log_line
from .telemetry import Event, EventType, Telemetry


class TrajectoryWriter:
    """Incrementally stores live expert events as crash-safe JSONL records."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.episode = 0
        self.sequence = 0
        self._lock = Lock()

    def __call__(self, event: Event) -> None:
        with self._lock:
            if event.event_type is EventType.EPISODE_STARTED:
                self.episode += 1
                self.sequence = 0
            self.sequence += 1
            record: dict[str, Any] = {
                "schema_version": 1,
                "episode": self.episode,
                "sequence": self.sequence,
                **event.to_dict(),
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, separators=(",", ":")) + "\n")


def default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data/generated/trajectories") / f"bedrock-expert-{stamp}.jsonl"


def default_content_log_directory() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is unavailable; pass --content-log-directory")
    return Path(appdata) / "Minecraft Bedrock Preview" / "logs"


def latest_complete_episode(log_path: Path) -> list[tuple[EventType, dict[str, Any]]]:
    """Return the latest terminal Archie episode from an existing Preview log."""
    current: list[tuple[EventType, dict[str, Any]]] = []
    latest: list[tuple[EventType, dict[str, Any]]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = parse_archie_log_line(line)
        if not parsed:
            continue
        event_type, payload = parsed
        if event_type is EventType.EPISODE_STARTED:
            current = []
        if current or event_type is EventType.EPISODE_STARTED:
            current.append((event_type, payload))
        if event_type in (EventType.EPISODE_COMPLETED, EventType.EPISODE_FAILED) and current:
            latest = current
            current = []
    return latest


def import_episode(log_path: Path, output: Path) -> int:
    writer = TrajectoryWriter(output)
    telemetry = Telemetry(sink=writer)
    episode = latest_complete_episode(log_path)
    for event_type, payload in episode:
        telemetry.publish(event_type, **payload)
    return len(episode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect physical Bedrock expert trajectories")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--transport", choices=("log", "websocket"), default="log")
    parser.add_argument("--content-log-directory", type=Path, default=None)
    parser.add_argument("--port", type=int, default=19131)
    args = parser.parse_args()

    output = args.output or default_output()
    writer = TrajectoryWriter(output)
    telemetry = Telemetry(sink=writer)
    if args.transport == "websocket":
        bridge = BedrockBridge(telemetry, port=args.port)
        connection_instruction = f"Minecraft command: /connect ws://127.0.0.1:{args.port}"
    else:
        directory = args.content_log_directory or default_content_log_directory()
        bridge = ContentLogBridge(telemetry, directory)
        connection_instruction = f"Watching Preview content logs: {directory}"
    bridge.start()
    print(f"Trajectory output: {output}")
    print(connection_instruction)
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
        print(f"Captured {len(telemetry.snapshot())} events across {writer.episode} episode(s).")


if __name__ == "__main__":
    main()
