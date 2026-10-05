"""Provider truncation cannot commit answers, summaries or protected tool work."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompt_values import ChatPromptValue

from agent.context_budget import ContextPolicy
from agent.react_agent import ReactAgent
from rag.rag_service import invoke_rag_model
from test_core_flows import ScriptedModel, answer, call
from test_context_memory import history, memory_value
from utils.model_output import IncompleteModelOutput, ensure_complete_response


def scripted_policy():
    # Keep these scripted-provider tests independent of real-model tokenizer
    # configuration and its larger thinking/output reserve.
    return ContextPolicy(reserve_output_tokens=1024, reasoning_enabled=False)


class OutputMetadataTests(unittest.TestCase):
    def test_provider_length_or_max_tokens_is_rejected(self):
        for metadata in ({"done_reason": "length"}, {"finish_reason": "length"},
                         {"finish_reason": "max_tokens"}):
            with self.subTest(metadata=metadata), self.assertRaises(IncompleteModelOutput):
                ensure_complete_response(AIMessage(content="partial answer", response_metadata=metadata))

    def test_completed_tool_response_is_allowed(self):
        message = call("fetch_external_data", user_id="1001", month="2025-08")
        message.response_metadata = {"done_reason": "stop"}
        ensure_complete_response(message)
        self.assertEqual(message.tool_calls[0]["args"]["user_id"], "1001")


class ContextOutputGraphTests(unittest.TestCase):
    def test_valid_json_marked_truncated_summary_uses_safe_fallback(self):
        summary = AIMessage(content=json.dumps(memory_value(), ensure_ascii=False),
                            response_metadata={"done_reason": "length"})
        summary_model = ScriptedModel(responses=[summary])
        model = ScriptedModel(responses=[answer("本轮完整答复")])
        agent = ReactAgent(model=model, summary_model=summary_model, context_policy=scripted_policy())
        agent.messages = history()
        self.assertEqual("".join(agent.execute_stream("继续会话")), "本轮完整答复")
        self.assertEqual(len(summary_model.seen), 1)
        self.assertIsNone(agent.summary, "A provider-truncated JSON summary was committed")
        self.assertEqual(agent.last_run["status"], "succeeded")
        self.assertTrue(any(event["event"] == "context_summary_fallback"
                            and event["error_type"] == "InvalidConversationMemory"
                            for event in agent.last_run["events"]))
        self.assertFalse(any(event["event"] == "context_summary_generated"
                             for event in agent.last_run["events"]))

    def test_truncated_tool_proposal_never_dispatches_or_commits(self):
        proposal = call("fetch_external_data", user_id="1001", month="2025-08")
        proposal.response_metadata = {"finish_reason": "max_tokens"}
        model = ScriptedModel(responses=[proposal, answer("不应执行到这里")])
        agent = ReactAgent("1001", model=model, context_policy=scripted_policy())
        previous = [HumanMessage(content="此前问候"), answer("此前完整回复")]
        previous_summary = memory_value("此前摘要")
        agent.messages, agent.summary = previous, previous_summary
        with patch("agent.tools.agent_tools.load_records") as protected_lookup:
            with self.assertRaises(IncompleteModelOutput):
                list(agent.execute_stream("查询2025年8月记录"))
            protected_lookup.assert_not_called()
        self.assertEqual(agent.messages, previous)
        self.assertEqual(agent.summary, previous_summary)
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(agent.last_run["status"], "failed")
        self.assertEqual(agent.last_run["counts"].get("tool", 0), 0)

    def test_rag_truncation_stops_turn_without_error_observation_or_commit(self):
        rag_model = ScriptedModel(responses=[AIMessage(
            content="未完成的知识回答", response_metadata={"done_reason": "length"})])
        model = ScriptedModel(responses=[call("rag_summarize", query="主刷保养"),
                                         answer("不应继续调用主模型")])
        agent = ReactAgent(model=model, context_policy=scripted_policy())
        previous = [HumanMessage(content="此前问候"), answer("此前完整回复")]
        agent.messages = previous

        def rag_query(query):
            response = invoke_rag_model(ChatPromptValue(messages=[HumanMessage(content=query)]), {})
            return response.content

        with patch("rag.rag_service.chat_model", rag_model), patch(
                "agent.tools.agent_tools.get_rag_service",
                return_value=SimpleNamespace(rag_summarize=rag_query)):
            with self.assertRaises(IncompleteModelOutput):
                list(agent.execute_stream("如何保养主刷"))
        self.assertEqual(agent.messages, previous)
        self.assertEqual(agent.last_run["status"], "failed")
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(len(rag_model.seen), 1)
        self.assertEqual(agent.last_run["counts"]["model"], 2)
        self.assertEqual(agent.last_run["counts"]["tool"], 1)


if __name__ == "__main__":
    unittest.main()
