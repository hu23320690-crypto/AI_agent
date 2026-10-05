"""Real graph regressions for compressed history and atomic memory commits."""
from dataclasses import replace
import json
from threading import Event, Thread
from typing import Any
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent.context_budget import ContextPolicy
from agent.react_agent import ReactAgent
from agent.runtime import ExecutionRuntime, RunCancelled, RunLimits
from rag.security import KnowledgeAccessError
from test_core_flows import ScriptedModel, answer, call
from test_context_memory import history, memory_value


def summary_answer(topic="主刷清理"):
    return answer(json.dumps(memory_value(topic), ensure_ascii=False))


def scripted_policy():
    # Scripted providers have no Qwen model identity and use the byte fallback.
    return ContextPolicy(reserve_output_tokens=1024, reasoning_enabled=False)


class BlockingSummaryModel(ScriptedModel):
    entered: Any = Field(exclude=True)
    release: Any = Field(exclude=True)
    exited: Any = Field(exclude=True)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        self.entered.set()
        try:
            if not self.release.wait(3):
                raise RuntimeError("Summary test worker was not released")
            return ChatResult(generations=[ChatGeneration(message=summary_answer("迟到的新摘要"))])
        finally:
            self.exited.set()


class RevokingModel(ScriptedModel):
    revoke: Any = Field(exclude=True)
    revocations_left: int = 1

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop, run_manager, **kwargs)
        if self.revocations_left:
            self.revocations_left -= 1
            self.revoke()
        return result


class ContextCommitGraphTests(unittest.TestCase):
    def test_compression_extracts_only_current_turn_rag_results(self):
        model = ScriptedModel(responses=[call("rag_summarize", query="本轮主刷清理"),
                                         answer("主模型的改写不应覆盖工具答案")])
        summary_model = ScriptedModel(responses=[summary_answer()])
        agent = ReactAgent(model=model, summary_model=summary_model, context_policy=scripted_policy())
        previous = history()
        # Put an old RAG observation in the most recent historical turn: it can
        # remain in the send view while the full graph prefix is much longer.
        old_call = call("rag_summarize", query="旧轮尘盒问题")
        previous[-1:-1] = [old_call, ToolMessage(
            content="旧轮RAG答案：尘盒旧内容", name="rag_summarize", status="success",
            tool_call_id=old_call.tool_calls[0]["id"])]
        agent.messages = previous
        current_answer = "本轮RAG答案：清理主刷前关闭电源。"
        with patch("agent.tools.agent_tools.get_rag_service") as service:
            service.return_value.rag_summarize.return_value = current_answer
            result = "".join(agent.execute_stream("主刷现在应如何清理？"))
        self.assertEqual(result, current_answer)
        self.assertEqual(agent.messages[-1].content, current_answer)
        self.assertNotIn("尘盒旧内容", result)
        self.assertEqual(len(summary_model.seen), 1)
        self.assertTrue(any(event["event"] == "context_summary_generated"
                            for event in agent.last_run["events"]))
        self.assertLess(len(agent.messages), len(previous))
        self.assertEqual(agent.last_run["counts"]["model"], 3)

    def test_cancel_or_clear_during_summary_cannot_commit_late_memory(self):
        for action in ("cancel", "clear"):
            with self.subTest(action=action):
                entered, release, exited, finished = Event(), Event(), Event(), Event()
                summary_model = BlockingSummaryModel(
                    responses=[], entered=entered, release=release, exited=exited)
                model = ScriptedModel(responses=[answer("主模型不应被调用")])
                limits = replace(RunLimits(), total_seconds=4, model_concurrency=1)
                agent = ReactAgent(model=model, summary_model=summary_model,
                                   limits=limits, executor=ExecutionRuntime(limits),
                                   context_policy=scripted_policy())
                previous = history()
                previous_summary = memory_value("已有摘要")
                agent.messages, agent.summary = previous, previous_summary
                errors = []

                def execute():
                    try:
                        list(agent.execute_stream("继续主刷清理的话题"))
                    except BaseException as exc:
                        errors.append(exc)
                    finally:
                        finished.set()

                worker = Thread(target=execute)
                worker.start()
                try:
                    self.assertTrue(entered.wait(1), "Summary did not start")
                    if action == "cancel":
                        self.assertTrue(agent.cancel_current())
                    else:
                        agent.clear_history()
                    self.assertTrue(finished.wait(1), "Cancellation waited for summary completion")
                    self.assertEqual(len(errors), 1)
                    self.assertIsInstance(errors[0], RunCancelled)
                    self.assertEqual(agent.last_run["status"], "cancelled")
                    self.assertEqual(agent.last_run["counts"]["model"], 1)
                    self.assertEqual(model.seen, [])
                    gate = agent.executor.gates["model"]
                    self.assertFalse(gate.acquire(blocking=False), "Late worker lost its capacity lease")
                    self.assertEqual(agent.messages, previous if action == "cancel" else [])
                    self.assertEqual(agent.summary, previous_summary if action == "cancel" else None)
                    completed_snapshot = agent.last_run
                finally:
                    release.set()
                    worker.join(2)
                self.assertTrue(exited.wait(1), "Late summary worker did not return")
                self.assertFalse(worker.is_alive())
                self.assertTrue(gate.acquire(timeout=1), "Late worker did not release capacity")
                gate.release()
                self.assertEqual(agent.messages, previous if action == "cancel" else [])
                self.assertEqual(agent.summary, previous_summary if action == "cancel" else None)
                self.assertEqual(agent.last_run, completed_snapshot)
                self.assertEqual(model.seen, [])

    def test_commit_revocation_rolls_back_new_summary_then_discards_old_memory(self):
        revoked = Event()
        checks = []

        def source_check():
            checks.append(True)
            if revoked.is_set():
                raise KnowledgeAccessError("source_revoked")

        model = RevokingModel(responses=[answer("本轮答案不能提交"), answer("新会话回答")],
                              revoke=revoked.set)
        summary_model = ScriptedModel(responses=[summary_answer("生成但未提交的新摘要")])
        agent = ReactAgent(model=model, summary_model=summary_model, context_policy=scripted_policy())
        previous = history()
        previous_summary = memory_value("已有的旧摘要")
        agent.messages, agent.summary = previous, previous_summary
        agent._history_checks = [source_check]
        with self.assertRaises(KnowledgeAccessError):
            list(agent.execute_stream("继续主刷话题"))
        self.assertTrue(any(event["event"] == "context_summary_generated"
                            for event in agent.last_run["events"]))
        self.assertEqual(agent.last_run["status"], "failed")
        self.assertEqual(agent.messages, previous)
        self.assertEqual(agent.summary, previous_summary)
        self.assertEqual(agent._history_checks, [source_check])
        self.assertGreaterEqual(len(checks), 2)
        self.assertEqual("".join(agent.execute_stream("开始新的对话")), "新会话回答")
        self.assertEqual(len(summary_model.seen), 1, "Revoked history was summarized again")
        self.assertEqual([message.content for message in model.seen[-1][1:]], ["开始新的对话"])
        self.assertIsNone(agent.summary)
        self.assertEqual(agent._history_checks, [])


if __name__ == "__main__":
    unittest.main()
