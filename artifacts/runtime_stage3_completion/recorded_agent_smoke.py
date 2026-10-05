"""Record an affected real two-turn flow and its actual retrieved evidence."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from evaluation.run import business_files, verify_dataset, telemetry, dump
from agent.react_agent import ReactAgent
from agent.tools.agent_tools import get_rag_service
from agent.runtime import current_run

import argparse
parser = argparse.ArgumentParser(description='真实 A11 复验，保存本次实际召回片段')
parser.add_argument('--run', required=True, help='已由 evaluation.run 新建的同版本目录')
args = parser.parse_args()
folder = Path(args.run)
if not folder.is_absolute():
    folder = ROOT/folder
if (folder/'agent_recheck.json').exists():
    raise RuntimeError('已有复验记录，拒绝覆写；请选择新的 --run 目录。')
folder.mkdir(parents=True, exist_ok=True)
before = business_files()
manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
assert manifest['code_sha256'] == before, 'Completion snapshot does not match current code'
case = next(c for c in verify_dataset() if c['id'] == 'A11')
service = get_rag_service()
original = service.retriever_docs
contexts = []

def record(query):
    docs = original(query)
    run = current_run()
    contexts.append({'query': query, 'run_id': run.run_id if run else None,
                     'docs': [{'text': d.page_content, 'metadata': dict(d.metadata)} for d in docs]})
    dump(folder/'agent_recheck_contexts.json', contexts)
    return docs

service.retriever_docs = record
recorder = telemetry()
agent = ReactAgent(case['user_id'], case['city'])
invoke = agent.agent.invoke
def traced(*args, **kwargs):
    config = dict(kwargs.get('config') or {})
    config['callbacks'] = [recorder]
    kwargs['config'] = config
    return invoke(*args, **kwargs)
agent.agent.invoke = traced
row = {'id': 'A11', 'note': '收尾代码复验；保存本次实际RAG片段，不覆写前次失败。',
       'status': 'ok', 'turns': [], 'code_sha256': before}
try:
    for turn in case['turns']:
        call_start = len(recorder.calls)
        result_start = len(recorder.results)
        start = time.perf_counter()
        answer = ''.join(agent.execute_stream(turn['query']))
        row['turns'].append({'query': turn['query'], 'answer': answer,
                             'seconds': time.perf_counter()-start,
                             'tool_calls': recorder.calls[call_start:],
                             'tool_results': recorder.results[result_start:], 'runtime': agent.last_run})
        dump(folder/'agent_recheck.json', row)
        print(json.dumps({'turn':len(row['turns']), 'answer':answer}, ensure_ascii=False), flush=True)
except Exception as exc:
    row.update(status='error', error_type=type(exc).__name__, error=str(exc), runtime=agent.last_run)
finally:
    service.retriever_docs = original
    row['model_calls'] = recorder.models
    row['code_unchanged'] = business_files() == before
    dump(folder/'agent_recheck.json', row)
    print(json.dumps({'status':row['status'], 'turns':len(row['turns']), 'code_unchanged':row['code_unchanged']}, ensure_ascii=False), flush=True)
if row['status'] != 'ok' or not row['code_unchanged']:
    raise SystemExit(1)
