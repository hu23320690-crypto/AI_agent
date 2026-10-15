"""Scripted planner JSON drives the real graph, tools, policy and Runtime."""
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
import pytest

from agent.runtime import BudgetExceeded, ExecutionRuntime, RunLimits
from evaluation.service_trace import TurnTrace
from service_desk.planner import parse_plan
from test_core_flows import answer, call
from test_service_agent import db, seed_path, graph


def step(i, tool, args=None, deps=(), covers=('g1',), **extra):
    return {'id': f's{i}', 'tool': tool, 'args': args or {}, 'depends_on': list(deps),
            'covers': list(covers), **extra}


def goal(kind='order', id='g1', text='购买耗材'):
    return {'id': id, 'type': kind, 'text': text}


def device():
    return {'from_step': 's1', 'pick': 'only_device'}


def order_plan(qty=1, kind='filter', *, condition=None):
    steps = [step(1, 'list_my_devices'), step(2, 'find_consumables',
        {'device_id': device(), 'kind': {'enum': kind}}, ['s1'])]
    deps = ['s1', 's2']
    if condition:
        steps.append(step(3, 'fetch_external_data', {'month': {'value': '2025-12', 'evidence': '上个月'}}))
        deps.append('s3')
    steps.append(step(4, 'propose_order', {'device_id': device(),
        'sku': {'from_step': 's2', 'pick': 'consumable_kind', 'kind': kind},
        'qty': {'value': qty, 'evidence': f'{qty}个'}}, deps, condition=condition))
    return {'goals': [goal()], 'steps': steps, 'ask_user': None}


def warranty_plan():
    return {'goals': [goal('warranty', text='查询保修')], 'steps': [step(1, 'list_my_devices'),
            step(2, 'check_warranty', {'device_id': device()}, ['s1'])], 'ask_user': None}


def planned(monkeypatch, db, plans, *, suffix=(), **kwargs):
    monkeypatch.setenv('AGENT_MODE', 'plan')
    agent, model = graph(monkeypatch, db, [*[answer(json.dumps(p, ensure_ascii=False)) for p in plans], *suffix], **kwargs)
    agent.turn_trace = TurnTrace()
    return agent, model


def tools(agent):
    return [c['name'] for c in agent.turn_trace.snapshot()['tool_calls']]


def test_valid_plan_pending_card_and_history(monkeypatch, db):
    agent, _ = planned(monkeypatch, db, [order_plan()])
    text = ''.join(agent.execute_stream('买1个滤网'))
    assert '已为你准备订单的确认卡片' in text
    assert text.endswith('请在确认卡片上确认，确认前不会提交。')
    assert tools(agent) == ['list_my_devices', 'find_consumables', 'propose_order']
    assert [type(m) for m in agent.messages] == [HumanMessage, AIMessage]
    assert [m.content for m in agent.messages] == ['买1个滤网', text]
    assert agent.last_run['planner_calls'] == 1 and agent.last_run['counts']['model'] == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT status FROM pending_actions').fetchone()[0] == 'pending'
        assert conn.execute('SELECT count(*) FROM orders WHERE source_action_id IS NOT NULL').fetchone()[0] == 0


def test_validation_replan_fallback_same_run(monkeypatch, db):
    agent, _ = planned(monkeypatch, db, [{}, {}], suffix=[call('list_my_devices'), answer('设备如下。')])
    text = ''.join(agent.execute_stream('查设备'))
    assert '你的设备' in text and agent.last_run['plan_fallback']
    assert agent.last_run['planner_calls'] == 2 and agent.last_run['replans'] == 1
    assert agent.last_run['counts']['model'] == 4
    assert len({event['call_id'] for event in agent.last_run['events'] if event['event'] == 'call_started' and event['kind'] == 'run'}) == 1


def test_condition_false_does_not_dispatch_propose(monkeypatch, db):
    cond = {'type': 'record_threshold', 'from_step': 's3', 'field_hint': 'HEPA',
            'op': '<', 'value': 1, 'unit': '%', 'evidence': '低于1%'}
    agent, _ = planned(monkeypatch, db, [order_plan(condition=cond)], user='1001')
    text = ''.join(agent.execute_stream('上个月HEPA低于1%才买1个滤网'))
    assert '条件不成立' in text and '2025-12 HEPA 低于 1%' in text
    assert 'propose_order' not in tools(agent)
    assert agent.last_run['skipped_steps'] == 1 and agent.last_run['planner_calls'] == 1


@pytest.mark.parametrize('qty,kind,reason', [(1, 'mop_pad', '库存不足'), (3, 'filter', '数量超过单次限购')])
def test_precheck_skips_propose(monkeypatch, db, qty, kind, reason):
    agent, _ = planned(monkeypatch, db, [order_plan(qty, kind)])
    text = ''.join(agent.execute_stream(f'买{qty}个耗材'))
    assert reason in text and 'propose_order' not in tools(agent)
    assert agent.last_run['planner_calls'] == 1


