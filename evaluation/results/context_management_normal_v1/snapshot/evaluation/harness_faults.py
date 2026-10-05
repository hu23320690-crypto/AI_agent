"""Reproducible fault scenarios against the real runtime and Agent graph.

No HTTP requests, database writes, or service outages are needed. Each injected
blocking worker is explicitly released; cancellation bounds waiting, not remote
execution. Assertions inspect dispatch, capacity, and conversation commit.
"""
from collections import Counter
from dataclasses import replace
from threading import Event, Thread
import time
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent.react_agent import ReactAgent
from agent.context_budget import ContextPolicy
from agent.runtime import (
    BudgetExceeded, CallTimeout, ExecutionRuntime, RunCancelled, RunContext,
    RunLimits, runtime_call,
)
from agent.runtime.resilience import (
    CircuitOpen, DependencyUnavailable, ResilienceController, ResiliencePolicy,
    dependency_call,
)


def _answer(text):
    return AIMessage(content=text)


def _tool(name, **arguments):
    return AIMessage(content='', tool_calls=[{
        'name': name, 'args': arguments, 'id': uuid4().hex,
    }])


class ScriptedFaultModel(BaseChatModel):
    """Model fixture: calls still pass through actual Agent middleware."""
    responses: list[Any] = Field(default_factory=list)
    dispatches: int = 0
    block_first: bool = False
    loop_tool: bool = False
    entered: Any = Field(default_factory=Event)
    release: Any = Field(default_factory=Event)
    exited: Any = Field(default_factory=Event)

    @property
    def _llm_type(self):
        return 'offline-fault-harness'

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.dispatches += 1
        blocked = self.block_first and self.dispatches == 1
        try:
            if blocked:
                self.entered.set()
                if not self.release.wait(5):
                    raise AssertionError('Harness failed to release model worker')
            if self.loop_tool:
                response = _tool('get_current_month')
            else:
                if not self.responses:
                    raise AssertionError('Unexpected model dispatch exhausted fixture')
                response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return ChatResult(generations=[ChatGeneration(message=response)])
        finally:
            if blocked:
                self.exited.set()


class FakeClock:
    """Only dependency recovery/backoff use synthetic time."""
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Scenario:
    def __init__(self, case_id, title):
        self.id, self.title = case_id, title
        self.started = time.monotonic()
        self.assertions, self.runs = [], []

    def check(self, name, actual, expected=True):
        self.assertions.append({'name': name, 'passed': actual == expected,
                                'actual': actual, 'expected': expected})

    def capture(self, phase, run):
        snapshot = run if isinstance(run, dict) else run.snapshot()
        self.runs.append({'phase': phase, **snapshot})

    def finish(self, error=None):
        counts = Counter()
        for run in self.runs:
            counts.update(run['counts'])
        row = {
            'id': self.id, 'title': self.title,
            'status': 'passed' if error is None and self.assertions and all(
                check['passed'] for check in self.assertions) else 'failed',
            'assertions': self.assertions,
            'elapsed': round(time.monotonic()-self.started, 6),
            'counts': dict(counts), 'trace': self.runs,
        }
        if error is not None:
            row['error_type'] = type(error).__name__
        return row


def _agent(model, *, executor=None, **limits):
    parameters = {'total_seconds': 3, 'model_seconds': 1, 'tool_seconds': 1, **limits}
    policy = replace(RunLimits(), **parameters)
    executor = executor or ExecutionRuntime(policy, resilience=ResilienceController(
        ResiliencePolicy(), jitter=lambda low, high: 0))
    return ReactAgent('1001', model=model, limits=policy, executor=executor,
                      context_policy=ContextPolicy(reserve_output_tokens=1024,
                                                   reasoning_enabled=False))


def _turn(agent):
    try:
        return ''.join(agent.execute_stream('离线故障验收')), None
    except Exception as exc:
        return None, exc


def _background(agent):
    outcome = {}
    def invoke():
        outcome['answer'], outcome['error'] = _turn(agent)
    worker = Thread(target=invoke, daemon=True)
    worker.start()
    return worker, outcome


def _capture_call(run, operation):
    try:
        return operation(), None
    except Exception as exc:
        run.fail(exc)
        return None, exc


