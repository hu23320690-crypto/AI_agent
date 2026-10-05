"""Offline ASGI and lifecycle checks; no Ollama, Docker or live credentials.

Async scenarios use asyncio.run rather than a pytest asyncio plugin. Workers are
real threads so timeout/cancel tests exercise admission until actual completion.
ASGITransport does not simulate a TCP disconnect; disconnect handling is tested
explicitly with a fake Request and a real manager job.
"""
import asyncio
from contextlib import asynccontextmanager
import threading
import time

import httpx
import pytest

from agent.runtime import ExecutionRuntime, RunCancelled, RunLimits
from api.app import create_app, wait_answer
from api.readiness import ReadinessProbe
from api.sessions import ServiceError, SessionManager
from api.settings import APISettings


KEY = "offline-api-tests-" + "x" * 32
AUTH = {"Authorization": "Bearer " + KEY}


def settings(**changes):
    return APISettings(api_key=KEY, shutdown_seconds=.05, **changes)


class FakeAgent:
    def __init__(self, *, user_id, city, **_):
        self.user_id, self.city = user_id, city
        self.history = []

    def execute_stream(self, query, *, run_context):
        run_context.check()
        answer = f"{self.user_id}|{self.city}|{len(self.history)}|{query}"
        run_context.complete(commit=lambda: self.history.append(query))
        yield answer


class BlockingAgent(FakeAgent):
    def __init__(self, *, entered, release, exited, **kwargs):
        super().__init__(**kwargs)
        self.entered, self.release, self.exited = entered, release, exited

    def execute_stream(self, query, *, run_context):
        self.entered.set()
        try:
            if not self.release.wait(3):
                raise AssertionError("test must release its worker")
            yield from super().execute_stream(query, run_context=run_context)
        finally:
            self.exited.set()


class BlockingFactory:
    def __init__(self):
        self.entered, self.release, self.exited = (threading.Event() for _ in range(3))
        self.agents = []

    def __call__(self, **kwargs):
        agent = BlockingAgent(entered=self.entered, release=self.release,
                              exited=self.exited, **kwargs)
        self.agents.append(agent)
        return agent


class Probe:
    def __init__(self, ready=True):
        self.ready, self.closed, self.calls = ready, False, 0

    async def __call__(self):
        self.calls += 1
        return {"ready": self.ready, **({} if self.ready else {"reason": "models_missing"})}

    async def close(self):
        self.closed = True


@asynccontextmanager
async def service(*, config=None, factory=FakeAgent, probe=None, limits=None):
    run_limits = limits or RunLimits()
    app = create_app(settings=config or settings(), agent_factory=factory,
                     readiness=probe or Probe(), limits=run_limits,
                     executor=ExecutionRuntime(run_limits))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url="http://test") as client:
            yield app, client


async def session(client, **values):
    response = await client.post("/v1/sessions", json=values, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


async def entered(event):
    until = time.monotonic() + 2
    while not event.is_set():
        assert time.monotonic() < until, "worker did not reach its controlled blocking point"
        await asyncio.sleep(.005)


async def drained(manager):
    until = time.monotonic() + 2
    while manager.jobs:
        assert time.monotonic() < until, "finished worker did not release admission"
        await asyncio.sleep(.005)


def error_code(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.headers["x-request-id"] == response.json()["request_id"]


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"},
                                     {"Authorization": "Basic " + KEY},
                                     [("Authorization", "Bearer " + KEY),
                                      ("Authorization", "Bearer " + KEY)]])
def test_bearer_required_and_duplicate_authorization_rejected(headers):
    async def scenario():
        async with service() as (_, client):
            response = await client.post("/v1/sessions", json={}, headers=headers)
            error_code(response, 401, "unauthorized")
            assert response.headers["www-authenticate"] == "Bearer"
            assert KEY not in response.text
            assert (await client.get("/healthz")).status_code == 200
    asyncio.run(scenario())


