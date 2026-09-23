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

`archie.live_policy.DecisionGate` implements and tests the host-side half of this contract. The next implementation step is the authenticated localhost transport and matching Bedrock revision gate.
