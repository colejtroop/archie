# Vision-Fused Policy V1

Status: trained and evaluated offline on three physical Preview episodes; live fused-policy control remains the next integration step.

## Contract

- Visual input: Visual Encoder V0's 128-dimensional first-person embedding
- Privileged input: 25-cell blueprint mask plus 25-cell built-state mask
- Output: 26 objective logits (25 cells plus complete)
- Safety initialization: `privileged_logits + 0 × visual_residual`
- Initial privileged selector: frozen Objective Selector V0 checkpoint
- Training split: whole episodes, with at least two training episodes and one held-out episode

The residual layer starts non-zero while its scalar gate starts at zero. This makes initial live behavior bit-for-bit identical to the verified privileged selector and still gives the gate a usable gradient. Vision earns influence through training instead of changing Archie's behavior merely because it was connected.

## V1 acceptance gate

1. Collect at least three clean, armed fullscreen episodes under varied conditions.
2. Retrain Visual Encoder V0 with an episode-held-out split.
3. Train the fused residual while keeping the privileged selector frozen.
4. Confirm no regression on policy validity and physical 3×3 completion.
5. Compare held-out performance with vision enabled and ablated.

Until those checks pass, this is a V1-ready fusion path, not a validated V1 model.

## First trained checkpoint

- Training data: 64 frames from two episodes
- Held-out data: 43 rainy-episode frames, including 38 labeled policy actions
- Fused masked accuracy: 100%
- Frozen privileged masked accuracy: 100%
- Zero-image masked accuracy: 100%
- Mean absolute visual residual: 0.3901 logits
- Mean real-vs-zero-image change: 0.3288 logits
- Learned visual gate: -0.01938

The real image measurably affects logits without changing any validity-masked decision on this task. That is the desired safe first inheritance result: vision is connected and trainable, while the proven privileged policy is preserved. Because the 3×3 wall is already completely determined by privileged masks, these results do not show that vision is necessary. The next evaluation must deploy fused inference live and then remove or corrupt selected privileged inputs.
