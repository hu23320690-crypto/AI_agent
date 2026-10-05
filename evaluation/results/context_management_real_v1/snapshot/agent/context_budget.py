"""Conservative local request-size estimates and pre-dispatch admission.

Counts are UTF-8 byte estimates plus framing allowances, not Qwen tokenizer
counts. They overcount ordinary text; they cannot prove an exact token bound for
every model/template/multimodal input. Admission never trims messages, invokes
models, or fails the run: callers may recover using older complete-turn summaries.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, fields
from functools import lru_cache
import json
import math
from pathlib import Path

from langchain_core.messages import BaseMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from agent.runtime import RuntimeControlError, current_run


@dataclass(frozen=True)
class ContextPolicy:
    window_tokens: int = 8192
    reserve_output_tokens: int = 1024
    safety_margin_tokens: int = 256
    keep_recent_turns: int = 2
    trigger_fraction: float = .8
    summary_max_tokens: int = 512
    summary_enabled: bool = True

    def __post_init__(self):
        integer_fields = ('window_tokens', 'reserve_output_tokens', 'safety_margin_tokens',
                          'keep_recent_turns', 'summary_max_tokens')
        for name in integer_fields:
            value = getattr(self, name)
            minimum = 0 if name == 'safety_margin_tokens' else 1
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f'context.{name} must be an integer >= {minimum}')
        fraction = self.trigger_fraction
        if (isinstance(fraction, bool) or not isinstance(fraction, (int, float))
                or not math.isfinite(fraction) or not 0 < fraction <= 1):
            raise ValueError('context.trigger_fraction must be finite and in (0, 1]')
        if not isinstance(self.summary_enabled, bool):
            raise ValueError('context.summary_enabled must be a boolean')
        if self.reserve_output_tokens + self.safety_margin_tokens >= self.window_tokens:
            raise ValueError('context window must exceed output reserve plus safety margin')
        if self.summary_max_tokens > self.reserve_output_tokens:
            raise ValueError('context.summary_max_tokens must fit the output reserve')


@lru_cache(maxsize=8)
def load_context_policy(path=None):
    """Load trusted configuration; edit-and-restart like runtime.yml."""
    import yaml
    path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / 'config/context.yml'
    values = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(values, dict):
        raise ValueError('context configuration must be a mapping')
    unknown = set(values) - {field.name for field in fields(ContextPolicy)}
    if unknown:
        raise ValueError('unknown context fields: ' + ', '.join(sorted(map(str, unknown))))
    return ContextPolicy(**values)


class ContextBudgetExceeded(RuntimeControlError):
    """Recoverable before dispatch; the turn owner decides whether to fail."""
    def __init__(self, estimated_tokens, input_limit, *, label='model.request'):
        self.estimated_tokens = estimated_tokens
        self.input_limit = input_limit
        self.label = label
        super().__init__('本次请求的上下文估计开销超过预算，请缩短问题或开启新会话。'
                         f'（估计 {estimated_tokens}，输入预算 {input_limit}）')


_REQUEST_FRAMING = 32
_MESSAGE_FRAMING = 16
_TOOL_FRAMING = 16
_FORMAT_FRAMING = 32
_HIDDEN_BLOCKS = frozenset({'reasoning', 'thinking', 'redacted_thinking', 'reasoning_content'})
_HIDDEN_METADATA = frozenset({'reasoning_content', 'thinking'})


def _without_hidden_blocks(content):
    if isinstance(content, list):
        return [block for block in content
                if not (isinstance(block, Mapping) and block.get('type') in _HIDDEN_BLOCKS)]
    return content


def _as_messages(messages):
    if hasattr(messages, 'to_messages'):
        messages = messages.to_messages()
    if isinstance(messages, (str, BaseMessage, Mapping)):
        return [messages]
    return messages


def sanitize_messages(messages):
    """Deep-copy the actual send view without hidden reasoning/usage metadata.

    Ollama replays AIMessage.additional_kwargs['reasoning_content'] as thinking.
    Removing it here (and sending this same view) avoids replaying hidden traces.
    Visible text and complete tool calls/results are preserved. Plain-text
    <think> strings are not guessed or removed: they remain visible and counted.
    """
    clean = []
    for message in _as_messages(messages):
        if isinstance(message, BaseMessage):
            copied = message.model_copy(deep=True)
            copied.content = _without_hidden_blocks(copied.content)
            copied.additional_kwargs = {key: value for key, value in copied.additional_kwargs.items()
                                        if key not in _HIDDEN_METADATA}
            copied.response_metadata = {}
            if hasattr(copied, 'usage_metadata'):
                copied.usage_metadata = None
            clean.append(copied)
        elif isinstance(message, Mapping):
            copied = deepcopy(dict(message))
            for key in (*_HIDDEN_METADATA, 'usage_metadata', 'response_metadata'):
                copied.pop(key, None)
            if isinstance(copied.get('additional_kwargs'), Mapping):
                copied['additional_kwargs'] = {key: value for key, value in copied['additional_kwargs'].items()
                                              if key not in _HIDDEN_METADATA}
            if 'content' in copied:
                copied['content'] = _without_hidden_blocks(copied['content'])
            clean.append(copied)
        elif isinstance(message, tuple) and len(message) == 2:
            clean.append((message[0], _without_hidden_blocks(deepcopy(message[1]))))
        elif isinstance(message, str):
            clean.append(message)
        else:
            raise ValueError(f'unsupported context message: {type(message).__name__}')
    return clean


def _message_for_wire(message):
    if isinstance(message, BaseMessage):
        role = getattr(message, 'role', None) or {
            'human': 'user', 'ai': 'assistant', 'system': 'system',
            'tool': 'tool', 'function': 'function',
        }.get(message.type, message.type)
        wire = {'role': role, 'content': message.content}
        for name in ('name', 'tool_call_id'):
            value = getattr(message, name, None)
            if value is not None:
                wire[name] = value
        calls = getattr(message, 'tool_calls', None)
        if not calls:
            calls = message.additional_kwargs.get('tool_calls')
        if calls:
            wire['tool_calls'] = calls
        # Do not silently ignore a field that Ollama will actually replay.
        for key in _HIDDEN_METADATA:
            if key in message.additional_kwargs:
                wire[key] = message.additional_kwargs[key]
        return wire
    if isinstance(message, str):
        return {'role': 'user', 'content': message}
    if isinstance(message, tuple) and len(message) == 2:
        return {'role': message[0], 'content': message[1]}
    if isinstance(message, Mapping):
        wire = {name: message[name] for name in
                ('role', 'type', 'content', 'name', 'tool_calls', 'tool_call_id',
                 'reasoning_content', 'thinking') if name in message}
        extra = message.get('additional_kwargs')
        if isinstance(extra, Mapping):
            if not wire.get('tool_calls') and extra.get('tool_calls'):
                wire['tool_calls'] = extra['tool_calls']
            for key in _HIDDEN_METADATA:
                if key in extra:
                    wire[key] = extra[key]
        return wire
    raise ValueError(f'unsupported context message: {type(message).__name__}')


def _json_bytes(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                              allow_nan=False).encode('utf-8'))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('context request must contain finite JSON-compatible content') from exc


def _format_schema(response_format):
    if isinstance(response_format, (Mapping, str, list)):
        return response_format
    if isinstance(response_format, type) and hasattr(response_format, 'model_json_schema'):
        return response_format.model_json_schema()
    schema = getattr(response_format, 'schema', response_format)
    if isinstance(schema, Mapping):
        return schema
    if isinstance(schema, type) and hasattr(schema, 'model_json_schema'):
        return schema.model_json_schema()
    if isinstance(schema, type):
        # LangChain AutoStrategy can hold dataclass/TypedDict schemas as well.
        return convert_to_openai_tool(schema)
    raise ValueError('unsupported context response_format')


def estimate_request(messages, tools=(), system_message=None, response_format=None):
    """Estimate public request fields without invoking/downloading tokenizers.

    Supports PromptValue, LangChain messages, wire dictionaries, and simple
    (role, content) tuples. A separately injected system message must not already
    be in messages. Tool definitions use LangChain's public schema conversion.
    No messages are mutated. Reasoning must be sanitized before the actual send;
    if it is supplied here it is counted, because Ollama can replay it.
    """
    size = _REQUEST_FRAMING
    if system_message is not None:
        if isinstance(system_message, str):
            system_message = {'role': 'system', 'content': system_message}
        size += _MESSAGE_FRAMING + _json_bytes(_message_for_wire(system_message))
    for message in _as_messages(messages):
        size += _MESSAGE_FRAMING + _json_bytes(_message_for_wire(message))
    for tool in tools or ():
        size += _TOOL_FRAMING + _json_bytes(convert_to_openai_tool(tool))
    if response_format is not None:
        size += _FORMAT_FRAMING + _json_bytes(_format_schema(response_format))
    return size


def _configured_values(model, name):
    """Inspect model plus bounded RunnableBinding wrappers, never invoke."""
    seen = set()
    for _ in range(8):
        if model is None or id(model) in seen:
            break
        seen.add(id(model))
        value = getattr(model, name, None)
        if value is not None:
            yield value
        kwargs = getattr(model, 'kwargs', None)
        if isinstance(kwargs, Mapping) and kwargs.get(name) is not None:
            yield kwargs[name]
        model = getattr(model, 'bound', None)


def effective_input_limit(policy, model=None):
    """Use the smaller actual context window and reserve space for output."""
    window = policy.window_tokens
    for configured in _configured_values(model, 'num_ctx'):
        if isinstance(configured, bool) or not isinstance(configured, int) or configured <= 0:
            raise ValueError('model.num_ctx must be a positive integer when configured')
        window = min(window, configured)
    limit = window - policy.reserve_output_tokens - policy.safety_margin_tokens
    if limit <= 0:
        raise ValueError('model context window cannot fit output reserve and safety margin')
    return limit


def output_cap(model=None, policy=None):
    """Positive Ollama num_predict cap; apply at every actual dispatch/retry.

    Preserve any existing smaller positive model cap. Negative unlimited or
    context-fill values are replaced by the reserve. Summary dispatch should
    clamp further to summary_max_tokens.
    """
    policy = policy if policy is not None else load_context_policy()
    cap = policy.reserve_output_tokens
    for configured in _configured_values(model, 'num_predict'):
        if isinstance(configured, bool) or not isinstance(configured, int):
            raise ValueError('model.num_predict must be an integer when configured')
        if configured > 0:
            cap = min(cap, configured)
    return cap


def enforce_request(messages, tools=(), system_message=None, response_format=None,
                    *, policy=None, model=None, run=None, label='model.request'):
    """Admit before dispatch, or raise without changing run status."""
    policy = policy if policy is not None else load_context_policy()
    run = run if run is not None else current_run()
    if run is not None:
        run.check()
    limit = effective_input_limit(policy, model)
    size = estimate_request(messages, tools, system_message, response_format)
    if run is not None:
        run.check()
        run.note('context_budget_checked', label=label, estimated_tokens=size,
                 input_limit=limit, estimation_method='utf8_bytes_plus_framing')
    if size > limit:
        if run is not None:
            run.note('context_budget_exceeded', label=label, estimated_tokens=size, input_limit=limit)
        raise ContextBudgetExceeded(size, limit, label=label)
    return size
