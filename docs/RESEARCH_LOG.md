# Archie Research Log

This is Archie's durable experimental record. It is structured so results can later support a research paper without relying on chat history. Claims are separated into **observations**, **interpretations**, and **unvalidated hypotheses**.

## Research objective

Archie studies whether an embodied Minecraft agent can learn to construct structures and survive using progressively less privileged world state and progressively more first-person visual perception. Privileged Bedrock state is allowed during early development as ground truth, supervision, and a safety/debugging signal; it is not the intended permanent perception interface.

## System under study

- Environment: Minecraft for Windows Preview, Bedrock Script API, and GameTest `SimulatedPlayer`
- Agent body: first-person simulated player using navigation, view direction, inventory interaction, jumping, and block breaking
- Current learned component: Objective Selector V0, a PyTorch policy trained by behavioral cloning over supported planar blueprint states
- Current deterministic components: spatial structure ordering, access-strategy ranking, and low-level physical control
- Visual-learning path: synchronized first-person frames plus privileged labels, compact visual encoder, then gated fusion with the proven privileged policy
- Neural visualization: live model/controller telemetry materialized as an Obsidian graph

## Measurement conventions

- Minecraft runs are identified by the telemetry `episode` field.
- Duration is computed from Bedrock ticks at 20 ticks per second.
- Exact completion requires every intended block, zero missing blocks, and successful temporary-access cleanup when applicable.
- A feature is called **validated** only after a live Preview run demonstrates the intended physical behavior. Unit tests establish regression safety, not embodied success.

## Experiment timeline

### V0.5.9 — live neural activation telemetry

**Question:** Can Obsidian display activations emitted by the actual in-game model rather than inferred or decorative activity?

**Change:** Added `MODEL_INFERENCE` telemetry containing compact H1/H2 activation summaries, valid actions, selected action, and selected logit.

**Observation:** Live planar runs illuminated real Objective Selector paths. Imported spatial structures remained labeled as deterministic and did not emit fabricated neural activations.

**Status:** Validated.

### V0.5.10 — visibility jump

**Question:** Can Archie recover when a top-row support face is occluded from a grounded eye position?

**Change:** After bounded re-aim failure, jump, aim during ascent, place near the apex, and verify through observed world state.

**Observation:** Archie successfully placed the first two top-row blocks while jumping. The next objective was selected while Archie was still airborne, and the broad arrival threshold incorrectly skipped lateral movement.

**Interpretation:** The jump primitive worked; the failure was controller sequencing and position gating.

**Status:** Partially validated, superseded by V0.5.11.

### V0.5.11 — post-jump landing and lane reacquisition

**Question:** Does waiting for a stable landing restore lateral movement after visibility jumps?

**Change:** Wait for feet to return to construction-ground height, emit `LAND`, then select the next objective. Tighten upper-row planar arrival radius from 2.25 to 0.8 blocks.

**Live result:** The 3×3 wall completed exactly, 9/9 blocks, with three successful visibility jumps and no failed placements.

**Status:** Validated.

### V0.6.0 — speed pass and dirt-pillar primitive

**Questions:**

1. Can controller latency be reduced without losing exact completion?
2. Can Archie gain elevation by looking down, jumping, placing dirt underfoot, and landing on it?

**Changes:** Reduced camera settle delay from eight ticks to three, aimed directly at the predicted top face, replaced scaffolding-block climbing with incremental dirt pillaring, and added top-down break/fall cleanup.

**Speed result:** The neural 3×3 wall completed exactly in 284 ticks (14.2 seconds), compared with approximately 374 ticks (18.7 seconds) in the preceding validated run: about 24% lower elapsed time. It still used 18 placement-controller attempts and 12 camera recoveries, so camera convergence remains the dominant avoidable overhead.

**Dirt result:** In the first tall 1×9 run, the initial `Jump → Place Dirt → Land` sequence succeeded on its first attempt. The following wall placement could not acquire the support face because the access column was three blocks laterally displaced.

**Interpretation:** Dirt pillaring itself was physically demonstrated. The subsequent failure was access geometry, not jump acceptance or underfoot placement.

**Status:** Speed pass validated; full pillar/build/descent episode not yet validated.

### V0.6.1 — central construction-lane pillar

**Hypothesis:** A dirt pillar placed in the proven central construction lane, two blocks in front of the wall, will make elevated support faces visible and reachable.

**Change:** Removed the three-block lateral offset while retaining incremental height and top-down cleanup.

**Expected test:** Tall 1×9 fixture completes ascent, elevated construction, and controlled descent with exact structure completion and zero remaining dirt.

**Status:** Packaged; awaiting live Preview validation.

## Current limitations and threats to validity

- The spatial blueprint planner is deterministic. Its decisions must not be described as learned neural reasoning.
- The learned Objective Selector chooses supported planar cells but does not yet own walking, aiming, jumping, recovery, or access-strategy selection.
- Bedrock world state currently verifies placement and supplies labels. This is privileged supervision and must be ablated as visual models mature.
- Current timing results are single-run engineering measurements, not statistically powered comparisons. Paper-quality claims require repeated trials, controlled fixtures, mean and dispersion, and failure-rate reporting.
- The first-person capture pipeline exists, but not every motor test records vision. Vision-off tests validate mechanics but cannot train the visual encoder.
- Repeating demonstrations does not automatically update model weights. A batch trainer, held-out evaluator, and checkpoint-promotion gate are required before tests constitute continual learning.

## Planned experimental program

1. Validate V0.6.1 ascent, construction, cleanup, and descent on the 1×9 fixture.
2. Record repeated motor episodes with randomized spawn offsets and target lanes.
3. Train a motor policy first by behavioral cloning from the reliable controller.
4. Introduce DAgger-style correction episodes where the learned policy acts and the controller labels corrections.
5. Evaluate candidate checkpoints on held-out geometry and lighting before promotion.
6. Add visual target/face estimation and measure performance while progressively ablating privileged target and completion inputs.
7. Add fall detection and ordinary recovery before attempting a water-bucket clutch curriculum.

## Paper-development checklist

- Preserve model and pack versions for every reported episode.
- Export raw telemetry and summarized metrics without committing large generated datasets.
- Record Minecraft Preview version, Script API versions, hardware, resolution, field of view, and capture settings.
- Predefine success criteria before large evaluation batches.
- Report failures and intervention counts, not only successful demonstrations.
- Separate simulator/unit-test evidence from live embodied evidence.
- Archive representative first-person frames and videos under bounded retention settings.

