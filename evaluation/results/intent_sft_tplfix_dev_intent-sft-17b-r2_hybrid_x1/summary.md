# Intent component evaluation: hybrid / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 52.50% | 15 | 0.00% | 1.3797 | 1.8863 | 1.8863 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 52.50% | 52.50% |
| dangerous | 15.0000 | 15.0000 |
| dangerous_count | 15.0000 | 15.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 1.3797 | 1.3797 |
| latency_all_p95 | 1.8863 | 1.8863 |
| latency_successful_p50 | 1.3797 | 1.3797 |
| latency_successful_p95 | 1.8863 | 1.8863 |
| slot_fields_accuracy | 90.00% | 90.00% |
| slot_unknown_fields_accuracy | 97.50% | 97.50% |
| slot_requested_field_order_accuracy | 90.00% | 90.00% |
| slot_target_month_accuracy | 97.50% | 97.50% |
| slot_comparison_month_accuracy | 65.00% | 65.00% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 100.00% | 100.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 4.0000 | 4.0000 |
| other_error | 0.0000 | 0.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 15, "wrong_scope": 0, "safe_fail": 4, "other_error": 0}

Execution states: {"ok": 40}

Conflict counts: {"exclusion_not_in_text": 4, "field_not_in_catalog": 8, "fields_rule_fallback": 1, "mention_unanchored_kept": 2, "month_unsupported": 1, "negated_field_selected": 2, "negated_month_selected": 1, "no_anchor": 1, "relative_month_recomputed": 3}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 1, "exact_accuracy": 1.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"exclusion_not_in_text": 1, "no_anchor": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 1.2741031000041403, "p95": 1.2741031000041403}, "successful": {"count": 1, "missing_count": 0, "p50": 1.2741031000041403, "p95": 1.2741031000041403}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 20, "exact_accuracy": 0.5128205128205128, "slot_accuracy": {"fields": 0.8974358974358975, "unknown_fields": 0.9743589743589743, "requested_field_order": 0.8974358974358975, "target_month": 0.9743589743589743, "comparison_month": 0.6410256410256411, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 15, "wrong_scope": 0, "safe_fail": 4, "other_error": 0}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"exclusion_not_in_text": 3, "field_not_in_catalog": 8, "fields_rule_fallback": 1, "mention_unanchored_kept": 2, "month_unsupported": 1, "negated_field_selected": 2, "negated_month_selected": 1, "relative_month_recomputed": 3}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.3839784000010695, "p95": 1.9553300999978092}, "successful": {"count": 39, "missing_count": 0, "p50": 1.3839784000010695, "p95": 1.9553300999978092}}}
