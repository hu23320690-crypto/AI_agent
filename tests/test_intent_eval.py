"""P2 scoring uses only fictional cases, CSV rows and injected script models."""
from dataclasses import replace
from datetime import date
import json
import io
import csv
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent.context_budget import ContextPolicy
from agent.intent import llm_parser
from agent.intent.resolve import TurnIntentResult
from agent.intent.schema import IntentProposal
from evaluation import intent_eval
from utils.report_intent import ReportIntent


CATALOG = ('星辉率', '晶片寿命', '幻尘消耗')


def gold(**changes):
    return {
        'fields': ['星辉率'], 'unknown_fields': [], 'limited': True,
        'full_report': False, 'target_month': '2032-11', 'compare': False,
        'comparison_month': None, 'knowledge_requested': False,
        'unresolved_month': False, 'requested_field_order': ['星辉率'],
        **changes,
    }


def case(**changes):
    return {
        'id': 'FICT001', 'split': 'dev', 'query': '2032年11月只列星辉率',
        'user_id': 'fictional-owner', 'today': '2033-03-14',
        'lookups': [{'month': '2032-11', 'phase': 'current'}],
        'history': [], 'previous_intent': None, 'gold': gold(), **changes,
    }


def proposal(**changes):
    return {
        'task_type': 'report',
        'fields': [{'mention': '星辉率', 'field': '星辉率'}],
        'scope': 'only_listed', 'target_month': '2032-11',
        'target_mention': '2032年11月', 'target_anchor': 'none',
        'compare': False, 'baseline_month': None, 'baseline_mention': '',
        'excluded_fields': [], 'knowledge_question': '', 'unresolved': False,
        **changes,
    }


class ScriptedModel:
    model = 'fictional-component-script'
    base_url = 'http://scripted.invalid'

    def __init__(self, *responses):
        self.responses = list(responses)
        self.seen = []

    def bind_tools(self, *_args, **_kwargs):
        raise AssertionError('Component evaluation must not bind tools')

    def invoke(self, messages):
        self.seen.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return AIMessage(content=json.dumps(response, ensure_ascii=False)
                         if isinstance(response, dict) else response)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden():
        raise AssertionError('Only explicitly injected script models are permitted')
    monkeypatch.setattr(llm_parser, 'intent_model', forbidden)
    monkeypatch.setattr(llm_parser, 'load_context_policy', lambda: ContextPolicy(
        window_tokens=16384, reserve_output_tokens=1024, reasoning_enabled=False))
    monkeypatch.delenv('AGENT_INTENT_MODE', raising=False)


def install_model(monkeypatch, *responses):
    model = ScriptedModel(*responses)
    monkeypatch.setattr(llm_parser, 'intent_model', lambda: model)
    return model


def records():
    return {
        ('fictional-owner', '2032-10'): {
            '效率': '星辉率:81%\\n幻尘消耗：2个/月', '耗材': '晶片寿命:23天'},
        ('fictional-owner', '2032-11'): {
            '效率': '星辉率：82%\\n幻尘消耗:1个/月', '耗材': '晶片寿命：22天'},
        ('fictional-owner', '2032-09'): {
            '效率': '未授权旧月率:73%', '耗材': '未授权旧月寿命:20天'},
        ('fictional-other', '2032-11'): {
            '效率': '其他用户率:64%', '耗材': '其他用户寿命:31天'},
    }


def write_fictional_csv(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=(
            '用户ID', '特征', '清洁效率', '耗材', '对比', '时间'))
        writer.writeheader()
        for (owner, month), value in records().items():
            writer.writerow({
                '用户ID': owner, '特征': '虚构舱室', '清洁效率': value['效率'],
                '耗材': value['耗材'], '对比': '虚构说明', '时间': month,
            })


def result(fields=('星辉率',), *, scope='only_listed', excluded=(), **changes):
    return TurnIntentResult(
        intent=ReportIntent(fields=fields, limited=scope == 'only_listed',
                            target_month='2032-11', **changes),
        knowledge_requested=False,
        trace={'mode': 'hybrid', 'source': 'llm', 'fallback_reason': None,
               'conflicts': [], 'latency_ms': 1},
        final_scope=scope, final_excluded_fields=excluded,
    )