def test_readiness_is_authenticated_and_reports_dependency_state():
    async def scenario():
        probe = Probe(False)
        async with service(probe=probe) as (_, client):
            error_code(await client.get("/readyz"), 401, "unauthorized")
            assert probe.calls == 0
            unavailable = await client.get("/readyz", headers=AUTH)
            assert unavailable.status_code == 503
            assert unavailable.json() == {"ready": False, "reason": "models_missing"}
            probe.ready = True
            assert (await client.get("/readyz", headers=AUTH)).json() == {"ready": True}
            schema = (await client.get("/openapi.json")).json()
            assert schema["paths"]["/v1/sessions"]["post"]["security"] == [{"APIKey": []}]
            assert "security" not in schema["paths"]["/healthz"]["get"]
            assert KEY not in str(schema)
        assert probe.closed
    asyncio.run(scenario())


def test_concurrent_readiness_calls_share_one_probe_and_cache_its_result():
    async def scenario():
        probe = ReadinessProbe()
        gate, calls = asyncio.Event(), []
        async def check():
            calls.append(True)
            await gate.wait()
            return {"ready": True}
        probe._check = check
        requests = [asyncio.create_task(probe()) for _ in range(8)]
        try:
            await asyncio.sleep(.01)
            assert len(calls) == 1
            gate.set()
            assert await asyncio.gather(*requests) == [{"ready": True}] * 8
            assert probe.task is None
            assert await probe() == {"ready": True}
            assert len(calls) == 1
        finally:
            gate.set()
            await probe.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("body", [{"query": ""}, {"query": " "}, {"query": "x" * 8001},
                                  {"query": "safe", "user_id": "internal-secret-user"},
                                  {"query": "safe", "runtime": {"max_model_calls": 999}},
                                  {"query": "safe", "city": "internal-secret-city"}])
def test_message_schema_forbids_internal_overrides_without_echoing_inputs(body):
    async def scenario():
        async with service() as (_, client):
            sid = await session(client, user_id="1001", city="上海")
            response = await client.post(f"/v1/sessions/{sid}/messages", json=body, headers=AUTH)
            error_code(response, 422, "invalid_request")
            assert "internal-secret" not in response.text
            assert "max_model_calls" not in response.text
            assert "x" * 100 not in response.text
    asyncio.run(scenario())


def test_session_schema_and_invalid_json_have_sanitized_errors():
    async def scenario():
        async with service() as (_, client):
            extra = await client.post("/v1/sessions", json={"api_key": "rejected-secret"}, headers=AUTH)
            error_code(extra, 422, "invalid_request")
            assert "rejected-secret" not in extra.text
            bad_json = await client.post("/v1/sessions", content=b'{"secret":"rejected-secret"',
                                         headers={**AUTH, "Content-Type": "application/json"})
            error_code(bad_json, 422, "invalid_request")
            assert "rejected-secret" not in bad_json.text
    asyncio.run(scenario())


@pytest.mark.parametrize("header", [None, "1"])
def test_actual_stream_body_cap_ignores_absent_or_underreported_content_length(header):
    async def scenario():
        async with service(config=settings(max_body_bytes=64)) as (_, client):
            async def chunks():
                yield b"{" + b" " * 40
                yield b" " * 40 + b"}"
            headers = {**AUTH, "Content-Type": "application/json"}
            if header is not None:
                headers["Content-Length"] = header
            response = await client.post("/v1/sessions", content=chunks(), headers=headers)
            error_code(response, 413, "body_too_large")
            if header is None:
                assert "content-length" not in response.request.headers
    asyncio.run(scenario())


def test_session_identity_and_history_are_isolated_and_factory_is_lazy():
    async def scenario():
        created = []
        def factory(**kwargs):
            created.append(FakeAgent(**kwargs))
            return created[-1]
        async with service(factory=factory) as (_, client):
            first = await session(client, user_id="1001", city="上海")
            second = await session(client, user_id="1002", city="北京")
            assert first != second and created == []
            async def ask(sid, query):
                response = await client.post(f"/v1/sessions/{sid}/messages", json={"query": query}, headers=AUTH)
                assert response.status_code == 200, response.text
                assert response.json()["status"] == "succeeded"
                assert response.json()["session_id"] == sid
                return response.json()
            one = await ask(first, "first-user-secret")
            two = await ask(second, "second-user-secret")
            next_one = await ask(first, "followup")
            assert one["answer"] == "1001|上海|0|first-user-secret"
            assert two["answer"] == "1002|北京|0|second-user-secret"
            assert next_one["answer"] == "1001|上海|1|followup"
            assert len({one["run_id"], two["run_id"], next_one["run_id"]}) == 3
            assert created[0].history == ["first-user-secret", "followup"]
            assert created[1].history == ["second-user-secret"]
    asyncio.run(scenario())


