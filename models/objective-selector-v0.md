# Objective Selector V0

Archie's first learned component selects the next physically supported target cell in a wall blueprint.

## Contract

- Input: 5×5 blueprint mask plus 5×5 privileged built-state mask
- Output: logits for 25 target cells plus a complete action
- Architecture: multilayer perceptron, 50 → 128 → 64 → 26
- Supervision: deterministic expert target choices across structurally valid walls from 1×1 through 5×5
- Safety: inference masks cells that are outside the blueprint, already filled, or unsupported
- Vision: not yet included
- Control scope: objective selection only; navigation, placement, observation, retry, and verification remain deterministic

## Training result

- Expert states: 15,024
- Training samples: 12,019
- Held-out samples: 3,005
- Raw held-out accuracy: 99.63%
- Validity-masked held-out accuracy: 100%
- Seed: 7
- Epochs: 300

The checkpoint is generated at `checkpoints/objective-selector-v0.pt` and intentionally excluded from Git. This model is a narrow behavioral-cloning milestone, not an end-to-end Minecraft or visual policy.
