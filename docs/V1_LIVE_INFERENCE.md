# V1 live inference boundary

The next live milestone moves objective selection from Bedrock's exported privileged model to the trained Python Vision-Fused Policy V1 while leaving physical execution inside the verified placement controller.

## Per decision

1. Preview emits an episode identifier, monotonically increasing state revision, blueprint mask, built-state labels, and current physical state.
2. The desktop runtime synchronizes the newest first-person frame to that revision.
3. Vision-Fused Policy V1 produces objective logits.
4. Python applies the existing physical-validity mask.
5. A decision is returned with episode, revision, action, and model source.
6. Bedrock accepts it only if episode and revision still match, then hands it to the placement controller.

## Safety contract

- Stale and cross-episode decisions are rejected.
- Invalid, filled, unsupported, and out-of-blueprint cells are rejected.
- Timeout or unavailable vision falls back to Objective Selector V0 and records the fallback explicitly.
- The placement controller retains authority over approach, reach, use-item, verification, retry, reposition, and abort.
- External inference cannot directly write structure blocks.

`archie.live_policy.DecisionGate` implements and tests the host-side contract. The Preview pack now implements the matching authenticated revision/validity gate, and `archie.live_fused_runtime.LiveFusedRuntime` synchronizes a captured frame before returning a decision over the bidirectional `/connect` channel. Missing or stale frames deliberately produce no response so Bedrock's bounded fallback owns recovery.

## Preview test sequence

Start `archie-neural-graph` with `--capture-vision --live-fused`. It prints a random session token. In fullscreen Preview:

1. `/connect localhost:19131`
2. `/scriptevent archie:external_on <printed-token>`
3. `/scriptevent archie:vision_on`
4. `/scriptevent archie:start`

Telemetry distinguishes requested, applied, rejected, and fallback decisions. Obsidian displays the actual policy source and labels a divergence from the privileged proposal as a vision-changed objective rather than a mismatch.
