# Intent component evaluation: llm_only / dev

Planned records: 40; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 50.00% | 3 | 40.00% | 0.7345 | 0.9881 | 0.9566 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 50.00% | 50.00% |
| dangerous | 3.0000 | 3.0000 |
| dangerous_count | 3.0000 | 3.0000 |
| fallback_count | 16.0000 | 16.0000 |
| fallback_rate | 40.00% | 40.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 40.0000 | 40.0000 |
| latency_all_p50 | 0.7345 | 0.7345 |
| latency_all_p95 | 0.9881 | 0.9881 |
| latency_successful_p50 | 0.7331 | 0.7331 |
| latency_successful_p95 | 0.9566 | 0.9566 |
| slot_fields_accuracy | 87.50% | 87.50% |
| slot_unknown_fields_accuracy | 90.00% | 90.00% |
| slot_requested_field_order_accuracy | 85.00% | 85.00% |
| slot_target_month_accuracy | 82.50% | 82.50% |
| slot_comparison_month_accuracy | 95.00% | 95.00% |
| slot_compare_accuracy | 97.50% | 97.50% |
| slot_scope_accuracy | 97.50% | 97.50% |
| slot_knowledge_requested_accuracy | 97.50% | 97.50% |
| slot_unresolved_month_accuracy | 100.00% | 100.00% |
| wrong_scope | 1.0000 | 1.0000 |
| safe_fail | 8.0000 | 8.0000 |
| other_error | 8.0000 | 8.0000 |
| execution_failure_count | 16.0000 | 16.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 3, "wrong_scope": 1, "safe_fail": 8, "other_error": 8}

Execution states: {"ok": 24, "error": 16}

Conflict counts: {"field_not_in_catalog": 1, "structure_invalid": 16}

Budget skips: 0; extra model attempts: 40.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.

SCORING_AMENDMENT_01: ID021 is retained in the full dev denominator and reported separately; it is not used to tune prompts.

Affected: {"planned_count": 1, "exact_count": 0, "exact_accuracy": 0.0, "slot_accuracy": {"fields": 1.0, "unknown_fields": 1.0, "requested_field_order": 1.0, "target_month": 1.0, "comparison_month": 1.0, "compare": 1.0, "scope": 1.0, "knowledge_requested": 1.0, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 0, "wrong_scope": 0, "safe_fail": 0, "other_error": 1}, "execution_status_counts": {"error": 1}, "execution_failure_count": 1, "fallback_count": 1, "fallback_rate": 1.0, "conflict_counts": {"structure_invalid": 1}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 1, "latency_seconds": {"all": {"count": 1, "missing_count": 0, "p50": 0.686225600016769, "p95": 0.686225600016769}, "successful": {"count": 0, "missing_count": 0, "p50": null, "p95": null}}}

Excluding affected (auxiliary): {"planned_count": 39, "exact_count": 20, "exact_accuracy": 0.5128205128205128, "slot_accuracy": {"fields": 0.8717948717948718, "unknown_fields": 0.8974358974358975, "requested_field_order": 0.8461538461538461, "target_month": 0.8205128205128205, "comparison_month": 0.9487179487179487, "compare": 0.9743589743589743, "scope": 0.9743589743589743, "knowledge_requested": 0.9743589743589743, "unresolved_month": 1.0}, "severity_counts": {"dangerous": 3, "wrong_scope": 1, "safe_fail": 8, "other_error": 7}, "execution_status_counts": {"ok": 24, "error": 15}, "execution_failure_count": 15, "fallback_count": 15, "fallback_rate": 0.38461538461538464, "conflict_counts": {"field_not_in_catalog": 1, "structure_invalid": 15}, "budget_skip_count": 0, "budget_skip_rate": 0.0, "extra_model_calls": 39, "latency_seconds": {"all": {"count": 39, "missing_count": 0, "p50": 0.7446894999884535, "p95": 1.059986000007484}, "successful": {"count": 24, "missing_count": 0, "p50": 0.7331083999888506, "p95": 0.9565861999872141}}}
