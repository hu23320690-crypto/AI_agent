"""Offline control tests: real graph + injected model, no Ollama needed."""
from dataclasses import replace
import json
from threading import Event, Thread
import time
from typing import Any
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from pydantic import Field

from agent.react_agent import ReactAgent
from agent.runtime import (
    RunContext, RunLimits, ExecutionRuntime, runtime_call, current_run,
    DeadlineExceeded, CallTimeout, BudgetExceeded, RunCancelled, RunBusy,
)
from model.factory import QwenRetrievalEmbeddings
from rag.rag_service import RagSummarizeService
from test_core_flows import ScriptedModel, call, answer


class BlockingModel(ScriptedModel):
    entered: Any = Field(default_factory=Event)
    release: Any = Field(default_factory=Event)
    exited: Any = Field(default_factory=Event)

    def _generate(self, *args, **kwargs):
        self.entered.set()
        try:
            if not self.release.wait(5):
                raise RuntimeError('test failed to release its worker')
            return super()._generate(*args, **kwargs)
        finally:
            self.exited.set()


def isolated_agent(model, **changes):
    limits = replace(RunLimits(), **changes)
    return ReactAgent('1001', model=model, limits=limits, executor=ExecutionRuntime(limits))


def background_turn(agent, query='测试问题'):
    outcome = {}
    def work():
        try:
            outcome['answer'] = ''.join(agent.execute_stream(query))
        except Exception as exc:
            outcome['error'] = exc
    worker = Thread(target=work, daemon=True)
    worker.start()
    return worker, outcome


