"""Retrieval ablation: vary chunk size, keeping overlap/model/corpus fixed."""
import json
import statistics
import time
import yaml
from pathlib import Path
from evaluation.run import ROOT, verify_dataset, dump, digest
from evaluation.metrics import retrieval_metrics, percentile
from rag.vector_store import VectorStoreService


def main():
    raise RuntimeError("历史实验入口已冻结；重现实验使用其保存的 snapshot。当前治理检索请用 evaluation.run 并选择新 --run 目录。")
    cases = [c for c in verify_dataset() if c['kind'] != 'agent']
    directory = ROOT / 'evaluation/results/retrieval_experiment_v1'
    directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    baseline_config = yaml.safe_load((ROOT/'evaluation/results/baseline_v1/snapshot/config/chroma.yml').read_text(encoding='utf-8'))
    for size in (200, 400, 600):
        config = dict(baseline_config, chunk_size=size, chunk_overlap=20,
                      collection_name='agent_chunks_qwen3_v1' if size == 200 else f'agent_exp_c{size}_o20_v1')
        path = directory / f'c{size}.json'
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            assert saved['config'] == config
            assert saved['dataset_sha256'] == digest(ROOT/'evaluation/cases.jsonl')
            summaries.append(saved['summary'])
            continue
        service = VectorStoreService(config=config)
        started = time.perf_counter()
        stats = service.load_document()
        assert not stats['failed'], stats
        index_seconds = time.perf_counter() - started
        results = {}
        for case in cases:
            started = time.perf_counter()
            docs = service.vector_store.similarity_search(case['query'], k=5)
            seconds = time.perf_counter() - started
            docs = [{'text':d.page_content, 'metadata':d.metadata} for d in docs]
            results[case['id']] = {'docs':docs, 'seconds':seconds, 'metrics':retrieval_metrics(case, docs)}
        scored = [v for v in results.values() if v['metrics'] is not None]
        summary = {'chunk_size':size, 'overlap':20, 'index_seconds':index_seconds,
                   'chunks':len(service.vector_store.get(include=[])['ids']),
                   'hit':{str(k):sum(r['metrics']['hit'][str(k)] for r in scored) for k in (1,3,5)},
                   'mean_context_chars':{str(k):statistics.mean(sum(len(r['text']) for r in v['docs'][:k]) for v in results.values()) for k in (1,3,5)},
                   'retrieval_median':statistics.median(v['seconds'] for v in results.values()),
                   'retrieval_p95':percentile([v['seconds'] for v in results.values()], .95)}
        dump(path, {'config':config, 'dataset_sha256':digest(ROOT/'evaluation/cases.jsonl'),
                    'summary':summary, 'results':results})
        summaries.append(summary)
        dump(directory/'summary.json', summaries)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    dump(directory/'summary.json', summaries)


if __name__ == '__main__':
    main()
