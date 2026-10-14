"""Request-local service retrieval state; identity/model are never tool inputs."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

_request = ContextVar('service_rag_request', default=None)
_evaluation_dispatch = ContextVar('service_evaluation_rag_dispatch', default=False)


@dataclass
class ServiceRagRequest:
    model_code: str | None
    references: list = field(default_factory=list)
    evaluation_context: dict | None = None


def current_request():
    return _request.get()


@contextmanager
def service_request(model_code, *, context=None):
    from service_desk.evaluation_context import kb_overlay
    request = ServiceRagRequest(model_code, evaluation_context=context if kb_overlay(context) else None)
    token = _request.set(request)
    try:
        yield request
    finally:
        _request.reset(token)


def evaluation_rag_dispatch_active():
    return _evaluation_dispatch.get()


@contextmanager
def evaluation_rag_dispatch():
    token = _evaluation_dispatch.set(True)
    try:
        yield
    finally:
        _evaluation_dispatch.reset(token)