class RuntimeGraphTests(unittest.TestCase):
    def test_rag_and_outer_model_share_budget(self):
        outer = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('多余改写')])
        inner = ScriptedModel(responses=[answer('先断电。')])
        with patch('rag.rag_service.VectorStoreService') as store:
            store.return_value.get_retriever.return_value.invoke.return_value = [Document(page_content='先断电。')]
            service = RagSummarizeService()
            service._ready = True
        agent = isolated_agent(outer, max_model_calls=2)
        with patch('agent.tools.agent_tools.get_rag_service', return_value=service), patch('rag.rag_service.chat_model', inner):
            with self.assertRaises(BudgetExceeded):
                list(agent.execute_stream('如何保养'))
        self.assertEqual(len(outer.seen), 1)
        self.assertEqual(len(inner.seen), 1)
        self.assertEqual(agent.last_run['counts']['model'], 2)
        self.assertEqual(agent.last_run['counts']['tool'], 1)
        self.assertEqual(agent.messages, [])

    def test_nested_rag_succeeds_and_keeps_callback_propagation(self):
        from evaluation.run import telemetry
        recorder = telemetry()
        outer = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('多余改写')])
        inner = ScriptedModel(responses=[answer('先断电。')])
        with patch('rag.rag_service.VectorStoreService') as store:
            store.return_value.get_retriever.return_value.invoke.return_value = [Document(page_content='先断电。')]
            service = RagSummarizeService()
            service._ready = True
        agent = isolated_agent(outer, max_model_calls=3)
        invoke = agent.agent.invoke
        def traced(*args, **kwargs):
            kwargs['config'] = {**kwargs['config'], 'callbacks': [recorder]}
            return invoke(*args, **kwargs)
        with patch('agent.tools.agent_tools.get_rag_service', return_value=service), patch('rag.rag_service.chat_model', inner), patch.object(agent.agent, 'invoke', side_effect=traced):
            self.assertEqual(''.join(agent.execute_stream('如何保养')), '先断电。')
        self.assertEqual(agent.last_run['counts']['model'], 3)
        self.assertEqual(agent.last_run['status'], 'succeeded')
        self.assertEqual(len(recorder.models), 3)

    def test_tool_budget_aborts_without_next_model_turn(self):
        model = ScriptedModel(responses=[call('get_current_month'), call('get_current_month'), answer('不应发生')])
        agent = isolated_agent(model, max_tool_calls=1)
        with self.assertRaises(BudgetExceeded):
            list(agent.execute_stream('反复查月份'))
        self.assertEqual(agent.last_run['counts']['tool'], 1)
        self.assertEqual(len(model.seen), 2)
        self.assertEqual(agent.messages, [])

    def test_tool_timeout_is_terminal_and_cannot_be_paraphrased(self):
        release, entered = Event(), Event()
        def blocked(_query):
            entered.set()
            release.wait(5)
            return '迟到的知识回答'
        model = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('不应生成的解释')])
        agent = isolated_agent(model, tool_seconds=.12)
        try:
            with patch('agent.tools.agent_tools.get_rag_service') as service:
                service.return_value.rag_summarize.side_effect = blocked
                with self.assertRaises(CallTimeout):
                    list(agent.execute_stream('保养'))
            self.assertTrue(entered.is_set())
            self.assertEqual(len(model.seen), 1)
            self.assertEqual(agent.messages, [])
        finally:
            release.set()

    def test_whole_turn_timeout_does_not_wait_for_blocking_model(self):
        model = BlockingModel(responses=[answer('迟到回答')])
        agent = isolated_agent(model, total_seconds=.2)
        started = time.monotonic()
        try:
            with self.assertRaises(DeadlineExceeded):
                list(agent.execute_stream('阻塞'))
            self.assertLess(time.monotonic()-started, 1.5)
            self.assertTrue(model.entered.is_set())
            self.assertFalse(model.exited.is_set())
            self.assertEqual(agent.last_run['status'], 'timed_out')
        finally:
            model.release.set()
            self.assertTrue(model.exited.wait(2))
        self.assertEqual(agent.messages, [])

    def test_cancel_and_clear_prevent_late_history_commit(self):
        model = BlockingModel(responses=[answer('迟到回答')])
        agent = isolated_agent(model)
        agent.messages = [answer('旧历史')]
        worker, outcome = background_turn(agent)
        try:
            self.assertTrue(model.entered.wait(2))
            with self.assertRaises(RunBusy):
                list(agent.execute_stream('并发提问'))
            agent.clear_history()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertIsInstance(outcome.get('error'), RunCancelled)
            self.assertEqual(agent.messages, [])
        finally:
            model.release.set()
            self.assertTrue(model.exited.wait(2))
            worker.join(2)
        self.assertEqual(agent.messages, [])
        self.assertEqual(agent.last_run['status'], 'cancelled')

    def test_cancel_keeps_previous_successful_history(self):
        model = BlockingModel(responses=[answer('迟到回答')])
        agent = isolated_agent(model)
        previous = [answer('成功历史')]
        agent.messages = previous
        worker, outcome = background_turn(agent)
        try:
            self.assertTrue(model.entered.wait(2))
            self.assertTrue(agent.cancel_current())
            worker.join(1)
            self.assertIsInstance(outcome.get('error'), RunCancelled)
            self.assertEqual(agent.messages, previous)
        finally:
            model.release.set()
            self.assertTrue(model.exited.wait(2))
            worker.join(2)

    def test_input_limit_does_not_dispatch_model(self):
        model = ScriptedModel(responses=[answer('不应发生')])
        agent = isolated_agent(model, max_query_chars=4)
        with self.assertRaises(BudgetExceeded):
            list(agent.execute_stream('超过限制的提问'))
        self.assertEqual(model.seen, [])
        self.assertEqual(agent.last_run['counts'], {})

    def test_output_limit_does_not_commit(self):
        agent = isolated_agent(ScriptedModel(responses=[answer('x'*200)]), max_output_chars=100)
        with self.assertRaises(BudgetExceeded):
            list(agent.execute_stream('超长回答'))
        self.assertEqual(agent.messages, [])

    def test_tool_args_limit_precedes_execution(self):
        agent = isolated_agent(ScriptedModel(responses=[call('get_weather', city='x'*200)]), max_tool_args_chars=50)
        with self.assertRaises(BudgetExceeded):
            list(agent.execute_stream('天气'))
        self.assertEqual(agent.last_run['counts'].get('tool', 0), 0)

    def test_trace_does_not_store_question_answer_or_arguments(self):
        agent = isolated_agent(ScriptedModel(responses=[answer('秘密回答 marker-result')]))
        list(agent.execute_stream('秘密问题 marker-query'))
        trace = json.dumps(agent.last_run, ensure_ascii=False)
        self.assertNotIn('marker-query', trace)
        self.assertNotIn('marker-result', trace)
        self.assertIn('call_started', trace)


