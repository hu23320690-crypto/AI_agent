"""Separate catalog/index, model metadata and administrator command checks."""
import json
from unittest.mock import patch

import pytest

from rag.security import KnowledgeAccessError
from rag.service_catalog import load_service_rag_config, service_catalog
from scripts import knowledge, manage
from service_rag_fixtures import corpus


def test_model_metadata_is_manifest_bound_and_json_scalar(corpus):
    store = corpus['service']
    stored = store.vector_store.get(include=['documents','metadatas'])
    assert len(stored['ids']) == 3
    for key, meta in zip(stored['ids'],stored['metadatas']):
        assert key == meta['chunk_id'] and meta['knowledge_catalog'] == 'service'
        assert isinstance(meta['models'],str)
        expected = store.catalog.manifest()[meta['source_file']]
        assert json.loads(meta['models']) == expected['models']
        assert meta['source_sha256'] == expected['sha256']
    assert corpus['legacy'].config['collection_name'] != store.config['collection_name']


def test_filter_applies_before_dense_and_lexical_ranking(corpus):
    store = corpus['service']
    with patch.object(store.vector_store,'similarity_search',wraps=store.vector_store.similarity_search) as dense:
        docs = store.search('宠物型胶刷维护',model_code='SV-300')
    assert {d.metadata['source_file'] for d in docs} == {'pet.txt','general.txt'}
    ids = set(dense.call_args.kwargs['filter']['chunk_id']['$in'])
    assert ids == {d.metadata['chunk_id'] for d in docs}
    assert {d.metadata['source_file'] for d in store._lexical_index.documents} == {'pet.txt','general.txt'}
    assert {d.metadata['source_file'] for d in store.search('维护',model_code=None)} == {'general.txt'}


def test_approval_requires_frozen_manifest_sha(corpus):
    with pytest.raises(KnowledgeAccessError,match='参考资料') as error:
        corpus['service'].catalog.approve('pet.txt',expected_sha256='0'*64,reason='wrong digest')
    assert error.value.code == 'service_approval_manifest_mismatch'


def test_source_model_metadata_tampering_is_not_authorized(corpus):
    store = corpus['service']
    data = store.vector_store.get(include=['metadatas'])
    index = next(i for i,m in enumerate(data['metadatas']) if m['source_file']=='tank.txt')
    altered = dict(data['metadatas'][index],models='["SV-300"]')
    store.vector_store._collection.update(ids=[data['ids'][index]],metadatas=[altered])
    assert 'tank.txt' not in {d.metadata['source_file'] for d in store.search('维护',model_code='SV-300')}


def test_service_cli_scan_status_approve_revoke_sync(corpus,capsys):
    store = corpus['service']
    with patch('scripts.knowledge.catalog',return_value=store.catalog):
        assert knowledge.main(['--catalog','service','scan']) == 0
        capsys.readouterr()
        assert knowledge.main(['status','--catalog','service']) == 0
        assert len(json.loads(capsys.readouterr().out)['allowed']) == 3
        expected = store.catalog.manifest()['pet.txt']
        assert knowledge.main(['--catalog','service','approve','pet.txt','--sha256',expected['sha256'],
                               '--reason','synthetic regression approval']) == 0
        entry = json.loads(capsys.readouterr().out)
        assert knowledge.main(['--catalog','service','revoke',entry['source_id'],'--reason','withdraw']) == 0
        capsys.readouterr()
    with patch('rag.service_store.ServiceVectorStoreService',return_value=store):
        assert knowledge.main(['--catalog','service','sync']) == 0
        assert len(json.loads(capsys.readouterr().out)['quarantined']) == 1


def test_doctor_service_catalog_and_hash_checks_with_counterexamples(corpus):
    store = corpus['service']
    with patch('rag.service_catalog.service_catalog',return_value=store.catalog):
        manage._check_service_source_catalog()
        manage._check_service_approved_sources()
        original = store.catalog.ledger_path.read_bytes()
        entries = json.loads(original)
        entries['sources'][0]['sha256'] = '0'*64
        store.catalog.ledger_path.write_text(json.dumps(entries),encoding='utf-8')
        with pytest.raises(KnowledgeAccessError) as error:
            manage._check_service_approved_sources()
        assert error.value.code == 'service_approval_manifest_mismatch'
        store.catalog.ledger_path.write_text('{invalid json',encoding='utf-8')
        with pytest.raises(KnowledgeAccessError):
            manage._check_service_source_catalog()
        store.catalog.ledger_path.write_bytes(original)


def test_published_seven_approvals_match_manifest():
    catalog = service_catalog()
    assert catalog.validate_approved_hashes() == 7
    assert len(catalog.snapshot().authorized) == 7
    assert all(e['review_note']=='S0 作者审核通过的合成资料（PR #5）'
               for e in catalog._read_ledger()['sources'])


@pytest.mark.parametrize('key,value', [
    ('collection_name','agent_chunks_qwen3_governed_v1'),('data_path','data'),
    ('source_catalog','config/knowledge_sources.json'),('chunk_size',201),('rrf_constant',61),
])
def test_service_config_rejects_legacy_namespace_and_parameter_drift(tmp_path,key,value):
    import yaml
    config=load_service_rag_config()
    config[key]=value
    path=tmp_path/'service.yml'
    path.write_text(yaml.safe_dump(config),encoding='utf-8')
    with pytest.raises(ValueError):
        load_service_rag_config(path)
