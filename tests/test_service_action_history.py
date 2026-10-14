"""Card events are complete turns, never original user instructions."""
import json
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from agent.context_budget import ContextPolicy
from agent.context_memory import TurnMemoryPlan, split_complete_turns
from agent.react_agent import ReactAgent
from agent.runtime import RunBusy, RunContext
from test_context_memory import Request, SummaryModel, controlled_policy
from test_core_flows import ScriptedModel, answer, call


def make_agent(monkeypatch, responses=(), *, toolset='service', db=None):
    monkeypatch.setenv('AGENT_TOOLSET', toolset)
    return ReactAgent('1002', model=ScriptedModel(responses=list(responses)), service_db_path=db,
                      context_policy=ContextPolicy(window_tokens=32768, reserve_output_tokens=1024,
                                                   reasoning_enabled=False))


def result(status='executed'):
    return {'action_id': str(uuid4()), 'status': status, 'message': '已创建订单 O-test，处理中。'}


@pytest.mark.parametrize('status', ['executed', 'rejected', 'expired', 'superseded', 'failed'])
def test_card_event_appends_one_pair_and_replay_is_unchanged(monkeypatch, status):
    agent = make_agent(monkeypatch)
    value = result(status)
    assert agent.record_action_event(value) is True
    assert len(agent.messages) == 2
    human, ai = agent.messages
    assert isinstance(human, HumanMessage) and human.name == 'action_event'
    assert human.content == f"[卡片操作] {'拒绝' if status == 'rejected' else '确认'} {value['action_id']}"
    assert isinstance(ai, AIMessage) and ai.content == value['message'] and not ai.tool_calls
    before = list(agent.messages)
    assert agent.record_action_event(value) is False and agent.messages == before


def test_card_event_uses_requested_operation_for_terminal_reject(monkeypatch):
    agent = make_agent(monkeypatch)
    value = result('expired') | {'operation': 'reject'}
    agent.record_action_event(value)
    assert agent.messages[0].content == '[卡片操作] 拒绝 ' + value['action_id']


def test_busy_card_event_does_not_write_even_after_run_cancelled(monkeypatch):
    agent = make_agent(monkeypatch)
    run = agent._active_run = RunContext()
    for cancelled in (False, True):
        if cancelled:
            run.cancel()
        with pytest.raises(RunBusy):
            agent.record_action_event(result())
        assert agent.messages == [] and agent._recorded_action_events == set()


def test_record_card_event_holds_state_lock(monkeypatch):
    agent = make_agent(monkeypatch)
    entered, finished = Event(), Event()

    def write():
        entered.set()
        agent.record_action_event(result())
        finished.set()

    with agent._state_lock:
        thread = Thread(target=write)
        thread.start()
        assert entered.wait(2)
        assert not finished.wait(.05) and agent.messages == []
    thread.join(2)
    assert finished.is_set() and len(agent.messages) == 2


def test_legacy_card_event_is_disabled(monkeypatch):
    agent = make_agent(monkeypatch, toolset='legacy')
    with pytest.raises(ValueError, match='service_disabled'):
        agent.record_action_event(result())
    assert agent.messages == []


@pytest.mark.parametrize('value', [{}, result('denied'), result() | {'message': None},
                                  result() | {'operation': 'execute'}])
def test_invalid_card_result_does_not_write(monkeypatch, value):
    agent = make_agent(monkeypatch)
    with pytest.raises(ValueError):
        agent.record_action_event(value)
    assert agent.messages == []


def test_card_event_is_excluded_from_rag_user_history(monkeypatch):
    agent = make_agent(monkeypatch)
    agent.messages = [HumanMessage(content='原来的用户问题'), answer('原来的回答')]
    value = result()
    agent.record_action_event(value)
    captured = {}

    class Graph:
        def invoke(self, state, **kwargs):
            captured.update(kwargs['context'])
            return {'messages': [*state['messages'], answer('回答')]}

    agent.agent = Graph()
    list(agent.execute_stream('下一问'))
    assert captured['rag_user_history'] == ['原来的用户问题']
    assert value['message'] in [m.content for m in agent.messages]


def test_card_event_is_excluded_from_intent_history(monkeypatch, tmp_path):
    import agent.react_agent as module
    original = module.resolve_turn_intent
    from service_desk.db import init_db
    db = init_db(tmp_path / 'service.db')
    agent = make_agent(monkeypatch, [call('fetch_external_data', month='2025-12'), answer('无关文本')], db=db)
    agent.messages = [HumanMessage(content='生成2025-11的报告'), answer('已记录')]
    agent.record_action_event(result())
    seen = {}

    def capture(query, **kwargs):
        seen.update(kwargs)
        return original(query, **kwargs)

    with patch.object(module, 'resolve_turn_intent', side_effect=capture):
        list(agent.execute_stream('改查2025-12的报告'))
    assert seen['history_queries'] == seen['llm_history_queries'] == ['生成2025-11的报告']


def test_card_event_not_in_summary_user_references_or_summary_input(monkeypatch):
    agent = make_agent(monkeypatch)
    value = result()
    agent.record_action_event(value)
    agent.messages.extend([HumanMessage(content='用户希望查询订单'), answer('已查询')])
    plan = TurnMemoryPlan(agent.messages, policy=controlled_policy(), summary_model=SummaryModel(), run=RunContext())
    turns = split_complete_turns(agent.messages)
    plan._preserve_references(turns)
    assert plan.summary['task_references'] == ['用户希望查询订单']
    request = plan._summary_request(SummaryModel(), turns)
    payload = json.loads(request.messages[-1].content)
    assert '[卡片操作]' not in request.messages[-1].content
    assert value['message'] in str(payload['completed_turns'])
    assert payload['task_references'] == ['用户希望查询订单']


def test_history_compression_keeps_complete_card_and_tool_turns(monkeypatch):
    agent = make_agent(monkeypatch)
    agent.messages = [HumanMessage(content='原目标 ' + 'x' * 3000), answer('旧回答 ' + 'y' * 3000)]
    first = result()
    agent.record_action_event(first)
    agent.messages.extend([
        HumanMessage(content='查订单'), AIMessage(content='', tool_calls=[{'id': 't', 'name': 'read', 'args': {}}]),
        ToolMessage(content='订单处理中', tool_call_id='t'), answer('查完'),
    ])
    policy = controlled_policy(window_tokens=4000, keep_recent_turns=2, summary_enabled=False)
    plan = TurnMemoryPlan(agent.messages, policy=policy, summary_model=SummaryModel(), run=RunContext())
    current = HumanMessage(content='继续')
    plan.prepare_request(Request([*agent.messages, current]))
    committed = plan.committed_messages([*agent.messages, current, answer('新回答')])
    turns = split_complete_turns(committed)
    assert plan.stats['dropped_turns'] >= 1
    card = next(turn for turn in turns if turn[0].name == 'action_event')
    assert len(card) == 2 and card[1].content == first['message']
    tool_turn = next(turn for turn in turns if turn[0].content == '查订单')
    assert len(tool_turn) == 4 and tool_turn[2].tool_call_id == tool_turn[1].tool_calls[0]['id']
    assert '[卡片操作]' not in str(plan.summary)
    agent.messages = committed
    assert agent.record_action_event(first) is False


def test_clear_history_clears_card_event_pairs(monkeypatch):
    agent = make_agent(monkeypatch)
    agent.record_action_event(result())
    agent.clear_history()
    assert agent.messages == [] and agent._recorded_action_events == set()