def scored_row(identifier='FICT001', *, prediction=None, expected=None, status='ok',
               seconds=1.0, repeat=1, trace=None, calls=0):
    prediction = gold() if prediction is None else prediction
    expected = gold() if expected is None else expected
    return {
        'id': f'{identifier}-r{repeat}', 'case_id': identifier, 'repeat': repeat,
        'status': status, 'prediction': prediction,
        'score': intent_eval.score_case(prediction, expected, status=status),
        'trace': trace or {'source': 'llm', 'fallback_reason': None, 'conflicts': []},
        'wall_seconds': seconds, 'extra_model_calls': calls,
    }


def test_catalog_comes_only_from_authorized_owner_lookup_months():
    inputs = intent_eval.build_case_inputs(case(lookups=[
        {'month': '2032-10', 'phase': 'history'},
        {'month': '2032-11', 'phase': 'current'},
    ]), records())
    assert inputs['known_fields'] == ('星辉率', '幻尘消耗', '晶片寿命')
    assert inputs['fallback_month'] == '2032-11'
    assert inputs['today'] == date(2033, 3, 14)
    assert not any('未授权' in field or '其他用户' in field
                   for field in inputs['known_fields'])


def test_csv_loader_builds_catalog_from_cleaning_and_supply_sections_only(tmp_path):
    from utils.records import load_records
    csv_path = tmp_path / 'fictional.csv'
    write_fictional_csv(csv_path)
    inputs = intent_eval.build_case_inputs(case(), load_records(str(csv_path)))
    assert inputs['known_fields'] == ('星辉率', '幻尘消耗', '晶片寿命')
    assert '虚构舱室' not in inputs['known_fields']
    assert '虚构说明' not in inputs['known_fields']


def test_last_current_month_includes_not_found_and_history_is_not_an_anchor():
    inputs = intent_eval.build_case_inputs(case(lookups=[
        {'month': '2032-11', 'phase': 'current'},
        {'month': '2032-10', 'phase': 'history'},
        {'month': '2032-12', 'phase': 'current'},
    ]), records())
    assert inputs['fallback_month'] == '2032-12'
    assert inputs['known_fields'] == ('星辉率', '幻尘消耗', '晶片寿命')
    historical = intent_eval.build_case_inputs(case(lookups=[
        {'month': '2032-10', 'phase': 'history'}]), records())
    assert historical['fallback_month'] is None


def test_nonexistent_lookup_and_unknown_owner_generate_no_fields():
    inputs = intent_eval.build_case_inputs(case(user_id='fictional-missing'), records())
    assert inputs['known_fields'] == ()
    assert inputs['fallback_month'] == '2032-11'


def test_input_building_cannot_take_catalog_or_selectors_from_gold():
    class UnreadableGold(dict):
        def __getitem__(self, _key):
            raise AssertionError('Gold must not provide resolver inputs')

        def get(self, *_args, **_kwargs):
            raise AssertionError('Gold must not provide resolver inputs')

        def items(self):
            raise AssertionError('Gold must not provide resolver inputs')

    inputs = intent_eval.build_case_inputs(case(
        gold=UnreadableGold(), known_fields=['手写未授权字段'],
        field_catalog=['手写未授权字段'], fallback_month='2099-01'), records())
    assert inputs['known_fields'] == ('星辉率', '幻尘消耗', '晶片寿命')
    assert inputs['fallback_month'] == '2032-11'


def test_history_and_previous_intent_are_passed_as_case_inputs():
    previous = {
        'fields': ['晶片寿命'], 'target_month': '2032-10', 'limited': True,
        'comparison_month': None, 'compare': False, 'unresolved_month': False,
    }
    inputs = intent_eval.build_case_inputs(case(
        history=['2032年10月只列晶片寿命', '晶片寿命保持这个选择'],
        previous_intent=previous), records())
    assert tuple(inputs['history_queries']) == (
        '2032年10月只列晶片寿命', '晶片寿命保持这个选择')
    assert inputs['previous_intent'] == ReportIntent(
        fields=('晶片寿命',), target_month='2032-10', limited=True)


def test_adapter_splits_catalog_and_keeps_unknowns_in_original_order():
    output = intent_eval.adapt_result(result(
        ('晶片寿命', '每夜幻尘量', '星辉率', '晶片寿命', '每夜幻尘量')), CATALOG)
    assert output['fields'] == ['晶片寿命', '星辉率']
    assert output['unknown_fields'] == ['每夜幻尘量']
    assert output['requested_field_order'] == ['晶片寿命', '每夜幻尘量', '星辉率']
    assert output['limited'] is True
    assert output['full_report'] is False


