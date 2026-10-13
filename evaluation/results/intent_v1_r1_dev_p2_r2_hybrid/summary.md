# Intent component evaluation: hybrid / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 75.00% | 3 | 0.00% | 1.2319 | 1.7835 | 1.7835 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 75.00% | 75.00% |
| dangerous | 3.0000 | 3.0000 |
| dangerous_count | 3.0000 | 3.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 1.2319 | 1.2319 |
| latency_all_p95 | 1.7835 | 1.7835 |
| latency_successful_p50 | 1.2319 | 1.2319 |
| latency_successful_p95 | 1.7835 | 1.7835 |
| slot_fields_accuracy | 92.50% | 92.50% |
| slot_unknown_fields_accuracy | 95.00% | 95.00% |
| slot_requested_field_order_accuracy | 87.50% | 87.50% |
| slot_target_month_accuracy | 90.00% | 90.00% |
| slot_comparison_month_accuracy | 97.50% | 97.50% |
| slot_compare_accuracy | 100.00% | 100.00% |
| slot_scope_accuracy | 100.00% | 100.00% |
| slot_knowledge_requested_accuracy | 100.00% | 100.00% |
| slot_unresolved_month_accuracy | 97.50% | 97.50% |
| wrong_scope | 0.0000 | 0.0000 |
| safe_fail | 5.0000 | 5.0000 |
| other_error | 2.0000 | 2.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 3, "wrong_scope": 0, "safe_fail": 5, "other_error": 2}

Execution states: {"ok": 40}

Conflict counts: {"mention_not_in_text": 2, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 1}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 0.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 0.0}, "severity_counts": {"dangerous": 1, "wrong_scope": 0, "safe_fail": 0, "other_error": 0}, "execution_status_counts": {"ok": 1}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 1.0425747999997839, "p95": 1.0425747999997839}, "successful": {"count": 1, "missing_count": 0, "p50": 1.0425747999997839, "p95": 1.0425747999997839}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 30, "exact_accuracy": 0.7692307692307693, "slot_accuracy": {"fields": 0.9230769230769231, "unknown_fields": 0.9487179487179487, "requested_field_order": 0.8717948717948718, "target_month": 0.9230769230769231, "comparison_month": 0.9743589743589743, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 2, "wrong_scope": 0, "safe_fail": 5, "other_error": 2}, "execution_status_counts": {"ok": 39}, "execution_failure_count": 0, "fallback_count": 0, "fallback_rate": 0.0, "conflict_counts": {"mention_not_in_text": 2, "month_unsupported": 3, "negated_field_selected": 1, "qualifier_dropped": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 1.2371046000007482, "p95": 1.8040128999982699}, "successful": {"count": 39, "missing_count": 0, "p50": 1.2371046000007482, "p95": 1.8040128999982699}}}
