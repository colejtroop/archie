from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from .bedrock_bridge import BedrockBridge
from .mcstructure import blueprint_payload, load_mcstructure
from .telemetry import Telemetry


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a Bedrock .mcstructure into Archie's live Preview body")
    parser.add_argument("path", type=Path)
    parser.add_argument("--port", type=int, default=19131)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    blueprint = load_mcstructure(args.path)
    payload = blueprint_payload(blueprint)
    bridge = BedrockBridge(Telemetry(), port=args.port)
    bridge.start()
    print(f"Validated {blueprint.name}: {len(blueprint.blocks)} blocks")
    print(f"In Minecraft Preview run: /connect localhost:{args.port}")
    deadline = monotonic() + args.timeout
    try:
        while not bridge.connected and monotonic() < deadline:
            sleep(0.1)
        if not bridge.connected:
            raise SystemExit("Minecraft did not connect before the timeout")
        message = json.dumps(payload, separators=(",", ":"))
        bridge.send_script_event("archie:structure", message)
        print("Spatial blueprint sent to Archie. Wait for the in-game loaded confirmation, then run /scriptevent archie:start")
        sleep(2)
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
