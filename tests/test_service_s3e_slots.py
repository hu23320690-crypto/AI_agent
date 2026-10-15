from copy import deepcopy

import pytest

from service_desk import plan_core, planner
from service_desk.render import guard_text
from test_service_reads import seed_path, read
from test_service_agent import db, graph
from test_service_plan_agent import visit_plan, planned


def test_slot_limit_and_earliest_dates(seed_path):
    for args in ({}, {'from_date': '2026-01-18'}):
        result = read(seed_path, 'find_service_slots', device_id='D-1002-01', **args)
        assert len(result['slots']) == 6
        assert result['slots'] == sorted(result['slots'], key=lambda s: (s['start_at'], s['slot_id']))
        assert result['slots'][0]['start_at'][:10] == args.get('from_date', '2026-01-13')
    # Schema and response envelope stay unchanged; zero slots is still valid.
    assert read(seed_path, 'find_service_slots', device_id='D-1002-01', from_date='2027-01-01')['slots'] == []


def test_executor_auto_target_date(monkeypatch, db):
    p = visit_plan()
    source = p['steps'][-1]['args']['slot_id']
    source['date'] = {'value': '2026-01-18', 'evidence': '1月18日'}
    source['start'] = {'value': '13:00', 'evidence': '13点'}
    agent, _ = planned(monkeypatch, db, [p])
    answer = ''.join(agent.execute_stream('运行异响，预约1月18日13点'))
    calls = agent.turn_trace.snapshot()['tool_calls']
    assert next(c for c in calls if c['name'] == 'find_service_slots')['args']['from_date'] == '2026-01-18'
    assert calls[-1]['name'] == 'propose_service_visit'
    assert '确认卡片' in answer