def test_not_found_idle_cancel_delete_and_session_capacity():
    async def scenario():
        async with service(config=settings(max_sessions=1)) as (_, client):
            error_code(await client.post("/v1/sessions/missing/messages", json={"query": "x"}, headers=AUTH),
                       404, "session_not_found")
            sid = await session(client)
            response = await client.post("/v1/sessions", json={}, headers=AUTH)
            error_code(response, 429, "session_capacity")
            assert response.headers["retry-after"] == "1"
            assert (await client.post(f"/v1/sessions/{sid}/cancel", headers=AUTH)).json() == {"cancelled": False}
            assert (await client.delete(f"/v1/sessions/{sid}", headers=AUTH)).status_code == 204
            error_code(await client.post(f"/v1/sessions/{sid}/cancel", headers=AUTH), 404, "session_not_found")
            await session(client)
    asyncio.run(scenario())


def test_idle_sessions_expire_without_model_calls():
    async def scenario():
        async with service(config=settings(max_sessions=1, session_ttl_seconds=10)) as (app, client):
            clock = [100.0]
            app.state.manager.clock = lambda: clock[0]
            sid = await session(client)
            clock[0] += 10
            error_code(await client.post(f"/v1/sessions/{sid}/cancel", headers=AUTH), 404, "session_not_found")
            await session(client)
    asyncio.run(scenario())


def test_same_session_conflicts_global_capacity_is_bounded_and_health_stays_responsive():
    async def scenario():
        factory = BlockingFactory()
        async with service(config=settings(max_concurrent=1), factory=factory) as (app, client):
            first, second = await session(client), await session(client)
            pending = asyncio.create_task(client.post(f"/v1/sessions/{first}/messages",
                                                       json={"query": "blocked"}, headers=AUTH))
            try:
                await entered(factory.entered)
                error_code(await client.post(f"/v1/sessions/{first}/messages", json={"query": "again"}, headers=AUTH),
                           409, "session_busy")
                busy = await client.post(f"/v1/sessions/{second}/messages", json={"query": "other"}, headers=AUTH)
                error_code(busy, 429, "service_busy")
                assert busy.headers["retry-after"] == "1"
                health = await asyncio.wait_for(client.get("/healthz"), timeout=.5)
                assert health.status_code == 200
                assert len(app.state.manager.jobs) == 1
            finally:
                factory.release.set()
                response = await pending
            assert response.status_code == 200
            await drained(app.state.manager)
    asyncio.run(scenario())


def test_cancel_keeps_admission_until_worker_exits_and_prevents_history_commit():
    async def scenario():
        factory = BlockingFactory()
        async with service(config=settings(max_concurrent=1), factory=factory) as (app, client):
            first, second = await session(client), await session(client)
            pending = asyncio.create_task(client.post(f"/v1/sessions/{first}/messages",
                                                       json={"query": "cancel me"}, headers=AUTH))
            try:
                await entered(factory.entered)
                assert (await client.post(f"/v1/sessions/{first}/cancel", headers=AUTH)).json() == {"cancelled": True}
                error_code(await client.post(f"/v1/sessions/{second}/messages", json={"query": "early"}, headers=AUTH),
                           429, "service_busy")
                assert len(app.state.manager.jobs) == 1
                assert factory.agents[0].history == []
            finally:
                factory.release.set()
                response = await pending
            error_code(response, 409, "run_cancelled")
            await drained(app.state.manager)
            assert factory.agents[0].history == []
            next_response = await client.post(f"/v1/sessions/{second}/messages", json={"query": "now"}, headers=AUTH)
            assert next_response.status_code == 200
    asyncio.run(scenario())


