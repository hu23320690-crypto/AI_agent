"""Full-report exclusions use only the authorized target record for this turn."""
from datetime import date

import pytest
from langchain_core.messages import AIMessage

import agent.react_agent as react_agent
from agent.context_budget import ContextPolicy
from agent.react_agent import ReactAgent
from test_llm_intent import (TODAY, install_model, make_run, no_real_intent_model,
                             proposal, set_config)
from utils.report_intent import resolve_report_intent
from utils.report_render import record_fields, render_lookup


USER = 'session-fictional-exclusion-user'


@pytest.fixture(autouse=True)
def fictitious_today(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return TODAY
    monkeypatch.setattr(react_agent, 'date', FixedDate)


def record(month='2032-11', *, fields=('星辉率', '晶片寿命'), user=USER):
    values = {'星辉率': '81%', '晶片寿命': '剩余23天', '幻尘消耗': '2个/月'}
    return {'status': 'ok', 'user_id': user, 'month': month, 'data': {
        '特征': '虚构舱室', '效率': '\\n'.join(f'{field}:{values[field]}' for field in fields),
        '耗材': '', '对比': '虚构说明'}}


def execute(query, current_results, *, lookup_records=(), lookup_result=None):
    selected = lookup_result if lookup_result is not None else current_results[-1]

    class LookupGraph:
        def invoke(self, state, *, config, context):
            context['lookup_result'] = selected
            context['lookup_results'] = list(current_results)
            return {'messages': [*state['messages'], AIMessage(content='scripted planner output')]}

    agent = object.__new__(ReactAgent)
    agent.user_id = USER
    agent.city = ''
    agent.agent = LookupGraph()
    agent.context_policy = ContextPolicy(window_tokens=16384, reserve_output_tokens=1024)
    run = make_run()
    agent.limits = run.limits
    _, text, _, intent = agent._execute_turn(query, [], run, lookup_records=lookup_records)
    return text, intent, run


def full_exclusion(monkeypatch, **changes):
    set_config(monkeypatch, mode='hybrid')
    return install_model(monkeypatch, proposal(scope='full_report', fields=[],
                                               excluded_fields=['晶片寿命'], **changes))


def test_full_report_exclusion_keeps_target_metrics_and_omits_history_only_metric(monkeypatch):
    full_exclusion(monkeypatch)
    target = record()
    older = record('2032-10', fields=('幻尘消耗', '晶片寿命'))
    text, intent, _ = execute('2032年11月完整报告，不要晶片寿命', [target],
                              lookup_records=[older])
    assert intent.fields == ('星辉率',)
    assert intent.target_month == '2032-11'
    assert not intent.limited
    assert '星辉率：81%' in text
    assert '晶片寿命' not in text
    assert '幻尘消耗' not in text
    assert '未提供' not in text


def test_full_report_exclusion_uses_target_instead_of_last_baseline_lookup(monkeypatch):
    full_exclusion(monkeypatch, compare=True, baseline_month='2032-10',
                   baseline_mention='2032年10月')
    target = record()
    baseline = record('2032-10', fields=('星辉率', '晶片寿命', '幻尘消耗'))
    text, intent, _ = execute('2032年11月完整报告，与2032年10月比较，不要晶片寿命',
                              [target, baseline])
    assert intent.fields == ('星辉率',)
    assert intent.compare
    assert intent.comparison_month == '2032-10'
    assert not intent.invalid_month and not intent.unresolved_month
    assert '2032-11 与 2032-10' in text
    assert '| 星辉率 |' in text
    assert '幻尘消耗' not in text


def test_listed_field_absent_from_target_remains_requested_and_unprovided(monkeypatch):
    set_config(monkeypatch, mode='hybrid')
    install_model(monkeypatch, proposal(fields=[{'mention': '幻尘消耗', 'field': '幻尘消耗'}],
                                       excluded_fields=['晶片寿命']))
    text, intent, _ = execute('2032年11月只列幻尘消耗，不要晶片寿命', [record()],
                              lookup_records=[record('2032-10', fields=('幻尘消耗',))])
    assert intent.fields == ('幻尘消耗',)
    assert intent.limited
    assert '幻尘消耗：未提供' in text


def test_rule_mode_report_exclusion_preserves_original_resolution_and_rendering(monkeypatch):
    set_config(monkeypatch, mode='rule')
    query = '2032年11月完整报告，不要晶片寿命'
    target, older = record(), record('2032-10', fields=('幻尘消耗', '晶片寿命'))
    text, intent, run = execute(query, [target], lookup_records=[older])
    known_fields = tuple(dict.fromkeys(field for item in [older, target]
                                       for field in record_fields(item['data'])))
    expected = resolve_report_intent(query, known_fields=known_fields, fallback_month='2032-11')
    assert intent == expected
    assert text == render_lookup(target, query=query, lookup_results=[older, target],
                                 intent=expected, current_results=[target])
    assert run.counts['model'] == 0


def test_full_report_exclusion_with_no_remaining_target_metric_cannot_expand(monkeypatch):
    full_exclusion(monkeypatch)
    text, intent, _ = execute('2032年11月完整报告，不要晶片寿命',
                              [record(fields=('晶片寿命',))],
                              lookup_records=[record('2032-10', fields=('星辉率', '幻尘消耗'))])
    assert intent.fields == ()
    assert intent.limited
    assert '无法识别所限定的字段' in text
    assert '星辉率' not in text and '晶片寿命' not in text and '幻尘消耗' not in text
    assert '使用报告' not in text


@pytest.mark.parametrize('case', ['cached_target', 'foreign_target', 'missing_target'])
def test_full_report_exclusion_does_not_filter_from_unavailable_current_target(monkeypatch, case):
    full_exclusion(monkeypatch)
    older = record(fields=('星辉率', '晶片寿命', '幻尘消耗'))
    actual = record('2032-12', fields=('晶片寿命',))
    if case == 'foreign_target':
        current = [record(fields=('晶片寿命',), user='other-fictional-user'), actual]
    elif case == 'missing_target':
        current = [{'status': 'not_found', 'user_id': USER, 'month': '2032-11'}, actual]
    else:
        current = [actual]
    text, intent, _ = execute('2032年11月完整报告，不要晶片寿命', current,
                              lookup_records=[older])
    assert intent.fields == ('星辉率', '幻尘消耗')
    assert not intent.limited
    missing_message = '未找到' if case == 'missing_target' else '本次未查询到'
    assert missing_message in text
    assert '81%' not in text and '2个/月' not in text


def test_full_report_exclusion_filters_after_default_target_month_is_normalized(monkeypatch):
    full_exclusion(monkeypatch, target_month=None, target_mention='')
    text, intent, _ = execute('完整报告，不要晶片寿命', [record()],
                              lookup_records=[record('2032-10', fields=('幻尘消耗',))])
    assert intent.target_month == '2032-11'
    assert intent.fields == ('星辉率',)
    assert '星辉率：81%' in text
    assert '幻尘消耗' not in text


def test_rule_scope_override_retains_explicit_missing_metric(monkeypatch):
    full_exclusion(monkeypatch)
    text, intent, _ = execute('2032年11月只列星辉率，不要晶片寿命',
                              [record(fields=('晶片寿命',))],
                              lookup_records=[record('2032-10', fields=('星辉率',))])
    assert intent.fields == ('星辉率',)
    assert intent.limited
    assert '星辉率：未提供' in text
