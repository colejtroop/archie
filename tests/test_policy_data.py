import unittest

from archie.policy_data import COMPLETE_ACTION, cell_index, expert_action, generate_expert_samples
from archie.policy import valid_actions
from archie.policy_data import masks


class PolicyDataTests(unittest.TestCase):
    def test_expert_selects_lowest_supported_missing_cell(self) -> None:
        self.assertEqual(expert_action(3, 3, (1, 0, 2)), cell_index(1, 0))

    def test_expert_reports_complete(self) -> None:
        self.assertEqual(expert_action(3, 3, (3, 3, 3)), COMPLETE_ACTION)

    def test_dataset_contains_diverse_shapes_and_complete_states(self) -> None:
        samples = generate_expert_samples(states_per_shape=16)
        self.assertGreater(len({(sample.width, sample.height) for sample in samples}), 20)
        self.assertIn(COMPLETE_ACTION, {sample.target for sample in samples})

    def test_validity_mask_rejects_filled_and_unsupported_cells(self) -> None:
        blueprint, built = masks(3, 3, (1, 0, 2))
        self.assertEqual(valid_actions(tuple(blueprint + built)), [cell_index(1, 0), cell_index(0, 1), cell_index(2, 2)])
