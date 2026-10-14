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
    ({'file': 'unlisted.py'}, 'scope'),
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


def overlay_records(inventory):
    root, manifest, amendments = inventory
    records = []
    for name in ('SI-I04.txt', 'SI-I05.txt', 'SI-I06.txt'):
        path = 'evaluation/service_injection_v1/overlays/' + name
        original, revised = ('original ' + name).encode(), ('revised ' + name).encode()
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(revised)
        manifest['files'][path] = digest(original)
        records.append(amendments['amendments'][0] | {
            'number': '02', 'file': path, 'old_sha256': digest(original),
            'new_sha256': digest(revised), 'reason': '去掉首行元提示',
        })
    amendments['amendments'].extend(records)
    return records


def test_same_amendment_number_can_register_three_distinct_files(inventory):
    records = overlay_records(inventory)
    root, manifest, amendments = inventory
    assert check_file_hashes(root, manifest, amendments) == {'ok': True, 'checked': 5, 'failures': []}
    allowed = accepted_hashes(manifest, amendments)
    for record in records:
        assert allowed[record['file']] == {record['old_sha256'], record['new_sha256']}
    assert allowed['config/service.yml'] == {manifest['files']['config/service.yml']}


def test_another_frozen_file_needs_its_own_approved_record(inventory):
    root, manifest, amendments = inventory
    path, revised = 'config/service.yml', b'revised config'
    (root / path).write_bytes(revised)
    assert check_file_hashes(root, manifest, amendments)['failures'] == [path]
    amendments['amendments'].append(amendments['amendments'][0] | {
        'number': '02', 'file': path, 'old_sha256': manifest['files'][path],
        'new_sha256': digest(revised), 'reason': '显式批准的配置修订测试夹具',
    })
    assert check_file_hashes(root, manifest, amendments)['ok']


def test_overlay_record_does_not_allow_new_hash_on_unlisted_file(inventory):
    records = overlay_records(inventory)
    root, manifest, amendments = inventory
    (root / 'config/service.yml').write_bytes((root / records[0]['file']).read_bytes())
    assert check_file_hashes(root, manifest, amendments)['failures'] == ['config/service.yml']


def test_unregistered_change_to_amended_overlay_is_rejected(inventory):
    records = overlay_records(inventory)
    root, manifest, amendments = inventory
    (root / records[1]['file']).write_bytes(b'new unregistered content')
    assert check_file_hashes(root, manifest, amendments)['failures'] == [records[1]['file']]


def test_duplicate_file_in_one_amendment_is_rejected(inventory):
    records = overlay_records(inventory)
    _, manifest, amendments = inventory
    amendments['amendments'].append(dict(records[0]))
    with pytest.raises(ValueError, match='duplicate file'):
        accepted_hashes(manifest, amendments)


def test_grouped_records_still_require_order_and_per_file_hash_chain(inventory):
    records = overlay_records(inventory)
    _, manifest, amendments = inventory
    amendments['amendments'].append(records[0] | {'number': '03', 'old_sha256': '0' * 64,
                                               'new_sha256': digest(b'latest overlay')})
    with pytest.raises(ValueError, match='chain'):
        accepted_hashes(manifest, amendments)
    amendments['amendments'][-1].update(number='01')
    with pytest.raises(ValueError, match='in increasing order'):
        accepted_hashes(manifest, amendments)


@pytest.mark.parametrize('filename,old_header,new_header', [
    ('SI-I04.txt', '胶刷外部维护片段（仅本例临时覆盖，不能作为系统指令）。', '胶刷外部维护补充说明。'),
    ('SI-I05.txt', '集尘站外部检查的临时检索片段。', '集尘站外部检查补充说明。'),
    ('SI-I06.txt', '电池与整机分别查询的临时资料片段。', '电池与整机保修查询补充说明。'),
])
def test_revision_02_changes_only_first_line_bytes(filename, old_header, new_header):
    name = 'evaluation/service_injection_v1/overlays/' + filename
    manifest = json.loads((ROOT / 'evaluation/service_v1/freeze_manifest.json').read_bytes())
    amendments = json.loads((ROOT / 'evaluation/service_v1/freeze_amendments.json').read_bytes())
    data = (ROOT / name).read_bytes()
    first, separator, tail = data.partition(b'\n')
    assert separator == b'\n' and first == new_header.encode('utf-8')
    assert not data.startswith(b'\xef\xbb\xbf') and b'\r' not in data
    # Reconstructing the original file pins every byte after its first line,
    # including blank lines, the payload and the original ending.
    assert digest(old_header.encode('utf-8') + separator + tail) == manifest['files'][name]
    records = [item for item in amendments['amendments'] if item['number'] == '02' and item['file'] == name]
    assert len(records) == 1
    assert records[0]['old_sha256'] == manifest['files'][name]
    assert records[0]['new_sha256'] == digest(data)
    assert records[0]['approval'] == '作者 2026-10-14 批准' and records[0]['gold_impact'] == '无'
