# Project state

## Current milestone

V0 first-block candidate; core loop is tested and the physical Bedrock pack is ready for its first in-game run.

## What works

- Relative blueprint and block-state representation
- Deterministic embodied simulator builds and verifies a 3×3 wall
- Placement retries, comparison, metrics, structured JSONL telemetry
- Optional survival fields from the first agent-state schema
- Sampled/bounded vision records with synchronized privileged labels
- Obsidian dashboard, including ARCHIE VISION and explicit no-model/no-frame states
- Six focused tests pass on a portable Python 3.13.7 runtime; the 3×3 demo reports exact completion (9/9 blocks)
- Packageable Preview behavior pack spawns a `SimulatedPlayer`, navigates, places via inventory interaction, observes the result, and emits structured chat telemetry

## Decisions

- Keep Python core independent of Bedrock details through `Environment`.
- Use Bedrock GameTest `SimulatedPlayer` for the first live body: navigation and item-on-block APIs produce physical actions; reset/fixtures may use direct world editing.
- Pin experimental module versions to Preview `1.26.60-preview.25`; beta modules must match the installed Preview build.
- Treat privileged state as V0/V1 ground truth and labels, never as the permanent perception contract.
- Store no raw frames by default. Recording must be enabled, sampled, and capped.

## Commands

```powershell
python -m unittest discover -s tests -v
python -m archie.demo --obsidian
```

## Blockers

- No installed Python runtime detected. Validation currently uses a temporary portable Python 3.13.7 runtime.
- Minecraft Bedrock/Preview and BDS were not detected, so the prepared pack cannot be run or visually verified locally yet.
- `@minecraft/server-gametest` is currently experimental/pre-release and may require Preview or a compatible BDS build.

## Immediate next step

Import `dist/Archie-V0.mcpack` into a compatible Minecraft Preview test world, run `/scriptevent archie:start`, and capture the resulting Archie chat telemetry.