def test_ambiguous_device_asks_and_does_not_replan(monkeypatch, db):
    agent, _ = planned(monkeypatch, db, [warranty_plan()], user='1020')
    text = ''.join(agent.execute_stream('查询保修'))
    assert '你有多台设备' in text and 'D-1020-01' in text and 'D-1020-02' in text
    assert tools(agent) == ['list_my_devices'] and agent.last_run['planner_calls'] == 1


def visit_plan():
    return {'goals': [goal('book', text='预约检查')], 'steps': [step(1, 'list_my_devices'),
        step(2, 'check_warranty', {'device_id': device()}, ['s1']),
        step(3, 'find_service_slots', {'device_id': device()}, ['s1']),
        step(4, 'propose_service_visit', {'device_id': device(), 'description': {'text': '运行异响'},
             'slot_id': {'from_step': 's3', 'pick': 'slot_at',
                'date': {'value': '2026-01-13', 'evidence': '明天'},
                'start': {'value': '09:00', 'evidence': '9点'}}}, ['s1', 's2', 's3'])], 'ask_user': None}


def test_unavailable_slot(monkeypatch, db):
    agent, _ = planned(monkeypatch, db, [visit_plan()])
    text = ''.join(agent.execute_stream('运行异响，预约明天9点'))
    assert '你指定的时段没有可约名额' in text
    assert 'propose_service_visit' not in tools(agent) and agent.last_run['planner_calls'] == 1


def test_verify_repairs_only_missing_with_reused_device(monkeypatch, db):
    first = warranty_plan()
    first['steps'] = first['steps'][:1]  # P5 coverage alone is insufficient evidence.
    repair = {'goals': first['goals'], 'steps': [step(2, 'check_warranty', {'device_id': device()}, ['s1'])]}
    agent, model = planned(monkeypatch, db, [first, repair])
    text = ''.join(agent.execute_stream('查保修'))
    assert '保修（D-1002-01' in text and '未能完成' not in text
    assert tools(agent) == ['list_my_devices', 'check_warranty']
    assert agent.last_run['planner_calls'] == 2 and agent.last_run['replans'] == 1
    feedback = json.loads(model.seen[1][-1].content)['feedback']
    assert feedback['missing_goals'] == first['goals'] and len(feedback['completed_results']) == 1


def test_verify_still_missing_reports_once(monkeypatch, db):
    first = warranty_plan()
    first['steps'] = first['steps'][:1]
    agent, _ = planned(monkeypatch, db, [first, {'goals': first['goals'], 'steps': []}])
    text = ''.join(agent.execute_stream('查保修'))
    assert '未能完成：查询保修' in text and agent.last_run['planner_calls'] == 2


def test_planner_budget_failure_commits_nothing(monkeypatch, db):
    limits = replace(RunLimits(), max_model_calls=1)
    agent, _ = planned(monkeypatch, db, [{}], limits=limits, executor=ExecutionRuntime(limits))
    with pytest.raises(BudgetExceeded):
        list(agent.execute_stream('查设备'))
    assert not agent.messages and agent.last_run['counts']['model'] == 1


@pytest.mark.parametrize('response', [AIMessage(content='{}', response_metadata={'done_reason': 'length'}),
    AIMessage(content='{"goals":'), AIMessage(content='{"a":1,"a":2}'), AIMessage(content='{"a":NaN}')])
def test_invalid_json_is_p1(monkeypatch, db, response):
    agent, model = planned(monkeypatch, db, [], suffix=[response, answer('{}'), answer('请重试。')])
    assert ''.join(agent.execute_stream('查设备')) == '请重试。'
    assert agent.last_run['plan_fallback'] and agent.last_run['planner_calls'] == 2
    assert all(e['codes'] == ['P1'] for e in agent.last_run['events'] if e['event'] == 'plan_validation')


def test_policy_and_trace_are_shared(monkeypatch, db):
    plan = warranty_plan()
    plan['steps'][1]['args']['device_id'] = {'value': 'D-1001-01', 'evidence': 'D-1001-01'}
    agent, _ = planned(monkeypatch, db, [plan, {'goals': plan['goals'], 'steps': []}])
    text = ''.join(agent.execute_stream('查D-1001-01保修'))
    assert '对象不属于当前用户' in text
    calls = agent.turn_trace.snapshot()['tool_calls']
    assert calls[-1]['content']['reason_code'] == 'identity_mismatch'
    assert agent.last_run['counts']['tool'] == 1  # denied before dispatch


def test_plan_history_two_turns(monkeypatch, db):
    agent, _ = planned(monkeypatch, db, [warranty_plan(), warranty_plan()])
    first = ''.join(agent.execute_stream('查保修'))
    second = ''.join(agent.execute_stream('再查一次'))
    assert [m.content for m in agent.messages] == ['查保修', first, '再查一次', second]


