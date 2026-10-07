"""Verified report state survives follow-ups and rolls back failed turns."""
from unittest.mock import patch

import pytest

from agent.react_agent import ReactAgent
from test_core_flows import ScriptedModel, answer, call, scripted_context_policy


def data(coverage, area):
    return {'特征': '测试房屋', '效率': f'覆盖率:{coverage}%\\n日均清扫:{area}㎡',
            '耗材': '滤网寿命:剩余30天', '对比': '本地测试记录'}


def test_selected_fields_and_delta_use_verified_committed_values():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2024-12'), answer('覆盖率999%'),
        call('fetch_external_data', user_id='1001', month='2025-01'), answer('增加100%'),
    ])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    records = {('1001', '2024-12'): data('77.5', '31.2'),
               ('1001', '2025-01'): data('80', '33.7')}
    with patch('agent.tools.agent_tools.load_records', return_value=records):
        first = ''.join(agent.execute_stream('查2024年12月覆盖率和日均清扫面积，只需要这两个数。'))
        assert '77.5%' in first and '31.2㎡' in first
        assert '999' not in first and '滤网' not in first and '测试房屋' not in first
        second = ''.join(agent.execute_stream('下一月这两项是多少，与刚才相比变化多少？'))
    assert '增加2.5个百分点' in second and '增加2.5㎡' in second
    assert '100%' not in second and '滤网' not in second
    assert len(agent._lookup_records) == 2
    assert agent.messages[-1].content == second
    agent.clear_history()
    assert agent._lookup_records == []
    assert agent._report_intent is None


def test_lookup_from_failed_turn_does_not_become_comparison_evidence():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2024-12'), answer('完成'),
        call('fetch_external_data', user_id='1001', month='2025-01'), RuntimeError('model unavailable'),
    ])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    records = {('1001', '2024-12'): data('77', '31'), ('1001', '2025-01'): data('80', '34')}
    with patch('agent.tools.agent_tools.load_records', return_value=records):
        list(agent.execute_stream('查询2024-12覆盖率'))
        before = list(agent.messages)
        before_intent = agent._report_intent
        with pytest.raises(RuntimeError):
            list(agent.execute_stream('查询2025-01覆盖率'))
    assert agent.messages == before
    assert agent._report_intent == before_intent
    assert [row['month'] for row in agent._lookup_records] == ['2024-12']


def test_comparison_does_not_use_fabricated_assistant_history_or_other_session():
    from langchain_core.messages import HumanMessage
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2025-01'), answer('增加100%')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    agent.messages = [HumanMessage(content='查2024-12覆盖率'), answer('覆盖率99%')]
    with patch('agent.tools.agent_tools.load_records', return_value={('1001', '2025-01'): data('80', '34')}):
        result = ''.join(agent.execute_stream('查询2025-01覆盖率，比上月变化多少？'))
    assert '无法计算变化' in result
    assert '99%' not in result and '增加' not in result
    isolated = ReactAgent('1001', model=ScriptedModel(responses=[]), context_policy=scripted_context_policy())
    assert isolated._lookup_records == []


def test_relative_month_state_survives_compression_without_duplicate_advancement():
    from dataclasses import replace
    from langchain_core.messages import HumanMessage
    responses = []
    for month in ['2032-10', '2032-11', '2032-12', '2033-01']:
        responses.extend([call('fetch_external_data', user_id='1001', month=month), answer('完成')])
    model = ScriptedModel(responses=responses)
    agent = ReactAgent('1001', model=model,
                       context_policy=replace(scripted_context_policy(), summary_enabled=False))
    records = {('1001', month): data(str(70 + i), '30')
               for i, month in enumerate(['2032-10', '2032-11', '2032-12', '2033-01'])}
    with patch('agent.tools.agent_tools.load_records', return_value=records):
        list(agent.execute_stream('2032年10月只列覆盖率'))
        list(agent.execute_stream('下一月覆盖率'))
        list(agent.execute_stream('下一月覆盖率'))
        # Simulate a genuine long suffix after the report turns. Runtime must
        # compress it, while the resolved month remains program-owned state.
        for index in range(8):
            agent.messages.extend([HumanMessage(content=f'准备进度{index}：' + '整理笔记。' * 160), answer('已记录')])
        result = ''.join(agent.execute_stream('下一月覆盖率，与上月相比变化多少？'))
    assert '2033-01 与 2032-12' in result
    assert '增加1个百分点' in result
    assert agent._report_intent.target_month == '2033-01'
    assert any(event['event'] == 'context_history_reduced' for event in agent.last_run['events'])
    references = [message for message in model.seen[-2]
                  if message.name == 'report_selection_reference']
    assert len(references) == 1
    import json
    assert json.loads(references[0].content)['previous_report_selection']['target_month'] == '2032-12'


def test_optional_report_reference_cannot_block_an_admissible_new_question():
    from dataclasses import asdict
    from langchain_core.messages import HumanMessage
    from agent.context_memory import TurnMemoryPlan
    from agent.context_budget import ContextPolicy, estimate_request
    from utils.report_intent import ReportIntent
    from test_context_memory import Request, new_run
    request = Request(messages=[HumanMessage(content='new unrelated task')])
    current_size = estimate_request(request.messages, request.tools, request.system_message, model=request.model)
    policy = ContextPolicy(window_tokens=current_size + 64 + 16, reserve_output_tokens=64,
                           summary_max_tokens=32, safety_margin_tokens=0)
    plan = TurnMemoryPlan([], policy=policy, summary_model=None, run=new_run(),
                          report_reference=asdict(ReportIntent(fields=('coverage', 'area'),
                                                              target_month='2032-12')))
    view = plan.prepare_request(request)
    assert view.messages == request.messages
    assert plan.stats['report_reference_removed'] is True


def test_report_reference_has_its_own_size_bound():
    from langchain_core.messages import HumanMessage
    from agent.context_memory import TurnMemoryPlan
    from test_context_memory import Request, new_run
    reference = {'fields': ['field-' + 'x' * 200 for _ in range(100)], 'target_month': '2032-12'}
    plan = TurnMemoryPlan([], policy=scripted_context_policy(), summary_model=None,
                          run=new_run(), report_reference=reference)
    view = plan.prepare_request(Request(messages=[HumanMessage(content='new task')]))
    import json
    selected = json.loads(view.messages[0].content)['previous_report_selection']
    assert len(json.dumps(selected, ensure_ascii=False).encode('utf-8')) <= 1024
