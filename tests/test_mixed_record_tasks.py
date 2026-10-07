"""A numeric report must not erase a requested evidence or knowledge subtask."""
from unittest.mock import patch

import pytest

from agent.react_agent import ReactAgent
from test_core_flows import ScriptedModel, answer, call, scripted_context_policy


def data(fields):
    return {'特征': '测试房屋', '效率': '\\n'.join(f'{k}:{v}' for k, v in fields.items()),
            '耗材': '', '对比': '测试记录'}


def test_record_render_preserves_the_requested_distinct_measurement_boundary():
    model = ScriptedModel(responses=[call('fetch_external_data', user_id='1001', month='2031-06'),
                                     answer('已经达到维修门槛，整机检测合格，立即拆电机。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'容量衰减': '35%', '人工干预占比': '65%'})}):
        reply = ''.join(agent.execute_stream('查2031年6月，只列容量衰减和人工干预占比；'
            '这些记录能否直接证明实际运转时长已达到维护门槛？不要把不同指标当同一量。'))
    assert '35%' in reply and '65%' in reply
    assert '尚不足以确认' in reply and '不同名称' in reply
    assert '整机检测合格' not in reply and '立即拆电机' not in reply
    assert len(agent.last_run['events']) > 0
    assert agent.messages[-1].content == reply


def test_an_explicit_same_quantity_condition_can_be_supported_by_actual_data():
    model = ScriptedModel(responses=[call('fetch_external_data', user_id='1001', month='2031-06'),
                                     answer('猜测覆盖率只有10%，不达标。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}):
        reply = ''.join(agent.execute_stream('查2031年6月覆盖率；这些记录能否证明覆盖率高于75%？'))
    assert '80%' in reply and '数值满足' in reply
    assert '10%' not in reply and '尚不足以确认' not in reply


def test_report_and_a_successful_knowledge_subtask_are_both_delivered():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-06'),
        call('rag_summarize', query='净化器滤材清理步骤是什么？'),
        answer('无据的改写：全年换一次，费用999元。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}), \
            patch('agent.tools.agent_tools.get_rag_service') as service:
        service.return_value.rag_summarize.return_value = '资料给出的清理步骤：先断开电源，再擦拭滤材。'
        reply = ''.join(agent.execute_stream('查2031年6月覆盖率，只列这一项；另外说明净化器滤材如何清理。'))
    assert '80%' in reply and '先断开电源，再擦拭滤材' in reply
    assert '999元' not in reply and '全年' not in reply


@pytest.mark.parametrize('subquestion', [
    '另外解释覆盖率的含义。',
    '覆盖率的定义是什么？',
    '覆盖率的含义？',
    '什么是覆盖率？',
    '覆盖率代表什么？',
    '覆盖率表示什么？',
    '先不解释，改为解释覆盖率的含义。',
    '不用解释寿命，但说明覆盖率的定义。',
])
def test_report_keeps_the_successful_explicit_definition_subtask(subquestion):
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-06'),
        call('rag_summarize', query='覆盖率的定义是什么？'),
        answer('覆盖率意味着整机检测全部合格。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}), \
            patch('agent.tools.agent_tools.get_rag_service') as service:
        service.return_value.rag_summarize.return_value = '资料定义：覆盖率为已覆盖面积占计划清洁面积的比例。'
        reply = ''.join(agent.execute_stream('查询2031年6月，只列覆盖率；' + subquestion))
    assert '80%' in reply and '资料定义：覆盖率为' in reply
    assert '整机检测全部合格' not in reply


@pytest.mark.parametrize('query', [
    '查询2031年6月，只列覆盖率。',
    '查询2031年6月，只列覆盖率，不解释含义。',
    '查询2031年6月，只列覆盖率，不要输出含义解释。',
    '查询2031年6月，只列覆盖率，不解释耗材更换周期的含义。',
    '查询2031年6月，定义字段：只列覆盖率。',
])
def test_an_unsolicited_definition_tool_call_does_not_expand_a_plain_report(query):
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-06'),
        call('rag_summarize', query='覆盖率的定义是什么？'), answer('完成')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}), \
            patch('agent.tools.agent_tools.get_rag_service') as service:
        service.return_value.rag_summarize.return_value = '不应追加的定义内容。'
        reply = ''.join(agent.execute_stream(query))
    assert reply == '演示用户 1001，2031-06：\n- 覆盖率：80%'


@pytest.mark.parametrize('suffix', ['', '，不解释含义', '，不必补充周期解释'])
def test_a_field_named_replacement_cycle_is_still_a_plain_selected_field_report(suffix):
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-06'),
        call('rag_summarize', query='耗材更换周期的定义是什么？'), answer('完成')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'耗材更换周期': '30天'})}), \
            patch('agent.tools.agent_tools.get_rag_service') as service:
        service.return_value.rag_summarize.return_value = '不应追加的周期解释。'
        reply = ''.join(agent.execute_stream('查询2031年6月，只列耗材更换周期' + suffix))
    assert reply == '演示用户 1001，2031-06：\n- 耗材更换周期：30天'


def test_a_failed_knowledge_subtask_is_not_hidden_by_a_successful_report():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-06'),
        call('rag_summarize', query='净化器滤材清理步骤是什么？'), answer('所有子任务都成功了。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}), \
            patch('agent.tools.agent_tools.get_rag_service', side_effect=ConnectionError('offline')):
        reply = ''.join(agent.execute_stream('查2031年6月覆盖率；另外说明净化器滤材如何清理。'))
    assert '80%' in reply and '本轮知识查询未完成' in reply
    assert '所有子任务都成功' not in reply


def test_a_simple_selected_field_report_does_not_get_unsolicited_boundary_prose():
    model = ScriptedModel(responses=[call('fetch_external_data', user_id='1001', month='2031-06'),
                                     answer('泛泛分析')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-06'): data({'覆盖率': '80%'})}):
        reply = ''.join(agent.execute_stream('2031年6月只列覆盖率'))
    assert reply == '演示用户 1001，2031-06：\n- 覆盖率：80%'


def test_an_unanchored_relative_month_does_not_commit_a_tool_guessed_selector():
    model = ScriptedModel(responses=[
        call('fetch_external_data', user_id='1001', month='2031-07'), answer('完成'),
        call('fetch_external_data', user_id='1001', month='2031-08'), answer('完成')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    with patch('agent.tools.agent_tools.load_records', return_value={
            ('1001', '2031-07'): data({'覆盖率': '81%'}),
            ('1001', '2031-08'): data({'覆盖率': '82%'})}):
        first = ''.join(agent.execute_stream('下一月覆盖率是多少？'))
        assert agent._report_intent.unresolved_month is True
        assert agent._report_intent.target_month is None
        second = ''.join(agent.execute_stream('继续下一月覆盖率是多少？'))
    assert '81%' not in first and '82%' not in second
    assert agent._report_intent.unresolved_month is True
    assert agent._report_intent.target_month is None
