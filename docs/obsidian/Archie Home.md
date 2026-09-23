# Archie

> Embodied Minecraft Bedrock construction research project. **Obsidian** is Archie's live perception, debugging, and model-telemetry interface.

## Navigation

- [[Project Overview]]
- [[Project State]]

## Current milestone

V0 first-block candidate: the deterministic construction loop is tested, and a packageable Minecraft Preview behavior pack is ready for its first in-game run.

## Latest verified run

| Metric | Result |
|---|---:|
| Blueprint | 3×3 stone wall |
| Completion | 100% |
| Correct blocks | 9 |
| Missing blocks | 0 |
| Incorrect blocks | 0 |
| Extra blocks | 0 |
| Placement failures | 0 |
| Distance traveled | 12 blocks |
| Exact completion | Yes |

## Active systems

- Canonical relative voxel blueprints
- Move → select → place → observe → verify loop
- Retry and repair accounting
- Structured construction and survival telemetry
- Bounded first-person vision recording with privileged labels
- Live native Graph View of Archie's learned network and activations
- Bedrock Preview pack using a physical GameTest `SimulatedPlayer`

## Honest runtime state

- **Learned model:** not active
- **Live Minecraft frame source:** not connected
- **Bedrock body:** implemented around experimental GameTest `SimulatedPlayer`; in-game validation pending

## Immediate next step

Install a compatible Minecraft Preview build, import `Archie-V0.mcpack`, and run `/scriptevent archie:start` in an experimental flat test world.

