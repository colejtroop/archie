import unittest

from archie.blueprint import BlockSpec, Position, wall
from archie.state import compare_build


class BlueprintTests(unittest.TestCase):
    def test_wall_uses_relative_coordinates(self) -> None:
        target = wall(3, 2).at_origin(Position(10, 4, -3))
        self.assertEqual(len(target), 6)
        self.assertIn(Position(12, 5, -3), target)

    def test_comparison_distinguishes_all_fault_types(self) -> None:
        stone = BlockSpec("minecraft:stone")
        dirt = BlockSpec("minecraft:dirt")
        target = {Position(0, 0, 0): stone, Position(1, 0, 0): stone, Position(2, 0, 0): stone}
        current = {Position(0, 0, 0): stone, Position(1, 0, 0): dirt, Position(9, 0, 0): dirt}
        result = compare_build(target, current)
        self.assertEqual(len(result.correct), 1)
        self.assertEqual(len(result.incorrect), 1)
        self.assertEqual(len(result.missing), 1)
        self.assertEqual(len(result.extra), 1)
        self.assertFalse(result.exact)


if __name__ == "__main__":
    unittest.main()

