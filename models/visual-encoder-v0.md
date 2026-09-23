# Visual Encoder V0

Status: trained on three clean physical Preview episodes and consumed by Vision-Fused Policy V1. Broader data is still required before generalization claims.

## Contract

- Input: RGB first-person frames with the top 9% Preview debug strip removed, then resized to 160×90
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

Production training requires at least two labeled episodes and holds out complete episodes. The single-episode path is available only through the explicitly named `--allow-single-episode-smoke` flag.

## Three-episode training run

- Clean retained frames: 107 (night, clear daylight, and rain)
- Training episodes: 2
- Held-out episodes: 1 (rain)
- Training loss: 3.917 → 2.206 over 20 epochs
- Held-out loss: 2.320 on 43 frames

This is enough to validate the episode-split and fusion pipeline. It is not enough to claim robust visual perception across worlds, structures, viewpoints, or failure modes.
