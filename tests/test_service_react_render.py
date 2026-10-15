"""S3 shared rendering uses actual observations and commits public text only."""
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from evaluation.service_trace import TurnTrace
from test_service_agent import db, seed_path, graph
from test_core_flows import call, answer


def test_react_guard_and_facts_and_public_history(monkeypatch, db):
    agent, _ = graph(monkeypatch, db, [call('list_my_devices'),
        answer('已为你预约。编号 D-FAKE-99。请查看设备。')])
    agent.turn_trace = TurnTrace()
    text = ''.join(agent.execute_stream('我的设备'))
    assert '已为你预约' not in text and 'D-FAKE-99' not in text
    assert '请查看设备。' in text and '你的设备：D-1002-01' in text
    assert [type(m) for m in agent.messages] == [HumanMessage, AIMessage]
    assert [m.content for m in agent.messages] == ['我的设备', text]
    assert len(agent.turn_trace.snapshot()['tool_calls']) == 1


def test_report_rag_and_proposal_all_survive(monkeypatch, db):
    agent, _ = graph(monkeypatch, db, [call('fetch_external_data', month='2025-12'),
        call('rag_summarize', query='清洁方法'),
        call('propose_order', device_id='D-1002-01', sku='SKU-FILTER', qty=1),
        answer('请查看确认卡片。')])
    with patch('agent.tools.agent_tools.get_rag_service') as rag:
        rag.return_value.rag_summarize.return_value = '清理前关闭电源。'
        text = ''.join(agent.execute_stream('查看2025-12报告和清洁方法，买一个滤网'))
    assert '2025-12' in text and '资料说明：清理前关闭电源。' in text
    assert '待确认：' in text and text.endswith('请在确认卡片上确认，确认前不会提交。')
