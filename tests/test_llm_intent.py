"""P1 intent guards use fictitious reports and scripted, tool-free models only."""
from dataclasses import replace
from datetime import date
import json
from threading import Event, Thread

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama

from agent.context_budget import ContextPolicy
from agent.intent import llm_parser
from agent.intent import resolve as intent_resolve
from agent.intent.resolve import resolve_turn_intent
from agent.react_agent import ReactAgent, _knowledge_requested
from agent.runtime import DeadlineExceeded, ExecutionRuntime, RunCancelled, RunContext, RunLimits
from agent.runtime.resilience import dependency_key
from model.factory import budgeted_chat_model
from utils.report_intent import ReportIntent, resolve_report_intent
from utils.report_render import render_lookup


CATALOG = ('星辉率', '晶片寿命', '幻尘消耗')
TODAY = date(2033, 3, 14)


def proposal(**changes):
    """Every required key is present; fields/dates belong only to this fixture."""
    value = {
        'task_type': 'report',
        'fields': [{'mention': '星辉率', 'field': '星辉率'}],
        'scope': 'only_listed',
        'target_month': '2032-11',
        'target_mention': '2032年11月',
        'compare': False,
        'baseline_month': None,
        'baseline_mention': '',
        'excluded_fields': [],
        'knowledge_question': '',
        'unresolved': False,
    }
    return {**value, **changes}


class ScriptedIntentModel:
    """Minimal invocation surface; any attempt to bind tools fails the test."""
    model = 'fictitious-intent-no-network'
    base_url = 'http://scripted.invalid'

    def __init__(self, *responses):
        self.responses = list(responses)
        self.seen = []

    def bind_tools(self, *_args, **_kwargs):
        raise AssertionError('Intent parsing must not bind tools')

    def invoke(self, messages):
        self.seen.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            response = response()
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=(json.dumps(response, ensure_ascii=False)
                                  if isinstance(response, dict) else response))


@pytest.fixture(autouse=True)
def no_real_intent_model(monkeypatch):
    """An omitted script must fail immediately, before touching an endpoint."""
    def forbidden():
        raise AssertionError('This test may invoke only an injected scripted model')
    monkeypatch.setattr(llm_parser, 'intent_model', forbidden)
    monkeypatch.setattr(llm_parser, 'load_context_policy', lambda: ContextPolicy(
        window_tokens=16384, reserve_output_tokens=1024, reasoning_enabled=False))
    monkeypatch.delenv('AGENT_INTENT_MODE', raising=False)


def install_model(monkeypatch, *responses):
    model = ScriptedIntentModel(*responses)
    monkeypatch.setattr(llm_parser, 'intent_model', lambda: model)
    return model


def make_run(**changes):
    limits = replace(RunLimits(), **changes)
    return RunContext(limits, ExecutionRuntime(limits))


def resolve(query='2032年11月只列星辉率', **changes):
    return resolve_turn_intent(query, **{
        'known_fields': CATALOG, 'fallback_month': '2032-11',
        'today': TODAY, 'mode': 'hybrid', **changes})


def fictional_record(month='2032-11', user='session-fictional-user'):
    return {'status': 'ok', 'user_id': user, 'month': month, 'data': {
        '特征': '虚构舱室', '效率': '星辉率:81%\\n幻尘消耗:2个/月',
        '耗材': '晶片寿命:剩余23天', '对比': '虚构说明'}}


def test_01_valid_proposal_is_adopted_and_is_tool_free(monkeypatch):
    model = install_model(monkeypatch, proposal())
    run = make_run()
    result = resolve(run=run)
    assert result.intent == ReportIntent(fields=('星辉率',), target_month='2032-11', limited=True)
    assert result.knowledge_requested is False
    assert result.trace['source'] == 'llm'
    assert not result.trace['conflicts']
    assert run.counts['model'] == 1
    assert len(model.seen) == 1


