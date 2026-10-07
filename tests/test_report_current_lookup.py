"""Historical records may support baselines, never replace a fresh target lookup."""
from unittest.mock import patch

from agent.react_agent import ReactAgent
from test_core_flows import ScriptedModel, answer, call, scripted_context_policy
from utils.report_intent import ReportIntent
from utils.report_render import render_lookup


def data(coverage):
    return {'特征': '测试房屋', '效率': f'覆盖率:{coverage}%',
            '耗材': '滤网寿命:剩余30天', '对比': '本地测试记录'}


def record(month, coverage):
    return {'status': 'ok', 'user_id': '1001', 'month': month, 'data': data(coverage)}


def test_cached_target_month_does_not_hide_wrong_current_month_by_default():
    cached = record('2032-11', '77')
    actual = record('2032-12', '91')
    text = render_lookup(actual, query='重新查询2032年11月覆盖率', lookup_results=[cached])
    assert '77%' not in text and '91%' not in text
    assert '2032-11' in text and ('未查询' in text or '未查到' in text)


def test_agent_wrong_month_lookup_cannot_claim_stale_target_is_a_current_query():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2032-11'), answer('完成'),
        call('fetch_external_data', user_id='1001', month='2032-12'), answer('完成'),
    ])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    records = [{('1001', '2032-11'): data('77')},
               {('1001', '2032-11'): data('80'), ('1001', '2032-12'): data('91')}]
    with patch('agent.tools.agent_tools.load_records', side_effect=records):
        first = ''.join(agent.execute_stream('查询2032年11月覆盖率'))
        second = ''.join(agent.execute_stream('重新查询2032年11月覆盖率'))
    assert '77%' in first
    assert '77%' not in second and '91%' not in second and '80%' not in second
    assert '2032-11' in second and ('未查询' in second or '未查到' in second)


def test_target_can_be_an_earlier_successful_lookup_in_this_same_turn():
    target = record('2032-11', '80')
    baseline = record('2032-10', '75')
    intent = ReportIntent(fields=('覆盖率',), target_month='2032-11',
                          comparison_month='2032-10', compare=True, limited=True)
    text = render_lookup(baseline, intent=intent,
                         lookup_results=[record('2032-11', '77')],
                         current_results=[target, baseline])
    assert '80%' in text and '75%' in text and '增加5个百分点' in text
    assert '77%' not in text


def test_historical_baseline_still_supports_deterministic_delta():
    intent = ReportIntent(fields=('覆盖率',), target_month='2032-11',
                          comparison_month='2032-10', compare=True, limited=True)
    text = render_lookup(record('2032-11', '80'), intent=intent,
                         lookup_results=[record('2032-10', '70')])
    assert '80%' in text and '70%' in text and '增加10个百分点' in text


def test_explicit_absence_of_current_results_cannot_replay_old_target():
    cached = record('2032-11', '77')
    text = render_lookup(cached, query='重新查询2032年11月覆盖率',
                         lookup_results=[cached], current_results=[])
    assert '77%' not in text
    assert '2032-11' in text and ('未查询' in text or '未查到' in text)


def test_current_not_found_overrides_a_previously_found_target():
    missing = {'status': 'not_found', 'user_id': '1001', 'month': '2032-11'}
    text = render_lookup(missing, query='重新查询2032年11月覆盖率',
                         lookup_results=[record('2032-11', '77')], current_results=[missing])
    assert '未找到' in text
    assert '77%' not in text