def test_http_wait_timeout_cancels_run_but_keeps_real_worker_capacity():
    async def scenario():
        factory = BlockingFactory()
        async with service(config=settings(max_concurrent=1, request_timeout_seconds=.05), factory=factory) as (app, client):
            first, second = await session(client), await session(client)
            pending = asyncio.create_task(client.post(f"/v1/sessions/{first}/messages", json={"query": "late"}, headers=AUTH))
            try:
                await entered(factory.entered)
                response = await pending
                error_code(response, 504, "request_timeout")
                job = app.state.manager.sessions[first].job
                assert job.run.snapshot()["status"] == "cancelled"
                assert not job.task.done() and len(app.state.manager.jobs) == 1
                error_code(await client.post(f"/v1/sessions/{second}/messages", json={"query": "early"}, headers=AUTH),
                           429, "service_busy")
            finally:
                factory.release.set()
                await drained(app.state.manager)
            assert factory.agents[0].history == []
    asyncio.run(scenario())


def test_deleting_busy_session_never_reinserts_it_or_releases_worker_early():
    async def scenario():
        factory = BlockingFactory()
        async with service(config=settings(max_concurrent=1, session_ttl_seconds=10), factory=factory) as (app, client):
            sid, second = await session(client), await session(client)
            pending = asyncio.create_task(client.post(f"/v1/sessions/{sid}/messages", json={"query": "late"}, headers=AUTH))
            try:
                await entered(factory.entered)
                # Expiry must leave an active request available for cancellation.
                record = app.state.manager.sessions[sid]
                record.touched -= 11
                app.state.manager.expire()
                assert sid in app.state.manager.sessions
                assert (await client.delete(f"/v1/sessions/{sid}", headers=AUTH)).status_code == 204
                assert sid not in app.state.manager.sessions
                error_code(await client.post(f"/v1/sessions/{second}/messages", json={"query": "early"}, headers=AUTH),
                           429, "service_busy")
            finally:
                factory.release.set()
                response = await pending
            error_code(response, 409, "run_cancelled")
            await drained(app.state.manager)
            assert sid not in app.state.manager.sessions
            assert factory.agents[0].history == []
    asyncio.run(scenario())


def test_cancellation_before_worker_start_does_not_construct_agent():
    async def scenario():
        limits = RunLimits()
        constructed = []
        manager = SessionManager(settings(max_concurrent=1), factory=lambda **kwargs: constructed.append(kwargs),
                                 limits=limits, executor=ExecutionRuntime(limits))
        gate, occupied = threading.Event(), threading.Event()
        def occupy():
            occupied.set()
            assert gate.wait(3), "test must release queued worker"
        blocker = manager.pool.submit(occupy)
        job = None
        try:
            await entered(occupied)
            sid = manager.create("1001", "上海").session_id
            job = manager.submit(sid, "never start")
            assert manager.cancel(sid)
            assert not job.task.done()
            gate.set()
            with pytest.raises(RunCancelled):
                await job.task
            await drained(manager)
            assert constructed == []
        finally:
            gate.set()
            await manager.close()
            blocker.result(timeout=1)
    asyncio.run(scenario())


@pytest.mark.parametrize("disconnect", [True, False])
def test_disconnect_or_http_task_cancellation_keeps_executor_future_alive(disconnect):
    async def scenario():
        factory, limits = BlockingFactory(), RunLimits()
        manager = SessionManager(settings(max_concurrent=1), factory=factory,
                                 limits=limits, executor=ExecutionRuntime(limits))
        class Request:
            async def receive(self):
                if disconnect:
                    return {"type": "http.disconnect"}
                await asyncio.Event().wait()
        sid = manager.create("1001", "上海").session_id
        job = manager.submit(sid, "do not commit")
        waiter = None
        try:
            await entered(factory.entered)
            waiter = asyncio.create_task(wait_answer(Request(), job, 1))
            if disconnect:
                with pytest.raises(ServiceError) as failure:
                    await waiter
                assert failure.value.code == "client_disconnected" and failure.value.status == 499
            else:
                await asyncio.sleep(.01)
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
            assert job.run.snapshot()["status"] == "cancelled"
            assert not job.task.cancelled() and not job.task.done()
            assert len(manager.jobs) == 1
        finally:
            factory.release.set()
            with pytest.raises(RunCancelled):
                await job.task
            await drained(manager)
            await manager.close()
        assert factory.agents[0].history == []
    asyncio.run(scenario())


