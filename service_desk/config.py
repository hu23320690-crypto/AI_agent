"""Read only the new service configuration, independently of legacy config."""
from datetime import date
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    values = yaml.safe_load(Path(path or ROOT / 'config/service.yml').read_text(encoding='utf-8'))
    expected = {'business_date', 'db_path', 'kb_dir', 'pending_action_ttl_seconds', 'seed_content_sha256'}
    if not isinstance(values, dict) or set(values) != expected:
        raise ValueError('service configuration fields do not match')
    business_date = values['business_date']
    if not isinstance(business_date, str) or date.fromisoformat(business_date).isoformat() != business_date:
        raise ValueError('business_date must be an ISO date string')
    for name in ('db_path', 'kb_dir'):
        value = values[name]
        if not isinstance(value, str) or not value or '\\' in value or ':' in value:
            raise ValueError(f'{name} must be a repository-relative path')
        target = Path(value)
        if target.is_absolute() or '..' in target.parts or target == Path('.'):
            raise ValueError(f'{name} must stay within the repository')
    if type(values['pending_action_ttl_seconds']) is not int or values['pending_action_ttl_seconds'] <= 0:
        raise ValueError('pending_action_ttl_seconds must be a positive integer')
    if not isinstance(values['seed_content_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', values['seed_content_sha256']):
        raise ValueError('seed_content_sha256 must be a SHA256 hex digest')
    return values