def test_adapter_never_maps_unknowns_using_substrings_or_aliases():
    output = intent_eval.adapt_result(result(('墙角星辉率', '星辉率')), CATALOG)
    assert output['fields'] == ['星辉率']
    assert output['unknown_fields'] == ['墙角星辉率']
    assert output['requested_field_order'] == ['墙角星辉率', '星辉率']


def test_adapter_preserves_inconsistent_baseline_instead_of_silently_repairing_it():
    final = result(comparison_month='2032-10', compare=False)
    output = intent_eval.adapt_result(final, CATALOG)
    assert output['compare'] is False
    assert output['comparison_month'] == '2032-10'
    assert intent_eval.score_case(output, gold())['severity'] == 'dangerous'


@pytest.mark.parametrize('scope', ['only_listed', 'full_report', 'unspecified'])
def test_adapter_observes_final_scope_and_exclusions_instead_of_proposal(scope):
    proposal_diagnostic = IntentProposal.model_validate(proposal(
        scope='full_report' if scope != 'full_report' else 'only_listed',
        excluded_fields=['幻尘消耗']))
    retained = () if scope == 'unspecified' else ('星辉率', '晶片寿命')
    final = replace(result(retained, scope=scope,
                           excluded=('晶片寿命',)), proposal=proposal_diagnostic)
    output = intent_eval.adapt_result(final, CATALOG)
    assert output['full_report'] is (scope == 'full_report')
    assert output['limited'] is (scope == 'only_listed')
    assert output['excluded_fields'] == ['晶片寿命']
    if scope in {'full_report', 'unspecified'}:
        assert output['fields'] == output['unknown_fields'] == output['requested_field_order'] == []


def test_unspecified_final_scope_with_limited_intent_keeps_final_field_selection():
    final = result(('星辉率', '每夜幻尘量'), scope='unspecified')
    final = replace(final, intent=replace(final.intent, limited=True))
    output = intent_eval.adapt_result(final, CATALOG)
    assert output['limited'] is True
    assert output['full_report'] is False
    assert output['fields'] == ['星辉率']
    assert output['unknown_fields'] == ['每夜幻尘量']
    assert output['requested_field_order'] == ['星辉率', '每夜幻尘量']


def test_adapter_needs_no_gold_and_full_scope_empty_renderer_guard_is_not_a_limit():
    # Renderer guards may set limited when every catalog field is excluded;
    # the final semantic scope remains full_report.
    final = result((), scope='full_report', excluded=CATALOG)
    final = replace(final, intent=replace(final.intent, limited=True))
    output = intent_eval.adapt_result(final, CATALOG)
    assert output['limited'] is False
    assert output['full_report'] is True
    assert output['fields'] == output['unknown_fields'] == output['requested_field_order'] == []


def test_exact_score_checks_known_and_unknown_sets_and_mixed_order():
    expected = gold(fields=['星辉率', '晶片寿命'], unknown_fields=['每夜幻尘量'],
                    requested_field_order=['星辉率', '每夜幻尘量', '晶片寿命'])
    reordered_sets = {**expected, 'fields': ['晶片寿命', '星辉率']}
    assert intent_eval.score_case(reordered_sets, expected)['pass'] is True
    moved_unknown = {**expected,
                     'requested_field_order': ['星辉率', '晶片寿命', '每夜幻尘量']}
    score = intent_eval.score_case(moved_unknown, expected)
    assert score['pass'] is False
    assert score['slot_correct']['fields'] is True
    assert score['slot_correct']['unknown_fields'] is True
    assert score['slot_correct']['requested_field_order'] is False
    assert score['severity'] == 'other_error'


def test_case_unknown_aliases_apply_to_unknown_slot_and_same_order_position():
    expected = gold(fields=['星辉率'], unknown_fields=['每夜幻尘量'],
                    requested_field_order=['每夜幻尘量', '星辉率'])
    predicted = {**expected, 'unknown_fields': ['夜夜幻尘量'],
                 'requested_field_order': ['夜夜幻尘量', '星辉率']}
    assert intent_eval.score_case(predicted, expected,
                                  unknown_aliases=['夜夜幻尘量'])['pass'] is True
    assert intent_eval.score_case(predicted, expected)['pass'] is False
    displaced = {**predicted, 'requested_field_order': ['星辉率', '夜夜幻尘量']}
    assert intent_eval.score_case(displaced, expected,
                                  unknown_aliases=['夜夜幻尘量'])['pass'] is False


