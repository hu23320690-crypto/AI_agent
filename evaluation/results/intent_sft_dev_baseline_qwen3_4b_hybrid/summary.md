# Intent component evaluation: hybrid / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 80.00% | 1 | 2.50% | 0.9987 | 1.3614 | 1.3614 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 80.00% | 80.00% |
| dangerous | 1.0000 | 1.0000 |
| dangerous_count | 1.0000 | 1.0000 |
| fallback_count | 1.0000 | 1.0000 |
| fallback_rate | 2.50% | 2.50% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 0.9987 | 0.9987 |
| latency_all_p95 | 1.3614 | 1.3614 |
| latency_successful_p50 | 0.9987 | 0.9987 |
| latency_successful_p95 | 1.3614 | 1.3614 |
| slot_fields_accuracy | 95.00% | 95.00% |
| slot_unknown_fields_accuracy | 87.50% | 87.50% |
| slot_requested_field_order_accuracy | 82.50% | 82.50% |
| slot_target_month_accuracy | 95.00% | 95.00% |
| slot_comparison_month_accuracy | 100.00% | 100.00% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 97.50% | 97.50% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 97.50% | 97.50% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 1.0000 | 1.0000 |
| other_error | 5.0000 | 5.0000 |
| execution_failure_count | 1.0000 | 1.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 1, "wrong_scope": 1, "safe_fail": 1, "other_error": 5}

Execution states: {"timeout": 1, "ok": 39}

Conflict counts: {"mention_unanchored_kept": 3, "negated_field_selected": 2, "qualifier_dropped": 1}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 0.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 0.0}, "severity_counts": {"dangerous": 1, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.8476151000068057, "p95": 0.8476151000068057}, "successful": {"count": 1, "missing_count": 0, "p50": 0.8476151000068057, "p95": 0.8476151000068057}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 32, "exact_accuracy": 0.8205128205128205, "slot_accuracy": {"fields": 0.9487179487179487, "unknown_fields": 0.8717948717948718, "requested_field_order": 0.8205128205128205, "target_month": 0.9743589743589743, "comparison_month": 1.0, "compare": 1.0, "scope": 0.9743589743589743, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 1, "safe_fail": 1, "other_error": 5}, "execution_status_counts": {"timeout": 1, "ok": 38}, "execution_failure_count": 1, "fallback_count": 1, "fallback_rate": 0.02564102564102564, "conflict_counts": {"mention_unanchored_kept": 3, "negated_field_selected": 2, "qualifier_dropped": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.0152377000049455, "p95": 7.048498000003747}, "successful": {"count": 38, "missing_count": 0, "p50": 0.9987201999902027, "p95": 1.3613710999925388}}}
