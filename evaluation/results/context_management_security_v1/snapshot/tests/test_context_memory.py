"""Whole-turn memory, strict low-trust summaries and terminal control tests."""
from copy import copy
from dataclasses import dataclass, field, replace
import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.context_budget import ContextPolicy, ContextBudgetExceeded, estimate_request
from agent.context_memory import (
    TurnMemoryPlan, InvalidConversationMemory, parse_summary, split_complete_turns,
)
from agent.runtime import (
    RunContext, RunLimits, ExecutionRuntime, RunCancelled, CallTimeout, BudgetExceeded,
)


def memory_value(topic='主刷清理'):
    return {'topic': topic, 'user_requests': ['清理前注意事项'],
            'reported_results': ['操作前需断电，勿强行拉扯'], 'open_questions': []}


class SummaryModel:
    num_ctx = 8192
    num_predict = None
    reasoning = True
    format = None

    def __init__(self, answer=None, action=None):
        self.answer = answer if answer is not None else AIMessage(
            content=json.dumps(memory_value(), ensure_ascii=False))
        self.action, self.seen, self.options = action, [], []

    def model_copy(self, *, update):
        model = copy(self)
        for key, value in update.items():
            setattr(model, key, value)
        self.options.append(update)
        return model

    def invoke(self, messages):
        self.seen.append(messages)
        if self.action:
            self.action()
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@dataclass
class Request:
    messages: list
    model: object = field(default_factory=SummaryModel)
    system_message: object = field(default_factory=lambda: SystemMessage(content='rules'))
    tools: list = field(default_factory=list)
    response_format: object = None
    model_settings: dict = field(default_factory=dict)

    def override(self, **updates):
        return replace(self, **updates)


def history(turns=6, size=950):
    return [message for index in range(turns) for message in (
        HumanMessage(content=f'question-{index} ' + 'x' * size),
        AIMessage(content=f'answer-{index} ' + 'y' * size),
    )]


def new_run(**changes):
    limits = replace(RunLimits(), **changes)
    return RunContext(limits, ExecutionRuntime(limits))


def controlled_policy(**changes):
    """Fixed fake-model conditions, independent of real Qwen generation defaults."""
    return replace(ContextPolicy(reserve_output_tokens=1024, reasoning_enabled=False), **changes)