def test_unknown_aliases_never_authorize_known_field_aliases():
    predicted = gold(fields=['星光率'], requested_field_order=['星光率'])
    score = intent_eval.score_case(predicted, gold(), unknown_aliases=['星光率'])
    assert score['pass'] is False
    assert score['slot_correct']['fields'] is False


@pytest.mark.parametrize('slot,value', [
    ('limited', 1), ('full_report', 0), ('compare', 0),
    ('knowledge_requested', 0), ('unresolved_month', 0),
])
def test_score_does_not_accept_integer_boolean_slots(slot, value):
    score = intent_eval.score_case(gold(**{slot: value}), gold())
    assert score['pass'] is False
    assert slot in score['differences']


def test_month_null_and_empty_string_are_not_interchangeable():
    score = intent_eval.score_case(gold(target_month=''), gold(target_month=None))
    assert score['pass'] is False
    assert 'target_month' in score['differences']


@pytest.mark.parametrize('predicted, expected, severity', [
    (gold(fields=['晶片寿命'], limited=False, full_report=True,
          requested_field_order=['晶片寿命']), gold(), 'dangerous'),
    (gold(target_month='2032-12', limited=False, full_report=True), gold(), 'dangerous'),
    (gold(comparison_month='2032-12', compare=True), gold(), 'dangerous'),
    (gold(target_month='2032-11'), gold(target_month=None), 'dangerous'),
    (gold(fields=[], limited=False, full_report=True, requested_field_order=[]),
     gold(), 'wrong_scope'),
    (gold(fields=[], requested_field_order=[]), gold(), 'safe_fail'),
    (gold(fields=[], unknown_fields=['星辉率'], requested_field_order=['星辉率']),
     gold(), 'safe_fail'),
    (gold(target_month=None, unresolved_month=True), gold(), 'safe_fail'),
    (gold(knowledge_requested=True), gold(), 'other_error'),
    (gold(compare=True), gold(), 'other_error'),
])
def test_error_precedence(predicted, expected, severity):
    score = intent_eval.score_case(predicted, expected)
    assert score['pass'] is False
    assert score['severity'] == severity


def test_all_original_differences_survive_exclusive_dangerous_classification():
    predicted = gold(fields=['晶片寿命'], unknown_fields=['缺失提议项'],
                     limited=False, full_report=True, target_month='2032-12',
                     comparison_month='2032-10', compare=True,
                     knowledge_requested=True, unresolved_month=True,
                     requested_field_order=['缺失提议项', '晶片寿命'])
    score = intent_eval.score_case(predicted, gold())
    assert score['severity'] == 'dangerous'
    assert set(score['differences']) == {
        'fields', 'unknown_fields', 'limited', 'full_report', 'target_month',
        'comparison_month', 'compare', 'knowledge_requested',
        'unresolved_month', 'requested_field_order',
    }
    assert len(score['error_flags']) > 1


@pytest.mark.parametrize('status', ['error', 'timeout', 'structure_invalid', 'truncated'])
def test_failed_execution_never_passes_even_with_correct_fallback_prediction(status):
    score = intent_eval.score_case(gold(), gold(), status=status)
    assert score['execution_ok'] is False
    assert score['pass'] is False


def test_failure_with_no_prediction_remains_in_accuracy_and_slot_denominators():
    failed = scored_row('FICT002', status='error', seconds=None)
    failed['prediction'] = None
    failed['score'] = intent_eval.score_case(None, gold(), status='error')
    summary = intent_eval.summarize_results([scored_row(), failed], mode='hybrid', repeat=1, split='dev')
    aggregate = summary['aggregate']
    assert aggregate['planned_count'] == 2
    assert aggregate['exact_count'] == 1
    assert aggregate['exact_accuracy'] == .5
    assert all(value == .5 for value in aggregate['slot_accuracy'].values())
    assert aggregate['latency_seconds']['all']['missing_count'] == 1


def test_nearest_rank_latency_reports_all_states_and_only_successes():
    rows = [scored_row(f'FICT{index:03}', seconds=float(index),
                       status='ok' if index % 2 else 'timeout')
            for index in range(1, 11)]
    aggregate = intent_eval.summarize_results(rows)['aggregate']
    assert aggregate['planned_count'] == 10
    assert aggregate['exact_accuracy'] == .5
    assert aggregate['latency_seconds']['all'] == {
        'count': 10, 'missing_count': 0, 'p50': 5.0, 'p95': 10.0}
    assert aggregate['latency_seconds']['successful'] == {
        'count': 5, 'missing_count': 0, 'p50': 5.0, 'p95': 9.0}


