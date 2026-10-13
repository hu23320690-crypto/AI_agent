"""Strict, permission-free proposal returned by the intent model."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntentField(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    mention: str
    field: str | None


class IntentProposal(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    task_type: Literal["report", "report_with_knowledge", "knowledge_only", "other"]
    fields: list[IntentField]
    scope: Literal["only_listed", "full_report", "unspecified"]
    # V5 validates calendar values so an invalid slot can fall back separately.
    target_month: str | None
    target_mention: str
    compare: bool
    baseline_month: str | None
    baseline_mention: str
    excluded_fields: list[str]
    knowledge_question: str
    unresolved: bool


INTENT_SCHEMA = IntentProposal.model_json_schema()
