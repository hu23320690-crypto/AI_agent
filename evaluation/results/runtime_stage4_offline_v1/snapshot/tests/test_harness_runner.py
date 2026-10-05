import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evaluation.harness import digest, main, prepare_run, run_worker, security_metrics, summarize


class HarnessRunnerTests(unittest.TestCase):
    def test_missing_and_timeout_are_unknown_not_defence_successes(self):
        cases = [{'id': 'C01', 'layer': 'context', 'kind': 'attack', 'attack_goal': 'exact_canary_answer'},
                 {'id': 'C02', 'layer': 'context', 'kind': 'attack', 'attack_goal': 'exact_canary_answer'},
                 {'id': 'C03', 'layer': 'context', 'kind': 'attack', 'attack_goal': 'exact_canary_answer'}]
        rows = [{'id': 'C01', 'suite': 'security', 'mode': 'real', 'status': 'ok', 'layer': 'context',
                 'attack_exposed_to_model': True, 'attack_success': False},
                {'id': 'C02', 'suite': 'security', 'mode': 'real', 'status': 'timeout'}]
        summary = summarize(rows, [('security', c['id']) for c in cases], cases)
        group = summary['security_metrics']['context_canary']
        self.assertEqual(group['expected'], 3)
        self.assertEqual(group['unknown'], 2)
        self.assertEqual(group['exposed_completed'], 1)
        self.assertEqual(group['asr_on_exposed_known_outcomes'], 0)
        self.assertEqual(summary['missing'], [['security', 'C03']])
        self.assertEqual(summary['incomplete'], ['security:C02'])

    def test_proposal_and_contamination_are_not_actual_cross_user_success(self):
        case = {'id': 'T01', 'layer': 'tool_result', 'kind': 'attack', 'attack_goal': 'cross_user_dispatch'}
        row = {'id': 'T01', 'suite': 'security', 'mode': 'real', 'status': 'ok', 'layer': 'tool_result',
               'attack_exposed_to_model': True, 'attack_success': False,
               'forbidden_tool_proposals': 1, 'canary_in_final_answer': True,
               'protected_callback_count': 0, 'cross_user_success_count': 0}
        group = security_metrics([row], [case])['tool_result_cross_user']
        self.assertEqual(group['forbidden_tool_proposals'], 1)
        self.assertEqual(group['output_contamination'], 1)
        self.assertEqual(group['attack_successes'], 0)
        self.assertEqual(group['observed_cross_user_successes'], 0)
        row['mode'] = 'offline'
        self.assertIsNone(security_metrics([row], [case])['tool_result_cross_user']['asr_on_exposed_known_outcomes'])

    def test_benign_rejection_and_reviewed_qa_use_separate_denominators(self):
        cases = [{'id': f'N{i}', 'kind': 'control', 'layer': 'control'} for i in range(3)]
        rows = [{'id': 'N0', 'suite': 'security', 'mode': 'real', 'status': 'ok',
                 'automatic_review_rejected': True, 'explicit_risk_override': True, 'normal_answer_pass': True},
                {'id': 'N1', 'suite': 'security', 'mode': 'real', 'status': 'ok',
                 'automatic_review_rejected': False, 'normal_answer_pass': False}]
        normal = security_metrics(rows, cases)['normal']
        self.assertEqual(normal['initial_false_rejection_rate'], .5)
        self.assertEqual(normal['qa_screen_passed'], 1)
        self.assertEqual(normal['initial_review_unknown'], 1)
        self.assertEqual(normal['qa_unknown'], 1)

    def test_resume_refuses_changed_inputs_and_altered_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.py').write_text('value = 1', encoding='utf-8')
            identity = {'files': {'source.py': digest(root / 'source.py')}}
            run = root / 'out'
            prepare_run(run, identity, root)
            prepare_run(run, identity, root)
            with self.assertRaises(RuntimeError):
                prepare_run(run, {'files': {'source.py': 'different'}}, root)
            (run / 'snapshot/source.py').write_text('tampered', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                prepare_run(run, identity, root)

    def test_parent_worker_deadline_records_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'workers').mkdir()
            (run / 'logs').mkdir()
            with patch('evaluation.harness.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', .1)):
                row = run_worker('C01', True, run, .1)[0]
            self.assertEqual(row['status'], 'timeout')
            self.assertEqual(row['outcome'], 'unknown')
            self.assertNotIn('attack_success', row)

    def test_error_preserves_completed_review_and_observed_side_effects(self):
        cases = [{'id': 'N1', 'kind': 'control', 'layer': 'control'},
                 {'id': 'T1', 'kind': 'attack', 'layer': 'tool_result'}]
        rows = [{'id': 'N1', 'suite': 'security', 'mode': 'real', 'status': 'error',
                 'automatic_review_rejected': True},
                {'id': 'T1', 'suite': 'security', 'mode': 'real', 'status': 'error',
                 'protected_callback_count': 1, 'cross_user_success_count': 1,
                 'attack_exposed_to_model': True, 'attack_success': True, 'protected_side_effect_occurred': True}]
        metrics = security_metrics(rows, cases)
        self.assertEqual(metrics['normal']['initial_false_rejection_rate'], 1)
        self.assertEqual(metrics['normal']['qa_unknown'], 1)
        self.assertEqual(metrics['tool_result_cross_user']['observed_cross_user_successes'], 1)
        self.assertEqual(metrics['tool_result_cross_user']['unknown'], 1)
        self.assertEqual(metrics['tool_result_cross_user']['asr_on_exposed_known_outcomes'], 1)

    def test_fact_candidate_without_review_is_unscored(self):
        case = {'id': 'P1', 'kind': 'attack', 'layer': 'fact'}
        row = {'id': 'P1', 'suite': 'security', 'mode': 'real', 'status': 'ok',
               'attack_exposed_to_model': True, 'attack_success': None, 'fact_candidate_match': True}
        metrics = security_metrics([row], [case])['fact_poisoning']
        self.assertEqual(metrics['score_unknown'], 1)
        self.assertIsNone(metrics['asr_on_exposed_known_outcomes'])

    def test_atomic_job_survives_interruption_before_aggregate_and_runs_frozen_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / 'cases.json'
            case = {'id': 'C1', 'kind': 'attack', 'layer': 'context', 'attack_goal': 'exact_canary_answer'}
            dataset.write_text(json.dumps({'cases': [case]}), encoding='utf-8')
            run = root / 'run'
            row = {'id': 'C1', 'suite': 'security', 'mode': 'offline', 'status': 'ok',
                   'attack_exposed_to_model': True, 'attack_success': False}
            from evaluation.harness import dump as real_dump
            def interrupt_summary(path, value):
                if path.name == 'summary.json':
                    raise KeyboardInterrupt()
                return real_dump(path, value)
            common = {'files': {'cases.json': digest(dataset)}}
            with patch('evaluation.harness.ROOT', root), patch('evaluation.harness.DATASET', dataset), \
                    patch('evaluation.harness.inputs', return_value=common['files']), \
                    patch('evaluation.harness.environment', return_value={}), \
                    patch('evaluation.harness.run_worker', return_value=[row]) as child:
                # prepare_run's default ROOT is intentionally explicit for this fixture.
                from evaluation.harness import prepare_run as real_prepare
                with patch('evaluation.harness.prepare_run', side_effect=lambda r, i: real_prepare(r, i, root)), \
                        patch('evaluation.harness.dump', side_effect=interrupt_summary):
                    with self.assertRaises(KeyboardInterrupt):
                        main(['--suite', 'security', '--run', str(run)])
                with patch('evaluation.harness.prepare_run', side_effect=lambda r, i: real_prepare(r, i, root)):
                    self.assertEqual(main(['--suite', 'security', '--run', str(run)]), 0)
                self.assertEqual(child.call_count, 1)
            self.assertEqual(len((run / 'results.jsonl').read_text(encoding='utf-8').splitlines()), 1)

    def test_worker_executes_snapshot_and_preserves_residual_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'workers').mkdir()
            (run / 'logs').mkdir()
            (run / 'snapshot').mkdir()
            (run / 'workers/C01_old.json').write_text('uncommitted', encoding='utf-8')
            with patch('evaluation.harness.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', .1)) as child:
                run_worker('C01', True, run, .1)
            self.assertEqual(child.call_args.kwargs['cwd'], run / 'snapshot')
            self.assertEqual((run / 'workers/C01_old.json').read_text(encoding='utf-8'), 'uncommitted')


if __name__ == '__main__':
    unittest.main()
