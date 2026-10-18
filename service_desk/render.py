
"""售后服务 Agent 的共用渲染器与文本守卫（纯函数，仅用标准库）。

本模块把一轮里的工具结果渲染成固定格式的“事实块”，把模型自己写的文字
按句过滤掉无依据的事实记号，并按子目标结果生成 plan 模式的结论句。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

__all__ = [
    "render_facts",
    "guard_text",
    "render_outcomes",
    "render_ask",
    "compose_answer",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

FULLWIDTH_MAP = {
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "％": "%",
}

AMOUNT_PATTERN = r"[0-9]+(?:\.[0-9]+)?\s*元|[0-9]+(?:\.[0-9]+)?\s*分"

TOKEN_PATTERNS = (
    re.compile(r"(?:[DTAOS]|SKU)-[A-Za-z0-9-]*[A-Za-z0-9]|E[0-9]{2}"),
    re.compile(r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}[日号]"),
    re.compile(r"[0-9]{1,2}月[0-9]{1,2}[日号]"),
    re.compile(r"[0-9]{1,2}:[0-9]{2}"),
    re.compile(AMOUNT_PATTERN),
    re.compile(r"[0-9]+(?:\.[0-9]+)?\s*%"),
    re.compile(r"[0-9]+(?:\.[0-9]+)?\s*(?:个工作日|工作日|小时|分钟|秒|周|天|个|件|次|㎡)"),
)

CLAIM_RE = re.compile(r"已(?:为你|帮你)?(?:预约|下单|取消|提交|创建|改约)")
NEGATION_WORDS = ("未", "尚未", "没有", "不会")

SENTENCE_RE = re.compile(r"[^。！？；\n]*[。！？；\n]|[^。！？；\n]+")

STATUS_CN = {
    "processing": "处理中",
    "completed": "已完成",
    "cancelled": "已取消",
    "scheduled": "已预约",
}

METRIC_CN = {
    "area_m2": ("清扫面积", "㎡"),
    "duration_min": ("清扫时长", "分钟"),
    "error_events": ("错误事件", "次"),
}

COMPONENT_ORDER = ("whole_machine", "battery", "consumables")

ACTION_CN = {"visit": "预约", "order": "订单", "change": "变更"}

OP_CN = {"<=": "不高于", "<": "低于", ">=": "不低于", ">": "高于"}

COMPONENT_CONDITION_CN = {"whole_machine": "整机在保", "battery": "电池在保"}

PROPOSAL_TAIL = "请在确认卡片上确认，确认前不会提交。"
ASK_FALLBACK = "请补充更多信息。"

WARRANTY_NOTE = "在保不代表一定免费，故障原因需服务人员检查。"
SELF_FIX_NOTE = "可以先按手册自查，自查后仍异常再申请上门。"
VISIT_NOTE = "不建议自行处理，需要服务人员上门检查。"

TZ_CN = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _to_halfwidth(text: object) -> str:
    """把全角数字、全角字母和常见全角符号转换成半角。

    全角标点（如逗号、冒号、分号）保持原样，避免改动面向用户的文字。
    """
    chars = []
    for ch in str(text):
        if ch in FULLWIDTH_MAP:
            chars.append(FULLWIDTH_MAP[ch])
            continue
        code = ord(ch)
        # 全角 ０-９、Ａ-Ｚ、ａ-ｚ
        if 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(ch)
    return "".join(chars)


def _compact(text: str) -> str:
    """去掉空格，用于“数字 + 单位”的记号比较。"""
    return re.sub(r"[ \t]+", "", text)


def _digits(value: object) -> str:
    """把整数常量（可能写成全角）转成半角数字字符串。"""
    return _to_halfwidth(value).strip()


def _num(value: object) -> str:
    """格式化数值：去掉多余的 .0。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _to_halfwidth(value)
    if number.is_integer():
        return str(int(number))
    return repr(round(number, 2))


def _num2(value: object) -> str:
    """格式化数值：固定保留两位小数。"""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return _to_halfwidth(value)


def _yuan(cents: object) -> str:
    """把金额从分换算成“x.xx 元”。"""
    try:
        return f"{int(cents) / 100:.2f} 元"
    except (TypeError, ValueError):
        return f"{_to_halfwidth(cents)} 元"


