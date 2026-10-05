"""Offline request-admission tests: no Ollama or external tokenizer needed."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from agent.context_budget import (
    ContextPolicy, ContextBudgetExceeded, load_context_policy, estimate_request,
    effective_input_limit, enforce_request, output_cap, sanitize_messages,
)
from agent.runtime import RunContext, RunCancelled


@tool
def sample_tool(query: str) -> str:
    """Search for a short query."""
    return query


class SampleOutput(BaseModel):
    answer: str


class ContextPolicyTests(unittest.TestCase):
    def test_default_configuration_and_replace_for_small_window(self):
        self.assertEqual(load_context_policy(), ContextPolicy())
        small = replace(ContextPolicy(), window_tokens=512, reserve_output_tokens=64,
                        safety_margin_tokens=16, summary_max_tokens=32, keep_recent_turns=1)
        self.assertEqual(effective_input_limit(small), 432)

    def test_invalid_values_and_budget_combinations_fail_closed(self):
        cases = [
            {'window_tokens': True}, {'window_tokens': 0}, {'window_tokens': 8192.0},
            {'reserve_output_tokens': False}, {'reserve_output_tokens': -1},
            {'safety_margin_tokens': True}, {'safety_margin_tokens': -1},
            {'keep_recent_turns': 0}, {'keep_recent_turns': True},
            {'trigger_fraction': True}, {'trigger_fraction': float('nan')},
            {'trigger_fraction': float('inf')}, {'trigger_fraction': 0},
            {'trigger_fraction': 1.1}, {'summary_max_tokens': 0},
            {'summary_max_tokens': True}, {'summary_max_tokens': 1025},
            {'summary_enabled': 'false'}, {'summary_enabled': 1}, {'window_tokens': 1280},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(ContextPolicy(), **changes)

    def test_yaml_unknown_non_mapping_and_invalid_values_rejected(self):
        with TemporaryDirectory() as directory:
            for index, text in enumerate(('unknown: 1', '- 1', 'window_tokens: true',
                                          'trigger_fraction: .nan', '')):
                path = Path(directory) / f'invalid-{index}.yml'
                path.write_text(text, encoding='utf-8')
                with self.subTest(text=text), self.assertRaises(ValueError):
                    load_context_policy(path)
            path = Path(directory) / 'valid.yml'
            path.write_text('summary_enabled: false\nsafety_margin_tokens: 0\n', encoding='utf-8')
            self.assertFalse(load_context_policy(path).summary_enabled)
            self.assertEqual(load_context_policy(path).safety_margin_tokens, 0)

    def test_real_window_reserves_output_and_preserves_smaller_binding(self):
        policy = ContextPolicy()
        self.assertEqual(effective_input_limit(policy), 6912)
        self.assertEqual(effective_input_limit(policy, SimpleNamespace(num_ctx=4096)), 2816)
        bound = SimpleNamespace(bound=SimpleNamespace(num_ctx=16384), kwargs={'num_ctx': 4096})
        self.assertEqual(effective_input_limit(policy, bound), 2816)
        for value in (True, 0, -1, 4096.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                effective_input_limit(policy, SimpleNamespace(num_ctx=value))
        with self.assertRaises(ValueError):
            effective_input_limit(policy, SimpleNamespace(num_ctx=1024))

    def test_positive_output_cap_preserves_stricter_model_limit(self):
        policy = ContextPolicy()
        self.assertEqual(output_cap(policy=policy), 1024)
        self.assertEqual(output_cap(SimpleNamespace(num_predict=-1), policy), 1024)
        self.assertEqual(output_cap(SimpleNamespace(num_predict=4096), policy), 1024)
        self.assertEqual(output_cap(SimpleNamespace(num_predict=128), policy), 128)
        binding = SimpleNamespace(bound=SimpleNamespace(num_predict=256), kwargs={'num_predict': 64})
        self.assertEqual(output_cap(binding, policy), 64)
        with self.assertRaises(ValueError):
            output_cap(SimpleNamespace(num_predict=True), policy)


class RequestEstimateTests(unittest.TestCase):
    def test_system_tools_and_format_all_add_to_request_estimate(self):
        messages = [HumanMessage(content='主刷如何清理？')]
        bare = estimate_request(messages)
        system = estimate_request(messages, system_message='Answer from references only.')
        with_tools = estimate_request(messages, tools=[sample_tool])
        with_format = estimate_request(messages, response_format=SampleOutput)
        self.assertGreater(system, bare)
        self.assertGreater(with_tools, bare)
        self.assertGreater(with_format, bare)
        self.assertGreater(estimate_request(messages, [sample_tool], 'Instructions', SampleOutput),
                           max(system, with_tools, with_format))

    def test_utf8_visible_content_and_tool_arguments_are_counted(self):
        ascii_size = estimate_request([HumanMessage(content='x')])
        chinese_size = estimate_request([HumanMessage(content='中')])
        self.assertEqual(chinese_size - ascii_size, 2)
        call = AIMessage(content='', tool_calls=[{'id': 'call-1', 'name': 'search',
                                                  'args': {'query': 'x'}, 'type': 'tool_call'}])
        larger = call.model_copy(update={'tool_calls': [{'id': 'call-1', 'name': 'search',
                                                        'args': {'query': 'x' * 300}, 'type': 'tool_call'}]})
        self.assertEqual(estimate_request([larger]) - estimate_request([call]), 299)
        observation = ToolMessage(content='result', tool_call_id='call-1')
        longer_id = observation.model_copy(update={'tool_call_id': 'call-123456'})
        self.assertEqual(estimate_request([longer_id]) - estimate_request([observation]), 5)

    def test_replayable_reasoning_counted_then_sanitized_metadata_not_counted(self):
        plain = AIMessage(content='visible answer')
        noisy = AIMessage(content='visible answer',
                          additional_kwargs={'reasoning_content': 'hidden' * 10000},
                          response_metadata={'ignored': 'metadata' * 10000},
                          usage_metadata={'input_tokens': 900000, 'output_tokens': 900000,
                                          'total_tokens': 1800000})
        self.assertGreater(estimate_request([noisy]), estimate_request([plain]) + 50000)
        clean = sanitize_messages([noisy])
        self.assertEqual(estimate_request([plain]), estimate_request(clean))
        metadata_only = noisy.model_copy(update={'additional_kwargs': {}})
        self.assertEqual(estimate_request([plain]), estimate_request([metadata_only]))
        dictionary = {'role': 'assistant', 'content': 'visible answer',
                      'response_metadata': {'ignored': 'x' * 10000}, 'usage_metadata': {'total_tokens': 90000}}
        self.assertEqual(estimate_request([plain]), estimate_request([dictionary]))

    def test_sanitize_preserves_complete_tool_calls_and_deep_copies(self):
        call = AIMessage(content=[{'type': 'thinking', 'thinking': 'hidden'},
                                  {'type': 'text', 'text': 'visible'}],
                         tool_calls=[{'id': 'c', 'name': 'search', 'args': {'query': 'x'}, 'type': 'tool_call'}],
                         additional_kwargs={'reasoning_content': 'hidden'})
        observation = ToolMessage(content='tool output', tool_call_id='c')
        original = [call, observation, HumanMessage(content='<think>literal user text</think>')]
        clean = sanitize_messages(original)
        self.assertEqual(clean[0].tool_calls, call.tool_calls)
        self.assertEqual(clean[1].tool_call_id, 'c')
        self.assertEqual(clean[0].content, [{'type': 'text', 'text': 'visible'}])
        self.assertEqual(clean[2].content, original[2].content)
        self.assertEqual(clean[0].additional_kwargs, {})
        clean[0].tool_calls[0]['args']['query'] = 'changed'
        self.assertEqual(call.tool_calls[0]['args']['query'], 'x')
        self.assertEqual(call.additional_kwargs['reasoning_content'], 'hidden')

    def test_sanitized_view_matches_actual_ollama_reasoning_replay_boundary(self):
        model = ChatOllama(model='offline-not-invoked', validate_model_on_init=False)
        call = AIMessage(content='visible',
                         tool_calls=[{'id': 'c', 'name': 'search', 'args': {'query': 'x'}, 'type': 'tool_call'}],
                         additional_kwargs={'reasoning_content': 'hidden trace'})
        observation = ToolMessage(content='result', tool_call_id='c')
        raw_wire = model._convert_messages_to_ollama_messages([call, observation])
        clean_wire = model._convert_messages_to_ollama_messages(sanitize_messages([call, observation]))
        self.assertEqual(raw_wire[0]['thinking'], 'hidden trace')
        self.assertNotIn('thinking', clean_wire[0])
        self.assertEqual(clean_wire[0]['content'], raw_wire[0]['content'])
        self.assertEqual(clean_wire[0]['tool_calls'], raw_wire[0]['tool_calls'])
        self.assertEqual(clean_wire[1]['tool_call_id'], 'c')

    def test_response_strategy_schema_mapping_is_counted(self):
        messages = [HumanMessage(content='answer')]
        schema = {'type': 'object', 'properties': {'answer': {'type': 'string'}}}
        self.assertEqual(estimate_request(messages, response_format=SimpleNamespace(schema=schema)),
                         estimate_request(messages, response_format=schema))

    def test_raw_tool_calls_counted_once_without_duplicate_metadata(self):
        parsed = AIMessage(content='', tool_calls=[{'id': 'c', 'name': 'search',
                                                    'args': {'query': 'x'}, 'type': 'tool_call'}])
        both = parsed.model_copy(update={'additional_kwargs': {'tool_calls': [{'large': 'x' * 99999}]}})
        self.assertEqual(estimate_request([parsed]), estimate_request([both]))
        raw = AIMessage(content='', additional_kwargs={'tool_calls': [
            {'id': 'c', 'type': 'function', 'function': {'name': 'search', 'arguments': '{"query":"x"}'}}
        ]})
        self.assertGreater(estimate_request([raw]), estimate_request([AIMessage(content='')]))

    def test_prompt_value_matches_explicit_messages(self):
        prompt = ChatPromptTemplate.from_messages([('system', 'Only facts.'), ('human', '{query}')])
        value = prompt.invoke({'query': '主刷保养'})
        self.assertEqual(estimate_request(value), estimate_request(value.to_messages()))
        self.assertEqual(estimate_request([SystemMessage(content='Only facts.'), HumanMessage(content='主刷保养')]),
                         estimate_request([('system', 'Only facts.'), ('user', '主刷保养')]))

    def test_nonfinite_nonserializable_and_cyclic_content_fail_closed(self):
        cyclic = {}
        cyclic['self'] = cyclic
        for content in ({'value': float('nan')}, {'value': object()}, cyclic):
            with self.subTest(content=type(content).__name__), self.assertRaises(ValueError):
                estimate_request([{'role': 'user', 'content': content}])


class RequestAdmissionTests(unittest.TestCase):
    def test_check_records_only_safe_metadata_and_never_dispatches(self):
        run = RunContext()
        messages = [HumanMessage(content='private query')]
        size = enforce_request(messages, run=run, label='agent.model')
        self.assertEqual(size, estimate_request(messages))
        self.assertEqual(run.counts['model'], 0)
        event = run.events[-1]
        self.assertEqual(event['event'], 'context_budget_checked')
        self.assertEqual(event['estimation_method'], 'utf8_bytes_plus_framing')
        self.assertNotIn('private query', str(event))

    def test_overflow_recoverable_and_complete_messages_unmodified(self):
        policy = replace(ContextPolicy(), window_tokens=512, reserve_output_tokens=64,
                         safety_margin_tokens=16, summary_max_tokens=32)
        call = AIMessage(content='', tool_calls=[{'id': 'c', 'name': 'search',
                                                 'args': {'query': 'x'}, 'type': 'tool_call'}])
        result = ToolMessage(content='x' * 600, tool_call_id='c')
        current = HumanMessage(content='keep current question')
        messages = [HumanMessage(content='old question'), call, result, current]
        before = [message.model_dump() for message in messages]
        run = RunContext()
        with self.assertRaises(ContextBudgetExceeded) as caught:
            enforce_request(messages, policy=policy, run=run, label='summary.request')
        self.assertEqual(caught.exception.input_limit, 432)
        self.assertEqual(caught.exception.label, 'summary.request')
        self.assertEqual([message.model_dump() for message in messages], before)
        self.assertEqual(run.status, 'running')
        self.assertIsNone(run.error)
        self.assertEqual(run.counts['model'], 0)
        self.assertEqual(run.events[-1]['event'], 'context_budget_exceeded')
        self.assertGreater(enforce_request([current], policy=policy, run=run), 0)

    def test_boundary_admitted_and_one_extra_byte_rejected(self):
        messages = [HumanMessage(content='x')]
        size = estimate_request(messages)
        policy = ContextPolicy(window_tokens=size + 20, reserve_output_tokens=16,
                               safety_margin_tokens=4, summary_max_tokens=8)
        self.assertEqual(enforce_request(messages, policy=policy), size)
        with self.assertRaises(ContextBudgetExceeded):
            enforce_request([HumanMessage(content='xx')], policy=policy)

    def test_already_cancelled_run_does_not_estimate_or_dispatch(self):
        run = RunContext()
        run.cancel()
        with self.assertRaises(RunCancelled):
            enforce_request([HumanMessage(content='x')], run=run)
        self.assertEqual(run.counts['model'], 0)
        self.assertFalse(any(event['event'] == 'context_budget_checked' for event in run.events))


if __name__ == '__main__':
    unittest.main()
