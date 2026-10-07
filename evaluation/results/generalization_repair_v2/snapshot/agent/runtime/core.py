"""Bounded waiting for synchronous integrations; this does NOT kill threads.

One context owns the deadline and all nested budgets. Workers retain their
capacity lease until they actually exit, even when their caller stops waiting.
Separate gates for nested stages avoid exhausting a single recursive pool.
"""
from __future__ import annotations

from collections import Counter
from contextlib import nullcontext
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, fields
from functools import lru_cache
import math
from pathlib import Path
from threading import BoundedSemaphore, Event, RLock, Thread
import time
from uuid import uuid4


class RuntimeControlError(RuntimeError):
    """Terminal run control, never convert this into a retryable tool result."""


class DeadlineExceeded(RuntimeControlError):
    pass


class CallTimeout(RuntimeControlError):
    def __init__(self, message, *, kind=None):
        super().__init__(message)
        self.kind = kind


class BudgetExceeded(RuntimeControlError):
    pass


class RunCancelled(RuntimeControlError):
    pass


class RunBusy(RuntimeControlError):
    pass


@dataclass(frozen=True)
class RunLimits:
    total_seconds: float = 120
    model_seconds: float = 90
    tool_seconds: float = 110
    retrieval_seconds: float = 100
    embedding_seconds: float = 90
    max_model_calls: int = 8
    max_tool_calls: int = 12
    max_embedding_calls: int = 16
    max_query_chars: int = 8000
    max_output_chars: int = 16000
    max_tool_args_chars: int = 4000
    max_commit_checks: int = 2048
    run_concurrency: int = 2
    model_concurrency: int = 2
    tool_concurrency: int = 4
    retrieval_concurrency: int = 2
    embedding_concurrency: int = 2

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"runtime.{field.name} must be a finite positive number")
            if not field.name.endswith('_seconds') and not isinstance(value, int):
                raise ValueError(f"runtime.{field.name} must be an integer")


@lru_cache(maxsize=1)
def load_limits():
    import yaml
    path = Path(__file__).resolve().parents[2] / 'config/runtime.yml'
    return RunLimits(**yaml.safe_load(path.read_text(encoding='utf-8')))


_active: ContextVar[RunContext | None] = ContextVar('agent_run', default=None)


def current_run():
    return _active.get()


class RunContext:
    def __init__(self, limits=None, executor=None, *, clock=time.monotonic):
        self.limits = limits or load_limits()
        self.executor = executor or default_runtime()
        self.clock = clock
        self.run_id = uuid4().hex
        self.started = clock()
        self.deadline = self.started + self.limits.total_seconds
        self.status = 'running'
        self.error = None
        self.counts = Counter()
        self.events = []
        self._commit_checks = []
        self._commit_check_keys = set()
        self.lock = RLock()
        self.note('run_started')

    def note(self, event, **details):
        with self.lock:
            if len(self.events) < 256:
                self.events.append({'event': event, 'seconds': round(self.clock()-self.started, 6), **details})

    def fail(self, error, status='failed'):
        with self.lock:
            if self.status == 'running':
                self.status, self.error = status, error
                self.note('run_finished', status=status, error_type=type(error).__name__)
            return self.error or error

    def check(self):
        with self.lock:
            if self.error is not None:
                raise self.error
            if self.status != 'running':
                raise RunCancelled('本轮已经结束。')
            if self.clock() >= self.deadline:
                raise self.fail(DeadlineExceeded('本轮已超过总时间预算，请缩小问题范围后重试。'), 'timed_out')

    def cancel(self):
        self.fail(RunCancelled('本轮已取消，未提交回答。'), 'cancelled')

    def check_budget(self, kind):
        with self.lock:
            self.check()
            maximum = getattr(self.limits, f'max_{kind}_calls', None)
            if maximum is not None and self.counts[kind] >= maximum:
                raise self.fail(BudgetExceeded(f'本轮 {kind} 调用次数已达到上限，请简化问题后重试。'))

    def reserve(self, kind):
        with self.lock:
            self.check_budget(kind)
            self.counts[kind] += 1

    def check_size(self, text, maximum, label):
        self.check()
        if len(text) > maximum:
            raise self.fail(BudgetExceeded(f'{label}超过本轮长度限制。'))

    def add_commit_check(self, check):
        """Trusted application checks, never supplied by model arguments."""
        with self.lock:
            self.check()
            key = getattr(check, 'evidence_key', None)
            if key is not None:
                if key in self._commit_check_keys:
                    return
            if len(self._commit_checks) >= self.limits.max_commit_checks:
                raise self.fail(BudgetExceeded('会话来源依赖已达到上限，请清空会话后重试。'))
            if key is not None:
                self._commit_check_keys.add(key)
            self._commit_checks.append(check)

    def get_commit_checks(self):
        with self.lock:
            return tuple(self._commit_checks)

    def validate_commit_checks(self):
        with self.lock:
            self.check()
            checks = tuple(self._commit_checks)
        # File I/O must not hold the lock used by deadline/cancel checks.
        for check in checks:
            self.check()
            check()
            self.check()

    def complete(self, *, commit=None, commit_lock=None):
        if self.get_commit_checks():
            runtime_call('retrieval', 'run.commit_validation', self.validate_commit_checks, run=self)
        with commit_lock if commit_lock is not None else nullcontext():
            with self.lock:
                self.check()
                if commit is not None:
                    commit()
                self.status = 'succeeded'
                self.note('run_finished', status=self.status)

    def snapshot(self):
        with self.lock:
            return {'run_id': self.run_id, 'status': self.status,
                    'seconds': round(self.clock()-self.started, 6),
                    'counts': dict(self.counts),
                    'error_type': type(self.error).__name__ if self.error else None,
                    'events': [dict(event) for event in self.events]}