def test_repeat_mean_and_worst_keep_full_repeats_instead_of_best_case_selection():
    rows = [scored_row('FICT001', repeat=1), scored_row('FICT002', repeat=1),
            scored_row('FICT001', repeat=2),
            scored_row('FICT002', repeat=2, prediction=gold(target_month='2032-12'))]
    summary = intent_eval.summarize_results(rows, mode='hybrid', repeat=2, split='dev')
    assert len(summary['repeats']) == 2
    assert summary['repeat_metrics']['exact_accuracy']['mean'] == .75
    assert summary['repeat_metrics']['exact_accuracy']['worst'] == .5
    assert summary['repeat_metrics']['dangerous']['mean'] == .5
    assert summary['repeat_metrics']['dangerous']['worst'] == 1


def test_fallback_conflicts_budget_skip_and_extra_calls_use_planned_denominator():
    rows = [
        scored_row('FICT001', trace={'source': 'rule', 'fallback_reason': 'model_budget',
                                     'conflicts': []}),
        scored_row('FICT002', trace={'source': 'merged', 'fallback_reason': None,
                                     'conflicts': ['month_unsupported', 'scope_rule_override']}, calls=1),
        scored_row('FICT003', status='structure_invalid', trace={
            'source': 'rule', 'fallback_reason': 'invalid_proposal',
            'conflicts': ['structure_invalid']}, calls=1),
    ]
    aggregate = intent_eval.summarize_results(rows)['aggregate']
    assert aggregate['planned_count'] == 3
    assert aggregate['fallback_count'] == 2
    assert aggregate['fallback_rate'] == pytest.approx(2 / 3)
    assert aggregate['budget_skip_count'] == 1
    assert aggregate['budget_skip_rate'] == pytest.approx(1 / 3)
    assert aggregate['extra_model_calls'] == 2
    assert aggregate['conflict_counts'] == {
        'month_unsupported': 1, 'scope_rule_override': 1, 'structure_invalid': 1}


def test_amended_dev_id021_is_single_listed_without_reducing_main_denominator():
    # The identifier is specified by the amendment; the content here is invented.
    rows = [scored_row('FICT001'),
            scored_row('ID021', prediction=gold(target_month=None, unresolved_month=True))]
    summary = intent_eval.summarize_results(rows, split='dev')
    assert summary['aggregate']['planned_count'] == 2
    assert summary['aggregate']['exact_accuracy'] == .5
    amended = summary['amendment_id021']
    assert amended['ids'] == ['ID021']
    assert amended['all_dev_denominator_preserved'] is True
    assert amended['affected']['planned_count'] == 1
    assert amended['excluding_affected']['planned_count'] == 1
    assert amended['excluding_affected']['exact_accuracy'] == 1


def test_cli_test_requires_approval_before_reading_dataset_or_creating_run(monkeypatch, tmp_path):
    dataset = tmp_path / 'fictional-test.jsonl'
    run = tmp_path / 'fresh-run'
    original = Path.read_text
    reads = []
    def guarded_read(path, *args, **kwargs):
        if path == dataset:
            reads.append(path)
            raise AssertionError('Approval gate must precede dataset access')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded_read)
    try:
        outcome = intent_eval.main(['--dataset', str(dataset), '--split', 'test',
                                    '--mode', 'rule', '--repeat', '1', '--run', str(run)])
    except SystemExit as exc:
        outcome = exc.code
    assert outcome not in (0, None)
    assert reads == []
    assert not run.exists()