def _model_blocked(case):
    model = ScriptedFaultModel(block_first=True, responses=[
        _answer('迟到回答'), _answer('正常控制回答'),
    ])
    agent = _agent(model, model_seconds=.12)
    try:
        result, error = _turn(agent)
        case.check('model_timeout_is_terminal', isinstance(error, CallTimeout))
        case.check('worker_really_dispatched', model.entered.is_set())
        case.check('caller_stops_before_worker_exits', model.exited.is_set(), False)
        case.check('one_model_dispatch_without_overlap_retry', model.dispatches, 1)
        case.check('no_failed_turn_history_commit', len(agent.messages), 0)
        case.check('no_answer_emitted', result, None)
        case.capture('blocked_model', agent.last_run)
    finally:
        model.release.set()
        if not model.exited.wait(2):
            raise AssertionError('Model fixture did not exit')
    result, error = _turn(agent)
    case.check('recovered_capacity_accepts_normal_turn', error is None and result == '正常控制回答')
    case.check('only_control_turn_commits', len(agent.messages), 2)
    case.capture('normal_control', agent.last_run)


def _tool_blocked(case):
    entered, release, exited = Event(), Event(), Event()
    side_effects = []
    def block(query):
        side_effects.append('tool_dispatched')
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError('Harness failed to release tool worker')
            return '迟到的工具结果'
        finally:
            exited.set()
    model = ScriptedFaultModel(responses=[
        _tool('rag_summarize', query='保养'), _answer('正常控制回答'),
    ])
    agent = _agent(model, tool_seconds=.12)
    try:
        with patch('agent.tools.agent_tools.get_rag_service') as service:
            service.return_value.rag_summarize.side_effect = block
            result, error = _turn(agent)
        case.check('tool_timeout_is_terminal', isinstance(error, CallTimeout))
        case.check('tool_operation_really_dispatched', entered.is_set())
        case.check('caller_stops_before_tool_exits', exited.is_set(), False)
        case.check('no_model_paraphrase_after_timeout', model.dispatches, 1)
        case.check('tool_dispatch_count', len(side_effects), 1)
        case.check('no_failed_turn_history_commit', len(agent.messages), 0)
        case.check('no_answer_emitted', result, None)
        case.capture('blocked_tool', agent.last_run)
    finally:
        release.set()
        if not exited.wait(2):
            raise AssertionError('Tool fixture did not exit')
    result, error = _turn(agent)
    case.check('normal_turn_after_tool_release', error is None and result == '正常控制回答')
    case.check('only_control_turn_commits', len(agent.messages), 2)
    case.capture('normal_control', agent.last_run)


def _dependency_system():
    clock = FakeClock()
    policy = ResiliencePolicy(minimum_samples=3, failure_threshold=3)
    controller = ResilienceController(policy, clock=clock, sleeper=clock.sleep,
                                      jitter=lambda low, high: high)
    limits = RunLimits()
    executor = ExecutionRuntime(limits, resilience=controller)
    return clock, controller, limits, executor


def _dependency(run, operation, dependency='harness.chat'):
    return dependency_call('model', 'harness.dependency', operation,
                           dependency=dependency, retry_safe=True, run=run)


def _trip(case, clock, controller, limits, executor):
    dispatches = []
    def fail():
        dispatches.append('failed_request')
        raise ConnectionError('Injected offline dependency failure')
    first = RunContext(limits, executor, clock=clock)
    _, first_error = _capture_call(first, lambda: _dependency(first, fail))
    case.check('first_run_stops_after_two_attempts', len(dispatches), 2)
    case.check('retry_exhaustion_error', isinstance(first_error, DependencyUnavailable))
    case.capture('first_failure', first)
    second = RunContext(limits, executor, clock=clock)
    _, second_error = _capture_call(second, lambda: _dependency(second, fail))
    case.check('third_failure_trips_without_fourth_attempt', len(dispatches), 3)
    case.check('breaker_rejects_retry', isinstance(second_error, CircuitOpen))
    case.check('circuit_is_open', controller.breaker('harness.chat').snapshot()['state'], 'OPEN')
    case.capture('tripping_failure', second)
    return dispatches


