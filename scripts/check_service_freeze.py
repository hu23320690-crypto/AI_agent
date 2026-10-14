"""Hash-only frozen inventory verification with author-approved amendments.

No task-set or knowledge text is decoded. The original manifest is immutable;
amendment 01 can change only contracts.py, never the other frozen inputs.
"""
from datetime import date
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SHA256 = '023009ffc9a2748fdea38b2f99ec81d5f37a64737a6432a78a60525f3b125502'
AMENDABLE_FILES = frozenset({'service_desk/contracts.py'})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_hashes(manifest, amendments):
    original = manifest['files']
    latest, last_number = {}, 0
    require(amendments.get('version') == 1, 'unsupported amendments version')
    for item in amendments['amendments']:
        number, name = item['number'], item['file']
        require(isinstance(number, str) and re.fullmatch(r'[0-9]{2}', number), 'invalid amendment number')
        require(int(number) > last_number, 'amendments must be in increasing order')
        last_number = int(number)
        require(name in original and name in AMENDABLE_FILES, 'file is outside approved amendment scope')
        require(date.fromisoformat(item['date']).isoformat() == item['date'], 'invalid amendment date')
        require(item['approval'] == '作者 2026-10-14 批准' and item['gold_impact'] == '无', 'amendment lacks author approval or gold review')
        require(item['reason'].strip() and item['verification'], 'incomplete amendment record')
        require(item['old_sha256'] == latest.get(name, original[name]), 'broken amendment hash chain')
        require(re.fullmatch(r'[a-f0-9]{64}', item['new_sha256']) and item['new_sha256'] != item['old_sha256'], 'invalid new hash')
        latest[name] = item['new_sha256']
    return {name: {old, latest.get(name, old)} for name, old in original.items()}


def check_file_hashes(root, manifest, amendments):
    root = Path(root).resolve()
    allowed = accepted_hashes(manifest, amendments)
    failures = []
    for name, expected in allowed.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root), 'frozen path escapes root')
        if not path.is_file() or sha256(path) not in expected:
            failures.append(name)
    return {'ok': not failures, 'checked': len(allowed), 'failures': failures}


def check_freeze(root=ROOT):
    root = Path(root)
    manifest_path = root / 'evaluation/service_v1/freeze_manifest.json'
    require(sha256(manifest_path) == MANIFEST_SHA256, 'original freeze manifest changed')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    amendments_path = root / 'evaluation/service_v1/freeze_amendments.json'
    amendments = json.loads(amendments_path.read_text(encoding='utf-8')) if amendments_path.exists() else {'version': 1, 'amendments': []}
    return check_file_hashes(root, manifest, amendments)


if __name__ == '__main__':
    result = check_freeze()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
