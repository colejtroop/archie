import unittest

from archie.live_policy import DecisionGate, LivePolicyDecision, PolicySource
from archie.policy_data import masks
from archie.train_fused_policy import ablate_built_features


class DecisionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        blueprint, built = masks(3, 3, (0, 0, 0))
        self.features = tuple(blueprint + built)
        self.gate = DecisionGate()
        self.gate.begin("episode-a")

    def test_accepts_current_valid_decision(self) -> None:
        decision = LivePolicyDecision("episode-a", 0, 0, PolicySource.FUSED_V1)
        self.assertTrue(self.gate.accept(decision, self.features))

    def test_rejects_stale_or_cross_episode_decision(self) -> None:
        self.gate.advance()
        self.assertFalse(self.gate.accept(LivePolicyDecision("episode-a", 0, 0, PolicySource.FUSED_V1), self.features))
        self.assertFalse(self.gate.accept(LivePolicyDecision("episode-b", 1, 0, PolicySource.FUSED_V1), self.features))

    def test_rejects_physically_invalid_action(self) -> None:
        with self.assertRaises(ValueError):
            self.gate.accept(LivePolicyDecision("episode-a", 0, 10, PolicySource.FUSED_V1), self.features)

    def test_built_state_ablation_never_changes_blueprint(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is optional")
        blueprint, built = masks(3, 3, (1, 0, 0))
        features = torch.tensor([blueprint + built], dtype=torch.float32)
        ablated = ablate_built_features(features, 1.0)
        self.assertTrue(torch.equal(ablated[:, :25], features[:, :25]))
        self.assertEqual(float(ablated[:, 25:].sum()), 0.0)


if __name__ == "__main__":
    unittest.main()
