"""Offline draft manifest validation; does not ingest or create a collection."""
import hashlib
import json
from pathlib import Path
import re


def validate_manifest(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if (not isinstance(manifest, dict) or set(manifest) != {'version', 'files'}
            or type(manifest['version']) is not int or manifest['version'] != 1):
        raise ValueError('invalid service knowledge manifest')
    entries = manifest['files']
    if not isinstance(entries, list) or len(entries) != 7:
        raise ValueError('expected seven knowledge drafts')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'file', 'sha256', 'models', 'description'}:
            raise ValueError('invalid manifest entry fields')
        name = entry['file']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_-]+\.txt', name) or name in seen:
            raise ValueError('invalid or duplicate knowledge filename')
        seen.add(name)
        models = entry['models']
        if (not isinstance(models, list) or not models or len(set(models)) != len(models)
                or (models != ['all'] and not set(models).issubset({'SV-100', 'SV-200', 'SV-300', 'SV-400'}))):
            raise ValueError('invalid knowledge model scope')
        if not isinstance(entry['description'], str) or not entry['description'].strip():
            raise ValueError('missing knowledge description')
        content = (directory / name).read_bytes()
        content.decode('utf-8')
        if hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError(f'knowledge hash mismatch: {name}')
    if {path.name for path in directory.glob('*.txt')} != seen:
        raise ValueError('knowledge files do not match manifest')
    return manifest
