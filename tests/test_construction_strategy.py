import unittest

from archie.construction_strategy import AccessMethod, BuildSite, choose_strategy, enumerate_strategies


class ConstructionStrategyTests(unittest.TestCase):
    def test_ground_strategy_is_enough_for_three_block_height(self) -> None:
        choice = choose_strategy(BuildSite(3, 3, 3, 27))
        self.assertEqual(choice.access, AccessMethod.GROUND)
        self.assertEqual(choice.scaffold_blocks, 0)

    def test_tall_free_standing_build_requires_scaffold(self) -> None:
        choice = choose_strategy(BuildSite(9, 9, 1, 81))
        self.assertEqual(choice.access, AccessMethod.SCAFFOLD)
        self.assertGreater(choice.scaffold_blocks, 0)

    def test_existing_wall_beats_scaffolding(self) -> None:
        choice = choose_strategy(
            BuildSite(9, 9, 1, 81, existing_vertical_support=frozenset({"east"}))
        )
        self.assertEqual(choice.approach, "east")
        self.assertEqual(choice.access, AccessMethod.EXISTING_SUPPORT)
        self.assertEqual(choice.scaffold_blocks, 0)

    def test_infeasible_scaffold_candidates_are_removed(self) -> None:
        candidates = enumerate_strategies(BuildSite(9, 9, 1, 81, scaffold_available=0))
        self.assertEqual(candidates, ())
        with self.assertRaisesRegex(ValueError, "no executable strategy"):
            choose_strategy(BuildSite(9, 9, 1, 81, scaffold_available=0))


if __name__ == "__main__":
    unittest.main()
