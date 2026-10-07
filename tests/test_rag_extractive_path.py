from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from agent.runtime import RunContext, runtime_call
from evaluation.observe import ModelObserver
from rag.rag_service import RagSummarizeService
from rag.security import KnowledgeAccessError


def test_extractive_answer_preserves_steps_and_commit_authorization():
    store = MagicMock()
    store.maintenance_entry_complete.return_value = True
    evidence = Document(page_content='3. 部件甲：每9天清理，晾干后安装，8个月更换，破损立即更换。',
                        metadata={'source_id': 'approved', 'source_version': 'v1',
                                  'chunk_index': 0, 'chunk_count': 1})
    run = RunContext()
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with patch.object(service, 'chain') as chain:
            answer = runtime_call('run', 'test.extractive', lambda: service.answer_documents(
                '部件甲多久清理和更换？', [evidence]), run=run)
            chain.invoke.assert_not_called()
    assert evidence.page_content.removeprefix('3. ') in answer
    assert len(run.get_commit_checks()) == 1
    assert store.validate_documents.call_count >= 2
    store.validate_documents.side_effect = KnowledgeAccessError('revoked after answer')
    with pytest.raises(KnowledgeAccessError):
        run.complete()


def test_observer_installed_records_program_response_separately_from_model_input():
    store = MagicMock()
    store.maintenance_entry_complete.return_value = True
    evidence = Document(page_content='部件乙：每周冲洗，晾干后使用。',
                        metadata={'source_id': 'approved', 'source_version': 'v1',
                                  'chunk_index': 0, 'chunk_count': 1})
    observer = ModelObserver()
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with observer.installed(), patch.object(service, 'chain') as chain:
            answer = service.answer_documents('部件乙多久冲洗？', [evidence])
            chain.invoke.assert_not_called()
    assert observer.calls == []
    assert observer.rag_answers[0]['answer'] == answer
    assert observer.rag_answers[0]['docs'][0]['text'] == evidence.page_content
    assert observer.rag_answers[0]['model_request_indices'] == []
