"""Request boundaries and optional-summary execution use the real runtime/graph."""
from dataclasses import replace
from threading import Event, Thread
import unittest
from unittest.mock import patch

from agent.runtime import (RunContext, RunLimits, ExecutionRuntime, RunCancelled,
                           CallTimeout, BudgetExceeded, runtime_call, optional_model_call)


class OptionalSummaryRuntimeTests(unittest.TestCase):
    def make_run(self, **changes):
        limits = replace(RunLimits(), **changes)
        return RunContext(limits, ExecutionRuntime(limits))

    def test_optional_timeout_keeps_parent_alive_and_worker_capacity(self):
        run = self.make_run(total_seconds=2, model_concurrency=2)
        entered, release, exited = Event(), Event(), Event()
        def blocked():
            entered.set()
            try:
                release.wait(2)
                return 'late summary'
            finally:
                exited.set()
        try:
            with self.assertRaises(CallTimeout):
                optional_model_call('summary', blocked, run=run, dependency='test-summary', seconds=.05)
            self.assertTrue(entered.is_set())
            self.assertEqual(run.status, 'running')
            self.assertEqual(run.counts['model'], 1)
            gate = run.executor.gates['model']
            self.assertTrue(gate.acquire(blocking=False))
            self.assertFalse(gate.acquire(blocking=False), 'Timed-out worker lost its lease')
            gate.release()
            self.assertEqual(runtime_call('model', 'main', lambda: 'answer', run=run), 'answer')
            run.complete()
            self.assertEqual(run.counts['model'], 2)
        finally:
            release.set()
        self.assertTrue(exited.wait(1))

    def test_optional_queue_timeout_does_not_dispatch_or_count_outage(self):
        run = self.make_run(total_seconds=2, model_concurrency=1)
        gate = run.executor.gates['model']
        gate.acquire()
        called = []
        try:
            with self.assertRaises(CallTimeout):
                optional_model_call('summary', lambda: called.append(True), run=run,
                                    dependency='test-summary', seconds=.03)
            self.assertEqual(called, [])
            self.assertEqual(run.counts['model'], 0)
            self.assertEqual(run.executor.resilience.breaker('test-summary').snapshot()['failures'], 0)
            self.assertEqual(run.status, 'running')
        finally:
            gate.release()

    def test_optional_cancellation_stays_terminal(self):
        run = self.make_run(total_seconds=2)
        entered, release = Event(), Event()
        errors = []
        def blocked():
            entered.set()
            release.wait(2)
        def execute():
            try:
                optional_model_call('summary', blocked, run=run, dependency='test-summary', seconds=1)
            except BaseException as exc:
                errors.append(exc)
        worker = Thread(target=execute)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            run.cancel()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertIsInstance(errors[0], RunCancelled)
            self.assertEqual(run.status, 'cancelled')
        finally:
            release.set()
            worker.join(2)

    def test_evidence_deduplication_and_limit_are_bounded(self):
        run = self.make_run(max_commit_checks=2)
        class Check:
            def __init__(self, key):
                self.evidence_key = key
            def __call__(self):
                pass
        first = Check(('source', 1, 'chunk-a'))
        run.add_commit_check(first)
        run.add_commit_check(Check(first.evidence_key))
        self.assertEqual(run.get_commit_checks(), (first,))
        run.add_commit_check(Check(('source', 1, 'chunk-b')))
        with self.assertRaises(BudgetExceeded):
            run.add_commit_check(Check(('source', 2, 'chunk-a')))


class ContextGraphIntegrationTests(unittest.TestCase):
    def test_current_input_over_budget_dispatches_zero_models(self):
        from agent.react_agent import ReactAgent
        from agent.context_budget import ContextBudgetExceeded
        from test_core_flows import ScriptedModel, answer
        model = ScriptedModel(responses=[answer('must not dispatch')])
        agent = ReactAgent(model=model)
        with self.assertRaises(ContextBudgetExceeded):
            list(agent.execute_stream('x' * 7000))
        self.assertEqual(model.seen, [])
        self.assertEqual(agent.last_run['counts'].get('model', 0), 0)
        self.assertEqual(agent.messages, [])
        self.assertIsNone(agent.summary)

    def test_current_tool_chain_is_not_trimmed_to_make_it_fit(self):
        from agent.react_agent import ReactAgent
        from agent.context_budget import ContextBudgetExceeded
        from test_core_flows import ScriptedModel, call, answer
        model = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('must not dispatch')])
        agent = ReactAgent(model=model)
        with patch('agent.tools.agent_tools.get_rag_service') as service:
            service.return_value.rag_summarize.return_value = 'x' * 7000
            with self.assertRaises(ContextBudgetExceeded):
                list(agent.execute_stream('如何保养'))
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(agent.last_run['counts'].get('model', 0), 1)
        self.assertEqual(agent.last_run['counts']['tool'], 1)
        self.assertEqual(agent.messages, [])

    def test_rag_budget_checked_before_dispatch(self):
        from agent.context_budget import ContextBudgetExceeded
        from rag.rag_service import invoke_rag_model
        from langchain_core.prompt_values import ChatPromptValue
        from langchain_core.messages import HumanMessage
        from test_core_flows import ScriptedModel, answer
        model = ScriptedModel(responses=[answer('must not dispatch')])
        run = RunContext()
        with patch('rag.rag_service.chat_model', model):
            with self.assertRaises(ContextBudgetExceeded):
                runtime_call('run', 'test.rag', lambda: invoke_rag_model(
                    ChatPromptValue(messages=[HumanMessage(content='x' * 8000)]), {}), run=run)
        self.assertEqual(model.seen, [])
        self.assertEqual(run.counts['model'], 0)

    def test_revocation_discards_summary_and_raw_history(self):
        from agent.react_agent import ReactAgent
        from rag.security import KnowledgeAccessError
        from langchain_core.messages import HumanMessage
        from test_core_flows import ScriptedModel, answer
        model = ScriptedModel(responses=[answer('新的回答')])
        agent = ReactAgent(model=model)
        agent.messages = [HumanMessage(content='obsolete-raw'), answer('obsolete-answer')]
        agent.summary = {'topic': 'obsolete-summary', 'user_requests': [],
                         'reported_results': [], 'open_questions': []}
        def revoked():
            raise KnowledgeAccessError('revoked')
        agent._history_checks = [revoked]
        self.assertEqual(''.join(agent.execute_stream('你好')), '新的回答')
        self.assertIsNone(agent.summary)
        self.assertNotIn('obsolete', str(model.seen))
        self.assertEqual(agent._history_checks, [])

    def test_clear_also_removes_summary(self):
        from agent.react_agent import ReactAgent
        from test_core_flows import ScriptedModel
        agent = ReactAgent(model=ScriptedModel(responses=[]))
        agent.summary = {'topic': 'old'}
        agent.clear_history()
        self.assertIsNone(agent.summary)


if __name__ == '__main__':
    unittest.main()
