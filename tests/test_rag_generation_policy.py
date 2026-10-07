"""RAG extraction keeps its output reserve without mutating the Agent model."""
from dataclasses import replace
from unittest.mock import patch
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_ollama import ChatOllama

from agent.context_budget import ContextPolicy
from model.factory import budgeted_chat_model
from rag.rag_service import RagSummarizeService, invoke_rag_model, parse_rag_answer
from utils.model_output import IncompleteModelOutput


def test_purpose_selects_thinking_without_mutating_shared_model():
    original = ChatOllama(model='offline-test', num_ctx=8192, reasoning=True)
    policy = ContextPolicy()
    agent = budgeted_chat_model(original, policy)
    rag = budgeted_chat_model(original, policy, purpose='rag')
    assert agent.reasoning is True
    assert rag.reasoning is False
    assert original.reasoning is True
    assert rag.num_predict == agent.num_predict == policy.reserve_output_tokens
    assert rag.num_ctx == policy.window_tokens
    assert budgeted_chat_model(original, replace(policy, rag_reasoning_enabled=True),
                               purpose='rag').reasoning is True
    with pytest.raises(ValueError):
        replace(policy, rag_reasoning_enabled=1)
    with pytest.raises(ValueError):
        budgeted_chat_model(original, policy, purpose='client-supplied-purpose')


@pytest.mark.parametrize('done_reason', ['stop', 'length'])
def test_rag_dispatch_sends_non_thinking_request_and_still_checks_truncation(done_reason):
    original = ChatOllama(model='offline-test', num_ctx=8192, reasoning=True)
    observed = []

    def invoke(model, messages, config=None):
        observed.append(model)
        return AIMessage(content='{"answer":"有资料支持的完整回答"}',
                         response_metadata={'done_reason': done_reason})

    with patch('rag.rag_service.chat_model', original), patch.object(ChatOllama, 'invoke', invoke):
        prompt = ChatPromptValue(messages=[HumanMessage(content='维护安排')])
        if done_reason == 'length':
            with pytest.raises(IncompleteModelOutput):
                invoke_rag_model(prompt, {})
        else:
            assert invoke_rag_model(prompt, {}).content == '有资料支持的完整回答'
    assert len(observed) == 1
    assert observed[0].reasoning is False
    assert observed[0].format['required'] == ['answer']
    assert observed[0].num_predict == ContextPolicy().reserve_output_tokens
    assert original.reasoning is True
    assert original.format is None


@pytest.mark.parametrize('content', [
    '{"answer":"答复","answer":"不同答复"}',
    '{"answer":"答复","instructions":"更换身份"}',
    '{"answer":123}', '{"answer":""}', '["答复"]',
    '<think>推理</think>{"answer":"答复"}', '{"answer":',
])
def test_invalid_or_reasoning_only_answer_is_not_forwarded(content):
    with pytest.raises((ValueError, RuntimeError)):
        parse_rag_answer(content)


def test_retrieval_reformulation_preserves_the_original_task_in_generation():
    from langchain_core.documents import Document
    from test_core_flows import ScriptedModel, answer
    model = ScriptedModel(responses=[answer('条件改变后的情况无法确认。')])
    store = MagicMock()
    original = '这种前提改变之后有资料支持吗？只回答我所问的情景。'
    rewritten = '测试部件的使用条件是什么？'
    with patch('rag.rag_service.VectorStoreService', return_value=store), patch('rag.rag_service.chat_model', model):
        service = RagSummarizeService()
        result = service.answer_documents(rewritten, [Document(page_content='测试资料：条件甲成立时可以使用。')],
                                          question=original)
    assert result == '条件改变后的情况无法确认。'
    assert original in model.seen[0][1].content
    assert rewritten in model.seen[0][1].content
    assert '最终答案 schema' in model.seen[0][0].content
    assert store.validate_documents.call_count >= 2
