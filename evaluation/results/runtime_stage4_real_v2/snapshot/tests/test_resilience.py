"""Fault injection uses scripted dependencies and a fake clock, never outages."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

import httpx
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings, ChatOllama
from ollama import ResponseError

from agent.react_agent import ReactAgent
from agent.runtime import (RunContext, RunLimits, ExecutionRuntime, BudgetExceeded,
                           RunCancelled, CallTimeout, RuntimeControlError)
from agent.runtime.resilience import (
    CircuitBreaker, CircuitOpen, DependencyUnavailable, ResilienceController,
    ResiliencePolicy, dependency_call, dependency_key, transient_error,
    retry_after_seconds,
)
from model.factory import QwenRetrievalEmbeddings
from rag.rag_service import RagSummarizeService
from test_core_flows import ScriptedModel, call, answer


class FakeClock:
    def __init__(self):
        self.now = 100.0
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


def system(*, policy=None, limits=None):
    clock = FakeClock()
    policy = policy or ResiliencePolicy()
    limits = limits or RunLimits()
    controller = ResilienceController(policy, clock=clock, sleeper=clock.sleep, jitter=lambda low, high: high)
    executor = ExecutionRuntime(limits, resilience=controller)
    run = RunContext(limits, executor, clock=clock)
    return clock, controller, executor, run


def request(run, operation, *, dependency='test.chat', retry_safe=True, kind='model'):
    return dependency_call(kind, 'test.request', operation, dependency=dependency,
                           retry_safe=retry_safe, run=run)


def graph_executor():
    # Graph runs use the real RunContext clock. Remove waiting here; fake-time
    # backoff is separately tested with matching fake RunContext/controller clocks.
    return ExecutionRuntime(resilience=ResilienceController(ResiliencePolicy(), jitter=lambda low, high: 0))


class CircuitTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.policy = ResiliencePolicy(minimum_samples=2, failure_threshold=2)
        self.circuit = CircuitBreaker('test', self.policy, self.clock)

    def trip(self):
        for _ in range(2):
            self.circuit.record(self.circuit.acquire(), 'failure')

    def test_failures_trip_and_only_successful_probe_recovers(self):
        self.trip()
        with self.assertRaises(CircuitOpen):
            self.circuit.acquire()
        self.clock.sleep(self.policy.recovery_seconds)
        probe = self.circuit.acquire()
        self.assertTrue(probe.probe)
        self.circuit.record(probe, 'success')
        self.assertEqual(self.circuit.snapshot()['state'], 'CLOSED')
        self.assertEqual(self.circuit.snapshot()['samples'], 0)

    def test_old_failures_expire_and_minimum_sample_count_matters(self):
        circuit = CircuitBreaker('test', replace(self.policy, minimum_samples=3), self.clock)
        for _ in range(2):
            circuit.record(circuit.acquire(), 'failure')
        self.assertEqual(circuit.snapshot()['state'], 'CLOSED')
        self.clock.sleep(self.policy.window_seconds+1)
        circuit.record(circuit.acquire(), 'success')
        self.assertEqual(circuit.snapshot()['samples'], 1)
        self.assertEqual(circuit.snapshot()['failures'], 0)

    def test_minimum_samples_and_failure_threshold_both_required(self):
        circuit = CircuitBreaker('test', replace(self.policy, minimum_samples=3), self.clock)
        for outcome in ['failure', 'success', 'failure']:
            circuit.record(circuit.acquire(), outcome)
        self.assertEqual(circuit.snapshot()['state'], 'OPEN')

    def test_half_open_allows_only_one_concurrent_probe(self):
        self.trip()
        self.clock.sleep(self.policy.recovery_seconds)
        def try_acquire(_):
            try:
                return self.circuit.acquire()
            except CircuitOpen:
                return None
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(try_acquire, range(24)))
        self.assertEqual(sum(p is not None for p in results), 1)

    def test_failed_probe_reopens_with_new_cooldown(self):
        self.trip()
        self.clock.sleep(self.policy.recovery_seconds)
        probe = self.circuit.acquire()
        self.circuit.record(probe, 'failure')
        with self.assertRaises(CircuitOpen):
            self.circuit.acquire()
        self.clock.sleep(self.policy.recovery_seconds)
        self.assertTrue(self.circuit.acquire().probe)

    def test_cancelled_probe_releases_slot_without_claiming_recovery(self):
        self.trip()
        self.clock.sleep(self.policy.recovery_seconds)
        probe = self.circuit.acquire()
        self.circuit.record(probe, 'neutral')
        self.assertEqual(self.circuit.snapshot()['state'], 'HALF_OPEN')
        self.assertTrue(self.circuit.acquire().probe)

    def test_late_success_or_failure_cannot_change_new_circuit_generation(self):
        late_success = self.circuit.acquire()
        late_failure = self.circuit.acquire()
        self.trip()
        self.circuit.record(late_success, 'success')
        self.assertEqual(self.circuit.snapshot()['state'], 'OPEN')
        self.clock.sleep(self.policy.recovery_seconds)
        self.circuit.record(self.circuit.acquire(), 'success')
        self.circuit.record(late_failure, 'failure')
        self.assertEqual(self.circuit.snapshot()['failures'], 0)

    def test_queued_permission_becomes_invalid_when_another_request_trips(self):
        queued = self.circuit.acquire()
        self.trip()
        with self.assertRaises(CircuitOpen):
            self.circuit.validate(queued)


class RetryTests(unittest.TestCase):
    def test_transient_failure_retries_once_and_counts_both_attempts(self):
        clock, controller, _, run = system()
        operation = Mock(side_effect=[ConnectionError('transient'), 'ok'])
        self.assertEqual(request(run, operation), 'ok')
        self.assertEqual(operation.call_count, 2)
        self.assertEqual(run.counts['model'], 2)
        self.assertAlmostEqual(clock()-run.started, .5)
        self.assertEqual(controller.breaker('test.chat').snapshot()['failures'], 1)
        self.assertEqual(len([e for e in run.events if e['event']=='retry_scheduled']), 1)

    def test_backoff_grows_and_caps_with_jitter(self):
        policy = ResiliencePolicy(max_attempts=5, minimum_samples=10, failure_threshold=10)
        clock, controller, _, run = system(policy=policy)
        caps = []
        def jitter(low, high):
            caps.append(high)
            return high/2
        controller.jitter = jitter
        operation = Mock(side_effect=[ConnectionError()] * 4 + ['ok'])
        self.assertEqual(request(run, operation), 'ok')
        self.assertEqual(caps, [.5, 1, 2, 2])
        self.assertAlmostEqual(clock()-run.started, 2.75)

    def test_retry_exhaustion_does_not_exceed_configured_attempts(self):
        _, _, _, run = system()
        operation = Mock(side_effect=ConnectionError('sensitive-error-content'))
        with self.assertRaises(DependencyUnavailable):
            request(run, operation)
        self.assertEqual(operation.call_count, 2)
        self.assertNotIn('sensitive-error-content', json.dumps(run.snapshot()))

    def test_write_operation_is_single_attempt_by_default(self):
        _, _, _, run = system()
        operation = Mock(side_effect=ConnectionError())
        with self.assertRaises(DependencyUnavailable):
            dependency_call('tool', 'write', operation, dependency='external.write', run=run)
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(run.counts['tool'], 1)

    def test_nontransient_errors_do_not_retry_or_count_as_dependency_failure(self):
        for exc in [ValueError('invalid'), PermissionError('denied'), RuntimeError('bug'),
                    ResponseError('unauthorized', 401), ResponseError('forbidden', 403),
                    ResponseError('missing', 404), ResponseError('invalid', 422),
                    httpx.PoolTimeout('local pool'), httpx.LocalProtocolError('local misuse')]:
            with self.subTest(error=type(exc).__name__):
                _, controller, _, run = system()
                operation = Mock(side_effect=exc)
                with self.assertRaises(type(exc)):
                    request(run, operation)
                self.assertEqual(operation.call_count, 1)
                self.assertEqual(controller.breaker('test.chat').snapshot()['samples'], 0)

    def test_missing_business_record_is_a_success_not_a_service_failure(self):
        _, controller, _, run = system()
        self.assertEqual(request(run, lambda: {'status': 'not_found'}, kind='tool'), {'status': 'not_found'})
        self.assertEqual(controller.breaker('test.chat').snapshot()['failures'], 0)

    def test_known_transport_and_status_failures_are_retryable(self):
        for exc in [httpx.ConnectError('x'), httpx.ReadTimeout('x'), TimeoutError(),
                    ResponseError('overloaded', 429), ResponseError('unavailable', 503)]:
            with self.subTest(error=type(exc).__name__):
                self.assertTrue(transient_error(exc))

    def test_total_attempt_budget_includes_retries(self):
        clock, _, _, run = system(limits=replace(RunLimits(), max_model_calls=1))
        operation = Mock(side_effect=ConnectionError())
        with self.assertRaises(BudgetExceeded):
            request(run, operation)
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(run.counts['model'], 1)
        self.assertEqual(clock(), run.started)  # no backoff with exhausted budget

    def test_cancel_during_backoff_does_not_start_second_attempt(self):
        _, controller, _, run = system()
        controller.sleeper = lambda seconds: run.cancel()
        operation = Mock(side_effect=ConnectionError())
        with self.assertRaises(RunCancelled):
            request(run, operation)
        self.assertEqual(operation.call_count, 1)

    def test_retry_delay_must_fit_remaining_logical_call_time(self):
        clock, _, _, run = system(limits=replace(RunLimits(), model_seconds=1))
        def fail_late():
            clock.sleep(.8)
            raise ConnectionError()
        with self.assertRaises(DependencyUnavailable):
            request(run, fail_late)
        self.assertEqual(run.counts['model'], 1)
        self.assertAlmostEqual(clock()-run.started, .8)

    def test_retry_after_is_respected_or_request_stops_without_early_retry(self):
        response = httpx.Response(429, headers={'Retry-After': '3'}, request=httpx.Request('GET', 'http://test'))
        exc = httpx.HTTPStatusError('rate limited', request=response.request, response=response)
        self.assertEqual(retry_after_seconds(exc), 3)
        clock, _, _, run = system()
        self.assertEqual(request(run, Mock(side_effect=[exc, 'ok'])), 'ok')
        self.assertAlmostEqual(clock()-run.started, 3)
        _, _, _, short_run = system(limits=replace(RunLimits(), total_seconds=2))
        operation = Mock(side_effect=exc)
        with self.assertRaises(DependencyUnavailable):
            request(short_run, operation)
        self.assertEqual(operation.call_count, 1)

    def test_circuit_persists_across_runs_but_isolates_dependencies(self):
        clock, controller, executor, first = system()
        with self.assertRaises(DependencyUnavailable):
            request(first, Mock(side_effect=ConnectionError()))
        second = RunContext(first.limits, executor, clock=clock)
        with self.assertRaises(CircuitOpen):
            request(second, Mock(side_effect=ConnectionError()))
        denied = RunContext(first.limits, executor, clock=clock)
        operation = Mock(return_value='must not happen')
        with self.assertRaises(CircuitOpen):
            request(denied, operation)
        operation.assert_not_called()
        self.assertEqual(denied.counts['model'], 0)
        healthy = RunContext(first.limits, executor, clock=clock)
        self.assertEqual(request(healthy, lambda: 'other works', dependency='other.chat'), 'other works')
        self.assertEqual(controller.breaker('test.chat').snapshot()['state'], 'OPEN')

    def test_half_open_failure_does_not_retry_inside_probe(self):
        policy = ResiliencePolicy(minimum_samples=1, failure_threshold=1)
        clock, controller, executor, run = system(policy=policy)
        with self.assertRaises(CircuitOpen):
            request(run, Mock(side_effect=ConnectionError()))
        clock.sleep(policy.recovery_seconds)
        probe_run = RunContext(run.limits, executor, clock=clock)
        operation = Mock(side_effect=ConnectionError())
        with self.assertRaises(DependencyUnavailable):
            request(probe_run, operation)
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(controller.breaker('test.chat').snapshot()['state'], 'OPEN')

    def test_wait_timeout_does_not_launch_overlapping_retry(self):
        policy = ResiliencePolicy(minimum_samples=1, failure_threshold=1)
        controller = ResilienceController(policy)
        limits = replace(RunLimits(), model_seconds=.08)
        executor = ExecutionRuntime(limits, resilience=controller)
        run = RunContext(limits, executor)
        release, exited = Event(), Event()
        calls = []
        def blocked():
            calls.append(True)
            try:
                release.wait(5)
                return 'late'
            finally:
                exited.set()
        try:
            with self.assertRaises(CallTimeout):
                request(run, blocked)
            self.assertEqual(calls, [True])
            self.assertEqual(controller.breaker('test.chat').snapshot()['state'], 'OPEN')
        finally:
            release.set()
            self.assertTrue(exited.wait(2))
        self.assertEqual(controller.breaker('test.chat').snapshot()['state'], 'OPEN')

    def test_queue_timeout_is_not_a_dependency_outage(self):
        controller = ResilienceController(ResiliencePolicy(minimum_samples=1, failure_threshold=1))
        limits = replace(RunLimits(), model_seconds=.08, model_concurrency=1)
        executor = ExecutionRuntime(limits, resilience=controller)
        run = RunContext(limits, executor)
        executor.gates['model'].acquire()
        try:
            with self.assertRaises(CallTimeout):
                request(run, lambda: self.fail('must not dispatch'))
        finally:
            executor.gates['model'].release()
        self.assertEqual(controller.breaker('test.chat').snapshot()['samples'], 0)

    def test_nested_retry_owners_are_rejected(self):
        _, _, _, run = system()
        inner = Mock(return_value='never')
        with self.assertRaises(RuntimeControlError):
            request(run, lambda: request(run, inner, dependency='nested'))
        inner.assert_not_called()

    def test_terminal_dependency_failure_interrupts_sibling_wait_immediately(self):
        from agent.runtime import runtime_call
        controller = ResilienceController(ResiliencePolicy(max_attempts=1))
        run = RunContext(RunLimits(), ExecutionRuntime(resilience=controller))
        entered, release = Event(), Event()
        outcomes = []
        def blocked():
            entered.set()
            release.wait(5)
        def sibling():
            try:
                runtime_call('tool', 'sibling', blocked, run=run)
            except Exception as exc:
                outcomes.append(exc)
        worker = Thread(target=sibling, daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(DependencyUnavailable):
                request(run, Mock(side_effect=ConnectionError()))
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(run.status, 'failed')
            self.assertIsInstance(outcomes[0], DependencyUnavailable)
        finally:
            release.set()
            worker.join(2)

    def test_invalid_policy_is_rejected(self):
        for kwargs in [{'max_attempts': 6}, {'max_attempts': 1.5}, {'window_seconds': float('inf')},
                       {'minimum_samples': True}, {'base_delay_seconds': 3, 'max_delay_seconds': 1}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ResiliencePolicy(**kwargs)


class ResilienceGraphTests(unittest.TestCase):
    def test_real_graph_retries_model_and_only_commits_success(self):
        executor = graph_executor()
        model = ScriptedModel(responses=[ConnectionError(), answer('恢复成功')])
        agent = ReactAgent(model=model, executor=executor)
        self.assertEqual(''.join(agent.execute_stream('测试')), '恢复成功')
        self.assertEqual(agent.last_run['counts']['model'], 2)
        self.assertEqual(agent.last_run['status'], 'succeeded')

    def test_rag_retries_inner_model_without_replaying_tool(self):
        executor = graph_executor()
        outer = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('改写')])
        inner = ScriptedModel(responses=[ConnectionError(), answer('先断电。')])
        with patch('rag.rag_service.VectorStoreService') as store:
            store.return_value.get_retriever.return_value.invoke.return_value = [Document(page_content='先断电。')]
            service = RagSummarizeService()
            service._ready = True
        agent = ReactAgent(model=outer, executor=executor)
        with patch('agent.tools.agent_tools.get_rag_service', return_value=service), patch('rag.rag_service.chat_model', inner):
            self.assertEqual(''.join(agent.execute_stream('如何保养')), '先断电。')
        self.assertEqual(agent.last_run['counts']['model'], 4)
        self.assertEqual(agent.last_run['counts']['tool'], 1)
        self.assertEqual(store.return_value.get_retriever.return_value.invoke.call_count, 1)

    def test_rag_exhaustion_is_terminal_and_cannot_be_replaced_by_fake_answer(self):
        executor = graph_executor()
        outer = ScriptedModel(responses=[call('rag_summarize', query='保养'), answer('编造的回答')])
        inner = ScriptedModel(responses=[ConnectionError(), ConnectionError()])
        with patch('rag.rag_service.VectorStoreService') as store:
            store.return_value.get_retriever.return_value.invoke.return_value = [Document(page_content='先断电。')]
            service = RagSummarizeService()
            service._ready = True
        agent = ReactAgent(model=outer, executor=executor)
        with patch('agent.tools.agent_tools.get_rag_service', return_value=service), patch('rag.rag_service.chat_model', inner):
            with self.assertRaises(DependencyUnavailable):
                list(agent.execute_stream('如何保养'))
        self.assertEqual(len(outer.seen), 1)
        self.assertEqual(agent.messages, [])

    def test_embedding_retry_counts_each_http_attempt(self):
        _, _, _, run = system()
        embedding = QwenRetrievalEmbeddings(model='test')
        from agent.runtime import runtime_call
        with patch.object(OllamaEmbeddings, 'embed_documents', side_effect=[ConnectionError(), [[1., 0.]]]) as operation:
            result = runtime_call('retrieval', 'test', lambda: embedding.embed_query('主刷'), run=run)
        self.assertEqual(result, [1., 0.])
        self.assertEqual(operation.call_count, 2)
        self.assertEqual(run.counts['embedding'], 2)

    def test_model_and_rag_use_same_key_embedding_is_separate_and_secrets_are_hidden(self):
        model = Mock(base_url='http://user:private-token@localhost:11434', model='qwen')
        self.assertEqual(dependency_key(model, 'chat'), dependency_key(model, 'chat'))
        self.assertNotEqual(dependency_key(model, 'chat'), dependency_key(model, 'embedding'))
        self.assertNotIn('private-token', dependency_key(model, 'chat'))

    def test_breaker_is_shared_by_new_agent_instances_and_recovers(self):
        policy = ResiliencePolicy(max_attempts=1, minimum_samples=2, failure_threshold=2)
        clock, controller, executor, _ = system(policy=policy)
        for _ in range(2):
            agent = ReactAgent(model=ScriptedModel(responses=[ConnectionError()]), executor=executor)
            with self.assertRaises(DependencyUnavailable):
                list(agent.execute_stream('失败'))
        model = ScriptedModel(responses=[answer('恢复后成功')])
        agent = ReactAgent(model=model, executor=executor)
        with self.assertRaises(CircuitOpen):
            list(agent.execute_stream('熔断中'))
        self.assertEqual(model.seen, [])
        self.assertEqual(agent.messages, [])
        clock.sleep(policy.recovery_seconds)
        self.assertEqual(''.join(agent.execute_stream('恢复探测')), '恢复后成功')
        self.assertEqual(controller.breaker(dependency_key(model, 'chat')).snapshot()['state'], 'CLOSED')

    def test_actual_ollama_adapter_retries_http_503_before_streaming_answer(self):
        # Exercise the pinned SDK's ResponseError conversion, without a server.
        attempts = []
        def http_handler(request):
            attempts.append(request)
            if len(attempts) == 1:
                return httpx.Response(503, json={'error': 'temporarily unavailable'})
            payload = {'model': 'test-chat', 'created_at': '2026-09-30T00:00:00Z',
                       'message': {'role': 'assistant', 'content': '依赖恢复成功'},
                       'done': True, 'done_reason': 'stop', 'prompt_eval_count': 1, 'eval_count': 1}
            return httpx.Response(200, content=(json.dumps(payload)+'\n').encode())
        model = ChatOllama(model='test-chat', base_url='http://local-test.invalid')
        with httpx.Client(base_url='http://local-test.invalid', transport=httpx.MockTransport(http_handler)) as client:
            with patch.object(model._client, '_client', client):
                agent = ReactAgent(model=model, executor=graph_executor())
                self.assertEqual(''.join(agent.execute_stream('测试')), '依赖恢复成功')
        self.assertEqual(len(attempts), 2)
        self.assertEqual(agent.last_run['counts']['model'], 2)


if __name__ == '__main__':
    unittest.main()