def _local_date(digits: str) -> str:
    """把 YYYYMMDD 或 YYYY-M-D 形式补零成 YYYY-MM-DD。"""
    parts = [p for p in re.split(r"[^0-9]+", digits) if p != ""]
    if len(parts) == 1 and len(parts[0]) == 8:
        return f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}"
    if len(parts) == 3:
        year, month, day = parts
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return digits


def _match_date_in_haystack(month: object, day: object, haystack: str) -> bool:
    """在来源文本里找某月某日，中文写法和连字符写法都算命中。"""
    month_text = str(int(month))
    day_text = str(int(day))
    if re.search(rf"{month_text}月{day_text}[日号]", haystack):
        return True
    return re.search(rf"(?:^|[^0-9])0?{month_text}-0?{day_text}(?![0-9])", haystack) is not None


def _match_full_date_in_haystack(year: object, month: object, day: object, haystack: str) -> bool:
    """在来源文本里找某年某月某日，中文写法和连字符写法都算命中。"""
    year_text = str(int(year))
    month_text = str(int(month))
    day_text = str(int(day))
    if re.search(rf"{year_text}年0?{month_text}月0?{day_text}[日号]", haystack):
        return True
    return re.search(rf"(?:^|[^0-9]){year_text}-0?{month_text}-0?{day_text}(?![0-9])", haystack) is not None


def _time_text(value: object) -> str:
    """把带时区的时间显示为“YYYY-MM-DD HH:MM”。"""
    raw = _to_halfwidth(value).strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", raw)
    if not match:
        return raw
    year, month, day, hour, minute = match.groups()
    if not re.search(r"(Z|[+-]\d{2}:?\d{2})$", raw):
        return f"{year}-{month}-{day} {hour}:{minute}"
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return f"{year}-{month}-{day} {hour}:{minute}"
    if moment.tzinfo is None:
        return f"{year}-{month}-{day} {hour}:{minute}"
    local = moment.astimezone(TZ_CN)
    return local.strftime("%Y-%m-%d %H:%M")


def _status_cn(status: object) -> str:
    """把状态码翻成中文，未知状态原样返回。"""
    text = _to_halfwidth(status).strip()
    return STATUS_CN.get(text, text)


