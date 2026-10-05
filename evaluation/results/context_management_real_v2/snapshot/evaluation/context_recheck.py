"""Frozen synthetic long history + actual Ollama summarization and follow-ups.

The history is seeded, not 24 real user/model exchanges. Raw outputs remain
separate from semantic review. No production corpus or identity is changed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
import time
from unittest.mock import patch
from uuid import uuid4

from evaluation.harness import dump, environment, inputs, prepare_run

ROOT = Path(__file__).resolve().parents[1]


def seeded_history():
    from langchain_core.messages import AIMessage, HumanMessage
    messages = [HumanMessage(content='我今天要处理的是主刷毛发缠绕。说明要保留安全提醒；资料没写清楚时请明确说资料不足，不要猜。'),
                AIMessage(content='已记录你的处理对象和说明要求。')]
    for index in range(1, 24):
        messages.extend([HumanMessage(content=f'准备进度{index}，暂时不开始操作。'),
                         AIMessage(content=f'已记录进度{index}。')])
    return messages


def worker(output):
    from agent.react_agent import ReactAgent
    from langchain_ollama import ChatOllama
    from agent.context_budget import estimate_request
    agent = ReactAgent('1001')
    history = seeded_history()
    agent.messages = history
    models, lock = [], Lock()
    original = ChatOllama._generate
    def record(model, messages, *args, **kwargs):
        row = {'model': model.model, 'num_ctx': model.num_ctx,
               'num_predict': model.num_predict, 'reasoning': model.reasoning,
               'messages': [m.model_dump(mode='json') for m in messages],
               'estimated_messages_only': estimate_request(messages)}
        with lock:
            models.append(row)
        start = time.perf_counter()
        try:
            result = original(model, messages, *args, **kwargs)
            row['response'] = result.generations[0].message.model_dump(mode='json')
            row['status'] = 'ok'
            return result
        except Exception as exc:
            row.update(status='error', error_type=type(exc).__name__)
            raise
        finally:
            row['seconds'] = time.perf_counter() - start
    row = {'id': 'L01', 'status': 'ok', 'seeded_turns': 24,
           'note': '24 synthetic completed turns, followed by actual summary and actual questions.',
           'seeded_history': [m.model_dump(mode='json') for m in history],
           'turns': [], 'model_calls': models, 'semantic_review': None}
    try:
        with patch.object(ChatOllama, '_generate', record):
            for query in ('请回顾：我这次要处理哪个部件的问题？我对你的说明有什么要求？',
                          '那清理它之前需要断开电源吗？'):
                start = time.perf_counter()
                answer = ''.join(agent.execute_stream(query))
                row['turns'].append({'query': query, 'answer': answer,
                                     'seconds': time.perf_counter() - start,
                                     'summary': agent.summary, 'retained_messages': len(agent.messages),
                                     'runtime': agent.last_run})
                dump(output, row)
    except Exception as exc:
        row.update(status='error', error_type=type(exc).__name__, runtime=agent.last_run)
    finally:
        dump(output, row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='evaluation/results/context_management_real_v1')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    if args.worker:
        worker(Path(args.output))
        return 0
    folder = Path(args.run)
    if not folder.is_absolute():
        folder = ROOT / folder
    identity = {'files': inputs(), 'environment': environment(True), 'cases': ['L01'],
                'timeout_seconds': args.timeout, 'seeded_turns': 24}
    prepare_run(folder, identity)
    target = folder / 'jobs/L01.json'
    if not target.exists():
        attempt = 'L01_' + uuid4().hex
        output = folder / 'workers' / (attempt + '.json')
        with (folder / 'logs' / (attempt + '.log')).open('x', encoding='utf-8') as log:
            try:
                result = subprocess.run([sys.executable, '-B', '-m', 'evaluation.context_recheck',
                                         '--worker', '--output', str(output)], cwd=ROOT,
                                        env={**os.environ, 'PYTHONUTF8': '1'}, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=args.timeout)
                row = json.loads(output.read_text(encoding='utf-8')) if result.returncode == 0 and output.exists() else {
                    'id': 'L01', 'status': 'error', 'error_type': 'WorkerFailure'}
            except subprocess.TimeoutExpired:
                row = {'id': 'L01', 'status': 'timeout', 'outcome': 'unknown'}
        if inputs() != identity['files']:
            row.update(status='error', error_type='InputsChanged')
        dump(target, row)
    row = json.loads(target.read_text(encoding='utf-8'))
    dump(folder / 'results.json', [row])
    print(json.dumps({'id': row['id'], 'status': row['status'],
                      'answers': [turn['answer'] for turn in row.get('turns', [])],
                      'model_calls': len(row.get('model_calls', []))}, ensure_ascii=False), flush=True)
    return int(row['status'] != 'ok')


if __name__ == '__main__':
    raise SystemExit(main())
