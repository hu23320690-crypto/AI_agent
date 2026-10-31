"""Service-only two-collection RRF, quotas, provenance and bound model scope."""
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from functools import lru_cache
import json
import re
import hashlib
from pathlib import Path

from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from rag.hybrid import fuse
from rag.security import KnowledgeAccessError, stable_source_id
from rag.service_store import ServiceVectorStoreService
from rag.vector_store import VectorStoreService
from service_desk.evaluation_context import kb_overlay

ROOT = Path(__file__).resolve().parents[1]
KB_DISPLAY_FILE = 'service_notes.txt'


class EmptyLegacyCollection:
    """An absent legacy index stays absent; service requests never create it."""
    def get(self, **kwargs):
        return {'ids': [], 'documents': [], 'metadatas': []}

    def similarity_search(self, *args, **kwargs):
        return []


@lru_cache(maxsize=1)
def service_components():
    from model.factory import embedding_model
    from utils.config_hander import chroma_conf
    from utils.path_tool import get_abs_path
    try:
        collection = Chroma(collection_name=chroma_conf['collection_name'],
            embedding_function=embedding_model, persist_directory=get_abs_path(chroma_conf['persist_directory']),
            create_collection_if_not_exists=False)
    except NotFoundError:
        collection = EmptyLegacyCollection()
    return VectorStoreService(vector_store=collection), ServiceVectorStoreService()


class ServiceRetrieval:
    def __init__(self, legacy, service, model_code, *, evidence_sink=None, evaluation_context=None):
        self.legacy, self.service, self.model_code = legacy, service, model_code
        self.evidence_sink = evidence_sink
        self.config = service.config
        self.evaluation_context = evaluation_context

    def _overlay_document(self):
        overlay = kb_overlay(self.evaluation_context)
        if overlay is None:
            return None
        # Ordinary service metadata; the evaluation authority stays out of band.
        try:
            raw = overlay.path.read_bytes()
            # Match install_overlay's text-mode newline normalization, while
            # retaining the raw file digest for later identity revalidation.
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            if text != overlay.text or hashlib.sha256(raw).hexdigest() != overlay.file_sha256:
                raise KnowledgeAccessError('source_content_changed')
        except (OSError, UnicodeError) as exc:
            raise KnowledgeAccessError('source_unavailable') from exc
        # The real carrier identity is private to the capability and runner
        # audit. All tasks display the same ordinary service source name.
        path, name = (ROOT / 'service_kb' / KB_DISPLAY_FILE).resolve(), KB_DISPLAY_FILE
        sha = hashlib.sha256(overlay.text.encode()).hexdigest()
        source_id, pipeline = stable_source_id(name), self.service.pipeline
        chunk_id = hashlib.sha256(f'{source_id}:1:{sha}:{pipeline}:0'.encode()).hexdigest()
        manifest = json.dumps({'version': 1, 'files': [{'file': name, 'sha256': sha,
                              'models': ['all']}]}, sort_keys=True).encode()
        return Document(page_content=overlay.text, metadata={
            'source': str(path), 'source_id': source_id, 'source_version': 1,
            'source_sha256': sha, 'knowledge_catalog': 'service', 'source_file': name,
            'models': '["all"]', 'manifest_sha256': hashlib.sha256(manifest).hexdigest(),
            'start_index': 0, 'source_key': hashlib.sha256(str(path).casefold().encode()).hexdigest(),
            'file_hash': sha, 'pipeline': pipeline, 'chunk_id': chunk_id,
            'chunk_index': 0, 'chunk_count': 1,
            'chunk_sha256': hashlib.sha256(overlay.text.encode()).hexdigest()})

    def _is_overlay(self, doc):
        expected = self._overlay_document()
        return (expected is not None and doc.page_content == expected.page_content
                and doc.metadata == expected.metadata)

    def get_retriever(self):
        return RunnableLambda(self.search)

    @staticmethod
    def _kind(doc):
        return doc.metadata.get('knowledge_catalog', 'legacy')

    def _store(self, doc):
        kind = self._kind(doc)
        if kind not in ('legacy', 'service'):
            raise KnowledgeAccessError('unknown_knowledge_catalog')
        return self.service if kind == 'service' else self.legacy

    def validate_documents(self, docs):
        groups = {'legacy': [], 'service': []}
        for doc in docs:
            if self._is_overlay(doc):
                continue
            kind = self._kind(doc)
            self._store(doc)
            if kind == 'service':
                models = json.loads(doc.metadata.get('models', '[]'))
                if 'all' not in models and self.model_code not in models:
                    raise KnowledgeAccessError('service_model_scope_mismatch')
            groups[kind].append(doc)
        for kind, documents in groups.items():
            if documents:
                (self.legacy if kind == 'legacy' else self.service).validate_documents(documents)
        if self.evidence_sink is not None:
            self.evidence_sink([Document(page_content=d.page_content, metadata=deepcopy(d.metadata)) for d in docs])

    def maintenance_entry_complete(self, doc, line):
        self.validate_documents([doc])
        if self._is_overlay(doc):
            return line in doc.page_content.splitlines()
        return self._store(doc).maintenance_entry_complete(doc, line)

    def _select(self, candidates, k):
        selected, texts, counts = [], [], Counter()
        policy = self.service.catalog.policy
        for doc in candidates:
            source = (self._kind(doc), doc.metadata['source_id'])
            text = re.sub(r'\s+', '', doc.page_content).casefold()
            if counts[source] >= policy.max_chunks_per_source:
                continue
            if policy.deduplicate_chunks and any(text == prior or SequenceMatcher(
                    None, text, prior, autojunk=False).ratio() >= .96 for prior in texts):
                continue
            selected.append(doc)
            texts.append(text)
            counts[source] += 1
            if len(selected) == k:
                break
        return selected

    def search(self, query, k=None):
        k = self.config['k'] if k is None else k
        if k <= 0:
            return []
        window = max(k, self.config['candidate_k'])
        legacy = [Document(page_content=d.page_content,
                           metadata=dict(d.metadata, knowledge_catalog='legacy', models='["all"]'))
                  for d in self.legacy.search(query, k=window)]
        service = self.service.search(query, k=window, model_code=self.model_code)
        candidates = fuse([legacy, service], len(legacy) + len(service), self.config['rrf_constant'])
        selected = self._select(candidates, k)
        overlay = self._overlay_document()
        if overlay is not None:
            selected.append(overlay)
        self.validate_documents(selected)
        return selected

    def references(self, docs):
        self.validate_documents(docs)
        references = []
        for doc in docs:
            if self._is_overlay(doc):
                references.append({'doc_ref': f"service_kb/{doc.metadata['source_file']}#{doc.metadata['chunk_id']}",
                                   'models': ['all']})
                continue
            store = self._store(doc)
            entry = store.catalog.snapshot().authorized.get(doc.metadata['source_id'])
            if entry is None:
                raise KnowledgeAccessError('reference_source_not_authorized')
            prefix = 'service_kb' if self._kind(doc) == 'service' else 'data'
            models = json.loads(doc.metadata['models']) if self._kind(doc) == 'service' else ['all']
            references.append({'doc_ref': f"{prefix}/{entry['path']}#{doc.metadata['chunk_id']}", 'models': models})
        return references