def _sorted_args(args: object) -> str:
    """把工具参数规范化成可以比较的字符串（键排序、全角转半角）。"""
    try:
        return json.dumps(args, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return _to_halfwidth(args)


def _fact_key(result: dict) -> tuple:
    """去重用的键：工具名 + 规范化后的参数。"""
    tool = _to_halfwidth(result.get("tool") or "")
    return (tool, _to_halfwidth(_sorted_args(result.get("args") or {})))


def _date_input(value: object) -> str:
    """把日期入参转成日期文本（接受 dict 形式的原话取值）。"""
    if isinstance(value, dict):
        return _to_halfwidth(value.get("value", ""))
    return _to_halfwidth(value)


def _is_failure(payload: object) -> bool:
    """判断工具结果是否是失败结果。"""
    if not isinstance(payload, dict):
        return False
    if payload.get("status") in ("blocked", "denied", "error"):
        return True
    return payload.get("ok") is False


NUMBER_UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(个工作日|工作日|小时|分钟|秒|周|天|个|件|次|㎡|元|分|%)")

AMOUNT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(元|分)")

CENTS_FIELD_RE = re.compile(r'"([a-z_]*cents)":\s*(-?[0-9]+(?:\.[0-9]+)?)')


def _contains(text: str, needle: str) -> bool:
    """子串判断。"""
    if not needle:
        return True
    return text.find(needle) != -1


def _number_text(value: float) -> str:
    """把数值格式化成"去掉多余 .0"的文本。"""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _amount_text(number: str) -> str:
    """把金额规范化成"x.xx元"，便于按数值比较。"""
    return f"{float(number):.2f}元"


def _sentence_marks(text: str) -> list[str]:
    """从句子里抽出所有事实记号（已转半角、去掉记号内部的空格）。"""
    haystack = _to_halfwidth(text)
    marks: list[str] = []
    for pattern in TOKEN_PATTERNS:
        for match in pattern.findall(haystack):
            raw = _compact(match)
            if raw and not any(raw == existing for existing in marks):
                marks.append(raw)
    return marks


def _mark_supported(mark: str, haystack: str) -> bool:
    """判断一个事实记号是否能在允许来源里找到（两种日期写法等价）。"""
    if _contains(haystack, mark):
        return True
    amount = AMOUNT_RE.fullmatch(mark)
    if amount is not None:
        number, unit = amount.groups()
        if _contains(haystack, _amount_text(number)):
            return True
        # 工具结果里的 *_cents 字段除以 100 也是金额依据
        if unit == "元":
            cents = float(number) * 100
            for _field, raw in CENTS_FIELD_RE.findall(haystack):
                if float(raw) == cents:
                    return True
        else:
            for _field, raw in CENTS_FIELD_RE.findall(haystack):
                if float(raw) == float(number):
                    return True
        return False
    matched = NUMBER_UNIT_RE.fullmatch(mark)
    if matched is not None:
        number, unit = matched.groups()
        if _contains(haystack, _number_text(float(number)) + unit):
            return True
        if _contains(haystack, _number_text(float(number)) + " " + unit):
            return True
        # 面积在工具结果里是单独的数值字段，允许只比对数字
        return unit == "㎡" and _contains(haystack, _number_text(float(number)))
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?%", mark):
        return _contains(haystack, mark)
    if re.fullmatch(r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}", mark):
        year, month, day = mark.split("-")
        return _match_full_date_in_haystack(year, month, day, haystack)
    if re.fullmatch(r"[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}[日号]", mark):
        year, month, day = re.findall(r"[0-9]+", mark)
        return _match_full_date_in_haystack(year, month, day, haystack)
    if re.fullmatch(r"[0-9]{1,2}月[0-9]{1,2}[日号]", mark):
        month, day = re.findall(r"[0-9]+", mark)
        return _match_date_in_haystack(month, day, haystack)
    return False


# ---------------------------------------------------------------------------
# 事实块
# ---------------------------------------------------------------------------

def _fact_list_my_devices(payload: dict, _result: dict) -> str:
    """设备清单事实块。"""
    devices = payload.get("devices") or []
    parts = []
    for device in devices:
        parts.append(
            "{device_id}（{model_code} {display_name}，购买日期 {purchase_date}）".format(
                device_id=_to_halfwidth(device.get("device_id", "")),
                model_code=_to_halfwidth(device.get("model_code", "")),
                display_name=_to_halfwidth(device.get("display_name", "")),
                purchase_date=_date_input(device.get("purchase_date", "")),
            )
        )
    if not parts:
        return "没有查到你的设备。"
    return "你的设备：" + "；".join(parts) + "。"


def _fact_lookup_error_code(payload: dict, result: dict) -> str:
    """错误码事实块。"""
    status = _to_halfwidth(payload.get("status", "")).strip()
    if status == "clarify":
        return _to_halfwidth(payload.get("message", ""))
    if status == "not_found" or not payload.get("definitions"):
        args = result.get("args") or {}
        model = _to_halfwidth(args.get("model_code") or args.get("model") or "").strip()
        model = model or "该设备"
        code = _to_halfwidth(args.get("code") or "").strip()
        return f"型号 {model} 没有错误码 {code} 的定义，请核对屏幕上的编号。"
    parts = []
    for definition in payload.get("definitions") or []:
        tail = SELF_FIX_NOTE if definition.get("self_fixable") else VISIT_NOTE
        parts.append(
            "错误码 {code}（{model}）：{title}。严重程度 {severity}；{tail}".format(
                code=_to_halfwidth(definition.get("code", "")),
                model=_to_halfwidth(definition.get("model_code", "")),
                title=_to_halfwidth(definition.get("title", "")),
                severity=_num(definition.get("severity")),
                tail=tail,
            )
        )
    return "；".join(parts)


def _fact_check_warranty(payload: dict, _result: dict) -> str:
    """保修事实块。"""
    device_id = _to_halfwidth(payload.get("device_id", ""))
    business_date = _date_input(payload.get("business_date", ""))
    coverage = {
        _to_halfwidth(item.get("component", "")): item
        for item in payload.get("coverage") or []
    }
    parts = []
    any_in_warranty = False
    for component in COMPONENT_ORDER:
        item = coverage.get(component)
        if item is None:
            continue
        name = {"whole_machine": "整机", "battery": "电池", "consumables": "耗材"}[component]
        if item.get("in_warranty"):
            any_in_warranty = True
            parts.append(f"{name}在保，到期日 {_date_input(item.get('expires_date', ''))}")
        elif component == "consumables":
            reason = _to_halfwidth(item.get("reason") or "").strip().rstrip("。；;")
            parts.append(reason or "耗材正常磨损不在保")
        else:
            parts.append(f"{name}已过保，到期日 {_date_input(item.get('expires_date', ''))}")
    text = f"保修（{device_id}，以 {business_date} 为准）：" + "；".join(parts) + "。"
    if any_in_warranty:
        text += WARRANTY_NOTE
    return text


def _fact_rag_summarize(payload: dict, _result: dict) -> str:
    """资料说明事实块，保留 answer 原文的换行。"""
    return "资料说明：" + str(payload.get("answer", ""))


def _fact_get_daily_usage(payload: dict, _result: dict) -> str:
    """用量统计事实块。"""
    metric = _to_halfwidth(payload.get("metric", "")).strip()
    name, unit = METRIC_CN.get(metric, ("用量", ""))
    if unit in ("㎡", "分钟", "次"):
        unit = " " + unit
    return (
        "{device_id} 在 {start} 至 {end}（有记录 {days} 天）："
        "{name}合计 {total}{unit}，日均 {average}{unit}，最大 {maximum}{unit}。"
    ).format(
        device_id=_to_halfwidth(payload.get("device_id", "")),
        start=_date_input(payload.get("start", "")),
        end=_date_input(payload.get("end", "")),
        days=_num(payload.get("days_observed")),
        name=name,
        total=_num(payload.get("total")),
        average=_num2(payload.get("daily_average")),
        maximum=_num(payload.get("maximum")),
        unit=unit,
    )


def _fact_find_service_slots(payload: dict, _result: dict) -> str:
    """可约时段事实块。"""
    slots = payload.get("slots") or []
    if not slots:
        return "未查到可约时段。"
    parts = []
    for index, slot in enumerate(slots, start=1):
        start_at = _time_text(slot.get("start_at", ""))
        end_at = _time_text(slot.get("end_at", ""))
        start_text = start_at
        end_text = end_at
        if len(start_at) >= 16 and start_at[:10] == end_at[:10]:
            end_text = end_at[11:]
        parts.append(f"{index}）{start_text}–{end_text}（剩余 {_num(slot.get('available'))}）")
    return "可约时段：" + "；".join(parts) + "。"


def _fact_find_consumables(payload: dict, _result: dict) -> str:
    """耗材清单事实块。"""
    parts = []
    for item in payload.get("consumables") or []:
        stock = item.get("stock", 0)
        try:
            in_stock = float(stock) > 0
        except (TypeError, ValueError):
            in_stock = bool(stock)
        text = "{sku} {name}，{price}，".format(
            sku=_to_halfwidth(item.get("sku", "")),
            name=_to_halfwidth(item.get("name", "")),
            price=_yuan(item.get("price_cents")),
        )
        if in_stock:
            text += f"库存 {_num(stock)}"
            if item.get("max_per_order") is not None:
                text += f"，单次限购 {_num(item.get('max_per_order'))}"
        else:
            text += "缺货"
        parts.append(text)
    if not parts:
        return "没有查到兼容耗材。"
    return "兼容耗材：" + "；".join(parts) + "。"


def _fact_get_my_orders_and_tickets(payload: dict, _result: dict) -> str:
    """订单、工单和预约记录事实块。"""
    records = payload.get("records") or []
    if not records:
        return "没有查到相关记录。"
    parts = []
    for record in records:
        kind = _to_halfwidth(record.get("kind", "")).strip()
        record_id = _to_halfwidth(record.get("id", ""))
        status = _status_cn(record.get("status"))
        if kind == "order":
            parts.append(
                f"订单 {record_id}：{_to_halfwidth(record.get('sku', ''))} × "
                f"{_num(record.get('qty'))}，{_yuan(record.get('amount_cents'))}，{status}。"
            )
        elif kind == "ticket":
            parts.append(f"工单 {record_id}：{_ticket_subject(record)}，{status}。")
        elif kind == "appointment":
            parts.append(
                f"预约 {record_id}：时段 {_to_halfwidth(record.get('slot_id', ''))}，{status}。"
            )
        else:
            parts.append(f"{record_id}：{status}。")
    return "".join(parts)


def _ticket_subject(record: dict) -> str:
    """工单的要点：有错误码写错误码，没有就用描述前 30 个字。"""
    error_code = record.get("error_code")
    if error_code:
        return _to_halfwidth(error_code)
    description = _to_halfwidth(record.get("description") or "").strip()
    if not description:
        return "无错误码"
    clipped = description[:30]
    return clipped + "…" if len(description) > 30 else clipped


def _fact_proposal(payload: dict, _result: dict) -> str:
    """待确认卡片的说明。"""
    summary = _to_halfwidth(payload.get("summary", ""))
    expires = _time_text(payload.get("expires_at", ""))
    return f"待确认：{summary}（有效期至 {expires}）。"


FACT_RENDERERS = {
    "list_my_devices": _fact_list_my_devices,
    "lookup_error_code": _fact_lookup_error_code,
    "check_warranty": _fact_check_warranty,
    "rag_summarize": _fact_rag_summarize,
    "get_daily_usage": _fact_get_daily_usage,
    "find_service_slots": _fact_find_service_slots,
    "find_consumables": _fact_find_consumables,
    "get_my_orders_and_tickets": _fact_get_my_orders_and_tickets,
    "propose_service_visit": _fact_proposal,
    "propose_order": _fact_proposal,
    "propose_change": _fact_proposal,
}

SKIPPED_TOOLS = {"fetch_external_data"}


def render_facts(results: list[dict]) -> list[str]:
    """按输入顺序为每个工具结果生成一个事实块的字符串。

    相同的 (tool, 规范化后的 args) 只保留第一次；fetch_external_data 跳过；
    失败结果直接输出 message。
    """
    facts: list[str] = []
    unique: dict[tuple, dict] = {}
    for result in results or []:
        key = _fact_key(result or {})
        previous = unique.get(key)
        # Verification may recover a failed read. Keep its successful evidence
        # at the original call position instead of hiding it behind the failure.
        if previous is None or (_is_failure(previous.get('payload'))
                                and not _is_failure((result or {}).get('payload'))):
            unique[key] = result or {}
    for result in unique.values():
        tool = _to_halfwidth((result or {}).get("tool") or "")
        if tool in SKIPPED_TOOLS:
            continue
        payload = (result or {}).get("payload") or {}
        if _is_failure(payload):
            facts.append(_to_halfwidth(payload.get("message", "")))
            continue
        renderer = FACT_RENDERERS.get(tool)
        if renderer is None:
            continue
        facts.append(renderer(payload, result or {}))
    return facts


# ---------------------------------------------------------------------------
# 文本守卫
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """按句号、叹号、问号、分号和换行切句，保留原标点。"""
    return [part for part in SENTENCE_RE.findall(text) if part]


def guard_text(text: str, sources: list[str]) -> tuple[str, list[str]]:
    """过滤掉没有依据的事实句和谎称已完成的写操作句。

    返回（保留文本, 被删句子列表）。事实记号必须出现在某个 source 里；
    命中完成声明（前面没有否定词）时整句删除。
    """
    normalized = _to_halfwidth(text or "")
    haystack = _compact(_to_halfwidth("\n".join(str(item) for item in (sources or []))))
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in _split_sentences(normalized):
        if any(not _mark_supported(mark, haystack) for mark in _sentence_marks(sentence)):
            dropped.append(sentence)
            continue
        claim = CLAIM_RE.search(sentence)
        if claim is not None and not any(word in sentence[: claim.start()] for word in NEGATION_WORDS):
            dropped.append(sentence)
            continue
        kept.append(sentence)
    return "".join(kept), dropped


# ---------------------------------------------------------------------------
# plan 模式的结论句
# ---------------------------------------------------------------------------

def _describe_condition(condition: object) -> str:
    """把条件渲染成中文描述。"""
    if not isinstance(condition, dict):
        return ""
    kind = _to_halfwidth(condition.get("type", "")).strip()
    if kind == "warranty_in_force":
        return COMPONENT_CONDITION_CN.get(_to_halfwidth(condition.get("component", "")), "")
    if kind == "record_threshold":
        month = _to_halfwidth(condition.get("month", ""))
        field = _to_halfwidth(condition.get("field_hint", ""))
        op = OP_CN.get(_to_halfwidth(condition.get("op", "")), _to_halfwidth(condition.get("op", "")))
        value = _num(condition.get("value"))
        unit = _to_halfwidth(condition.get("unit", ""))
        return f"{month} {field} {op} {value}{unit}".strip()
    return ""


def render_outcomes(outcomes: list[dict]) -> list[str]:
    """按子目标结果生成 plan 模式的结论句列表（done 不输出句子）。"""
    sentences: list[str] = []
    for outcome in outcomes or []:
        status = _to_halfwidth((outcome or {}).get("status", "")).strip()
        action = ACTION_CN.get(_to_halfwidth((outcome or {}).get("action") or ""), "")
        if status == "proposed":
            sentences.append(f"已为你准备{action}的确认卡片。")
        elif status == "condition_false":
            sentences.append(
                f"按你的要求（{_describe_condition(outcome.get('condition'))}），"
                f"条件不成立，未生成{action}卡片。"
            )
        elif status == "condition_unknown":
            sentences.append(
                f"无法判断你的条件（{_describe_condition(outcome.get('condition'))}）"
                f"是否成立，未生成{action}卡片。"
            )
        elif status == "precheck_failed":
            sentences.append(f"{_to_halfwidth(outcome.get('reason') or '')}，未生成{action}卡片。")
        elif status == "slot_unavailable":
            sentences.append("你指定的时段没有可约名额，未生成预约卡片。")
        elif status == "missing":
            sentences.append(f"未能完成：{_to_halfwidth(outcome.get('goal_text') or '')}。")
    return sentences


def render_ask(ask: dict, results: list[dict]) -> str:
    """渲染需要用户补充信息的提问。"""
    ask = ask or {}
    kind = _to_halfwidth(ask.get("type", "")).strip()
    if kind == "which_device":
        devices: list[str] = []
        for result in results or []:
            if _to_halfwidth((result or {}).get("tool") or "") != "list_my_devices":
                continue
            payload = (result or {}).get("payload") or {}
            for device in payload.get("devices") or []:
                devices.append(
                    "{device_id}（{model_code}）".format(
                        device_id=_to_halfwidth(device.get("device_id", "")),
                        model_code=_to_halfwidth(device.get("model_code", "")),
                    )
                )
        return f"你有多台设备：{'；'.join(devices)}。请问是哪一台？"
    if kind == "which_slot":
        return "请从下面的可约时段里选一个。"
    if kind == "quantity":
        return "请告诉我需要的数量。"
    kept, _dropped = guard_text(
        _to_halfwidth(ask.get("text", "")),
        [json.dumps((result or {}).get("payload") or {}, ensure_ascii=False) for result in results or []],
    )
    return kept.strip() or ASK_FALLBACK


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def _has_successful_proposal(results: list[dict]) -> bool:
    """判断本轮是否有成功的写操作提议。"""
    for result in results or []:
        tool = _to_halfwidth((result or {}).get("tool") or "")
        if tool not in ("propose_service_visit", "propose_order", "propose_change"):
            continue
        payload = (result or {}).get("payload") or {}
        if not _is_failure(payload):
            return True
    return False


def _join_blocks(blocks: list[str]) -> str:
    """用空行拼接非空内容块，结尾不留多余空行。"""
    return "\n\n".join(block for block in blocks if block)


def compose_answer(
    *,
    mode: str,
    results: list[dict],
    model_text: str | None = None,
    outcomes: list[dict] | None = None,
    ask: dict | None = None,
    report_text: str | None = None,
    sources: list[str] = (),
) -> str:
    """按模式组装最终回答：结论说明 + 月度报告 + 事实块 + 固定结尾句。"""
    fact_blocks = render_facts(results)
    # A ReAct turn can read again after proposing. Keep card explanations last
    # without changing the call order supplied to render_facts or its deduplication.
    facts_text = "\n".join([b for b in fact_blocks if not b.startswith("待确认：")]
                           + [b for b in fact_blocks if b.startswith("待确认：")])
    source_texts = list(sources or [])
    source_texts.extend(
        json.dumps((result or {}).get("payload") or {}, ensure_ascii=False)
        for result in results or []
    )
    if report_text:
        source_texts.append(str(report_text))
    if facts_text:
        source_texts.append(facts_text)
    if _to_halfwidth(mode or "").strip() == "plan":
        ask_text = render_ask(ask, results) if ask else ""
        outcome_text = "".join(render_outcomes(outcomes or []))
        head = "\n".join(part for part in (ask_text, outcome_text) if part)
        blocks = [head]
    else:
        kept, _dropped = guard_text(_to_halfwidth(model_text or ""), source_texts)
        blocks = [kept.strip()]
    if report_text:
        blocks.append(str(report_text).strip())
    blocks.append(facts_text)
    answer = _join_blocks(blocks)
    if _has_successful_proposal(results):
        answer = (answer + "\n" + PROPOSAL_TAIL) if answer else PROPOSAL_TAIL
    return answer