def invalid_responses():
    good = json.dumps(proposal(), ensure_ascii=False)
    return [
        'not JSON',
        good[:-1],
        good.replace('"task_type": "report"', '"task_type": "report", "task_type": "other"'),
        good.replace('"mention": "星辉率"', '"mention": "星辉率", "mention": "晶片寿命"'),
        proposal(unexpected='forbidden'),
        {key: value for key, value in proposal().items() if key != 'scope'},
        proposal(compare='false'),
        proposal(task_type='invalid-enum'),
        AIMessage(content=good, response_metadata={'done_reason': 'length'}),
    ]


@pytest.mark.parametrize('response', invalid_responses())
def test_02_invalid_structure_falls_back_without_failing_turn(monkeypatch, response):
    install_model(monkeypatch, response)
    run = make_run()
    result = resolve(run=run)
    assert result.intent == resolve_report_intent('2032年11月只列星辉率', known_fields=CATALOG,
                                                   fallback_month='2032-11')
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'invalid_proposal'
    assert run.status == 'running'


def test_03_outside_catalog_degrades_to_unknown_and_renders_unprovided(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '辉光耗用', 'field': '幽灵指标'}]))
    result = resolve('2032年11月只列辉光耗用')
    assert result.intent.fields == ('辉光耗用',)
    assert 'field_not_in_catalog' in result.trace['conflicts']
    text = render_lookup(fictional_record(), intent=result.intent)
    assert '辉光耗用：未提供' in text
    assert '星辉率：81%' not in text


def test_04_unanchored_field_mention_is_discarded(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '晶片寿命', 'field': '晶片寿命'}]))
    result = resolve()
    assert result.intent.fields == ('星辉率',)
    assert '晶片寿命' not in result.intent.fields
    assert result.intent.limited
    assert 'mention_not_in_text' in result.trace['conflicts']


def test_05_qualifier_cannot_be_dropped_to_a_catalog_field(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '墙角星辉率', 'field': '星辉率'}]))
    result = resolve('2032年11月只列墙角星辉率')
    assert result.intent.fields == ('墙角星辉率',)
    assert 'qualifier_dropped' in result.trace['conflicts']
    assert '墙角星辉率：未提供' in render_lookup(fictional_record(), intent=result.intent)


