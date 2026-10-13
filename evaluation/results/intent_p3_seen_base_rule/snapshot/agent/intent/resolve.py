"""Rule baseline, validated proposal merging and privacy-safe resolution trace."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import re
import time
from typing import Literal

from agent.context_budget import ContextBudgetExceeded
from agent.runtime import (CallTimeout, CircuitOpen, DependencyUnavailable,
                           RunContext, RuntimeControlError, current_run)
from utils.report_intent import ReportIntent, _FULL, _ONLY, _positive_text, resolve_report_intent
from .llm_parser import (InvalidIntentProposal, bounded_history_queries,
                         load_intent_config, parse_turn_intent)
from .validate import validate_proposal
from .schema import IntentProposal


@dataclass(frozen=True)
class TurnIntentResult:
    intent: ReportIntent
    knowledge_requested: bool
    trace: dict
    # Proposal is diagnostic; consumers use the final range/exclusion slots,
    # independently of the renderer's remaining-field list or rule fallback.
    proposal: IntentProposal | None = None
    final_scope: Literal['only_listed', 'full_report', 'unspecified'] = 'unspecified'
    final_excluded_fields: tuple[str, ...] = ()


def _explicit_scope(query):
    """Observe only current positive scope words, with _update precedence."""
    positive = _positive_text(query)
    full_matches = list(_FULL.finditer(positive))
    only_matches = list(_ONLY.finditer(positive))
    if full_matches and (not only_matches or
                         full_matches[-1].start() > only_matches[-1].start()):
        return 'full_report'
    if only_matches:
        return 'only_listed'
    return None


def _rule_final_scope(query, rule_intent):
    """Describe the rule result without treating inferred limits as evidence."""
    return _explicit_scope(query) or ('only_listed' if rule_intent.limited else 'unspecified')


def _rule_knowledge_requested(query):
    # Keep the existing function as the single rule implementation. Import
    # lazily because react_agent imports this module for report resolution.
    from agent.react_agent import _knowledge_requested
    return _knowledge_requested(query)


def _knowledge_excluded(query):
    return bool(re.search(r'(?:不要|不必|无需|不用|不需要|别|禁止)\s*'
                          r'(?:再|额外|另外)?\s*(?:说明|解释|介绍|阐明|讲解)', query))


def _previous_from_history(history_queries, known_fields, fallback_month):
    """Recover the same absolute selector state when no saved intent exists."""
    previous = ReportIntent()
    for query in history_queries:
        if isinstance(query, str):
            updated = resolve_report_intent(query, known_fields=known_fields,
                                            fallback_month=fallback_month, previous_intent=previous)
            if updated.fields or updated.target_month or updated.limited or updated.compare:
                previous = updated
    return previous


def resolve_turn_intent(query, *, history_queries=(), previous_intent=None,
                        known_fields=(), fallback_month=None, today=None, run=None,
                        mode=None, llm_history_queries=None):
    """Select only; lookup identity, permission and facts remain caller-owned.

    history_queries is the legacy rule replay view. Agent callers with a saved
    absolute intent may supply a separate llm_history_queries user-text view,
    avoiding a second relative-month replay while retaining extraction anchors.
    """
    started = time.monotonic()
    history_queries, known_fields = tuple(history_queries), tuple(dict.fromkeys(known_fields))
    # Always run the unchanged baseline with exactly the caller's old inputs.
    rule = resolve_report_intent(query, history_queries, known_fields=known_fields,
                                 fallback_month=fallback_month, previous_intent=previous_intent)
    explicit_scope = _explicit_scope(query)
    rule_scope = _rule_final_scope(query, rule)
    rule_knowledge = _rule_knowledge_requested(query)
    cfg = load_intent_config()
    if mode is not None:
        cfg = replace(cfg, mode=mode)
    run = run or current_run()

    def result(intent=rule, knowledge=rule_knowledge, *, source='rule', reason=None,
               conflicts=(), proposal=None, final_scope=rule_scope or 'unspecified',
               final_excluded_fields=()):
        if run is not None:
            run.check()
        trace = {'mode': cfg.mode, 'source': source, 'fallback_reason': reason,
                 'conflicts': list(dict.fromkeys(conflicts)),
                 'latency_ms': round((time.monotonic() - started) * 1000, 3)}
        if run is not None:
            run.note('intent_resolved', **trace)
        return TurnIntentResult(intent, knowledge, trace, proposal,
                                final_scope, tuple(final_excluded_fields))

    if cfg.mode == 'rule':
        return result()
    today = today if today is not None else date.today()
    run = run or RunContext()
    run.check()
    # Optional calls must never turn an already exhausted budget into a
    # terminal BudgetExceeded, nor consume the last few seconds of a turn.
    if run.remaining_calls('model') < 1:
        return result(reason='model_budget')
    if run.deadline - run.clock() < cfg.timeout_seconds + 5:
        return result(reason='time_budget')
    llm_history = history_queries if llm_history_queries is None else tuple(llm_history_queries)
    bounded = bounded_history_queries(llm_history, cfg)
    # A legacy/component caller may supply user history before any absolute
    # intent was saved. Its last resolved month must precede this turn's lookup;
    # otherwise V7 could shift the already queried target a second time.
    effective_previous = previous_intent
    if effective_previous is None and llm_history:
        effective_previous = _previous_from_history(llm_history, known_fields, fallback_month)
    try:
        proposal = parse_turn_intent(query, history_queries=bounded,
                                     previous_intent=effective_previous, known_fields=known_fields,
                                     today=today, fallback_month=fallback_month, run=run, cfg=cfg)
    except InvalidIntentProposal:
        return result(reason='invalid_proposal', conflicts=('structure_invalid',))
    except ContextBudgetExceeded:
        return result(reason='context_budget')
    except CallTimeout:
        run.check()  # Only a local optional wait timeout is recoverable.
        return result(reason='model_timeout')
    except CircuitOpen:
        return result(reason='circuit_open')
    except DependencyUnavailable:
        return result(reason='model_error')
    except RuntimeControlError:
        raise
    except Exception:
        run.check()
        # Commit checks may raise non-runtime source-access errors; validate
        # again so these cannot disappear into an optional model fallback.
        run.validate_commit_checks()
        return result(reason='model_error')

    checked = validate_proposal(
        proposal, query=query, history_queries=bounded, previous_intent=effective_previous,
        known_fields=known_fields, fallback_month=fallback_month, today=today, rule_intent=rule,
        mode=cfg.mode)
    if checked.rejected:
        return result(reason='task_type_conflict', conflicts=checked.conflicts)
    had_fields = bool(proposal.fields)
    proposal, conflicts = checked.proposal, list(checked.conflicts)
    if cfg.mode == 'hybrid' and explicit_scope is not None and explicit_scope != proposal.scope:
        updates = {'scope': explicit_scope}
        if explicit_scope == 'full_report':
            updates['fields'] = []
        proposal = proposal.model_copy(update=updates)
        conflicts.append('scope_rule_override')
    limited = (proposal.scope == 'only_listed' or
               proposal.scope == 'unspecified' and bool(proposal.fields))
    full = proposal.scope == 'full_report'
    knowledge = bool(proposal.knowledge_question.strip())
    if cfg.mode == 'hybrid':
        if _knowledge_excluded(query) and knowledge:
            knowledge = False
            conflicts.append('knowledge_rule_override')
    excluded = set(proposal.excluded_fields)
    if full:
        # The legacy renderer has no exclusion slot. Explicit remaining
        # catalog fields prevent a full report from reintroducing exclusions.
        fields = tuple(field for field in known_fields if field not in excluded) if excluded else ()
        if excluded and not fields:
            limited = True  # Empty fields must never expand back to all data.
    else:
        fields = tuple(dict.fromkeys(
            item.field if item.field is not None else item.mention for item in proposal.fields))
        if not fields and cfg.mode == 'hybrid':
            # Field validation can remove all items. Keep the baseline's safe
            # selectors rather than accidentally expanding an unspecified list.
            fields = tuple(field for field in rule.fields if field not in excluded)
            if fields:
                conflicts.append('fields_rule_fallback')
            limited = limited or rule.limited or had_fields
    intent = ReportIntent(fields=fields, target_month=proposal.target_month,
                          comparison_month=proposal.baseline_month, compare=proposal.compare,
                          limited=limited, invalid_month=checked.invalid_month,
                          unresolved_month=checked.unresolved_month)
    return result(intent, knowledge, source='merged' if conflicts else 'llm',
                  conflicts=conflicts, proposal=proposal, final_scope=proposal.scope,
                  final_excluded_fields=proposal.excluded_fields)