class ExecutionRuntime:
    def __init__(self, limits=None, *, resilience=None):
        from .resilience import ResilienceController
        limits = limits or load_limits()
        self.resilience = resilience or ResilienceController()
        self.gates = {kind: BoundedSemaphore(getattr(limits, f'{kind}_concurrency'))
                      for kind in ('run', 'model', 'tool', 'retrieval', 'embedding')}

    def call(self, run, kind, name, operation, *, deadline=None, timeout_is_terminal=True):
        run.check()
        call_id = uuid4().hex
        limit = getattr(run.limits, f'{kind}_seconds', run.limits.total_seconds)
        until = min(run.deadline, run.clock() + limit)
        if deadline is not None:
            until = min(until, deadline)

        def check_wait():
            run.check()
            if run.clock() >= until:
                error = CallTimeout(f'{kind} 调用或排队超时。', kind=kind)
                if timeout_is_terminal:
                    raise run.fail(error, 'timed_out')
                # Optional work may stop waiting without poisoning the parent
                # turn. Its worker still owns capacity until it actually exits.
                raise error

        gate = self.gates[kind]
        run.note('call_queued', kind=kind, name=name, call_id=call_id)
        while True:
            check_wait()
            if gate.acquire(timeout=min(.02, max(0, until-run.clock()))):
                break
        try:
            check_wait()
            run.reserve(kind)
        except BaseException:
            gate.release()
            raise
        done = Event()
        box = {}
        inherited = copy_context()

        def work():
            token = _active.set(run)
            try:
                check_wait()
                run.note('call_started', kind=kind, name=name, call_id=call_id)
                box['result'] = operation()
                check_wait()
                run.note('call_finished', kind=kind, name=name, call_id=call_id)
            except BaseException as exc:
                box['error'] = exc
                run.note('call_failed', kind=kind, name=name, call_id=call_id,
                         error_type=type(exc).__name__)
            finally:
                _active.reset(token)
                gate.release()
                done.set()

        worker = Thread(target=lambda: inherited.run(work), name=f'agent-{kind}-{call_id[:8]}', daemon=True)
        try:
            worker.start()
        except BaseException:
            gate.release()
            raise
        while not done.wait(timeout=min(.02, max(0, until-run.clock()))):
            check_wait()
        check_wait()
        if 'error' in box:
            raise box['error']
        return box['result']


@lru_cache(maxsize=1)
def default_runtime():
    return ExecutionRuntime()


def runtime_call(kind, name, operation, *, run=None, deadline=None, timeout_is_terminal=True):
    context = run or current_run()
    # Index administration / legacy low-level evaluation has no request context.
    if context is None:
        return operation()
    return context.executor.call(context, kind, name, operation, deadline=deadline,
                                 timeout_is_terminal=timeout_is_terminal)