def test_06_unsupported_month_uses_rule_slot(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2033-06'))
    result = resolve()
    assert result.intent.target_month == '2032-11'
    assert 'month_unsupported' in result.trace['conflicts']


@pytest.mark.parametrize('prefix', ['撤回2032年2月那份', '2032年2月只作为背景'])
def test_06_withdrawn_or_background_month_is_not_forced_as_target(monkeypatch, prefix):
    install_model(monkeypatch, proposal(target_month='2032-08', target_mention='2032年8月'))
    result = resolve(prefix + '；本次请列2032年8月的星辉率', fallback_month='2032-08')
    assert result.intent.target_month == '2032-08'
    assert 'month_unsupported' not in result.trace['conflicts']


def test_06_null_unresolved_month_is_not_replaced_by_explicit_background(monkeypatch):
    install_model(monkeypatch, proposal(target_month=None, target_mention='', unresolved=True))
    result = resolve('2032年2月是背景记录；目标月份还没确定，只列星辉率')
    assert result.intent.target_month is None
    assert result.intent.unresolved_month
    assert '无法确定' in render_lookup(fictional_record(), intent=result.intent)


def test_06_negated_month_cannot_be_selected(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2032-02', target_mention='2032年2月'))
    result = resolve('不是2032年2月，是2032年8月，只列星辉率', fallback_month='2032-08')
    assert result.intent.target_month == '2032-08'
    assert 'negated_month_selected' in result.trace['conflicts']


def test_07_relative_month_is_recomputed_across_year_boundary(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2032-11', target_mention='下一月'))
    previous = ReportIntent(fields=('星辉率',), target_month='2032-12', limited=True)
    result = resolve('下一月只列星辉率', previous_intent=previous, fallback_month='2033-01')
    assert result.intent.target_month == '2033-01'
    assert 'relative_month_recomputed' in result.trace['conflicts']


def test_08_relative_month_without_report_anchor_stays_unresolved(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2033-02', target_mention='上个月'))
    result = resolve('上个月只列星辉率', fallback_month=None)
    assert result.intent.unresolved_month
    assert 'no_anchor' in result.trace['conflicts']


def test_09_negated_field_is_discarded(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '星辉率', 'field': '星辉率'},
        {'mention': '晶片寿命', 'field': '晶片寿命'}]))
    result = resolve('2032年11月只列星辉率，不要晶片寿命')
    assert result.intent.fields == ('星辉率',)
    assert 'negated_field_selected' in result.trace['conflicts']


@pytest.mark.parametrize('task_type', ['knowledge_only', 'other'])
def test_10_completed_report_lookup_rejects_conflicting_task(monkeypatch, task_type):
    install_model(monkeypatch, proposal(task_type=task_type))
    result = resolve()
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'task_type_conflict'
    assert 'task_type_conflict' in result.trace['conflicts']


def set_config(monkeypatch, **changes):
    cfg = replace(llm_parser.IntentConfig(), **changes)
    monkeypatch.setattr(llm_parser, 'load_intent_config', lambda path=None: cfg)
    monkeypatch.setattr(intent_resolve, 'load_intent_config', lambda path=None: cfg)
    return cfg


def test_11_optional_timeout_keeps_parent_running_and_ignores_late_result(monkeypatch):
    set_config(monkeypatch, timeout_seconds=.06)
    entered, release, exited = Event(), Event(), Event()
    def blocked():
        entered.set()
        try:
            assert release.wait(3), 'test did not release scripted worker'
            return proposal(fields=[{'mention': '晶片寿命', 'field': '晶片寿命'}])
        finally:
            exited.set()
    model = install_model(monkeypatch, blocked)
    run = make_run()
    try:
        result = resolve(run=run)
        assert entered.is_set()
        assert result.trace['source'] == 'rule'
        assert result.trace['fallback_reason'] == 'model_timeout'
        assert run.status == 'running'
        saved_intent = result.intent
        committed = []
        run.complete(commit=lambda: committed.append(saved_intent))
    finally:
        release.set()
        assert exited.wait(2)
    assert result.intent == saved_intent
    assert committed == [saved_intent]
    assert run.status == 'succeeded'
    assert len(model.seen) == 1


def test_12_exhausted_call_budget_skips_model_without_budget_exception(monkeypatch):
    model = install_model(monkeypatch, proposal())
    run = make_run(max_model_calls=1)
    run.reserve('model')
    assert run.remaining_calls('model') == 0
    result = resolve(run=run)
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'model_budget'
    assert model.seen == []
    assert run.status == 'running'


def test_13_open_circuit_skips_model_and_falls_back(monkeypatch):
    model = install_model(monkeypatch, proposal())
    run = make_run()
    breaker = run.executor.resilience.breaker(dependency_key(model, 'chat'))
    for _ in range(breaker.policy.minimum_samples + breaker.policy.failure_threshold):
        if breaker.snapshot()['state'] == 'OPEN':
            break
        breaker.record(breaker.acquire(), 'failure')
    result = resolve(run=run)
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'circuit_open'
    assert model.seen == []
    assert run.status == 'running'


@pytest.mark.parametrize('extra', [{'user_id': 'model-fictional-user'},
                                  {'tools': ['fetch_external_data']}])
def test_14_identity_and_tool_keys_invalidate_entire_proposal(monkeypatch, extra):
    install_model(monkeypatch, {**proposal(), **extra})
    result = resolve()
    assert result.trace['source'] == 'rule'
    assert result.trace['fallback_reason'] == 'invalid_proposal'
    text = render_lookup(fictional_record(), intent=result.intent)
    assert 'session-fictional-user' in text
    assert 'model-fictional-user' not in text


def test_14_agent_report_user_remains_session_user(monkeypatch):
    install_model(monkeypatch, proposal(user_id='model-fictional-user'))
    set_config(monkeypatch, mode='hybrid')
    class LookupGraph:
        def invoke(self, state, *, config, context):
            record = fictional_record(user=context['user_id'])
            context['lookup_result'] = record
            context['lookup_results'] = [record]
            return {'messages': [*state['messages'], AIMessage(content='scripted planner output')]}
    agent = object.__new__(ReactAgent)
    agent.user_id = 'session-fictional-user'
    agent.city = ''
    agent.agent = LookupGraph()
    agent.context_policy = ContextPolicy(window_tokens=16384, reserve_output_tokens=1024)
    run = make_run()
    agent.limits = run.limits
    _, text, _, _ = agent._execute_turn('2032年11月只列星辉率', [], run)
    assert 'session-fictional-user' in text
    assert 'model-fictional-user' not in text


def test_15_rule_mode_never_constructs_or_invokes_a_model():
    result = resolve(mode='rule')
    assert result.intent == resolve_report_intent('2032年11月只列星辉率', known_fields=CATALOG,
                                                   fallback_month='2032-11')
    assert result.knowledge_requested == _knowledge_requested('2032年11月只列星辉率')
    assert result.trace['source'] == 'rule'


def test_16_trace_contains_codes_only_and_no_user_text(monkeypatch):
    query = '私密原文marker-query，2032年11月只列墙角星辉率'
    history = ('私密历史marker-history，只列幻尘消耗',)
    install_model(monkeypatch, proposal(fields=[{'mention': '墙角星辉率', 'field': '星辉率'}]))
    run = make_run()
    result = resolve(query, history_queries=history, run=run)
    trace = json.dumps({'result': result.trace, 'run': run.snapshot()}, ensure_ascii=False)
    for private in ('marker-query', 'marker-history', '墙角星辉率', '2032年11月'):
        assert private not in trace
    event = next(event for event in run.events if event['event'] == 'intent_resolved')
    assert event['conflicts'] == result.trace['conflicts']
    assert 'qualifier_dropped' in trace
    assert set(result.trace) == {'mode', 'source', 'fallback_reason', 'conflicts', 'latency_ms'}


@pytest.mark.parametrize('slot', ['target_month', 'baseline_month'])
def test_invalid_month_slot_uses_rule_month(monkeypatch, slot):
    query = '2032年11月星辉率与2032年10月相比'
    value = proposal(compare=True, baseline_month='2032-10', baseline_mention='2032年10月')
    value[slot] = '2032-13'
    install_model(monkeypatch, value)
    result = resolve(query)
    assert result.intent.target_month == '2032-11'
    assert result.intent.comparison_month == '2032-10'
    assert 'month_invalid' in result.trace['conflicts']


def test_comparison_relative_baseline_is_recomputed(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2033-01', target_mention='2033年1月',
        compare=True, baseline_month='2032-11', baseline_mention='环比'))
    result = resolve('2033年1月只列星辉率并计算环比', fallback_month='2033-01')
    assert result.intent.comparison_month == '2032-12'
    assert 'relative_month_recomputed' in result.trace['conflicts']


