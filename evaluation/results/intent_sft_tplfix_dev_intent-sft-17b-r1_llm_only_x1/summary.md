# Intent component evaluation: llm_only / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 35.00% | 19 | 0.00% | 1.2754 | 1.7785 | 1.7785 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 35.00% | 35.00% |
| dangerous | 19.0000 | 19.0000 |
| dangerous_count | 19.0000 | 19.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 1.2754 | 1.2754 |
| latency_all_p95 | 1.7785 | 1.7785 |
| latency_successful_p50 | 1.2754 | 1.2754 |
| latency_successful_p95 | 1.7785 | 1.7785 |
| slot_fields_accuracy | 90.00% | 90.00% |
| slot_unknown_fields_accuracy | 92.50% | 92.50% |
| slot_requested_field_order_accuracy | 87.50% | 87.50% |
| slot_target_month_accuracy | 80.00% | 80.00% |
| slot_comparison_month_accuracy | 52.50% | 52.50% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 97.50% | 97.50% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 6.0000 | 6.0000 |
| other_error | 1.0000 | 1.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 19, "wrong_scope": 0, "safe_fail": 6, "other_error": 1}

Execution states: {"ok": 40}

Conflict counts: {"field_not_in_catalog": 9}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 0.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 1}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 1.2201823999930639, "p95": 1.2201823999930639}, "successful": {"count": 1, "missing_count": 0, "p50": 1.2201823999930639, "p95": 1.2201823999930639}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 14, "exact_accuracy": 0.358974358974359, "slot_accuracy": {"fields": 0.8974358974358975, "unknown_fields": 0.9230769230769231, "requested_field_order": 0.8717948717948718, "target_month": 0.7948717948717948, "comparison_month": 0.5128205128205128, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 19, "wrong_scope": 0, "safe_fail": 6, "other_error": 0}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"field_not_in_catalog": 9}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.3116502999910153, "p95": 1.821721799991792}, "successful": {"count": 39, "missing_count": 0, "p50": 1.3116502999910153, "p95": 1.821721799991792}}}
