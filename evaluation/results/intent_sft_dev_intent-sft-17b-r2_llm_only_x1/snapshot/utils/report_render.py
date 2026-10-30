"""Render only verified lookup facts, with deterministic field selection/deltas."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
import re

from utils.report_intent import ReportIntent, canonical_field_name, resolve_report_intent, valid_month


def record_fields(data: Mapping[str, str]) -> dict[str, str]:
    """Read the human-readable CSV metrics without interpreting free prose."""
    fields = {}
    for section in ('效率', '耗材'):
        for line in str(data.get(section, '')).replace('\\n', '\n').splitlines():
            parts = re.split(r'[:：]', line, maxsplit=1)
            if len(parts) == 2 and parts[0].strip():
                fields[parts[0].strip()] = parts[1].strip()
    return fields


def _record_field_name(label: str, fields: Mapping[str, str]) -> str | None:
    percentage_fields = [field for field, value in fields.items()
                         if re.fullmatch(r'(?:剩余\s*)?[+-]?\d+(?:\.\d+)?\s*[%％]', value)]
    return canonical_field_name(label, fields, percentage_fields=percentage_fields)


def _validated_results(result: dict, lookup_results: Iterable[dict]):
    """Supplemental policy-checked results must have the same selected identity.

    These structure checks are defense in depth, not authorization of raw JSON.
    Callers may only provide records returned by policy-checked tool execution.
    """
    selected = result.get('user_id')
    by_month = {}
    for item in (*lookup_results, result):
        if not isinstance(item, dict) or item.get('user_id') != selected:
            continue
        month, status = item.get('month'), item.get('status')
        if not valid_month(month) or status not in ('ok', 'not_found'):
            continue
        if status == 'ok' and (not isinstance(item.get('data'), dict) or
                any(not isinstance(value, str) for value in item['data'].values())):
            continue
        by_month[month] = item
    return by_month


def _not_found(user_id: str, month: str) -> str:
    return (f'未找到演示用户 {user_id} 在 {month} 的使用记录，无法生成该月报告。'
            '请确认用户 ID 和月份。')


def _decimal_text(value: Decimal) -> str:
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _difference(before: str | None, after: str | None) -> str:
    if before is None or after is None:
        return '未提供，无法计算差值'
    # "Remaining" is a display qualifier for the recorded scalar, not a
    # forecast. Reject other prose rather than converting estimates to facts.
    numeric = re.compile(r'^(?:剩余\s*)?([+-]?\d+(?:\.\d+)?)\s*(%|％|㎡|m²|平方米|天|次(?:/周|/月|/日)?|个(?:/月|/周|/日)?|分钟|小时)$')
    old, new = numeric.fullmatch(before), numeric.fullmatch(after)
    if not old or not new:
        return '无法计算差值（记录不是单一可比数值）'
    old_unit, new_unit = old[2].replace('％', '%'), new[2].replace('％', '%')
    if old_unit != new_unit:
        return '无法计算差值（记录单位不同）'
    try:
        change = Decimal(new[1]) - Decimal(old[1])
    except InvalidOperation:
        return '无法计算差值'
    unit = '个百分点' if new_unit == '%' else new_unit
    amount = _decimal_text(abs(change)) + unit
    return ('增加' if change > 0 else '减少' if change < 0 else '不变：') + amount


def _cell(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def render_lookup(result: dict, *, query: str = '', previous_queries: Iterable[str] = (),
                  lookup_results: Iterable[dict] = (), intent: ReportIntent | None = None,
                  current_results: Iterable[dict] | None = None) -> str:
    """Render facts from policy-checked lookups, never LLM numeric conclusions.

    Legacy callers get a complete report. Current queries and prior user text
    select fields/months. Only verified tool records may support comparison;
    missing data never becomes zero or a model-estimated difference.
    """
    lookup_results = tuple(lookup_results)
    current_results = None if current_results is None else tuple(current_results)
    # Current-turn records can include the target before a later baseline
    # lookup. They also take precedence over committed historical values.
    by_month = _validated_results({'user_id': result.get('user_id')},
                                 (*lookup_results, result, *(current_results or ())))
    user_id, actual_month = result.get('user_id', ''), result.get('month', '')
    known_fields = tuple(dict.fromkeys(field for item in by_month.values()
                        if item['status'] == 'ok' for field in record_fields(item['data'])))
    if intent is None:
        intent = resolve_report_intent(query, previous_queries, known_fields=known_fields,
                                       fallback_month=actual_month)
    if intent.invalid_month:
        return '指定月份无效，无法查询或生成结论。请使用有效的 YYYY-MM 月份。'
    if intent.unresolved_month:
        return '无法确定相对月份的参照月份，不能猜测目标或比较月份。请提供有效的 YYYY-MM 月份。'
    month = intent.target_month or actual_month
    current_by_month = _validated_results(result, ()) if current_results is None else (
        _validated_results({'user_id': user_id}, current_results))
    current = current_by_month.get(month)
    if current is None:
        return f'本次未查询到所要求的 {month} 月记录，不能用其他月份的记录代替。'
    if current['status'] == 'not_found':
        return _not_found(user_id, month)
    data, fields = current['data'], intent.fields
    if intent.limited and not fields:
        return f'{month} 的记录已查询，但无法识别所限定的字段。请提供记录中的指标名称。'
    if fields or intent.compare:
        values = record_fields(data)
        fields = tuple(dict.fromkeys(_record_field_name(field, values) or field for field in fields)) or tuple(values)
        if intent.compare:
            baseline = by_month.get(intent.comparison_month)
            if not baseline or baseline['status'] != 'ok':
                lines = [f'{month}：', *(f'- {field}：{values.get(field, "未提供")}' for field in fields)]
                explanation = (f'未找到 {intent.comparison_month} 的比较记录' if baseline else
                               f'未查询到 {intent.comparison_month or "指定基准月份"} 的比较记录')
                return '\n'.join(lines) + f'\n\n{explanation}，无法计算变化；不会以零值代替缺失记录。'
            earlier = record_fields(baseline['data'])
            earlier_values = {field: earlier.get(_record_field_name(field, earlier)) for field in fields}
            lines = [f'演示用户 {user_id}，{month} 与 {intent.comparison_month} 比较：',
                     f'| 指标 | {intent.comparison_month} | {month} | 变化 |',
                     '| --- | --- | --- | --- |']
            lines.extend('| ' + ' | '.join(_cell(value) for value in (
                field, earlier_values.get(field) or '未提供', values.get(field, '未提供'),
                _difference(earlier_values.get(field), values.get(field)))) + ' |' for field in fields)
            return '\n'.join(lines)
        return '\n'.join([f'演示用户 {user_id}，{month}：',
                          *(f'- {field}：{values.get(field, "未提供")}' for field in fields)])
    sections = [("使用概况", "特征"), ("清洁表现", "效率"),
                ("耗材状态", "耗材"), ("使用对比", "对比")]
    parts = [f"# 扫地机器人 {month} 使用报告", f"演示用户：{user_id}"]
    for title, key in sections:
        value = data.get(key) or "未提供"
        lines = str(value).replace("\\n", "\n").splitlines()
        parts.append(f"## {title}\n" + "\n".join(f"- {line}" for line in lines))
    parts.append("以上为本地演示记录。未提供的指标不作推算；剩余寿命与比例不转换为未经记录支持的更换日期。")
    return "\n\n".join(parts)
