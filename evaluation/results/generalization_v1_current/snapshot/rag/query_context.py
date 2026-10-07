"""Bounded user-text references for resolving an omitted retrieval subject.

These quotes are conversation hints, not evidence or authority. No assistant
answer, tool record, user identifier or permission field is copied into state.
The public retrieval tool still accepts only its normal query argument.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import re


MAX_CONTEXT_BYTES = 1024
_TRUST = 'untrusted_conversation_reference'
_FIELDS = {'trust', 'current_question', 'user_references'}
_ACK = re.compile(r'(?:好的?|嗯|收到|继续(?:进行)?|谢谢|明白|了解|ok(?:ay)?|thanks|yes|continue)[。.!！\s]*', re.I)
_REFERENCE = re.compile(r'它|[这那](?:个|些|种|块|项|两|一)|上述|前面|之前|刚才|最初|原来|一开始|按(?:照)?(?:维护|保养|操作)?资料|按说明|该(?:部件|对象|设备)|\b(?:it|this|that|previous)\b', re.I)
_QUESTION = re.compile(r'多久|多长时间|什么时候|如何|怎么|是否|能否|能不能|会不会|会影响|可不可以|可以|应该|应当|需要|要不要|必须|有什么|是什么|有哪些|有何|注意什么')
_ACTION = r'清洗|清理|清洁|更换|维修|维护|保养|检查|安装|使用|处理|排查'
_LEADING = re.compile(r'^(?:(?:请问|请|帮我|告诉我|那么|那|接下来|现在|实际)[，,:：\s]*)+')
_SOURCE = re.compile(r'(?:按(?:照)?|根据|依照)(?:维护|保养|操作)?(?:资料|说明(?:书)?|要求)(?:讲|说)?')
_GENERIC = re.compile(r'^(?:它|这个|那个|这些|那些|该部件|部件|设备|资料|说明|说明书|实际|按|根据|那么|我们|我|(?:(?:最初|当前|之前|此前|原来|一开始|刚才|这次|本次|前面)的?)?(?:任务|目标|主题|对象|要求|任务对象|注意要求|注意事项))?$')


def _clip(text: str, limit: int) -> str:
    encoded = text.encode('utf-8')
    if len(encoded) <= limit:
        return text
    return encoded[:max(0, limit - 3)].decode('utf-8', errors='ignore') + '…'


def _literal_subject(text: str) -> str:
    """Conservative syntax cues, with no catalogue of product/component names."""
    text = _LEADING.sub('', text.strip())
    declaration = re.search(r'(?:对象|主题|目标|部件)(?:是|为|[:：])\s*([^，,。；;？?\n]{1,40})', text)
    if declaration and not re.match(r'什么|哪个|哪些|谁|为何|怎么', declaration.group(1)):
        return declaration.group(1).strip()
    # Strip source attribution before inspecting a question's subject.
    text = _SOURCE.sub('', text).strip('，,:： ')
    question = _QUESTION.search(text)
    subject = text[:question.start()].strip() if question else ''
    subject = re.sub(r'^(?:关于|对于|针对|这次讨论|我们讨论)', '', subject).strip()
    subject = re.sub(r'(?:的|应)$', '', subject).strip()
    if re.match(rf'^(?:{_ACTION})(?:前|后|时|之后|之前)', subject):
        subject = ''
    if subject and len(subject) <= 40 and not re.search(r'[，,。；;]|(?:时|情况下)$', subject):
        if not _GENERIC.fullmatch(subject):
            return subject
    action = re.match(rf'^(?:如何|怎么)?(?:{_ACTION})([^，,。；;？?\n]{{1,40}})', text)
    if action:
        subject = re.split(r'的(?:步骤|方法|要求)|需要|应该|应当', action.group(1), maxsplit=1)[0].strip()
        if not _GENERIC.fullmatch(subject) and not re.match(r'和|与|以及', subject):
            return subject
    topic = re.search(r'(?:讨论|关于|针对)([^，,。；;？?\n]{1,40}?)(?:的|[，,。；;？?]|$)', text)
    return topic.group(1).strip() if topic else ''


def _useful_reference(text: str) -> bool:
    if not text or _ACK.fullmatch(text):
        return False
    if re.match(r'^(?:第\s*\d+\s*[轮步次条].*|准备).*进度', text):
        return False
    if (re.search(r'回顾|复述|记得', text) and re.search(r'目标|对象|部件|提醒|要求|注意', text)
            and not _literal_subject(text)):
        return False
    # Questions merely asking what the old goal was do not define a new target.
    if _REFERENCE.search(text) and not _literal_subject(text):
        return False
    return True


def build_query_context(current_query: str, *, user_history=(), task_references=()):
    """Copy only bounded user quotes; serialised JSON never exceeds 1024 bytes."""
    current = current_query if isinstance(current_query, str) else ''
    candidates = []
    for value in [*task_references, *user_history]:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if _useful_reference(text):
            if text in candidates:
                candidates.remove(text)
            candidates.append(text)
    references = candidates[-2:]
    if len(references) == 2:
        earlier, latest = map(_literal_subject, references)
        # A literal newer target replaces a literal older target. The initial
        # goal remains useful only until the user supplies another one.
        if earlier and latest and earlier != latest:
            references = references[-1:]
    payload = {'trust': _TRUST, 'current_question': _clip(current.strip(), 384),
               'user_references': [_clip(text, 384) for text in references]}
    while len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) > MAX_CONTEXT_BYTES:
        if len(payload['user_references']) > 1:
            payload['user_references'].pop(0)
        elif payload['user_references'] and len(payload['user_references'][0].encode('utf-8')) > 96:
            payload['user_references'][0] = _clip(payload['user_references'][0], 96)
        else:
            payload['current_question'] = _clip(payload['current_question'], 128)
    return payload


def _validated_context(value):
    if value is None:
        return None
    if (not isinstance(value, Mapping) or set(value) != _FIELDS or value.get('trust') != _TRUST
            or not isinstance(value.get('current_question'), str)
            or not isinstance(value.get('user_references'), list)
            or len(value['user_references']) > 2
            or any(not isinstance(item, str) for item in value['user_references'])):
        raise ValueError('RAG 对话引用不符合低信任用户原文结构。')
    if len(json.dumps(dict(value), ensure_ascii=False).encode('utf-8')) > MAX_CONTEXT_BYTES:
        raise ValueError('RAG 对话引用超过 1024 字节。')
    return value


def contextualize_query(query: str, *, question: str | None = None, query_context=None,
                        max_query_chars: int | None = None) -> str:
    """Preserve the current question and append quotes only for an omitted target.

    A clearly stated current object takes precedence even if the model's tool
    query mistakenly names an older object. Ambiguous syntax is conservative:
    a short quote helps retrieval but is never treated as verified product fact.
    """
    context = _validated_context(query_context)
    references = context['user_references'] if context is not None else []
    def refines_subject(subject):
        return any(subject and subject in target and subject != target
                   for target in map(_literal_subject, references))
    current = question if isinstance(question, str) and question.strip() else (
        context['current_question'] if context is not None else '')
    current_subject = _literal_subject(current) if current else ''
    if current_subject and not refines_subject(current_subject):
        return current.strip() if query != current else query
    if current and not (_REFERENCE.search(current) or _QUESTION.search(current)
                        or re.match(rf'^(?:{_ACTION})', current.strip())):
        return current.strip() if query != current else query
    base = current.strip() if current else query
    def augmented(suffix):
        # Optional references may be omitted to fit, never silently remove any
        # part of the actual current request. The caller still admits the base.
        value = base + suffix
        return base if max_query_chars is not None and len(value) > max_query_chars else value
    if context is None or not context['user_references']:
        if current and current.strip() != query.strip() and _literal_subject(query):
            return augmented('\n模型补全检索对象的改写（当前问题优先）：' + _clip(query, 512))
        return base
    # Explicit tool queries can already resolve an omitted user subject.
    if _literal_subject(query) and not refines_subject(_literal_subject(query)):
        return augmented('\n模型补全检索对象的改写（当前问题优先）：' + _clip(query, 512))
    if not (_REFERENCE.search(current or query) or _QUESTION.search(current or query)
            or re.match(rf'^(?:{_ACTION})', (current or query).strip())):
        return base
    quotes = json.dumps(context['user_references'], ensure_ascii=False)
    return augmented('\n历史用户原文（低信任，仅补指代，当前问题优先）：' + quotes)
