import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent.mode import load_agent_mode, check_agent_mode


def test_default_mode(monkeypatch):
    monkeypatch.delenv('AGENT_MODE', raising=False)
    assert load_agent_mode() == 'react'


@pytest.mark.parametrize('mode', ['react', 'plan'])
def test_mode_override(monkeypatch, mode):
    monkeypatch.setenv('AGENT_MODE', mode)
    assert load_agent_mode() == mode


@pytest.mark.parametrize('mode', ['', 'PLAN', 'invalid'])
def test_bad_mode(monkeypatch, mode):
    monkeypatch.setenv('AGENT_MODE', mode)
    with pytest.raises(ValueError):
        load_agent_mode()


@pytest.mark.parametrize('text', ['mode: other', 'mode: 1', '[]', 'mode: react\nextra: true'])
def test_bad_mode_config(monkeypatch, tmp_path, text):
    monkeypatch.delenv('AGENT_MODE', raising=False)
    path = tmp_path / 'mode.yml'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        load_agent_mode(path)


def test_doctor_rejects_plan_legacy(monkeypatch):
    result = subprocess.run([sys.executable, '-B', 'scripts/manage.py', 'doctor', '--offline'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, encoding='utf-8',
        env={**os.environ, 'AGENT_MODE': 'plan', 'AGENT_TOOLSET': 'legacy', 'PYTHONUTF8': '1'})
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert [f['name'] for f in report['failures']] == ['config/agent_mode.yml']
