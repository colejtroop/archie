# Project state

## Current milestone

V0 foundation; core loop implemented and tested, live Bedrock execution not yet connected.

## What works

- Relative blueprint and block-state representation
- Deterministic embodied simulator builds and verifies a 3×3 wall
- Placement retries, comparison, metrics, structured JSONL telemetry
- Optional survival fields from the first agent-state schema
- Sampled/bounded vision records with synchronized privileged labels
- Obsidian dashboard, including ARCHIE VISION and explicit no-model/no-frame states
- Six focused tests pass on a portable Python 3.13.7 runtime; the 3×3 demo reports exact completion (9/9 blocks)

## Decisions

- Keep Python core independent of Bedrock details through `Environment`.
- Use Bedrock GameTest `SimulatedPlayer` for the first live body: navigation and item-on-block APIs produce physical actions; reset/fixtures may use direct world editing.
- Treat privileged state as V0/V1 ground truth and labels, never as the permanent perception contract.
- Store no raw frames by default. Recording must be enabled, sampled, and capped.

## Commands

```powershell
python -m unittest discover -s tests -v
python -m archie.demo --obsidian
```

## Blockers

- No installed Python runtime detected. Validation currently uses a temporary portable Python 3.13.7 runtime.
- Minecraft Bedrock/Preview and BDS were not detected, so no real placement or frame capture can be tested locally yet.
- `@minecraft/server-gametest` is currently experimental/pre-release and may require Preview or a compatible BDS build.

## Immediate next step

Install Python 3.11+, run the tests/demo, then implement and install the smallest Bedrock behavior pack that navigates a `SimulatedPlayer`, places one block with `useItemInSlotOnBlock`, and verifies the resulting block type.
