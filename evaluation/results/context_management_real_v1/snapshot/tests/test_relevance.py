"""Generic lexical coverage properties; no network or benchmark-answer fixtures."""
import unittest

from langchain_core.documents import Document
from rag.relevance import QueryCoverageReranker


def document(text):
    return Document(page_content=text, metadata={"source_id": "fixture-source"})


class QueryCoverageTests(unittest.TestCase):
    def test_operation_condition_beats_repeated_object_only_match(self):
        topic = document("滤网检查滤网安装滤网位置滤网规格。")
        condition = document("更换任何配件时，首先停止运转。")
        unrelated = document("机身每天使用干布擦拭。")
        repeat = document("再次检查滤网安装滤网位置。")
        docs = [topic, unrelated, repeat, condition]
        ranker = QueryCoverageReranker(docs)
        result = ranker.rerank("更换滤网时是否要停止运转？", docs)
        self.assertEqual(result[:2], docs[:2])
        self.assertIs(result[2], condition)

    def test_repetition_cannot_raise_query_coverage(self):
        once, repeated = document("滤网安装"), document("滤网安装" * 30)
        ranker = QueryCoverageReranker([once, repeated])
        scores = ranker.scores("滤网安装", [once, repeated])
        self.assertEqual(scores[0], scores[1])
        self.assertEqual(ranker.rerank("滤网安装", [once, repeated]), [once, repeated])

    def test_unknown_query_terms_leave_fused_order_unchanged(self):
        docs = [document("主刷清理"), document("电池安装")]
        ranker = QueryCoverageReranker(docs)
        self.assertEqual(ranker.scores("ZX-19088", docs), [0., 0.])
        self.assertEqual(ranker.rerank("ZX-19088", docs), docs)

    def test_model_identifier_is_counted_as_one_term(self):
        wrong, exact = document("支持机型 ZZX-101"), document("支持机型 ZZX-102")
        ranker = QueryCoverageReranker([wrong, exact])
        self.assertEqual(ranker.scores("ZZX-102", [wrong, exact]), [0., 1.])

    def test_rare_matched_term_receives_more_weight(self):
        common = document("清理部件")
        rare = document("断开连接")
        corpus = [common, document("清理部件"), document("清理部件"), rare]
        ranker = QueryCoverageReranker(corpus)
        scores = ranker.scores("清理部件断开连接", [common, rare])
        self.assertGreater(scores[1], scores[0])

    def test_no_candidates_and_empty_corpus_are_supported(self):
        ranker = QueryCoverageReranker([])
        self.assertEqual(ranker.rerank("测试问题", []), [])
        docs = [document("资料")]
        self.assertEqual(ranker.rerank("资料", docs), docs)

    def test_source_label_has_no_effect_on_scores_and_documents_are_not_mutated(self):
        a, b = document("电池更换"), document("电池更换")
        a.metadata["source"] = "irrelevant-A11-path.txt"
        b.metadata["source"] = "other-path.txt"
        ranker = QueryCoverageReranker([a, b])
        before = [dict(doc.metadata) for doc in (a, b)]
        self.assertEqual(ranker.scores("电池更换", [a, b]), [1., 1.])
        self.assertEqual(ranker.rerank("电池更换", [a, b]), [a, b])
        self.assertEqual([doc.metadata for doc in (a, b)], before)

    def test_all_query_aspects_already_covered_preserve_order(self):
        docs = [document("滤网安装"), document("停止运转"), document("普通检查"), document("滤网安装停止运转")]
        ranker = QueryCoverageReranker(docs)
        self.assertEqual(ranker.rerank("滤网安装，停止运转", docs), docs)

    def test_other_sources_keep_their_fused_positions(self):
        first, second, repeated, new = [document(text) for text in ("滤网检查", "滤网规格", "滤网位置", "停止运转")]
        other = Document(page_content="电池检查", metadata={"source_id": "other"})
        docs = [first, other, second, repeated, new]
        ranker = QueryCoverageReranker(docs)
        result = ranker.rerank("检查滤网前停止运转", docs)
        self.assertIs(result[1], other)
        self.assertEqual(result[:3], docs[:3])
        self.assertIs(result[3], new)

    def test_source_cap_one_and_invalid_cap(self):
        docs = [document("检查滤网"), document("停止运转")]
        ranker = QueryCoverageReranker(docs)
        self.assertIs(ranker.rerank("停止运转", docs, source_cap=1)[0], docs[1])
        with self.assertRaises(ValueError):
            ranker.rerank("滤网", docs, source_cap=0)


if __name__ == "__main__":
    unittest.main()
