"""Application tool permissions, checked before dispatch and budget reservation.

The current user is a page-selected demonstration identity, not authenticated
production identity. Model-supplied arguments never establish permissions.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from utils.records import normalize_month


POLICY_ERROR = "工具调用未通过安全检查，请检查当前会话设置和输入后重试。"
POLICY_OBSERVATION = (
    "工具调用被安全策略拒绝，未执行。请使用当前会话允许的工具和有效参数；"
    "不得据此编造结果或重复相同调用。"
)
_INJECTED_ARGUMENTS = frozenset({
    "runtime", "context", "run_context", "state", "store", "config", "tool_call_id",
})


class ToolPolicyDenied(ValueError):
    def __init__(self, code: str):
        self.code = code
        # Never retain the invalid input or a Pydantic exception in the message.
        super().__init__("Tool permission denied")


class PublicArguments(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def clean_text(cls, value: Any, info):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("empty text")
            allowed_controls = "\n\t" if info.field_name == "query" else ""
            if any((ord(char) < 32 and char not in allowed_controls) or ord(char) == 127
                   for char in value):
                raise ValueError("control character")
        return value


class NoArguments(PublicArguments):
    pass


class QueryArguments(PublicArguments):
    query: str = Field(min_length=1, max_length=3000)


class CityArguments(PublicArguments):
    city: str = Field(min_length=1, max_length=100)


class RecordArguments(PublicArguments):
    user_id: str = Field(min_length=1, max_length=64)
    month: str = Field(min_length=1, max_length=20)


TOOL_ARGUMENTS = {
    "rag_summarize": QueryArguments,
    "get_weather": CityArguments,
    "get_user_location": NoArguments,
    "get_user_id": NoArguments,
    "get_current_month": NoArguments,
    "fetch_external_data": RecordArguments,
    "fill_context_for_report": NoArguments,
}


def safe_tool_name(name: Any) -> str:
    """Only fixed registered names enter policy logs and run traces."""
    return name if isinstance(name, str) and name in TOOL_ARGUMENTS else "<unknown>"


def _valid_report(context: Mapping[str, Any]) -> bool:
    report = context.get("report_data")
    if not isinstance(report, dict) or report.get("status") != "ok":
        return False
    selected = context.get("user_id")
    if not isinstance(selected, str) or not selected or report.get("user_id") != selected:
        return False
    if context.get("lookup_result") != report:
        return False
    month = report.get("month")
    try:
        if not isinstance(month, str) or normalize_month(month) != month:
            return False
    except ValueError:
        return False
    data = report.get("data")
    return (isinstance(data, dict)
            and set(data) == {"特征", "效率", "耗材", "对比"}
            and all(isinstance(value, str) and bool(value.strip()) for value in data.values()))


def authorize_tool(name: str, arguments: Any, context: Mapping[str, Any], *, tool=None) -> dict:
    """Return normalized public arguments; otherwise raise a fixed coded denial.

    Runtime/state/store injection is performed by LangGraph after this check.
    Each ReactAgent turn creates a new context, so report_data cannot carry over
    from a previous turn. Tool functions retain their own defensive checks.
    """
    if not isinstance(name, str) or name not in TOOL_ARGUMENTS:
        raise ToolPolicyDenied("tool_not_allowed")
    if not isinstance(arguments, dict):
        raise ToolPolicyDenied("arguments_invalid")
    if _INJECTED_ARGUMENTS.intersection(arguments):
        raise ToolPolicyDenied("injected_argument")
    schema = TOOL_ARGUMENTS[name]
    if tool is not None and set(tool.tool_call_schema.model_fields) != set(schema.model_fields):
        raise ToolPolicyDenied("schema_mismatch")
    try:
        validated = schema.model_validate(arguments, strict=True).model_dump()
    except ValidationError:
        raise ToolPolicyDenied("arguments_invalid") from None
    if name == "fetch_external_data":
        selected = context.get("user_id")
        if not isinstance(selected, str) or not selected:
            raise ToolPolicyDenied("identity_missing")
        if validated["user_id"] != selected:
            raise ToolPolicyDenied("identity_mismatch")
        try:
            validated["month"] = normalize_month(validated["month"])
        except ValueError:
            raise ToolPolicyDenied("month_invalid") from None
        # Permission comes from server-side context, not model-generated text.
        validated["user_id"] = selected
    elif name == "fill_context_for_report" and not _valid_report(context):
        raise ToolPolicyDenied("report_unavailable")
    return validated
