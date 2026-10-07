from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from rag.answer_policy import (requires_conditional_guarantee, CONDITIONAL_GUARANTEE_REPLY,
                               conditional_guarantee_reply)
from rag.rag_service import RagSummarizeService
from rag.security import KnowledgeAccessError
from agent.runtime import RunContext, runtime_call


@pytest.mark.parametrize('question', [
    '能够保证未连接电源后仍正常工作吗？',
    '前提改变后可以确保成功吗？',
    '能保证没有设置任务也照常执行吗？',
])
def test_removed_condition_cannot_receive_an_operational_guarantee(question):
    assert requires_conditional_guarantee(question)


@pytest.mark.parametrize('question', [
    '手机离线后是否还能执行？请说明条件。',
    '这个部件一定要晾干后再用吗？',
    '怎样保证清洗后的部件晾干？',
    '已连接设备并完成设置时可以执行吗？',
])
def test_ordinary_facts_and_maintenance_are_not_routed_as_guarantees(question):
    assert not requires_conditional_guarantee(question)


def test_guarantee_boundary_checks_sources_and_registers_commit_checks():
    store = MagicMock()
    run = RunContext()
    with patch('rag.rag_service.VectorStoreService', return_value=store):
        service = RagSummarizeService()
        with patch.object(service, 'chain') as chain:
            text = runtime_call('run', 'test.guarantee', lambda: service.answer_documents(
                '使用条件是什么', [Document(page_content='条件甲成立时可以执行。')],
                question='能保证没有条件甲也执行吗？'), run=run)
            chain.invoke.assert_not_called()
    assert text.startswith(CONDITIONAL_GUARANTEE_REPLY)
    assert len(run.get_commit_checks()) == 1
    store.validate_documents.assert_called()
    store.validate_documents.side_effect = KnowledgeAccessError('source revoked')
    with pytest.raises(KnowledgeAccessError):
        run.complete()


def test_condition_reply_quotes_prerequisite_without_inventing_changed_outcome():
    question = '能保证控制端关闭时仍会执行吗？'
    docs = [Document(page_content='- 只要设备已联网并完成设置，控制端离线后仍按预设工作。')]
    reply = conditional_guarantee_reply(question, docs)
    assert question in reply
    assert docs[0].page_content.removeprefix('- ') in reply
    assert '无法确认' in reply
    assert '一定不能执行' not in reply


def test_unrelated_or_partial_prerequisite_is_not_completed_by_guessing():
    docs = [Document(page_content='只要条件甲成立，可以\n'),
            Document(page_content='只要灯罩洁净，照明更好。')]
    reply = conditional_guarantee_reply('能保证电机未接电时仍运行吗？', docs)
    assert '灯罩' not in reply
    assert '条件甲' not in reply
