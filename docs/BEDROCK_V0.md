# Bedrock V0 physical placement

Archie's first live body uses the experimental Bedrock GameTest `SimulatedPlayer`. The pack performs real player navigation and inventory-based block placement. Direct block writes are used only to reset its tiny support/air test fixture.

## Requirements

- Minecraft Preview compatible with engine `1.26.60-preview.25`
- Beta APIs/experimental creator features enabled for the test world
- Cheats enabled and the testing player made an operator

The module is pre-release. Exact Preview versions matter: the manifest currently requests `@minecraft/server` `2.12.0-beta.1.26.60-preview.25` and `@minecraft/server-gametest` `1.0.0-beta.1.26.60-preview.25`.

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
3. Archie walks toward the target.
4. Archie selects stone and uses it on a support block.
5. The pack reads the target block after the action.
6. Chat reports `BLOCK_PLACEMENT_SUCCEEDED` and `EPISODE_COMPLETED` with `exact_completion: true`.

If it fails, retain the complete purple `[Archie]` chat message. Its structured payload identifies the failed stage and API error.