@pytest.mark.parametrize('query, scope, limited, fields', [
    ('2032年11月只列星辉率', 'full_report', True, ('星辉率',)),
    ('2032年11月完整报告', 'only_listed', False, ()),
])
def test_explicit_rule_scope_overrides_conflicting_proposal(monkeypatch, query, scope, limited, fields):
    install_model(monkeypatch, proposal(scope=scope))
    result = resolve(query)
    assert result.intent.limited == limited
    assert result.intent.fields == fields
    assert result.trace['source'] == 'merged'


def test_explicit_do_not_explain_suppresses_llm_knowledge_question(monkeypatch):
    install_model(monkeypatch, proposal(task_type='report_with_knowledge',
                                        knowledge_question='如何养护晶片？'))
    result = resolve('2032年11月只列星辉率，不要解释')
    assert result.knowledge_requested is False
    assert result.trace['source'] == 'merged'


def test_positive_knowledge_subquestion_is_kept(monkeypatch):
    install_model(monkeypatch, proposal(task_type='report_with_knowledge',
                                        knowledge_question='晶片如何养护？'))
    result = resolve('2032年11月只列星辉率；晶片如何养护？')
    assert result.knowledge_requested


def test_llm_only_keeps_v1_v2_v10_but_disables_v3_through_v9(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '并未出现的墙角星辉率', 'field': '星辉率'},
        {'mention': '辉光耗用', 'field': '目录外指标'}],
        target_month='2033-06', target_mention='上个月'))
    result = resolve('2032年11月只列辉光耗用，不要星辉率', mode='llm_only')
    assert result.intent.fields == ('星辉率', '辉光耗用')
    assert result.intent.target_month == '2033-06'
    assert result.trace['conflicts'] == ['field_not_in_catalog']


