from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from agent.react_agent import ReactAgent
from rag.rag_service import EvidenceCheck
from rag.security import KnowledgeAccessError
from test_core_flows import ScriptedModel, answer, scripted_context_policy


@pytest.mark.parametrize('revoked', [False, True])
def test_changed_condition_guarantee_cannot_depend_on_planner_retrieval_choice(revoked):
    store = MagicMock()
    evidence = Document(page_content='只要设备已连接网络且完成设置，控制端离线后仍按预设工作。',
                        metadata={'source_id': 'approved', 'source_version': 1})
    model = ScriptedModel(responses=[answer('保证设备未联网也能正常工作，完全没有限制。')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    agent.messages = [HumanMessage(content='控制端离线后是否执行？'), answer('设备联网且已设置时可以。')]
    agent._history_checks = [EvidenceCheck(store, evidence)]
    if revoked:
        store.validate_documents.side_effect = KnowledgeAccessError('source revoked')
    result = ''.join(agent.execute_stream('能保证设备未连接网络时也执行吗？'))
    assert '无法确认' in result
    assert '保证设备未联网也能正常工作' not in result
    assert ('控制端离线后仍按预设工作' in result) is not revoked
    assert 'agent_conditional_guarantee_declined' in [e['event'] for e in agent.last_run['events']]
