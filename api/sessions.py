"""Event-loop-owned registry with bounded executor admission and sticky cancellation."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import time
from uuid import uuid4

from agent.runtime import RunContext, default_runtime, load_limits

log = logging.getLogger('agent.api')


class ServiceError(Exception):
    def __init__(self, code, message, status, *, retry_after=None):
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after
        super().__init__(message)


@dataclass
class Session:
    session_id: str
    user_id: str
    city: str
    touched: float
    agent: object = None
    job: Job | None = None


@dataclass
class Job:
    run: RunContext
    task: asyncio.Future


def production_agent(*, user_id, city, limits, executor):
    # Import/model metadata validation may block: only run inside the worker.
    from agent.react_agent import ReactAgent
    return ReactAgent(user_id=user_id, city=city, limits=limits, executor=executor)


class SessionManager:
    def __init__(self, settings, *, factory=production_agent, limits=None, executor=None, clock=time.monotonic):
        self.settings, self.factory, self.clock = settings, factory, clock
        self.limits = limits or load_limits()
        self.executor = executor or default_runtime()
        self.pool = ThreadPoolExecutor(max_workers=settings.max_concurrent, thread_name_prefix='api-agent')
        self.sessions = {}
        self.jobs = set()
        self.closing = False
        self._reaper = None

    def start(self):
        self._reaper = asyncio.create_task(self._expire_loop(), name='api-session-expiry')

    def expire(self):
        now = self.clock()
        for key, session in list(self.sessions.items()):
            if session.job is None and now-session.touched >= self.settings.session_ttl_seconds:
                del self.sessions[key]

    async def _expire_loop(self):
        while True:
            await asyncio.sleep(min(30, self.settings.session_ttl_seconds))
            self.expire()

    def create(self, user_id, city):
        self.expire()
        if self.closing:
            raise ServiceError('service_closing', '服务正在关闭。', 503)
        if len(self.sessions) >= self.settings.max_sessions:
            raise ServiceError('session_capacity', '会话容量已满，请删除旧会话或稍后重试。', 429, retry_after=1)
        session = Session(uuid4().hex, user_id, city, self.clock())
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id):
        self.expire()
        if session_id not in self.sessions:
            raise ServiceError('session_not_found', '会话不存在或已过期。', 404)
        return self.sessions[session_id]

    def submit(self, session_id, query):
        session = self.get(session_id)
        if self.closing:
            raise ServiceError('service_closing', '服务正在关闭。', 503)
        if session.job is not None:
            raise ServiceError('session_busy', '当前会话已有请求运行。', 409)
        if len(self.jobs) >= self.settings.max_concurrent:
            raise ServiceError('service_busy', '服务容量已满，请稍后重试。', 429, retry_after=1)
        # No await between admission and registration. The event loop serializes it.
        run = RunContext(self.limits, self.executor)
        if len(query) > self.limits.max_query_chars:
            raise ServiceError('query_too_long', '问题超过长度上限。', 422)
        loop = asyncio.get_running_loop()

        def execute():
            try:
                run.check()
                if session.agent is None:
                    session.agent = self.factory(user_id=session.user_id, city=session.city,
                                                 limits=self.limits, executor=self.executor)
                run.check()
                answers = list(session.agent.execute_stream(query, run_context=run))
                if not answers or run.snapshot()['status'] != 'succeeded':
                    raise RuntimeError('Agent did not complete the supplied run')
                return ''.join(answers)
            except BaseException as exc:
                run.fail(exc)
                raise

        try:
            future = loop.run_in_executor(self.pool, execute)
        except BaseException as exc:
            run.fail(exc)
            raise
        session.job = Job(run, future)
        session.touched = self.clock()
        self.jobs.add(future)

        def finished(task):
            # Runs only when the real executor future finishes; never cancel it.
            self.jobs.discard(task)
            if session.job is not None and session.job.task is task:
                session.job = None
                session.touched = self.clock()
            try:
                task.exception()  # Consume exceptions even when HTTP stopped waiting.
            except asyncio.CancelledError:
                pass
            snapshot = run.snapshot()
            log.info('agent_run run_id=%s status=%s seconds=%s counts=%s',
                     snapshot['run_id'], snapshot['status'], snapshot['seconds'], snapshot['counts'])
        future.add_done_callback(finished)
        return session.job

    def cancel(self, session_id):
        session = self.get(session_id)
        if session.job is None:
            return False
        session.job.run.cancel()
        return True

    def delete(self, session_id):
        session = self.get(session_id)
        if session.job is not None:
            session.job.run.cancel()
        del self.sessions[session_id]
        # Worker references this object only. Its callback never reinserts it.

    async def close(self):
        self.closing = True
        if self._reaper is not None:
            self._reaper.cancel()
            await asyncio.gather(self._reaper, return_exceptions=True)
        for session in self.sessions.values():
            if session.job is not None:
                session.job.run.cancel()
        if self.jobs:
            await asyncio.wait(tuple(self.jobs), timeout=self.settings.shutdown_seconds)
        self.pool.shutdown(wait=False, cancel_futures=False)
        self.sessions.clear()
