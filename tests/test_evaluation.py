import unittest
import hashlib
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import patch
from evaluation.metrics import evidence_coverage, retrieval_metrics, percentile, tool_selection
from evaluation.run import verify_dataset
from evaluation.report import summarize

class EvaluationTests(unittest.TestCase):
    def test_frozen_sources_and_unique_ids(self):
        cases=verify_dataset()
        self.assertEqual(sum(c["kind"]=="knowledge" for c in cases),40)
        self.assertEqual(sum(c["kind"]=="unanswerable" for c in cases),8)
        self.assertEqual(sum(c["kind"]=="agent" for c in cases),12)

    def test_windows_manifest_paths_are_portable_and_source_hashes_remain_enforced(self):
        # PurePosixPath exposes the original Linux failure even on Windows:
        # a backslash remains part of a filename rather than becoming a separator.
        with TemporaryDirectory() as folder:
            dataset = Path(folder) / "cases.jsonl"
            dataset.write_bytes(b'{"id":"K01","kind":"knowledge"}\n')
            dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
            expected_source_hash = "a" * 64
            manifest = {"case_count": 1, "dataset_sha256": dataset_hash,
                        "files": {"data\\evidence.txt": expected_source_hash}}
            (dataset.parent / "dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            portable_root = PurePosixPath("/frozen/project")
            actual_source_hash = expected_source_hash

            def digest_for_path(path):
                if path == dataset:
                    return dataset_hash
                self.assertEqual(path, portable_root / "data/evidence.txt")
                return actual_source_hash

            with patch("evaluation.run.ROOT", portable_root), patch("evaluation.run.digest", digest_for_path):
                self.assertEqual(verify_dataset(dataset), [{"id": "K01", "kind": "knowledge"}])
                actual_source_hash = "b" * 64
                with self.assertRaisesRegex(AssertionError, "Source changed"):
                    verify_dataset(dataset)

    def test_evidence_split_across_chunks_can_be_covered(self):
        quote="清洁机器人时全程断开电源，切勿用水直接冲洗机身。"
        self.assertGreater(evidence_coverage(quote,["清洁机器人时全程断开电源，","切勿用水直接冲洗机身。"]),0.95)
        self.assertLess(evidence_coverage(quote,["电源开关在机身后部。"]),0.6)

    def test_source_and_rank_matter(self):
        case={"evidence":[{"source":"data/a.txt","quote":"清洁机器人时全程断开电源。"}]}
        docs=[{"text":"清洁机器人时全程断开电源。","metadata":{"source":"b.txt"}},
              {"text":"清洁机器人时全程断开电源。","metadata":{"source":"a.txt"}}]
        score=retrieval_metrics(case,docs)
        self.assertFalse(score["hit"]["1"])
        self.assertTrue(score["hit"]["3"])
        self.assertEqual(score["reciprocal_rank_at_5"],0.5)
        self.assertIsNone(retrieval_metrics({"evidence":[]},docs))

    def test_tool_choice_checks_missing_and_extra(self):
        rule={"required_tools":["rag_summarize"],"allowed_tools":["rag_summarize"]}
        self.assertTrue(tool_selection(rule,[{"name":"rag_summarize"}])["pass"])
        self.assertFalse(tool_selection(rule,[])["pass"])
        self.assertFalse(tool_selection(rule,[{"name":"rag_summarize"},{"name":"get_weather"}])["pass"])

    def test_nearest_rank_percentile(self):
        self.assertEqual(percentile(list(range(1,21)),0.95),19)
        self.assertIsNone(percentile([],0.95))

    def test_pending_and_error_answers_never_implicitly_pass(self):
        cases=[{"id":"K1","kind":"knowledge"},{"id":"K2","kind":"knowledge"}]
        rows=[{"id":"K1","mode":"qa","status":"timeout"}]
        result=summarize(cases,rows,{},[])
        self.assertEqual(result["knowledge_answers"]["planned"],2)
        self.assertEqual(result["knowledge_answers"]["completed"],1)
        self.assertEqual(result["knowledge_answers"]["errors"],1)
        self.assertEqual(result["knowledge_answers"]["strict_pass"],0)

