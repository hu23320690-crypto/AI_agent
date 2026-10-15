"""Denied card context must not crash a turn or weaken tool authorization."""
from unittest.mock import patch

from langchain_core.messages import HumanMessage, AIMessage
import pytest

from test_core_flows import answer, call
from test_service_agent import db, seed_path, graph


@pytest.mark.parametrize('user', ['', 'unregistered-user'])
def test_plan_denied_card_context_uses_existing_react_path(monkeypatch, db, user):
    monkeypatch.setenv('AGENT_MODE', 'plan')
    agent, _ = graph(monkeypatch, db, [answer('你好，请先设置演示用户。')], user=user)
    text = ''.join(agent.execute_stream('早上好'))
    assert text == '你好，请先设置演示用户。'
    assert agent.last_run['planner_calls'] == 0
    assert agent.last_run['plan_fallback']
    assert agent.last_run['counts']['model'] == 1
    assert agent.last_run['counts'].get('tool', 0) == 0
    assert any(e['event'] == 'plan_card_context_denied' for e in agent.last_run['events'])
    assert [type(m) for m in agent.messages] == [HumanMessage, AIMessage]
    assert [m.content for m in agent.messages] == ['早上好', text]


@pytest.mark.parametrize('user', ['', 'unregistered-user'])
def test_plan_identity_fallback_still_denies_protected_reads(monkeypatch, db, user):
    monkeypatch.setenv('AGENT_MODE', 'plan')
    agent, _ = graph(monkeypatch, db, [call('check_warranty', device_id='D-1002-01'),
        answer('请先设置演示用户。')], user=user)
    with patch('service_desk.tools._read', side_effect=AssertionError('must not reach database read')) as read:
        text = ''.join(agent.execute_stream('查询保修'))
    read.assert_not_called()
    assert '安全检查' in text
    observed = agent.turn_trace.snapshot()['tool_calls']
    assert len(observed) == 1 and observed[0]['status'] == 'error'
    assert observed[0]['content']['status'] == 'denied'
    assert agent.last_run['planner_calls'] == 0 and agent.last_run['plan_fallback']
