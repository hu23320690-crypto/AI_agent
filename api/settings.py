"""Trusted process configuration, never accepted from a message request."""
from dataclasses import dataclass, field
import math
import os


@dataclass(frozen=True)
class APISettings:
    api_key: str = field(repr=False)
    max_concurrent: int = 2
    max_sessions: int = 100
    session_ttl_seconds: float = 1800
    request_timeout_seconds: float = 125
    shutdown_seconds: float = 5
    max_body_bytes: int = 32768

    def __post_init__(self):
        if not isinstance(self.api_key, str) or len(self.api_key) < 32 or not self.api_key.isascii():
            raise ValueError('API_KEY must be at least 32 ASCII characters; generate a random secret')
        for name in ('max_concurrent', 'max_sessions', 'max_body_bytes'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f'API {name} must be a positive integer')
        for name in ('session_ttl_seconds', 'request_timeout_seconds', 'shutdown_seconds'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'API {name} must be finite and positive')

    @classmethod
    def from_env(cls):
        return cls(api_key=os.environ.get('API_KEY', ''),
                   max_concurrent=int(os.environ.get('API_MAX_CONCURRENT', '2')),
                   max_sessions=int(os.environ.get('API_MAX_SESSIONS', '100')),
                   session_ttl_seconds=float(os.environ.get('API_SESSION_TTL_SECONDS', '1800')),
                   request_timeout_seconds=float(os.environ.get('API_REQUEST_TIMEOUT_SECONDS', '125')),
                   shutdown_seconds=float(os.environ.get('API_SHUTDOWN_SECONDS', '5')))
