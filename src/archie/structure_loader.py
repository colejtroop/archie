from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from .bedrock_bridge import BedrockBridge
from .construction_strategy import BuildSite, choose_strategy
from .mcstructure import blueprint_payload, load_mcstructure
from .telemetry import Telemetry


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a Bedrock .mcstructure into Archie's live Preview body")
    parser.add_argument("path", type=Path)
    parser.add_argument("--port", type=int, default=19131)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--existing-support", choices=("north", "east", "south", "west"), action="append", default=[])
    parser.add_argument("--scaffold-budget", type=int, default=64)
    args = parser.parse_args()

    blueprint = load_mcstructure(args.path)
    payload = blueprint_payload(blueprint)
    positions = tuple(blueprint.blocks)
    strategy = choose_strategy(BuildSite(
        width=max(position.x for position in positions) + 1,
        height=max(position.y for position in positions) + 1,
        depth=max(position.z for position in positions) + 1,
        block_count=len(positions),
        existing_vertical_support=frozenset(args.existing_support),
        scaffold_available=args.scaffold_budget,
    ))
    payload["strategy"] = {
        "approach": strategy.approach,
        "access": strategy.access.value,
        "rotations": strategy.rotations,
        "scaffold_blocks": strategy.scaffold_blocks,
        "estimated_steps": strategy.estimated_steps,
        "camera_turns": strategy.camera_turns,
        "trapped_risk": strategy.trapped_risk,
        "score": strategy.score,
    }
    bridge = BedrockBridge(Telemetry(), port=args.port)
    bridge.start()
    print(f"Validated {blueprint.name}: {len(blueprint.blocks)} blocks")
    print(f"Strategy: {strategy.access.value} from {strategy.approach}; {strategy.scaffold_blocks} temporary scaffold blocks")
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
