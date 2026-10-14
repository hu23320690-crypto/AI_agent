"""Resumable service evaluation: isolated worker and database per task."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from evaluation.service_eval import (ROOT, canonical, database_snapshot, digest, distinct_proposals,
                                     dump, matches, proposal_ref, read_rows, write_rows)

DEV = 'evaluation/service_v1/dev.jsonl'
FORMAL = ('evaluation/service_v1/test.jsonl', 'evaluation/service_injection_v1/cases.jsonl')


def frozen_hashes(root=ROOT):
    base = Path(root) / 'evaluation/service_v1'
    manifest = json.loads((base / 'freeze_manifest.json').read_text(encoding='utf-8'))
    hashes = dict(manifest['files'])
    amendment_path = base / 'freeze_amendments.json'
    if amendment_path.exists():
        for amendment in json.loads(amendment_path.read_text(encoding='utf-8'))['amendments']:
            name = amendment['file']
            if hashes.get(name) != amendment['old_sha256']:
                raise ValueError('Broken freeze amendment chain')
            hashes[name] = amendment['new_sha256']
    return hashes


def verify_dataset(dataset, *, formal=False, root=ROOT, environ=None):
    """Gate by canonical path BEFORE reading/hash-opening a restricted input."""
    root, dataset = Path(root).resolve(), Path(dataset).resolve()
    env = os.environ if environ is None else environ
    if dataset != (root / DEV).resolve():
        if (dataset not in {(root / name).resolve() for name in FORMAL} or
                not formal or env.get('SERVICE_EVAL_FORMAL') != '1'):
            raise ValueError('Only dev.jsonl is allowed; formal evaluation requires --formal AND SERVICE_EVAL_FORMAL=1')
    name = dataset.relative_to(root).as_posix()
    if digest(dataset) != frozen_hashes(root).get(name):
        raise ValueError('Frozen dataset hash mismatch')
    rows = read_rows(dataset)
    ids = [row['id'] for row in rows]
    if not rows or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[A-Za-z0-9_-]+', key) for key in ids):
        raise ValueError('Empty dataset or unsafe/duplicate case ID')
    return rows


def input_hashes():
    files = []
    for directory in ('agent', 'rag', 'utils', 'model', 'prompts', 'config', 'service_desk'):
        files.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and
                     p.suffix in ('.py', '.sql', '.txt', '.json', '.yml', '.gz') and '__pycache__' not in p.parts)
    files.extend(ROOT / 'evaluation' / name for name in
                 ('service_run.py', 'service_eval.py', 'service_trace.py', 'service_fake.py', 'service_injection.py')
                 if (ROOT / 'evaluation' / name).exists())
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)}


def environment_identity(dataset, *, timeout=240, mode='react', seed=20261014, ids=None, script=None):
    from service_desk.config import load_config
    config = load_config()
    if script:
        models = {'scripted': {'digest': digest(script)}}
    else:
        # Metadata lookup resolves mutable tags; it does not generate text.
        import urllib.request
        import yaml
        config_model = yaml.safe_load((ROOT / 'config/rag.yml').read_text(encoding='utf-8'))
        host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/')
        with urllib.request.urlopen(host + '/api/tags', timeout=10) as response:
            available = json.load(response)['models']
        models = {}
        for role, key in (('chat', 'chat_model_name'), ('embedding', 'embedding_model_name')):
            name = config_model[key]
            matched = [m for m in available if m['name'] in (name, name + ':latest')]
            if len(matched) != 1:
                raise ValueError('Model tag unavailable or ambiguous: ' + name)
            models[role] = {'name': matched[0]['name'], 'digest': matched[0]['digest']}
    source_names = [p for folder in ('service_kb', 'data') for p in (ROOT / folder).rglob('*') if p.is_file()]
    source_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(source_names)}
    cases = read_rows(dataset)
    overlays = {case['injection']['overlay'] for case in cases if case.get('injection')}
    for name in overlays:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Overlay escapes repository')
        source_hashes[name] = digest(path)
    return {'runner': 'service', 'identity_version': 1, 'code_sha256': input_hashes(),
            'source_sha256': source_hashes, 'dataset_sha256': digest(dataset),
            'dataset_path': Path(dataset).resolve().relative_to(ROOT).as_posix(),
            'freeze_sha256': {name: digest(ROOT / 'evaluation/service_v1' / name)
                              for name in ('freeze_manifest.json', 'freeze_amendments.json')},
            'service_config': config, 'model_identity': models, 'script_sha256': digest(script) if script else None,
            'mode': mode, 'toolset': 'service', 'seed': seed, 'ids': sorted(ids) if ids else None,
            'timeout_seconds': timeout, 'inference_concurrency': 1, 'python': sys.version,
            'platform': platform.platform(), 'ollama_host': os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'),
            'dependencies': {name: importlib.metadata.version(name) for name in ('langchain', 'langchain-core', 'langgraph')}}


def assert_resume_identity(previous, current):
    changed = [key for key, value in current.items() if previous.get(key) != value]
    if changed:
        raise ValueError('Cannot resume changed evaluation identity: ' + ', '.join(changed))


def create_seed(path):
    from service_desk.db import init_db, content_sha256
    from service_desk.config import load_config
    init_db(path)
    observed = content_sha256(path)
    if observed != load_config()['seed_content_sha256']:
        raise ValueError('Seed normalized content hash mismatch')
    return observed


def cards_since(path, previous):
    snapshot = database_snapshot(path)
    return [{'action_id': row['action_id'], 'tool': row['tool'], 'args': json.loads(row['args_json']),
             'args_sha256': row['args_sha256'], 'created_at': row['created_at'],
             'expires_at': row['expires_at'], 'status': row['status']}
            for row in sorted(snapshot['pending_actions'], key=lambda row: (row['created_at'], row['action_id']))
            if row['action_id'] not in previous]


def careful_event(agent, case, row, event):
    from service_desk.actions import confirm_action, reject_action
    start = time.perf_counter()
    n, k = proposal_ref(event['proposal_ref'])
    specs = [turn for turn in case['turns'] if turn['type'] == 'user']
    wanted = specs[n-1]['expected_proposals'][k]
    actual_turn = next((turn for turn in row['turns'] if turn['user_turn'] == n), {})
    cards = actual_turn.get('proposals', [])
    chosen = None
    status = 'ok'
    operation = event['type']
    if operation == 'confirm':
        chosen = next((card for card in cards if matches(wanted, card)), None)
        if chosen is None and cards:
            status, operation = 'proposal_mismatch', 'reject'
            chosen = cards[k] if k < len(cards) else cards[-1]
    else:
        chosen = cards[k] if k < len(cards) else None
    entry = {'type': event['type'], 'proposal_ref': event['proposal_ref'], 'operation': operation,
             'started_at': datetime.now(timezone.utc).isoformat(),
             'status': status if chosen else 'missing_proposal', 'action_id': chosen['action_id'] if chosen else None}
    if chosen:
        # Archive the exact card being confirmed; H2 checks this as well as DB hashes.
        entry['card'] = dict(chosen)
        result = (confirm_action if operation == 'confirm' else reject_action)(agent.service_state, chosen['action_id'])
        entry['result'] = result
        result_for_history = {**result, 'operation': operation}
        entry['history_recorded'] = agent.record_action_event(result_for_history)
        expected_status = 'executed' if operation == 'confirm' else 'rejected'
        if result.get('status') != expected_status and entry['status'] == 'ok':
            entry['status'] = 'action_failed'
    entry['seconds'] = time.perf_counter() - start
    row['operations'].append(entry)
    return entry


def execute_case(case, db_path, *, spec=None, on_change=None, agent_factory=None):
    """Trusted in-process entry used only with synthetic cases in tests."""
    from evaluation.service_trace import TurnTrace
    from service_desk.db import content_sha256
    from evaluation.service_fake import offline_dependencies, scripted_model
    on_change = on_change or (lambda row: None)
    row = {'id': case['id'], 'user_id': case['user_id'], 'mode': 'react', 'status': 'running',
           'session_id': str(uuid4()), 'turns': [], 'operations': [], 'db_path': str(db_path),
           'initial_db': database_snapshot(db_path)}
    on_change(row)
    with offline_dependencies(spec) if spec is not None else nullcontext():
        from agent.react_agent import ReactAgent
        kwargs = {'user_id': case['user_id'], 'session_id': row['session_id'], 'service_db_path': db_path}
        if spec is not None:
            kwargs['model'] = scripted_model(spec)
            from agent.context_budget import ContextPolicy
            # Fake providers count UTF-8 bytes, unlike the pinned Qwen tokenizer.
            kwargs['context_policy'] = ContextPolicy(window_tokens=32768, reserve_output_tokens=1024,
                                                     reasoning_enabled=False)
        agent = (agent_factory or ReactAgent)(**kwargs)
        if agent.toolset != 'service':
            raise ValueError('Runner requires service toolset')
        if case.get('injection'):
            from evaluation.service_injection import install_overlay
            row['injection'] = install_overlay(case['injection'], agent.service_state, db_path)
        # Baseline for gates follows the intended injection overlay.
        row['initial_db'] = database_snapshot(db_path)
        user_turn = 0
        try:
            for event in case['turns']:
                if event['type'] != 'user':
                    careful_event(agent, case, row, event)
                    on_change(row)
                    continue
                user_turn += 1
                before = {card['action_id'] for card in row['initial_db']['pending_actions']}
                before.update(card['action_id'] for turn in row['turns'] for card in turn.get('proposals', []))
                turn = {'type': 'user', 'user_turn': user_turn, 'query': event['query'], 'status': 'running',
                        'answer': '', 'proposals': [], 'tool_calls': [], 'model_requests': []}
                row['turns'].append(turn)
                started = time.perf_counter()
                def observed():
                    turn.update(trace.snapshot())
                    on_change(row)
                trace = TurnTrace(observed)
                agent.turn_trace = trace
                on_change(row)
                try:
                    turn['answer'] = ''.join(agent.execute_stream(event['query']))
                    turn['status'] = 'ok'
                except BaseException as error:
                    kind = type(error).__name__
                    turn.update(status='truncated' if kind == 'IncompleteModelOutput' else
                                'timeout' if kind in ('DeadlineExceeded', 'CallTimeout') else 'error',
                                error_type=kind, error=str(error))
                    raise
                finally:
                    turn.update(trace.snapshot(), runtime=agent.last_run, seconds=time.perf_counter()-started)
                    turn['proposals'] = distinct_proposals(cards_since(db_path, before))
                    for index, proposal in enumerate(turn['proposals']):
                        proposal['proposal_ref'] = f't{user_turn}.p{index}'
                    on_change(row)
            row['status'] = 'ok'
        except BaseException as error:
            row.update(status=row['turns'][-1]['status'] if row['turns'] and row['turns'][-1]['status'] != 'ok' else 'error',
                       error_type=type(error).__name__, error=str(error))
        finally:
            row['final_db'] = database_snapshot(db_path)
            row['db_content_sha256'] = content_sha256(db_path)
            if case.get('injection'):
                from evaluation.service_injection import exposure
                row.update(exposure(case['injection'], row['turns'], complete=row['status'] == 'ok'))
            on_change(row)
    return row


def run_task(case, run, *, timeout=240, script=None):
    """Claim BEFORE dispatch: an interrupted/failed/timed-out case never reruns."""
    raw = run / 'raw' / (case['id'] + '.json')
    if raw.exists():
        return json.loads(raw.read_text(encoding='utf-8'))
    db = run / 'databases' / (case['id'] + '.db')
    claim = {'id': case['id'], 'user_id': case['user_id'], 'mode': 'react', 'status': 'error',
             'error_type': 'InterruptedRun', 'error': 'Claimed task without terminal worker result',
             'turns': [], 'operations': [], 'db_path': str(db),
             'initial_db': database_snapshot(run / 'seed.db')}
    with raw.open('x', encoding='utf-8') as handle:
        handle.write(canonical(claim) + '\n')
    shutil.copyfile(run / 'seed.db', db)
    partial = run / 'workers' / (case['id'] + '.json')
    command = [sys.executable, '-B', '-m', 'evaluation.service_run', '--worker', '--run', str(run), '--case', case['id']]
    if script:
        command += ['--script', str(script)]
    started = time.perf_counter()
    with (run / 'logs' / (case['id'] + '.log')).open('w', encoding='utf-8') as log:
        try:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
                           check=True, env={**os.environ, 'AGENT_TOOLSET': 'service', 'PYTHONUTF8': '1'})
            row = json.loads(partial.read_text(encoding='utf-8'))
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            row = json.loads(partial.read_text(encoding='utf-8')) if partial.exists() else claim
            timed_out = isinstance(error, subprocess.TimeoutExpired)
            row.update(status='timeout' if timed_out else 'error', error_type=type(error).__name__,
                       error=str(error), timeout_seconds=timeout)
            for turn in row['turns']:
                if turn['status'] == 'running':
                    turn.update(status=row['status'], error_type=type(error).__name__,
                                seconds=min(timeout, time.perf_counter()-started))
    row['wall_seconds'] = time.perf_counter() - started
    from service_desk.db import content_sha256
    row.update(final_db=database_snapshot(db), db_content_sha256=content_sha256(db))
    if case.get('injection'):
        from evaluation.service_injection import exposure
        row.update(exposure(case['injection'], row['turns'], complete=row['status'] == 'ok'))
    dump(raw, row)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default=DEV)
    parser.add_argument('--run', required=True)
    parser.add_argument('--mode', choices=('react', 'plan'), default='react')
    parser.add_argument('--timeout', type=float, default=240)
    parser.add_argument('--seed', type=int, default=20261014)
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--formal', action='store_true')
    parser.add_argument('--script', help='Explicit JSON scripts, never generated from gold')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--case', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.mode == 'plan':
        parser.error('plan 模式由 S3 实现')
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    run = Path(args.run).resolve()
    if args.worker:
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        source = ROOT / manifest['dataset_path']
        cases = verify_dataset(source, formal=manifest.get('formal', False))
        assert_resume_identity(manifest, environment_identity(source, timeout=manifest['timeout_seconds'],
            mode=manifest['mode'], seed=manifest['seed'], ids=manifest['ids'], script=args.script))
        case = next(case for case in cases if case['id'] == args.case)
        spec = json.loads(Path(args.script).read_text(encoding='utf-8'))[case['id']] if args.script else None
        execute_case(case, run / 'databases' / (case['id'] + '.db'), spec=spec,
                     on_change=lambda row: dump(run / 'workers' / (case['id'] + '.json'), row))
        return 0
    dataset = Path(args.dataset)
    if not dataset.is_absolute():
        dataset = ROOT / dataset
    cases = verify_dataset(dataset, formal=args.formal)
    selected = [case for case in cases if not args.ids or case['id'] in args.ids]
    if not selected or (args.ids and set(args.ids) - {case['id'] for case in cases}):
        parser.error('Unknown/empty case selection')
    identity = environment_identity(dataset, timeout=args.timeout, mode=args.mode, seed=args.seed,
                                    ids=args.ids, script=args.script)
    if run.exists() and not (run / 'manifest.json').exists() and any(run.iterdir()):
        raise ValueError('Run directory is nonempty without an identity manifest')
    run.mkdir(parents=True, exist_ok=True)
    if (run / 'manifest.json').exists():
        manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        assert_resume_identity(manifest, identity)
        if digest(run / 'cases.jsonl') != manifest['cases_sha256']:
            raise ValueError('Stored cases changed')
    else:
        for folder in ('raw', 'workers', 'logs', 'databases', 'snapshot'):
            (run / folder).mkdir(exist_ok=True)
        write_rows(run / 'cases.jsonl', selected)
        for name in {*identity['code_sha256'], *identity['source_sha256']}:
            target = run / 'snapshot' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        manifest = {**identity, 'formal': args.formal, 'cases_sha256': digest(run / 'cases.jsonl'),
                    'started_at': datetime.now(timezone.utc).isoformat(), 'planned_tasks': len(selected),
                    'note': 'Scripted smoke is pipeline validation, not model quality evidence.' if args.script else
                            'Automatic scores exclude answer content and faithfulness.'}
        dump(run / 'manifest.json', manifest)
    with tempfile.TemporaryDirectory(prefix='service-eval-seed-') as temporary:
        seed = Path(temporary) / 'seed.db'
        create_seed(seed)
        if (run / 'seed.db').exists():
            from service_desk.db import content_sha256
            if content_sha256(run / 'seed.db') != identity['service_config']['seed_content_sha256']:
                raise ValueError('Stored seed changed')
        else:
            shutil.copyfile(seed, run / 'seed.db')
    rows = []
    for case in selected:
        assert_resume_identity(identity, environment_identity(dataset, timeout=args.timeout, mode=args.mode,
            seed=args.seed, ids=args.ids, script=args.script))
        row = run_task(case, run, timeout=args.timeout, script=args.script)
        rows.append(row)
        write_rows(run / 'results.jsonl', rows)
        print(case['id'], row['status'], flush=True)
    return int(any(row['status'] != 'ok' for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