def test_invalid_verify_repair_fallback_keeps_completed_evidence(monkeypatch, db):
    first = warranty_plan()
    first['steps'] = first['steps'][:1]
    agent, model = planned(monkeypatch, db, [first, {}, {}], suffix=[answer('请补充保修需求。')])
    text = ''.join(agent.execute_stream('查保修'))
    assert '你的设备' in text and agent.last_run['plan_fallback']
    assert agent.last_run['planner_calls'] == 3 and agent.last_run['replans'] == 2
    assert tools(agent) == ['list_my_devices']
    assert any(m.type == 'tool' and m.name == 'list_my_devices' for m in model.seen[-1])


def test_ambiguous_slots_ask_which_slot(monkeypatch, db):
    from service_desk.tools import _read
    proposal = visit_plan()
    proposal['steps'][-1]['args']['slot_id']['start'] = {'value': '13:00', 'evidence': '13点'}
    def read(name, args, context, connection):
        result = _read(name, args, context, connection)
        if name == 'find_service_slots':
            slot = deepcopy(next(s for s in result['slots'] if s['start_at'].startswith('2026-01-13T13:00')))
            result['slots'].append({**slot, 'slot_id': slot['slot_id'] + '-extra'})
        return result
    agent, _ = planned(monkeypatch, db, [proposal])
    with patch('service_desk.tools._read', side_effect=read):
        text = ''.join(agent.execute_stream('运行异响，预约明天13点'))
    assert '请从下面的可约时段里选一个' in text and 'propose_service_visit' not in tools(agent)


def test_verify_cannot_add_new_work_for_completed_goal(monkeypatch, db):
    first = warranty_plan()
    first['goals'].append(goal('status', 'g2', '查进度'))
    first['steps'][0]['covers'].append('g2')
    repair = {'goals': [first['goals'][1]], 'steps': [step(3, 'check_warranty',
        {'device_id': device()}, ['s1'], covers=['g1'])]}
    agent, _ = planned(monkeypatch, db, [first, repair, repair], suffix=[answer('已查询现有资料。')])
    list(agent.execute_stream('查保修和进度'))
    assert agent.last_run['plan_fallback']
    assert tools(agent).count('check_warranty') == 1


def test_actual_tool_budget_shared_after_fallback(monkeypatch, db):
    limits = replace(RunLimits(), max_tool_calls=1)
    agent, _ = planned(monkeypatch, db, [{}, {}], suffix=[call('list_my_devices'),
        call('list_my_devices')], limits=limits, executor=ExecutionRuntime(limits))
    with pytest.raises(BudgetExceeded):
        list(agent.execute_stream('查设备'))
    assert agent.messages == [] and agent.last_run['counts']['tool'] == 1
    assert agent.last_run['plan_fallback']


def test_failed_read_repaired_without_repeating_success(monkeypatch, db):
    from service_desk.tools import _read
    first = warranty_plan()
    repair = {'goals': first['goals'], 'steps': [step(2, 'check_warranty', {'device_id': device()}, ['s1'])]}
    attempts = []
    def read(name, *args):
        if name == 'check_warranty':
            attempts.append(name)
            if len(attempts) == 1:
                raise ValueError('synthetic read failure')
        return _read(name, *args)
    agent, _ = planned(monkeypatch, db, [first, repair])
    with patch('service_desk.tools._read', side_effect=read):
        text = ''.join(agent.execute_stream('查保修'))
    assert len(attempts) == 2 and tools(agent).count('list_my_devices') == 1
    assert '保修（D-1002-01' in text and agent.last_run['replans'] == 1


def test_pending_card_arguments_can_be_reused(monkeypatch, db):
    second = {'goals': [goal()], 'steps': [
        step(1, 'find_consumables', {'device_id': {'from_pending': 'device_id', 'tool': 'propose_order'},
                                   'kind': {'enum': 'filter'}}),
        step(2, 'propose_order', {'device_id': {'from_pending': 'device_id', 'tool': 'propose_order'},
                                'sku': {'from_step': 's1', 'pick': 'consumable_kind', 'kind': 'filter'},
                                'qty': {'value': 2, 'evidence': '2个'}}, ['s1'])]}
    agent, model = planned(monkeypatch, db, [order_plan(), second])
    list(agent.execute_stream('买1个滤网'))
    agent.turn_trace = TurnTrace()
    text = ''.join(agent.execute_stream('改成2个'))
    assert '待确认：' in text and tools(agent) == ['find_consumables', 'propose_order']
    cards = json.loads(model.seen[1][-1].content)['pending_cards']
    assert cards[0]['args']['qty'] == 1
    with sqlite3.connect(db) as conn:
        assert sorted(row[0] for row in conn.execute('SELECT status FROM pending_actions')) == ['pending', 'superseded']
