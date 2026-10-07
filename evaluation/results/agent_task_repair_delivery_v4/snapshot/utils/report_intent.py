"""Deterministic report selectors from user text, never model conclusions.

Month and field selectors confer no permission: callers must still use the
server-selected identity and policy-checked lookup results.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from collections.abc import Iterable


@dataclass(frozen=True)
class ReportIntent:
    fields: tuple[str, ...] = ()
    target_month: str | None = None
    comparison_month: str | None = None
    compare: bool = False
    limited: bool = False
    invalid_month: bool = False


_MONTH = re.compile(r"(?<!\d)(\d{4})\s*[-/年]\s*(\d{1,2})\s*月?(?!\d)")
_BARE_MONTH = re.compile(r"(?<![\d年/上下-])(?P<month>\d{1,2}|十二|十一|十|[一二三四五六七八九])\s*月")
_CHINESE_MONTHS = {word: index for index, word in enumerate(
    ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"), 1)}
_ONLY = re.compile(r"(?:只|仅)(?:需要|需|返回|列出|列|看|要|报出|报|给|提供|展示|回答|显示|输出)|限定.*字段")
_REFERENCE = re.compile(r"[这那](?:两|几|些|个|一)|上述|刚才|同样|它们|继续|原来|之前|前面|一开始|最初")
_COMPARE = re.compile(r"相比|比较|对比|比上(?:一|个)?月|较上(?:一|个)?月|增加|减少|提高|下降|增长|降低|变化|差值|差多少|环比")
_FULL = re.compile(r"(?:完整|全部|全面|所有).{0,4}(?:报告|记录|字段|指标)|(?:报告|记录).{0,4}(?:完整|全部|所有)")


def valid_month(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        return False
    try:
        date(int(value[:4]), int(value[5:]), 1)
    except ValueError:
        return False
    return True


def shift_month(value: str | None, offset: int) -> str | None:
    if not valid_month(value):
        return None
    absolute = int(value[:4]) * 12 + int(value[5:]) - 1 + offset
    year, zero_month = divmod(absolute, 12)
    return f"{year:04d}-{zero_month + 1:02d}" if 1 <= year <= 9999 else None


def _field_key(text: str) -> str:
    # Display/unit modifiers do not change the underlying recorded metric.
    return re.sub(r"\s|[:：]|每月|每周|每日|频次|次数|面积|数值|指标|字段", "", text).casefold()


def _field_mentions(query: str, known_fields: Iterable[str]) -> tuple[str, ...]:
    # Negative clauses must not select the very fields they exclude.
    positive = re.split(r"[，,。；;]\s*(?:不要|无需|不需要|不用|别)", query, maxsplit=1)[0]
    compact = _field_key(positive)
    matches = []
    for field in dict.fromkeys(known_fields):
        key = _field_key(field)
        if key and key in compact:
            matches.append((compact.index(key), -len(key), field))
    # A longer label must not additionally select its contained shorter label.
    selected, spans = [], []
    for position, negative_length, field in sorted(matches):
        end = position - negative_length
        if any(start <= position and end <= finish for start, finish in spans):
            continue
        selected.append(field)
        spans.append((position, end))
    return tuple(selected)


def _explicit_field_list(query: str, known_fields: Iterable[str]) -> tuple[str, ...]:
    """Keep unknown names in a clear limited-field list instead of omitting them."""
    marker = _ONLY.search(query)
    if marker is None:
        return ()
    scope = re.split(r'[，,。；;？?]', query[marker.end():], maxsplit=1)[0].strip()
    if not scope or re.match(r'(?:这|那|上述|同样|两个|三个|几个|\d+个)', scope):
        return ()
    labels = []
    for phrase in re.split(r'、|以及|和|与|及', scope):
        phrase = re.sub(r'^(?:我|以下|的|出|一下)+', '', phrase.strip())
        phrase = re.sub(r'(?:各是多少|是多少|分别是多少|即可|就行|这.{0,4}字段|字段|数值)$', '', phrase).strip()
        if not phrase or len(phrase) > 40 or re.search(r'报告|记录|\d{4}|月份|不要|不用', phrase):
            return ()
        matched = _field_mentions(phrase, known_fields)
        labels.extend(matched or (phrase,))
    return tuple(dict.fromkeys(labels))


def _plain_field_list(query: str, known_fields: Iterable[str]) -> tuple[str, ...]:
    """Recognize a narrow noun list, preserving unknown requested metric names.

    This is deliberately not free-form intent inference. Comparison, report,
    negation and conversational clauses stay on their existing parsing paths.
    """
    if _ONLY.search(query) or _COMPARE.search(query) or _FULL.search(query):
        return ()
    scope = re.split(r'[，,。；;？?]', query, maxsplit=1)[0].strip()
    if re.search(r'不要|无需|不需要|不用|别|报告|记录|相较|相对|而非|而不是', scope):
        return ()
    scope = re.sub(r'^(?:请|麻烦)?(?:帮我)?(?:查询|查看|查|看|告诉我|给我|返回|提供)?\s*', '', scope)
    # Remove only explicit date selectors; unsupported free prose is rejected
    # below, rather than guessed into a metric name.
    scope = _MONTH.sub('', scope)
    scope = _BARE_MONTH.sub('', scope)
    scope = re.sub(r'^(?:我的|我|的|本月|这个月|当月)\s*', '', scope)
    scope = re.sub(r'(?:分别|各)?是多少$|(?:的数据|的数值|数值)$', '', scope).strip()
    if not re.search(r'、|以及|和|及', scope):
        return ()
    labels = []
    for phrase in re.split(r'、|以及|和|及', scope):
        phrase = phrase.strip()
        if (not phrase or len(phrase) > 20 or
                not re.fullmatch(r'[\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z0-9_]*', phrase) or
                re.search(r'请|查|看|问|回答|多少|为什么|如何|怎么|需要|要求|这两|那两|(?:是|否|吗)$', phrase)):
            return ()
        matched = _field_mentions(phrase, known_fields)
        # If a known label is embedded in unrelated prose, do not discard the
        # rest of the phrase and silently pretend it was a clean metric name.
        if matched and (len(matched) != 1 or _field_key(phrase) != _field_key(matched[0])):
            return ()
        labels.extend(matched or (phrase,))
    return tuple(dict.fromkeys(labels))


def _explicit_months(query: str, previous: ReportIntent, fallback_month: str | None):
    matches, occupied, invalid = [], [], False
    for match in _MONTH.finditer(query):
        year, month = map(int, match.groups())
        value = f"{year:04d}-{month:02d}"
        if valid_month(value):
            matches.append((match.start(), value))
        else:
            invalid = True
        occupied.append(match.span())
    year_source = (matches[0][1] if matches else previous.target_month) or fallback_month
    for match in _BARE_MONTH.finditer(query):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        raw = match.group('month')
        month = int(raw) if raw.isdigit() else _CHINESE_MONTHS[raw]
        if not 1 <= month <= 12:
            invalid = True
        elif valid_month(year_source):
            matches.append((match.start(), f"{year_source[:4]}-{month:02d}"))
    return sorted(matches), invalid


def _update(query: str, previous: ReportIntent, known_fields: Iterable[str], fallback_month: str | None):
    fields = (_explicit_field_list(query, known_fields) or _plain_field_list(query, known_fields)
              or _field_mentions(query, known_fields))
    full_matches = list(_FULL.finditer(query))
    only_matches = list(_ONLY.finditer(query))
    full = bool(full_matches) and (not only_matches or full_matches[-1].start() > only_matches[-1].start())
    compare = bool(_COMPARE.search(query)) and "同类" not in query and "同面积" not in query
    reference = bool(_REFERENCE.search(query))
    if not fields and not full and (reference or compare):
        fields = previous.fields
    if full:
        fields = ()
    limited = not full and (bool(fields) or bool(_ONLY.search(query)) or
                           (reference and previous.limited))
    explicit, invalid = _explicit_months(query, previous, fallback_month)
    target, baseline = None, None
    if explicit:
        target = explicit[0][1]
        if len(explicit) >= 2 and compare:
            # "比较 A 和 B" and "与 A 相比，B" put the baseline first.
            if re.search(r"^(?:请)?(?:比较|对比|与|和|相较)", query.strip()):
                baseline, target = explicit[0][1], explicit[-1][1]
            else:
                baseline = explicit[-1][1]
    elif re.search(r"下一(?:个)?月|下个?月", query):
        target = shift_month(previous.target_month, 1)
    elif re.search(r"上一(?:个)?月|上个?月", query) and not compare:
        target = shift_month(previous.target_month, -1)
    else:
        target = previous.target_month if reference or compare else None
    if compare and baseline is None:
        if re.search(r"上(?:一|个)?月|环比", query):
            baseline = shift_month(target or fallback_month, -1)
        else:
            baseline = previous.target_month
    return ReportIntent(fields=fields, target_month=target, comparison_month=baseline,
                        compare=compare, limited=limited, invalid_month=invalid)


def resolve_report_intent(query: str, previous_queries: Iterable[str] = (), *,
                          known_fields: Iterable[str] = (), fallback_month: str | None = None,
                          previous_intent: ReportIntent | None = None) -> ReportIntent:
    """Resolve references against user instructions, excluding assistant prose.

    A saved intent may replace discarded user history. It remains a selector;
    only validated lookup results can supply its values.
    """
    fields = tuple(known_fields)
    intent = previous_intent or ReportIntent()
    for previous_query in previous_queries:
        if isinstance(previous_query, str):
            updated = _update(previous_query, intent, fields, fallback_month)
            if updated.fields or updated.target_month or updated.limited or updated.compare:
                intent = updated
    return _update(query, intent, fields, fallback_month)