def test_history_is_recent_bounded_utf8_and_anchors_only_admitted_text(monkeypatch):
    cfg = set_config(monkeypatch, history_queries=3, history_bytes=36)
    history = ('古早锚点星辉率', '前史一' * 8, '前史二' * 8, '晶片寿命')
    bounded = llm_parser.bounded_history_queries(history, cfg)
    assert len(bounded) <= 3
    assert sum(len(item.encode('utf-8')) for item in bounded) <= 36
    assert bounded[-1] == '晶片寿命'
    assert '古早锚点星辉率' not in ''.join(bounded)
    model = install_model(monkeypatch, proposal(fields=[
        {'mention': '晶片寿命', 'field': '晶片寿命'},
        {'mention': '古早锚点星辉率', 'field': '星辉率'}]))
    result = resolve('2032年11月只列同样的指标', history_queries=history)
    assert result.intent.fields == ('晶片寿命',)
    assert 'mention_not_in_text' in result.trace['conflicts']
    payload = json.loads(next(message.content for message in model.seen[0]
                              if isinstance(message, HumanMessage)))
    assert payload['history_queries'] == list(bounded)
    assert payload['today'] == '2033-03-14'
    assert payload['field_catalog'] == '\n'.join(CATALOG)


def test_context_admission_failure_skips_dispatch_and_preserves_parent(monkeypatch):
    model = install_model(monkeypatch, proposal())
    monkeypatch.setattr(llm_parser, 'load_context_policy', lambda: ContextPolicy(
        window_tokens=1200, reserve_output_tokens=1024, safety_margin_tokens=64))
    run = make_run()
    result = resolve(run=run)
    assert result.trace['fallback_reason'] == 'context_budget'
    assert model.seen == []
    assert run.counts['model'] == 0
    assert run.status == 'running'


def test_insufficient_remaining_time_skips_dispatch(monkeypatch):
    model = install_model(monkeypatch, proposal())
    run = make_run(total_seconds=10)
    result = resolve(run=run)
    assert result.trace['fallback_reason'] == 'time_budget'
    assert model.seen == []
    assert run.status == 'running'


@pytest.mark.parametrize('control', ['cancel', 'deadline'])
def test_total_deadline_and_cancel_propagate_instead_of_falling_back(monkeypatch, control):
    entered, release, exited = Event(), Event(), Event()
    def blocked():
        entered.set()
        try:
            assert release.wait(3), 'test did not release scripted worker'
            return proposal()
        finally:
            exited.set()
    install_model(monkeypatch, blocked)
    run = make_run()
    outcome = {}
    def work():
        try:
            outcome['result'] = resolve(run=run)
        except BaseException as exc:
            outcome['error'] = exc
    worker = Thread(target=work, daemon=True)
    worker.start()
    try:
        assert entered.wait(2)
        if control == 'cancel':
            run.cancel()
        else:
            with run.lock:
                run.deadline = run.clock() - 1
        worker.join(2)
        assert not worker.is_alive()
        assert isinstance(outcome.get('error'), RunCancelled if control == 'cancel' else DeadlineExceeded)
        assert 'result' not in outcome
    finally:
        release.set()
        assert exited.wait(2)
        worker.join(2)


