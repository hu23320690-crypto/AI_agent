from copy import deepcopy

import pytest

from service_desk import plan_core, planner
from service_desk.render import guard_text
from test_service_reads import seed_path, read
from test_service_agent import db, graph
from test_service_plan_agent import visit_plan, planned


def test_legacy_does_not_import_service_signals(monkeypatch):
    from agent.react_agent import ReactAgent
    from test_core_flows import ScriptedModel, answer, scripted_context_policy
    from service_desk import signals
    def fail(*args, **kwargs):
        raise AssertionError('legacy must not use service signals')
    monkeypatch.setattr(signals, 'recognize', fail)
    monkeypatch.setenv('AGENT_TOOLSET', 'legacy')
    monkeypatch.setenv('AGENT_MODE', 'react')
    model = ScriptedModel(responses=[answer('30秒内有效。')])
    agent = ReactAgent(model=model, context_policy=scripted_context_policy())
    assert ''.join(agent.execute_stream('如果还在保才预约，并说明步骤')) == '30秒内有效。'


