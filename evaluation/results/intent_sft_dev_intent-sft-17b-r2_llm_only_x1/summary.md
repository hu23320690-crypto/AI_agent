# Intent component evaluation: llm_only / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 90.00% | 1 | 0.00% | 1.0640 | 1.5101 | 1.5101 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 90.00% | 90.00% |
| dangerous | 1.0000 | 1.0000 |
| dangerous_count | 1.0000 | 1.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 1.0640 | 1.0640 |
| latency_all_p95 | 1.5101 | 1.5101 |
| latency_successful_p50 | 1.0640 | 1.0640 |
| latency_successful_p95 | 1.5101 | 1.5101 |
| slot_fields_accuracy | 97.50% | 97.50% |
| slot_unknown_fields_accuracy | 97.50% | 97.50% |
| slot_requested_field_order_accuracy | 97.50% | 97.50% |
| slot_target_month_accuracy | 100.00% | 100.00% |
| slot_comparison_month_accuracy | 100.00% | 100.00% |
| slot_compare_accuracy | 97.50% | 97.50% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 97.50% | 97.50% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 0.0000 | 0.0000 |
| other_error | 3.0000 | 3.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 1, "wrong_scope": 0, "safe_fail": 0, "other_error": 3}

Execution states: {"ok": 40}

Conflict counts: {}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 0.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 1}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.9347157000011066, "p95": 0.9347157000011066}, "successful": {"count": 1, "missing_count": 0, "p50": 0.9347157000011066, "p95": 0.9347157000011066}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 36, "exact_accuracy": 0.9230769230769231, "slot_accuracy": {"fields": 0.9743589743589743, "unknown_fields": 0.9743589743589743, "requested_field_order": 0.9743589743589743, "target_month": 1.0, "comparison_month": 1.0, "compare": 0.9743589743589743, "scope": 1.0, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 1, "wrong_scope": 0, "safe_fail": 0, "other_error": 2}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.064913099995465, "p95": 1.5520013999921503}, "successful": {"count": 39, "missing_count": 0, "p50": 1.064913099995465, "p95": 1.5520013999921503}}}
