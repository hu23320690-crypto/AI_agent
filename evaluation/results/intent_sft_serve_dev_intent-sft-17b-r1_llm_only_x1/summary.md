# Intent component evaluation: llm_only / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 65.00% | 8 | 0.00% | 0.9148 | 1.1897 | 1.1897 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 65.00% | 65.00% |
| dangerous | 8.0000 | 8.0000 |
| dangerous_count | 8.0000 | 8.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 0.9148 | 0.9148 |
| latency_all_p95 | 1.1897 | 1.1897 |
| latency_successful_p50 | 0.9148 | 0.9148 |
| latency_successful_p95 | 1.1897 | 1.1897 |
| slot_fields_accuracy | 92.50% | 92.50% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 90.00% | 90.00% |
| slot_target_month_accuracy | 90.00% | 90.00% |
| slot_comparison_month_accuracy | 82.50% | 82.50% |
| slot_compare_accuracy | 95.00% | 95.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 100.00% | 100.00% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 3.0000 | 3.0000 |
| other_error | 3.0000 | 3.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 8, "wrong_scope": 0, "safe_fail": 3, "other_error": 3}

Execution states: {"ok": 40}

Conflict counts: {"field_not_in_catalog": 9}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 1, "exact_accuracy": 1.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.7983562999870628, "p95": 0.7983562999870628}, "successful": {"count": 1, "missing_count": 0, "p50": 0.7983562999870628, "p95": 0.7983562999870628}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 25, "exact_accuracy": 0.6410256410256411, "slot_accuracy": {"fields": 0.9230769230769231, "unknown_fields": 0.8974358974358975, "requested_field_order": 0.8974358974358975, "target_month": 0.8974358974358975, "comparison_month": 0.8205128205128205, "compare": 0.9487179487179487, "scope": 1.0, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 8, "wrong_scope": 0, "safe_fail": 3, "other_error": 3}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"field_not_in_catalog": 9}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 0.9179996000020765, "p95": 1.1921265000128187}, "successful": {"count": 39, "missing_count": 0, "p50": 0.9179996000020765, "p95": 1.1921265000128187}}}
