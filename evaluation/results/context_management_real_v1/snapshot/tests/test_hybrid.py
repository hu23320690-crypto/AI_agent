import unittest
from langchain_core.documents import Document
from rag.hybrid import BM25Index, fuse, tokenize


def doc(text):
    return Document(page_content=text, metadata={'source':'test.txt'})


class HybridTests(unittest.TestCase):
    def test_chinese_parts_and_model_identifiers_are_retained(self):
        terms=tokenize('集尘袋容量 XQ-999')
        self.assertIn('尘袋', terms)
        self.assertIn('xq-999', terms)

    def test_no_keyword_match_returns_no_arbitrary_candidates(self):
        index=BM25Index([doc('集尘袋容量至少2.5L'),doc('主刷清理')])
        self.assertEqual(index.search('陌生型号 ZZX-888',5),[])
        self.assertEqual(index.search('集尘袋',1)[0].page_content,'集尘袋容量至少2.5L')
        self.assertEqual(BM25Index([]).search('机器人',5),[])

    def test_fusion_rewards_agreement_without_duplicate_votes(self):
        a,b,c=doc('A'),doc('B'),doc('C')
        self.assertEqual(fuse([[a,b],[c,b]],1)[0].page_content,'B')
        self.assertEqual([d.page_content for d in fuse([[a,a,b],[b]],2)],['B','A'])

    def test_same_text_from_different_sources_keeps_provenance(self):
        a=Document(page_content='同文',metadata={'source':'a.txt'})
        b=Document(page_content='同文',metadata={'source':'b.txt'})
        self.assertEqual(len(fuse([[a],[b]],5)),2)

    def test_vector_and_hybrid_routes_always_apply_approved_chunk_filter(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        from rag.vector_store import VectorStoreService
        from rag.security import SourceCatalog, chunk_sha256
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            data.mkdir()
            (data/'test.txt').write_text('机器人清理', encoding='utf-8')
            ledger = root/'sources.json'
            ledger.write_text(json.dumps({'schema_version': 1, 'sources': []}), encoding='utf-8')
            catalog = SourceCatalog(data, ledger)
            entry = catalog.approve('test.txt', reason='offline fixture')
            config = {'collection_name':'test', 'persist_directory':'unused', 'chunk_size':200,
                      'chunk_overlap':20, 'separators':[''], 'k':5,
                      'data_path':str(data), 'source_catalog':str(ledger)}
            store = MagicMock()
            service = VectorStoreService(config=config, vector_store=store)
            document = catalog.load_source(entry)[0]
            document.metadata.update(chunk_id='testchunk', pipeline=service.pipeline,
                                     chunk_sha256=chunk_sha256(document.page_content))
            store.similarity_search.return_value = [document]
            store.get.return_value = {'ids':['testchunk'], 'documents':[document.page_content],
                                      'metadatas':[document.metadata]}
            self.assertEqual(len(service.search('机器人', k=3)), 1)
            store.similarity_search.assert_called_with('机器人', k=20,
                                                       filter={'chunk_id':{'$in':['testchunk']}})
            service.config.update(retrieval_mode='hybrid', candidate_k=20)
            self.assertEqual(len(service.search('机器人', k=5)), 1)
            store.similarity_search.assert_called_with('机器人', k=20,
                                                       filter={'chunk_id':{'$in':['testchunk']}})
