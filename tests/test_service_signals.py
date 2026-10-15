from copy import deepcopy

import pytest

from service_desk.signals import recognize, validate_signals
from test_service_plan_agent import order_plan, warranty_plan, planned, tools
from test_service_agent import db, seed_path, graph
from test_core_flows import answer


@pytest.mark.parametrize('text,component', [
    ('在保才预约', 'whole_machine'), ('如果还在保，请安排检查', 'whole_machine'),
    ('只有整机还在保才安排', 'whole_machine'), ('若还在保，预约', 'whole_machine'),
    ('电池在保的话才处理', 'battery')])
def test_warranty_condition_positive(text, component):
    assert recognize(text)['conditions'] == [{'type': 'warranty_in_force', 'component': component}]


@pytest.mark.parametrize('text', ['查一下是不是还在保', '过保也预约', '在保不代表免费', '有现货就买', '限购是多少', '如果不在保也预约'])
def test_warranty_condition_negative(text):
    assert recognize(text)['conditions'] == []


@pytest.mark.parametrize('phrase,op', [('不高于', '<='), ('不超过', '<='), ('低于', '<'), ('高于', '>'), ('不低于', '>=')])
@pytest.mark.parametrize('unit', ['%', '天'])
def test_threshold_condition(phrase, op, unit):
    signal = recognize(f'上月滤网剩余{phrase}17{unit}才买')['conditions'][0]
    assert signal['op'] == op and signal['value'] == 17 and signal['unit'] == unit
    assert recognize(f'上月剩余{phrase}17{unit}')['conditions'] == []


@pytest.mark.parametrize('text,expected', [('请查处理方法', True), ('请说明安全注意事项', True),
    ('给出步骤', True), ('解释政策', True), ('不要说明，只查日期', False),
    ('不用解释政策', False), ('不要解释，但请给出清洁步骤', True), ('买一个滤网', False)])
def test_knowledge_recognition(text, expected):
    assert recognize(text)['knowledge_requested'] is expected


def test_p9_matches_warranty_component_and_numeric_constraints():
    p = order_plan()
    signals = recognize('电池在保才买')
    assert {e['code'] for e in validate_signals(p, signals)} == {'P9'}
    p['steps'][-1]['condition'] = {'type': 'warranty_in_force', 'component': 'whole_machine'}
    assert validate_signals(p, signals)
    p['steps'][-1]['condition']['component'] = 'battery'
    assert not validate_signals(p, signals)
    signal = recognize('HEPA剩余不高于17%才买')
    cond = {'type': 'record_threshold', 'op': '<=', 'value': 17, 'unit': '%', 'field_hint': 'HEPA'}
    p['steps'][-1]['condition'] = cond
    assert not validate_signals(p, signal)
    for key, value in [('op', '<'), ('value', 18), ('unit', '天'), ('field_hint', '电池')]:
        changed = deepcopy(p)
        changed['steps'][-1]['condition'][key] = value
        assert validate_signals(changed, signal)[0]['code'] == 'P9'
    assert not validate_signals(warranty_plan(), signals)  # no writes


def test_p10_requires_goal_and_step():
    p = warranty_plan()
    signals = recognize('说明操作步骤')
    assert validate_signals(p, signals)[0]['code'] == 'P10'
    p['goals'].append({'id': 'g2', 'type': 'knowledge', 'text': '步骤'})
    assert validate_signals(p, signals)[0]['code'] == 'P10'
    p['steps'].append({'id': 's3', 'tool': 'rag_summarize'})
    assert not validate_signals(p, signals)
    assert not validate_signals(warranty_plan(), recognize('查保修'))


def test_react_prompt_and_planner_receive_identical_signals(monkeypatch, db):
    text = '电池在保才买1个滤网，并说明更换步骤'
    monkeypatch.setenv('AGENT_MODE', 'react')
    agent, model = graph(monkeypatch, db, [answer('请稍候。')])
    list(agent.execute_stream(text))
    prompt = model.seen[0][0].content
    assert '本轮用户附带条件：电池在保。提议前必须先核对，条件不成立就不要提议。' in prompt
    assert '本轮用户要求说明：必须调用 rag_summarize。' in prompt
    agent, model = planned(monkeypatch, db, [{}, {}], suffix=[answer('请重试。')])
    list(agent.execute_stream(text))
    import json
    assert json.loads(model.seen[0][-1].content)['service_signals'] == recognize(text)


def test_p9_p10_reach_planner_feedback_before_any_proposal(monkeypatch, db):
    p = order_plan()
    agent, model = planned(monkeypatch, db, [p, p], suffix=[answer('请补充。')])
    list(agent.execute_stream('在保才买1个滤网，并说明更换步骤'))
    assert not tools(agent)
    import json
    errors = json.loads(model.seen[1][-1].content)['feedback']['validation_errors']
    assert {'P9', 'P10'} <= {e['code'] for e in errors}
    assert agent.last_run['plan_fallback']


@pytest.mark.parametrize('query,expected', [
    ('这台机器能自己越过台阶吗？', True), ('这个型号会自动识别地毯吗？', True),
    ('设备支持多地图吗？', True), ('明天能安排检查吗？', False),
    ('设备能预约吗？', False)])
def test_product_capability_questions_are_knowledge(query, expected):
    assert recognize(query)['knowledge_requested'] is expected
