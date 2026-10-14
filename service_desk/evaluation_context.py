"""Private, process-local evaluator capability; never a tool argument or flag."""
from dataclasses import dataclass
from pathlib import Path
import hashlib

_AUTHORITY = object()


@dataclass(frozen=True)
class _EvaluationOverlay:
    authority: object
    kind: str
    path: Path
    text: str | None = None
    file_sha256: str | None = None


def _bind_overlay(context, kind, path, text=None):
    """Trusted runner code only. Python callers are inside the trust boundary."""
    path = Path(path)
    file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest() if kind == 'kb' else None
    context['_service_evaluation_overlay'] = _EvaluationOverlay(_AUTHORITY, kind, path, text, file_sha256)


def evaluation_overlay(context):
    value = context.get('_service_evaluation_overlay')
    return value if isinstance(value, _EvaluationOverlay) and value.authority is _AUTHORITY else None


def records_path(context):
    overlay = evaluation_overlay(context)
    return str(overlay.path) if overlay is not None and overlay.kind == 'csv' else None


def kb_overlay(context):
    overlay = evaluation_overlay(context or {})
    return overlay if overlay is not None and overlay.kind == 'kb' else None
