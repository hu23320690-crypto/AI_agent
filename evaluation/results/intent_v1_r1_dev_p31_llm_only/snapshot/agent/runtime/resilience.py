"""Single retry owner at dependency leaves; process-local circuit breakers."""
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path
import random
from threading import Event, RLock
import time

import httpx
from ollama import ResponseError

from .core import RuntimeControlError, CallTimeout, current_run, runtime_call


class CircuitOpen(RuntimeControlError):
    def __init__(self):
        super().__init__('相关依赖暂不可用，已进入熔断保护，请稍后重试。')


class DependencyUnavailable(RuntimeControlError):
    pass


@dataclass(frozen=True)
class ResiliencePolicy:
    max_attempts: int = 2  # includes the first request
    base_delay_seconds: float = .5
    max_delay_seconds: float = 2
    minimum_samples: int = 3
    failure_threshold: int = 3
    window_seconds: float = 60
    recovery_seconds: float = 15

    def __post_init__(self):
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'resilience.{name} must be finite and positive')
            if not name.endswith('_seconds') and not isinstance(value, int):
                raise ValueError(f'resilience.{name} must be an integer')
        if self.max_attempts > 5:
            raise ValueError('resilience.max_attempts must be at most 5')
        if self.base_delay_seconds > self.max_delay_seconds:
            raise ValueError('base delay must not exceed max delay')


@lru_cache(maxsize=1)
def load_resilience_policy():
    import yaml
    path = Path(__file__).resolve().parents[2] / 'config/resilience.yml'
    return ResiliencePolicy(**yaml.safe_load(path.read_text(encoding='utf-8')))


def dependency_key(model, channel):
    # Endpoint credentials/URLs are hashed, never written to the run trace.
    endpoint = getattr(model, 'base_url', None) or os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
    model_name = getattr(model, 'model', None) or type(model).__qualname__
    identity = f'{endpoint}|{model_name}'
    return f'{channel}:{hashlib.sha256(identity.encode()).hexdigest()[:16]}'


def transient_error(exc):
    if isinstance(exc, RuntimeControlError):
        return False
    if isinstance(exc, (httpx.HTTPStatusError, ResponseError)):
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else exc.status_code
        return status in {408, 429, 500, 502, 503, 504}
    # Local pool saturation / configuration / validation errors are not outages.
    return isinstance(exc, (ConnectionError, TimeoutError, httpx.ConnectError,
                           httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError,
                           httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout))


