"""Authenticated REST service. Run one Uvicorn worker for process-local sessions."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from agent.runtime import (BudgetExceeded, CallTimeout, DeadlineExceeded, RunBusy, RunCancelled,
                           CircuitOpen, DependencyUnavailable)
from agent.context_budget import ContextBudgetExceeded
from utils.model_output import IncompleteModelOutput
from rag.security import KnowledgeAccessError
from api.settings import APISettings
from api.sessions import SessionManager, ServiceError, production_agent
from api.readiness import ReadinessProbe

log = logging.getLogger('agent.api')


class SessionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    user_id: str = Field(default='', max_length=64)
    city: str = Field(default='', max_length=128)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=8000)


class BoundaryMiddleware:
    """Check auth before buffering; cap actual streamed bytes, not just the header."""
    def __init__(self, app, settings_getter):
        self.app, self.settings_getter = app, settings_getter

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault('state', {})['request_id'] = request_id
        settings = self.settings_getter()
        status = 500
        started = time.monotonic()

        async def tagged_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []), (b'x-request-id', request_id.encode())]}
            await send(message)

        async def reject(code, text, number, headers=None):
            await JSONResponse({'error': {'code': code, 'message': text}, 'request_id': request_id},
                               status_code=number, headers=headers)(scope, receive, tagged_send)

        try:
            path = scope.get('path', '')
            if path.startswith('/v1/') or path == '/readyz':
                values = [v for k, v in scope['headers'] if k == b'authorization']
                expected = ('Bearer '+settings.api_key).encode('ascii')
                if len(values) != 1 or not hmac.compare_digest(values[0], expected):
                    return await reject('unauthorized', '需要有效的 Bearer API key。', 401, {'WWW-Authenticate': 'Bearer'})
            bodies = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                if len(bodies) + len(chunk) > settings.max_body_bytes:
                    return await reject('body_too_large', '请求体超过大小限制。', 413)
                bodies.extend(chunk)
                if not message.get('more_body', False):
                    break
            delivered = False

            async def limited_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': bytes(bodies), 'more_body': False}
                return await receive()
            await self.app(scope, limited_receive, tagged_send)
        finally:
            route = scope.get('route')
            log.info('http_request request_id=%s method=%s route=%s status=%s seconds=%.3f',
                     request_id, scope['method'], getattr(route, 'path', '<unmatched>'),
                     status, time.monotonic()-started)


def map_failure(exc):
    if isinstance(exc, ServiceError):
        return exc
    for category, code, text, status in (
        (RunCancelled, 'run_cancelled', '本轮已取消，未提交回答。', 409),
        (RunBusy, 'session_busy', '会话正在运行。', 409),
        (DeadlineExceeded, 'deadline_exceeded', '本轮已超过执行预算。', 504),
        (CallTimeout, 'dependency_timeout', '依赖调用超时。', 504),
        (ContextBudgetExceeded, 'context_budget_exceeded', '上下文超过预算，请缩短问题或新建会话。', 422),
        (BudgetExceeded, 'call_budget_exceeded', '请求超过调用或长度预算。', 422),
        (IncompleteModelOutput, 'incomplete_model_output', '模型未完成回答，本轮未提交。', 502),
        (CircuitOpen, 'dependency_unavailable', '依赖暂时不可用。', 503),
        (DependencyUnavailable, 'dependency_unavailable', '依赖暂时不可用。', 503),
        (KnowledgeAccessError, 'knowledge_unavailable', '知识来源已失效，请更新资料后重试。', 503),
    ):
        if isinstance(exc, category):
            return ServiceError(code, text, status)
    return ServiceError('internal_error', '请求未完成，请稍后重试。', 500)


async def wait_answer(request, job, timeout):
    async def disconnected():
        # Pydantic already consumed the body. Listen directly to ASGI events;
        # is_disconnected() uses a cancelled AnyIO scope which can swallow an
        # external asyncio cancellation and leave this watcher running forever.
        while True:
            message = await request.receive()
            if message['type'] == 'http.disconnect':
                return

    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({job.task, watcher}, timeout=timeout,
                                     return_when=asyncio.FIRST_COMPLETED)
        if job.task in done:
            return job.task.result()
        job.run.cancel()
        if watcher in done:
            raise ServiceError('client_disconnected', '客户端已断开，本轮取消。', 499)
        raise ServiceError('request_timeout', 'HTTP 请求等待超时，本轮取消。', 504)
    except asyncio.CancelledError:
        job.run.cancel()
        raise
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        # Never cancel job.task: admission stays held until its real thread exits.


def create_app(*, settings=None, agent_factory=production_agent, readiness=None, limits=None, executor=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings or APISettings.from_env()
        app.state.manager = SessionManager(app.state.settings, factory=agent_factory, limits=limits, executor=executor)
        app.state.probe = readiness or ReadinessProbe()
        app.state.manager.start()
        try:
            yield
        finally:
            await app.state.manager.close()
            close = getattr(app.state.probe, 'close', None)
            if close is not None:
                await close()

    app = FastAPI(title='Robot Vacuum RAG Agent API', version='1.0.0', lifespan=lifespan)
    app.add_middleware(BoundaryMiddleware, settings_getter=lambda: app.state.settings)

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        headers = {'Retry-After': str(exc.retry_after)} if exc.retry_after is not None else None
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message},
                             'request_id': request.state.request_id}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo rejected bodies, tokens or internal exception details.
        return await service_error(request, ServiceError('invalid_request', '参数不合法，请核对接口格式。', 422))

    @app.get('/healthz')
    async def health():
        return {'status': 'ok'}

    @app.get('/readyz')
    async def ready(request: Request):
        result = await app.state.probe()
        return JSONResponse(result, status_code=200 if result['ready'] else 503)

    @app.post('/v1/sessions', status_code=201)
    async def create_session(body: SessionInput):
        session = app.state.manager.create(body.user_id, body.city)
        return {'session_id': session.session_id, 'user_id': session.user_id, 'city': session.city}

    @app.post('/v1/sessions/{session_id}/messages')
    async def send_message(session_id: str, body: MessageInput, request: Request):
        job = app.state.manager.submit(session_id, body.query)
        try:
            answer = await wait_answer(request, job, app.state.settings.request_timeout_seconds)
        except ServiceError:
            raise
        except Exception as exc:
            if map_failure(exc).status == 500:
                log.exception('agent_error run_id=%s', job.run.run_id)
            raise map_failure(exc) from exc
        snap = job.run.snapshot()
        return {'session_id': session_id, 'answer': answer, 'run_id': snap['run_id'],
                'status': snap['status'], 'seconds': snap['seconds'], 'counts': snap['counts']}

    @app.post('/v1/sessions/{session_id}/cancel')
    async def cancel_session(session_id: str):
        return {'cancelled': app.state.manager.cancel(session_id)}

    @app.delete('/v1/sessions/{session_id}', status_code=204)
    async def delete_session(session_id: str):
        app.state.manager.delete(session_id)
        return Response(status_code=204)

    # Advertise bearer auth in generated OpenAPI without exposing the secret.
    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        schema.setdefault('components', {}).setdefault('securitySchemes', {})['APIKey'] = {'type': 'http', 'scheme': 'bearer'}
        for path, operations in schema['paths'].items():
            if path.startswith('/v1/') or path == '/readyz':
                for operation in operations.values():
                    if isinstance(operation, dict):
                        operation['security'] = [{'APIKey': []}]
        return schema
    app.openapi = openapi
    return app


app = create_app()
