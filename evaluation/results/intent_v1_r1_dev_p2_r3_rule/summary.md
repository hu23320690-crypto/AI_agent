# Intent component evaluation: rule / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 25.00% | 8 | 0.00% | 0.0011 | 0.0019 | 0.0019 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 25.00% | 25.00% |
| dangerous | 8.0000 | 8.0000 |
| dangerous_count | 8.0000 | 8.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 0.0000 | 0.0000 |
| latency_all_p50 | 0.0011 | 0.0011 |
| latency_all_p95 | 0.0019 | 0.0019 |
| latency_successful_p50 | 0.0011 | 0.0011 |
| latency_successful_p95 | 0.0019 | 0.0019 |
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
| other_error | 1.0000 | 1.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 8, "wrong_scope": 6, "safe_fail": 15, "other_error": 1}

Execution states: {"ok": 40}

Conflict counts: {}

Budget skips: 0; extra model attempts: 0.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 1, "exact_accuracy": 1.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 0, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.0010905999988608528, "p95": 0.0010905999988608528}, "successful": {"count": 1, "missing_count": 0, "p50": 0.0010905999988608528, "p95": 0.0010905999988608528}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 9, "exact_accuracy": 0.23076923076923078, "slot_accuracy": {"fields": 0.6410256410256411, "unknown_fields": 0.8205128205128205, "requested_field_order": 0.5897435897435898, "target_month": 0.48717948717948717, "comparison_month": 0.8205128205128205, "compare": 0.9230769230769231, "scope": 0.8461538461538461, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 8, "wrong_scope": 6, "safe_fail": 15, "other_error": 1}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 0, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 0.0011505000002216548, "p95": 0.004215999997541076}, "successful": {"count": 39, "missing_count": 0, "p50": 0.0011505000002216548, "p95": 0.004215999997541076}}}
