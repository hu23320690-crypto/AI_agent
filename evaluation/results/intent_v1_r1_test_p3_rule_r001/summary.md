# Intent component evaluation: rule / test

Planned records: 100; repeats: 1.

| Repeat | Exact | Dangerous | Fallback | p50 all (s) | p95 all (s) | p95 successful (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 16.00% | 13 | 0.00% | 0.0011 | 0.0015 | 0.0015 |

| Metric | Mean | Worst repeat |
| --- | ---: | ---: |
| exact_accuracy | 16.00% | 16.00% |
| dangerous | 13.0000 | 13.0000 |
| dangerous_count | 13.0000 | 13.0000 |
| fallback_count | 0.0000 | 0.0000 |
| fallback_rate | 0.00% | 0.00% |
| budget_skip_count | 0.0000 | 0.0000 |
| budget_skip_rate | 0.00% | 0.00% |
| extra_model_calls | 0.0000 | 0.0000 |
| latency_all_p50 | 0.0011 | 0.0011 |
| latency_all_p95 | 0.0015 | 0.0015 |
| latency_successful_p50 | 0.0011 | 0.0011 |
| latency_successful_p95 | 0.0015 | 0.0015 |
| slot_fields_accuracy | 60.00% | 60.00% |
| slot_unknown_fields_accuracy | 65.00% | 65.00% |
| slot_requested_field_order_accuracy | 48.00% | 48.00% |
| slot_target_month_accuracy | 72.00% | 72.00% |
| slot_comparison_month_accuracy | 86.00% | 86.00% |
| slot_compare_accuracy | 92.00% | 92.00% |
| slot_scope_accuracy | 91.00% | 91.00% |
| slot_knowledge_requested_accuracy | 95.00% | 95.00% |
| slot_unresolved_month_accuracy | 94.00% | 94.00% |
| wrong_scope | 9.0000 | 9.0000 |
| safe_fail | 48.0000 | 48.0000 |
| other_error | 14.0000 | 14.0000 |
| execution_failure_count | 0.0000 | 0.0000 |

All planned records remain in denominators. Slot rates measure final semantic selectors; overall passes additionally require execution success.

Severity: {"dangerous": 13, "wrong_scope": 9, "safe_fail": 48, "other_error": 14}

Execution states: {"ok": 100}

Conflict counts: {}

Budget skips: 0; extra model attempts: 0.

Latency: nearest-rank ceil(p*n), all states and successful execution states separately. Missing latency observations: 0.
