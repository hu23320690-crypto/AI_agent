# Intent component evaluation: llm_only / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.00% | 8 | 100.00% | 0.8957 | 2.1368 | missing |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 0.00% | 0.00% |
| dangerous | 8.0000 | 8.0000 |
| dangerous_count | 8.0000 | 8.0000 |
| fallback_count | 40.0000 | 40.0000 |
| fallback_rate | 100.00% | 100.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 0.8957 | 0.8957 |
| latency_all_p95 | 2.1368 | 2.1368 |
| latency_successful_p50 | missing | missing |
| latency_successful_p95 | missing | missing |
| slot_fields_accuracy | 65.00% | 65.00% |
| slot_unknown_fields_accuracy | 82.50% | 82.50% |
| slot_requested_field_order_accuracy | 60.00% | 60.00% |
| slot_target_month_accuracy | 50.00% | 50.00% |
| slot_comparison_month_accuracy | 82.50% | 82.50% |
| slot_compare_accuracy | 92.50% | 92.50% |
| slot_scope_accuracy | 85.00% | 85.00% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 100.00% | 100.00% |
| wrong_scope | 6.0000 | 6.0000 |
| safe_fail | 15.0000 | 15.0000 |
| other_error | 11.0000 | 11.0000 |
| execution_failure_count | 40.0000 | 40.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 8, "wrong_scope": 6, "safe_fail": 15, "other_error": 11}

Execution states: {"error": 40}

Conflict counts: {"structure_invalid": 40}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 1}, "execution_status_counts": {"error": 1}, "execution_failure_count": 1, "fallback_count": 1, "fallback_rate": 1.0, "conflict_counts": {"structure_invalid": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.6788882999971975, "p95": 0.6788882999971975}, "successful": {"count": 0, "missing_count": 0, "p50": null, "p95": null}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 0.6410256410256411, "unknown_fields": 0.8205128205128205, "requested_field_order": 0.5897435897435898, "target_month": 0.48717948717948717, "comparison_month": 0.8205128205128205, "compare": 0.9230769230769231, "scope": 0.8461538461538461, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 8, "wrong_scope": 6, "safe_fail": 15, "other_error": 10}, "execution_status_counts": {"error": 39}, "execution_failure_count": 39, "fallback_count": 39, "fallback_rate": 1.0, "conflict_counts": {"structure_invalid": 39}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 0.907960800017463, "p95": 2.772002399986377}, "successful": {"count": 0, "missing_count": 0, "p50": null, "p95": null}}}
