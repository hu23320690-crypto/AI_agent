"""Governed small-corpus retrieval: authorization precedes both ranking routes."""
import hashlib
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from threading import RLock
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from rag.hybrid import BM25Index, fuse
from rag.relevance import QueryCoverageReranker
from rag.security import SourceCatalog, KnowledgeAccessError
from utils.config_hander import chroma_conf
from model.factory import embedding_model
from utils.path_tool import get_abs_path
from utils.logger_hander import logger
from agent.runtime import RuntimeControlError, current_run


class VectorStoreService:
    def __init__(self, *, config=None, embedding=None, vector_store=None):
        self.config = dict(chroma_conf if config is None else config)
        self.catalog = SourceCatalog(
            get_abs_path(self.config['data_path']),
            get_abs_path(self.config.get('source_catalog', 'config/knowledge_sources.json')),
            policy_path=get_abs_path(self.config.get('security_policy', 'config/security.yml')))
        self._lock = RLock()
        self._lexical_index, self._lexical_stamp = None, None
        self._coverage_reranker = None
        self.vector_store = vector_store if vector_store is not None else Chroma(
            collection_name=self.config['collection_name'],
            embedding_function=embedding if embedding is not None else embedding_model,
            persist_directory=get_abs_path(self.config['persist_directory']))
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config['chunk_size'], chunk_overlap=self.config['chunk_overlap'],
            separators=self.config['separators'], length_function=len, add_start_index=True)
        self.pipeline = hashlib.sha256(json.dumps({
            'version': 2, 'size': self.config['chunk_size'],
            'overlap': self.config['chunk_overlap'], 'separators': self.config['separators'],
            'embedding': getattr(embedding if embedding is not None else embedding_model,
                                 'model', type(embedding).__qualname__),
        }, sort_keys=True).encode()).hexdigest()

    def get_retriever(self):
        return RunnableLambda(self.search)

    def _allowed(self, doc, snapshot):
        return (doc.metadata.get('pipeline') == self.pipeline
                and isinstance(doc.metadata.get('chunk_id'), str)
                and self.catalog.document_allowed(doc, snapshot))

    def validate_documents(self, docs):
        self.catalog.validate_documents(docs)
        if any(d.metadata.get('pipeline') != self.pipeline or not d.metadata.get('chunk_id') for d in docs):
            raise KnowledgeAccessError('invalid_index_version')

    def maintenance_entry_complete(self, doc, line):
        """Prove a retrieved item's physical-line boundary in its current source.

        Resolve sources only through the administrator ledger. Caller metadata
        paths cannot select files, and source text is loaded with the catalog's
        existing size/risk/version checks. Never cache an authorization snapshot.
        """
        run = current_run()
        def check():
            if run is not None:
                run.check()
        check()
        self.validate_documents([doc])
        check()
        if not isinstance(line, str) or not any(value.strip() == line.strip()
                                               for value in doc.page_content.splitlines()):
            return False
        snapshot = self.catalog.snapshot()
        check()
        entry = snapshot.authorized.get(doc.metadata.get('source_id'))
        if (entry is None or entry['version'] != doc.metadata.get('source_version')
                or entry['sha256'] != doc.metadata.get('source_sha256')):
            raise KnowledgeAccessError('maintenance_source_not_current')
        documents = self.catalog.load_source(entry)
        check()
        self.validate_documents([doc])
        check()
        start = doc.metadata.get('start_index')
        boundary = re.compile(r'^\s*(?:\d{1,3}[.、)]\s*|#{1,6}\s+)')
        complete = False
        for page_index, source in enumerate(documents):
            check()
            if source.metadata.get('page') != doc.metadata.get('page'):
                continue
            # Even a valid-looking chunk hash must describe this exact source
            # substring, not a truncated sentence substituted at another offset.
            if (type(start) is not int or start < 0 or
                    source.page_content[start:start + len(doc.page_content)] != doc.page_content):
                continue
            offsets = []
            offset = 0
            for value in doc.page_content.splitlines(keepends=True):
                check()
                if value.rstrip('\r\n').strip() == line.strip():
                    offsets.append(start + offset)
                offset += len(value)
            verdicts = []
            for position in offsets:
                check()
                begin = source.page_content.rfind('\n', 0, position) + 1
                end = source.page_content.find('\n', position)
                end = len(source.page_content) if end < 0 else end
                if source.page_content[begin:end].strip() != line.strip():
                    verdicts.append(False)
                    continue
                following = source.page_content[end:].splitlines()
                for later_page in documents[page_index + 1:]:
                    check()
                    following.extend(later_page.page_content.splitlines())
                next_line = next((value for value in following if value.strip()), None)
                verdicts.append(next_line is None or bool(boundary.match(next_line)))
            complete = bool(verdicts) and all(verdicts)
            break
        check()
        self.validate_documents([doc])
        check()
        return complete

    def _eligible(self, snapshot):
        stored = self.vector_store.get(include=['documents', 'metadatas'])
        return [Document(page_content=text, metadata=meta or {})
                for key, text, meta in zip(stored['ids'], stored['documents'], stored['metadatas'])
                if text is not None and meta and key == meta.get('chunk_id')
                and self._allowed(Document(page_content=text, metadata=meta), snapshot)]

    def _select(self, candidates, k):
        selected, normalized, counts = [], [], Counter()
        for doc in candidates:
            source = doc.metadata['source_id']
            text = re.sub(r'\s+', '', doc.page_content).casefold()
            if counts[source] >= self.catalog.policy.max_chunks_per_source:
                continue
            if self.catalog.policy.deduplicate_chunks and any(text == prior or SequenceMatcher(None, text, prior, autojunk=False).ratio() >= .96
                   for prior in normalized):
                continue
            selected.append(doc)
            normalized.append(text)
            counts[source] += 1
            if len(selected) == k:
                break
        return selected

    def search(self, query, k=None):
        k = self.config['k'] if k is None else k
        if k <= 0:
            return []
        with self._lock:
            snapshot = self.catalog.snapshot()
            eligible = self._eligible(snapshot)
            run = current_run()
            if run is not None:
                run.note('knowledge_filter', allowed_chunks=len(eligible), blocked_sources=len(snapshot.blocked))
                for blocked in snapshot.blocked[:16]:
                    run.note('knowledge_source_blocked', source_id=blocked.get('source_id', '<invalid>'),
                             reason_code=blocked['reason'])
            if not eligible:
                return []
            # A denied source cannot crowd legitimate evidence out of vector TopK.
            permitted = {d.metadata['chunk_id'] for d in eligible}
            window = max(k, self.config.get('candidate_k', 20))
            dense = self.vector_store.similarity_search(
                query, k=window, filter={'chunk_id': {'$in': sorted(permitted)}})
            dense = [d for d in dense if d.metadata.get('chunk_id') in permitted and self._allowed(d, snapshot)]
            mode = self.config.get('retrieval_mode', 'vector')
            if mode == 'vector':
                candidates = dense
            elif mode == 'hybrid':
                stamp = (snapshot.stamp, tuple((d.metadata['chunk_id'], d.metadata['chunk_sha256']) for d in eligible))
                if self._lexical_index is None or self._lexical_stamp != stamp:
                    self._lexical_index, self._lexical_stamp = BM25Index(eligible), stamp
                    self._coverage_reranker = QueryCoverageReranker(eligible)
                sparse = self._lexical_index.search(query, window)
                candidates = fuse([dense, sparse], len(dense) + len(sparse), self.config.get('rrf_constant', 60))
                candidates = self._coverage_reranker.rerank(
                    query, candidates, source_cap=self.catalog.policy.max_chunks_per_source)
            else:
                raise ValueError(f'Unknown retrieval mode: {mode}')
            selected = self._select(candidates, k)
            # Re-read policy and bytes after query embedding/ranking may have waited.
            self.validate_documents(selected)
            return selected

    def load_document(self):
        """Synchronize approved byte snapshots; no runtime auto-approval."""
        with self._lock:
            snapshot = self.catalog.snapshot()
            stats = {'indexed': 0, 'skipped': 0, 'chunks': 0, 'failed': [], 'quarantined': snapshot.blocked}
            stored = self.vector_store.get(include=['documents', 'metadatas'])
            stale = []
            for key, text, meta in zip(stored['ids'], stored['documents'], stored['metadatas']):
                if not meta or not text or not self.catalog.document_allowed(
                        Document(page_content=text, metadata=meta or {}), snapshot):
                    stale.append(key)
            if stale:
                if current_run() is not None:
                    current_run().check()
                self.vector_store.delete(ids=stale)
            for entry in snapshot.authorized.values():
                path = self.catalog.data_root / entry['path']
                try:
                    run = current_run()
                    if run is not None:
                        run.check()
                    old = self.vector_store.get(where={'source_id': entry['source_id']}, include=['metadatas'])
                    metadata = old.get('metadatas') or []
                    if metadata and all(
                        m.get('source_sha256') == entry['sha256'] and m.get('source_version') == entry['version']
                        and m.get('pipeline') == self.pipeline and m.get('chunk_count') == len(metadata)
                        for m in metadata):
                        stats['skipped'] += 1
                        continue
                    documents = self.catalog.load_source(entry)
                    chunks = [d for d in self.splitter.split_documents(documents) if d.page_content.strip()]
                    if not chunks:
                        raise ValueError('文档没有可入库的文本')
                    ids = []
                    source_key = hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest()
                    for index, doc in enumerate(chunks):
                        key = hashlib.sha256(
                            f"{entry['source_id']}:{entry['version']}:{entry['sha256']}:{self.pipeline}:{index}".encode()).hexdigest()
                        doc.metadata.update(source_key=source_key, file_hash=entry['sha256'], pipeline=self.pipeline,
                                            chunk_id=key, chunk_index=index, chunk_count=len(chunks),
                                            chunk_sha256=hashlib.sha256(doc.page_content.encode()).hexdigest())
                        ids.append(key)
                    self.validate_documents(chunks)
                    for offset in range(0, len(chunks), 64):
                        if run is not None:
                            run.check()
                        self.vector_store.add_documents(chunks[offset:offset+64], ids=ids[offset:offset+64])
                    self.validate_documents(chunks)
                    if run is not None:
                        run.check()
                    stale = sorted(set(old['ids']) - set(ids))
                    if stale:
                        self.vector_store.delete(ids=stale)
                    stats['indexed'] += 1
                    stats['chunks'] += len(chunks)
                    logger.info('[加载知识库]来源 %s 版本 %s 入库 %d 个分块', entry['source_id'], entry['version'], len(chunks))
                except RuntimeControlError:
                    raise
                except Exception:
                    stats['failed'].append(str(path))
                    logger.exception('[加载知识库]来源 %s 加载失败', entry['source_id'])
            self._lexical_index, self._lexical_stamp = None, None
            self._coverage_reranker = None
            return stats


if __name__ == '__main__':
    stats = VectorStoreService().load_document()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats['failed']:
        raise SystemExit(1)
