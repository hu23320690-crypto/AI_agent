"""Reproducible retrieval-only ablation on a frozen protected candidate cache.

No chat model is called. Candidate collection always applies the current
catalog and content checks. Replaying a cache describes those captured bytes;
it does not claim that cached sources are still authorized today.
"""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]


def pack(document):
    return {"text": document.page_content, "metadata": document.metadata}


def select(candidates, *, limit=5, source_cap=3, deduplicate=True):
    selected, texts, counts = [], [], Counter()
    for document in candidates:
        source = document.metadata["source_id"]
        text = re.sub(r"\s+", "", document.page_content).casefold()
        if source_cap is not None and counts[source] >= source_cap:
            continue
        if deduplicate and any(text == prior or
                               SequenceMatcher(None, text, prior, autojunk=False).ratio() >= .96
                               for prior in texts):
            continue
        selected.append(document)
        texts.append(text)
        counts[source] += 1
        if len(selected) == limit:
            break
    return selected


def collect(path, dataset):
    from rag.vector_store import VectorStoreService
    from rag.hybrid import BM25Index
    from evaluation.run import business_files, digest, verify_dataset
    store = VectorStoreService()
    snapshot = store.catalog.snapshot()
    corpus = store._eligible(snapshot)
    if not corpus:
        raise RuntimeError("No authorized indexed corpus; run knowledge sync first")
    permitted = sorted(document.metadata["chunk_id"] for document in corpus)
    index = BM25Index(corpus)
    cases = [case for case in verify_dataset(dataset) if case["kind"] != "agent"]
    # An observed model rewrite from the third-stage A11 trace. Its reference
    # is the unchanged K19 evidence; the wording is not fed to the ranker code.
    k19 = next((case for case in cases if case["id"] == "K19"), None)
    if k19 is not None:
        cases.append(dict(k19, id="A11_followup", query="清理主刷前需要断开电源吗？"))
    rows = []
    for case in cases:
        started = time.perf_counter()
        dense = store.vector_store.similarity_search(
            case["query"], k=20, filter={"chunk_id": {"$in": permitted}})
        sparse = index.search(case["query"], 20)
        store.validate_documents(dense + sparse)
        rows.append({"case": case, "dense": [pack(document) for document in dense],
                     "sparse": [pack(document) for document in sparse],
                     "seconds": time.perf_counter() - started})
        print(case["id"], flush=True)
    payload = {"schema_version": 1, "dataset_sha256": digest(dataset),
               "source_stamp": snapshot.stamp, "code_sha256": business_files(),
               "corpus": [pack(document) for document in corpus], "rows": rows,
               "selection": {"source_cap": store.catalog.policy.max_chunks_per_source,
                             "deduplicate": store.catalog.policy.deduplicate_chunks},
               "definition": "Current authorized collection; dense20/BM25 20; no chat inference."}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def evaluate(payload):
    from langchain_core.documents import Document
    from rag.hybrid import fuse
    from rag.relevance import QueryCoverageReranker
    from evaluation.metrics import retrieval_metrics
    def unpack(row):
        return Document(page_content=row["text"], metadata=row["metadata"])
    reranker = QueryCoverageReranker([unpack(row) for row in payload["corpus"]])
    results = {variant: [] for variant in
               ("rrf_cap3", "rrf_no_cap", "source_coverage_cap3")}
    diagnostics = []
    deduplicate = payload.get("selection", {}).get("deduplicate", True)
    for row in payload["rows"]:
        case = row["case"]
        dense, sparse = [unpack(doc) for doc in row["dense"]], [unpack(doc) for doc in row["sparse"]]
        fused = fuse([dense, sparse], len(dense) + len(sparse), 60)
        reranked = reranker.rerank(case["query"], fused, source_cap=3)
        for name, candidates, cap in (("rrf_cap3", fused, 3),
                                      ("rrf_no_cap", fused, None),
                                      ("source_coverage_cap3", reranked, 3)):
            chosen = select(candidates, source_cap=cap, deduplicate=deduplicate)
            docs = [pack(document) for document in chosen]
            results[name].append({"id": case["id"], "query": case["query"],
                                  "kind": case["kind"], "docs": docs,
                                  "metrics": retrieval_metrics(case, docs)})
        if case["id"] == "A11_followup":
            for route, documents in (("dense20", dense), ("bm25_20", sparse),
                                     ("rrf_union", fused), ("source_coverage_union", reranked)):
                hits = [{"rank": rank, "doc": pack(document)}
                        for rank, document in enumerate(documents, 1)
                        if retrieval_metrics(case, [pack(document)])["hit"]["1"]]
                diagnostics.append({"route": route, "evidence_hits": hits})
    summary = {}
    for name, rows in results.items():
        knowledge = [row for row in rows if row["kind"] == "knowledge" and row["id"] != "A11_followup"]
        summary[name] = {
            "knowledge_cases": len(knowledge),
            "hits": {str(k): sum(row["metrics"]["hit"][str(k)] for row in knowledge) for k in (1, 3, 5)},
            "top5_misses": [row["id"] for row in knowledge if not row["metrics"]["hit"]["5"]],
            "no_answer_cases": sum(row["kind"] == "unanswerable" for row in rows),
            "no_answer_nonempty": sum(row["kind"] == "unanswerable" and bool(row["docs"]) for row in rows),
            "a11_hit": next((row["metrics"]["hit"] for row in rows if row["id"] == "A11_followup"), None),
        }
    return {"schema_version": 1, "summary": summary, "a11_candidate_diagnostic": diagnostics,
            "results": results,
            "definition": "Frozen candidates; unchanged source evidence >=60% coverage; no answer accuracy score."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="New directory; existing outputs are never overwritten")
    parser.add_argument("--cache", help="Replay an existing captured candidate cache, without model calls")
    parser.add_argument("--dataset", default="evaluation/cases.jsonl")
    args = parser.parse_args()
    run = Path(args.run)
    if not run.is_absolute():
        run = ROOT/run
    run.mkdir(parents=True, exist_ok=True)
    if any(run.iterdir()):
        raise RuntimeError("Ablation output must be an empty directory; preserve every earlier result")
    if args.cache:
        cache = Path(args.cache)
        if not cache.is_absolute():
            cache = ROOT/cache
        payload = json.loads(cache.read_text(encoding="utf-8"))
        (run/"candidate_cache.json").write_bytes(cache.read_bytes())
    else:
        dataset = Path(args.dataset)
        if not dataset.is_absolute():
            dataset = ROOT/dataset
        payload = collect(run/"candidate_cache.json", dataset)
    result = evaluate(payload)
    result["candidate_cache_sha256"] = hashlib.sha256((run/"candidate_cache.json").read_bytes()).hexdigest()
    result["reranker_sha256"] = hashlib.sha256((ROOT/"rag/relevance.py").read_bytes()).hexdigest()
    result["vector_store_sha256"] = hashlib.sha256((ROOT/"rag/vector_store.py").read_bytes()).hexdigest()
    result["evaluation_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (run/"ablation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
