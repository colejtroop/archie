# Archie

> Embodied Minecraft Bedrock construction research project. **Obsidian** is Archie's live perception, debugging, and model-telemetry interface.

## Navigation

- [[Project Overview]]
- [[Project State]]

## Current milestone

V0 foundation: the deterministic construction loop is implemented and tested. Live Minecraft Bedrock execution is not connected yet.

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
- Live browser-based Obsidian dashboard

## Honest runtime state

- **Learned model:** not active
- **Live Minecraft frame source:** not connected
- **Bedrock body:** planned around experimental GameTest `SimulatedPlayer`

## Immediate next step

Implement and install the smallest Bedrock behavior pack that navigates a simulated player, places one physical block with an inventory action, observes the resulting block type, and reports verification to Archie.

