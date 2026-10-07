"""Conversation quotes enrich retrieval without supplying facts or authority."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from agent.react_agent import ReactAgent
from agent.tools.agent_tools import rag_summerize
from rag.query_context import build_query_context, contextualize_query
from evaluation.observe import seed_messages
from test_core_flows import ScriptedModel, answer, call, scripted_context_policy


def test_omitted_subject_gets_original_user_target_without_answer_facts():
    goal = '我们讨论空气净化器活性炭滤芯，要求说明清洗和更换条件，资料不足就不要猜。'
    question = '按维护资料应该多久清洗和更换？破损时要等到规定日期吗？'
    context = build_query_context(question, task_references=[goal],
                                  user_history=['最初目标是什么？', '准备进度：整理便签。', '好的'])
    retrieval = contextualize_query('多久清洗和更换？', question=question, query_context=context)
    assert goal in retrieval
    assert '空气净化器活性炭滤芯' in retrieval
    assert question in retrieval
    assert '最初目标是什么' not in retrieval and '便签' not in retrieval
    assert 'untrusted_conversation_reference' == context['trust']
    assert 'reported_results' not in context


@pytest.mark.parametrize('question', ['那新的电机多久维护？', '怎么清理主刷？',
                                     '这个充电座有什么用途？', '独立新对象说明'])
def test_explicit_current_object_wins_over_old_context_and_wrong_tool_query(question):
    goal = '对象是旧滤芯，讨论维护方法。'
    context = build_query_context(question, task_references=[goal])
    retrieval = contextualize_query('旧滤芯多久维护？', question=question, query_context=context)
    assert retrieval == question
    assert '旧滤芯' not in retrieval


def test_newest_literal_user_target_replaces_an_old_target():
    context = build_query_context('它多久清洗？', task_references=['对象是旧滤芯，说明维护。'],
                                  user_history=['对象是新的风机，讨论维护。'])
    retrieval = contextualize_query('它多久清洗？', query_context=context)
    assert '新的风机' in retrieval and '旧滤芯' not in retrieval


def test_complete_tool_query_does_not_get_an_unrelated_old_goal():
    context = build_query_context('它多久清洗？', task_references=['对象是旧滤芯，说明维护。'])
    retrieval = contextualize_query('主刷多久清洗？', query_context=context)
    assert '主刷' in retrieval and '旧滤芯' not in retrieval


def test_shortened_subject_can_be_refined_by_a_quoted_specific_target():
    context = build_query_context('滤芯多久更换？', task_references=['对象是净化器的活性炭滤芯。'])
    retrieval = contextualize_query('滤芯多久更换？', query_context=context)
    assert '活性炭滤芯' in retrieval


def test_goal_recall_question_does_not_replace_original_target():
    goal = '我这次要维护的部件是净化器的活性炭滤芯。请保留资料不足不要猜的要求。'
    question = '按维护资料应多久清洗和更换？破损时要等到规定日期吗？'
    context = build_query_context(question, task_references=[goal], user_history=[
        '请回顾一下，这次我要维护的具体部件是什么？我要求保留什么提醒？'])
    assert context['user_references'] == [goal]
    assert goal in contextualize_query(question, question=question, query_context=context)


@pytest.mark.parametrize('number_spacing', ['第63轮', '第 63轮', '第63 轮', '第 63 轮', '第\t63\t轮'])
def test_progress_sequence_whitespace_does_not_replace_task_goal(number_spacing):
    goal = '我这次要维护的部件是净化器的活性炭滤芯。'
    question = '它多久清洗？'
    context = build_query_context(question, task_references=[goal], user_history=[
        number_spacing + '整理进度：资料排序和核对标题，尚未开始操作。'])
    assert context['user_references'] == [goal]
    assert '活性炭滤芯' in contextualize_query(question, query_context=context)


@pytest.mark.parametrize('retained_only', [False, True])
def test_full_real_synthetic_seed_preserves_goal_at_context_to_retrieval_boundary(retained_only):
    cases_path = Path(__file__).resolve().parents[1] / 'evaluation/holdout_v2/cases.jsonl'
    case = next(json.loads(line) for line in cases_path.read_text(encoding='utf-8').splitlines()
                if json.loads(line).get('category') == 'long_history_component')
    seeded = seed_messages(case['seed_history'])
    assert len(seeded) == 128, 'Exercise all 64 real synthetic completed pairs'
    user_history = [message.content for message in seeded if isinstance(message, HumanMessage)]
    if retained_only:
        user_history = user_history[-2:]
    user_history.append(case['turns'][0]['query'])
    # The observed real summary preserved this exact first user quote. Derive
    # it from the input fixture, never from gold answers or model response text,
    # so this regression does not depend on a private run artifact's location.
    actual_summary = {'task_references': [seeded[0].content]}
    question = case['turns'][1]['query']
    context = build_query_context(question, user_history=user_history,
                                  task_references=actual_summary['task_references'])
    retrieval = contextualize_query(question, question=question, query_context=context)
    assert case['seed_history']['goal'] in retrieval
    assert context['user_references'] == actual_summary['task_references']
    assert '第 63 轮' not in retrieval and '第 64 轮' not in retrieval
    assert '整理进度' not in retrieval
    assert len(json.dumps(context, ensure_ascii=False).encode('utf-8')) <= 1024


def test_missing_context_keeps_the_original_question():
    assert contextualize_query('改写问题') == '改写问题'
    assert contextualize_query('不相关改写', question='新的电机多久维护？') == '新的电机多久维护？'


def test_long_current_question_is_preserved_including_last_object_and_requirement():
    question = '请按完整资料说明。' * 600 + '新的电机多久维护？最后请说明是否必须断电。'
    context = build_query_context(question, task_references=['对象是旧滤芯。'])
    retrieval = contextualize_query('旧滤芯多久维护？', question=question, query_context=context)
    assert retrieval.startswith(question)
    assert '最后请说明是否必须断电。' in retrieval


def test_optional_reference_is_dropped_instead_of_truncating_a_legal_current_request():
    question = '请保留原来的目标。' * 20 + '它多久维护？'
    context = build_query_context(question, task_references=['对象是旧滤芯。'])
    retrieval = contextualize_query(question, question=question, query_context=context,
                                    max_query_chars=len(question))
    assert retrieval == question


def test_context_is_bounded_by_serialized_utf8_bytes_including_json_escapes():
    context = build_query_context('问题：' + '\\"\n中文' * 1000,
                                  task_references=['对象是滤芯，' + '\\"\n中文' * 1000],
                                  user_history=['对象是新的风机，' + '中文' * 1000])
    assert len(json.dumps(context, ensure_ascii=False).encode('utf-8')) <= 1024
    with pytest.raises(ValueError):
        contextualize_query('它多久清洗', query_context={**context, 'permissions': ['admin']})
    with pytest.raises(ValueError):
        contextualize_query('它多久清洗', query_context={**context, 'user_references': ['x' * 1025]})


def test_real_agent_tool_receives_program_owned_user_quotes_without_public_schema_change():
    question = '按维护资料应该多久清洗和更换？'
    goal = '对象是空气净化器活性炭滤芯，资料不足不要猜。'
    model = ScriptedModel(responses=[call('rag_summarize', query='多久清洗和更换？'), answer('完成')])
    agent = ReactAgent('1001', model=model, context_policy=scripted_context_policy())
    agent.summary = {'topic': '整理资料', 'user_requests': [], 'reported_results': ['不能拿我当知识事实'],
                     'open_questions': [], 'task_references': [goal]}
    agent.messages = [HumanMessage(content='最初目标是什么？'), answer('模型提到了其他部件，不应保存。')]
    with patch('agent.tools.agent_tools.get_rag_service') as service:
        service.return_value.rag_summarize.return_value = '真实工具答复'
        assert ''.join(agent.execute_stream(question)) == '真实工具答复'
        args = service.return_value.rag_summarize.call_args
    assert args.kwargs['question'] == question
    assert args.kwargs['query_context']['user_references'] == [goal]
    assert '不能拿我当知识事实' not in json.dumps(args.kwargs['query_context'], ensure_ascii=False)
    assert '模型提到了其他部件' not in json.dumps(args.kwargs['query_context'], ensure_ascii=False)
    assert set(rag_summerize.tool_call_schema.model_json_schema()['properties']) == {'query'}
