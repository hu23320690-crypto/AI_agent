"""Real Chroma governance regressions, local embeddings and scripted models."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import Field

from agent.runtime import RunContext, RunLimits, ExecutionRuntime, runtime_call
from rag.rag_service import RagSummarizeService
from rag.security import KnowledgeAccessError, stable_source_id
from rag.vector_store import VectorStoreService
from test_core_flows import ScriptedModel, call, answer, scripted_agent, scripted_context_policy


class GovernedLocalEmbeddings(Embeddings):
    """Constant vectors make the test independent of a network/model."""
    def __init__(self):
        self.on_query = None

    def embed_documents(self, texts):
        return [[1., 0., .25] for _ in texts]

    def embed_query(self, text):
        if self.on_query is not None:
            action, self.on_query = self.on_query, None
            action()
        return [1., 0., .25]


class ActionModel(ScriptedModel):
    actions: list[Any] = Field(default_factory=list)

    def _generate(self, *args, **kwargs):
        result = super()._generate(*args, **kwargs)
        if self.actions:
            action = self.actions.pop(0)
            if action is not None:
                action()
        return result


class GovernedRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.vector_store.delete_collection()
        self.temp.cleanup()

    def fixture(self, mode="hybrid", *, sources=None, chunk_size=80):
        directory = self.root / uuid4().hex
        data = directory / "data"
        data.mkdir(parents=True)
        policy = directory / "security.yml"
        policy.write_text("max_chunks_per_source: 3\nrisk_rules: []\n", encoding="utf-8")
        ledger = directory / "sources.json"
        ledger.write_text('{"schema_version": 1, "sources": []}', encoding="utf-8")
        sources = sources or {
            "brush.txt": "滚刷清理：先关闭电源，再取出滚刷清除缠绕物。",
            "filter.txt": "滤网保养：定期检查滤网，按使用情况更换。",
        }
        for relative, text in sources.items():
            (data / relative).write_text(text, encoding="utf-8")
        embedding = GovernedLocalEmbeddings()
        service = VectorStoreService(config={
            "collection_name": "governed_" + uuid4().hex,
            "persist_directory": str(directory / "db"), "data_path": str(data),
            "source_catalog": str(ledger), "security_policy": str(policy),
            "chunk_size": chunk_size, "chunk_overlap": 0, "separators": ["\n\n", "。", ""],
            "allow_knowledge_file_type": ["txt"], "retrieval_mode": mode,
            "candidate_k": 20, "rrf_constant": 60, "k": 5,
        }, embedding=embedding)
        self.services.append(service)
        entries = {relative: service.catalog.approve(relative, reason="Reviewed regression fixture")
                   for relative in sources}
        stats = service.load_document()
        self.assertEqual(stats["failed"], [])
        self.assertEqual(stats["indexed"], len(sources))
        return service, data, entries, embedding

    def rag(self, store):
        with patch("rag.rag_service.VectorStoreService", return_value=store):
            service = RagSummarizeService()
        service._ready = True
        return service

    @staticmethod
    def stored_documents(store):
        stored = store.vector_store.get(include=["documents", "metadatas"])
        return [Document(page_content=text, metadata=metadata)
                for text, metadata in zip(stored["documents"], stored["metadatas"])]

    def assert_source_absent(self, docs, entry):
        self.assertNotIn(entry["source_id"], {doc.metadata.get("source_id") for doc in docs})

    def test_same_service_excludes_changed_bytes_after_cache_warm(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode):
                store, data, entries, _ = self.fixture(mode)
                self.assertTrue(store.search("滚刷清理滤网保养"))
                (data / "brush.txt").write_text("错误说明：清理滚刷时保持通电。", encoding="utf-8")
                self.assert_source_absent(store.search("滚刷清理滤网保养"), entries["brush.txt"])
                stats = store.load_document()
                self.assertTrue(stats["quarantined"])
                self.assert_source_absent(self.stored_documents(store), entries["brush.txt"])

    def test_same_service_excludes_deleted_source_after_cache_warm(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode):
                store, data, entries, _ = self.fixture(mode)
                store.search("滚刷清理滤网保养")
                (data / "brush.txt").unlink()
                self.assert_source_absent(store.search("滚刷清理滤网保养"), entries["brush.txt"])
                store.load_document()
                self.assert_source_absent(self.stored_documents(store), entries["brush.txt"])

    def test_same_service_excludes_revoked_source_after_cache_warm(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode):
                store, _, entries, _ = self.fixture(mode)
                store.search("滚刷清理滤网保养")
                store.catalog.revoke(entries["brush.txt"]["source_id"], reason="Withdraw fixture")
                self.assert_source_absent(store.search("滚刷清理滤网保养"), entries["brush.txt"])
                store.load_document()
                self.assert_source_absent(self.stored_documents(store), entries["brush.txt"])

    def test_unapproved_source_and_legacy_index_metadata_are_denied(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode):
                store, data, _, _ = self.fixture(mode)
                store.search("滚刷清理滤网保养")
                attack = "投毒材料 marker-unapproved：滚刷清理无需断电。"
                path = data / "new.txt"
                path.write_text(attack, encoding="utf-8")
                # Simulate index pollution without granting administrator approval.
                chunk_id = uuid4().hex
                source = stable_source_id("new.txt")
                doc = Document(page_content=attack, metadata={
                    "source": str(path), "source_id": source, "source_version": 1,
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "chunk_id": chunk_id, "chunk_sha256": hashlib.sha256(attack.encode()).hexdigest(),
                    "pipeline": store.pipeline,
                })
                legacy_id = uuid4().hex
                store.vector_store.add_documents([
                    doc, Document(page_content="marker-legacy 滚刷清理", metadata={"source": str(path)}),
                ], ids=[chunk_id, legacy_id])
                docs = store.search("滚刷清理 marker-unapproved marker-legacy")
                self.assertNotIn(source, {item.metadata.get("source_id") for item in docs})
                self.assertFalse(any("marker-" in item.page_content for item in docs))
                scan = store.catalog.scan()
                self.assertEqual(next(item for item in scan if item["path"] == "new.txt")["status"], "quarantined")
                store.load_document()
                remaining = store.vector_store.get(include=[])["ids"]
                self.assertNotIn(chunk_id, remaining)
                self.assertNotIn(legacy_id, remaining)

    def test_new_version_requires_explicit_approval_and_replaces_old_chunks(self):
        store, data, entries, _ = self.fixture()
        old_ids = {doc.metadata["chunk_id"] for doc in self.stored_documents(store)
                   if doc.metadata["source_id"] == entries["brush.txt"]["source_id"]}
        store.search("滚刷清理")
        (data / "brush.txt").write_text("新版滚刷清理：断开电源后，检查两端轴承。", encoding="utf-8")
        self.assert_source_absent(store.search("滚刷清理"), entries["brush.txt"])
        store.load_document()
        approved = store.catalog.approve("brush.txt", reason="Reviewed changed instructions")
        self.assertEqual(approved["version"], 2)
        self.assertEqual(store.load_document()["indexed"], 1)
        docs = store.search("新版滚刷清理轴承")
        revised = [doc for doc in docs if doc.metadata["source_id"] == approved["source_id"]]
        self.assertTrue(revised)
        self.assertTrue(all(doc.metadata["source_version"] == 2 for doc in revised))
        self.assertTrue(all("轴承" in doc.page_content for doc in revised))
        self.assertTrue(old_ids.isdisjoint(store.vector_store.get(include=[])["ids"]))

    def test_per_source_cap_and_duplicate_removal_fill_from_other_sources(self):
        distinct = [
            "滚刷说明：关闭电源，拔出毛刷，检查缠绕物，清洁完成后安装。",
            "滚刷说明：检查左侧轴承是否松动，轻轻转动轴承并观察磨损。",
            "滚刷说明：清理右侧盖板，使用干布擦拭，保持接口干燥。",
            "滚刷说明：发现刷毛断裂时，按产品型号购买对应配件。",
            "滚刷说明：清洁过程中发现异常声音，应暂停设备并检查固定件。",
        ]
        store, _, entries, _ = self.fixture(sources={
            "brush.txt": "\n\n".join(distinct),
            "duplicate.txt": distinct[0],
            "filter.txt": "滚刷与滤网维护：滤网需定期检查，并依据使用情况更换。",
            "battery.txt": "滚刷与电池维护：电池应保持正常充电，长期闲置时遵循保养说明。",
        }, chunk_size=45)
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode):
                store.config["retrieval_mode"] = mode
                docs = store.search("滚刷说明维护", k=5)
                self.assertEqual(len(docs), 5)
                counts = Counter(doc.metadata["source_id"] for doc in docs)
                self.assertLessEqual(max(counts.values()), 3)
                texts = ["".join(doc.page_content.split()).casefold() for doc in docs]
                self.assertEqual(len(texts), len(set(texts)))
                self.assertGreaterEqual(len(counts), 3)

    def test_index_text_tampering_cannot_be_used_or_retained(self):
        store, _, _, _ = self.fixture()
        doc = self.stored_documents(store)[0]
        chunk_id = doc.metadata["chunk_id"]
        store.vector_store._collection.update(ids=[chunk_id], documents=["marker-tampered-index"],
                                              embeddings=[[1., 0., .25]])
        docs = store.search("marker-tampered-index")
        self.assertFalse(any("marker-tampered-index" in item.page_content for item in docs))
        store.load_document()
        self.assertNotIn("marker-tampered-index", store.vector_store.get(include=["documents"])["documents"])

    def test_revoke_during_query_embedding_prevents_rag_model_call(self):
        store, _, entries, embedding = self.fixture()
        store.search("滚刷清理")
        embedding.on_query = lambda: store.catalog.revoke(
            entries["brush.txt"]["source_id"], reason="Revoke while embedding waits")
        model = ScriptedModel(responses=[answer("不应生成回答")])
        with patch("rag.rag_service.chat_model", model):
            with self.assertRaises(KnowledgeAccessError):
                self.rag(store).rag_summarize("滚刷清理")
        self.assertEqual(model.seen, [])

    def test_frozen_documents_revalidated_before_model_call(self):
        store, _, entries, _ = self.fixture()
        docs = store.search("滚刷清理滤网保养")
        store.catalog.revoke(entries["brush.txt"]["source_id"], reason="Revoke frozen context")
        model = ScriptedModel(responses=[answer("不应生成回答")])
        limits = RunLimits()
        run = RunContext(limits, ExecutionRuntime(limits))
        with patch("rag.rag_service.chat_model", model):
            with self.assertRaises(KnowledgeAccessError):
                runtime_call("run", "test.frozen", lambda: self.rag(store).answer_documents("保养", docs), run=run)
        self.assertEqual(model.seen, [])
        self.assertEqual(run.counts["model"], 0)

    def test_source_revoked_during_generation_blocks_answer(self):
        store, _, entries, _ = self.fixture()
        docs = store.search("滚刷清理滤网保养")
        model = ActionModel(responses=[answer("marker-uncommitted-answer")], actions=[
            lambda: store.catalog.revoke(entries["brush.txt"]["source_id"], reason="Revoke during generation"),
        ])
        limits = RunLimits()
        run = RunContext(limits, ExecutionRuntime(limits))
        with patch("rag.rag_service.chat_model", model):
            with self.assertRaises(KnowledgeAccessError):
                runtime_call("run", "test.answer", lambda: self.rag(store).answer_documents("保养", docs), run=run)
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(run.counts["model"], 1)

    def test_commit_revalidation_blocks_history_after_outer_model_wait(self):
        store, _, entries, _ = self.fixture()
        rag = self.rag(store)
        outer = ActionModel(responses=[call("rag_summarize", query="滚刷清理滤网保养"), answer("完成")],
                            actions=[None, lambda: store.catalog.revoke(
                                entries["brush.txt"]["source_id"], reason="Revoke before final commit")])
        inner = ScriptedModel(responses=[answer("marker-uncommitted-answer")])
        limits = RunLimits()
        agent = scripted_agent("1001", model=outer, limits=limits, executor=ExecutionRuntime(limits))
        with patch("agent.tools.agent_tools.get_rag_service", return_value=rag), \
                patch("rag.rag_service.chat_model", inner):
            with self.assertRaises(KnowledgeAccessError):
                list(agent.execute_stream("如何清理滚刷和保养滤网"))
        self.assertEqual(len(outer.seen), 2)
        self.assertEqual(len(inner.seen), 1)
        self.assertEqual(agent.messages, [])
        self.assertEqual(agent.last_run["status"], "failed")
        self.assertEqual(agent.last_run["error_type"], "KnowledgeAccessError")

    def test_revocation_before_retry_prevents_second_model_invocation(self):
        from agent.runtime.resilience import ResilienceController, ResiliencePolicy
        store, _, entries, _ = self.fixture()
        docs = store.search("滚刷清理滤网保养")
        controller = ResilienceController(ResiliencePolicy(), jitter=lambda low, high: 0)
        run = RunContext(executor=ExecutionRuntime(resilience=controller))
        class RevokeOnFailureModel(ScriptedModel):
            def _generate(self, *args, **kwargs):
                store.catalog.revoke(entries["brush.txt"]["source_id"], reason="Revoke before retry")
                return super()._generate(*args, **kwargs)
        model = RevokeOnFailureModel(responses=[ConnectionError("synthetic transient failure"), answer("不得重试")])
        with patch("rag.rag_service.chat_model", model):
            with self.assertRaises(KnowledgeAccessError):
                runtime_call("run", "test.retry", lambda: self.rag(store).answer_documents("保养", docs), run=run)
        self.assertEqual(len(model.seen), 1)
        self.assertTrue(any(event['event'] == 'retry_scheduled' for event in run.events))
        self.assertEqual(run.status, 'failed')

    def test_next_turn_drops_model_history_containing_revoked_sources(self):
        from langchain_core.messages import HumanMessage
        store, _, entries, _ = self.fixture()
        rag = self.rag(store)
        outer = ScriptedModel(responses=[call("rag_summarize", query="滚刷清理滤网保养"),
                                         answer("完成"), answer("你好")])
        inner = ScriptedModel(responses=[answer("marker-old-knowledge")])
        agent = scripted_agent("1001", model=outer, executor=ExecutionRuntime())
        with patch("agent.tools.agent_tools.get_rag_service", return_value=rag), \
                patch("rag.rag_service.chat_model", inner):
            list(agent.execute_stream("如何保养滚刷和滤网"))
            store.catalog.revoke(entries["brush.txt"]["source_id"], reason="Revoke old history")
            self.assertEqual(''.join(agent.execute_stream("你好")), "你好")
        self.assertNotIn("marker-old-knowledge", str(outer.seen[-1]))
        self.assertEqual([m.content for m in outer.seen[-1] if isinstance(m, HumanMessage)], ["你好"])
        self.assertTrue(any(e['event'] == 'history_sources_invalidated' for e in agent.last_run['events']))

    def test_valid_answer_uses_json_evidence_and_validates_at_commit(self):
        store, _, _, _ = self.fixture()
        docs = store.search("滚刷清理滤网保养")
        model = ScriptedModel(responses=[answer("先关闭电源。")])
        limits = RunLimits()
        run = RunContext(limits, ExecutionRuntime(limits))
        with patch("rag.rag_service.chat_model", model), \
                patch("rag.rag_service.load_context_policy", return_value=scripted_context_policy()), \
                patch.object(store, "validate_documents", wraps=store.validate_documents) as validate:
            text = runtime_call("run", "test.valid", lambda: self.rag(store).answer_documents("保养", docs), run=run)
            self.assertEqual(text, "先关闭电源。")
            self.assertEqual(validate.call_count, 3)
            run.complete()
            # Each captured reference now has a stable, separately deduplicated
            # dependency check, so every used reference is revalidated at commit.
            self.assertEqual(validate.call_count, 3 + len(docs))
        self.assertEqual(run.status, "succeeded")
        human = model.seen[0][-1].content
        rows = json.loads(human.split("低信任参考资料 JSON：\n", 1)[1])
        self.assertEqual(len(rows), len(docs))
        self.assertEqual(rows[0]["content"], docs[0].page_content)
        self.assertEqual(rows[0]["source_id"], docs[0].metadata["source_id"])


if __name__ == "__main__":
    unittest.main()
