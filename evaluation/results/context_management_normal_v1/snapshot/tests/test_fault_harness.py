"""The executable Harness must prove effects and emit reviewable records."""
import json
import unittest
from unittest.mock import patch

from evaluation.harness_faults import Scenario, run_faults


class FaultHarnessTests(unittest.TestCase):
    def test_all_integrated_fault_scenarios_and_normal_controls_pass(self):
        rows = run_faults()
        self.assertEqual([row['id'] for row in rows], [f'F{i:02d}' for i in range(1, 8)])
        for row in rows:
            with self.subTest(case=row['id']):
                self.assertEqual(row['status'], 'passed', json.dumps(row, ensure_ascii=False))
                self.assertGreaterEqual(len(row['assertions']), 7)
                self.assertTrue(all(item['passed'] for item in row['assertions']))
                self.assertGreater(row['counts'].get('model', 0), 0)
                self.assertGreaterEqual(len(row['trace']), 2)
                self.assertGreaterEqual(row['elapsed'], 0)
        json.dumps(rows, ensure_ascii=False)

    def test_exception_alone_is_not_a_pass(self):
        case = Scenario('fault', 'must fail')
        self.assertEqual(case.finish()['status'], 'failed')
        case.check('side_effect_missing', 0, 1)
        self.assertEqual(case.finish()['status'], 'failed')
        case.check('another_check_passed', True)
        self.assertEqual(case.finish()['status'], 'failed')

    def test_unexpected_error_fails_and_does_not_abort_remaining_scenarios(self):
        def broken(case):
            raise RuntimeError('private-error-marker')
        def normal(case):
            case.check('normal', True)
        with patch('evaluation.harness_faults.SCENARIOS', [
            ('broken', 'unexpected error', broken), ('normal', 'normal', normal),
        ]):
            rows = run_faults()
        self.assertEqual(rows[0]['status'], 'failed')
        self.assertEqual(rows[0]['error_type'], 'RuntimeError')
        self.assertEqual(rows[1]['status'], 'passed')
        self.assertNotIn('private-error-marker', json.dumps(rows))


if __name__ == '__main__':
    unittest.main()