def test_model_error_is_recoverable_without_sensitive_exception_trace(monkeypatch):
    install_model(monkeypatch, RuntimeError('private-model-error-marker'))
    run = make_run()
    result = resolve(run=run)
    assert result.trace['fallback_reason'] == 'model_error'
    assert run.status == 'running'
    assert 'private-model-error-marker' not in json.dumps(run.snapshot())


def test_intent_model_factory_caps_output_disables_reasoning_and_sets_schema():
    from agent.intent.schema import INTENT_SCHEMA
    original = ChatOllama(model='fictitious-factory-no-network', reasoning=True,
                          temperature=.8, num_ctx=8192, num_predict=800)
    selected = budgeted_chat_model(original, ContextPolicy(), purpose='intent')
    assert selected.reasoning is False
    assert selected.temperature == 0
    assert 0 < selected.num_predict <= 384
    assert selected.format == INTENT_SCHEMA
    assert original.reasoning is True
    assert original.format != INTENT_SCHEMA


def test_intent_configuration_defaults_and_environment_override(monkeypatch, tmp_path):
    path = tmp_path / 'fictional-intent.yml'
    path.write_text('mode: rule\ntimeout_seconds: 15\nhistory_queries: 3\nhistory_bytes: 1024\n',
                    encoding='utf-8')
    assert llm_parser.load_intent_config(path).mode == 'rule'
    monkeypatch.setenv('AGENT_INTENT_MODE', 'hybrid')
    assert llm_parser.load_intent_config(path).mode == 'hybrid'
    monkeypatch.setenv('AGENT_INTENT_MODE', 'invalid')
    with pytest.raises(ValueError):
        llm_parser.load_intent_config(path)


@pytest.mark.parametrize('content', [
    'mode: rule\nunknown: 1\n', 'mode: invalid\n', 'timeout_seconds: 0\n',
    'history_queries: 4\n', 'history_bytes: 1025\n', 'history_queries: true\n',
])
def test_invalid_intent_configuration_is_rejected(tmp_path, content):
    path = tmp_path / 'fictional-invalid-intent.yml'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        llm_parser.load_intent_config(path)


@pytest.mark.parametrize('query, history, previous, fallback', [
    ('2032年11月只列星辉率和晶片寿命', (), None, '2032-11'),
    ('2032年11月只列辉光耗用', (), None, '2032-11'),
    ('2032年11月只列星辉率，不要幻尘消耗', (), None, '2032-11'),
    ('只列晶片寿命，改为完整报告', ('2032年11月只列星辉率',), None, '2032-11'),
    ('下一月这两个指标呢', ('2032年12月只列星辉率和晶片寿命',), None, '2033-01'),
    ('下一月这两个指标呢', (), ReportIntent(fields=('星辉率', '晶片寿命'),
        target_month='2032-12', limited=True), '2033-01'),
    ('2033年1月星辉率与2032年12月相比', (), None, '2033-01'),
    ('2032年11月星辉率环比', (), None, '2032-11'),
    ('2032年13月只列星辉率', (), None, '2032-11'),
    ('上个月只列星辉率', (), None, None),
    ('2032年11月只列星辉率，晶片如何养护？', (), None, '2032-11'),
    ('2032年11月只列星辉率，不要解释', (), None, '2032-11'),
    ('2032年11月只列星辉率，不要解释，但晶片的含义是什么？', (), None, '2032-11'),
    ('完整报告', ('2032年10月只列星辉率', '下一月这项呢'), None, '2032-11'),
    ('2032年11月幻尘消耗和辉光耗用是多少', (), None, '2032-11'),
])
def test_rule_mode_is_equivalent_for_fictitious_inputs(query, history, previous, fallback):
    run = make_run()
    result = resolve(query, mode='rule', history_queries=history,
                     previous_intent=previous, fallback_month=fallback, run=run)
    expected = resolve_report_intent(query, history, known_fields=CATALOG,
                                    fallback_month=fallback, previous_intent=previous)
    assert result.intent == expected
    assert result.knowledge_requested == _knowledge_requested(query)
    assert result.trace['source'] == 'rule'
    assert run.counts['model'] == 0


