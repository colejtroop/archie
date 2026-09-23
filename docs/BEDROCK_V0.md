# Bedrock V0 physical placement

Archie's first live body uses the experimental Bedrock GameTest `SimulatedPlayer`. The pack performs real player navigation and inventory-based block placement. Direct block writes are used only to reset its support/air test fixture.

The first end-to-end physical placement was verified in Minecraft Preview on 2026-09-22. On 2026-09-23, the exported Objective Selector V0 neural network selected all nine targets for a complete physical 3×3 wall. The verified neural run completed 9/9 placements with no failures or retries.

The hierarchical placement controller was physically verified on 2026-09-23. It detected an initial 5.00-block stand-point gap, selected `REPOSITION`, moved into reach, and completed all nine placements with exact final verification.

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

### Blueprint input

The current learned policy accepts a named vertical pattern up to 5×5. `rows` are ordered bottom-to-top, use `1` for a block and `0` for empty space, and every upper block must be supported by a block in the row below it. Load a pattern before starting:

```text
/scriptevent archie:blueprint {"name":"stone-pyramid","block":"minecraft:stone","rows":["11111","01110","00100"]}
/scriptevent archie:start
```

Archie validates the name, block identifier, dimensions, cell values, non-empty structure, and support constraints before accepting it. The selected blueprint persists for the current world session. This V1 input is intentionally planar; native `.mcstructure` ingestion and arbitrary 3D planning are separate milestones.

Archie's repository-side editable blueprint convention is `.archie.json`. Minecraft Bedrock's native saved-structure suffix is `.mcstructure`. The host importer validates little-endian Bedrock NBT, its dimensions, palette indexes, and block data before sending a compact spatial plan to Preview:

```powershell
archie-load-structure "blueprints\cobblestone_3x3x3.mcstructure"
```

Then run `/connect localhost:19131` in Preview. When chat confirms the spatial blueprint loaded, run `/scriptevent archie:start`. Spatial inputs are currently bounded to 5×5×5, 64 blocks, nine palette entries, empty block-state maps, and vertically supported cells. Spatial target ordering is deterministic: floor-by-floor, lateral lane-by-lane, and far-to-near within each lane. The learned 25-action planar objective selector remains isolated until its action representation is generalized.

### Opt-in first-person capture

Archie's camera mirror is always off by default. To prepare a bounded, labeled capture run:

```powershell
archie-neural-graph --vault "C:\path\to\your\ObsidianVault" --capture-vision --vision-fps 2 --vision-max-frames 300
```

Put Minecraft Preview in fullscreen and keep it foreground for the entire run, then arm the camera and start the build. Capture pauses rather than saving contaminated frames whenever Preview is not foreground.

```text
/scriptevent archie:vision_on
/scriptevent archie:start
```

The camera follows Archie's simulated head, hides the HUD during capture, suppresses in-game progress messages to prevent label leakage, and automatically clears when the episode ends. Vision-armed builds pause for 12 seconds after spawn so transient command and join messages can fade before construction begins; non-vision builds start immediately. `/scriptevent archie:vision_off` always clears the issuing player's camera and restores the HUD, including after an episode. JPEG frames and synchronized privileged labels are written under `data/generated/vision/preview` and remain excluded from Git.

Expected behavior:

1. Chat reports a concise build-start summary; full structured events go to the Preview content log with the `[ArchieTelemetry]` prefix.
2. A player named **Archie** appears beside a test fixture offset from the observing player, keeping the human avatar out of its navigation path.
3. The pack loads the selected validated blueprint (a 3×3 stone wall by default) and runs Objective Selector V0 inference against the current built-state mask.
4. For each neural-policy target, Archie moves into reach, selects stone, and physically uses it on the supporting block.
5. A lower-level placement controller chooses approach, place, verify, reposition, retry, advance, or abort. Each placement is observed and recovery is bounded to three attempts.
6. The complete structure is checked against all nine targets.
7. Chat reports a concise `9/9 blocks verified` completion summary.

Movement and placement verification are readiness-driven. Archie checks every two ticks while navigating and every tick after placement, while retaining the original bounded timeouts and retry policy. This removes the former fixed 40-tick movement delay and 10-tick success delay without weakening failure detection.

For compact spatial structures up to three blocks wide, the placement controller reuses one central construction vantage two blocks clear of the front face. It completes each depth lane from far to near, minimizing view-angle changes between clicks instead of sweeping the entire back plane. Spatial arrival uses a 1.25-block radius at that cleared vantage so normal navigation jitter does not trigger reposition timeouts. An eight-tick aim/cooldown phase keeps successive clicks on Minecraft's reliable 10-tick item-use cadence. Wider structures currently use per-column vantages; learned viewpoint selection remains a later perception/control skill.

If it fails, retain the red `[Archie]` summary. Detailed structured diagnostics remain in the Preview content log.

For manifest/load troubleshooting, temporarily set the script module entry to `scripts/diagnostic.js`. A successful `/scriptevent archie:ping` returns `[Archie] DIAGNOSTIC_OK`.

