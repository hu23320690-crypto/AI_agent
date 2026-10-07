"""Entry boundaries use current ledger bytes, not arbitrary metadata paths."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from rag.security import SourceCatalog, KnowledgeAccessError, stable_source_id, chunk_sha256
from rag.vector_store import VectorStoreService
from rag.maintenance_answer import extract_maintenance_answer


@pytest.fixture
def store(tmp_path):
    root = tmp_path.resolve()
    data = root / 'data'
    data.mkdir()
    ledger = root / 'sources.json'
    ledger.write_text('{"schema_version":1,"sources":[]}', encoding='utf-8')
    instance = VectorStoreService.__new__(VectorStoreService)
    instance.catalog = SourceCatalog(data, ledger)
    instance.pipeline = 'test-pipeline'
    return instance


def source_chunk(store, text, *, chunk=None, name='guide.txt'):
    path = store.catalog.data_root / name
    path.write_text(text, encoding='utf-8')
    entry = {'path': name, 'source_id': stable_source_id(name), 'version': 1,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': 'approved',
             'allow_risk': False, 'review_note': 'local offline fixture'}
    raw = json.loads(store.catalog.ledger_path.read_text(encoding='utf-8'))
    raw['sources'] = [value for value in raw['sources'] if value['source_id'] != entry['source_id']] + [entry]
    store.catalog.ledger_path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    content = text if chunk is None else chunk
    return Document(page_content=content, metadata={
        'source': str(path), 'source_id': entry['source_id'], 'source_version': 1,
        'source_sha256': entry['sha256'], 'pipeline': store.pipeline,
        'chunk_id': 'fixture-' + name, 'chunk_sha256': chunk_sha256(content),
        'start_index': text.index(content), 'chunk_index': 0, 'chunk_count': 2})


def test_period_at_middle_chunk_end_is_proven_by_next_source_item(store):
    line = '11. 部件甲：每周清理，晾干后安装，破损立即更换。'
    chunk = source_chunk(store, line + '\n12. 部件乙：每月清理。', chunk=line)
    assert store.maintenance_entry_complete(chunk, line)
    answer = extract_maintenance_answer('部件甲多久清理和更换', [chunk],
                                        boundary_check=store.maintenance_entry_complete)
    assert answer.endswith('部件甲：每周清理，晾干后安装，破损立即更换。')


@pytest.mark.parametrize('continuation', ['清理后晾干，破损立即更换。', '破损立即更换。\n12. 部件乙：每月清理。'])
def test_period_followed_by_same_item_continuation_is_not_complete(store, continuation):
    line = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, line + '\n' + continuation, chunk=line)
    assert not store.maintenance_entry_complete(chunk, line)
    assert extract_maintenance_answer('部件甲多久清理', [chunk],
                                     boundary_check=store.maintenance_entry_complete) is None


def test_same_physical_line_has_unseen_second_sentence(store):
    partial = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, partial + '破损立即更换。\n12. 部件乙：每月清理。', chunk=partial)
    assert not store.maintenance_entry_complete(chunk, partial)


def test_real_source_end_is_a_complete_boundary(store):
    line = '11. 部件甲：每周清理，晾干后安装。'
    chunk = source_chunk(store, line, chunk=line)
    assert store.maintenance_entry_complete(chunk, line)


def test_revoked_source_raises_before_boundary_load(store):
    line = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, line)
    raw = json.loads(store.catalog.ledger_path.read_text(encoding='utf-8'))
    raw['sources'][0]['status'] = 'revoked'
    store.catalog.ledger_path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(KnowledgeAccessError):
        store.maintenance_entry_complete(chunk, line)


def test_revocation_while_loading_is_rechecked(store):
    line = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, line)
    original = store.catalog.load_source
    def load(entry):
        result = original(entry)
        raw = json.loads(store.catalog.ledger_path.read_text(encoding='utf-8'))
        raw['sources'][0]['status'] = 'revoked'
        store.catalog.ledger_path.write_text(json.dumps(raw), encoding='utf-8')
        return result
    with patch.object(store.catalog, 'load_source', side_effect=load), pytest.raises(KnowledgeAccessError):
        store.maintenance_entry_complete(chunk, line)


def test_source_version_and_path_substitution_are_rejected(store):
    line = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, line)
    for changed in ({'source_version': 2}, {'source': str(store.catalog.data_root / 'other.txt')}):
        candidate = chunk.model_copy(deep=True)
        candidate.metadata.update(changed)
        with pytest.raises(KnowledgeAccessError):
            store.maintenance_entry_complete(candidate, line)


def test_ledger_identity_selects_source_and_forged_offset_cannot_prove_boundary(store):
    line = '11. 部件甲：每周清理。'
    first = source_chunk(store, line + '\n12. 部件乙：每月清理。', chunk=line)
    source_chunk(store, line + '\n还有另一条件。', chunk=line, name='another.txt')
    assert store.maintenance_entry_complete(first, line)
    first.metadata['start_index'] = 1
    assert not store.maintenance_entry_complete(first, line)


def test_run_cancel_is_checked_before_catalog_work(store):
    from agent.runtime import RunContext, RunCancelled
    line = '11. 部件甲：每周清理。'
    chunk = source_chunk(store, line)
    run = RunContext()
    run.cancel()
    with patch('rag.vector_store.current_run', return_value=run), patch.object(store.catalog, 'snapshot') as snapshot:
        with pytest.raises(RunCancelled):
            store.maintenance_entry_complete(chunk, line)
    snapshot.assert_not_called()
