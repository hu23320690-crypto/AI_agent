"""Answer explicit record/measurement boundary questions without model prose.

Callers must supply only policy-checked lookup results and revalidated source
documents. This module interprets numeric evidence; it grants no identity or
source authorization, and never diagnoses hardware from a similar field name.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import re

from utils.report_render import record_fields


_ASK = re.compile(r'能否|是否|能不能|可否|可以|足以|能.*(?:证明|判断|确认)')
_JUDGMENT = re.compile(r'证明|证实|确认|认定|判断|门槛|阈值|条件|达标|合格|满足')
_OPERATORS = {
    '低于': '<', '小于': '<', '不足': '<', '少于': '<',
    '高于': '>', '大于': '>', '超过': '>', '多于': '>',
    '不低于': '>=', '不少于': '>=', '至少': '>=', '达到': '>=',
    '不高于': '<=', '不超过': '<=', '最多': '<=',
    '等于': '==', '为': '==', '是': '==',
    '以下': '<=', '以上': '>=',
    '>=': '>=', '<=': '<=', '≥': '>=', '≤': '<=', '>': '>', '<': '<',
}
_OP = '|'.join(sorted(_OPERATORS, key=len, reverse=True))
_UNIT = r'%|％|分钟|小时|天|㎡|m²|平方米|次(?:/周|/月|/日)?|个(?:/月|/周|/日)?'
_VALUE = re.compile(rf'^(?:剩余)?\s*(\d+(?:\.\d+)?)\s*({_UNIT})$')
_BASELINE = r'原始|最初|初始|基准|原'
_CURRENT = r'当前|实际|本次|现'


def _measurement(value):
    if not isinstance(value, str):
        return None
    match = _VALUE.fullmatch(value.strip())
    if not match:
        return None
    try:
        amount = Decimal(match[1])
    except InvalidOperation:
        return None
    unit = match[2].replace('％', '%').replace('m²', '㎡').replace('平方米', '㎡')
    return amount, unit


def _compare(value, operator, threshold):
    return {'<': value < threshold, '>': value > threshold,
            '<=': value <= threshold, '>=': value >= threshold,
            '==': value == threshold}[operator]


def _compatible(value, threshold):
    left, right = value
    amount, unit = threshold
    if right == unit:
        return left, amount
    # This is an explicit unit conversion, not a change in metric semantics.
    time_scale = {'分钟': Decimal(1), '小时': Decimal(60), '天': Decimal(1440)}
    if right in time_scale and unit in time_scale:
        return left * time_scale[right], amount * time_scale[unit]
    return None


def _decision_scope(query):
    # Do not mistake the report's preceding requested field list for the
    # quantity in a separate judgment question (e.g. battery loss vs runtime).
    sentences = re.split(r'[。；;？?\n]', query)
    selected = [part for part in sentences if _ASK.search(part) and
                (_JUDGMENT.search(part) or re.search(rf'(?:{_OP})\s*\d', part))]
    return '；'.join(selected)


def _quantity_name(text):
    """Keep the whole named quantity, removing only question grammar.

    Object/region qualifiers (e.g. a particular reservoir or corner) are part
    of the metric. They must never be dropped to find a shorter record label.
    """
    text = re.split(r'[，,:：。；;\n]', text)[-1].strip()
    text = re.sub(r'^\d+[.、)）]\s*', '', text)
    for _ in range(4):
        predicates = list(re.finditer(
            r'(?:能否|是否|能不能|可否|可以|足以)(?:直接|据此)?'
            r'(?:证明|证实|确认|认定|判断|说明)?', text))
        if not predicates:
            break
        last = predicates[-1]
        tail = text[last.end():].strip()
        tail = re.split(rf'(?:{_OP})\s*(?=\d)|(?:已经|已)?(?:达到|满足|符合|通过|达标|合格|低于|高于|小于|大于|不低于|不高于|超过|不超过)', tail)[0]
        text = tail.strip() or text[:last.start()].strip()
    text = re.sub(r'^(?:若|当|如果|我的|我|这些记录中的|记录中的|数据中的|本月|当月|本次|当前|实际)\s*', '', text)
    text = re.sub(r'(?:已经|已|应|需|要|必须|的数值|数值|为|是|在|的)$', '', text).strip()
    return text


def _same_quantity(name, field, value):
    # The displayed "remaining" value explicitly permits that same modifier
    # in its label. No component, region or denominator aliases are inferred.
    if value.startswith('剩余'):
        name = name.replace('剩余', '')
        field = field.replace('剩余', '')
    return name == _quantity_name(field)


def _scope_names(scope):
    return tuple(_quantity_name(part) for part in re.split(r'[；;]', scope) if part.strip())


def _condition(text, field, value):
    # Parse the complete condition quantity before matching the record field.
    # A substring search would let "coverage" authorize "corner coverage".
    before = re.compile(rf'(?P<op>{_OP})\s*(?P<n>\d+(?:\.\d+)?)\s*(?P<u>{_UNIT})')
    after = re.compile(rf'(?P<n>\d+(?:\.\d+)?)\s*(?P<u>{_UNIT})(?P<op>以下|以上)')
    for pattern in (after, before):
        for match in pattern.finditer(text):
            name = _quantity_name(text[:match.start()])
            if _same_quantity(name, field, value):
                literal = name + match[0]
                return _OPERATORS[match['op']], (Decimal(match['n']), match['u'].replace('％', '%')), literal
    return None


def _relative_condition(text, fields, *, allowed_quantities):
    # Only explicit current/baseline fields of the same named quantity permit
    # a percentage of an original value. "battery loss" is not "runtime".
    for current_field, current_value in fields.items():
        prefix = re.match(rf'^(?:{_CURRENT})(.+)$', current_field)
        if not prefix:
            continue
        quantity = prefix[1]
        # Bind this very comparison to the user's requested quantity. Having
        # some other current field in scope cannot authorize a source's rule.
        if _quantity_name(quantity) not in allowed_quantities or quantity not in text:
            continue
        for baseline_field, baseline_value in fields.items():
            if not re.fullmatch(rf'(?:{_BASELINE}){re.escape(quantity)}', baseline_field):
                continue
            match = re.search(rf'(?P<op>衰减至|降低至|降至|减少至|{_OP})'
                              rf'(?P<baseline>(?:{_BASELINE})[^，,。；;\d%％]{{1,40}}?)的?\s*'
                              rf'(?P<n>\d+(?:\.\d+)?)\s*[%％](?P<post>以下|以上)?', text)
            if (not match or _quantity_name(text[:match.start()]) != quantity
                    or re.sub(rf'^(?:{_BASELINE})', '', match['baseline']).rstrip('的') != quantity):
                continue
            measured, baseline = _measurement(current_value), _measurement(baseline_value)
            if measured is None or baseline is None:
                continue
            comparable = _compatible(measured, baseline)
            if comparable is None or comparable[1] <= 0:
                continue
            ratio = comparable[0] / comparable[1] * 100
            literal = quantity + match[0]
            operator = ('<=' if match['post'] == '以下' else '>=' if match['post'] == '以上' else
                        _OPERATORS.get(match['op']))
            if operator is None:
                continue
            threshold = Decimal(match['n'])
            holds = _compare(ratio, operator, threshold)
            return (f'同量数值比较：{current_field}为{current_value}，{baseline_field}为{baseline_value}；'
                    f'按“{literal}”的条件，记录数值{"满足" if holds else "不满足"}该门槛。'
                    '这只是这些测量值与给定条件的比较，不代表其他故障或设备安全状态已通过检测。')
    return None


def record_evidence_reply(query: str, lookup_result, *, source_documents=()) -> str | None:
    """Return an evidence-bound reply for a clearly requested judgment subtask.

    Exact comparable recorded measurements may establish an explicit numeric
    condition. A missing metric, undefined ratio basis or merely similar label
    yields an information boundary, not a positive or negative diagnosis.
    """
    if not isinstance(query, str):
        return None
    scope = _decision_scope(query)
    if not scope:
        return None
    if (not isinstance(lookup_result, Mapping) or lookup_result.get('status') != 'ok'
            or not isinstance(lookup_result.get('data'), Mapping)
            or any(not isinstance(value, str) for value in lookup_result['data'].values())):
        return None
    fields = record_fields(lookup_result['data'])
    scope_names = _scope_names(scope)
    sources = [scope]
    # Sources are optional, bounded evidence, never model conclusions or
    # conversation summaries. The calling runtime revalidates them at commit.
    for document in list(source_documents)[:8]:
        text = getattr(document, 'page_content', None)
        if isinstance(text, str) and len(text) <= 8192:
            sources.extend(part for part in re.split(r'[。；;\n]', text) if part.strip())
    replies = []
    for field, value in fields.items():
        measured = _measurement(value)
        if measured is None or not any(_same_quantity(name, field, value) for name in scope_names):
            continue
        for text in sources:
            condition = _condition(text, field, value)
            if condition is None:
                continue
            operator, threshold, literal = condition
            comparable = _compatible(measured, threshold)
            if comparable is None:
                continue
            holds = _compare(comparable[0], operator, comparable[1])
            replies.append(f'{field}记录为{value}；按“{literal}”的条件，'
                           f'该字段的数值{"满足" if holds else "不满足"}。')
            break
    if replies:
        return '同量数值比较：\n' + '\n'.join(replies) + '\n这仅确认所列字段的数值关系，不替代其他设备状态检测。'
    for text in sources:
        # A source threshold also needs the same quantity explicitly named in
        # the user's decision question. Unrelated historical rules are ignored.
        relative = _relative_condition(text, fields, allowed_quantities=scope_names)
        if relative is not None:
            return relative
    return ('这些月记录只能支持已列出的指标值，尚不足以确认所问门槛或设备状态。'
            '判断需要与该条件对应的同量测量和明确的指标定义；'
            '若条件涉及相对基准，还需对应的原始值/当前值。'
            '不能把不同名称的指标或缺少基准的比例直接当作同一个量，'
            '也不能据此确定已经达到或尚未达到维修、更换等条件。')
