import unittest

from archie.live_policy import DecisionGate, LivePolicyDecision, PolicySource
from archie.policy_data import masks


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


if __name__ == "__main__":
    unittest.main()
