"""New switch coverage; existing regressions are left unchanged."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent.toolset import load_toolset

ROOT = Path(__file__).resolve().parents[1]


def test_default_toolset(monkeypatch):
    monkeypatch.delenv('AGENT_TOOLSET', raising=False)
    assert load_toolset() == 'legacy'


@pytest.mark.parametrize('mode', ['legacy', 'service'])
def test_toolset_environment_override(monkeypatch, mode):
    monkeypatch.setenv('AGENT_TOOLSET', mode)
    assert load_toolset() == mode


@pytest.mark.parametrize('mode', ['', 'SERVICE', 'invalid'])
def test_invalid_toolset_environment(monkeypatch, mode):
    monkeypatch.setenv('AGENT_TOOLSET', mode)
    with pytest.raises(ValueError, match='legacy or service'):
        load_toolset()


@pytest.mark.parametrize('text', ['toolset: other', 'toolset: 1', '[]', 'toolset: legacy\nextra: yes'])
def test_invalid_toolset_config(monkeypatch, tmp_path, text):
    monkeypatch.delenv('AGENT_TOOLSET', raising=False)
    path = tmp_path / 'toolset.yml'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        load_toolset(path)


def test_doctor_rejects_invalid_toolset(monkeypatch):
    monkeypatch.setenv('AGENT_TOOLSET', 'invalid')
    result = subprocess.run([sys.executable, '-B', 'scripts/manage.py', 'doctor', '--offline'],
                            cwd=ROOT, capture_output=True, encoding='utf-8',
                            env={**os.environ, 'PYTHONUTF8': '1'})
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert [item['name'] for item in report['failures']] == ['config/toolset.yml']
