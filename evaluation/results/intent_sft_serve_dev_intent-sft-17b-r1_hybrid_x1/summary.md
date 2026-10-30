# Intent component evaluation: hybrid / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 65.00% | 6 | 0.00% | 0.9236 | 1.1831 | 1.1831 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 65.00% | 65.00% |
| dangerous | 6.0000 | 6.0000 |
| dangerous_count | 6.0000 | 6.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 0.9236 | 0.9236 |
| latency_all_p95 | 1.1831 | 1.1831 |
| latency_successful_p50 | 0.9236 | 0.9236 |
| latency_successful_p95 | 1.1831 | 1.1831 |
| slot_fields_accuracy | 92.50% | 92.50% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 90.00% | 90.00% |
| slot_target_month_accuracy | 87.50% | 87.50% |
| slot_comparison_month_accuracy | 82.50% | 82.50% |
| slot_compare_accuracy | 95.00% | 95.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 95.00% | 95.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 5.0000 | 5.0000 |
| other_error | 3.0000 | 3.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 6, "wrong_scope": 0, "safe_fail": 5, "other_error": 3}

Execution states: {"ok": 40}

Conflict counts: {"anchor_lookup_consistency": 1, "exclusion_not_in_text": 1, "field_not_in_catalog": 9, "month_unsupported": 2, "negated_field_selected": 1, "no_anchor": 3}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 1, "exact_accuracy": 1.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"no_anchor": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.8288582000241149, "p95": 0.8288582000241149}, "successful": {"count": 1, "missing_count": 0, "p50": 0.8288582000241149, "p95": 0.8288582000241149}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 25, "exact_accuracy": 0.6410256410256411, "slot_accuracy": {"fields": 0.9230769230769231, "unknown_fields": 0.8974358974358975, "requested_field_order": 0.8974358974358975, "target_month": 0.8717948717948718, "comparison_month": 0.8205128205128205, "compare": 0.9487179487179487, "scope": 1.0, "knowledge_requested": 0.9743589743589743, "unresolved_month": 0.9487179487179487}, "severity_counts": {"dangerous": 6, "wrong_scope": 0, "safe_fail": 5, "other_error": 3}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"anchor_lookup_consistency": 1, "exclusion_not_in_text": 1, "field_not_in_catalog": 9, "month_unsupported": 2, "negated_field_selected": 1, "no_anchor": 2}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 0.9269136999791954, "p95": 1.1898292000114452}, "successful": {"count": 39, "missing_count": 0, "p50": 0.9269136999791954, "p95": 1.1898292000114452}}}
