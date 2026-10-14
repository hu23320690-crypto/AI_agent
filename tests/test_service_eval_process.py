"""Real isolated Python processes and wall timeout, using synthetic scripts only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from evaluation.service_eval import ROOT, dump
from evaluation.service_run import create_seed, run_task


@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    path = tmp_path_factory.mktemp('synthetic-process') / 'seed.db'
    create_seed(path)
    return path


def run_directory(seed, tmp_path):
    for folder in ('raw', 'databases', 'logs', 'workers'):
        (tmp_path / folder).mkdir()
    shutil.copyfile(seed, tmp_path / 'seed.db')
    return tmp_path


def test_wall_timeout_and_failed_claim_are_never_reexecuted(seed, tmp_path, monkeypatch):
    run = run_directory(seed, tmp_path)
    script = tmp_path / 'worker.py'
    script.write_text('import time\ntime.sleep(10)\n', encoding='utf-8')
    original = subprocess.run
    count = []
    def dispatch(command, **kwargs):
        count.append(1)
        return original([sys.executable, '-B', str(script)], **kwargs)
    monkeypatch.setattr('evaluation.service_run.subprocess.run', dispatch)
    case = {'id': 'SYN-TIMEOUT', 'user_id': '1001'}
    row = run_task(case, run, timeout=.2)
    assert row['status'] == 'timeout'
    assert row['initial_db']['devices'] and row['db_content_sha256']
    assert run_task(case, run, timeout=.2) == row
    assert len(count) == 1


def test_case_is_run_in_a_different_process_with_its_own_database(seed, tmp_path, monkeypatch):
    run = run_directory(seed, tmp_path)
    script = tmp_path / 'worker.py'
    script.write_text(
        'import sys, os\nfrom pathlib import Path\n'
        'sys.path.insert(0, ' + repr(str(ROOT)) + ')\n'
        'sys.path.insert(0, ' + repr(str(ROOT / 'tests')) + ')\n'
        'from evaluation.service_run import execute_case\n'
        'from evaluation.service_eval import dump\n'
        'from test_service_eval_runner import synthetic_case, script\n'
        'run=Path(sys.argv[1])\n'
        'row=execute_case(synthetic_case(), run / "databases/SYN-ORDER.db", spec=script())\n'
        'row["worker_pid"]=os.getpid()\n'
        'dump(run / "workers/SYN-ORDER.json",row)\n', encoding='utf-8')
    original = subprocess.run
    def dispatch(command, **kwargs):
        return original([sys.executable, '-B', str(script), str(run)], **kwargs)
    monkeypatch.setattr('evaluation.service_run.subprocess.run', dispatch)
    row = run_task({'id': 'SYN-ORDER', 'user_id': '1001'}, run, timeout=30)
    assert row['status'] == 'ok' and row['worker_pid'] != os.getpid()
    from service_desk.db import content_sha256
    assert row['db_content_sha256'] != content_sha256(run / 'seed.db')
    assert content_sha256(run / 'seed.db') == content_sha256(seed)


def test_worker_missing_record_is_preserved_as_error(seed, tmp_path, monkeypatch):
    run = run_directory(seed, tmp_path)
    monkeypatch.setattr('evaluation.service_run.subprocess.run', lambda command, **k: subprocess.CompletedProcess(command, 0))
    row = run_task({'id': 'SYN-NO-RECORD', 'user_id': '1001'}, run)
    assert row['status'] == 'error' and row['error_type'] == 'FileNotFoundError'


def test_post_worker_input_change_is_recorded_and_not_retried(seed, tmp_path, monkeypatch):
    run = run_directory(seed, tmp_path)
    dump(run / 'workers/SYN-CHANGED.json', {'id': 'SYN-CHANGED', 'user_id': '1001', 'status': 'ok', 'turns': [], 'operations': []})
    monkeypatch.setattr('evaluation.service_run.subprocess.run', lambda command, **k: subprocess.CompletedProcess(command, 0))
    def changed():
        raise ValueError('synthetic identity changed')
    case = {'id': 'SYN-CHANGED', 'user_id': '1001'}
    row = run_task(case, run, validate_identity=changed)
    assert row['status'] == 'error' and row['error_type'] == 'InputsChanged'
    assert run_task(case, run) == row


def test_resume_rejects_changed_task_database(seed, tmp_path):
    run = run_directory(seed, tmp_path)
    shutil.copyfile(seed, run / 'databases/SYN-CHANGED.db')
    dump(run / 'raw/SYN-CHANGED.json', {'id': 'SYN-CHANGED', 'status': 'ok', 'db_content_sha256': '0' * 64})
    with pytest.raises(ValueError, match='Stored task database changed'):
        run_task({'id': 'SYN-CHANGED'}, run)
