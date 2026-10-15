from copy import deepcopy

import pytest

from service_desk import plan_core as core
from test_service_plan_agent import order_plan, warranty_plan, visit_plan, planned, tools
from test_service_agent import db, seed_path


CTX = {'business_date': '2026-01-12', 'user_text': '买两个滤网，明天下午三点，E07，上个月',
       'history_user_texts': []}


@pytest.mark.parametrize('tool,name,value', [
    ('check_warranty', 'component', 'battery'), ('get_daily_usage', 'metric', 'area_m2'),
    ('find_consumables', 'kind', 'filter'), ('propose_change', 'change', 'reschedule')])
@pytest.mark.parametrize('wrapped', [False, True])
def test_normalize_enums_only_known_values(tool, name, value, wrapped):
    raw = {'value': value, 'evidence': ''} if wrapped else value
    plan = {'steps': [{'id': 's1', 'tool': tool, 'args': {name: raw}}]}
    fixed, changes = core.normalize_plan(plan, CTX)
    assert fixed['steps'][0]['args'][name] == {'enum': value}
    assert [c['type'] for c in changes] == ['enum']
    assert plan['steps'][0]['args'][name] == raw  # caller unchanged
    plan['steps'][0]['args'][name] = {'value': 'invented', 'evidence': ''}
    assert core.normalize_plan(plan, CTX) == (plan, [])


@pytest.mark.parametrize('pick,fields', [
    ('record', {'kind': 'order', 'status': 'processing'}),
    ('consumable_kind', {'kind': 'filter'})])
def test_nested_enums_round_trip(pick, fields):
    source = {'from_step': 's1', 'pick': pick, **fields}
    plan = {'steps': [{'id': 's2', 'tool': 'propose_change', 'args': {'target_id': source}}]}
    fixed, changes = core.normalize_plan(plan, CTX)
    actual = fixed['steps'][0]['args']['target_id']
    assert all(actual[k] == {'enum': v} for k, v in fields.items())
    assert len(changes) == len(fields)
    assert isinstance(core._parse_arg_source(actual), core.RecordPickArg if pick == 'record' else core.ConsumablePickArg)
    source['kind'] = 'invented'
    assert core.normalize_plan(plan, CTX)[0]['steps'][0]['args']['target_id']['kind'] == 'invented'


@pytest.mark.parametrize('count', [0, 1, 2])
@pytest.mark.parametrize('condition', [False, True])
def test_reference_unique_prior_tool_only(count, condition):
    tool = 'check_warranty' if condition else 'list_my_devices'
    source = {'type': 'warranty_in_force', 'component': 'whole_machine', 'from_step': 's9'} if condition else {
        'pick': 'only_device', 'from_step': 's9'}
    earlier = [{'id': f's{i+1}', 'tool': tool, 'args': {}} for i in range(count)]
    last = {'id': 's8', 'tool': 'propose_order', 'args': {}, 'depends_on': []}
    last['condition' if condition else 'args'] = source if condition else {'device_id': source}
    plan = {'steps': [*earlier, {'id': 's9', 'tool': 'find_consumables', 'args': {}}, last]}
    fixed, changes = core.normalize_plan(plan, CTX)
    if count == 1:
        assert len(changes) == 1 and changes[0]['type'] == 'reference'
        assert fixed['steps'][-1]['depends_on'] == ['s1']
    else:
        assert fixed == plan and not changes


@pytest.mark.parametrize('name,value,evidence', [
    ('qty', 2, '两个'), ('code', 'E07', 'E07'), ('error_code', 'E07', 'E07'),
    ('from_date', '2026-01-13', '明天'), ('month', '2025-12', '上个月')])
def test_evidence_unique_fragment_and_not_invented(name, value, evidence):
    p = {'steps': [{'id': 's1', 'tool': 'lookup_error_code', 'args': {name: {'value': value, 'evidence': ''}}}]}
    fixed, changes = core.normalize_plan(p, CTX)
    assert fixed['steps'][0]['args'][name] == {'value': value, 'evidence': evidence}
    assert changes[0]['type'] == 'evidence'
    assert core.normalize_plan(p, {**CTX, 'user_text': ''}) == (p, [])
    assert core.normalize_plan(p, {**CTX, 'history_user_texts': [CTX['user_text']]}) == (p, [])


def test_nested_time_date_and_ids_no_literal_slot_escape():
    p = visit_plan()
    source = p['steps'][-1]['args']['slot_id']
    source['date']['evidence'] = ''
    source['start'] = {'value': '15:00', 'evidence': 'missing'}
    fixed, changes = core.normalize_plan(p, CTX)
    assert source['date']['value'] == fixed['steps'][-1]['args']['slot_id']['date']['value']
    assert fixed['steps'][-1]['args']['slot_id']['start']['evidence'] == '下午三点'
    assert len(changes) == 2
    p['steps'][-1]['args']['slot_id'] = {'value': 'S-made-up', 'evidence': ''}
    fixed, _ = core.normalize_plan(p, {**CTX, 'user_text': 'S-made-up'})
    assert fixed['steps'][-1]['args']['slot_id']['evidence'] == ''
    assert not core.validate_plan(fixed, CTX)['ok']


@pytest.mark.parametrize('name', ['id', 'target_id', 'device_id'])
def test_id_evidence_only_exact_unique_user_identifier(name):
    p = {'steps': [{'id': 's1', 'tool': 'get_my_orders_and_tickets', 'args': {name: {'value': 'O-123', 'evidence': ''}}}]}
    assert core.normalize_plan(p, {**CTX, 'user_text': '查O-123'})[0]['steps'][0]['args'][name]['evidence'] == 'O-123'
    for text in ('查O-1234', '查123', 'O-123和O-123'):
        assert core.normalize_plan(p, {**CTX, 'user_text': text}) == (p, [])


def test_graph_normalization_is_counted_and_validated(monkeypatch, db):
    p = order_plan()
    p['steps'][1]['args']['kind'] = 'filter'
    p['steps'][-1]['args']['qty']['evidence'] = ''
    agent, _ = planned(monkeypatch, db, [p])
    text = ''.join(agent.execute_stream('买1个滤网'))
    assert '确认卡片' in text and tools(agent)[-1] == 'propose_order'
    assert agent.last_run['plan_normalizations'] == 3  # kind, pick.kind, qty
    events = [e for e in agent.last_run['events'] if e['event'] == 'plan_normalization']
    assert len(events) == 3 and {e['type'] for e in events} == {'enum', 'evidence'}
