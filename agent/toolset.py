"""Trusted toolset selection, independent of legacy configuration."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLSETS = frozenset({'legacy', 'service'})


def load_toolset(path=None):
    """Read config and the effective environment override on each call."""
    values = yaml.safe_load(Path(path or ROOT / 'config/toolset.yml').read_text(encoding='utf-8'))
    if not isinstance(values, dict) or set(values) != {'toolset'}:
        raise ValueError('toolset configuration must contain only toolset')
    selected = os.environ.get('AGENT_TOOLSET', values['toolset'])
    if not isinstance(selected, str) or selected not in TOOLSETS:
        raise ValueError('toolset must be legacy or service')
    return selected
