# 由 DeepSeek 协助编写。
"""售后服务 Agent 的计划模型、校验、参数解析、条件判断和写操作预检。

planner（小模型）只声明"要做什么、查哪些工具、参数从哪里来"，本模块负责
把这些声明按确定性规则校验、解析和检查，确保模型不写任何编号的字面值。
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

__all__ = [
    "TOOLS",
    "WRITE_TOOLS",
    "Plan",
    "Goal",
    "Step",
    "plan_json_schema",
    "normalize_text",
    "parse_date",
    "parse_month",
    "parse_time",
    "parse_number",
    "validate_plan",
    "normalize_plan",
    "resolve_args",
    "evaluate_condition",
    "precheck",
]

# ---------------------------------------------------------------------------
# 工具清单
# ---------------------------------------------------------------------------

TOOLS = {
    "list_my_devices": {"params": {}, "required": []},
    "lookup_error_code": {
        "params": {"code": {"type": "string"}, "device_id": {"type": "string"}},
        "required": ["code"],
    },
    "check_warranty": {
        "params": {
            "device_id": {"type": "string"},
            "component": {"type": "string", "enum": ["whole_machine", "battery", "consumables"]},
        },
        "required": ["device_id"],
    },
    "rag_summarize": {
        "params": {"query": {"type": "string"}, "device_id": {"type": "string"}},
        "required": ["query"],
    },
    "fetch_external_data": {"params": {"month": {"type": "string"}}, "required": ["month"]},
    "get_daily_usage": {
        "params": {
            "device_id": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "metric": {"type": "string", "enum": ["area_m2", "duration_min", "error_events"]},
        },
        "required": ["device_id", "start", "end", "metric"],
    },
    "find_service_slots": {
        "params": {
            "device_id": {"type": "string"},
            "from_date": {"type": "string"},
            "days": {"type": "integer"},
        },
        "required": ["device_id"],
    },
    "find_consumables": {
        "params": {
            "device_id": {"type": "string"},
            "kind": {
                "type": "string",
                "enum": [
                    "main_brush",
                    "side_brush",
                    "rubber_brush",
                    "filter",
                    "mop_pad",
                    "dust_bag",
                ],
            },
        },
        "required": ["device_id"],
    },
    "get_my_orders_and_tickets": {
        "params": {
            "kind": {"type": "string", "enum": ["order", "ticket", "appointment"]},
            "id": {"type": "string"},
        },
        "required": [],
    },
    "propose_service_visit": {
        "params": {
            "device_id": {"type": "string"},
            "error_code": {"type": "string"},
            "description": {"type": "string"},
            "slot_id": {"type": "string"},
        },
        "required": ["device_id", "description", "slot_id"],
    },
    "propose_order": {
        "params": {
            "device_id": {"type": "string"},
            "sku": {"type": "string"},
            "qty": {"type": "integer"},
        },
        "required": ["device_id", "sku", "qty"],
    },
    "propose_change": {
        "params": {
            "target_id": {"type": "string"},
            "change": {
                "type": "string",
                "enum": ["reschedule", "cancel_appointment", "cancel_order"],
            },
            "new_slot_id": {"type": "string"},
        },
        "required": ["target_id", "change"],
    },
}

WRITE_TOOLS = {"propose_service_visit", "propose_order", "propose_change"}

GOAL_TYPES = (
    "diagnose", "warranty", "knowledge", "report", "usage",
    "slots", "consumables", "status", "book", "order", "change",
)

GOAL_WRITE_TOOL = {
    "book": "propose_service_visit",
    "order": "propose_order",
    "change": "propose_change",
}

PICK_TOOL = {
    "only_device": "list_my_devices",
    "device_matching": "list_my_devices",
    "slot_at": "find_service_slots",
    "consumable_kind": "find_consumables",
    "record": "get_my_orders_and_tickets",
}

CONDITION_TOOL = {
    "warranty_in_force": "check_warranty",
    "record_threshold": "fetch_external_data",
}

# 每个参数允许的参数来源种类
PARAM_SOURCE_KINDS = {
    "device_id": {"device", "value", "pending"},
    "slot_id": {"slot", "pending"},
    "new_slot_id": {"slot", "pending"},
    "sku": {"consumable", "pending"},
    "target_id": {"record", "value"},
    "description": {"text", "pending"},
    "code": {"value", "pending"},
    "error_code": {"value", "pending"},
    "start": {"value", "pending"},
    "end": {"value", "pending"},
    "from_date": {"value", "pending"},
    "month": {"value", "pending"},
    "qty": {"value", "pending"},
    "days": {"value", "pending"},
    "id": {"value", "record", "pending"},
    "query": {"free_text", "text", "value", "pending"},
    "kind": {"value", "enum", "pending"},
    "metric": {"value", "enum", "pending"},
    "component": {"value", "enum", "pending"},
    "change": {"value", "enum", "pending"},
}

VALUE_PARSERS = {
    "start": "date",
    "end": "date",
    "from_date": "date",
    "month": "month",
}

# 用 parse_number 复算的参数
NUMBER_PARAMS = {"qty", "days"}

# 编号类参数：value 必须原样出现在 evidence 里
ID_PARAMS = {"id", "target_id", "device_id"}

CONDITION_OPS = {
    "<=": lambda left, right: left <= right,
    "<": lambda left, right: left < right,
    ">=": lambda left, right: left >= right,
    ">": lambda left, right: left > right,
}

# ---------------------------------------------------------------------------
# 规范化：全角转半角、中文数字
# ---------------------------------------------------------------------------

CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10,
}

FULLWIDTH_MAP = {"％": "%", "．": ".", "－": "-"}

CN_NUMBER_RE = re.compile(
    r"十[一二三四五六七八九]?|[零一二两三四五六七八九]十[零一二两三四五六七八九]?|[零一二两三四五六七八九]"
)


def _cn_number_to_int(text: str) -> int | None:
    """把一个中文数字（一到十二、两、二十以内）转成整数。"""
    if text in ("十", "一十"):
        return 10
    if text.startswith("十") and len(text) == 2:
        return 10 + CN_DIGITS.get(text[1], 0)
    if len(text) == 2 and text[1] == "十":
        return CN_DIGITS.get(text[0], 0) * 10
    if len(text) == 3 and text[1] == "十":
        return CN_DIGITS.get(text[0], 0) * 10 + CN_DIGITS.get(text[2], 0)
    if text in CN_DIGITS:
        return CN_DIGITS[text]
    return None


def normalize_text(text: Any) -> str:
    """全角转半角，并把一到十二的中文数字（含"两"）换成阿拉伯数字。"""
    chars: list[str] = []
    for ch in str(text if text is not None else ""):
        if ch in FULLWIDTH_MAP:
            chars.append(FULLWIDTH_MAP[ch])
            continue
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(ch)
    return CN_NUMBER_RE.sub(lambda match: str(_cn_number_to_int(match.group(0))), "".join(chars))


# ---------------------------------------------------------------------------
# 规范化：日期、月份、时间、数量
# ---------------------------------------------------------------------------

RELATIVE_DATES = {"大后天": 3, "后天": 2, "明天": 1, "今天": 0}


def _numbered_regex(year: str, require_day: bool = False) -> re.Pattern:
    """构造"年月日 + 以空格分隔的数字"的正则。"""
    day = r"[日号]" if require_day else r"[日号]?"
    prefix = rf"{year}\s*年\s*" if year else ""
    return re.compile(rf"{prefix}([0-9]+)\s*月\s*([0-9]+)\s*{day}")


def parse_date(evidence: Any, business_date: Any) -> str | None:
    """把原话里的日期表达解析成 YYYY-MM-DD，解析不了返回 None。"""
    if evidence is None:
        return None
    text = normalize_text(evidence).strip()
    if not text:
        return None
    try:
        base = date.fromisoformat(str(business_date).strip()[:10])
    except (TypeError, ValueError):
        return None
    for word, offset in RELATIVE_DATES.items():
        if text.find(word) != -1:
            return (base + timedelta(days=offset)).isoformat()
    matched = re.search(r"([0-9]{4})\s*[-/]\s*([0-9]{1,2})\s*[-/]\s*([0-9]{1,2})", text)
    if matched:
        year, month, day = int(matched.group(1)), int(matched.group(2)), int(matched.group(3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    matched = _numbered_regex(r"([0-9]{4})").search(text)
    if matched:
        year, month, day = int(matched.group(1)), int(matched.group(2)), int(matched.group(3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    matched = _numbered_regex(r"", require_day=True).search(text)
    if matched:
        month, day = int(matched.group(1)), int(matched.group(2))
        try:
            return date(base.year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """按月份偏移，返回（年, 月）。"""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def parse_month(evidence: Any, business_date: Any) -> str | None:
    """把原话里的月份表达解析成 YYYY-MM，解析不了返回 None。"""
    if evidence is None:
        return None
    text = normalize_text(evidence).strip()
    if not text:
        return None
    try:
        base = date.fromisoformat(str(business_date).strip()[:10])
    except (TypeError, ValueError):
        return None
    if _contains(text, "上个月") or _contains(text, "上月"):
        year, month = _shift_month(base.year, base.month, -1)
        return f"{year:04d}-{month:02d}"
    if _contains(text, "下个月") or _contains(text, "下月"):
        year, month = _shift_month(base.year, base.month, 1)
        return f"{year:04d}-{month:02d}"
    if _contains(text, "这个月") or _contains(text, "本月") or _contains(text, "当月"):
        return f"{base.year:04d}-{base.month:02d}"
    matched = re.search(r"([0-9]{4})\s*[-/年]\s*([0-9]{1,2})\s*月?", text)
    if matched:
        year, month = int(matched.group(1)), int(matched.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
        return None
    matched = re.search(r"([0-9]{1,2})\s*月", text)
    if matched:
        month = int(matched.group(1))
        if not 1 <= month <= 12:
            return None
        year = base.year if month <= base.month else base.year - 1
        return f"{year:04d}-{month:02d}"
    return None


def parse_time(evidence: Any) -> str | None:
    """把原话里的时间表达解析成 HH:MM，解析不了返回 None。"""
    if evidence is None:
        return None
    text = normalize_text(evidence).strip()
    if not text:
        return None

    def with_period(hour: int, marker: str) -> int:
        if marker in ("下午", "晚上") and hour < 12:
            return hour + 12
        return hour

    matched = re.search(r"(上午|下午|晚上|中午)?\s*([0-9]{1,2})\s*[:：]\s*([0-9]{2})", text)
    if matched:
        marker, hour_text, minute_text = matched.group(1) or "", matched.group(2), matched.group(3)
        hour, minute = int(hour_text), int(minute_text)
        hour = with_period(hour, marker)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None
    matched = re.search(r"(上午|下午|晚上|中午|凌晨|早上|夜里)?\s*([0-9]{1,2})\s*点", text)
    if matched:
        marker, hour_text = matched.group(1) or "", matched.group(2)
        hour = with_period(int(hour_text), marker)
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
        return None
    return None


def parse_number(evidence: Any) -> int | None:
    """把原话里的数量解析成整数（"两个"得 2，"3件"得 3）。"""
    if evidence is None:
        return None
    text = normalize_text(evidence).strip()
    if not text:
        return None
    matched = re.search(r"[0-9]+", text)
    if matched:
        return int(matched.group(0))
    if _contains(text, "十"):
        matched = CN_NUMBER_RE.search(text)
        if matched:
            return _cn_number_to_int(matched.group(0))
    if _contains(text, "两"):
        return 2
    return None

# ---------------------------------------------------------------------------
# 计划的数据模型（pydantic v2，strict，extra="forbid"）
# ---------------------------------------------------------------------------

MODEL_CONFIG = ConfigDict(extra="forbid", strict=True)


class ValueArg(BaseModel):
    """原话取值。"""

    model_config = MODEL_CONFIG

    value: Union[str, int]
    evidence: str


class EnumArg(BaseModel):
    """枚举值。"""

    model_config = MODEL_CONFIG

    enum: str


class TextArg(BaseModel):
    """原话文本。"""

    model_config = MODEL_CONFIG

    text: str


class FreeTextArg(BaseModel):
    """自由文本，只允许用于 rag_summarize.query。"""

    model_config = MODEL_CONFIG

    free_text: str


class DevicePickArg(BaseModel):
    """从设备清单里挑设备。"""

    model_config = MODEL_CONFIG

    from_step: str
    pick: Literal["only_device", "device_matching"]
    hint: str | None = None


class SlotPickArg(BaseModel):
    """按时段挑选。date 和 start 都是原话取值。"""

    model_config = MODEL_CONFIG

    from_step: str
    pick: Literal["slot_at"]
    date: ValueArg
    start: ValueArg


class ConsumablePickArg(BaseModel):
    """按耗材种类挑选。"""

    model_config = MODEL_CONFIG

    from_step: str
    pick: Literal["consumable_kind"]
    kind: Union[str, EnumArg]


class RecordKindEnum(EnumArg):
    enum: Literal["order", "appointment"]


class RecordStatusEnum(EnumArg):
    enum: Literal["processing", "scheduled"]


class RecordPickArg(BaseModel):
    """从订单或预约里挑记录，id 是原话取值。"""

    model_config = MODEL_CONFIG

    from_step: str
    pick: Literal["record"]
    kind: Union[Literal["order", "appointment"], RecordKindEnum]
    id: ValueArg | None = None
    status: Union[Literal["processing", "scheduled"], RecordStatusEnum] | None = None
    hint: str | None = None


class PendingArg(BaseModel):
    """沿用本会话唯一一张同类待确认卡片的参数。"""

    model_config = MODEL_CONFIG

    from_pending: str
    tool: str


ArgSource = Annotated[
    Union[
        ValueArg, EnumArg, TextArg, FreeTextArg,
        DevicePickArg, SlotPickArg, ConsumablePickArg, RecordPickArg, PendingArg,
    ],
    Field(discriminator=None),
]

class WarrantyCondition(BaseModel):
    """保修条件。"""

    model_config = MODEL_CONFIG

    type: Literal["warranty_in_force"]
    from_step: str
    component: Literal["whole_machine", "battery"]


class RecordThresholdCondition(BaseModel):
    """月度记录阈值条件。"""

    model_config = MODEL_CONFIG

    type: Literal["record_threshold"]
    from_step: str
    field_hint: str
    op: Literal["<=", "<", ">=", ">"]
    value: Union[int, float]
    unit: Literal["%", "天"]
    evidence: str


Condition = Annotated[
    Union[WarrantyCondition, RecordThresholdCondition],
    Field(discriminator=None),
]


class Goal(BaseModel):
    """一个子目标。"""

    model_config = MODEL_CONFIG

    id: str = Field(pattern=r"^g[0-9]+$")
    type: Literal[
        "diagnose", "warranty", "knowledge", "report", "usage",
        "slots", "consumables", "status", "book", "order", "change",
    ]
    text: str

    @field_validator("text")
    @classmethod
    def check_text(cls, value: str) -> str:
        if not 1 <= len(value) <= 60:
            raise ValueError("goal text 长度必须在 1-60 之间")
        return value


class Step(BaseModel):
    """一个工具调用步骤。"""

    model_config = MODEL_CONFIG

    id: str = Field(pattern=r"^s[0-9]+$")
    tool: Literal[
        "list_my_devices", "lookup_error_code", "check_warranty", "rag_summarize",
        "fetch_external_data", "get_daily_usage", "find_service_slots",
        "find_consumables", "get_my_orders_and_tickets", "propose_service_visit",
        "propose_order", "propose_change",
    ]
    args: dict[str, ArgSource] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    covers: list[str] = Field(default_factory=list)
    condition: Condition | None = None


class AskUser(BaseModel):
    """需要用户补充信息的提问。"""

    model_config = MODEL_CONFIG

    type: Literal["which_device", "which_slot", "quantity", "other"]
    text: str

    @field_validator("text")
    @classmethod
    def check_text(cls, value: str) -> str:
        if not 1 <= len(value) <= 80:
            raise ValueError("ask_user.text 长度必须在 1-80 之间")
        return value


class Plan(BaseModel):
    """一整轮的计划。"""

    model_config = MODEL_CONFIG

    goals: list[Goal]
    steps: list[Step] = Field(default_factory=list)
    ask_user: AskUser | None = None

    @field_validator("goals")
    @classmethod
    def check_goals(cls, value: list[Goal]) -> list[Goal]:
        if not 1 <= len(value) <= 4:
            raise ValueError("goals 数量必须在 1-4 之间")
        return value

    @field_validator("steps")
    @classmethod
    def check_steps(cls, value: list[Step]) -> list[Step]:
        if len(value) > 6:
            raise ValueError("steps 数量不能超过 6")
        return value

    @field_validator("steps")
    @classmethod
    def check_unique_steps(cls, value: list[Step]) -> list[Step]:
        seen = [step.id for step in value]
        if len(set(seen)) != len(seen):
            raise ValueError("step id 必须唯一")
        return value

    @field_validator("goals")
    @classmethod
    def check_unique_goals(cls, value: list[Goal]) -> list[Goal]:
        seen = [goal.id for goal in value]
        if len(set(seen)) != len(seen):
            raise ValueError("goal id 必须唯一")
        return value

    @field_validator("goals")
    @classmethod
    def check_goal_step_ids_distinct(cls, value: list[Goal], info: Any) -> list[Goal]:
        steps = info.data.get("steps") or []
        overlap = {goal.id for goal in value} & {step.id for step in steps}
        if overlap:
            raise ValueError("goal id 和 step id 不能重复")
        return value


def plan_json_schema() -> dict:
    """返回给 Ollama 结构化输出用的 JSON Schema。"""
    return Plan.model_json_schema()


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------

def _error(code: str, step_id: str | None, detail: str) -> dict:
    """构造一条校验错误。"""
    return {"code": code, "step_id": step_id, "detail": detail}


def _normalize(text: Any) -> str:
    """校验用的文本规范化。"""
    if isinstance(text, EnumArg):
        text = text.enum
    elif isinstance(text, dict) and set(text) == {"enum"}:
        text = text["enum"]
    return normalize_text(text)


def _contains(text: str, needle: str) -> bool:
    """子串判断，忽略空格（"不高于15%"能匹配"不高于 15%"）。"""
    if not needle:
        return False
    return _compact_spaces(text).find(_compact_spaces(needle)) != -1


def _compact_spaces(text: str) -> str:
    """去掉空格，便于比较原话片段。"""
    return re.sub(r"[ \t]+", "", text if isinstance(text, str) else str(text))


def _step_index(steps: list[Step]) -> dict[str, int]:
    """step id 到位置的映射。"""
    return {step.id: index for index, step in enumerate(steps)}


def _source_kind(source: Any) -> str:
    """判断参数来源的种类。"""
    if isinstance(source, DevicePickArg):
        return "device"
    if isinstance(source, SlotPickArg):
        return "slot"
    if isinstance(source, ConsumablePickArg):
        return "consumable"
    if isinstance(source, RecordPickArg):
        return "record"
    if isinstance(source, PendingArg):
        return "pending"
    if isinstance(source, FreeTextArg):
        return "free_text"
    if isinstance(source, EnumArg):
        return "enum"
    if isinstance(source, TextArg):
        return "text"
    return "value"


def _source_step_ids(step: Step) -> list[str]:
    """收集一个步骤里所有 from_step 引用（含条件）。"""
    refs: list[str] = []
    for source in step.args.values():
        from_step = getattr(source, "from_step", None)
        if isinstance(from_step, str):
            refs.append(from_step)
    condition = step.condition
    condition_step = getattr(condition, "from_step", None)
    if isinstance(condition_step, str):
        refs.append(condition_step)
    return refs


def _required_device_from_pending(step: Step, param: str = "device_id") -> bool:
    """判断某个参数是否来自 from_pending。"""
    source = step.args.get(param)
    return isinstance(source, PendingArg)


def _needs_error_code(step: Step) -> bool:
    """判断 propose_service_visit 是否声明了错误码。"""
    source = step.args.get("error_code")
    if source is None:
        return False
    return not isinstance(source, PendingArg)


def _applied_steps(steps: list[Step], index: dict[str, int], current: int) -> set[str]:
    """写步骤之前（更早出现或依赖到的）步骤集合。"""
    applied: set[str] = set()
    for position in range(current):
        applied.add(steps[position].id)
    pending = [steps[current].id]
    while pending:
        step_id = pending.pop()
        step = steps[index[step_id]]
        for dependency in step.depends_on:
            if dependency in index and dependency not in applied:
                applied.add(dependency)
                pending.append(dependency)
    return applied


def _find_tool_step(
    steps: list[Step],
    index: dict[str, int],
    applied: set[str],
    tool: str,
    force_first: bool = False,
) -> bool:
    """判断某个读步骤是否在写步骤之前已经出现。"""
    for step in steps:
        if step.tool != tool or step.id not in applied:
            continue
        if force_first and not (
            step.id in steps[index[steps[0].id]].depends_on or index[step.id] == 0
        ):
            continue
        return True
    return False


def _has_condition_kind(step: Step, condition_type: str) -> bool:
    """判断写步骤上是否带了某类条件。"""
    return step.condition is not None and step.condition.type == condition_type


def _evidence_errors(step_id: str, name: str, raw: Any, evidence_pool: list[str]) -> tuple[list[dict], str]:
    """校验一个原话取值来源的出处，返回（错误列表, 可用的归一化出处）。"""
    errors: list[dict] = []
    if not isinstance(raw, ValueArg):
        return errors, ""
    evidence = _normalize(raw.evidence)
    if not evidence:
        errors.append(_error("P3", step_id, f"参数 {name} 的 evidence 不能为空"))
        return errors, ""
    if not any(evidence in candidate for candidate in evidence_pool):
        errors.append(_error("P3", step_id, f"参数 {name} 的 evidence 不在用户原话里：{raw.evidence}"))
        return errors, ""
    return errors, evidence


def _recompute_errors(
    step_id: str,
    name: str,
    raw: ValueArg,
    parser: str | None,
    business_date: Any,
    default_error: str,
) -> list[dict]:
    """按参数类型复算原话取值，返回错误列表。"""
    errors: list[dict] = []
    value = _normalize(raw.value)
    if parser is not None:
        computed = (
            parse_date(raw.evidence, business_date)
            if parser == "date"
            else parse_month(raw.evidence, business_date)
        )
        if computed is not None and computed != value:
            errors.append(_error("P3", step_id, f"参数 {name} 和 evidence 复算不一致"))
        return errors
    if name in NUMBER_PARAMS:
        computed_number = parse_number(raw.evidence)
        if computed_number is not None and str(computed_number) != str(raw.value):
            errors.append(_error("P3", step_id, f"参数 {name} 和 evidence 复算不一致"))
        return errors
    if not _contains(value, _normalize(raw.evidence)):
        errors.append(_error("P3", step_id, default_error))
    return errors


def _slot_errors(step_id: str, name: str, source: SlotPickArg, business_date: Any) -> list[dict]:
    """校验 slot_at 的 date 和 start 两个原话取值。"""
    errors: list[dict] = []
    date_value = _normalize(source.date.value)
    date_computed = parse_date(source.date.evidence, business_date)
    if date_computed is not None and date_computed != date_value:
        errors.append(_error("P3", step_id, f"参数 {name}.date 和 evidence 复算不一致"))
    start_value = _normalize(source.start.value)
    start_computed = parse_time(source.start.evidence)
    if start_computed is not None and start_computed != start_value:
        errors.append(_error("P3", step_id, f"参数 {name}.start 和 evidence 复算不一致"))
    return errors


def _record_id_errors(step_id: str, name: str, source: RecordPickArg) -> list[dict]:
    """校验 record.id：value 必须原样出现在 evidence 里。"""
    errors: list[dict] = []
    if source.id is None:
        return errors
    value = _normalize(source.id.value)
    evidence = _normalize(source.id.evidence)
    if not _contains(evidence, value):
        errors.append(_error("P3", step_id, f"参数 {name}.id 的取值必须原样出现在 evidence 里"))
    return errors


def _code_errors(step_id: str, name: str, raw: ValueArg) -> list[dict]:
    """校验 code：value 必须等于 evidence 里的 E 加两位数字。"""
    errors: list[dict] = []
    matched = re.search(r"E[0-9]{2}", _normalize(raw.evidence).upper())
    if matched is None:
        errors.append(_error("P3", step_id, f"参数 {name} 的 evidence 里没有错误码"))
    elif _normalize(raw.value).upper() != matched.group(0):
        errors.append(_error("P3", step_id, f"参数 {name} 和 evidence 里的错误码不一致"))
    return errors


def _validate_value_source(
    step_id: str,
    name: str,
    raw: Any,
    evidence_pool: list[str],
    business_date: Any,
    code_param: bool = False,
    number_param: bool = False,
    id_param: bool = False,
) -> list[dict]:
    """校验一个原话取值来源（含出处、复算和编号方向）。"""
    errors, evidence = _evidence_errors(step_id, name, raw, evidence_pool)
    if errors:
        return errors
    if code_param:
        return _code_errors(step_id, name, raw)
    parser = VALUE_PARSERS.get(name)
    if parser is not None:
        return _recompute_errors(step_id, name, raw, parser, business_date, "")
    if number_param:
        return _recompute_errors(step_id, name, raw, None, business_date, "")
    if id_param:
        if not _contains(evidence, _normalize(raw.value)):
            errors.append(_error("P3", step_id, f"参数 {name} 的取值必须原样出现在 evidence 里"))
        return errors
    return _recompute_errors(
        step_id, name, raw, None, business_date, f"参数 {name} 的取值必须原样出现在 evidence 里"
    )


def normalize_plan(plan: dict, ctx: dict) -> tuple[dict, list[dict]]:
    """Repair unambiguous syntax without conferring execution authority."""
    from service_desk.normalization import normalize_plan as normalize
    return normalize(plan, ctx)


def validate_plan(plan: dict, ctx: dict) -> dict:
    """校验计划结构、参数来源、依赖、覆盖和预算，收集所有错误。"""
    try:
        parsed = Plan.model_validate(plan)
    except ValidationError as error:
        details = []
        for item in error.errors():
            location = ".".join(str(part) for part in item.get("loc") or [])
            details.append(f"{location}: {item.get('msg')}")
        return {
            "ok": False,
            "errors": [_error("P1", None, "计划结构不合法：" + "；".join(details))],
            "plan": None,
        }

    errors: list[dict] = []
    plan_dict = parsed.model_dump(exclude_none=True)
    steps = parsed.steps
    goals = parsed.goals
    index = _step_index(steps)
    user_text = _normalize(ctx.get("user_text") or "")
    evidence_pool = [user_text]
    evidence_pool.extend(_normalize(item) for item in ctx.get("history_user_texts") or [])
    pending_cards = ctx.get("pending_cards") or []
    remaining_model_calls = ctx.get("remaining_model_calls")
    remaining_tool_calls = ctx.get("remaining_tool_calls")

    if {goal.id for goal in goals} & {step.id for step in steps}:
        errors.append(_error("P1", None, "goal id 和 step id 不能重复"))

    for step in steps:
        # P2：工具、参数名、必填参数
        spec = TOOLS[step.tool]
        params = spec["params"]
        for name in step.args:
            if name == "user_id":
                errors.append(_error("P2", step.id, "参数里不允许出现 user_id"))
            elif name not in params:
                errors.append(_error("P2", step.id, f"工具 {step.tool} 没有参数 {name}"))
        for name in spec["required"]:
            if name not in step.args:
                errors.append(_error("P2", step.id, f"缺少必填参数 {name}"))

        for name, source in step.args.items():
            kind = _source_kind(source)
            # P3：参数来源的种类必须和参数匹配
            allowed = PARAM_SOURCE_KINDS.get(name)
            if allowed is not None and kind not in allowed:
                errors.append(_error("P3", step.id, f"参数 {name} 不能用这种来源"))
            if isinstance(source, ValueArg):
                errors.extend(
                    _validate_value_source(
                        step.id,
                        name,
                        source,
                        evidence_pool,
                        ctx.get("business_date"),
                        code_param=name == "code",
                        number_param=name in NUMBER_PARAMS,
                        id_param=name in ID_PARAMS,
                    )
                )
            elif isinstance(source, TextArg):
                if not _contains(user_text, _normalize(source.text)):
                    errors.append(_error("P3", step.id, f"text 必须来自本轮原话：{source.text}"))
            elif isinstance(source, FreeTextArg):
                if name != "query":
                    errors.append(_error("P3", step.id, "free_text 只能用于 rag_summarize.query"))
            elif isinstance(source, EnumArg):
                if not any(source.enum == item for item in (params.get(name, {}).get("enum") or [])):
                    errors.append(_error("P3", step.id, f"参数 {name} 的枚举值不合法"))
            elif isinstance(source, (DevicePickArg, SlotPickArg, ConsumablePickArg, RecordPickArg)):
                position = index.get(source.from_step)
                if position is None:
                    errors.append(_error("P3", step.id, f"from_step {source.from_step} 不存在"))
                else:
                    if position >= index[step.id]:
                        errors.append(_error("P3", step.id, f"from_step {source.from_step} 必须更早出现"))
                    if steps[position].tool != PICK_TOOL[source.pick]:
                        errors.append(
                            _error("P3", step.id, f"from_step {source.from_step} 的工具类型和 pick 不匹配")
                        )
                if isinstance(source, DevicePickArg) and source.pick == "device_matching" and not source.hint:
                    errors.append(_error("P3", step.id, "device_matching 需要 hint"))
                if isinstance(source, SlotPickArg):
                    date_errors, date_evidence = _evidence_errors(
                        step.id, f"{name}.date", source.date, evidence_pool
                    )
                    start_errors, start_evidence = _evidence_errors(
                        step.id, f"{name}.start", source.start, evidence_pool
                    )
                    errors.extend(date_errors)
                    errors.extend(start_errors)
                    if date_evidence and start_evidence:
                        errors.extend(_slot_errors(step.id, name, source, ctx.get("business_date")))
                if isinstance(source, RecordPickArg) and source.id is not None:
                    id_errors, id_evidence = _evidence_errors(step.id, f"{name}.id", source.id, evidence_pool)
                    errors.extend(id_errors)
                    if id_evidence:
                        errors.extend(_record_id_errors(step.id, name, source))
            elif isinstance(source, PendingArg):
                same_tool = [card for card in pending_cards if card.get("tool") == source.tool]
                matches = [card for card in same_tool if source.from_pending in (card.get("args") or {})]
                if len(same_tool) != 1 or len(matches) != 1:
                    errors.append(
                        _error("P3", step.id, f"from_pending 需要唯一一张 {source.tool} 卡片且含参数 {source.from_pending}")
                    )

        # P4：depends_on 必须包含所有 from_step
        for reference in _source_step_ids(step):
            if reference not in index:
                errors.append(_error("P4", step.id, f"引用不存在的步骤 {reference}"))
            elif reference not in step.depends_on and reference != step.id:
                errors.append(_error("P4", step.id, f"depends_on 缺少 {reference}"))
        for dependency in step.depends_on:
            if dependency not in index:
                errors.append(_error("P4", step.id, f"依赖不存在的步骤 {dependency}"))

        # P6：condition 只能出现在写步骤上
        if step.condition is not None and step.tool not in WRITE_TOOLS:
            errors.append(_error("P6", step.id, "只有写步骤可以带 condition"))

        # 条件本身的校验
        condition = step.condition
        if condition is not None:
            position = index.get(condition.from_step)
            if position is None:
                errors.append(_error("P3", step.id, f"条件的 from_step {condition.from_step} 不存在"))
            elif steps[position].tool != CONDITION_TOOL[condition.type]:
                errors.append(_error("P3", step.id, "条件的 from_step 工具类型不对"))
            if isinstance(condition, RecordThresholdCondition):
                if not any(_contains(candidate, _normalize(condition.evidence)) for candidate in evidence_pool):
                    errors.append(_error("P3", step.id, "条件的 evidence 必须出现在原话里"))
                numbers = re.findall(r"[0-9]+(?:\.[0-9]+)?", _normalize(condition.evidence))
                if not numbers or float(numbers[0]) != float(condition.value):
                    errors.append(_error("P3", step.id, "条件里的数字必须等于 value"))

        # P5：covers 只能引用已存在的 goal
        for goal_id in step.covers:
            if goal_id not in {goal.id for goal in goals}:
                errors.append(_error("P5", step.id, f"covers 引用了不存在的 goal {goal_id}"))

    # P4：依赖图无环
    visiting: set[str] = set()
    visited: set[str] = set()

    def _walk(step_id: str) -> None:
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in steps[index[step_id]].depends_on:
            if dependency not in index:
                continue
            if dependency in visiting:
                errors.append(_error("P4", step_id, "依赖图存在环"))
            else:
                _walk(dependency)
        visiting.discard(step_id)
        visited.add(step_id)

    for step in steps:
        _walk(step.id)

    # P5：goal 覆盖
    covered = {goal_id for step in steps for goal_id in step.covers}
    for goal in goals:
        if goal.id not in covered and parsed.ask_user is None:
            errors.append(_error("P5", None, f"goal {goal.id} 没有被任何步骤覆盖"))
        needed = GOAL_WRITE_TOOL.get(goal.type)
        if needed is not None and parsed.ask_user is None:
            if not any(step.tool == needed and goal.id in step.covers for step in steps):
                errors.append(_error("P5", None, f"goal {goal.id} 必须由 {needed} 覆盖"))

    # P6：写步骤的数量和依赖限制
    write_steps = [step for step in steps if step.tool in WRITE_TOOLS]
    if len(write_steps) > 2:
        errors.append(_error("P6", None, "最多只能有 2 个写步骤"))
    for step in write_steps:
        for other in steps:
            if step.id in other.depends_on:
                errors.append(_error("P6", other.id, "写步骤不能被其他步骤依赖"))

    # P7：服务流程要求
    for step in steps:
        if step.tool not in WRITE_TOOLS:
            continue
        applied = _applied_steps(steps, index, index[step.id])
        required: list[str] = []
        if step.tool == "propose_service_visit":
            if not _required_device_from_pending(step):
                required.append("list_my_devices")
            if _needs_error_code(step):
                required.append("lookup_error_code")
            if not _required_device_from_pending(step):
                required.append("check_warranty")
            required.append("find_service_slots")
        elif step.tool == "propose_order":
            if not _required_device_from_pending(step):
                required.append("list_my_devices")
            required.append("find_consumables")
            if _has_condition_kind(step, "record_threshold"):
                required.append("fetch_external_data")
        elif step.tool == "propose_change":
            required.append("get_my_orders_and_tickets")
            change = step.args.get("change")
            if isinstance(change, ValueArg) and _normalize(change.value) == "reschedule":
                required.append("find_service_slots")
            elif isinstance(change, EnumArg) and _normalize(change.enum) == "reschedule":
                required.append("find_service_slots")
        for tool in required:
            if not _find_tool_step(steps, index, applied, tool):
                errors.append(_error("P7", step.id, f"{step.tool} 之前缺少 {tool} 步骤"))

    if any(goal.type == "knowledge" for goal in goals):
        if not any(step.tool == "rag_summarize" for step in steps):
            errors.append(_error("P7", None, "有 knowledge 目标时必须规划 rag_summarize"))

    # P8：预算
    if remaining_model_calls is not None:
        rag_steps = sum(1 for step in steps if step.tool == "rag_summarize")
        if rag_steps > remaining_model_calls:
            errors.append(_error("P8", None, "rag_summarize 步骤数超出剩余模型调用预算"))
    if remaining_tool_calls is not None and len(steps) > remaining_tool_calls:
        errors.append(_error("P8", None, "步骤总数超出剩余工具调用预算"))

    from service_desk.signals import recognize, validate_signals
    errors.extend(validate_signals(plan_dict, ctx.get("service_signals") or recognize(ctx.get("user_text", ""))))
    return {"ok": not errors, "errors": errors, "plan": plan_dict}


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def _step_result(results: dict, step_id: str) -> dict | None:
    """取某一个步骤的工具结果。"""
    result = (results or {}).get(step_id)
    if isinstance(result, dict) and isinstance(result.get("payload"), dict):
        return result
    return None


def _resolve_value(name: str, source: ValueArg, ctx: dict) -> Any:
    """原话取值：按参数类型返回规范化后的值。"""
    parser = VALUE_PARSERS.get(name)
    if parser == "date":
        parsed = parse_date(source.evidence, ctx.get("business_date"))
        return parsed if parsed is not None else _normalize(source.value)
    if parser == "month":
        parsed = parse_month(source.evidence, ctx.get("business_date"))
        return parsed if parsed is not None else _normalize(source.value)
    if parser == "number":
        parsed = parse_number(source.evidence)
        return parsed if parsed is not None else source.value
    if name == "code":
        matched = re.search(r"E[0-9]{2}", _normalize(source.value).upper())
        return matched.group(0) if matched else _normalize(source.value)
    if isinstance(source.value, str):
        return _normalize(source.value)
    return source.value


def _resolve_primary(
    name: str,
    source: Any,
    results: dict,
    ctx: dict,
    resolve_ctx: Any = None,
) -> dict:
    """解析一个参数来源，返回 {"status", "value"} 或失败说明。"""
    business_date = ctx.get("business_date")
    if isinstance(source, ValueArg):
        return {"status": "ok", "value": _resolve_value(name, source, ctx)}
    if isinstance(source, EnumArg):
        return {"status": "ok", "value": _normalize(source.enum)}
    if isinstance(source, TextArg):
        return {"status": "ok", "value": _normalize(source.text)}
    if isinstance(source, FreeTextArg):
        return {"status": "ok", "value": _normalize(source.free_text)}
    if isinstance(source, PendingArg):
        # 只统计该工具的待确认卡片，其它工具的卡片不参与
        same_tool = [
            card for card in ctx.get("pending_cards") or [] if card.get("tool") == source.tool
        ]
        matches = [card for card in same_tool if source.from_pending in (card.get("args") or {})]
        if len(same_tool) != 1 or len(matches) != 1:
            return {
                "status": "unresolved",
                "param": name,
                "detail": f"需要唯一一张 {source.tool} 的待确认卡片且含参数 {source.from_pending}",
                "candidates": [],
            }
        return {"status": "ok", "value": (matches[0].get("args") or {})[source.from_pending]}

    result = _step_result(results, source.from_step)
    if result is None:
        return {
            "status": "unresolved",
            "param": name,
            "detail": f"缺少步骤 {source.from_step} 的结果",
            "candidates": [],
        }
    payload = result["payload"]

    if isinstance(source, DevicePickArg):
        devices = payload.get("devices") or []
        if source.pick == "only_device":
            if len(devices) == 1:
                return {"status": "ok", "value": _normalize(devices[0].get("device_id"))}
            if not devices:
                return {"status": "unresolved", "param": name, "detail": "没有查到设备", "candidates": []}
            return {
                "status": "ambiguous",
                "param": name,
                "detail": "有多台设备",
                "candidates": [_normalize(item.get("device_id")) for item in devices],
            }
        hint = _normalize(source.hint or "")
        matches = []
        for item in devices:
            haystack = _normalize(f"{item.get('display_name', '')}{item.get('model_code', '')}")
            if hint and _contains(haystack, hint):
                matches.append(item)
        if len(matches) == 1:
            return {"status": "ok", "value": _normalize(matches[0].get("device_id"))}
        status = "ambiguous" if len(matches) > 1 else "unresolved"
        return {
            "status": status,
            "param": name,
            "detail": "没有匹配到唯一设备",
            "candidates": [_normalize(item.get("device_id")) for item in matches],
        }

    if isinstance(source, SlotPickArg):
        # 用校验过的 value；解析不出来时退回原话
        want_date = parse_date(source.date.evidence, business_date) or _normalize(source.date.value)
        want_start = parse_time(source.start.evidence) or _normalize(source.start.value)
        matches = []
        for slot in payload.get("slots") or []:
            start_at = _normalize(slot.get("start_at", ""))
            if want_date and want_start and start_at[:10] == want_date and start_at[11:16] == want_start:
                matches.append(slot)
        if len(matches) == 1:
            return {"status": "ok", "value": _normalize(matches[0].get("slot_id"))}
        if not matches:
            return {
                "status": "unresolved",
                "param": name,
                "detail": "slot_unavailable",
                "candidates": [],
            }
        return {
            "status": "ambiguous",
            "param": name,
            "detail": "有多个符合条件的时段",
            "candidates": [_normalize(item.get("slot_id")) for item in matches],
        }

    if isinstance(source, ConsumablePickArg):
        kind = _normalize(source.kind)
        matches = [item for item in payload.get("consumables") or [] if _normalize(item.get("kind")) == kind]
        if len(matches) == 1:
            return {"status": "ok", "value": _normalize(matches[0].get("sku"))}
        status = "ambiguous" if len(matches) > 1 else "unresolved"
        return {
            "status": status,
            "param": name,
            "detail": "没有匹配到唯一耗材",
            "candidates": [_normalize(item.get("sku")) for item in matches],
        }

    if isinstance(source, RecordPickArg):
        matches = _match_records(source, payload)
        if len(matches) == 1:
            return {"status": "ok", "value": _normalize(matches[0].get("id"))}
        status = "ambiguous" if len(matches) > 1 else "unresolved"
        return {
            "status": status,
            "param": name,
            "detail": "没有匹配到唯一记录",
            "candidates": [_normalize(item.get("id")) for item in matches],
        }

    return {"status": "unresolved", "param": name, "detail": "不支持的参数来源", "candidates": []}


def _record_haystack(record: dict, records: list[dict]) -> str:
    """记录里可用于 hint 匹配的文本。"""
    kind = _normalize(record.get("kind"))
    if kind == "order":
        return _normalize(record.get("sku", ""))
    if kind == "ticket":
        return _normalize(record.get("description", ""))
    if kind == "appointment":
        ticket_id = record.get("ticket_id")
        for item in records:
            if item.get("id") == ticket_id:
                return _normalize(item.get("description", ""))
    return ""


def _match_records(source: RecordPickArg, payload: dict) -> list[dict]:
    """按 kind、id、status、hint 依次过滤记录。"""
    records = payload.get("records") or []
    matches = [item for item in records if _normalize(item.get("kind")) == _normalize(source.kind)]
    if source.id is not None:
        wanted = _normalize(source.id.value)
        matches = [item for item in matches if _normalize(item.get("id")) == wanted]
    if source.status is not None:
        wanted_status = _normalize(source.status)
        matches = [item for item in matches if _normalize(item.get("status")) == wanted_status]
    if source.hint:
        hint = _normalize(source.hint)
        matches = [item for item in matches if _contains(_record_haystack(item, records), hint)]
    return matches


def _parse_arg_source(raw: Any) -> Any:
    """把 dict 形式的参数来源解析成参数来源对象；解析不了时原样返回。"""
    if isinstance(raw, BaseModel):
        return raw
    if not isinstance(raw, dict):
        return raw
    for model in (
        DevicePickArg, SlotPickArg, ConsumablePickArg, RecordPickArg,
        PendingArg, FreeTextArg, EnumArg, TextArg, ValueArg,
    ):
        try:
            return model.model_validate(raw)
        except ValidationError:
            continue
    return raw


def resolve_args(step: dict, results: dict, ctx: dict) -> dict:
    """解析一个步骤的全部参数，返回 ok 或 unresolved/ambiguous。"""
    args: dict[str, Any] = {}
    for name, raw in (step.get("args") or {}).items():
        source = _parse_arg_source(raw)
        if not isinstance(source, BaseModel):
            return {
                "status": "unresolved",
                "param": name,
                "detail": "参数来源无法识别",
                "candidates": [],
            }
        resolved = _resolve_primary(name, source, results, ctx)
        if resolved.get("status") != "ok":
            return {
                "status": resolved.get("status", "unresolved"),
                "param": name,
                "detail": resolved.get("detail", ""),
                "candidates": resolved.get("candidates", []),
            }
        args[name] = resolved.get("value")
    return {"status": "ok", "args": args}


# ---------------------------------------------------------------------------
# 条件判断
# ---------------------------------------------------------------------------

def _split_field_lines(text: Any) -> list[str]:
    """按真换行和字面量 "\\n" 拆行。"""
    raw = str(text if text is not None else "")
    raw = raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    return [line.strip() for line in raw.split("\n") if line.strip()]


def _find_threshold_value(data: dict, field_hint: str) -> tuple[float, str] | None:
    """在文本字段里找含 field_hint 的行，取冒号后的第一个数值和单位。"""
    hint = _normalize(field_hint).lower()
    for value in data.values():
        if not isinstance(value, str):
            continue
        for line in _split_field_lines(value):
            normalized = _normalize(line).lower()
            if normalized.find(hint) == -1:
                continue
            matched = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(%|天)", normalized)
            if matched:
                return float(matched.group(1)), matched.group(2)
    return None


def evaluate_condition(cond: dict, results: dict) -> tuple[str, str]:
    """判断用户附带的条件，返回（true/false/unknown, 说明）。"""
    if not isinstance(cond, dict):
        return "unknown", "没有可判断的条件"
    kind = _normalize(cond.get("type", ""))
    from_step = cond.get("from_step")
    result = _step_result(results, from_step) if isinstance(from_step, str) else None

    if kind == "warranty_in_force":
        if result is None:
            return "unknown", "没有保修查询结果"
        component = _normalize(cond.get("component", ""))
        for item in result["payload"].get("coverage") or []:
            if _normalize(item.get("component")) == component:
                if item.get("in_warranty"):
                    return "true", f"{component} 在保"
                return "false", f"{component} 已过保"
        return "unknown", "保修结果里没有该部件"

    if kind == "record_threshold":
        if result is None:
            return "unknown", "没有月度记录结果"
        payload = result["payload"]
        if _normalize(payload.get("status", "ok")) != "ok":
            return "unknown", "月度记录不可用"
        data = payload.get("data") or {}
        found = _find_threshold_value(data, str(cond.get("field_hint", "")))
        if found is None:
            return "unknown", "没有找到对应字段"
        value, unit = found
        if unit != _normalize(cond.get("unit", "")):
            return "unknown", "单位不一致"
        compare = CONDITION_OPS.get(_normalize(cond.get("op", "")))
        if compare is None:
            return "unknown", "未知的比较符"
        if compare(value, float(cond.get("value", 0))):
            return "true", f"{value}{unit} 满足条件"
        return "false", f"{value}{unit} 不满足条件"

    return "unknown", "未知的条件类型"


# ---------------------------------------------------------------------------
# 写操作预检
# ---------------------------------------------------------------------------

def _consumables_result(results: dict, device_id: Any) -> dict | None:
    """找 device_id 匹配的耗材查询结果。"""
    wanted = _normalize(device_id)
    for result in (results or {}).values():
        if not isinstance(result, dict) or result.get("tool") != "find_consumables":
            continue
        payload = result.get("payload") or {}
        if _normalize(payload.get("device_id", "")) == wanted:
            return result
    return None


def _find_record(results: dict, target_id: Any) -> dict | None:
    """在所有记录结果里找指定编号的记录。"""
    wanted = _normalize(target_id)
    for result in (results or {}).values():
        if not isinstance(result, dict) or result.get("tool") != "get_my_orders_and_tickets":
            continue
        for record in (result.get("payload") or {}).get("records") or []:
            if _normalize(record.get("id")) == wanted:
                return record
    return None


def _slot_available(results: dict, slot_id: Any) -> bool:
    """判断时段是否出现在某个时段查询结果里。"""
    wanted = _normalize(slot_id)
    for result in (results or {}).values():
        if not isinstance(result, dict) or result.get("tool") != "find_service_slots":
            continue
        for slot in (result.get("payload") or {}).get("slots") or []:
            if _normalize(slot.get("slot_id")) == wanted:
                return True
    return False


def precheck(tool: str, args: dict, results: dict) -> dict | None:
    """发起写操作前的确定性预检，不满足时返回 reason_code 和 message。"""
    args = args or {}
    if tool == "propose_order":
        found = _consumables_result(results, args.get("device_id"))
        if found is None:
            return {"reason_code": "no_catalog_evidence", "message": "没有查到该设备的耗材清单"}
        items = (found.get("payload") or {}).get("consumables") or []
        wanted = _normalize(args.get("sku"))
        item = next((entry for entry in items if _normalize(entry.get("sku")) == wanted), None)
        if item is None:
            return {"reason_code": "incompatible_consumable", "message": "耗材与所选设备型号不兼容"}
        qty = args.get("qty") or 0
        if float(item.get("stock", 0)) < float(qty):
            return {"reason_code": "out_of_stock", "message": "库存不足"}
        if item.get("max_per_order") is not None and float(qty) > float(item["max_per_order"]):
            return {"reason_code": "purchase_limit", "message": "数量超过单次限购"}
        return None

    if tool == "propose_service_visit":
        if not _slot_available(results, args.get("slot_id")):
            return {"reason_code": "slot_unavailable", "message": "所选时段没有可约名额"}
        return None

    if tool == "propose_change":
        record = _find_record(results, args.get("target_id"))
        if record is None:
            return {"reason_code": "no_record_evidence", "message": "没有查到该记录"}
        change = _normalize(args.get("change"))
        kind = _normalize(record.get("kind"))
        status = _normalize(record.get("status"))
        if change == "cancel_order":
            if kind != "order" or status != "processing":
                return {"reason_code": "order_not_processing", "message": "该订单当前不能取消"}
        elif change in ("reschedule", "cancel_appointment"):
            if kind != "appointment" or status != "scheduled":
                return {"reason_code": "appointment_not_scheduled", "message": "该预约当前不能变更"}
        if change == "reschedule" and not _slot_available(results, args.get("new_slot_id")):
            return {"reason_code": "slot_unavailable", "message": "所选时段没有可约名额"}
        return None

    return None