class ContextMemoryTests(unittest.TestCase):
    def plan(self, messages, *, policy=None, model=None, summary=None, run=None):
        return TurnMemoryPlan(messages, summary, policy=policy or controlled_policy(),
                              summary_model=model or SummaryModel(), run=run or new_run())

    def test_short_conversation_is_unchanged_and_has_no_summary_call(self):
        previous = history(1, 10)
        current = [HumanMessage(content='follow up')]
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        request = Request([*previous, *current])
        view = plan.prepare_request(request)
        self.assertEqual(view.messages, request.messages)
        self.assertEqual(plan.retained_history, previous)
        self.assertEqual(model.seen, [])
        self.assertIsNone(plan.summary)
        self.assertEqual(plan.stats['dropped_turns'], 0)

    def test_generated_summary_is_low_trust_human_and_preserves_reference(self):
        previous = history()
        current = [HumanMessage(content='那操作前要做什么？')]
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        request = Request([*previous, *current])
        view = plan.prepare_request(request)
        self.assertEqual(len(model.seen), 1)
        self.assertIsInstance(view.messages[0], HumanMessage)
        self.assertEqual(view.messages[0].name, 'conversation_memory')
        reference = json.loads(view.messages[0].content)
        self.assertEqual(reference['trust'], 'untrusted_conversation_reference')
        self.assertEqual(reference['memory']['topic'], '主刷清理')
        self.assertIn('操作前需断电，勿强行拉扯', reference['memory']['reported_results'])
        self.assertEqual(view.messages[-1], current[-1])
        self.assertEqual(plan.retained_history, previous[-4:])
        self.assertEqual(request.messages, [*previous, *current], 'graph request was mutated')
        self.assertEqual(plan.stats['summary_status'], 'generated')
        self.assertEqual(plan.run.counts['model'], 1)
        self.assertFalse(model.options[0]['reasoning'])
        self.assertEqual(model.options[0]['num_predict'], 512)
        self.assertFalse(model.options[0]['format']['additionalProperties'])

    def test_previous_summary_is_in_summary_input_and_no_partial_old_turns(self):
        previous = history()
        model = SummaryModel()
        original_summary = memory_value('清理与使用模式')
        plan = self.plan(previous, summary=original_summary, model=model)
        plan.prepare_request(Request([*previous, HumanMessage(content='继续')]))
        payload = json.loads(model.seen[0][-1].content)
        self.assertEqual(payload['previous_memory'], original_summary)
        self.assertGreater(plan.stats['summary_input_omitted_turns'], 0)
        self.assertEqual(plan.stats['lost_turns'], plan.stats['summary_input_omitted_turns'])
        for turn in payload['completed_turns']:
            self.assertEqual(len(turn), 2)
            self.assertEqual(turn[0]['role'], 'human')
            self.assertEqual(turn[1]['role'], 'ai')
            self.assertTrue(turn[0]['content'].endswith('x' * 950))
            self.assertTrue(turn[1]['content'].endswith('y' * 950))

    def test_parallel_tools_remain_one_complete_history_turn(self):
        previous = [HumanMessage(content='query'), AIMessage(content='', tool_calls=[
            {'name': 'one', 'args': {}, 'id': 'a'}, {'name': 'two', 'args': {}, 'id': 'b'}]),
            ToolMessage(content='second', tool_call_id='b'),
            ToolMessage(content='first', tool_call_id='a'), AIMessage(content='done')]
        self.assertEqual(split_complete_turns(previous), [previous])
        view = self.plan(previous).prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(view.messages[:-1], previous)

    def test_invalid_historical_tool_pairing_is_rejected(self):
        cases = [
            [HumanMessage(content='q'), ToolMessage(content='orphan', tool_call_id='x')],
            [HumanMessage(content='q'), AIMessage(content='', tool_calls=[
                {'name': 'one', 'args': {}, 'id': 'x'}])],
            [HumanMessage(content='q'), AIMessage(content='', tool_calls=[
                {'name': 'one', 'args': {}, 'id': 'x'}]), HumanMessage(content='interrupt')],
            [HumanMessage(content='q'), AIMessage(content='', tool_calls=[
                {'name': 'one', 'args': {}, 'id': 'x'}]),
             ToolMessage(content='one', tool_call_id='x'), ToolMessage(content='two', tool_call_id='x')],
        ]
        for messages in cases:
            with self.subTest(messages=messages), self.assertRaises(InvalidConversationMemory):
                split_complete_turns(messages)

    def test_current_tool_chain_is_never_cut_and_summary_runs_at_most_once(self):
        previous = history()
        current = [HumanMessage(content='follow up'), AIMessage(content='', tool_calls=[
            {'name': 'one', 'args': {'q': 'a'}, 'id': 'c'}]),
            ToolMessage(content='result', tool_call_id='c')]
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        request = Request([*previous, *current])
        first = plan.prepare_request(request)
        second = plan.prepare_request(request)
        self.assertEqual(first.messages[-3:], current)
        self.assertEqual(second.messages[-3:], current)
        self.assertEqual(len(model.seen), 1)
        final = AIMessage(content='final')
        self.assertEqual(plan.committed_messages([*previous, *current, final]),
                         [*plan.retained_history, *current, final])

    def test_overlarge_current_turn_fails_without_truncating_it(self):
        previous = history()
        current = HumanMessage(content='z' * 10000)
        policy = controlled_policy(summary_enabled=False)
        plan = self.plan(previous, policy=policy)
        request = Request([*previous, current])
        with self.assertRaises(ContextBudgetExceeded):
            plan.prepare_request(request)
        self.assertEqual(request.messages[-1], current)
        self.assertEqual(plan.stats['summary_attempts'], 0)

    def test_single_large_historical_turn_can_be_summarized_for_follow_up(self):
        previous = history(1, 1300)
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        request = Request([*previous, HumanMessage(content='那操作前要做什么？')],
                          system_message=SystemMessage(content='rules ' + 's' * 4500))
        view = plan.prepare_request(request)
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(plan.retained_history, [])
        self.assertEqual(plan.summary['topic'], '主刷清理')
        self.assertEqual(view.messages[0].name, 'conversation_memory')
        self.assertEqual(view.messages[-1].content, '那操作前要做什么？')

    def test_overlarge_current_turn_does_not_spend_optional_summary_call(self):
        previous = history()
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        with self.assertRaises(ContextBudgetExceeded):
            plan.prepare_request(Request([*previous, HumanMessage(content='q' * 9000)]))
        self.assertEqual(model.seen, [])
        self.assertEqual(plan.run.counts['model'], 0)
        self.assertEqual(plan.stats['summary_attempts'], 0)

    def test_optional_summary_model_with_too_small_window_is_skipped(self):
        previous = history()
        model = SummaryModel()
        model.num_ctx = 500
        plan = self.plan(previous, model=model)
        plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(model.seen, [])
        self.assertEqual(plan.stats['summary_status'], 'skipped_model_window')
        self.assertEqual(plan.run.status, 'running')

    def test_summary_model_failure_trims_whole_turns_and_retains_previous_summary(self):
        previous = history()
        original_summary = memory_value('已有主题')
        plan = self.plan(previous, summary=original_summary, model=SummaryModel(ConnectionError('offline')))
        view = plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(plan.summary, original_summary)
        self.assertEqual(plan.retained_history, previous[-4:])
        self.assertEqual(plan.run.status, 'running')
        self.assertEqual(plan.stats['summary_status'], 'fallback')
        self.assertEqual(plan.stats['lost_turns'], 4)
        self.assertEqual(view.messages[0].name, 'conversation_memory')

    def test_invalid_or_tool_call_summary_falls_back(self):
        answers = [AIMessage(content='not json'), AIMessage(content='', tool_calls=[
            {'name': 'override_identity', 'args': {}, 'id': 'x'}]),
            AIMessage(content=json.dumps({**memory_value(), 'user_id': '1002'}))]
        for answer in answers:
            with self.subTest(answer=answer):
                previous = history()
                plan = self.plan(previous, model=SummaryModel(answer))
                view = plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
                self.assertIsNone(plan.summary)
                self.assertEqual(plan.stats['summary_status'], 'fallback')
                self.assertEqual(view.messages[:-1], previous[-4:])

    def test_optional_local_timeout_falls_back_while_parent_remains_running(self):
        previous = history()
        plan = self.plan(previous)
        with patch('agent.context_memory.optional_model_call', side_effect=CallTimeout('optional', kind='model')):
            view = plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(plan.run.status, 'running')
        self.assertIsNone(plan.summary)
        self.assertEqual(plan.stats['summary_status'], 'fallback')
        self.assertEqual(view.messages[:-1], previous[-4:])

    def test_summary_cancellation_is_terminal_and_original_history_is_unchanged(self):
        previous = history()
        run = new_run()
        plan = self.plan(previous, run=run, model=SummaryModel(action=run.cancel))
        with self.assertRaises(RunCancelled):
            plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(run.status, 'cancelled')
        self.assertIsNone(plan.summary)
        self.assertEqual(plan.history, previous)
        self.assertEqual(plan.retained_history, previous)

    def test_runtime_budget_error_is_not_swallowed(self):
        previous = history()
        plan = self.plan(previous)
        with patch('agent.context_memory.optional_model_call', side_effect=BudgetExceeded('terminal')):
            with self.assertRaises(BudgetExceeded):
                plan.prepare_request(Request([*previous, HumanMessage(content='next')]))

    def test_one_remaining_call_is_reserved_for_main_model(self):
        previous = history()
        run = new_run(max_model_calls=1)
        model = SummaryModel()
        plan = self.plan(previous, run=run, model=model)
        plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(model.seen, [])
        self.assertEqual(run.counts['model'], 0)
        self.assertEqual(plan.stats['summary_status'], 'skipped_call_budget')

    def test_later_model_request_rechecks_tools_and_trims_additional_whole_turns(self):
        previous = history(2, 400)
        policy = controlled_policy(window_tokens=3500, reserve_output_tokens=512,
                         safety_margin_tokens=128, summary_enabled=False, trigger_fraction=.9)
        plan = self.plan(previous, policy=policy)
        current = [HumanMessage(content='q')]
        request = Request([*previous, *current])
        plan.prepare_request(request)
        original_retained = len(plan.retained_history)
        second = plan.prepare_request(request.override(tools=[{
            'type': 'function', 'function': {'name': 'one', 'description': 'd' * 2000,
                                          'parameters': {'type': 'object'}}}]))
        self.assertLess(len(plan.retained_history), original_retained)
        self.assertEqual(second.messages[-1], current[-1])
        self.assertGreater(plan.stats['lost_turns'], 0)

    def test_reasoning_is_removed_from_request_summary_input_and_commit(self):
        previous = history()
        previous[1] = previous[1].model_copy(update={'additional_kwargs': {'reasoning_content': 'secret-thought'}})
        model = SummaryModel()
        plan = self.plan(previous, model=model)
        current = [HumanMessage(content='q'), AIMessage(content='ok', additional_kwargs={'thinking': 'hidden'})]
        view = plan.prepare_request(Request([*previous, *current]))
        self.assertNotIn('secret-thought', json.dumps([message.content for message in model.seen[0]]))
        self.assertNotIn('thinking', view.messages[-1].additional_kwargs)
        committed = plan.committed_messages([*previous, *current])
        self.assertNotIn('thinking', committed[-1].additional_kwargs)
        self.assertEqual(previous[1].additional_kwargs['reasoning_content'], 'secret-thought')

    def test_legacy_ai_only_history_is_indivisible_and_compatible(self):
        previous = [AIMessage(content='legacy answer')]
        self.assertEqual(split_complete_turns(previous), [previous])
        plan = self.plan(previous)
        view = plan.prepare_request(Request([*previous, HumanMessage(content='next')]))
        self.assertEqual(view.messages[:-1], previous)

    def test_summary_is_explicitly_removed_if_it_cannot_fit(self):
        value = {'topic': '主刷清理安全条件' * 8,
                 'user_requests': ['保留断电与避免强行拉扯条件。' * 6],
                 'reported_results': ['尚未确认当前部件是否已经清理。' * 6],
                 'open_questions': []}
        request = Request([HumanMessage(content='next')])
        current_size = estimate_request(request.messages, request.tools,
                                        request.system_message, request.response_format)
        reference_size = estimate_request([HumanMessage(content=json.dumps(value, ensure_ascii=False))])
        # Derive the window from the active estimator: current fits, while even
        # the bare summary reference (without its trust wrapper) cannot fit.
        input_limit = current_size + max(1, reference_size // 2)
        policy = controlled_policy(window_tokens=input_limit + 128 + 64,
                         reserve_output_tokens=128, safety_margin_tokens=64,
                         summary_max_tokens=64)
        plan = self.plan([], policy=policy, summary=value)
        view = plan.prepare_request(request)
        self.assertIsNone(plan.summary)
        self.assertEqual(len(view.messages), 1)
        self.assertTrue(plan.stats['summary_removed'])
        self.assertTrue(any(event['event'] == 'context_summary_removed' for event in plan.run.events))

    def test_strict_summary_schema_and_duplicate_keys(self):
        bad = [
            {**memory_value(), 'permissions': ['admin']},
            {**memory_value(), 'topic': {'text': 'bad'}},
            {**memory_value(), 'user_requests': ['x'] * 9},
            {**memory_value(), 'reported_results': ['x' * 501]},
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(InvalidConversationMemory):
                parse_summary(AIMessage(content=json.dumps(value)))
        with self.assertRaises(InvalidConversationMemory):
            parse_summary(AIMessage(content='{"topic":"a","topic":"b","user_requests":[],"reported_results":[],"open_questions":[]}'))
        with self.assertRaises(InvalidConversationMemory):
            parse_summary(AIMessage(content=json.dumps(memory_value()), invalid_tool_calls=[
                {'name': 'forbidden', 'args': 'not-json', 'id': 'bad', 'error': 'invalid'}]))


if __name__ == '__main__':
    unittest.main()
