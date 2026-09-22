from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .blueprint import wall
from .builder import DeterministicBuilder
from .environment import SimulatedEnvironment
from .obsidian import serve
from .telemetry import Telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Archie's V0 embodied construction loop")
    parser.add_argument("--obsidian", action="store_true", help="serve Obsidian at http://127.0.0.1:8765")
    parser.add_argument("--step-delay", type=float, default=0.1)
    parser.add_argument("--telemetry", type=Path, default=Path("artifacts/v0-telemetry.jsonl"))
    args = parser.parse_args()

    telemetry = Telemetry(sink=lambda event: time.sleep(args.step_delay))
    server = serve(telemetry) if args.obsidian else None
    if server:
        print("Obsidian: http://127.0.0.1:8765")
    result = DeterministicBuilder(SimulatedEnvironment(), telemetry).build(wall())
    telemetry.write_jsonl(args.telemetry)
    print(json.dumps(asdict(result.metrics), indent=2))
    if server:
        print("Build complete; press Ctrl+C to stop Obsidian.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()
    return 0 if result.comparison.exact else 1


if __name__ == "__main__":
    raise SystemExit(main())

