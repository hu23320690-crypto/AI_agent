"""Optional retrieval references cannot block an admissible current question."""
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from agent.context_budget import ContextBudgetExceeded, ContextPolicy, estimate_request
from rag.query_context import build_query_context, contextualize_query
from rag.rag_service import RagSummarizeService
from test_core_flows import ScriptedModel, answer


def service_with_short_reference():
    with patch('rag.rag_service.VectorStoreService'):
        service = RagSummarizeService()
    document = Document(page_content='这份资料介绍设备的结构，没有提供其他结论。',
                        metadata={'source_id': 'fixture', 'source': 'guide.txt',
                                  'source_version': 1, 'chunk_id': 'fixture-chunk'})
    return service, [document]


def prompt_size(service, docs, task, model):
    messages = service.prompt_template.invoke(
        {'input': task, 'context': service.format_context(docs)}).to_messages()
    return estimate_request(messages, model=model)


def policy_with_input_limit(limit):
    return ContextPolicy(window_tokens=limit + 1024 + 64,
                         reserve_output_tokens=1024, safety_margin_tokens=64,
                         reasoning_enabled=False)


def test_optional_subject_quote_is_dropped_when_current_question_alone_fits():
    service, docs = service_with_short_reference()
    question = '请介绍上述对象的结构，并说明资料不足的部分。'
    context = build_query_context(question, task_references=['对象是新的测试设备，说明结构。'])
    retrieval = contextualize_query('它是什么结构？', question=question, query_context=context)
    assert retrieval.startswith(question)
    model = ScriptedModel(responses=[answer('完整答复。')])
    current_size = prompt_size(service, docs, question, model)
    augmented_size = prompt_size(service, docs, retrieval, model)
    assert augmented_size > current_size
    input_limit = (current_size + augmented_size) // 2
    policy = policy_with_input_limit(input_limit)
    with patch('rag.rag_service.chat_model', model), patch('rag.rag_service.load_context_policy', return_value=policy):
        result = service.answer_documents(retrieval, docs, question=question)
    assert result == '完整答复。'
    assert len(model.seen) == 1
    user_text = '\n'.join(str(message.content) for message in model.seen[0] if message.type == 'human')
    assert question in user_text
    assert '对象是新的测试设备' not in user_text
    assert '设备的结构' in user_text, 'The real document remains; only the optional quote is dropped'


def test_current_question_occurs_once_when_optional_reference_is_admitted():
    service, docs = service_with_short_reference()
    question = '请介绍上述对象的结构，并说明资料不足的部分。'
    context = build_query_context(question, task_references=['对象是新的测试设备，说明结构。'])
    retrieval = contextualize_query('它是什么结构？', question=question, query_context=context)
    model = ScriptedModel(responses=[answer('完整答复。')])
    policy = policy_with_input_limit(prompt_size(service, docs, retrieval, model) + 2048)
    with patch('rag.rag_service.chat_model', model), patch('rag.rag_service.load_context_policy', return_value=policy):
        assert service.answer_documents(retrieval, docs, question=question) == '完整答复。'
    user_text = '\n'.join(str(message.content) for message in model.seen[0] if message.type == 'human')
    assert user_text.count(question) == 1
    assert '新的测试设备' in user_text
    assert '低信任' in user_text


def test_current_question_itself_over_budget_is_rejected_before_dispatch():
    service, docs = service_with_short_reference()
    question = '请完整说明这个独立对象的结构以及证据限制。' * 50
    model = ScriptedModel(responses=[answer('不得派发。')])
    required = prompt_size(service, docs, question, model)
    policy = policy_with_input_limit(required - 1)
    with patch('rag.rag_service.chat_model', model), patch('rag.rag_service.load_context_policy', return_value=policy):
        with pytest.raises(ContextBudgetExceeded):
            service.answer_documents(question, docs, question=question)
    assert model.seen == []
