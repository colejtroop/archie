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
- Native Obsidian brain graph with color-coded live objective selection, honest privileged-state features, and sequential placement-controller branches
- Dependency-free simulation demo and focused unit tests
- Verified Minecraft Preview first-block run: Archie physically moved, placed stone, observed it, and reported exact completion
- Verified Minecraft Preview 3×3 wall run: nine physical placements with per-block observation, retries, progress, and final structure verification
- Headless expert-trajectory collection from Preview content logs, with concise in-game messages
- PyTorch Objective Selector V0 trained by behavioral cloning across 15,024 valid wall states; 100% validity-masked held-out accuracy
- Live Preview telemetry can drive the Obsidian brain graph and simultaneously record a crash-safe training trajectory
- Visual Encoder V0 training pipeline: compact CNN, 128-dimensional embedding, and masked progress/action/placement supervision
- Vision-fused V1 policy scaffold: the proven privileged selector is frozen as a safe base while a gated visual residual learns from episode-held-out data
- First trained fused checkpoint: 100% masked accuracy on 38 actions from an entirely held-out rainy episode, with measurable image-conditioned logit changes and no inherited-policy regression
- Hierarchical placement controller beneath the objective selector, branching through approach, place, verify, reposition, retry, advance, and abort

### Experimental

- A packageable Bedrock Preview behavior pack uses GameTest `SimulatedPlayer` for actual navigation, looking, inventory selection, placement, and observation. Its first physical placement was verified in Preview on 2026-09-22. See [`docs/BEDROCK_V0.md`](docs/BEDROCK_V0.md).

### Planned

- Multi-episode visual dataset covering varied lighting, weather, viewpoints, and placement failures
- Deterministic scaffolding and repair
- Expert trajectories and a PyTorch visual/construction policy

## Quick start

Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\archie-neural-graph --vault "C:\path\to\your\ObsidianVault"
```

Open Obsidian's native Graph View, then run the Archie command in Minecraft Preview. The graph follows Preview's content-log telemetry and records the episode under `data/generated/trajectories`. Pass `--source demo` to visualize the trained model without Minecraft.

Telemetry is written to `artifacts/v0-telemetry.jsonl` and excluded from Git.

## Architecture

`Blueprint` is translated to absolute target voxels. `DeterministicBuilder` chooses one target at a time, asks an `Environment` to move/select/place, observes the block, and verifies it. The environment boundary keeps Minecraft implementation details out of construction and future ML code.

Vision is a parallel observation stream. Each real JPEG/PNG frame is synchronized with privileged player, blueprint, world, survival, target, action, and placement-result labels. Recording is opt-in, sampled, and bounded; privileged labels are training/debug ground truth, not a permanent policy dependency. Training splits whole episodes so adjacent frames cannot leak into validation, and removes Preview's top debug strip before pixels reach the model.

The intended live Bedrock implementation uses Microsoft's experimental GameTest `SimulatedPlayer`. This is Bedrock-native but currently requires preview/experimental support; the stable player API can observe input but cannot synthesize full player movement and item use.

## Roadmap

1. Run the fused PyTorch policy in the live Preview control path and verify a physical build.
2. Measure controlled privileged-input corruption and ablation while preserving safety masks.
3. Add deterministic scaffolding and repair curricula.
4. Expand visual data across structures, viewpoints, mobs, failures, and worlds.

