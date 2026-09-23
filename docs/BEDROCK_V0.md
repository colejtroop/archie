# Bedrock V0 physical placement

Archie's first live body uses the experimental Bedrock GameTest `SimulatedPlayer`. The pack performs real player navigation and inventory-based block placement. Direct block writes are used only to reset its support/air test fixture.

The first end-to-end physical placement was verified in Minecraft Preview on 2026-09-22. The run emitted `EPISODE_STARTED`, state and movement events, `BLOCK_PLACEMENT_SUCCEEDED`, and `EPISODE_COMPLETED` with exact completion and no missing blocks.

## Requirements

- Minecraft Preview compatible with engine `1.26.60-preview.28`
- Beta APIs/experimental creator features enabled for the test world
- Cheats enabled and the testing player made an operator

The module is pre-release. The installed Preview runtime reports the accepted manifest versions as `@minecraft/server` `2.12.0-beta` and `@minecraft/server-gametest` `1.0.0-beta`.

## Package

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_bedrock_pack.ps1
```

This creates `dist/Archie-V0.mcpack`. Open that file with Minecraft Preview and activate **Archie V0 Physical Builder** on a flat test world.

## Run

Stand on open, flat ground and enter:

```text
/scriptevent archie:start
```

Expected behavior:

1. Chat reports `EPISODE_STARTED`.
2. A player named **Archie** appears three blocks away.
3. The pack loads a bottom-up 3×3 stone-wall plan.
4. For each target, Archie moves into reach, selects stone, and physically uses it on the supporting block.
5. Each placement is observed and retried up to three times when verification fails.
6. The complete structure is checked against all nine targets.
7. Chat reports `EPISODE_COMPLETED` with `exact_completion: true`, nine correct blocks, and zero missing blocks.

If it fails, retain the complete purple `[Archie]` chat message. Its structured payload identifies the failed stage and API error.

For manifest/load troubleshooting, temporarily set the script module entry to `scripts/diagnostic.js`. A successful `/scriptevent archie:ping` returns `[Archie] DIAGNOSTIC_OK`.

