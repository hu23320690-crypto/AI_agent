"""One prespecified hybrid candidate on the original 200-character chunks."""
import statistics
import time
from evaluation.run import ROOT, verify_dataset, dump
from evaluation.metrics import retrieval_metrics, percentile
from rag.vector_store import VectorStoreService
from rag.hybrid import BM25Index, fuse
from langchain_core.documents import Document
from utils.config_hander import chroma_conf


def main():
    raise RuntimeError("历史实验入口已冻结；重现实验使用其保存的 snapshot。当前治理检索请用 evaluation.run 并选择新 --run 目录。")
    folder=ROOT/'evaluation/results/retrieval_experiment_v1'
    if (folder/'bm25.json').exists() or (folder/'hybrid.json').exists():
        raise RuntimeError('Experiment already recorded; do not overwrite the original measurements.')
    service=VectorStoreService(config=dict(chroma_conf, chunk_size=200, chunk_overlap=20,
                                          collection_name='agent_chunks_qwen3_v1'))
    stored=service.vector_store.get(include=['documents','metadatas'])
    index=BM25Index([Document(page_content=text,metadata=meta) for text,meta in zip(stored['documents'],stored['metadatas'])])
    results={'bm25':{},'hybrid':{}}
    for case in verify_dataset():
        if case['kind']=='agent': continue
        started=time.perf_counter()
        sparse=index.search(case['query'],20)
        sparse_seconds=time.perf_counter()-started
        dense=service.vector_store.similarity_search(case['query'],k=20)
        merged=fuse([dense,sparse],5,60)
        hybrid_seconds=time.perf_counter()-started
        for mode,docs,seconds in [('bm25',sparse[:5],sparse_seconds),('hybrid',merged,hybrid_seconds)]:
            documents=[{'text':d.page_content,'metadata':d.metadata} for d in docs]
            results[mode][case['id']]={'docs':documents,'seconds':seconds,'metrics':retrieval_metrics(case,documents)}
    for mode,rows in results.items():
        scored=[r for r in rows.values() if r['metrics']]
        summary={'mode':mode,'chunk_size':200,'candidates_per_route':20,'rrf_constant':60,
                 'hit':{str(k):sum(r['metrics']['hit'][str(k)] for r in scored) for k in (1,3,5)},
                 'median_seconds':statistics.median(r['seconds'] for r in rows.values()),
                 'p95_seconds':percentile([r['seconds'] for r in rows.values()],.95),
                 'mean_context_chars':{str(k):statistics.mean(sum(len(d['text']) for d in r['docs'][:k]) for r in rows.values()) for k in (1,3,5)}}
        dump(folder/(mode+'.json'),{'results':rows,'summary':summary})
        print(summary,flush=True)


if __name__=='__main__': main()