def test_cli_explicit_p3_approval_allows_dispatch_for_a_fictional_test_path(monkeypatch, tmp_path):
    # Only a stub receives this fictitious path: no held-out data is opened.
    calls = []
    monkeypatch.setattr(intent_eval, 'run_evaluation',
                        lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
    dataset, run = tmp_path / 'fictional-test.jsonl', tmp_path / 'fresh-run'
    assert intent_eval.main([
        '--dataset', str(dataset), '--split', 'test', '--p3-approved',
        '--mode', 'rule', '--repeat', '3', '--run', str(run),
    ]) == 0
    assert calls == [((dataset, 'test', 'rule', 3, run), {'p3_approved': True})]


@pytest.mark.parametrize('relative', [
    'evaluation/intent_v1/test.jsonl', 'evaluation/intent_v1/cases.jsonl',
    'evaluation/intent_v1_r1/test.jsonl', 'evaluation/intent_v1_r1/cases.jsonl',
    'evaluation/intent_agent_v1/dev.jsonl', 'evaluation/intent_agent_v1_r1/dev.jsonl',
])
def test_api_cannot_read_protected_test_combined_or_agent_files_as_dev(
        monkeypatch, tmp_path, relative):
    # All paths are inside a nonexistent fictional repository, and the guard
    # must reject them without opening or inventorying any dataset files.
    fake_root = tmp_path / 'fictional-repository'
    monkeypatch.setattr(intent_eval, 'ROOT', fake_root)
    def forbidden_read(*_args, **_kwargs):
        raise AssertionError('Access guard must run before file reads')
    monkeypatch.setattr(Path, 'read_text', forbidden_read)
    run = tmp_path / 'fresh-run'
    with pytest.raises(ValueError):
        intent_eval.run_evaluation(fake_root / relative, 'dev', 'rule', 1, run)
    assert not run.exists()


def test_direct_api_test_split_also_requires_explicit_approval(monkeypatch, tmp_path):
    def forbidden_read(*_args, **_kwargs):
        raise AssertionError('Approval guard must run before dataset reads')
    monkeypatch.setattr(Path, 'read_text', forbidden_read)
    run = tmp_path / 'fresh-run'
    with pytest.raises(ValueError, match='p3-approved'):
        intent_eval.run_evaluation(tmp_path / 'fictional-test.jsonl', 'test', 'rule', 1, run)
    assert not run.exists()


@pytest.mark.parametrize('repeat', ['0', '-1'])
def test_cli_invalid_repeat_is_refused_before_any_dataset_access(tmp_path, repeat):
    with pytest.raises(SystemExit) as error:
        intent_eval.main([
            '--dataset', str(tmp_path / 'missing-fictional.jsonl'),
            '--split', 'dev', '--mode', 'rule', '--repeat', repeat,
            '--run', str(tmp_path / 'fresh-run'),
        ])
    assert error.value.code != 0


def test_cli_rejects_existing_run_before_reading_dataset(monkeypatch, tmp_path):
    dataset = tmp_path / 'fictional-dev.jsonl'
    run = tmp_path / 'existing-run'
    run.mkdir()
    sentinel = run / 'retain.txt'
    sentinel.write_text('preserve fictional output', encoding='utf-8')
    original = Path.read_text
    def guarded_read(path, *args, **kwargs):
        if path == dataset:
            raise AssertionError('Existing directory must be rejected before inputs')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded_read)
    try:
        outcome = intent_eval.main(['--dataset', str(dataset), '--split', 'dev',
                                    '--mode', 'rule', '--repeat', '1', '--run', str(run)])
    except SystemExit as exc:
        outcome = exc.code
    assert outcome not in (0, None)
    assert sentinel.read_text(encoding='utf-8') == 'preserve fictional output'


def test_rule_case_runner_invokes_real_resolver_without_constructing_model():
    row = intent_eval.evaluate_case(case(), records(), 'rule')
    assert row['status'] == 'ok'
    assert row['score']['pass'] is True
    assert row['prediction'] == {**gold(), 'excluded_fields': []}
    assert row['trace']['source'] == 'rule'
    assert row['extra_model_calls'] == 0
    assert row['wall_seconds'] >= 0


def test_case_top_level_order_is_passed_only_to_scoring():
    fixture = case()
    fixture['requested_field_order'] = fixture['gold'].pop('requested_field_order')
    row = intent_eval.evaluate_case(fixture, records(), 'rule')
    assert row['score']['pass'] is True
    assert row['prediction']['requested_field_order'] == ['星辉率']


@pytest.mark.parametrize('mode', ['llm_only', 'hybrid'])
def test_script_model_integration_uses_case_context_and_preserves_diagnostic_slots(monkeypatch, mode):
    model = install_model(monkeypatch, proposal())
    row = intent_eval.evaluate_case(case(), records(), mode)
    assert row['status'] == 'ok'
    assert row['score']['pass'] is True
    assert row['extra_model_calls'] == 1
    assert row['raw_proposal']['scope'] == 'only_listed'
    assert row['validation'] is not None
    assert row['validated_proposal'] is not None
    assert row['final_intent']['target_month'] == '2032-11'
    payload = json.loads(next(message.content for message in model.seen[0]
                              if isinstance(message, HumanMessage)))
    assert payload['today'] == '2033-03-14'
    assert payload['current_lookup_month'] == '2032-11'
    assert payload['field_catalog'] == '星辉率\n幻尘消耗\n晶片寿命'


