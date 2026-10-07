"""Offline regressions: real LangChain graph and Chroma, scripted model/embeddings."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from typing import Any
from pydantic import Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.embeddings import Embeddings
from agent.react_agent import ReactAgent
from agent.context_budget import ContextPolicy
from agent.runtime import BudgetExceeded
from utils.records import normalize_month, load_records
from rag.vector_store import VectorStoreService
from utils.model_output import final_answer

class ScriptedModel(BaseChatModel):
    responses: list[Any]
    seen: list[Any] = Field(default_factory=list)
    @property
    def _llm_type(self):
        return "scripted-regression"
    def bind_tools(self, tools, **kwargs):
        return self
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])

def call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": uuid4().hex}])

def answer(text):
    return AIMessage(content=text)

def tool_results(agent, name):
    return [m for m in agent.messages if isinstance(m, ToolMessage) and m.name == name]

def scripted_context_policy(*, window_tokens=8192):
    return ContextPolicy(window_tokens=window_tokens, reserve_output_tokens=1024,
                         reasoning_enabled=False)


def scripted_agent(*args, **kwargs):
    """Keep fake-model graph tests independent of Qwen reasoning defaults."""
    kwargs.setdefault('context_policy', scripted_context_policy())
    return ReactAgent(*args, **kwargs)

class AgentFlowTests(unittest.TestCase):
    def test_knowledge_and_followup_preserve_history(self):
        model = ScriptedModel(responses=[
            call("rag_summarize", query="滚刷如何清理"), answer("先关闭电源，再清理滚刷。"),
            call("rag_summarize", query="滚刷多久清理一次"), answer("按说明书和使用情况定期检查。"),
        ])
        agent = scripted_agent("1001", model=model)
        with patch("agent.tools.agent_tools.get_rag_service") as service:
            service.return_value.rag_summarize.return_value = "参考资料：关闭电源再清理。"
            self.assertIn("关闭电源", "".join(agent.execute_stream("滚刷怎么清理？")))
            list(agent.execute_stream("那它多久清理一次？"))
        humans = [m.content for m in model.seen[2] if isinstance(m, HumanMessage)]
        self.assertEqual(humans, ["滚刷怎么清理？", "那它多久清理一次？"])
        self.assertEqual(len(tool_results(agent, "rag_summarize")), 2)

    def test_report_data_and_prompt_switch(self):
        model = ScriptedModel(responses=[
            call("get_user_id"), call("fetch_external_data", user_id="1001", month="2025-8"),
            call("fill_context_for_report"), answer("2025-08 使用报告"),
            answer("你好"),
        ])
        # This fixture checks report prompt transitions. Compression has its
        # own graph tests; fake providers count UTF-8 bytes rather than tokens.
        agent = scripted_agent("1001", model=model,
                               context_policy=scripted_context_policy(window_tokens=16384))
        list(agent.execute_stream("生成 2025 年 8 月报告"))
        data = json.loads(tool_results(agent, "fetch_external_data")[0].content)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["month"], "2025-08")
        self.assertIn("本轮已查询的报告资料", model.seen[3][0].content)
        self.assertIn("清洁表现", model.seen[3][0].content)
        list(agent.execute_stream("你好"))
        self.assertNotIn("本轮已查询的报告资料", model.seen[4][0].content)

    def test_report_does_not_trust_invented_numbers(self):
        model = ScriptedModel(responses=[
            call("fetch_external_data", user_id="1001", month="2025-08"),
            answer("主刷使用进度50%，滤网90天内更换"),
        ])
        agent = scripted_agent("1001", model=model)
        text = "".join(agent.execute_stream("生成八月报告"))
        self.assertIn("本轮已查询的报告资料", model.seen[1][0].content)
        self.assertIn("剩余50天", text)
        self.assertIn("剩余30%", text)
        self.assertNotIn("90天", text)
        self.assertNotIn("进度50%", text)
        self.assertEqual(agent.messages[-1].content, text)

    def test_missing_result_and_outage_cannot_be_overridden_by_model(self):
        model = ScriptedModel(responses=[
            call("fetch_external_data", user_id="1001", month="2099-01"),
            answer("只支持2026年，请查询2029年"),
        ])
        text = "".join(scripted_agent("1001", model=model).execute_stream("查询2099年"))
        self.assertIn("未找到", text)
        self.assertNotIn("2026", text)
        self.assertNotIn("2029", text)
        model = ScriptedModel(responses=[call("rag_summarize", query="回充故障"), answer("联系小米客服")])
        with patch("agent.tools.agent_tools.get_rag_service", side_effect=ConnectionError("offline")):
            text = "".join(scripted_agent(model=model).execute_stream("无法回充"))
        self.assertIn("查询未完成", text)
        self.assertNotIn("小米", text)

    def test_no_records_cannot_enable_report(self):
        model = ScriptedModel(responses=[
            call("fetch_external_data", user_id="1001", month="2099-01"),
            call("fill_context_for_report"), answer("2099-01 没有记录。"),
        ])
        agent = scripted_agent("1001", model=model)
        list(agent.execute_stream("查 2099-01"))
        self.assertEqual(json.loads(tool_results(agent, "fetch_external_data")[0].content)["status"], "not_found")
        self.assertEqual(tool_results(agent, "fill_context_for_report")[0].status, "error")
        self.assertNotIn("本轮已查询的报告资料", model.seen[-1][0].content)

    def test_tool_failure_becomes_observation(self):
        model = ScriptedModel(responses=[call("rag_summarize", query="保养"), answer("知识服务暂不可用。")])
        agent = scripted_agent(model=model)
        with patch("agent.tools.agent_tools.get_rag_service", side_effect=ConnectionError("offline")):
            result = "".join(agent.execute_stream("如何保养"))
        self.assertIn("查询未完成", result)
        self.assertEqual(tool_results(agent, "rag_summarize")[0].status, "error")

    def test_selected_identity_city_and_actual_month(self):
        model = ScriptedModel(responses=[
            call("get_user_id"), call("get_user_location"), call("get_current_month"),
            call("get_weather", city="悉尼"), answer("天气未接入"),
        ])
        agent = scripted_agent("1002", "悉尼", model=model)
        list(agent.execute_stream("查询信息"))
        self.assertEqual(tool_results(agent, "get_user_id")[0].content, "1002")
        self.assertEqual(tool_results(agent, "get_user_location")[0].content, "悉尼")
        self.assertEqual(tool_results(agent, "get_current_month")[0].content, date.today().strftime("%Y-%m"))
        self.assertIn("尚未接入", tool_results(agent, "get_weather")[0].content)

    def test_missing_identity_never_falls_back_to_random_user(self):
        model = ScriptedModel(responses=[
            call("get_user_id"), call("get_user_location"),
            call("fetch_external_data", user_id="1001", month="2025-08"),
            answer("请先设置演示用户 ID"),
        ])
        agent = scripted_agent(model=model)
        list(agent.execute_stream("生成报告"))
        self.assertIn("尚未设置", tool_results(agent, "get_user_id")[0].content)
        self.assertIn("尚未设置", tool_results(agent, "get_user_location")[0].content)
        self.assertEqual(tool_results(agent, "fetch_external_data")[0].status, "error")

    def test_missing_lookup_clears_previous_report_data(self):
        model = ScriptedModel(responses=[
            call("fetch_external_data", user_id="1001", month="2025-08"),
            call("fill_context_for_report"),
            call("fetch_external_data", user_id="1001", month="2099-01"),
            call("fill_context_for_report"), answer("没有指定月份记录"),
        ])
        # The fake model has no tokenizer: leave room for both full report
        # observations so this case exercises report state invalidation.
        agent = scripted_agent("1001", model=model,
                               context_policy=scripted_context_policy(window_tokens=16384))
        list(agent.execute_stream("查询两个不同月份"))
        self.assertEqual(tool_results(agent, "fill_context_for_report")[-1].status, "error")
        self.assertNotIn("本轮已查询的报告资料", model.seen[-1][0].content)

    def test_other_user_rejected_and_failed_turn_rolled_back(self):
        model = ScriptedModel(responses=[
            call("fetch_external_data", user_id="1002", month="2025-08"),
            answer("请切换演示用户"), RuntimeError("model offline"), answer("重试成功"),
        ])
        agent = scripted_agent("1001", model=model)
        list(agent.execute_stream("查另外一个用户"))
        self.assertEqual(tool_results(agent, "fetch_external_data")[0].status, "error")
        previous = list(agent.messages)
        with self.assertRaises(RuntimeError):
            list(agent.execute_stream("失败的问题"))
        self.assertEqual(agent.messages, previous)
        list(agent.execute_stream("重试"))
        self.assertNotIn("失败的问题", [m.content for m in model.seen[-1] if isinstance(m, HumanMessage)])

    def test_sessions_are_isolated_and_can_clear(self):
        first = scripted_agent("1001", model=ScriptedModel(responses=[answer("记住了")]))
        list(first.execute_stream("我叫小明"))
        second_model = ScriptedModel(responses=[answer("不知道你的姓名")])
        second = scripted_agent("1002", model=second_model)
        list(second.execute_stream("我叫什么"))
        self.assertNotIn("我叫小明", str(second_model.seen))
        first.clear_history()
        self.assertEqual(first.messages, [])

    def test_runaway_calls_are_bounded(self):
        model = ScriptedModel(responses=[call("get_current_month") for _ in range(10)])
        # Context is deliberately ample; the model-call budget must stop this
        # loop at exactly eight dispatches, with no partial history commit.
        agent = scripted_agent(model=model,
                               context_policy=scripted_context_policy(window_tokens=16384))
        with self.assertRaises(BudgetExceeded):
            list(agent.execute_stream("不断重试"))
        self.assertEqual(agent.last_run['counts']['model'], 8)
        self.assertEqual(len(model.seen), 8)
        self.assertEqual(agent.messages, [])

class RecordTests(unittest.TestCase):
    def test_reasoning_is_not_a_final_answer(self):
        self.assertEqual(final_answer("<think>分析</think>正式回答"), "正式回答")
        self.assertEqual(final_answer("兼容旧模型的分析</think>正式回答"), "正式回答")
        for text in ("<think>未完成的分析", "分析</think>", ""):
            with self.assertRaises(RuntimeError):
                final_answer(text)

    def test_month_formats_and_invalid_values(self):
        for value in ("2025-8", "2025-08", "2025/8", "2025年8月"):
            self.assertEqual(normalize_month(value), "2025-08")
        for value in ("2025-13", "2025-00", "August", ""):
            with self.assertRaises(ValueError):
                normalize_month(value)
        self.assertEqual(len(load_records()), 120)

    def test_csv_quoted_comma_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            path.write_text('用户ID,特征,清洁效率,耗材,对比,时间\n1001,"公寓,木地板",85%,40%,正常,2025-8\n', encoding="utf-8")
            self.assertEqual(load_records(str(path))[("1001", "2025-08")]["特征"], "公寓,木地板")

class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, (len(text) % 17) / 17.0, 0.25] for text in texts]
    def embed_query(self, text):
        return self.embed_documents([text])[0]

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.data.mkdir()
        self.path = self.data / "guide.txt"
        self.path.write_text("滚刷需要定期清理。关闭电源以后再取出滚刷。" * 30, encoding="utf-8")
        self.config = {
            "collection_name": "test_" + uuid4().hex, "persist_directory": str(self.root / "db"),
            "data_path": str(self.data), "allow_knowledge_file_type": ["txt"],
            "chunk_size": 60, "chunk_overlap": 10, "separators": ["。", ""], "k": 3,
        }
        from rag.security import SourceCatalog
        ledger = self.root / "sources.json"
        ledger.write_text(json.dumps({"schema_version": 1, "sources": []}), encoding="utf-8")
        self.config["source_catalog"] = str(ledger)
        self.catalog = SourceCatalog(self.data, ledger)
        self.catalog.approve("guide.txt", reason="offline test fixture")
        self.service = VectorStoreService(config=self.config, embedding=LocalEmbeddings())

    def tearDown(self):
        self.service.vector_store.delete_collection()
        self.temp.cleanup()

    def test_split_metadata_dedup_and_replace(self):
        first = self.service.load_document()
        self.assertEqual(first["failed"], [])
        stored = self.service.vector_store.get(include=["documents", "metadatas"])
        self.assertGreater(len(stored["ids"]), 1)
        self.assertTrue(all(len(text) <= 60 for text in stored["documents"]))
        self.assertTrue(all(m["source"] == str(self.path) for m in stored["metadatas"]))
        self.assertEqual(self.service.load_document()["skipped"], 1)
        # A new process/service must compute the same pipeline identity.
        again = VectorStoreService(config=self.config, embedding=LocalEmbeddings())
        self.assertEqual(again.load_document()["skipped"], 1)
        self.path.write_text("更新后的保养说明。", encoding="utf-8")
        self.catalog.approve("guide.txt", reason="test version update")
        self.assertEqual(self.service.load_document()["indexed"], 1)
        updated = self.service.vector_store.get(include=["documents"])
        self.assertEqual(updated["documents"], ["更新后的保养说明。"])
        self.assertTrue(set(stored["ids"]).isdisjoint(updated["ids"]))

    def test_partial_batch_failure_is_retried(self):
        self.path.write_text("定期清理滚刷。" * 1000, encoding="utf-8")
        self.catalog.approve("guide.txt", reason="test batch update")
        original = self.service.vector_store.add_documents
        calls = 0
        def fail_second(documents, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ConnectionError("embedding unavailable")
            return original(documents, **kwargs)
        with patch.object(self.service.vector_store, "add_documents", side_effect=fail_second):
            failed = self.service.load_document()
        self.assertEqual(failed["failed"], [str(self.path)])
        fixed = self.service.load_document()
        self.assertEqual(fixed["indexed"], 1)
        self.assertEqual(fixed["failed"], [])
        self.assertGreater(fixed["chunks"], 64)
        self.assertEqual(self.service.load_document()["skipped"], 1)

if __name__ == "__main__":
    unittest.main()
