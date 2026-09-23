import unittest
from pathlib import Path

from archie.blueprint import BlockSpec, Position, wall
from archie.mcstructure import blueprint_payload, load_mcstructure
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

    def test_loads_user_cobblestone_mcstructure(self) -> None:
        path = Path("blueprints/cobblestone_3x3x3.mcstructure")
        if not path.exists():
            self.skipTest("local user blueprint is not present")
        blueprint = load_mcstructure(path)
        payload = blueprint_payload(blueprint)
        self.assertEqual(len(blueprint.blocks), 27)
        self.assertEqual({block.block_type for block in blueprint.blocks.values()}, {"minecraft:cobblestone"})
        self.assertEqual(len(payload["palette"]), 1)
        self.assertEqual(len(payload["cells"]), 27)


if __name__ == "__main__":
    unittest.main()