def test_invalid_script_output_is_preserved_as_failure_not_correct_rule_result(monkeypatch):
    install_model(monkeypatch, 'fictitious invalid JSON')
    row = intent_eval.evaluate_case(case(), records(), 'hybrid')
    assert row['status'] != 'ok'
    assert row['score']['pass'] is False
    assert row['trace']['fallback_reason'] == 'invalid_proposal'
    assert row['raw_response']['content'] == 'fictitious invalid JSON'
    assert row['prediction']['fields'] == ['星辉率']


def test_non_message_script_output_keeps_invalid_structure_classification(monkeypatch):
    invalid_response = {'fictitious': 'not an AIMessage'}
    model = SimpleNamespace(
        model='fictional-invalid-type', base_url='http://scripted.invalid',
        invoke=lambda _messages: invalid_response,
    )
    monkeypatch.setattr(llm_parser, 'intent_model', lambda: model)
    row = intent_eval.evaluate_case(case(), records(), 'hybrid')
    assert row['execution_reason'] == 'invalid_proposal'
    assert row['trace']['fallback_reason'] == 'invalid_proposal'
    assert row['status'] == 'error'
    assert row['score']['pass'] is False
    assert row['raw_response']['message_type'] == 'dict'
    assert row['raw_response']['content'] == invalid_response


def test_script_model_exception_is_retained_without_removing_case(monkeypatch):
    install_model(monkeypatch, RuntimeError('fictional model failed'))
    row = intent_eval.evaluate_case(case(), records(), 'hybrid')
    assert row['status'] != 'ok'
    assert row['score']['pass'] is False
    assert row['trace']['fallback_reason'] == 'model_error'
    assert row['wall_seconds'] >= 0


def test_resolver_execution_exception_is_a_scored_result():
    def broken(*_args, **_kwargs):
        raise RuntimeError('fictional resolver failure')
    row = intent_eval.evaluate_case(case(), records(), 'hybrid', resolver=broken)
    assert row['status'] == 'error'
    assert row['score']['pass'] is False
    assert row['score']['execution_ok'] is False
    assert row['prediction'] is None


@pytest.mark.parametrize('configured,override,expected', [
    ('hybrid', None, 'hybrid'), ('rule', 'llm_only', 'llm_only'),
])
def test_agent_runner_manifest_records_effective_config_or_environment_intent_mode(
        monkeypatch, tmp_path, configured, override, expected):
    from evaluation import run as agent_runner
    fake_root = tmp_path / 'fictional-repository'
    config = fake_root / 'config'
    config.mkdir(parents=True)
    (config / 'rag.yml').write_text(
        'chat_model_name: fictional-chat\nembedding_model_name: fictional-embedding\n',
        encoding='utf-8')
    (config / 'intent.yml').write_text(f'mode: {configured}\n', encoding='utf-8')
    data = fake_root / 'data'
    data.mkdir()
    source = data / 'fictional.csv'
    source.write_text('fictional bytes\n', encoding='utf-8')
    dataset = fake_root / 'fictional-cases.jsonl'
    dataset.write_text(json.dumps(case(), ensure_ascii=False) + '\n', encoding='utf-8')
    (fake_root / 'dataset_manifest.json').write_text(json.dumps({
        'files': {'data/fictional.csv': agent_runner.digest(source)},
    }), encoding='utf-8')
    monkeypatch.setattr(agent_runner, 'ROOT', fake_root)
    monkeypatch.setattr(llm_parser, '_ROOT', fake_root)
    monkeypatch.setattr(agent_runner, 'business_files', lambda: {'fictional.py': '0' * 64})
    monkeypatch.setattr(agent_runner, 'evaluation_files', lambda: {'fictional-eval.py': '1' * 64})
    monkeypatch.setattr(agent_runner.importlib.metadata, 'version', lambda _name: 'fictional-v1')
    response = json.dumps({'models': [
        {'name': 'fictional-chat', 'digest': 'script-chat-digest'},
        {'name': 'fictional-embedding', 'digest': 'script-embedding-digest'},
    ]})
    monkeypatch.setattr(agent_runner.urllib.request, 'urlopen',
                        lambda *_args, **_kwargs: io.StringIO(response))
    if override is not None:
        monkeypatch.setenv('AGENT_INTENT_MODE', override)
    identity = agent_runner.environment_identity(dataset, timeout=12)
    assert identity['intent_mode'] == expected


