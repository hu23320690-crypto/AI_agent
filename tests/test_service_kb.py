"""Draft manifest, model scope and structured fact agreement with the seed."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3

import pytest

from service_desk.config import ROOT
from service_desk.db import init_db
from service_desk.knowledge import validate_manifest

BRANDS = ('石头', '科沃斯', '追觅', '云鲸', '小米', '米家', '戴森', '美的', '海尔', '松下',
          'iRobot', 'Roomba', 'Roborock', 'Ecovacs', 'Dreame', 'Narwal', 'Dyson')
KB = ROOT / 'service_kb'


@pytest.fixture(scope='module')
def facts(tmp_path_factory):
    database = tmp_path_factory.mktemp('service-kb') / 'seed.db'
    init_db(database)
    with closing(sqlite3.connect(database)) as connection:
        codes = {(model, code): (title, ref) for model, code, title, ref in connection.execute(
            'SELECT model_code,code,title,doc_ref FROM error_codes')}
        consumables = {sku: name for sku, name in connection.execute('SELECT sku,name FROM consumables')}
        compatibility = {}
        for sku, model in connection.execute('SELECT sku,model_code FROM consumable_models'):
            compatibility.setdefault(sku, set()).add(model)
    return codes, consumables, compatibility


def test_manifest_hashes_scope_and_offline_validation():
    manifest = validate_manifest(KB)
    for entry in manifest['files']:
        assert hashlib.sha256((KB / entry['file']).read_bytes()).hexdigest() == entry['sha256']
        if entry['file'].endswith('_manual.txt'):
            assert entry['models'] == [entry['file'][:6].upper()]
        else:
            assert entry['models'] == ['all']


@pytest.mark.parametrize('filename', [
    'sv-100_manual.txt', 'sv-200_manual.txt', 'sv-300_manual.txt', 'sv-400_manual.txt',
    'errors.txt', 'warranty_service.txt', 'consumables.txt',
])
def test_draft_length_brand_free_and_no_dynamic_numeric_facts(filename):
    text = (KB / filename).read_text(encoding='utf-8')
    assert 1500 <= len(re.findall(r'[\u4e00-\u9fff]', text)) <= 3000
    assert all(brand.casefold() not in text.casefold() for brand in BRANDS)
    assert '以系统查询结果为准' in text
    assert not re.search(r'\d+\s*(?:个月|月保修|元|分/件|件库存|个库存|件限购)', text)


def test_all_error_and_sku_mentions_exist_with_matching_model_scope(facts):
    codes, consumables, compatibility = facts
    known_codes = {code for _, code in codes}
    for entry in validate_manifest(KB)['files']:
        text = (KB / entry['file']).read_text(encoding='utf-8')
        mentions = set(re.findall(r'\bE\d+\b', text))
        assert mentions <= known_codes
        skus = set(re.findall(r'\bSKU-[A-Z0-9]+(?:-[A-Z0-9]+)*\b', text))
        assert skus <= consumables.keys()
        if entry['models'] != ['all']:
            for model in entry['models']:
                for code in mentions:
                    assert (model, code) in codes
                for sku in skus:
                    assert model in compatibility[sku]
                title, _ = codes[model, 'E07']
                assert f'本型号 E07 的名称是“{title}”' in text


def test_every_database_error_reference_resolves_to_exact_heading(facts):
    codes, _, _ = facts
    errors = (KB / 'errors.txt').read_text(encoding='utf-8')
    for (model, code), (title, reference) in codes.items():
        filename, anchor = reference.split('#')
        assert filename == 'errors.txt'
        assert f'## {anchor} {title}\n' in errors
        match = re.search(rf'## {re.escape(anchor)} {re.escape(title)}\n(.*?)(?=\n## |\Z)', errors, re.S)
        assert match and model in match[1]
    assert len({title for (model, code), (title, ref) in codes.items() if code == 'E07'}) == 4


def test_guide_sku_names_and_compatibility_are_complete_and_exact(facts):
    _, consumables, compatibility = facts
    guide = (KB / 'consumables.txt').read_text(encoding='utf-8')
    for sku, name in consumables.items():
        match = re.search(rf'{re.escape(sku)} 的名称是“([^”]+)”，适用型号：([^。]+)。', guide)
        assert match and match[1] == name
        assert set(re.findall(r'SV-\d{3}', match[2])) == compatibility[sku]


def test_manifest_detects_modified_missing_and_unlisted_drafts(tmp_path):
    copied = tmp_path / 'kb'
    shutil.copytree(KB, copied)
    path = copied / 'errors.txt'
    original = path.read_bytes()
    path.write_bytes(original + b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        validate_manifest(copied)
    path.write_bytes(original)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        validate_manifest(copied)
    path.write_bytes(original)
    (copied / 'unlisted.txt').write_text('extra', encoding='utf-8')
    with pytest.raises(ValueError, match='match manifest'):
        validate_manifest(copied)


@pytest.mark.parametrize('field,value', [('file', '../outside.txt'), ('models', ['SV-999']), ('models', ['all', 'SV-100'])])
def test_manifest_rejects_path_escape_and_wrong_model_scope(tmp_path, field, value):
    copied = tmp_path / 'kb'
    shutil.copytree(KB, copied)
    path = copied / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['files'][0][field] = value
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        validate_manifest(copied)
