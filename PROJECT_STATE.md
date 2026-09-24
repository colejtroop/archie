# Project state

## Current milestone

Construction Strategy V1 ranks physically meaningful access plans before a spatial build: ground, jump, existing vertical support, or temporary scaffold. The selected method is now part of the validated Preview contract, structured telemetry, and Obsidian brain trace. The next controller milestone must physically place, climb, and remove any selected scaffold rather than granting elevated reach.

## What works

- Relative blueprint and block-state representation
- Deterministic embodied simulator builds and verifies a 3×3 wall
- Placement retries, comparison, metrics, structured JSONL telemetry
- Optional survival fields from the first agent-state schema
- Sampled/bounded vision records with synchronized privileged labels
- Native Obsidian brain graph accurately distinguishes the active privileged objective selector from the offline visual model and traces the live placement-controller branch sequence
- Twenty-two focused tests pass on a portable Python runtime; the simulator and live Preview wall runs report exact completion (9/9 blocks)
- Packageable Preview behavior pack spawns a `SimulatedPlayer`, navigates, places via inventory interaction, observes the result, and emits structured chat telemetry
- Live Preview run completed with `BLOCK_PLACEMENT_SUCCEEDED` and `EPISODE_COMPLETED` (`exact_completion: true`, one correct block, zero missing blocks)
- Live Preview multi-block run physically built and verified a complete 3×3 stone wall through nine player-driven placements
- Headless content-log collector converts structured Bedrock events into crash-safe, sequenced JSONL expert trajectories
- PyTorch Objective Selector V0 inherits deterministic expert target selection across 15,024 valid wall states; held-out accuracy is 99.63% raw and 100% with physical-validity masking
- Objective Selector V0 weights export to Bedrock JavaScript; live Preview inference selected policy actions `0, 1, 2, 5, 6, 7, 10, 11, 12` and completed all nine physical placements with zero failures or retries
- The verified neural Preview episode is recoverable from the content log as a 58-event JSONL trajectory
- Live Preview content-log telemetry now drives the simplified Obsidian brain graph while recording the same episode
- An opt-in Preview camera mirror and bounded Windows frame sampler are ready for first-person capture; camera control remains off by default and clears at episode end
- Visual Encoder V0 prerequisites are implemented: labeled-frame dataset loading, a 69,965-parameter CNN with a 128-dimensional embedding, progress/action/placement heads, masked multi-task loss, and checkpoint training
- A first 20-frame clean subset completed end-to-end visual smoke training (loss 4.064 → 1.622); this validates the pipeline only, not visual generalization
- Visual training now crops the Preview debug strip and holds out entire episodes rather than leaking temporally adjacent frames across the split
- Vision-fused Policy V1 initializes with exactly the proven privileged logits while retaining a live gradient into its gated visual residual
- The physical test fixture is offset from the observer and Archie approaches from the working side, preventing the human avatar from blocking its spawn path
- Desktop capture is explicitly run with interactive-session access; failures now report why frames are being skipped instead of silently producing an empty dataset
- Three clean Preview episodes produced 107 retained frames across night, clear daylight, and rain; the rainy episode was held out in full
- Vision-Fused Policy V1 retained 100% validity-masked accuracy on 38 held-out actions; real pixels changed logits by 0.329 on average while zero-image ablation left decisions unchanged
- A live placement controller now branches beneath each selected objective: approach, place, verify, advance, reposition, retry, or bounded abort. These decisions are emitted as telemetry and visualized in Obsidian.
- Preview verification: the controller detected an initial 5.00-block stand-point gap, selected REPOSITION, entered reach, and then completed the 3×3 wall 9/9 with zero placement failures or retries.
- The live V1 bridge is implemented end to end: desktop frame/state synchronization, fused inference, bidirectional `/connect` command transport, token authentication, Bedrock episode/revision validation, validity masking, and bounded fallback telemetry.
- Blueprint input accepts a named, block-typed, bottom-to-top binary pattern up to 5×5 and rejects malformed, empty, oversized, or unsupported structures before a build begins.
- Bedrock `.mcstructure` import decodes the native little-endian NBT format without third-party dependencies and transfers a validated compact 3D plan over the local `/connect` bridge. Spatial builds use a separate deterministic back-to-front planner until the neural action space grows beyond its planar 25 cells.
- The physical controller polls navigation readiness every two ticks and placement success every tick, preserving bounded recovery while removing 2.5 seconds of unconditional waiting per block.
- Compact spatial builds reuse a central angled construction vantage, and item use waits two ticks for the simulated player's aim to settle; this targets both excess walking and the first-attempt failures observed in the initial 25/27 cube run.
- The first shared-vantage test exposed that the planar 2.25-block arrival radius allowed placement while Archie still occupied a target cell; spatial arrival is now isolated at a strict 1.0-block radius before aiming.
- Spatial target order now forms explicit placement rays: floor-by-floor, lateral lane-by-lane, and far-to-near, reducing camera rotation between successive clicks.
- The first placement-ray test showed the one-block front vantage could overlap the next target and that five-tick successive uses were rejected. The corrected controller stands two blocks clear and targets a reliable ten-tick click cadence.
- V0.4.4 physically completed the imported 3×3×3 cobblestone structure exactly: 27/27 blocks, zero failed placements, and zero retries. Its 66.2-second runtime was dominated by 20 unnecessary arrival repositions at 1.02 blocks; the safe cleared-vantage tolerance is now 1.25 blocks.
- Obsidian's native brain graph now maintains exactly one bright `brain-current` node and advances it through spatial input, selected cell, placement-controller branch, verified state, and completion as live Minecraft telemetry arrives.
- V0.4.6 physically verified three post-layer inspection events with a 27/27 build in 35.9 seconds, but captured frames showed the human avatar obstructing the straight-on viewpoint. Inspection now uses a diagonal offset and emits explicit `INSPECT_LAYER_n` frame labels.
- Compact Obsidian nodes use filesystem-safe names and replace superseded targets, progress, and inspection states instead of accumulating full episode history in Graph View.
- Construction Strategy V1 exposes a stable neural-training feature vector and ranks orientation/access candidates by movement, camera turns, scaffold material, and trapping risk. Tests verify that existing vertical support beats scaffolding and that a free-standing 9×9 wall requires scaffolding.
- Structure loading now transmits the selected strategy to Preview, which validates it and emits `STRATEGY_SELECTED`; Obsidian displays the active ground, jump, wall, or scaffold choice.
- Fused-policy training and evaluation accept controlled built-state dropout/ablation so dependence on privileged progress inputs can be measured rather than assumed.
- First live fused run: 10/10 V1 decisions applied (nine placements plus complete), zero fallbacks/rejections, average decision latency ~0.33 s, maximum ~0.65 s, and exact 9/9 physical completion with zero placement failures or retries.

