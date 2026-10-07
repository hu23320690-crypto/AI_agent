from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from agent.runtime import RunContext, runtime_call
from rag.answer_policy import missing_named_manufacturer_reply
from rag.rag_service import RagSummarizeService
from rag.security import KnowledgeAccessError


@pytest.mark.parametrize('name', ['晨星Z9', 'Other Vendor B2'])
def test_general_values_cannot_be_attributed_to_an_absent_quoted_product(name):
    docs = [Document(page_content='机型专用液体可按1:80稀释。')]
    reply = missing_named_manufacturer_reply(f'请确认“{name}”的厂家规定兑水比例。', docs)
    assert name in reply and '无法确认' in reply
    assert '1:80' not in reply


@pytest.mark.parametrize('question', [
    '按资料，通用清洁液比例是多少？',
    '怎样安装“部件甲”？',
    '“部件甲”的厂家规定电压是多少？',
])
def test_general_questions_and_evidenced_entities_continue_to_normal_answering(question):
    assert missing_named_manufacturer_reply(question, [Document(page_content='部件甲厂家电压为12V。')]) is None


def test_original_question_controls_entity_check_instead_of_retrieval_rewrite():
    store = MagicMock()
    run = RunContext()
    docs = [Document(page_content='普通液体稀释比例1:80。')]
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with patch.object(service, 'chain') as chain:
            reply = runtime_call('run', 'test.factory', lambda: service.answer_documents(
                '普通液体比例', docs, question='“陌生Z3”的厂家规定比例是多少？'), run=run)
            chain.invoke.assert_not_called()
    assert '陌生Z3' in reply and '无法确认' in reply
    assert len(run.get_commit_checks()) == 1
    store.validate_documents.side_effect = KnowledgeAccessError('revoked')
    with pytest.raises(KnowledgeAccessError):
        run.complete()


def test_missing_entity_response_does_not_bypass_initial_authorization():
    store = MagicMock()
    store.validate_documents.side_effect = KnowledgeAccessError('revoked')
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with pytest.raises(KnowledgeAccessError):
            service.answer_documents('“未批准Z3”的厂家比例是多少？', [Document(page_content='普通液体1:80。')])
