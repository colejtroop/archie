# Visual Encoder V0

Status: architecture, training pipeline, and first smoke-trained checkpoint implemented. More varied clean episodes are required before performance claims or policy fusion.

## Contract

- Input: RGB first-person frames resized to 160×90
- Encoder: three convolutional stages and a 128-dimensional embedding
- Supervised heads: structure progress, objective-selector action, and placement outcome
- Missing labels: ignored independently through masked multi-task losses
- Output checkpoint: `checkpoints/visual-encoder-v0.pt` (excluded from Git)

This encoder is intentionally small. Its first job is to prove that synchronized first-person pixels contain learnable construction state. It does not replace privileged state or control Archie yet. After dataset validation, its embedding will be fused with the existing blueprint and built-state policy inputs.

## First pipeline validation

- Retained clean frames: 20 from one fullscreen physical episode
- Available labels: 20 progress, 18 objective action, 1 placement outcome
- Progress range: 0.444–0.889
- Parameters: 69,965
- Smoke-training epochs: 20
- Training loss: 4.064 → 1.622
- Validation loss: 1.581 on four temporally adjacent frames

These values validate execution only. The sample is tiny, temporally correlated, and does not cover early progress, varied lighting/weather, failure cases, or enough placement outcomes for a meaningful generalization estimate.