## Decisions

- Keep Python core independent of Bedrock details through `Environment`.
- Use Bedrock GameTest `SimulatedPlayer` for the first live body: navigation and item-on-block APIs produce physical actions; reset/fixtures may use direct world editing.
- Use the beta channel versions reported by the running Preview manifest loader (`2.12.0-beta` and `1.0.0-beta`). Fully qualified `.28` package versions are rejected in the pack manifest.
- Treat privileged state as V0/V1 ground truth and labels, never as the permanent perception contract.
- Store no raw frames by default. Recording must be enabled, sampled, and capped.
- Keep learned scope explicit: Objective Selector V0 chooses the next supported blueprint cell; it does not yet control navigation, placement, or visual perception.
- Freeze the verified privileged selector during initial fusion; vision contributes through a gated residual that is exactly zero at initialization.
- Keep high-level objective selection separate from low-level placement control so navigation and recovery can grow without retraining blueprint planning.

## Commands

```powershell
python -m unittest discover -s tests -v
archie-neural-graph --vault "C:\path\to\your\ObsidianVault"
```

## Constraints

- Validation currently uses a temporary portable Python 3.13.7 runtime because no system Python is installed.
- `@minecraft/server-gametest` is currently experimental/pre-release and may require Preview or a compatible BDS build.

## Immediate next step

Implement a reach gate plus physical temporary-scaffold placement, climbing, and cleanup. Validate it on a structure whose upper layer cannot be reached from ground level, then use the resulting trajectories as expert labels for the learned strategy ranker.
