import unittest
from unittest.mock import patch
from test_core_flows import ScriptedModel, call, answer, scripted_agent


class KnowledgeBoundaryTests(unittest.TestCase):
    def test_insufficient_evidence_cannot_be_replaced_by_invented_contact(self):
        model = ScriptedModel(responses=[call('rag_summarize', query='清理前要断电吗'),
                                        answer('请联系小米客服400-900-8888')])
        agent = scripted_agent(model=model)
        with patch('agent.tools.agent_tools.get_rag_service') as service:
            service.return_value.rag_summarize.return_value = '参考资料中未提供足够信息'
            text = ''.join(agent.execute_stream('清理前要断电吗'))
        self.assertEqual(text, '参考资料中未提供足够信息')
        self.assertEqual(agent.messages[-1].content, text)

    def test_grounded_answer_and_next_turn_do_not_mix(self):
        model = ScriptedModel(responses=[call('rag_summarize', query='保养'),
                                        answer('主刷每天更换'), answer('你好')])
        agent = scripted_agent(model=model)
        with patch('agent.tools.agent_tools.get_rag_service') as service:
            service.return_value.rag_summarize.return_value = '定期清理主刷。'
            self.assertEqual(''.join(agent.execute_stream('如何保养')), '定期清理主刷。')
        self.assertEqual(''.join(agent.execute_stream('你好')), '你好')

    def test_multiple_knowledge_results_are_preserved(self):
        model = ScriptedModel(responses=[call('rag_summarize', query='主刷'),
                                        call('rag_summarize', query='尘盒'), answer('编造的合并结论')])
        with patch('agent.tools.agent_tools.get_rag_service') as service:
            service.return_value.rag_summarize.side_effect = ['清理主刷。', '清空尘盒。']
            text = ''.join(scripted_agent(model=model).execute_stream('两个部件怎么保养'))
        self.assertIn('清理主刷。', text)
        self.assertIn('清空尘盒。', text)
        self.assertNotIn('编造', text)
