"""Bounded, tool-free optional intent extraction; model text is never logged."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date
import json
import math
import os
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.context_budget import enforce_request, load_context_policy
from agent.runtime import dependency_key, optional_model_call
from utils.model_output import IncompleteModelOutput, ensure_complete_response
from .schema import INTENT_SCHEMA, IntentProposal


_ROOT = Path(__file__).resolve().parents[2]
MODES = frozenset({'rule', 'hybrid', 'llm_only'})


@dataclass(frozen=True)
class IntentConfig:
    mode: str = 'rule'
    timeout_seconds: float = 15
    history_queries: int = 3
    history_bytes: int = 1024

    def __post_init__(self):
        if not isinstance(self.mode, str) or self.mode not in MODES:
            raise ValueError('intent.mode must be rule, hybrid or llm_only')
        value = self.timeout_seconds
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError('intent.timeout_seconds must be finite and positive')
        for name, maximum in (('history_queries', 3), ('history_bytes', 1024)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
                raise ValueError(f'intent.{name} must be an integer in [0, {maximum}]')


def load_intent_config(path=None):
    """Read trusted config and the effective environment mode on each call."""
    import yaml
    path = Path(path) if path is not None else _ROOT / 'config/intent.yml'
    values = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(values, dict):
        raise ValueError('intent configuration must be a mapping')
    unknown = set(values) - {field.name for field in fields(IntentConfig)}
    if unknown:
        raise ValueError('unknown intent configuration fields')
    values = dict(values)
    if 'AGENT_INTENT_MODE' in os.environ:
        values['mode'] = os.environ['AGENT_INTENT_MODE']
    return IntentConfig(**values)


def bounded_history_queries(history_queries, cfg):
    """Keep recent user text within a UTF-8 byte limit, never assistant text."""
    history = [value for value in history_queries if isinstance(value, str)]
    if not cfg.history_queries or not cfg.history_bytes:
        return ()
    remaining, selected = cfg.history_bytes, []
    for value in reversed(history[-cfg.history_queries:]):
        raw = value.encode('utf-8')
        truncated = len(raw) > remaining
        if truncated:
            # Preserve the latest wording without splitting a UTF-8 character.
            value = raw[-remaining:].decode('utf-8', errors='ignore')
        if value:
            selected.append(value)
            remaining -= len(value.encode('utf-8'))
        if not remaining or truncated:
            break
    return tuple(reversed(selected))


class InvalidIntentProposal(ValueError):
    """V1 failure with a fixed safe message, never the offending model text."""


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidIntentProposal('Intent proposal has duplicate keys')
        result[key] = value
    return result


def _invalid_constant(value):
    raise InvalidIntentProposal('Intent proposal contains non-JSON constants')


def parse_proposal(message):
    """V1: complete strict JSON, including nested duplicate/extra-key checks."""
    if (not isinstance(message, AIMessage) or message.tool_calls or message.invalid_tool_calls
            or message.additional_kwargs.get('tool_calls')
            or not isinstance(message.content, str) or len(message.content) > 16384):
        raise InvalidIntentProposal('Intent proposal must be a tool-free JSON answer')
    try:
        ensure_complete_response(message)
        value = json.loads(message.content, object_pairs_hook=_json_object,
                           parse_constant=_invalid_constant)
        return IntentProposal.model_validate(value)
    except (ValueError, TypeError, RecursionError, IncompleteModelOutput) as exc:
        raise InvalidIntentProposal('Intent proposal failed structural validation') from exc


def intent_model():
    # Lazy construction/import keeps rule mode free of optional model work.
    from model.factory import budgeted_chat_model, chat_model
    return budgeted_chat_model(chat_model, load_context_policy(), purpose='intent')


def parse_turn_intent(query, *, history_queries, previous_intent, known_fields,
                      today, run, cfg):
    model = intent_model()
    policy = load_context_policy()
    messages = [
        SystemMessage(content=(_ROOT / 'prompts/intent_parser.txt').read_text(encoding='utf-8')),
        HumanMessage(content=json.dumps({
            'field_catalog': '\n'.join(known_fields),
            'today': (today or date.today()).isoformat(),
            'previous_intent': asdict(previous_intent) if previous_intent is not None else None,
            'history_queries': list(history_queries),
            'query': query,
        }, ensure_ascii=False)),
    ]
    enforce_request(messages, response_format=INTENT_SCHEMA, policy=policy,
                    model=model, run=run, label='agent.intent')
    # Source revocation is terminal even though this model call is optional.
    run.validate_commit_checks()
    response = optional_model_call(
        'agent.intent', lambda: model.invoke(messages), run=run,
        dependency=dependency_key(model, 'chat'), seconds=cfg.timeout_seconds)
    run.check()
    run.validate_commit_checks()
    return parse_proposal(response)
