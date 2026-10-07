from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from agent.runtime import RunContext, runtime_call
from rag.qa_answer import extract_boolean_answer
from rag.rag_service import RagSummarizeService
from rag.security import KnowledgeAccessError


def doc(answer='不可，两者规格不同，需使用专用部件。'):
    return Document(page_content='12. **部件甲可以用在系统乙中吗？**\n- ' + answer + '\n13. **下一问题？**',
                    metadata={'source_id': 'source', 'source_version': 1})


def test_source_answer_is_preserved_without_money_or_operating_claims():
    evidence = doc()
    result = extract_boolean_answer('我想把部件甲装到系统乙中省钱，可以吗？', [evidence],
                                    boundary_check=lambda *args: True)
    assert result.endswith('不可，两者规格不同，需使用专用部件。')
    assert '省钱' not in result


@pytest.mark.parametrize('question', ['这个可以吗？', '部件甲可以用在系统乙中吗？另外电池寿命多久？',
                                     '部件甲可以用在系统乙中吗？价格多少？'])
def test_weak_or_multi_part_questions_do_not_lose_the_unanswered_parts(question):
    assert extract_boolean_answer(question, [doc()], boundary_check=lambda *args: True) is None


def test_conflicting_answers_and_unproven_boundaries_fall_back():
    question = '部件甲可以用在系统乙中吗？'
    assert extract_boolean_answer(question, [doc(), doc('可以，无其他限制。')],
                                  boundary_check=lambda *args: True) is None
    assert extract_boolean_answer(question, [doc()], boundary_check=lambda *args: False) is None
    assert extract_boolean_answer(question, [doc()]) is None


def test_partial_or_multi_line_answer_is_not_truncated_into_a_complete_answer():
    evidence = doc('不可，两者规格不同')
    assert extract_boolean_answer('部件甲可以用在系统乙中吗？', [evidence],
                                  boundary_check=lambda *args: True) is None


def test_public_service_keeps_commit_authorization_for_quoted_qa():
    store = MagicMock()
    store.maintenance_entry_complete.return_value = True
    run = RunContext()
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with patch.object(service, 'chain') as chain:
            result = runtime_call('run', 'test.qa', lambda: service.answer_documents(
                '部件甲可以用在系统乙中吗？', [doc()]), run=run)
            chain.invoke.assert_not_called()
    assert '规格不同' in result
    assert len(run.get_commit_checks()) == 1
    store.validate_documents.side_effect = KnowledgeAccessError('revoked')
    with pytest.raises(KnowledgeAccessError):
        run.complete()
