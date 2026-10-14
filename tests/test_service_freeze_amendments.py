"""Amendment-aware hash checks cannot exempt any other frozen input."""
import hashlib
import json
import subprocess
import sys

import pytest

from scripts.check_service_freeze import ROOT, accepted_hashes, check_file_hashes, check_freeze


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def inventory(tmp_path):
    contracts, config = b'original contracts', b'original config'
    for name, data in [('service_desk/contracts.py', contracts), ('config/service.yml', config)]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {'files': {'service_desk/contracts.py': digest(contracts), 'config/service.yml': digest(config)}}
    record = {'number': '01', 'date': '2026-10-14', 'file': 'service_desk/contracts.py',
        'old_sha256': digest(contracts), 'new_sha256': digest(b'amended contracts'),
        'reason': '三个自由文本字段允许LF/TAB', 'approval': '作者 2026-10-14 批准',
        'gold_impact': '无', 'verification': ['hash-only check']}
    return tmp_path, manifest, {'version': 1, 'amendments': [record]}


@pytest.mark.parametrize('content,ok', [(b'original contracts', True), (b'amended contracts', True), (b'unregistered change', False)])
def test_original_or_latest_approved_hash_is_accepted(inventory, content, ok):
    root, manifest, amendments = inventory
    (root / 'service_desk/contracts.py').write_bytes(content)
    result = check_file_hashes(root, manifest, amendments)
    assert result['checked'] == 2 and result['ok'] is ok
    assert result['failures'] == ([] if ok else ['service_desk/contracts.py'])


def test_superseded_amendment_hash_is_not_an_extra_exemption(inventory):
    root, manifest, amendments = inventory
    previous = amendments['amendments'][0]
    amendments['amendments'].append(previous | {'number': '02', 'old_sha256': previous['new_sha256'],
                                              'new_sha256': digest(b'latest contracts')})
    (root / 'service_desk/contracts.py').write_bytes(b'amended contracts')
    assert check_file_hashes(root, manifest, amendments)['failures'] == ['service_desk/contracts.py']
    (root / 'service_desk/contracts.py').write_bytes(b'latest contracts')
    assert check_file_hashes(root, manifest, amendments)['ok']


def test_contract_amendment_cannot_skip_other_frozen_files(inventory):
    root, manifest, amendments = inventory
    amendments['amendments'][0]['verification'] = ['skip config/service.yml']
    (root / 'config/service.yml').write_bytes(b'changed config')
    result = check_file_hashes(root, manifest, amendments)
    assert result == {'ok': False, 'checked': 2, 'failures': ['config/service.yml']}


@pytest.mark.parametrize('change,needle', [
    ({'file': 'config/service.yml'}, 'scope'),
    ({'file': '../outside'}, 'scope'),
    ({'old_sha256': '0'*64}, 'chain'),
    ({'new_sha256': 'not-a-hash'}, 'new hash'),
    ({'approval': 'unapproved'}, 'approval'),
    ({'gold_impact': 'changed'}, 'gold review'),
    ({'number': '1'}, 'number'),
])
def test_unapproved_scope_or_invalid_chain_is_rejected(inventory, change, needle):
    _, manifest, amendments = inventory
    amendments['amendments'][0].update(change)
    with pytest.raises(ValueError, match=needle):
        accepted_hashes(manifest, amendments)


def test_manifest_itself_cannot_be_rewritten(tmp_path):
    path = tmp_path / 'evaluation/service_v1/freeze_manifest.json'
    path.parent.mkdir(parents=True)
    path.write_text('{"files":{}}', encoding='utf-8')
    with pytest.raises(ValueError, match='original freeze manifest changed'):
        check_freeze(tmp_path)


def test_committed_freeze_with_amendment_passes_hash_only_cli():
    result = check_freeze()
    assert result == {'ok': True, 'checked': 26, 'failures': []}
    run = subprocess.run([sys.executable, '-B', 'scripts/check_service_freeze.py'], cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == result
