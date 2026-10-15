"""Runner CLI and child workers propagate plan mode, using synthetic cases."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest

from evaluation.service_eval import ROOT
from evaluation.service_run import execute_case, main
from test_service_agent import db, seed_path
from test_service_plan_agent import warranty_plan


def synthetic_case():
    return {'id': 'SYN-PLAN', 'user_id': '1002', 'turns': [
        {'type': 'user', 'query': '查设备保修', 'expect': 'answer',
         'required_tools': ['list_my_devices', 'check_warranty'],
         'allowed_tools': ['list_my_devices', 'check_warranty'], 'expected_proposals': []}]}


def test_runner_plan_fake(monkeypatch, db):
    monkeypatch.setenv('AGENT_TOOLSET', 'service')
    monkeypatch.setenv('AGENT_MODE', 'react')
    row = execute_case(synthetic_case(), db, mode='plan', spec={'responses': [{'plan': warranty_plan()}]})
    assert row['status'] == 'ok' and row['mode'] == 'plan'
    turn = row['turns'][0]
    assert turn['runtime']['planner_calls'] == 1 and '保修（D-1002-01' in turn['answer']
    assert [call['name'] for call in turn['tool_calls']] == ['list_my_devices', 'check_warranty']
    assert os.environ['AGENT_MODE'] == 'react'


@pytest.fixture
def synthetic_dataset():
    # The real identity contract stores repository-relative dataset paths.
    # Keep only this self-authored input under the repo on every operating system.
    scratch = ROOT / 'work'
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='s3c-synthetic-', dir=scratch) as folder:
        yield Path(folder) / 'synthetic.jsonl'


def test_cli_plan_manifest_and_worker(monkeypatch, tmp_path, synthetic_dataset):
    # Only replace the dataset source with a self-authored synthetic case in this
    # test process; production path/hash gates remain the real implementation.
    from evaluation import service_run
    case = synthetic_case()
    dataset = synthetic_dataset
    dataset.write_text(json.dumps(case, ensure_ascii=False) + '\n', encoding='utf-8')
    script = tmp_path / 'script.json'
    script.write_text(json.dumps({case['id']: {'responses': [{'plan': warranty_plan()}]}}), encoding='utf-8')
    monkeypatch.setattr(service_run, 'verify_dataset', lambda *a, **k: [case])
    worker = tmp_path / 'worker.py'
    worker.write_text(
        'import json,sys\nfrom pathlib import Path\n'
        f'sys.path.insert(0, {str(ROOT)!r})\n'
        'from evaluation import service_run\n'
        f'case=json.loads({json.dumps(json.dumps(case))})\n'
        'service_run.verify_dataset=lambda *a,**k:[case]\n'
        'raise SystemExit(service_run.main(sys.argv[1:]))\n', encoding='utf-8')
    original = subprocess.run
    seen = []
    def dispatch(command, **kwargs):
        seen.append(command)
        return original([sys.executable, '-B', str(worker), *command[4:]], **kwargs)
    monkeypatch.setattr(service_run.subprocess, 'run', dispatch)
    run = tmp_path / 'run'
    assert main(['--dataset', str(dataset), '--run', str(run), '--mode', 'plan', '--script', str(script)]) == 0
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    raw = json.loads((run / 'raw/SYN-PLAN.json').read_text(encoding='utf-8'))
    assert manifest['mode'] == raw['mode'] == 'plan'
    assert raw['turns'][0]['runtime']['planner_calls'] == 1
    command = next(c for c in seen if isinstance(c, list) and '--worker' in c)
    assert command[-2:] == ['--script', str(script)]
    assert '--mode' in command and 'plan' in command