def _continuous_failures(case):
    clock, controller, limits, executor = _dependency_system()
    dispatches = _trip(case, clock, controller, limits, executor)
    denied_side_effects = []
    denied = RunContext(limits, executor, clock=clock)
    _, error = _capture_call(denied, lambda: _dependency(
        denied, lambda: denied_side_effects.append('should_not_dispatch')))
    case.check('open_circuit_rejects_new_run', isinstance(error, CircuitOpen))
    case.check('rejection_has_zero_dispatch_side_effects', len(denied_side_effects), 0)
    case.check('rejection_consumes_no_model_attempt', denied.counts['model'], 0)
    case.capture('open_rejection', denied)
    healthy = RunContext(limits, executor, clock=clock)
    result, error = _capture_call(healthy, lambda: _dependency(
        healthy, lambda: 'healthy', dependency='harness.other'))
    if error is None:
        healthy.complete()
    case.check('unrelated_dependency_control_succeeds', error is None and result == 'healthy')
    case.check('failed_dependency_stays_open', controller.breaker('harness.chat').snapshot()['state'], 'OPEN')
    case.check('fault_request_dispatches_remain_bounded', len(dispatches), 3)
    case.capture('healthy_dependency_control', healthy)


def _half_open_recovery(case):
    clock, controller, limits, executor = _dependency_system()
    _trip(case, clock, controller, limits, executor)
    clock.sleep(controller.policy.recovery_seconds)
    entered, release, exited = Event(), Event(), Event()
    dispatches = []
    probe = RunContext(limits, executor, clock=clock)
    outcome = {}
    def probe_operation():
        dispatches.append('probe')
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError('Harness failed to release recovery probe')
            return 'recovered'
        finally:
            exited.set()
    def invoke():
        outcome['result'], outcome['error'] = _capture_call(
            probe, lambda: _dependency(probe, probe_operation))
        if outcome['error'] is None:
            probe.complete()
    worker = Thread(target=invoke, daemon=True)
    worker.start()
    try:
        if not entered.wait(2):
            raise AssertionError('Recovery probe did not dispatch')
        case.check('cooldown_enters_half_open', controller.breaker('harness.chat').snapshot()['state'], 'HALF_OPEN')
        competitor = RunContext(limits, executor, clock=clock)
        competitor_effects = []
        _, error = _capture_call(competitor, lambda: _dependency(
            competitor, lambda: competitor_effects.append('unexpected')))
        case.check('second_probe_is_rejected', isinstance(error, CircuitOpen))
        case.check('only_one_probe_operation_dispatches', len(competitor_effects), 0)
        case.check('rejected_probe_consumes_no_attempt', competitor.counts['model'], 0)
        case.capture('concurrent_probe_rejection', competitor)
    finally:
        release.set()
        worker.join(2)
    case.check('probe_worker_exits', not worker.is_alive() and exited.is_set())
    case.check('successful_probe_returns_result', outcome.get('error') is None and outcome.get('result') == 'recovered')
    case.check('successful_probe_closes_circuit', controller.breaker('harness.chat').snapshot()['state'], 'CLOSED')
    case.check('exactly_one_recovery_probe', len(dispatches), 1)
    case.capture('successful_probe', probe)
    normal = RunContext(limits, executor, clock=clock)
    result, error = _capture_call(normal, lambda: _dependency(normal, lambda: 'normal'))
    if error is None:
        normal.complete()
    case.check('normal_request_after_recovery', error is None and result == 'normal')
    case.capture('normal_control', normal)


def _infinite_loop(case):
    model = ScriptedFaultModel(loop_tool=True)
    agent = _agent(model, max_model_calls=6, max_tool_calls=3)
    result, error = _turn(agent)
    case.check('loop_stops_with_budget_error', isinstance(error, BudgetExceeded))
    case.check('tool_dispatch_count_is_exact_limit', agent.last_run['counts'].get('tool'), 3)
    case.check('only_four_model_dispatches', model.dispatches, 4)
    case.check('no_failed_turn_history_commit', len(agent.messages), 0)
    case.check('no_loop_answer_emitted', result, None)
    case.capture('infinite_tool_loop', agent.last_run)
    model.loop_tool = False
    model.responses.append(_answer('正常控制回答'))
    result, error = _turn(agent)
    case.check('next_turn_has_fresh_budget', error is None and result == '正常控制回答')
    case.check('failed_loop_is_absent_from_history', len(agent.messages), 2)
    case.capture('normal_control', agent.last_run)