def retry_after_seconds(exc):
    # Ollama ResponseError currently drops headers; never invent Retry-After.
    if not isinstance(exc, httpx.HTTPStatusError):
        return 0.0
    value = exc.response.headers.get('Retry-After', '')
    try:
        delay = float(value)
        return max(0.0, delay) if math.isfinite(delay) else 0.0
    except ValueError:
        try:
            at = parsedate_to_datetime(value)
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            return max(0.0, (at-datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0.0


@dataclass
class Permit:
    epoch: int
    probe: bool
    used: bool = False


class CircuitBreaker:
    def __init__(self, dependency, policy, clock=time.monotonic):
        self.dependency, self.policy, self.clock = dependency, policy, clock
        self.state = 'CLOSED'
        self.epoch = 0
        self.opened_at = 0.0
        self.probe_active = False
        self.samples = deque()
        self.lock = RLock()

    def _trim(self):
        cutoff = self.clock() - self.policy.window_seconds
        while self.samples and self.samples[0][0] <= cutoff:
            self.samples.popleft()

    def _transition(self, state, run):
        previous = self.state
        self.state = state
        self.epoch += 1  # ignores late completions from an older circuit state
        self.probe_active = False
        self.samples.clear()
        if state == 'OPEN':
            self.opened_at = self.clock()
        if run is not None:
            run.note('circuit_transition', dependency=self.dependency, previous=previous, state=state)

    def acquire(self, run=None):
        with self.lock:
            if self.state == 'OPEN':
                if self.clock()-self.opened_at < self.policy.recovery_seconds:
                    raise CircuitOpen()
                self._transition('HALF_OPEN', run)
            if self.state == 'HALF_OPEN':
                if self.probe_active:
                    raise CircuitOpen()
                self.probe_active = True
            return Permit(self.epoch, self.state == 'HALF_OPEN')

    def validate(self, permit):
        with self.lock:
            # The caller may have waited for capacity while another call tripped.
            if permit.used or permit.epoch != self.epoch:
                raise CircuitOpen()

    def record(self, permit, outcome, run=None):
        with self.lock:
            if permit.used:
                return
            permit.used = True
            if permit.epoch != self.epoch:
                return
            if permit.probe:
                self.probe_active = False
                if outcome == 'success':
                    self._transition('CLOSED', run)
                elif outcome == 'failure':
                    self._transition('OPEN', run)
                # Neutral cancellation/invalid input releases the probe only.
                return
            if outcome == 'neutral':
                return
            self._trim()
            self.samples.append((self.clock(), outcome == 'failure'))
            if len(self.samples) >= self.policy.minimum_samples and sum(f for _, f in self.samples) >= self.policy.failure_threshold:
                self._transition('OPEN', run)

    def snapshot(self):
        with self.lock:
            self._trim()
            return {'state': self.state, 'samples': len(self.samples),
                    'failures': sum(f for _, f in self.samples), 'probe_active': self.probe_active}


_inside_dependency = ContextVar('inside_dependency', default=False)


class ResilienceController:
    def __init__(self, policy=None, *, clock=time.monotonic, sleeper=time.sleep, jitter=random.uniform):
        self.policy = policy or load_resilience_policy()
        self.clock, self.sleeper, self.jitter = clock, sleeper, jitter
        self.breakers = {}
        self.lock = RLock()

    def breaker(self, dependency):
        with self.lock:
            if dependency not in self.breakers:
                self.breakers[dependency] = CircuitBreaker(dependency, self.policy, self.clock)
            return self.breakers[dependency]

    def _backoff(self, run, delay, until):
        run.check()
        if run.clock()+delay >= min(until, run.deadline):
            raise DependencyUnavailable('剩余时间不足以等待依赖重试，本轮已停止。')
        target = run.clock()+delay
        while run.clock() < target:
            run.check()
            self.sleeper(min(.02, target-run.clock()))
        run.check()

    def call(self, run, kind, name, operation, *, dependency, retry_safe=False):
        if _inside_dependency.get():
            raise RuntimeControlError('依赖重试入口不能嵌套，请仅包装最底层请求。')
        if kind not in {'model', 'embedding', 'tool'}:
            raise ValueError('Only dependency leaves may retry')
        run.check()
        until = min(run.deadline, run.clock()+getattr(run.limits, f'{kind}_seconds'))
        breaker = self.breaker(dependency)
        attempts = self.policy.max_attempts if retry_safe else 1
        for attempt in range(1, attempts+1):
            run.check_budget(kind)
            try:
                permit = breaker.acquire(run)
            except CircuitOpen:
                run.note('circuit_rejected', dependency=dependency)
                raise
            started = Event()

            def invoke():
                breaker.validate(permit)
                run.check()
                token = _inside_dependency.set(True)
                started.set()
                try:
                    return operation()
                finally:
                    _inside_dependency.reset(token)

            try:
                result = runtime_call(kind, name, invoke, run=run, deadline=until)
            except BaseException as exc:
                transient = started.is_set() and transient_error(exc)
                # A local per-call wait timeout is terminal; count a dispatched
                # leaf failure but never overlap it with another retry.
                timed_out_leaf = isinstance(exc, CallTimeout) and exc.kind == kind and started.is_set()
                breaker.record(permit, 'failure' if transient or timed_out_leaf else 'neutral', run)
                if isinstance(exc, RuntimeControlError) or not transient:
                    raise
                run.note('dependency_failed', dependency=dependency, attempt=attempt,
                         error_type=type(exc).__name__)
                if attempt == attempts or permit.probe:
                    raise DependencyUnavailable('相关依赖请求失败，本轮已停止，请稍后重试。') from exc
                # No sleep or retry once this/another request has opened it.
                if breaker.snapshot()['state'] == 'OPEN':
                    run.note('circuit_rejected', dependency=dependency)
                    raise CircuitOpen() from exc
                run.check_budget(kind)
                cap = min(self.policy.max_delay_seconds, self.policy.base_delay_seconds * 2**(attempt-1))
                delay = max(self.jitter(0, cap), retry_after_seconds(exc))
                run.note('retry_scheduled', dependency=dependency, next_attempt=attempt+1,
                         delay_seconds=round(delay, 6))
                self._backoff(run, delay, until)
            else:
                breaker.record(permit, 'success', run)
                return result


def dependency_call(kind, name, operation, *, dependency, run=None, retry_safe=False):
    context = run or current_run()
    if context is None:
        # Offline index administration and direct low-level eval stay single-shot.
        return operation()
    try:
        return context.executor.resilience.call(context, kind, name, operation,
                                                dependency=dependency, retry_safe=retry_safe)
    except RuntimeControlError as exc:
        # Publish the terminal decision immediately, so sibling tool waits and
        # the root caller stop even if the graph is still joining other workers.
        raise context.fail(exc)


def optional_model_call(name, operation, *, run, dependency, seconds=10):
    """One optional summary attempt, sharing budgets, gates and circuit state.

    Only this attempt's local wait timeout is recoverable. Parent cancellation,
    total deadline and call-budget exhaustion remain terminal. No retry can
    overlap a late summary worker.
    """
    if _inside_dependency.get():
        raise RuntimeControlError('可选摘要必须在主模型请求之前执行。')
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Optional model timeout must be finite and positive')
    run.check_budget('model')
    until = min(run.deadline, run.clock() + seconds)
    breaker = run.executor.resilience.breaker(dependency)
    permit = breaker.acquire(run)
    started = Event()

    def invoke():
        breaker.validate(permit)
        run.check()
        token = _inside_dependency.set(True)
        started.set()
        try:
            return operation()
        finally:
            _inside_dependency.reset(token)

    try:
        result = runtime_call('model', name, invoke, run=run, deadline=until,
                              timeout_is_terminal=False)
    except BaseException as exc:
        failure = started.is_set() and (transient_error(exc) or
                                       isinstance(exc, CallTimeout) and exc.kind == 'model')
        breaker.record(permit, 'failure' if failure else 'neutral', run)
        raise
    else:
        breaker.record(permit, 'success', run)
        return result