def test_full_fictional_repeat_run_produces_hash_bound_archive_and_verified_seal(
        monkeypatch, tmp_path):
    from scripts.seal_evaluation_run import result_sha256, seal_run
    fake_root = tmp_path / 'fictional-repository'
    config = fake_root / 'config'
    config.mkdir(parents=True)
    (config / 'agent.yml').write_text('external_data_path: data/fictional.csv\n', encoding='utf-8')
    (config / 'intent.yml').write_text('mode: rule\n', encoding='utf-8')
    (config / 'rag.yml').write_text('chat_model_name: fictional-script\n', encoding='utf-8')
    source = fake_root / 'data/fictional.csv'
    write_fictional_csv(source)
    for name in (
        'app.py', 'requirements-lock.txt', 'prompts/intent_parser.txt',
        'evaluation/intent_eval.py', 'evaluation/INTENT_EVAL.md', 'evaluation/run.py',
        'scripts/seal_evaluation_run.py', 'scripts/prepare_evaluation_variant.py',
        'docs/plans/SCORING_AMENDMENT_01.md',
    ):
        target = fake_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('fictional source identity\n', encoding='utf-8')
    dataset = fake_root / 'evaluation/fictional-dev.jsonl'
    fixtures = [case(), case(id='FICT002', user_id='fictional-owner',
                             query='2032年11月只列晶片寿命',
                             gold=gold(fields=['晶片寿命'], requested_field_order=['晶片寿命']))]
    dataset.write_text(''.join(json.dumps(item, ensure_ascii=False) + '\n'
                               for item in fixtures), encoding='utf-8')
    monkeypatch.setattr(intent_eval, 'ROOT', fake_root)
    monkeypatch.setattr(llm_parser, '_ROOT', fake_root)
    monkeypatch.setattr(intent_eval, 'model_identity', lambda: {
        'name': 'fictional-script', 'configured_name': 'fictional-script',
        'digest': 'a' * 64, 'ollama_host': 'http://scripted.invalid',
    })
    monkeypatch.setattr(intent_eval.subprocess, 'check_output', lambda *_args, **_kwargs: 'f' * 40)
    archive = tmp_path / 'fictional-run'
    assert intent_eval.run_evaluation(dataset, 'dev', 'rule', 2, archive) == 0
    rows = [json.loads(line) for line in (archive / 'results.jsonl').read_text(
        encoding='utf-8').splitlines()]
    planned = [json.loads(line) for line in (archive / 'cases.jsonl').read_text(
        encoding='utf-8').splitlines()]
    reviews = [json.loads(line) for line in (archive / 'reviews.jsonl').read_text(
        encoding='utf-8').splitlines()]
    assert len(rows) == len(planned) == len(reviews) == 4
    assert len({row['id'] for row in rows}) == 4
    assert {row['repeat'] for row in rows} == {1, 2}
    assert all(row['score']['pass'] for row in rows)
    assert all(review['result_sha256'] == result_sha256(row)
               for row, review in zip(rows, reviews))
    manifest = json.loads((archive / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['mode'] == 'rule'
    assert manifest['repeat'] == 2
    assert manifest['model_identity']['intent']['digest'] == 'a' * 64
    assert manifest['input_dataset_sha256'] == intent_eval._digest(dataset)
    assert manifest['prompt_sha256']['prompts/intent_parser.txt'] == intent_eval._digest(
        fake_root / 'prompts/intent_parser.txt')
    assert manifest['configuration_sha256']['config/intent.yml'] == intent_eval._digest(
        config / 'intent.yml')
    for mapping in ('code_sha256', 'evaluation_sha256', 'source_sha256'):
        assert manifest[mapping]
        assert all(intent_eval._digest(archive / 'snapshot' / name) == digest
                   for name, digest in manifest[mapping].items())
    assert (archive / 'snapshot/input_dataset.jsonl').read_bytes() == dataset.read_bytes()
    assert (archive / 'summary.md').is_file()
    assert seal_run(archive, verify=True)['action'] == 'verified'
    (archive / 'summary.md').write_text('fictional tamper\n', encoding='utf-8')
    with pytest.raises(ValueError, match='inventory mismatch'):
        seal_run(archive, verify=True)