def _cancel_late_commit(case):
    model = ScriptedFaultModel(block_first=True, responses=[
        _answer('迟到回答'), _answer('正常控制回答'),
    ])
    agent = _agent(model)
    previous = [_answer('旧历史')]
    agent.messages = list(previous)
    worker, outcome = _background(agent)
    try:
        if not model.entered.wait(2):
            raise AssertionError('Cancelled model did not dispatch')
        case.check('cancel_marks_active_run', agent.cancel_current())
        worker.join(2)
        case.check('caller_returns_before_remote_worker', not worker.is_alive() and not model.exited.is_set())
        case.check('cancelled_turn_raises_control_error', isinstance(outcome.get('error'), RunCancelled))
        case.check('cancel_preserves_previous_history', agent.messages == previous)
        case.check('cancel_emits_no_answer', outcome.get('answer'), None)
        case.capture('cancelled_turn', agent.last_run)
    finally:
        model.release.set()
        if not model.exited.wait(2):
            raise AssertionError('Cancelled model fixture did not exit')
        worker.join(2)
    result, error = _turn(agent)
    case.check('normal_next_turn_after_late_return', error is None and result == '正常控制回答')
    case.check('late_worker_does_not_commit', len(agent.messages), len(previous)+2)
    case.check('late_answer_is_absent', all(message.content != '迟到回答' for message in agent.messages))
    case.capture('normal_control', agent.last_run)


def _capacity_queue(case):
    limits = replace(RunLimits(), total_seconds=3, model_seconds=.12, model_concurrency=1)
    executor = ExecutionRuntime(limits)
    release, entered, exited = Event(), Event(), Event()
    effects = []
    def blocked():
        effects.append('first_dispatched')
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError('Harness failed to release capacity holder')
            return 'late'
        finally:
            exited.set()
    first = RunContext(limits, executor)
    try:
        _, error = _capture_call(first, lambda: runtime_call('model', 'harness.capacity_holder', blocked, run=first))
        case.check('first_wait_times_out', isinstance(error, CallTimeout))
        case.check('first_worker_really_occupies_gate', entered.is_set() and not exited.is_set())
        case.capture('capacity_holder', first)
        queued = RunContext(limits, executor)
        _, error = _capture_call(queued, lambda: runtime_call('model', 'harness.queued',
            lambda: effects.append('unexpected_queued_dispatch'), run=queued))
        case.check('second_request_queue_times_out', isinstance(error, CallTimeout))
        case.check('timed_out_worker_keeps_capacity_lease', effects, ['first_dispatched'])
        case.check('queue_rejection_reserves_no_model_budget', queued.counts['model'], 0)
        case.check('queued_trace_has_no_start_event', any(
            event['event'] == 'call_started' for event in queued.events), False)
        case.capture('queue_timeout', queued)
    finally:
        release.set()
        if not exited.wait(2):
            raise AssertionError('Capacity holder did not exit')
    recovered = RunContext(replace(limits, model_seconds=1), executor)
    result, error = _capture_call(recovered, lambda: runtime_call(
        'model', 'harness.capacity_recovered', lambda: 'normal', run=recovered))
    if error is None:
        recovered.complete()
    case.check('gate_is_reusable_after_actual_worker_exit', error is None and result == 'normal')
    case.check('recovered_dispatch_reserves_one_attempt', recovered.counts['model'], 1)
    case.capture('normal_control', recovered)


SCENARIOS = (
    ('F01', '模型阻塞与迟到回答', _model_blocked),
    ('F02', '工具阻塞与终止传播', _tool_blocked),
    ('F03', '连续瞬态失败与熔断隔离', _continuous_failures),
    ('F04', '半开单探测与成功恢复', _half_open_recovery),
    ('F05', '无限工具循环与调用预算', _infinite_loop),
    ('F06', '取消后迟到结果不得提交', _cancel_late_commit),
    ('F07', '名额占满与排队超时', _capacity_queue),
)


def run_faults():
    """Return independently scored rows; unexpected errors fail that scenario."""
    rows = []
    for case_id, title, operation in SCENARIOS:
        case = Scenario(case_id, title)
        error = None
        try:
            operation(case)
        except Exception as exc:
            error = exc
        rows.append(case.finish(error))
    return rows