class RuntimeBoundaryTests(unittest.TestCase):
    def test_slow_call_keeps_capacity_until_actual_exit(self):
        limits = replace(RunLimits(), model_seconds=.08, model_concurrency=1)
        executor = ExecutionRuntime(limits)
        first = RunContext(limits, executor)
        release, entered = Event(), Event()
        def blocked():
            entered.set()
            release.wait(5)
            return 'late'
        try:
            with self.assertRaises(CallTimeout):
                runtime_call('model', 'blocked', blocked, run=first)
            self.assertTrue(entered.is_set())
            second = RunContext(limits, executor)
            unexpected = []
            with self.assertRaises(CallTimeout):
                runtime_call('model', 'queued', lambda: unexpected.append(True), run=second)
            self.assertEqual(unexpected, [])
            self.assertEqual(second.counts['model'], 0)
        finally:
            release.set()
        # A third request can proceed once the actual blocking worker exits.
        recovered = RunContext(replace(limits, model_seconds=2), executor)
        self.assertEqual(runtime_call('model', 'recovered', lambda: 'ok', run=recovered), 'ok')

    def test_nested_operations_share_run_id_and_deadline(self):
        now = [10.0]
        limits = replace(RunLimits(), total_seconds=5)
        run = RunContext(limits, ExecutionRuntime(limits), clock=lambda: now[0])
        observed = []
        def nested():
            observed.append((current_run().run_id, current_run().deadline))
            now[0] += 4
            return runtime_call('model', 'nested', lambda: observed.append(current_run().deadline))
        runtime_call('tool', 'parent', nested, run=run)
        self.assertEqual(observed, [(run.run_id, 15), 15])
        now[0] = 15
        with self.assertRaises(DeadlineExceeded):
            runtime_call('model', 'late', lambda: self.fail('must not execute'), run=run)

    def test_embedding_query_counts_once_and_keeps_qwen_instruction(self):
        limits = RunLimits()
        run = RunContext(limits, ExecutionRuntime(limits))
        embedding = QwenRetrievalEmbeddings(model='test-local-no-network')
        with patch.object(OllamaEmbeddings, 'embed_documents', return_value=[[1., 0.]]) as embed:
            result = runtime_call('retrieval', 'test', lambda: embedding.embed_query('主刷'), run=run)
        self.assertEqual(result, [1., 0.])
        self.assertEqual(run.counts['embedding'], 1)
        self.assertIn('Query: 主刷', embed.call_args.args[0][0])

    def test_cancelled_run_never_dispatches_new_work(self):
        run = RunContext(RunLimits(), ExecutionRuntime(RunLimits()))
        run.cancel()
        with self.assertRaises(RunCancelled):
            runtime_call('model', 'cancelled', lambda: self.fail('must not execute'), run=run)
        self.assertEqual(run.counts['model'], 0)

    def test_lazy_index_waiter_does_not_write_after_cancellation(self):
        limits = replace(RunLimits(), total_seconds=.1)
        run = RunContext(limits, ExecutionRuntime(limits))
        with patch('rag.rag_service.VectorStoreService'):
            service = RagSummarizeService()
        with service._index_lock:
            with self.assertRaises(DeadlineExceeded):
                runtime_call('retrieval', 'index-wait', service.ensure_index, run=run)
            service.vector_store.load_document.assert_not_called()
        # Wait for the pending reader to release its real worker lease.
        recovered = RunContext(RunLimits(), run.executor)
        runtime_call('retrieval', 'sync', lambda: None, run=recovered)
        service.vector_store.load_document.assert_not_called()

    def test_invalid_configuration_is_rejected(self):
        for field, value in [('total_seconds', 0), ('model_seconds', float('nan')),
                             ('max_model_calls', 1.5), ('tool_concurrency', True)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(RunLimits(), **{field: value})


if __name__ == '__main__':
    unittest.main()
