"""Offline vector fixtures; all texts are invented here, never from task sets."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from langchain_core.embeddings import Embeddings
import pytest

from rag.service_store import ServiceVectorStoreService
from rag.vector_store import VectorStoreService


class FakeEmbedding(Embeddings):
    model = 'service-regression-embedding'

    def __init__(self):
        self.on_query = None
        self.calls = []

    def embed_documents(self, texts):
        self.calls.append(('documents', tuple(texts)))
        return [[1., .25, 0.] for _ in texts]

    def embed_query(self, text):
        self.calls.append(('query', text))
        if self.on_query is not None:
            action, self.on_query = self.on_query, None
            action()
        return [1., .25, 0.]


class FakeVectorStore:
    """Exact flat search with the same chunk-id filter boundary as Chroma.

    Tiny, repeatedly deleted native HNSW collections can lose their unsynced
    readers on Windows. Governance tests exercise application logic here;
    the real persistent collection is verified separately by index/smoke runs.
    """
    def __init__(self, embedding):
        self.embedding, self.rows = embedding, {}
        self._collection = self

    def get(self, *, where=None, include=None):
        rows = [(key, doc) for key, (doc, _) in sorted(self.rows.items())
                if not where or all(doc.metadata.get(k) == v for k, v in where.items())]
        return {'ids': [key for key, _ in rows],
                'documents': [doc.page_content for _, doc in rows],
                'metadatas': [deepcopy(doc.metadata) for _, doc in rows]}

    def add_documents(self, docs, *, ids):
        vectors = self.embedding.embed_documents([doc.page_content for doc in docs])
        for key, doc, vector in zip(ids, docs, vectors):
            self.rows[key] = (deepcopy(doc), vector)

    def similarity_search(self, query, *, k, filter):
        vector = self.embedding.embed_query(query)
        permitted = set(filter['chunk_id']['$in'])
        rows = [(key, doc, sum(a*b for a,b in zip(vector, stored)))
                for key, (doc, stored) in self.rows.items() if key in permitted]
        rows.sort(key=lambda row: (-row[2], row[0]))
        return [deepcopy(doc) for _, doc, _ in rows[:k]]

    def update(self, *, ids, metadatas):
        for key, metadata in zip(ids, metadatas):
            doc, vector = self.rows[key]
            doc.metadata = deepcopy(metadata)

    def delete(self, *, ids):
        for key in ids:
            self.rows.pop(key, None)

    def delete_collection(self):
        self.rows.clear()


@pytest.fixture
def corpus(tmp_path):
    policy = tmp_path / 'security.yml'
    policy.write_text('max_chunks_per_source: 3\nrisk_rules:\n  - id: injection\n    pattern: "ignore all rules"\n', encoding='utf-8')
    stores = []

    def make(kind, sources):
        directory = tmp_path / kind
        directory.mkdir()
        ledger = tmp_path / (kind + '-sources.json')
        ledger.write_text('{"schema_version":1,"sources":[]}', encoding='utf-8')
        manifest = []
        for name, (text, models) in sources.items():
            path = directory / name
            path.write_text(text, encoding='utf-8')
            manifest.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'models':models,'description':'synthetic regression source'})
        manifest_path = directory / 'manifest.json'
        manifest_path.write_text(json.dumps({'version':1,'files':manifest}), encoding='utf-8')
        config = {'collection_name':kind+'_'+uuid4().hex,'persist_directory':str(tmp_path/'db'),
            'data_path':str(directory),'source_catalog':str(ledger),'manifest_path':str(manifest_path),
            'security_policy':str(policy),'chunk_size':200,'chunk_overlap':20,
            'separators':['\n\n','\n','。',''],'allow_knowledge_file_type':['txt'],
            'retrieval_mode':'hybrid','candidate_k':20,'rrf_constant':60,'k':5}
        embedding = FakeEmbedding()
        store = (ServiceVectorStoreService if kind=='service' else VectorStoreService)(
            config=config,embedding=embedding,vector_store=FakeVectorStore(embedding))
        stores.append(store)
        for entry in manifest:
            kwargs={'expected_sha256':entry['sha256']} if kind=='service' else {}
            store.catalog.approve(entry['file'],reason='synthetic regression approval',**kwargs)
        assert not store.load_document()['failed']
        return store, directory, embedding

    legacy, legacy_dir, legacy_embedding = make('legacy', {
        'general.txt':('通用资料：清理前关闭电源，使用柔软的布擦拭外部。',['all'])})
    service, service_dir, embedding = make('service', {
        'pet.txt':('宠物型胶刷维护：清除外部毛发，检查刷盖是否就位。',['SV-300']),
        'tank.txt':('扫拖型水箱维护：检查接口湿迹，不拆内部供水部件。',['SV-200']),
        'general.txt':('通用服务申请：准备完整现象记录，等待人员检查。',['all'])})
    yield {'legacy':legacy,'service':service,'legacy_dir':legacy_dir,'service_dir':service_dir,
           'embedding':embedding,'legacy_embedding':legacy_embedding,'root':tmp_path}
    for store in stores:
        store.vector_store.delete_collection()
