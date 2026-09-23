# Archie

Archie is a research platform for an embodied neural agent that physically constructs exact blueprints in Minecraft Bedrock. **Obsidian** is its live perception, debugging, and model-telemetry interface.

## Current status

### Working

- Canonical relative block-level blueprints, including block states
- Procedural lines/walls via the wall generator
- Deterministic move → select → place → observe → verify loop
- Retry handling, exact final verification, and structured telemetry
- Survival-ready agent state with optional health, hunger, threats, and time
- Bounded, configurable first-person frame records synchronized with privileged labels
- Obsidian live build, agent, event, vision, and honest no-model states
- Dependency-free simulation demo and focused unit tests
- Verified Minecraft Preview first-block run: Archie physically moved, placed stone, observed it, and reported exact completion

### Experimental

- A packageable Bedrock Preview behavior pack uses GameTest `SimulatedPlayer` for actual navigation, looking, inventory selection, placement, and observation. Its first physical placement was verified in Preview on 2026-09-22. See [`docs/BEDROCK_V0.md`](docs/BEDROCK_V0.md).

### Planned

- Bedrock-to-Python telemetry bridge
- Windows first-person frame capture connected to `VisionRecorder`
- Deterministic scaffolding and repair
- Expert trajectories and a PyTorch visual/construction policy

## Quick start

Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\archie-demo --obsidian
```

Open <http://127.0.0.1:8765>. The demo builds a verified 3×3 wall in the embodied simulator. It does not claim to be connected to Minecraft; Obsidian says `NO LIVE FRAME SOURCE CONNECTED` until real capture is attached.

Telemetry is written to `artifacts/v0-telemetry.jsonl` and excluded from Git.

## Architecture

`Blueprint` is translated to absolute target voxels. `DeterministicBuilder` chooses one target at a time, asks an `Environment` to move/select/place, observes the block, and verifies it. The environment boundary keeps Minecraft implementation details out of construction and future ML code.

Vision is a parallel observation stream. Each real JPEG/PNG frame can be synchronized with privileged player, blueprint, world, survival, target, action, and placement-result labels. Recording is sampled and bounded; privileged labels are training/debug ground truth, not a permanent policy dependency.

The intended live Bedrock implementation uses Microsoft's experimental GameTest `SimulatedPlayer`. This is Bedrock-native but currently requires preview/experimental support; the stable player API can observe input but cannot synthesize full player movement and item use.

## Roadmap

1. Stream the pack's structured events to the Python telemetry transport.
2. Stream Bedrock state and Windows first-person capture into Archie/Obsidian.
3. Complete the tiny-wall live demo, then add expert trajectory recording.
4. Train a PyTorch visual encoder fused with privileged state, progressively ablating privileged inputs.

