# Intent component evaluation: hybrid / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 65.00% | 2 | 0.00% | 1.6351 | 1.9913 | 1.9913 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 65.00% | 65.00% |
| dangerous | 2.0000 | 2.0000 |
| dangerous_count | 2.0000 | 2.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 1.6351 | 1.6351 |
| latency_all_p95 | 1.9913 | 1.9913 |
| latency_successful_p50 | 1.6351 | 1.6351 |
| latency_successful_p95 | 1.9913 | 1.9913 |
| slot_fields_accuracy | 87.50% | 87.50% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 77.50% | 77.50% |
| slot_target_month_accuracy | 90.00% | 90.00% |
| slot_comparison_month_accuracy | 97.50% | 97.50% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 97.50% | 97.50% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 8.0000 | 8.0000 |
| other_error | 4.0000 | 4.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 2, "wrong_scope": 0, "safe_fail": 8, "other_error": 4}

Execution states: {"ok": 40}

Conflict counts: {"exclusion_not_in_text": 4, "field_not_in_catalog": 2, "mention_not_in_text": 3, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 2, "relative_month_recomputed": 1, "scope_rule_override": 1}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 0.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 0.0}, "severity_counts": {"dangerous": 1, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 1.545847400000639, "p95": 1.545847400000639}, "successful": {"count": 1, "missing_count": 0, "p50": 1.545847400000639, "p95": 1.545847400000639}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 26, "exact_accuracy": 0.6666666666666666, "slot_accuracy": {"fields": 0.8717948717948718, "unknown_fields": 0.8974358974358975, "requested_field_order": 0.7692307692307693, "target_month": 0.9230769230769231, "comparison_month": 0.9743589743589743, "compare": 1.0, "scope": 1.0, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 1, "wrong_scope": 0, "safe_fail": 8, "other_error": 4}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"exclusion_not_in_text": 4, "field_not_in_catalog": 2, "mention_not_in_text": 3, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 2, "relative_month_recomputed": 1, "scope_rule_override": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.6372499999997672, "p95": 2.0679352000006475}, "successful": {"count": 39, "missing_count": 0, "p50": 1.6372499999997672, "p95": 2.0679352000006475}}}
