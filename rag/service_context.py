"""Request-local service retrieval state; identity/model are never tool inputs."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

_request = ContextVar('service_rag_request', default=None)


@dataclass
class ServiceRagRequest:
    model_code: str | None
    references: list = field(default_factory=list)


def current_request():
    return _request.get()


@contextmanager
def service_request(model_code):
    request = ServiceRagRequest(model_code)
    token = _request.set(request)
    try:
        yield request
    finally:
        _request.reset(token)
