"""Record actual deployed retrieval/answers for A11, A02 and the K14 rubric check."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from evaluation.harness import dump, environment, inputs, prepare_run
from evaluation.run import telemetry, verify_dataset

ROOT = Path(__file__).resolve().parents[1]


def worker(case_id, output):
    from agent.react_agent import ReactAgent
    from agent.tools.agent_tools import get_rag_service
    from rag.rag_service import RagSummarizeService
    from agent.runtime import current_run, RunContext, runtime_call
    case = next(c for c in verify_dataset() if c['id'] == case_id)
    contexts = []
    recorder = telemetry()
    service = get_rag_service() if case['kind'] == 'agent' else RagSummarizeService()
    original = service.retriever_docs
    def record(query):
        docs = original(query)
        run = current_run()
        contexts.append({'query': query, 'run_id': run.run_id if run else None,
                         'docs': [{'text': d.page_content, 'metadata': dict(d.metadata)} for d in docs]})
        return docs
    service.retriever_docs = record
    row = {'id': case_id, 'status': 'ok', 'turns': [], 'contexts': contexts}
    try:
        if case['kind'] == 'agent':
            agent = ReactAgent(case['user_id'], case['city'])
            original_invoke = agent.agent.invoke
            def traced(*args, **kwargs):
                kwargs['config'] = {**(kwargs.get('config') or {}), 'callbacks': [recorder]}
                return original_invoke(*args, **kwargs)
            agent.agent.invoke = traced
            for turn in case['turns']:
                call_start, result_start, start = len(recorder.calls), len(recorder.results), time.perf_counter()
                answer = ''.join(agent.execute_stream(turn['query']))
                row['turns'].append({'query': turn['query'], 'answer': answer,
                                     'seconds': time.perf_counter() - start,
                                     'tool_calls': recorder.calls[call_start:],
                                     'tool_results': recorder.results[result_start:], 'runtime': agent.last_run})
                dump(output, row)
        else:
            start = time.perf_counter()
            run = RunContext()
            try:
                answer = runtime_call('run', 'normal.rag', lambda: service.answer_documents(
                    case['query'], service.retriever_docs(case['query']), config={'callbacks': [recorder]}), run=run)
                run.complete()
            except Exception as exc:
                run.fail(exc)
                raise
            finally:
                row['runtime'] = run.snapshot()
            row['turns'].append({'query': case['query'], 'answer': answer, 'seconds': time.perf_counter() - start})
    except Exception as exc:
        row.update(status='error', error_type=type(exc).__name__)
    finally:
        service.retriever_docs = original
        row['model_calls'] = recorder.models
        row['tool_calls'] = recorder.calls
        dump(output, row)


def main():
    parser = argparse.ArgumentParser(description='Actual normal controls; save evidence, then review semantics separately')
    parser.add_argument('--run', default='evaluation/results/runtime_stage4_normal_v1')
    parser.add_argument('--worker')
    parser.add_argument('--output')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, Path(args.output))
        return
    folder = Path(args.run)
    if not folder.is_absolute():
        folder = ROOT / folder
    identity = {'files': inputs(), 'environment': environment(True), 'cases': ['K14', 'A11', 'A02'],
                'timeout_seconds': args.timeout, 'note': 'Runs current deployed index; verify source/code before and after each case.'}
    prepare_run(folder, identity)
    for case_id in identity['cases']:
        output = folder / 'jobs' / (case_id + '.json')
        if output.exists():
            continue
        if inputs() != identity['files']:
            raise RuntimeError('Normal evaluation inputs changed before case')
        print('Normal real ' + case_id, flush=True)
        attempt = case_id + '_' + uuid4().hex
        target = folder / 'workers' / (attempt + '.json')
        with (folder / 'logs' / (attempt + '.log')).open('x', encoding='utf-8') as log:
            try:
                result = subprocess.run([sys.executable, '-B', '-m', 'evaluation.normal_recheck',
                                         '--worker', case_id, '--output', str(target)], cwd=ROOT,
                                        env={**os.environ, 'PYTHONUTF8': '1'}, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=args.timeout)
                row = json.loads(target.read_text(encoding='utf-8')) if result.returncode == 0 and target.exists() else {
                    'id': case_id, 'status': 'error', 'error_type': 'WorkerFailure'}
            except subprocess.TimeoutExpired:
                row = {'id': case_id, 'status': 'timeout', 'outcome': 'unknown'}
        if inputs() != identity['files']:
            row.update(status='error', error_type='InputsChanged')
        dump(output, row)
    rows = [json.loads((folder / 'jobs' / (c + '.json')).read_text(encoding='utf-8')) for c in identity['cases']]
    dump(folder / 'results.json', rows)
    print(json.dumps([{'id': r['id'], 'status': r['status'], 'answers': [t['answer'] for t in r.get('turns', [])]} for r in rows], ensure_ascii=False), flush=True)
    return int(any(r['status'] != 'ok' for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
