"""Check only facts that can be disproved without guessing user intent."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from agent.intent.schema import IntentField, IntentProposal
from utils.report_intent import (
    ReportIntent,
    _BARE_MONTH,
    _CHINESE_MONTHS,
    _RELATIVE_MONTH,
    _positive_text,
    shift_month,
    valid_month,
)


@dataclass(frozen=True)
class ValidationResult:
    proposal: IntentProposal
    conflicts: tuple[str, ...] = ()
    invalid_month: bool = False
    unresolved_month: bool = False
    rejected: bool = False


# The absolute selector also accepts a spelled-out month after an explicit year.
# This is extraction of a written date, not an interpretation of its role.
_ABSOLUTE_MONTH = re.compile(
    r"(?<!\d)(?P<year>\d{4})\s*[-/年]\s*"
    r"(?P<month>\d{1,2}|十二|十一|十|[一二三四五六七八九])\s*月?(?!\d)"
)
_GENERAL_MODIFIERS = re.compile(r"剩余|寿命|率|的|数值|多少|情况|比例")


def _compact(value: str) -> str:
    return re.sub(r"\s", "", value)


def _legal_month(value: object) -> bool:
    # V5's wire format is ASCII YYYY-MM; Python's \d also accepts other digits.
    return (isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}", value) is not None
            and valid_month(value))


def _anchored(mention: str, texts: tuple[str, ...]) -> bool:
    compact = _compact(mention)
    return bool(compact) and any(compact in _compact(text) for text in texts)


def _only_masked_mention(mention: str, texts: tuple[str, ...]) -> bool:
    """A current exclusion overrides a historical positive mention."""
    compact = _compact(mention)
    if not compact:
        return False
    current = texts[0]
    if compact in _compact(current):
        return compact not in _compact(_positive_text(current))
    return _anchored(mention, texts) and not _anchored(
        mention, tuple(_positive_text(text) for text in texts)
    )


def _explicit_months(text: str, previous: ReportIntent, fallback: str | None) -> set[str]:
    """Extract written absolute/bare months with an already established year."""
    absolute: list[tuple[int, str]] = []
    occupied: list[tuple[int, int]] = []
    for match in _ABSOLUTE_MONTH.finditer(text):
        raw = match["month"]
        month = int(raw) if raw.isdigit() else _CHINESE_MONTHS[raw]
        value = f'{int(match["year"]):04d}-{month:02d}'
        if valid_month(value):
            absolute.append((match.start(), value))
        occupied.append(match.span())
    values = {value for _, value in absolute}
    occupied.extend(match.span() for match in _RELATIVE_MONTH.finditer(text))
    for match in _BARE_MONTH.finditer(text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        raw = match["month"]
        month = int(raw) if raw.isdigit() else _CHINESE_MONTHS[raw]
        earlier = [value for position, value in absolute if position < match.start()]
        anchor = (earlier[-1] if earlier else previous.target_month) or fallback
        if valid_month(anchor):
            value = f"{anchor[:4]}-{month:02d}"
            if valid_month(value):
                values.add(value)
    return values


def _relative_offset(mention: str, positive_texts: tuple[str, ...]) -> int | None:
    # A fabricated date mention must not create its own V6 justification.
    if not _anchored(mention, positive_texts):
        return None
    match = _RELATIVE_MONTH.search(mention)
    if match is not None:
        return 1 if match["next"] else -1
    return -1 if "环比" in mention else None


def validate_proposal(
    proposal: IntentProposal,
    *,
    query: str,
    history_queries: Iterable[str] = (),
    previous_intent: ReportIntent | None = None,
    known_fields: Iterable[str] = (),
    fallback_month: str | None = None,
    rule_intent: ReportIntent,
    mode: str = "hybrid",
) -> ValidationResult:
    """Validate a proposal on the report-query path, never grant tool authority.

    V1 lives at the JSON parser boundary. ``llm_only`` intentionally keeps only
    V2 and V10 here; it is the plan's ablation mode.
    """
    conflicts: list[str] = []

    def conflict(code: str) -> None:
        if code not in conflicts:
            conflicts.append(code)

    # V10: this function is called only after a policy-checked report lookup.
    if proposal.task_type in {"knowledge_only", "other"}:
        return ValidationResult(proposal, ("task_type_conflict",), rejected=True)

    catalog = set(known_fields)
    fields: list[IntentField] = []
    for item in proposal.fields:
        # V2: a model cannot extend the authorized field catalog.
        if item.field is not None and item.field not in catalog:
            conflict("field_not_in_catalog")
            item = item.model_copy(update={"field": None})
        fields.append(item)
    excluded_fields = []
    for field in dict.fromkeys(proposal.excluded_fields):
        if field not in catalog:
            conflict("field_not_in_catalog")
        else:
            excluded_fields.append(field)
    checked = proposal.model_copy(update={"fields": fields, "excluded_fields": excluded_fields})
    if mode == "llm_only":
        excluded = set(excluded_fields)
        checked = checked.model_copy(update={"fields": [
            item for item in fields if item.field not in excluded and item.mention not in excluded
        ]})
        return ValidationResult(checked, tuple(conflicts), unresolved_month=bool(
            checked.unresolved and (checked.target_month is None or
                                    checked.compare and checked.baseline_month is None)))

    previous = previous_intent or ReportIntent()
    texts = (query, *(text for text in history_queries if isinstance(text, str)))
    positive_texts = tuple(_positive_text(text) for text in texts)
    # V9: an exclusion is a current written fact, not model authority to hide
    # arbitrary catalog fields. A positive correction cancels the exclusion.
    excluded_fields = [field for field in excluded_fields if _only_masked_mention(field, (query,))]
    if len(excluded_fields) != len(checked.excluded_fields):
        conflict("exclusion_not_in_text")
    excluded = set(excluded_fields)
    fields = []
    for item in checked.fields:
        # V3: unknown labels must be anchored as strictly as catalog labels.
        if not _anchored(item.mention, texts):
            conflict("mention_not_in_text")
            continue
        # V4: do not discard a component or scope modifier around a field.
        mention = _compact(item.mention)
        field = _compact(item.field) if item.field is not None else ""
        if field and field != mention and field in mention:
            remainder = mention.replace(field, "", 1)
            if _GENERAL_MODIFIERS.sub("", remainder):
                conflict("qualifier_dropped")
                item = item.model_copy(update={"field": None})
        # V9: current exclusions also apply to a field copied from history.
        if (_only_masked_mention(item.mention, texts)
                or (item.field is not None and _only_masked_mention(item.field, texts))
                or item.field in excluded or item.mention in excluded):
            conflict("negated_field_selected")
            continue
        fields.append(item)

    updates: dict[str, object] = {"fields": fields, "excluded_fields": excluded_fields}
    target, baseline = checked.target_month, checked.baseline_month
    invalid = False
    unresolved = False
    fallback_slots: set[str] = set()

    # V5: invalid calendar values fall back per slot, not per proposal.
    if target is not None and not _legal_month(target):
        conflict("month_invalid")
        target = rule_intent.target_month
        fallback_slots.add("target")
        invalid = rule_intent.invalid_month
        unresolved = rule_intent.unresolved_month
    if baseline is not None and not _legal_month(baseline):
        conflict("month_invalid")
        baseline = rule_intent.comparison_month
        fallback_slots.add("baseline")
        invalid = invalid or rule_intent.invalid_month
        unresolved = unresolved or rule_intent.unresolved_month

    justified: set[str] = set()

    def recompute(slot: str, value: str | None, anchor: str | None, offset: int) -> str | None:
        nonlocal invalid, unresolved
        if not valid_month(anchor):
            # V8: never substitute today's date for a missing report anchor.
            conflict("no_anchor")
            unresolved = True
            return None
        calculated = shift_month(anchor, offset)
        if calculated is None:
            conflict("month_invalid")
            invalid = True
            return None
        # V7: month arithmetic, including year boundaries, belongs to code.
        if calculated != value:
            conflict("relative_month_recomputed")
        justified.add(slot)
        fallback_slots.discard(slot)
        return calculated

    raw_months = set().union(*(_explicit_months(text, previous, fallback_month) for text in texts))
    positive_months = set().union(*(
        _explicit_months(text, previous, fallback_month) for text in positive_texts
    ))
    current_months = _explicit_months(query, previous, fallback_month)
    current_positive_months = _explicit_months(_positive_text(query), previous, fallback_month)

    def validate_month(slot: str, value: str | None, mention: str, fallback: str | None) -> str | None:
        nonlocal invalid, unresolved
        # V6: null + unresolved is a valid safe failure, never filled from prose.
        if value is None or slot in fallback_slots:
            return value
        if (value not in raw_months and value != previous.target_month
                and slot not in justified):
            conflict("month_unsupported")
            invalid = invalid or rule_intent.invalid_month
            unresolved = unresolved or rule_intent.unresolved_month
            return fallback
        # V9: a supported date can still occur only in an exclusion.
        if ((value in current_months and value not in current_positive_months)
                or (value in raw_months and value not in positive_months)
                or _only_masked_mention(mention, texts)):
            conflict("negated_month_selected")
            invalid = invalid or rule_intent.invalid_month
            unresolved = unresolved or rule_intent.unresolved_month
            return fallback
        return value

    # Historical relative phrases were already resolved into previous_intent;
    # applying them again would move an inherited month a second time.
    current_positive = (_positive_text(query),)
    target_offset = _relative_offset(checked.target_mention, current_positive)
    baseline_offset = _relative_offset(checked.baseline_mention, current_positive)
    if target_offset is not None:
        target = recompute("target", target, previous.target_month or fallback_month, target_offset)
    # V8 also protects an omitted relative mention from a guessed current date.
    if (target_offset is None and baseline_offset is None
            and _RELATIVE_MONTH.search(_positive_text(query))
            and not valid_month(previous.target_month) and not valid_month(fallback_month)
            and target not in current_positive_months):
        conflict("no_anchor")
        target = None
        unresolved = True

    target = validate_month("target", target, checked.target_mention, rule_intent.target_month)
    # V7 baselines use the already validated target as their first anchor.
    # A positive explicit month-on-month request is deterministic even if the
    # model omitted its baseline mention or comparison flag.
    if "环比" in _positive_text(query):
        updates["compare"] = True
        baseline_offset = -1
    if baseline_offset is not None:
        baseline = recompute(
            "baseline", baseline, target or previous.target_month or fallback_month, baseline_offset
        )
    baseline = validate_month("baseline", baseline, checked.baseline_mention, rule_intent.comparison_month)
    updates.update(target_month=target, baseline_month=baseline)
    unresolved = unresolved or (checked.unresolved and
                                (target is None or checked.compare and baseline is None))
    if unresolved:
        updates["unresolved"] = True
    return ValidationResult(
        checked.model_copy(update=updates), tuple(conflicts),
        invalid_month=invalid, unresolved_month=unresolved,
    )
