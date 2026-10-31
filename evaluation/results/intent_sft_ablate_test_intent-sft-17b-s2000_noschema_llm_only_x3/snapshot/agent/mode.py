"""Trusted execution mode, loaded independently from toolset selection."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_agent_mode(path=None):
    values = yaml.safe_load(Path(path or ROOT / 'config/agent_mode.yml').read_text(encoding='utf-8'))
    if not isinstance(values, dict) or set(values) != {'mode'}:
        raise ValueError('agent mode configuration must contain only mode')
    selected = os.environ.get('AGENT_MODE', values['mode'])
    if not isinstance(selected, str) or selected not in {'react', 'plan'}:
        raise ValueError('agent mode must be react or plan')
    return selected


def check_agent_mode():
    from agent.toolset import load_toolset
    if load_agent_mode() == 'plan' and load_toolset() != 'service':
        raise ValueError('plan mode requires service toolset')