def test_inherited_historical_relative_month_is_not_applied_twice(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2032-10', target_mention='上一月'))
    previous = ReportIntent(fields=('星辉率',), target_month='2032-10', limited=True)
    result = resolve('继续只列星辉率', history_queries=(),
                     llm_history_queries=('上一月只列星辉率',), previous_intent=previous,
                     fallback_month='2032-10')
    assert result.intent.target_month == '2032-10'
    assert 'relative_month_recomputed' not in result.trace['conflicts']


def test_relative_baseline_uses_validated_target_month(monkeypatch):
    install_model(monkeypatch, proposal(target_month='2033-06', compare=True,
        baseline_month='2033-05', baseline_mention='上个月'))
    result = resolve('2032年11月星辉率与上个月相比')
    assert result.intent.target_month == '2032-11'
    assert result.intent.comparison_month == '2032-10'
    assert 'month_unsupported' in result.trace['conflicts']
    assert 'relative_month_recomputed' in result.trace['conflicts']


def test_full_report_explicit_exclusion_removes_catalog_field(monkeypatch):
    install_model(monkeypatch, proposal(scope='full_report', fields=[],
                                       excluded_fields=['晶片寿命']))
    result = resolve('2032年11月完整报告，不要晶片寿命')
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert not result.intent.limited
    text = render_lookup(fictional_record(), intent=result.intent)
    assert '星辉率：81%' in text
    assert '幻尘消耗：2个/月' in text
    assert '晶片寿命' not in text


def test_full_report_excluding_entire_catalog_never_expands_empty_fields(monkeypatch):
    install_model(monkeypatch, proposal(scope='full_report', fields=[],
                                       excluded_fields=list(CATALOG)))
    result = resolve('2032年11月完整报告，不要星辉率、晶片寿命、幻尘消耗')
    assert result.intent.fields == ()
    assert result.intent.limited
    assert '无法识别所限定的字段' in render_lookup(fictional_record(), intent=result.intent)


def test_listed_report_explicit_exclusion_removes_selected_field(monkeypatch):
    install_model(monkeypatch, proposal(fields=[
        {'mention': '星辉率', 'field': '星辉率'},
        {'mention': '晶片寿命', 'field': '晶片寿命'}], excluded_fields=['晶片寿命']))
    result = resolve('2032年11月只列星辉率，不要晶片寿命')
    assert result.intent.fields == ('星辉率',)
    assert 'negated_field_selected' in result.trace['conflicts']


def test_unanchored_exclusion_cannot_hide_requested_field(monkeypatch):
    install_model(monkeypatch, proposal(excluded_fields=['星辉率']))
    result = resolve()
    assert result.intent.fields == ('星辉率',)
    assert 'exclusion_not_in_text' in result.trace['conflicts']


def test_outside_catalog_exclusion_is_ignored(monkeypatch):
    install_model(monkeypatch, proposal(excluded_fields=['虚构目录外指标']))
    result = resolve()
    assert result.intent.fields == ('星辉率',)
    assert 'field_not_in_catalog' in result.trace['conflicts']


def test_positive_correction_cancels_prior_field_exclusion(monkeypatch):
    install_model(monkeypatch, proposal(fields=[{'mention': '晶片寿命', 'field': '晶片寿命'}],
                                       excluded_fields=['晶片寿命']))
    result = resolve('2032年11月不要晶片寿命，改为只列晶片寿命')
    assert result.intent.fields == ('晶片寿命',)
    assert 'exclusion_not_in_text' in result.trace['conflicts']


def test_llm_only_exclusions_need_catalog_membership_but_not_text_evidence(monkeypatch):
    install_model(monkeypatch, proposal(scope='full_report', fields=[],
                                       excluded_fields=['晶片寿命', '虚构目录外指标']))
    result = resolve('2032年11月完整报告', mode='llm_only')
    assert result.intent.fields == ('星辉率', '幻尘消耗')
    assert result.trace['conflicts'] == ['field_not_in_catalog']


@pytest.mark.parametrize('mode', ['hybrid', 'llm_only'])
def test_null_unresolved_baseline_is_not_filled_from_background_month(monkeypatch, mode):
    install_model(monkeypatch, proposal(compare=True, baseline_month=None,
                                       baseline_mention='', unresolved=True))
    result = resolve('2032年11月星辉率；2032年10月仅是背景，比较基准尚未确定', mode=mode)
    assert result.intent.target_month == '2032-11'
    assert result.intent.comparison_month is None
    assert result.intent.unresolved_month


def test_month_format_requires_ascii_digits(monkeypatch):
    install_model(monkeypatch, proposal(target_month='２０３２-１１'))
    result = resolve()
    assert result.intent.target_month == '2032-11'
    assert 'month_invalid' in result.trace['conflicts']


def test_unknown_scope_after_field_rejection_cannot_expand_to_full_report(monkeypatch):
    install_model(monkeypatch, proposal(scope='unspecified', fields=[
        {'mention': '幻尘消耗', 'field': '幻尘消耗'}]))
    result = resolve()
    assert result.intent.fields == ('星辉率',)
    assert result.intent.limited
    text = render_lookup(fictional_record(), intent=result.intent)
    assert '晶片寿命' not in text
    assert '幻尘消耗' not in text


@pytest.mark.parametrize('fail_at', [1, 2])
def test_source_invalidation_remains_terminal_before_and_after_optional_call(monkeypatch, fail_at):
    from rag.security import KnowledgeAccessError
    model = install_model(monkeypatch, proposal())
    run = make_run()
    seen = []
    def source_check():
        seen.append(True)
        if len(seen) == fail_at:
            raise KnowledgeAccessError('fictitious_source_revoked')
    run.add_commit_check(source_check)
    with pytest.raises(KnowledgeAccessError):
        resolve(run=run)
    assert len(model.seen) == fail_at - 1
    assert not any(event['event'] == 'intent_resolved' for event in run.events)


@pytest.mark.parametrize('history, target', [
    (('2032年12月只列星辉率',), '2033-01'),
    (('2032年12月只列星辉率', '下一月只列星辉率', '晶片如何养护？'), '2033-02'),
])
def test_hybrid_recovers_absolute_history_anchor_without_a_saved_intent(monkeypatch, history, target):
    model = install_model(monkeypatch, proposal(target_month=target, target_mention='下一月'))
    result = resolve('下一月只列星辉率', history_queries=history,
                     previous_intent=None, fallback_month=target)
    assert result.intent.target_month == target
    assert 'relative_month_recomputed' not in result.trace['conflicts']
    payload = json.loads(next(message.content for message in model.seen[0]
                              if isinstance(message, HumanMessage)))
    assert payload['previous_intent']['target_month'] == ('2032-12' if len(history) == 1 else '2033-01')


def test_empty_proposal_field_list_records_rule_field_fallback(monkeypatch):
    install_model(monkeypatch, proposal(fields=[]))
    result = resolve()
    assert result.intent.fields == ('星辉率',)
    assert result.trace['source'] == 'merged'
    assert 'fields_rule_fallback' in result.trace['conflicts']