def test_shutdown_cancels_active_runs_and_late_workers_cannot_commit():
    async def scenario():
        factory, limits = BlockingFactory(), RunLimits()
        manager = SessionManager(settings(max_concurrent=1), factory=factory,
                                 limits=limits, executor=ExecutionRuntime(limits))
        manager.start()
        sid = manager.create("1001", "上海").session_id
        job = manager.submit(sid, "late")
        try:
            await entered(factory.entered)
            await manager.close()
            assert manager.closing and manager.sessions == {}
            assert job.run.snapshot()["status"] == "cancelled"
            assert len(manager.jobs) == 1 and not job.task.done()
            with pytest.raises(ServiceError) as failure:
                manager.create("1002", "北京")
            assert failure.value.code == "service_closing"
        finally:
            factory.release.set()
            with pytest.raises(RunCancelled):
                await job.task
            await drained(manager)
            await manager.close()
        assert factory.agents[0].history == []
    asyncio.run(scenario())


def test_unexpected_agent_failure_is_generic_and_does_not_disclose_secrets():
    async def scenario():
        def broken_factory(**kwargs):
            raise RuntimeError("private-source.txt credential=do-not-echo-me")
        async with service(factory=broken_factory) as (app, client):
            sid = await session(client)
            response = await client.post(f"/v1/sessions/{sid}/messages", json={"query": "x"}, headers=AUTH)
            error_code(response, 500, "internal_error")
            assert "private-source" not in response.text and "do-not-echo-me" not in response.text
            await drained(app.state.manager)
    asyncio.run(scenario())


def test_factory_failure_marks_the_run_failed_and_releases_admission():
    async def scenario():
        limits = RunLimits()
        def broken_factory(**kwargs):
            raise RuntimeError("private initialization failure")
        manager = SessionManager(settings(max_concurrent=1), factory=broken_factory,
                                 limits=limits, executor=ExecutionRuntime(limits))
        try:
            sid = manager.create("1001", "上海").session_id
            job = manager.submit(sid, "x")
            with pytest.raises(RuntimeError, match="private initialization failure"):
                await job.task
            await drained(manager)
            assert job.run.snapshot()["status"] == "failed"
            assert job.run.snapshot()["error_type"] == "RuntimeError"
            assert manager.sessions[sid].job is None
        finally:
            await manager.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("changes", [{"api_key": "short"}, {"api_key": "秘密" * 32},
                                     {"max_concurrent": True}, {"max_sessions": 0},
                                     {"max_body_bytes": -1}, {"max_concurrent": 1.5},
                                     {"session_ttl_seconds": 0}, {"request_timeout_seconds": float("inf")},
                                     {"shutdown_seconds": float("nan")}, {"shutdown_seconds": True}])
def test_settings_reject_invalid_trusted_configuration(changes):
    values = {"api_key": KEY, **changes}
    with pytest.raises(ValueError):
        APISettings(**values)


def test_settings_load_environment_and_redact_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", KEY)
    monkeypatch.setenv("API_MAX_CONCURRENT", "3")
    monkeypatch.setenv("API_MAX_SESSIONS", "20")
    monkeypatch.setenv("API_SESSION_TTL_SECONDS", "600")
    monkeypatch.setenv("API_REQUEST_TIMEOUT_SECONDS", "100")
    monkeypatch.setenv("API_SHUTDOWN_SECONDS", "2")
    config = APISettings.from_env()
    assert config.max_concurrent == 3 and config.max_sessions == 20
    assert config.session_ttl_seconds == 600 and config.request_timeout_seconds == 100
    assert config.shutdown_seconds == 2 and KEY not in repr(config)
