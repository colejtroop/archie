from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from .bedrock_bridge import BedrockBridge
from .blueprint import wall
from .construction_strategy import BuildSite, choose_strategy
from .mcstructure import blueprint_payload, load_mcstructure
from .telemetry import Telemetry


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a Bedrock .mcstructure into Archie's live Preview body")
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--fixture-wall", metavar="WIDTHxHEIGHT")
    parser.add_argument("--port", type=int, default=19131)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="keep the WebSocket host connected after transferring the blueprint",
    )
    parser.add_argument("--existing-support", choices=("north", "east", "south", "west"), action="append", default=[])
    parser.add_argument("--scaffold-budget", type=int, default=64)
    args = parser.parse_args()

    if bool(args.path) == bool(args.fixture_wall):
        parser.error("provide exactly one mcstructure path or --fixture-wall WIDTHxHEIGHT")
    if args.fixture_wall:
        try:
            width, height = (int(value) for value in args.fixture_wall.lower().split("x", 1))
        except ValueError:
            parser.error("--fixture-wall must look like 3x9")
        blueprint = wall(width, height, "minecraft:cobblestone")
    else:
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
        if args.keep_alive:
            print("Archie host will remain connected until Minecraft disconnects or this process is stopped.")
            while bridge.connected:
                sleep(0.25)
        else:
            sleep(2)
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
